"""
LLM Client for DeepSeek-R1
大模型通信客户端：适配 PoloAPI 平台的 DeepSeek-R1 推理模型

核心特性：
- 支持 DeepSeek-R1 的 <think>...</think> 推理输出
- 自动提取和清洗 JSON 内容
- 完整的思考过程日志记录
"""
import os
import re
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv

# 加载环境变量（override=True 确保 .env 文件优先级最高）
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMClient:
    """
    大模型通信客户端（适配 DeepSeek-R1）
    
    DeepSeek-R1 是推理模型，输出格式为：
    <think>
    详细的思考过程...
    </think>
    
    ```json
    {
        "key": "value"
    }
    ```
    
    本客户端会自动提取思考过程并清洗 JSON 内容
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None
    ):
        """
        初始化 LLM 客户端（从环境变量读取配置）
        
        Args:
            api_key: API Key，如果为 None 则从环境变量读取
            base_url: API Base URL，如果为 None 则从环境变量读取
            model: 模型名称，如果为 None 则从环境变量读取
            temperature: 温度参数，越低越稳定（0.0-2.0）
            max_tokens: 最大输出 token 数
            timeout: 请求超时时间（秒）
        """
        # 从环境变量读取配置
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://poloai.top/v1")
        self.model = model or os.getenv("LLM_MODEL", "DeepSeek-R1")
        self.temperature = temperature or float(os.getenv("LLM_TEMPERATURE", "0.2"))
        self.max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", "2000"))
        self.timeout = timeout or int(os.getenv("LLM_TIMEOUT", "60"))
        
        # 验证必需配置
        if not self.api_key:
            raise ValueError(
                "LLM_API_KEY 未设置。请在 .env 文件中配置或通过参数传入。"
            )
        
        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
        
        logger.info(
            f"LLM 客户端初始化完成 | "
            f"模型: {self.model} | "
            f"Base URL: {self.base_url} | "
            f"Temperature: {self.temperature} | "
            f"Max Tokens: {self.max_tokens}"
        )
    
    def _extract_thinking_process(self, text: str) -> Optional[str]:
        """
        提取 DeepSeek-R1 的思考过程（<think>...</think> 标签内容）
        
        Args:
            text: 原始响应文本
            
        Returns:
            思考过程文本，如果没有则返回 None
        """
        # 使用正则表达式提取 <think> 标签内容
        think_pattern = r'<think>(.*?)</think>'
        match = re.search(think_pattern, text, re.DOTALL | re.IGNORECASE)
        
        if match:
            thinking = match.group(1).strip()
            return thinking
        
        return None
    
    def _extract_json(self, text: str) -> str:
        """
        从 DeepSeek-R1 的响应中提取纯净的 JSON 内容
        
        处理逻辑：
        1. 优先提取 ```json ... ``` markdown 代码块中的内容
        2. 如果没有 markdown 块，则剔除 <think> 标签后提取 { 和 } 之间的内容
        3. 清理多余的空白字符
        
        Args:
            text: 原始响应文本
            
        Returns:
            纯净的 JSON 字符串
            
        Raises:
            ValueError: 无法提取有效的 JSON 内容
        """
        # 策略 1: 提取 ```json ... ``` 代码块
        json_block_pattern = r'```json\s*(.*?)\s*```'
        match = re.search(json_block_pattern, text, re.DOTALL | re.IGNORECASE)
        
        if match:
            json_str = match.group(1).strip()
            logger.debug(f"从 markdown 代码块提取 JSON，长度: {len(json_str)}")
            return json_str
        
        # 策略 2: 剔除 <think> 标签后提取 JSON 对象
        # 先移除所有 <think>...</think> 内容
        cleaned_text = re.sub(
            r'<think>.*?</think>', 
            '', 
            text, 
            flags=re.DOTALL | re.IGNORECASE
        )
        
        # 提取第一个完整的 JSON 对象（从 { 到匹配的 }）
        json_obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        match = re.search(json_obj_pattern, cleaned_text, re.DOTALL)
        
        if match:
            json_str = match.group(0).strip()
            logger.debug(f"从文本中提取 JSON 对象，长度: {len(json_str)}")
            return json_str
        
        # 策略 3: 尝试提取任何 ``` 代码块（不限于 json 标记）
        code_block_pattern = r'```\w*\s*(.*?)\s*```'
        match = re.search(code_block_pattern, text, re.DOTALL)
        
        if match:
            json_str = match.group(1).strip()
            logger.debug(f"从通用代码块提取内容，长度: {len(json_str)}")
            return json_str
        
        # 如果所有策略都失败，抛出异常
        logger.error(f"无法从响应中提取 JSON。原始文本（前 500 字符）:\n{text[:500]}")
        raise ValueError(
            "无法从 LLM 响应中提取有效的 JSON 内容。"
            "请检查模型输出格式是否正确。"
        )
    
    def generate_json(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        retry_count: int = 3,
        completion_max_tokens: Optional[int] = None,
    ) -> str:
        """
        生成 JSON 格式的响应（适配 DeepSeek-R1）
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            retry_count: 失败重试次数
            completion_max_tokens: 本次调用的 max_tokens（None 则用实例默认值）
            
        Returns:
            纯净的 JSON 字符串（已清洗 <think> 标签）
            
        Raises:
            OpenAIError: API 调用失败
            json.JSONDecodeError: 返回的不是有效 JSON
            ValueError: 重试次数耗尽仍然失败
        """
        # 强制在 prompt 末尾附加 JSON 输出指令
        json_instruction = (
            "\n\n【重要指令】请在详细思考后，在输出的最后使用 ```json 包裹你的最终 JSON 结果。"
        )
        enhanced_prompt = prompt + json_instruction
        
        messages = []
        
        # 添加系统提示词
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # 添加用户提示词
        messages.append({
            "role": "user",
            "content": enhanced_prompt
        })
        
        _max_out = int(completion_max_tokens) if completion_max_tokens is not None else int(self.max_tokens)
        _MAX_TOKEN_CEIL = 16384  # 上限，避免无限放大
        logger.info(f"正在调用 LLM ({self.model}, max_tokens={_max_out})...")
        logger.debug(f"Prompt 长度: {len(enhanced_prompt)} 字符")
        
        # 重试机制
        last_error = None
        for attempt in range(1, retry_count + 1):
            try:
                # 调用 API（注意：DeepSeek-R1 不支持 response_format）
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=_max_out,
                    timeout=self.timeout
                    # 注意：不使用 response_format，因为 R1 需要自由输出思考过程
                )
                # 截断检测：finish_reason=='length' 说明 max_tokens 不够，下一轮翻倍。
                finish_reason = None
                try:
                    finish_reason = response.choices[0].finish_reason
                except Exception:  # pragma: no cover - defensive
                    pass
                if finish_reason == "length" and _max_out < _MAX_TOKEN_CEIL:
                    new_max = min(_max_out * 2, _MAX_TOKEN_CEIL)
                    logger.warning(
                        f"⚠️ LLM 输出被截断 (finish_reason=length, max_tokens={_max_out})；"
                        f"下一次重试将 max_tokens={new_max}"
                    )
                    _max_out = new_max
                    last_error = ValueError("LLM output truncated (finish_reason=length)")
                    if attempt < retry_count:
                        continue
                    else:
                        raise last_error
                
                # 提取响应内容
                raw_content = response.choices[0].message.content
                
                if not raw_content:
                    raise ValueError("LLM 返回空响应")
                
                logger.debug(f"LLM 原始响应长度: {len(raw_content)} 字符")
                
                # ==========================================
                # 🚀 增强版思维链提取逻辑
                # 兼容 DeepSeek/PoloAPI 的 reasoning_content 字段
                # ==========================================
                thinking = None
                message_obj = response.choices[0].message
                
                # 策略 1：从 API 返回的额外字段中提取 reasoning_content
                # 这是 DeepSeek 官方和大多数中转平台的标准做法
                if hasattr(message_obj, 'model_extra') and message_obj.model_extra:
                    thinking = message_obj.model_extra.get('reasoning_content')
                    if thinking:
                        logger.debug("从 model_extra.reasoning_content 提取思维链")
                
                # 策略 2：直接访问属性 (兼容某些定制的 SDK)
                if not thinking and hasattr(message_obj, 'reasoning_content'):
                    thinking = getattr(message_obj, 'reasoning_content')
                    if thinking:
                        logger.debug("从 reasoning_content 属性提取思维链")
                
                # 策略 3：正则回退机制 (有些平台会直接把 <think> 拼接到 content 里)
                if not thinking:
                    thinking = self._extract_thinking_process(raw_content)
                    if thinking:
                        logger.debug("从 <think> 标签提取思维链")
                # ==========================================
                
                if thinking:
                    # P-Stage1-D: 默认不把完整 chain-of-thought 写进论文级日志。
                    # 通过环境变量 STAGE1_LOG_REASONING=true 才打开整段输出（debug 用）。
                    import os as _os
                    _log_reasoning = _os.environ.get("STAGE1_LOG_REASONING", "").lower() in (
                        "1", "true", "yes", "on",
                    )
                    if _log_reasoning:
                        logger.info("=" * 80)
                        logger.info("🧠 DeepSeek-R1 思考过程（前 500 字符）:")
                        logger.info("-" * 80)
                        logger.info(thinking[:500] + ("..." if len(thinking) > 500 else ""))
                        logger.info("=" * 80)
                    else:
                        logger.info(
                            f"🧠 LLM 思维链已捕获（长度 {len(thinking)} 字符）— "
                            f"未保存原文；如需查看请设置 STAGE1_LOG_REASONING=true。"
                        )
                else:
                    logger.debug("未检测到思维链字段 (reasoning_content 或 <think> 标签)。")
                
                # 提取纯净的 JSON 内容
                json_str = self._extract_json(raw_content)
                
                # 验证是否为有效 JSON
                try:
                    json.loads(json_str)  # 仅验证，不解析
                except json.JSONDecodeError as e:
                    logger.error(f"提取的内容不是有效 JSON: {e}")
                    logger.error(f"提取内容（前 200 字符）: {json_str[:200]}")
                    raise
                
                logger.info(
                    f"LLM 调用成功 | "
                    f"输入 tokens: {response.usage.prompt_tokens} | "
                    f"输出 tokens: {response.usage.completion_tokens} | "
                    f"总计: {response.usage.total_tokens}"
                )
                
                return json_str
                
            except OpenAIError as e:
                last_error = e
                logger.warning(
                    f"LLM 调用失败 (尝试 {attempt}/{retry_count}): {e}"
                )
                
                if attempt < retry_count:
                    logger.info(f"正在重试...")
                    continue
                else:
                    logger.error(f"重试次数耗尽，调用失败")
                    raise ValueError(
                        f"LLM 调用失败，已重试 {retry_count} 次: {e}"
                    ) from e
            
            except json.JSONDecodeError as e:
                last_error = e
                logger.error(
                    f"JSON 解析失败 (尝试 {attempt}/{retry_count}): {e}"
                )
                
                if attempt < retry_count:
                    logger.info(f"正在重试...")
                    continue
                else:
                    raise ValueError(
                        f"LLM 返回格式错误，已重试 {retry_count} 次"
                    ) from e
            
            except ValueError as e:
                last_error = e
                logger.error(
                    f"内容提取失败 (尝试 {attempt}/{retry_count}): {e}"
                )
                # 即使 finish_reason != 'length'，也可能是 R1 把 JSON 写到 reasoning 而正文为空，
                # 或者代码块未闭合 —— 同样按"输出空间不够"加倍 max_tokens 重试一次。
                if "空响应" in str(e) or "无法从 LLM 响应中提取" in str(e):
                    if _max_out < _MAX_TOKEN_CEIL:
                        new_max = min(_max_out * 2, _MAX_TOKEN_CEIL)
                        logger.warning(
                            f"⚠️ 内容提取失败，疑似输出空间不足；下一次重试 max_tokens={new_max}"
                        )
                        _max_out = new_max
                
                if attempt < retry_count:
                    logger.info(f"正在重试...")
                    continue
                else:
                    raise
            
            except Exception as e:
                last_error = e
                logger.error(
                    f"未知错误 (尝试 {attempt}/{retry_count}): {e}"
                )
                
                if attempt < retry_count:
                    logger.info(f"正在重试...")
                    continue
                else:
                    raise
        
        # 理论上不会到达这里，但为了类型安全
        raise ValueError(f"LLM 调用失败: {last_error}")
    
    def generate_json_with_schema(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        retry_count: int = 3
    ) -> str:
        """
        生成符合指定 schema 的 JSON 响应
        
        Args:
            prompt: 用户提示词
            schema: JSON Schema 定义
            system_prompt: 系统提示词（可选）
            retry_count: 失败重试次数
            
        Returns:
            JSON 字符串
        """
        # 将 schema 添加到 prompt 中
        enhanced_prompt = (
            f"{prompt}\n\n"
            f"请严格按照以下 JSON Schema 输出：\n"
            f"```json\n{json.dumps(schema, indent=2, ensure_ascii=False)}\n```"
        )
        
        return self.generate_json(
            prompt=enhanced_prompt,
            system_prompt=system_prompt,
            retry_count=retry_count
        )
    
    def test_connection(self) -> bool:
        """
        测试 API 连接是否正常
        
        Returns:
            True 如果连接成功
        """
        try:
            logger.info("测试 LLM 连接...")
            response = self.generate_json(
                prompt="请输出一个简单的 JSON 对象，包含一个 'status' 字段，值为 'ok'。",
                retry_count=1
            )
            
            data = json.loads(response)
            if data.get("status") == "ok":
                logger.info("LLM 连接测试成功")
                return True
            else:
                logger.warning(f"LLM 返回异常: {response}")
                return False
                
        except Exception as e:
            logger.error(f"LLM 连接测试失败: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取当前模型配置信息
        
        Returns:
            模型配置字典
        """
        return {
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "api_key_set": bool(self.api_key)
        }
    
    def debug_response_structure(self, prompt: str = "测试") -> None:
        """
        调试方法：打印完整的响应结构，用于查看 API 返回的所有字段
        
        Args:
            prompt: 测试用的 prompt
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=500
            )
            
            message_obj = response.choices[0].message
            
            print("=" * 80)
            print("🔍 API 响应结构调试")
            print("=" * 80)
            
            print("\n[标准字段]")
            print(f"  content: {message_obj.content[:100]}...")
            print(f"  role: {message_obj.role}")
            
            print("\n[扩展字段 - model_extra]")
            if hasattr(message_obj, 'model_extra'):
                print(f"  存在: {bool(message_obj.model_extra)}")
                if message_obj.model_extra:
                    for key, value in message_obj.model_extra.items():
                        if isinstance(value, str) and len(value) > 100:
                            print(f"  {key}: {value[:100]}...")
                        else:
                            print(f"  {key}: {value}")
            else:
                print("  不存在")
            
            print("\n[所有属性]")
            for attr in dir(message_obj):
                if not attr.startswith('_'):
                    try:
                        value = getattr(message_obj, attr)
                        if not callable(value):
                            print(f"  {attr}: {type(value).__name__}")
                    except:
                        pass
            
            print("\n" + "=" * 80)
            
        except Exception as e:
            print(f"调试失败: {e}")
