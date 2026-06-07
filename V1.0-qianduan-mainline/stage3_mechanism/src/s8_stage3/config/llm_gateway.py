"""LLM 网关：统一封装所有 LLM 调用。

优先使用 response_format=json_schema + strict=True（Structured Outputs）；
若模型/endpoint 不支持，回退到 json_object + repair。
业务层不得直接发 HTTP 请求，统一走此网关。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Type

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    content: str = ""
    parsed: dict = field(default_factory=dict)
    usage: LLMUsage = field(default_factory=LLMUsage)
    model: str = ""
    cached: bool = False
    raw_response: str = ""
    error: Optional[str] = None


@dataclass
class LLMCallRecord:
    step: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    success: bool
    cache_hit: bool
    cache_key: str = ""
    temperature: Optional[float] = None
    seed: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ---------------------------------------------------------------------------
# 缓存 key
# ---------------------------------------------------------------------------

def _compute_cache_key(
    model: str,
    step: str,
    messages: list[dict],
    schema_name: str = "",
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
) -> str:
    payload = json.dumps(
        {
            "model": model,
            "step": step,
            "messages": messages,
            "schema": schema_name,
            "temperature": temperature,
            "seed": seed,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


# ---------------------------------------------------------------------------
# JSON 修复（兜底）
# ---------------------------------------------------------------------------

def _try_repair_json(text: str) -> dict:
    """尝试从非标准字符串中提取 JSON，仅在 Structured Outputs 不可用时触发。"""
    text = text.strip()
    # 去除 markdown 代码块
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
    text = text.strip()

    # 直接尝试
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 提取第一个 {...}
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Cannot parse JSON from LLM response: {text[:300]!r}")


# ---------------------------------------------------------------------------
# 主网关
# ---------------------------------------------------------------------------

class LLMGateway:
    """统一 LLM 访问网关，支持 mock / live 双模式。"""

    def __init__(self, settings, model_registry):
        self._settings = settings
        self._registry = model_registry
        self._call_records: list[LLMCallRecord] = []
        self._call_count: int = 0

        # 懒加载 openai client
        self._client = None
        self._mock_fn = None

        # 缓存目录
        self._cache_dir = settings.cache_dir / "llm_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        (self._cache_dir / "_raw_snapshots").mkdir(exist_ok=True)

        # 日志目录
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = settings.logs_dir / "llm_calls.jsonl"

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def is_mock(self) -> bool:
        return self._settings.llm_mode == "mock"

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def call_log(self) -> list[LLMCallRecord]:
        return list(self._call_records)

    # ------------------------------------------------------------------
    # 模型路由
    # ------------------------------------------------------------------

    def resolve_model_for_step(self, step_name: str, tier: Optional[str] = None) -> str:
        return self._registry.resolve_for_step(step_name, override_tier=tier)

    # ------------------------------------------------------------------
    # 预算检查
    # ------------------------------------------------------------------

    def _check_budget(self) -> None:
        if self._call_count >= self._settings.max_llm_calls_per_run:
            raise RuntimeError(
                f"LLM budget exceeded: {self._call_count} >= {self._settings.max_llm_calls_per_run} calls"
            )

    # ------------------------------------------------------------------
    # 缓存读写
    # ------------------------------------------------------------------

    def _read_cache(self, key: str) -> Optional[dict]:
        if not self._settings.enable_cache:
            return None
        path = self._cache_dir / f"{key}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _write_cache(self, key: str, data: dict, raw: str = "") -> None:
        if not self._settings.enable_cache:
            return
        path = self._cache_dir / f"{key}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if raw:
            raw_path = self._cache_dir / "_raw_snapshots" / f"{key}.txt"
            raw_path.write_text(raw, encoding="utf-8")

    # ------------------------------------------------------------------
    # 调用记录
    # ------------------------------------------------------------------

    def _record_call(self, record: LLMCallRecord) -> None:
        self._call_records.append(record)
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 主调用入口
    # ------------------------------------------------------------------

    def chat(self, messages: list[dict], step: str = "", model: Optional[str] = None) -> LLMResponse:
        """返回原始文本响应。"""
        if not model:
            model = self.resolve_model_for_step(step)
        if self.is_mock:
            return self._mock_chat(messages, step, model)
        return self._live_chat(messages, step, model)

    def chat_json(
        self,
        messages: list[dict],
        step: str = "",
        model: Optional[str] = None,
        output_schema: Optional[Type] = None,
    ) -> dict:
        """返回解析后的 JSON dict。

        output_schema: Pydantic 模型类（可选）。提供时，网关尝试使用
        response_format=json_schema+strict=True（Structured Outputs），
        以在 API 层面约束输出格式，减少 Pydantic 层面的修复需求。
        """
        if not model:
            model = self.resolve_model_for_step(step)
        schema_name = output_schema.__name__ if output_schema else ""

        if self.is_mock:
            return self._mock_chat_json(messages, step, model)

        return self._live_chat_json(messages, step, model, output_schema, schema_name)

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    def _get_mock_fn(self):
        if self._mock_fn is None:
            from s8_stage3.mock.mock_llm import mock_chat_json
            self._mock_fn = mock_chat_json
        return self._mock_fn

    def _mock_chat(self, messages: list[dict], step: str, model: str) -> LLMResponse:
        fn = self._get_mock_fn()
        result = fn(step, messages)
        return LLMResponse(content=json.dumps(result), parsed=result, model=f"mock:{model}")

    def _mock_chat_json(self, messages: list[dict], step: str, model: str) -> dict:
        fn = self._get_mock_fn()
        result = fn(step, messages)
        self._call_count += 1
        self._record_call(LLMCallRecord(
            step=step, model=f"mock:{model}",
            prompt_tokens=0, completion_tokens=0,
            latency_ms=0, success=True, cache_hit=False,
        ))
        return result

    # ------------------------------------------------------------------
    # Live 模式
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._settings.api_key,
                    base_url=self._settings.api_base_url,
                    timeout=self._settings.timeout_seconds,
                )
            except ImportError:
                raise RuntimeError("openai package not installed. Run: pip install openai")
        return self._client

    def _live_chat_json(
        self,
        messages: list[dict],
        step: str,
        model: str,
        output_schema: Optional[Type],
        schema_name: str,
    ) -> dict:
        self._check_budget()
        temperature = getattr(self._settings, "llm_temperature", 0.0)
        seed = getattr(self._settings, "llm_seed", 0) or None
        cache_key = _compute_cache_key(model, step, messages, schema_name, temperature, seed)
        cached = self._read_cache(cache_key)
        if cached:
            self._call_count += 1
            self._record_call(LLMCallRecord(
                step=step, model=model, prompt_tokens=0, completion_tokens=0,
                latency_ms=0, success=True, cache_hit=True,
                cache_key=cache_key, temperature=temperature, seed=seed,
            ))
            return cached

        client = self._get_client()
        last_error = None
        # 若平台/设置不支持 Structured Outputs，直接跳过 json_schema，避免产生无谓的 400
        use_structured = (
            output_schema is not None
            and getattr(self._settings, "use_structured_outputs", True)
        )
        for attempt in range(self._settings.max_retries):
            t0 = time.monotonic()
            try:
                if use_structured:
                    kwargs = self._build_request_kwargs(messages, model, output_schema)
                else:
                    kwargs = self._build_request_kwargs_fallback(messages, model)
                resp = client.chat.completions.create(**kwargs)
                latency_ms = (time.monotonic() - t0) * 1000

                raw = resp.choices[0].message.content or ""
                usage = resp.usage
                prompt_tokens = usage.prompt_tokens if usage else 0
                completion_tokens = usage.completion_tokens if usage else 0

                result = self._parse_response(raw, output_schema)

                self._write_cache(cache_key, result, raw)
                self._call_count += 1
                self._record_call(LLMCallRecord(
                    step=step, model=model,
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    latency_ms=latency_ms, success=True, cache_hit=False,
                    cache_key=cache_key, temperature=temperature, seed=seed,
                ))
                return result

            except Exception as e:
                last_error = e
                latency_ms = (time.monotonic() - t0) * 1000
                err_str = str(e).lower()
                # 若 endpoint 不支持 json_schema，降级到 json_object 重试
                if use_structured and any(kw in err_str for kw in (
                    "json_schema", "response_format", "unsupported", "invalid_request"
                )):
                    logger.warning(
                        f"[LLMGateway] Structured Outputs not supported by endpoint for step={step}. "
                        "Downgrading to json_object for remaining retries."
                    )
                    use_structured = False
                    # 立即重试（不计本次 attempt）
                    continue
                logger.warning(f"[LLMGateway] attempt {attempt+1} failed for step={step}: {e}")
                self._record_call(LLMCallRecord(
                    step=step, model=model, prompt_tokens=0, completion_tokens=0,
                    latency_ms=latency_ms, success=False, cache_hit=False,
                    cache_key=cache_key, temperature=temperature, seed=seed, error=str(e),
                ))
                if attempt < self._settings.max_retries - 1:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"[LLMGateway] All retries failed for step={step}: {last_error}") from last_error

    def _build_request_kwargs(
        self,
        messages: list[dict],
        model: str,
        output_schema: Optional[Type],
    ) -> dict:
        """构造 API 请求参数。
        
        优先级：
        1. output_schema 提供时 → response_format=json_schema + strict=True（Structured Outputs）
        2. schema 构建失败时 → response_format=json_object（兜底，LLM 自由输出合法 JSON）
        3. output_schema 为 None → response_format=json_object
        """
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        self._apply_reproducibility_kwargs(kwargs)
        if output_schema is not None:
            try:
                schema = output_schema.model_json_schema()
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_schema.__name__,
                        "schema": schema,
                        "strict": True,
                    },
                }
                logger.debug(f"[LLMGateway] Using json_schema strict for {output_schema.__name__}")
            except Exception as e:
                logger.warning(
                    f"[LLMGateway] Failed to build json_schema for {output_schema}: {e}. "
                    "Falling back to json_object."
                )
                kwargs["response_format"] = {"type": "json_object"}
        else:
            kwargs["response_format"] = {"type": "json_object"}
        return kwargs

    def _build_request_kwargs_fallback(
        self,
        messages: list[dict],
        model: str,
    ) -> dict:
        """json_schema 被 endpoint 拒绝时的降级请求参数（仅用 json_object）。"""
        return {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            **self._reproducibility_kwargs(),
        }

    def _reproducibility_kwargs(self) -> dict[str, Any]:
        """返回模型调用复现参数。"""
        kwargs: dict[str, Any] = {}
        temperature = getattr(self._settings, "llm_temperature", None)
        if temperature is not None:
            kwargs["temperature"] = temperature
        seed = getattr(self._settings, "llm_seed", 0)
        if seed:
            kwargs["seed"] = seed
        return kwargs

    def _apply_reproducibility_kwargs(self, kwargs: dict[str, Any]) -> None:
        kwargs.update(self._reproducibility_kwargs())

    def _parse_response(self, raw: str, output_schema: Optional[Type]) -> dict:
        """解析 LLM 返回的原始文本为 dict。"""
        if not raw:
            raise ValueError("LLM returned empty response")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[LLMGateway] JSON parse failed, attempting repair")
            return _try_repair_json(raw)

    # ------------------------------------------------------------------
    # Smoke 测试
    # ------------------------------------------------------------------

    def smoke_chat(self) -> bool:
        """验证 endpoint 可达性，返回 True 表示成功。"""
        try:
            client = self._get_client()
            resp = client.chat.completions.create(
                model=self._registry.resolve("cheap"),
                messages=[{"role": "user", "content": "Reply with the word: ok"}],
                max_tokens=64,
            )
            content = resp.choices[0].message.content or ""
            logger.info(f"[LLMGateway] smoke_chat OK: {content!r}")
            return True
        except Exception as e:
            logger.error(f"[LLMGateway] smoke_chat FAILED: {e}")
            return False

    # ------------------------------------------------------------------
    # 成本汇总
    # ------------------------------------------------------------------

    def get_cost_summary(self) -> dict:
        total_prompt = sum(r.prompt_tokens for r in self._call_records)
        total_completion = sum(r.completion_tokens for r in self._call_records)
        successes = sum(1 for r in self._call_records if r.success)
        failures = sum(1 for r in self._call_records if not r.success)
        cache_hits = sum(1 for r in self._call_records if r.cache_hit)
        return {
            "total_calls": self._call_count,
            "successes": successes,
            "failures": failures,
            "cache_hits": cache_hits,
            "llm_temperature": getattr(self._settings, "llm_temperature", None),
            "llm_seed": getattr(self._settings, "llm_seed", 0) or None,
            "configured_models": (
                self._registry.list_configured()
                if hasattr(self._registry, "list_configured")
                else {}
            ),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "calls": [r.to_dict() for r in self._call_records],
        }
