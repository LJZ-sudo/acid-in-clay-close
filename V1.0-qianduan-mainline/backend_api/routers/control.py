# -*- coding: utf-8 -*-
"""Hardware control routes — bridges to HardwareAdapter for both real and simulated modes.

All endpoints delegate to the HardwareAdapter singleton which manages
connection, temperature control, measurement triggering, and policy changes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Union

from backend_api.services.hardware_adapter import get_hardware_adapter

router = APIRouter()


class ConnectRequest(BaseModel):
    port: Optional[str] = "COM3"
    simulate: bool = False
    coarse_step: Optional[float] = 5.0
    fine_step: Optional[float] = 1.0
    t_start: Optional[float] = 20.0
    t_end: Optional[float] = -85.0


class TemperatureRequest(BaseModel):
    target: Optional[float] = None
    temperature: Optional[float] = None

    @property
    def effective_target(self) -> float:
        return self.target if self.target is not None else (self.temperature if self.temperature is not None else 0)


class PolicyRequest(BaseModel):
    mode: Optional[str] = None
    fine_step: Optional[float] = None
    coarse_step: Optional[float] = None
    fallback: Optional[str] = None


class StartExperimentRequest(BaseModel):
    sample_id: str = "unknown"
    t_start: float = 20.0
    t_end: float = -85.0
    coarse_step: float = 5.0
    fine_step: float = 1.0
    # Sample geometry (optional, recorded into sample_summary.json)
    thickness_m: Optional[float] = None
    area_m2: Optional[float] = None
    material_note: Optional[str] = None
    # CHI / EIS instrument settings (UI-side records; CHI must be set on the
    # device itself, but values are persisted for cross-checking)
    chi_high_freq_Hz: Optional[float] = None
    chi_low_freq_Hz: Optional[float] = None
    chi_init_voltage_V: Optional[float] = None
    chi_amplitude_mV: Optional[float] = None
    # BO / campaign provenance (when adopting a recipe from /optimization)
    R: Optional[float] = None
    N: Optional[float] = None
    campaign: Optional[str] = None
    parent_sample_id: Optional[str] = None
    # Auto post-processing (Stage0 + Stage1) after the cooling loop completes.
    ao_folder: Optional[str] = None  # e.g. "2026.5.12__ATA-2026-5-12-R0.35-N0.95"; default derived per sample_id
    auto_postprocess: bool = True
    # 仅当 auto_postprocess=True 时有效：False = 只跑复制 + Stage0，不跑 Stage1 BO（冷启动推荐）
    run_stage1_after_stage0: bool = True
    campaign_config: Optional[str] = None  # path to campaign JSON (Stage1)
    history_db_path: Optional[str] = None  # path to history_db_*.json (Stage1)
    source_tag: Optional[str] = None  # Stage1 --source_tag
    # Per-point LLM Agent (phase-transition decision after each measurement)
    enable_agent_decision: bool = True
    agent_api_key: Optional[str] = None  # overrides POLOAPI_KEY env var
    agent_model: Optional[str] = None    # default openai/gpt-5.4(须为合法 OpenRouter model ID)
    fine_scan_window_C: Optional[float] = None
    # 创新点开关(2026-07-05 起默认开——创新点必须默认真实运作,不能靠显式 opt-in 才存在。
    # 全部 fail-safe:失败只记事件、绝不影响测量/入库;无 API key 时 LLM 类自动降级只记事件。
    # 真机验证:fe3/fe4b live run 已全开跑通。)
    #   - enable_active_design : Gap2 内层可知性驱动选温(advisory + ActionGate 留痕,逐点注入决策
    #       prompt;纯计算零成本)
    #   - enable_stage3_reasoning : §12.14 收尾 stage3 假设/机制/设计原则推理链(真 LLM,收尾 3-4 次调用)
    #   - enable_epistemic : §12.15 收尾认知证书三对象(观测性/最小判别集/e-process 证伪);
    #                        并附带阻抗级正问题谱级辨识(§13 P13-A,收尾对真机谱跑 MechanismModel)。
    #                        纯 numpy/scipy 零 LLM 成本。
    #   - enable_falsification_market : §13 P13-B 收尾多角色 LLM 证伪市场(真 OpenRouter,收尾 ~9 次调用)
    enable_active_design: bool = True
    #   - active_design_mode : "advisory"(默认,仅注入 prompt,行为不变)|
    #       "canary"(P13-C:经 ActionGate 在固定阶梯相邻候选间微调下一 setpoint,受硬护栏约束)。
    #       canary 属物理执行层,保持显式开启(安全三阶段纪律),不随默认翻转。
    active_design_mode: str = "advisory"
    enable_stage3_reasoning: bool = True
    enable_epistemic: bool = True
    enable_falsification_market: bool = True
    #   - commit_gate_mode : "enforce"(默认,被拒点真挡出 BO)| "canary"(同 enforce,灰度)|
    #       "shadow"(P13-D:只记录裁决、被拒点仍进 BO=legacy)。仅门控测量提交,绝不门控温控/CHI。
    commit_gate_mode: str = "enforce"
    #   - inject_fault : G-2 真机故障注入(opt-in,真机验收治理拦截用)。dict 或 list of dict:
    #       {"type": "SAMPLE_MISMATCH"|"QA_FAIL", "at_step": <int>}。
    #       **只作用于测量提交治理层输入**(样品核对/QA),让真实 txn 判 entered_bo=False;
    #       **绝不触碰温控/CHI 物理命令**(安全)。默认 None=不注入。
    inject_fault: Optional[Union[dict, list]] = None
    # H 系列旧材料硬化(2026-07-05)live 终验开关(纯加法、legacy 永不覆盖):
    #   - enable_instrument_witness : H2 在线仪器见证(2026-07-05 起默认开;纯软件零成本、fail-safe)。
    #       每点用真实 CHI 文件 sha256 + 温控稳定 TEMP_TRACE + 仪器态经真实 EvidenceTransaction 推
    #       C_P。协议级故障经 inject_fault 里
    #       type∈{ACK_LOSS,INSTRUMENT_STUCK,FILE_MISSING,FILE_DELAY,SAMPLE_SWAP,CALIBRATION_EXPIRED}
    #       条目注入(仅驱动边界软件注入,绝不触碰温控/CHI 物理安全)。
    #   - canary_max_steps : H3 active_design canary 可执行邻域步数(clamp 1–3,默认 2)。
    #       仅在 enable_active_design=True 且 active_design_mode="canary" 时生效;硬护栏不变。
    #   - rb_r4_activate / rb_r4_signoff : H4 Rb-ACT R4 替换态激活(须三条件齐备:本 flag +
    #       预注册 gates_pass + 人审签核 token)。缺任一条件恒回退 legacy,legacy_overwritten=0。
    #       **默认关(有意人审门,不随默认翻转)**——未提供签核 token 时数值链恒 100% legacy,
    #       软件绝不自行替换。
    enable_instrument_witness: bool = True
    canary_max_steps: int = 2
    rb_r4_activate: bool = False
    rb_r4_signoff: Optional[str] = None
    # Safety thresholds + finalize behaviour (mirror run_online.py defaults)
    min_conductivity_threshold: Optional[float] = None  # σ hard fuse (S/cm)
    max_rb_ohm: Optional[float] = None                  # Rb hard fuse (Ω)
    max_consecutive_failures: Optional[int] = None      # measurement-failure fuse
    finalize_reheat_C: Optional[float] = None           # finalize reheat target °C
    # Resume mode — load prior state snapshot and skip initial cool-to-start
    resume: bool = False
    state_path: Optional[str] = None


class MeasurePolicyRequest(BaseModel):
    mode: Optional[str] = None
    fine_step: Optional[float] = None
    coarse_step: Optional[float] = None


@router.post("/connect")
def connect(req: ConnectRequest):
    hw = get_hardware_adapter()
    result = hw.connect(port=req.port, simulate=req.simulate)
    if not result.get("ok"):
        raise HTTPException(500, result.get("error", "Connection failed"))
    if req.coarse_step is not None:
        hw._coarse_step = req.coarse_step
        hw._step_size = req.coarse_step
    if req.fine_step is not None:
        hw._fine_step = req.fine_step
    return result


@router.post("/disconnect")
def disconnect():
    hw = get_hardware_adapter()
    return hw.disconnect()


@router.get("/status")
def get_status():
    hw = get_hardware_adapter()
    return hw.status


@router.post("/start")
def start_experiment(req: Optional[StartExperimentRequest] = None):
    if req is None:
        req = StartExperimentRequest()
    hw = get_hardware_adapter()
    return hw.start(
        sample_id=req.sample_id,
        t_start=req.t_start,
        t_end=req.t_end,
        coarse_step=req.coarse_step,
        fine_step=req.fine_step,
        thickness_m=req.thickness_m,
        area_m2=req.area_m2,
        material_note=req.material_note,
        chi_high_freq_Hz=req.chi_high_freq_Hz,
        chi_low_freq_Hz=req.chi_low_freq_Hz,
        chi_init_voltage_V=req.chi_init_voltage_V,
        chi_amplitude_mV=req.chi_amplitude_mV,
        R=req.R,
        N=req.N,
        campaign=req.campaign,
        parent_sample_id=req.parent_sample_id,
        ao_folder=req.ao_folder,
        auto_postprocess=req.auto_postprocess,
        run_stage1_after_stage0=req.run_stage1_after_stage0,
        campaign_config=req.campaign_config,
        history_db_path=req.history_db_path,
        source_tag=req.source_tag,
        enable_agent_decision=req.enable_agent_decision,
        agent_api_key=req.agent_api_key,
        agent_model=req.agent_model,
        enable_active_design=req.enable_active_design,
        active_design_mode=req.active_design_mode,
        enable_stage3_reasoning=req.enable_stage3_reasoning,
        enable_epistemic=req.enable_epistemic,
        enable_falsification_market=req.enable_falsification_market,
        commit_gate_mode=req.commit_gate_mode,
        inject_fault=req.inject_fault,
        enable_instrument_witness=req.enable_instrument_witness,
        canary_max_steps=req.canary_max_steps,
        rb_r4_activate=req.rb_r4_activate,
        rb_r4_signoff=req.rb_r4_signoff,
        fine_scan_window_C=req.fine_scan_window_C,
        min_conductivity_threshold=req.min_conductivity_threshold,
        max_rb_ohm=req.max_rb_ohm,
        max_consecutive_failures=req.max_consecutive_failures,
        finalize_reheat_C=req.finalize_reheat_C,
        resume=req.resume,
        state_path=req.state_path,
    )


class PostProcessRequest(BaseModel):
    sample_id: str
    ao_folder: Optional[str] = None
    campaign_config: Optional[str] = None
    history_db_path: Optional[str] = None
    source_tag: Optional[str] = None
    run_stage1_after_stage0: bool = True


@router.post("/postprocess")
def run_postprocess(req: PostProcessRequest):
    """Manually re-run the Stage0 + Stage1 pipeline for a finished experiment.

    Useful when auto_postprocess was off, or when the user wants to retry
    after fixing a 材料制备.txt mistake.
    """
    hw = get_hardware_adapter()
    return hw.run_post_processing(
        sample_id=req.sample_id,
        ao_folder=req.ao_folder,
        campaign_config=req.campaign_config,
        history_db_path=req.history_db_path,
        source_tag=req.source_tag,
        async_run=True,
        run_stage1=req.run_stage1_after_stage0,
    )


@router.post("/pause")
def pause_experiment():
    hw = get_hardware_adapter()
    hw._running = False
    return {"ok": True, "paused": True}


@router.post("/resume")
def resume_experiment():
    hw = get_hardware_adapter()
    hw._running = True
    return {"ok": True, "paused": False}


@router.post("/stop")
def stop_experiment():
    hw = get_hardware_adapter()
    return hw.stop()


@router.get("/temperature")
def get_temperature():
    hw = get_hardware_adapter()
    return hw.get_temperature()


@router.post("/temperature")
def set_temperature(req: TemperatureRequest):
    hw = get_hardware_adapter()
    return hw.set_temperature(req.effective_target)


@router.post("/measure")
def measure_now():
    """Trigger a single EIS measurement at the current temperature."""
    hw = get_hardware_adapter()
    return hw.trigger_measurement()


@router.post("/measurement-policy")
def apply_measurement_policy(req: Optional[MeasurePolicyRequest] = None):
    if req is None:
        req = MeasurePolicyRequest()
    """Apply measurement policy changes — actually modifies step size and mode."""
    hw = get_hardware_adapter()
    return hw.apply_policy(
        mode=req.mode,
        fine_step=req.fine_step,
        coarse_step=req.coarse_step,
    )


@router.post("/autonomous/start")
def start_autonomous():
    hw = get_hardware_adapter()
    hw._autonomous = True
    return {"ok": True, "autonomous": True}


@router.post("/autonomous/stop")
def stop_autonomous():
    hw = get_hardware_adapter()
    hw._autonomous = False
    return {"ok": True, "autonomous": False}


@router.get("/autonomous/status")
def autonomous_status():
    hw = get_hardware_adapter()
    return {"autonomous": hw._autonomous}


@router.post("/policy")
def update_policy(req: PolicyRequest):
    """Update general agent policy settings."""
    hw = get_hardware_adapter()
    return hw.apply_policy(
        mode=req.mode,
        fine_step=req.fine_step,
        coarse_step=req.coarse_step,
    )
