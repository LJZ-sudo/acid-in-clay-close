# 通用闭环多智能体平台 V2.0 - Agent深度实现与Evidence系统 (Part 2)

**文档版本**: v3.1 (实现对齐 + AM投稿强化版)  
**更新日期**: 2026-02-08  
**适用范围**: Agent逻辑详解、Evidence系统、审计链设计  
**关联文档**: 
- [Part 1: 架构与部署](./FRONTEND_AGENT_GUIDE_PART1.md)
- [完整写作指南](./FULL_PROJECT_WRITING_GUIDE.md)

---

## 目录 - 第二部分

1. [Orchestrator：中央调度器的状态机](#1-orchestrator中央调度器的状态机)
2. [PlannerAgent：实验导航员的四种策略](#2-planneragent实验导航员的四种策略)
3. [CriticAgent：质量守门员的多维评估](#3-criticagent质量守门员的多维评估)
4. [Agent博弈过程的记录与审计](#4-agent博弈过程的记录与审计)
5. [Evidence Package：证据驱动的可审计性](#5-evidence-package证据驱动的可审计性)
6. [事件日志系统](#6-事件日志系统)
7. [前端可视化实现](#7-前端可视化实现)
8. [开发指南：扩展与定制](#8-开发指南扩展与定制)

---

## 1. Orchestrator：中央调度器的状态机

> **对应论文 Figure 1(a) 中心位置 + Figure 1(d) 闭环流程**

### 1.1 状态机设计

**核心文件**: `frontend_web/backend/agents/orchestrator.py`

当前实现状态机：

```
IDLE → PLAN → ACT → OBSERVE → LEARN → (next cycle)
  │                                  │
  └────────────── stop_run() ────────┘ → STOPPED
```

与论文叙事对应：
- `PLAN`：Planner建议 + MainAgent决策 + Critic仲裁
- `ACT`：执行动作并进行安全边界检查
- `OBSERVE`：接收测量结果并触发质量评估
- `LEARN`：上下文和知识库更新（跨循环记忆）

### 1.2 核心循环实现

```python
# 摘要：process_cycle(current_state, current_evidence)
1) 构建 AgentState / AgentEvidence
2) 发布 STATE=PLAN
3) PlannerAgent.suggest_next_step(...)
4) 可选：KnowledgeBase.match_pattern(...) → PATTERN_MATCH
5) 可选：LiteratureSearch (phase_jump > 0.15) → LITERATURE_SEARCH
6) MainAgent.decide(...)
7) CriticAgent.critique_decision(...) → DECISION_CRITIQUE
8) 记录 debate/context（可审计）
9) 进入 ACT：逐条 action 执行 _execute_action
10) 每条动作记录 TOOL_CALL / TOOL_RESULT
11) OBSERVE：外部测量回流后 add_measurement(...)
12) CriticAgent.critique_measurement(...) → MEASUREMENT_CRITIQUE
13) 更新 status / experiment_summary / stop_recommendation
```

> AM写作建议：将 3-12 步定义为“可追溯自治回路（traceable autonomous loop）”，并在 Methods 中给出事件类型与字段映射表。

---

## 2. PlannerAgent：实验导航员的四种策略

> **对应论文 Figure 1(b) 左侧 + Figure 2(d) 自适应采样**

### 2.1 四种采样策略详解

**核心文件**: `frontend_web/backend/agents/planner_agent.py`

```python
class PlanningStrategy(str, Enum):
    """
    规划策略 - 模拟人类科学家的实验设计思路
    
    策略选择体现了"探索-利用"(Exploration-Exploitation)权衡
    """
    UNIFORM = "uniform"           # 均匀采样：实验初期的系统性扫描
    ADAPTIVE = "adaptive"         # 自适应采样：根据数据变化率调整步长
    FOCUSED = "focused"           # 聚焦采样：相变点附近的高密度测量
    COMPLETION = "completion"     # 完成采样：查漏补缺，确保数据完整性
```

### 2.2 策略切换逻辑

当前实现遵循“质量优先 + 相变优先 + 覆盖优化”三原则：

```python
# planner_agent.py 中的关键触发
if qc == "FAIL" or r_squared < 0.90:
    return NextStepRecommendation(action="EIS_RUN", parameters={"retry": True})

if phase_jump > 0.20 and phase == "COARSE" and not phase_flag:
    return NextStepRecommendation(action="SET_PHASE", parameters={"value": "FINE", "backtrack_to": T+3.0})

if phase == "FINE":
    # 默认 1.0°C 细步长推进，直到细测窗口结束

# 正常粗测推进
next_T = T_current - coarse_step  # 默认 3.0°C
```

补充能力（用于 Results/Methods 量化）：
- `optimize_measurement_plan(...)`：给出剩余温区最优测量计划
- `should_stop_early(...)`：给出提前停止建议与 remaining value
- `suggest_refinement_points(...)`：输出相变附近加密点

### 2.3 策略对比表（用于论文）

| 策略 | 触发条件 | 步长 | 目标 | 风险偏好 |
|-----|---------|-----|------|---------|
| **UNIFORM** | 实验初期 / 数据稀疏 | 5-10°C | 快速建立全局视图 | 中等探索 |
| **ADAPTIVE** | 正常测量阶段 | 1-5°C (动态) | 高效覆盖 | 平衡 |
| **FOCUSED** | 检测到相变信号 | 0.5-1°C | 精确定位相变点 | 高探索 |
| **COMPLETION** | 覆盖率 >80% | 变化 | 填补数据空隙 | 保守 |

---

## 3. CriticAgent：质量守门员的多维评估

> **对应论文 Figure 1(b) 右侧 + Figure 2(c) QC评分分布**

### 3.1 多维度评估矩阵

**核心文件**: `frontend_web/backend/agents/critic_agent.py`

当前实现评分维度：
1. R²拟合质量（主评分因子）
2. Rb合理性（`rb_min=10Ω`, `rb_max=1e9Ω`）
3. 与历史一致性（异常跳变惩罚）
4. 拟合方法适配性（`fit_method`）
5. 电导率物理合理性
6. 相位跳变预警（warning）

R²分级阈值（当前代码）：
- `excellent >= 0.99`
- `good >= 0.97`
- `acceptable >= 0.95`
- `poor >= 0.90`

重测规则（当前代码）：
- `needs_retry == True` 当 `score < 0.5`
- 或建议文本中含“重测/重新测量”语义

> AM写作建议：将 Critic 定义为“online quality gate”，强调其在决策前和测量后都参与评价，而非离线后处理。

### 3.2 评分等级与触发动作

| 等级 | 分数范围 | 评估结论 | 触发动作 | 论文引用 |
|-----|---------|---------|---------|---------|
| **A** | ≥0.95 | 优秀 | 继续下一步 | Fig 2(c) 绿色区 |
| **B** | 0.85-0.95 | 良好 | 继续下一步 | Fig 2(c) 浅绿区 |
| **C** | 0.70-0.85 | 可接受 | 记录警告，继续 | Fig 2(c) 黄色区 |
| **D** | 0.50-0.70 | 较差 | **建议重测** | Fig 2(c) 橙色区 |
| **F** | <0.50 | 不合格 | **强制重测** | Fig 2(c) 红色区 |

---

## 4. Agent博弈过程的记录与审计

> **对应论文 Figure 5(b): Agent协商时间线**

### 4.1 博弈记录结构

```python
@dataclass
class AgentDebateRecord:
    """Agent博弈记录 - 用于审计和可解释性"""
    
    step_id: str                      # 步骤ID
    timestamp: str                    # 时间戳
    
    # Planner信息
    planner_suggestion: Dict          # Planner建议
    planner_reasoning: str            # Planner推理过程
    planner_confidence: float         # Planner置信度
    planner_strategy: str             # 当前策略
    
    # Critic信息
    critic_evaluation: str            # Critic评估描述
    critic_score: float               # Critic评分
    critic_issues: List[str]          # 发现的问题
    critic_suggestions: List[str]     # 改进建议
    
    # 最终决策
    final_decision: str               # 最终执行的动作
    decision_accepted: bool           # 决策是否被接受
    modification_reason: str          # 修改原因（如有）
    
    # 上下文
    evidence_summary: Dict            # 当前证据摘要
    history_length: int               # 历史记录长度
```

### 4.2 博弈过程示例

```json
{
  "step_id": "S0023",
  "timestamp": "2026-02-02T14:35:22.456Z",
  
  "planner_suggestion": {
    "action": "SET_T",
    "value": -48.0,
    "strategy": "FOCUSED",
    "confidence": 0.85
  },
  "planner_reasoning": "检测到ln(Rb)跳变0.23，超过阈值0.15，触发聚焦采样策略。建议回退2°C进行精细测量。",
  "planner_confidence": 0.85,
  "planner_strategy": "FOCUSED",
  
  "critic_evaluation": "B级 - 当前数据质量良好，决策合理",
  "critic_score": 0.88,
  "critic_issues": [],
  "critic_suggestions": ["相变区测量时建议延长稳定等待时间"],
  
  "final_decision": "SET_T",
  "decision_accepted": true,
  "modification_reason": "",
  
  "evidence_summary": {
    "temperature_K": 223.15,
    "rb_ohm": 1.2e5,
    "r_squared": 0.96,
    "phase_jump": 0.23
  },
  "history_length": 22
}
```

---

## 5. Evidence Package：证据驱动的可审计性

> **对应论文 Figure 5(a): Evidence Package结构树**

### 5.1 Evidence Package 完整结构

```python
@dataclass
class EvidencePackage:
    """
    证据包 - 每个实验步骤的完整记录
    
    设计原则：
    1. 完整性：记录所有原始数据和处理过程
    2. 可追溯：每个数据点都有来源链接
    3. 可审计：支持第三方验证
    """
    
    # ========== 测量证据 ==========
    measurement: MeasurementEvidence
    
    # ========== 转变证据 ==========
    transition: Optional[TransitionEvidence]
    
    # ========== Agent协商轨迹 ==========
    deliberation: AgentDeliberationTrace
    
    # ========== 决策证据 ==========
    decision: DecisionEvidence
    
    # ========== 元数据 ==========
    metadata: EvidenceMetadata


@dataclass
class MeasurementEvidence:
    """测量证据"""
    raw_data_path: str              # 原始数据文件路径
    raw_data_checksum: str          # MD5校验和
    temperature_C: float            # 测量温度 (°C)
    temperature_K: float            # 测量温度 (K)
    rb_ohm: float                   # 体电阻 (Ω)
    sigma_S_cm: float               # 电导率 (S/cm)
    r_squared: float                # 拟合优度
    fit_method: str                 # 拟合方法
    fit_params: Dict                # 拟合参数
    frequency_range: Tuple[float, float]  # 频率范围 (Hz)
    amplitude_mV: float             # 测量振幅 (mV)


@dataclass
class TransitionEvidence:
    """转变证据（相变检测）"""
    change_point_T: float           # 变化点温度 (K)
    phase_jump_value: float         # 相位跳变幅度
    detection_method: str           # 检测方法 (BIC-DP / AIC / F-test)
    confidence_interval: Tuple[float, float]  # 置信区间
    segment_before: ArrheniusSegment  # 变化点前的分段
    segment_after: ArrheniusSegment   # 变化点后的分段


@dataclass
class AgentDeliberationTrace:
    """Agent协商轨迹 - 多Agent系统特有"""
    planner_suggestion: Dict        # Planner建议
    planner_confidence: float       # Planner置信度
    planner_reasoning: str          # Planner推理
    critic_score: float             # Critic评分
    critic_grade: str               # Critic等级
    critic_issues: List[str]        # Critic发现的问题
    critic_suggestions: List[str]   # Critic建议
    debate_outcome: str             # 博弈结果
    final_decision: str             # 最终决策


@dataclass
class DecisionEvidence:
    """决策证据"""
    trigger_type: str               # 触发类型 (PHASE_JUMP / QC_FAIL / PLANNER_SUGGEST / SCHEDULED)
    threshold_used: Dict            # 使用的阈值
    action_executed: str            # 执行的动作
    action_params: Dict             # 动作参数
    execution_result: str           # 执行结果 (SUCCESS / FAILED / SKIPPED)


@dataclass
class EvidenceMetadata:
    """元数据"""
    evidence_id: str                # 证据ID
    step_id: str                    # 步骤ID
    run_id: str                     # 运行ID
    timestamp: str                  # ISO格式时间戳
    platform_version: str           # 平台版本
    created_by: str                 # 创建者 (系统/Agent名)
```

### 5.2 Evidence Package JSON 示例

```json
{
  "evidence_id": "EVD-20260202-143522-0023",
  "step_id": "S0023",
  "run_id": "RUN-20260202-140000-SAMPLE001",
  
  "measurement": {
    "raw_data_path": "data/raw/RUN-20260202-140000/S0023_-50C.csv",
    "raw_data_checksum": "a1b2c3d4e5f6...",
    "temperature_C": -50.0,
    "temperature_K": 223.15,
    "rb_ohm": 1.2e5,
    "sigma_S_cm": 2.1e-6,
    "r_squared": 0.963,
    "fit_method": "linear_high_freq",
    "fit_params": {"slope": -1.234, "intercept": 5.678},
    "frequency_range": [100, 1000000],
    "amplitude_mV": 10
  },
  
  "transition": {
    "change_point_T": 223.5,
    "phase_jump_value": 0.23,
    "detection_method": "ln_Rb_jump",
    "confidence_interval": [221.0, 226.0]
  },
  
  "deliberation": {
    "planner_suggestion": {"action": "SET_T", "value": -48.0, "strategy": "FOCUSED"},
    "planner_confidence": 0.85,
    "planner_reasoning": "检测到相变信号，建议精细采样",
    "critic_score": 0.88,
    "critic_grade": "B",
    "critic_issues": [],
    "critic_suggestions": ["延长稳定等待时间"],
    "debate_outcome": "ACCEPTED",
    "final_decision": "SET_T"
  },
  
  "decision": {
    "trigger_type": "PHASE_JUMP",
    "threshold_used": {"phase_jump_threshold": 0.15},
    "action_executed": "SET_T",
    "action_params": {"value": -48.0, "rate": 2.0},
    "execution_result": "SUCCESS"
  },
  
  "metadata": {
    "timestamp": "2026-02-02T14:35:22.456Z",
    "platform_version": "2.0.0",
    "created_by": "Orchestrator"
  }
}
```

---

## 6. 事件日志系统

> **对应论文 Figure 5(b) 审计链 + Methods 可复现性说明**

### 6.1 事件类型完整列表

当前 `orchestrator.py` 中重点事件：

```python
# 运行/状态
STATE

# 认知层事件
PATTERN_MATCH
PLANNER_SUGGESTION
LITERATURE_SEARCH
DECISION_CRITIQUE
DECISION
UI_THOUGHT

# 执行层事件
TOOL_CALL
TOOL_RESULT

# 观测/质控
MEASUREMENT_CRITIQUE

# 异常
WARNING
ERROR
```

> 补充：消息总线层可额外提供 `REQUEST/RESPONSE/EVENT/BROADCAST/HEARTBEAT` 统计，用于系统级可运维性论证。

### 6.2 事件记录结构

```python
@dataclass
class OrchestratorEvent:
    """调度器事件 - 审计链的基本单元"""
    
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    run_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    event_type: str = ""
    step: str = ""
    agent: str = "Orchestrator"
    payload: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_log_line(self) -> str:
        """格式化为日志行"""
        return f"[{self.timestamp}] [{self.event_type}] Step={self.step} | {json.dumps(self.payload, ensure_ascii=False)}"
```

### 6.3 审计链示例

```text
[STATE] status=STARTED
[STATE] phase=PLAN
[PLANNER_SUGGESTION] action=SET_T, confidence=0.85
[PATTERN_MATCH] top_match=...
[LITERATURE_SEARCH] results_count=5
[DECISION_CRITIQUE] score=0.88, grade=B
[DECISION] next_actions=[...]
[UI_THOUGHT] step_title=...
[STATE] phase=ACT
[TOOL_CALL] action_type=SET_T
[TOOL_RESULT] success=true
[STATE] phase=OBSERVE
[MEASUREMENT_CRITIQUE] score=0.91, needs_retry=false
```

该链路可直接支撑 Fig 5(b) 的“触发→协商→执行→验证”审计叙事。

---

## 7. 前端可视化实现（实现对齐版）

### 7.1 核心页面与组件

- 页面：`Dashboard.jsx`、`Monitor.jsx`、`Arrhenius.jsx`、`History.jsx`
- Agent面板：`PlannerPanel.jsx`、`CriticPanel.jsx`、`ThoughtChainPanel.jsx`、`ToolsPanel.jsx`
- 图表：`TemperatureChart.jsx`、`ConductivityChart.jsx`、`ArrheniusChart.jsx`

### 7.2 状态与事件流

- `agentStore`：管理 `thoughtChain/currentDecision/plannerResult/criticResult/activeTools`
- `dataStore`：管理温度、电导率、测量记录、Arrhenius数据
- `uiStore`：管理连接状态、运行状态、通知
- 数据入口：
  - SSE：`/api/main-agent/stream`、`/api/autonomous/stream`
  - WebSocket：`thought_chain_event`、`temperature_update` 等

### 7.3 AM图稿建议（前端侧）

1. Fig S6 截图应覆盖 Dashboard + Monitor + Arrhenius + History 四页。
2. Fig 5(b) 推荐直接用 `thoughtChain + TOOL_CALL/RESULT` 事件截图。
3. SI 中给出 UI 字段到后端事件字段的映射表，强化可复现性。

### 7.4 字段级映射（Methods/SI 建议）

| 前端字段 | 后端事件字段 | 代码位置 | 论文用途 |
|---------|-------------|---------|---------|
| `plannerResult.action` | `PLANNER_SUGGESTION.payload.action` | `orchestrator.py` | Fig 5(b) 规划证据 |
| `criticResult.score` | `MEASUREMENT_CRITIQUE.payload.critique.score` | `critic_agent.py` + `orchestrator.py` | Fig 2(c) 质量门控 |
| `activeTools` | `TOOL_CALL/TOOL_RESULT.payload.action_type` | `agentStore.js` | Fig S6 工具执行可视化 |
| `thoughtChain` | `UI_THOUGHT.payload.*` | `main_agent.py` / `orchestrator.py` | 审计链与可解释性 |

## 8. 开发指南：扩展与定制

### 8.1 添加新的 Agent

```python
# 1. 定义Agent类
class NewAgent(BaseAgent):
    def __init__(self, config: Dict = None):
        super().__init__(AgentRole.NEW_AGENT)
        self.config = config or {}
    
    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """处理接收到的消息"""
        if message.type == MessageType.REQUEST:
            result = self._process_request(message.payload)
            return AgentMessage(
                type=MessageType.RESPONSE,
                sender=self.role,
                receiver=message.sender,
                payload=result,
                correlation_id=message.id
            )
    
    def _process_request(self, payload: Dict) -> Dict:
        """实现具体的处理逻辑"""
        # TODO: 实现你的逻辑
        return {"status": "success", "data": {...}}

# 2. 在 protocol.py 中添加角色
class AgentRole(str, Enum):
    # ... 现有角色
    NEW_AGENT = "new_agent"

# 3. 在 Orchestrator 中注册
self.new_agent = NewAgent(config.get('new_agent', {}))
self.message_bus.register_agent(self.new_agent)
```

### 8.2 修改 Planner 策略

```python
# 在 planner_agent.py 中添加新策略
class PlanningStrategy(str, Enum):
    # ... 现有策略
    BAYESIAN = "bayesian"  # 新增：贝叶斯优化策略

# 在 suggest_next_step 中添加处理
def suggest_next_step(self, state, evidence, history):
    # ...
    if strategy == PlanningStrategy.BAYESIAN:
        next_action = self._plan_bayesian_sampling(state, evidence)
    # ...

def _plan_bayesian_sampling(self, state, evidence):
    """贝叶斯优化采样策略"""
    # 使用高斯过程拟合历史数据
    gp = GaussianProcessRegressor()
    gp.fit(self.history_X, self.history_y)
    
    # 使用采集函数（如 Expected Improvement）选择下一点
    next_T = self._maximize_acquisition(gp, state['T_range'])
    
    return ActionSpec(action="SET_T", value=next_T)
```

### 8.3 调整 Critic 评分标准

```python
# 推荐方式：在初始化时注入配置（与当前实现一致）
critic = CriticAgent(config={
    "r_squared_excellent": 0.99,
    "r_squared_good": 0.97,
    "r_squared_acceptable": 0.95,
    "r_squared_poor": 0.90,
    "rb_min": 10,
    "rb_max": 1e9,
    "phase_jump_warning": 0.15,
})

# 需要按体系放宽/收紧时，直接调整阈值
# 例如：高噪声体系可把 poor 阈值从 0.90 调整到 0.88
```

> 建议：投稿中同步报告“阈值来源 + 灵敏度分析”，避免被审稿人质疑阈值任意性。

### 8.4 前端显示新的Agent状态

```javascript
// 1. 在 agentStore.js 中添加状态
export const useAgentStore = create((set, get) => ({
  // ... 现有状态
  newAgentState: {
    status: 'idle',
    lastResult: null
  },
  
  updateNewAgentState: (newState) => set({ 
    newAgentState: { ...get().newAgentState, ...newState } 
  }),
}));

// 2. 创建可视化组件
// src/components/agent/NewAgentPanel.jsx
export const NewAgentPanel = () => {
  const newAgentState = useAgentStore(state => state.newAgentState);
  
  return (
    <div className="new-agent-panel">
      <h3>🆕 New Agent</h3>
      <div>Status: {newAgentState.status}</div>
      {/* 添加更多可视化内容 */}
    </div>
  );
};

// 3. 在页面中引用
import { NewAgentPanel } from '../components/agent/NewAgentPanel';
```

### 8.5 投稿前实现一致性检查（建议）

1. 角色命名：论文可写 Planner，但代码协议角色为 `RECOMMENDER`。
2. 状态机：写作统一为 `IDLE → PLAN → ACT → OBSERVE → LEARN → ...`。
3. 端口与代理：开发默认 `5000`，前端 `vite.config.js` 代理到 `http://localhost:5000`。
4. API声明：优先使用已落地接口（`/autonomous/start-thinking`、`/autonomous/auto-decision`、`/autonomous/stream`）。
---

## 与论文Figure的对应关系总结

| 论文Figure | 本文档对应章节 | 核心内容 |
|-----------|--------------|---------|
| **Fig 1(a)** | Part 1 §2, §3 | 多Agent架构全景图 |
| **Fig 1(b)** | Part 1 §2.3, Part 2 §2, §3 | Planner-Critic博弈 |
| **Fig 1(c)** | Part 1 §5 | 数字-物理桥接 |
| **Fig 1(d)** | Part 2 §1 | Plan-Act-Observe-Learn 闭环 |
| **Fig 2(c)** | Part 2 §3.2 | QC评分分布 |
| **Fig 2(d)** | Part 2 §2 | 自适应采样策略 |
| **Fig 5(a)** | Part 2 §5 | Evidence Package结构 |
| **Fig 5(b)** | Part 2 §4, §6 | Agent协商时间线/审计链 |
| **Fig S6** | Part 2 §7 | UI界面截图 |

---

**结语**: 

通过本文档，您应该能够：
1. 理解多Agent系统的完整架构和协作机制
2. 掌握 Planner 和 Critic 的核心算法
3. 了解 Evidence Package 如何支撑可审计性
4. 知道如何扩展和定制平台功能

这些内容直接支撑论文 Figure 1-5 的绘制和 Methods 部分的撰写。












