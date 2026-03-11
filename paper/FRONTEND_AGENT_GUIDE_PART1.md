# 通用闭环多智能体平台 V2.0 - 前端架构指南 (Part 1)

**文档版本**: v3.1 (实现对齐 + AM投稿强化版)  
**更新日期**: 2026-02-08  
**适用范围**: 前端工程 (`frontend_web`) 与 Agent 后端集成  
**项目代号**: Universal Closed-Loop Multi-Agent SDL Platform  
**关联文档**: 
- [Part 2: Agent深度实现与Evidence系统](./FRONTEND_AGENT_GUIDE_PART2.md)
- [完整写作指南](./FULL_PROJECT_WRITING_GUIDE.md)

---

## 目录 - 第一部分

1. [项目概述与学术定位](#1-项目概述与学术定位)
2. [多智能体系统架构（核心创新）](#2-多智能体系统架构核心创新)
3. [Agent完整清单与职责矩阵](#3-agent完整清单与职责矩阵)
4. [消息总线与通信协议](#4-消息总线与通信协议)
5. [数字-物理桥接层](#5-数字-物理桥接层)
6. [前端交互层设计](#6-前端交互层设计)
7. [部署与环境配置](#7-部署与环境配置)
8. [AM投稿强化表达（基于当前实现）](#8-am投稿强化表达基于当前实现)

---

## 1. 项目概述与学术定位

### 1.1 SDL领域的学术定位

本项目 (**Universal Closed-Loop Multi-Agent SDL Platform**) 是一个面向 **Advanced Materials / Nature Communications** 级别投稿的自驱动实验室（SDL）平台。

**学术定位对比**：

| 维度 | 传统自动化 | 本平台（多Agent SDL） |
|-----|----------|---------------------|
| **决策模式** | 单一算法（如BO） | 多Agent协商博弈 |
| **数据质量** | 后处理剔除 | 实时Critic守门 |
| **可解释性** | 黑箱模型 | Agent对话全程可审计 |
| **可扩展性** | 单任务定制 | 模块化Agent可插拔 |
| **学术贡献** | 方法应用 | **架构创新** |

### 1.2 核心差异化功能

```
┌─────────────────────────────────────────────────────────────────────┐
│                    本平台的三大核心创新                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ① 多智能体协作系统 (Multi-Agent System)                            │
│     └── Planner-Critic博弈机制，模拟科学家"假设-验证"循环             │
│                                                                     │
│  ② 数字-物理可执行桥接 (Digital-Physical Bridge)                     │
│     └── Agent决策直接转化为硬件指令，无需人工转译                      │
│                                                                     │
│  ③ 证据驱动闭环 (Evidence-Driven Closed-Loop)                       │
│     └── Evidence Package + 事件日志，100%可审计                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 技术栈概览

| 层次 | 技术组件 | 职责 | 对应论文部分 |
|------|----------|------|------------|
| **前端交互层** | React 18 + Vite | 用户界面、实时监控、人机协同 | Fig 1(c), Fig S6 |
| **状态管理** | Zustand | 跨组件管理Agent状态、实验数据流 | Methods |
| **可视化** | ECharts | EIS谱图、Arrhenius曲线、温度趋势 | Fig 2-4 |
| **智能体后端** | Python 3.10+ | Agent核心逻辑、协商机制 | Fig 1(a)(b), Methods |
| **通信协议** | WebSocket / SSE | 实时数据传输、Agent消息同步 | Methods |
| **数据持久化** | SQLite + JSON | Evidence Package、事件日志 | SI |

---

## 2. 多智能体系统架构（核心创新）

> **这是论文 Figure 1 的核心内容，必须在 Abstract 第1-2句和 Introduction 第1段突出**

### 2.1 为什么需要多智能体？

传统SDL的局限性与本平台的解决方案：

| 传统方法 | 局限性 | 本平台解决方案 |
|---------|-------|--------------|
| **单一优化算法** (BO/GP) | 只关注参数优化，忽视数据质量 | 专设 **CriticAgent** 守护数据质量 |
| **规则驱动自动化** | 缺乏对异常情况的适应性 | 多Agent协商实现**柔性决策** |
| **端到端黑箱模型** | 决策不可解释，无法审计 | Agent间对话**全程可追溯** |
| **单体式架构** | 难以扩展到新任务 | 模块化Agent**可插拔替换** |

### 2.2 三层架构全景图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    Universal Closed-Loop Multi-Agent SDL Platform               │
│                         通用闭环多智能体自主实验平台                                │
│                                                                                  │
│                        ┌────────────────────────────┐                           │
│                        │    Frontend (React UI)     │  ← 人机交互界面             │
│                        │  Dashboard / Monitor / Log │                           │
│                        └────────────┬───────────────┘                           │
│                                     │ WebSocket                                 │
│  ═══════════════════════════════════╪═══════════════════════════════════════════│
│                                     ▼                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║                 🧠 Multi-Agent Cognitive Layer (数字世界)                   ║  │
│  ╠═══════════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                            ║  │
│  ║   ┌────────────────────────────────────────────────────────────────────┐  ║  │
│  ║   │                    Orchestrator (中央调度器)                         │  ║  │
│  ║   │      • 全局状态机  • 安全边界约束  • Agent协调调度  • 事件日志        │  ║  │
│  ║   └────────────────────────┬───────────────────────────────────────────┘  ║  │
│  ║                            │                                               ║  │
│  ║            ┌───────────────┼───────────────┐                               ║  │
│  ║            │               │               │                               ║  │
│  ║            ▼               ▼               ▼                               ║  │
│  ║    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                        ║  │
│  ║    │   Planner   │ │  MainAgent  │ │   Critic    │  ← 核心决策三角         ║  │
│  ║    │  (规划者)   │ │  (决策者)   │ │  (批判者)   │                        ║  │
│  ║    │             │ │             │ │             │                        ║  │
│  ║    │ • 采样策略  │ │ • 综合判断  │ │ • 质量评估  │                        ║  │
│  ║    │ • 探索/利用 │ │ • 动作选择  │ │ • 风险预警  │                        ║  │
│  ║    │ • 停止判断  │ │ • 异常处理  │ │ • 重测建议  │                        ║  │
│  ║    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘                        ║  │
│  ║           │               │               │                               ║  │
│  ║           └───────────────┼───────────────┘                               ║  │
│  ║                           │                                               ║  │
│  ║            ┌──────────────┴──────────────┐                                ║  │
│  ║            │     MessageBus (消息总线)    │  ← 松耦合通信中枢               ║  │
│  ║            │  • 路由分发  • 事件广播  • 审计记录                           ║  │
│  ║            └──────────────┬──────────────┘                                ║  │
│  ║                           │                                               ║  │
│  ║    ┌──────────────────────┼──────────────────────┐                        ║  │
│  ║    │                      │                      │                        ║  │
│  ║    ▼                      ▼                      ▼                        ║  │
│  ║ ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐                   ║  │
│  ║ │ Literature  │   │  Analysis   │   │   Knowledge     │  ← 支撑Agent      ║  │
│  ║ │   Agent     │   │   Agent     │   │     Base        │                   ║  │
│  ║ │ (文献检索)  │   │ (数据分析)  │   │   (知识库)      │                   ║  │
│  ║ └─────────────┘   └─────────────┘   └─────────────────┘                   ║  │
│  ║                                                                            ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                     │                                           │
│                                     │ Digital-Physical Bridge                   │
│                                     ▼                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║               ControllerAdapter (控制器适配层)                              ║  │
│  ║     • 策略→硬件指令  • 硬件反馈→Evidence  • 安全边界检查                     ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                     │                                           │
│                                     ▼                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║                    Physical Execution Layer (物理世界)                      ║  │
│  ║       [温控系统]  ←→  [电化学工作站CHI]  ←→  [样品单元/环境腔]               ║  │
│  ║        RS-232          VISA/GUI-RPA           手动装载                       ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Planner-Critic 博弈机制（最核心创新）

> **对应论文 Figure 1(b): Game-theoretic deliberation**

| Agent | 类比角色 | 决策倾向 | 风险偏好 | 核心职责 |
|-------|---------|---------|---------|---------|
| **Planner** | 探索型科学家 | 追求新发现 | Risk-Seeking | 提出下一步实验建议 |
| **Critic** | 保守型审稿人 | 确保质量 | Risk-Averse | 评估决策/测量质量 |
| **Orchestrator** | 实验室主管 | 平衡效率与质量 | Risk-Neutral | 协调Agent、执行决策 |

**博弈过程可视化**：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Planner-Critic 博弈决策流程                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  当前状态: T = -50°C, 已测20点, 检测到相位跳变                         │
│                                                                     │
│  ┌─────────────────┐          ┌─────────────────┐                  │
│  │    Planner      │          │     Critic      │                  │
│  │   (Risk-Seeking)│          │  (Risk-Averse)  │                  │
│  └────────┬────────┘          └────────┬────────┘                  │
│           │                            │                           │
│           ▼                            ▼                           │
│  ┌─────────────────┐          ┌─────────────────┐                  │
│  │ 建议: 加密采样   │          │ 评估: 当前数据   │                  │
│  │ T_next = -48°C  │          │ R² = 0.92 (B级) │                  │
│  │ 步长: 2°C→0.5°C │          │ 建议: 可接受    │                  │
│  │ 置信度: 0.85    │          │ 评分: 0.88      │                  │
│  └────────┬────────┘          └────────┬────────┘                  │
│           │                            │                           │
│           └──────────┬─────────────────┘                           │
│                      ▼                                             │
│           ┌─────────────────────┐                                  │
│           │    Orchestrator     │                                  │
│           │   (仲裁 + 执行)      │                                  │
│           └─────────┬───────────┘                                  │
│                     │                                              │
│                     ▼                                              │
│           ┌─────────────────────┐                                  │
│           │ 最终决策:           │                                  │
│           │ • 接受Planner建议   │                                  │
│           │ • 执行: SET_T -48°C │                                  │
│           │ • 记录到事件日志     │                                  │
│           └─────────────────────┘                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Agent完整清单与职责矩阵

### 3.1 Agent角色定义

**核心文件**: `frontend_web/backend/agents/protocol.py`

```python
class AgentRole(str, Enum):
    """
    Agent角色枚举 - 与当前实现一致
    """
    ORCHESTRATOR = "orchestrator"   # 全局调度
    MAIN_AGENT = "main_agent"       # 主决策
    ANALYSIS = "analysis"           # EIS/Arrhenius分析
    LITERATURE = "literature"       # 文献检索
    CRITIC = "critic"               # 质量评估
    KNOWLEDGE = "knowledge"         # 长期知识库
    EXECUTION = "execution"         # 执行代理（预留）
    SEGMENTATION = "segmentation"   # 变化点/分段
    RECOVERY = "recovery"           # 异常恢复
    RECOMMENDER = "recommender"     # 规划建议（语义等价于 Planner）
```

> 说明：论文叙事中可继续使用 **Planner**，代码协议层使用 `RECOMMENDER` 作为角色标识。

### 3.2 Agent职责矩阵

| Agent | 核心文件 | 输入 | 输出 | 触发条件 | 论文对应 |
|-------|---------|------|------|---------|---------|
| **Orchestrator** | `orchestrator.py` | 全局状态、Agent消息 | 执行指令、事件日志 | 持续运行 | Fig 1(a) 中心 |
| **MainAgent** | `main_agent_client.py` | 多源信息 | 最终决策 | 每个循环 | Fig 1(a) |
| **PlannerAgent** | `planner_agent.py` | 历史数据、覆盖率 | 采样策略建议 | PLAN阶段 | Fig 1(b) 左 |
| **CriticAgent** | `critic_agent.py` | 测量数据、决策 | 质量评分、改进建议 | 测量后/决策前 | Fig 1(b) 右 |
| **EIS工具链** | `tools_eis.py` | 原始EIS数据 | Rb、σ、拟合参数 | EIS测量后 | Fig 2(a) |
| **LiteratureAgent** | `literature_search.py` | 查询关键词 | 相关文献摘要 | 检测到异常 | Methods |
| **KnowledgeBase** | `knowledge/` | 实验结果 | 材料先验、历史模式 | 查询/更新 | Methods |
| **Segmentation** | `arrhenius_segmentation.py` | σ(T)数据 | 分段Ea、变化点 | 数据足够时 | Fig 3 |

### 3.3 Agent间消息类型

```python
class MessageType(str, Enum):
    """消息类型 - 对应 protocol.py 当前实现"""
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    EVENT = "EVENT"
    QUERY = "QUERY"
    BROADCAST = "BROADCAST"
    HEARTBEAT = "HEARTBEAT"
    ACK = "ACK"
    ERROR = "ERROR"
    CANCEL = "CANCEL"
```

> AM写作建议：Methods 中建议强调 `EVENT + HEARTBEAT + PRIORITY + TTL` 的组合，用于证明系统不仅可协同，而且可运维、可审计。

---

## 4. 消息总线与通信协议

### 4.1 MessageBus 设计

**核心文件**: `frontend_web/backend/agents/message_bus.py`

```python
class MessageBus:
    """
    消息总线 - 多Agent系统的通信中枢

    设计原则（支撑论文通用性主张）:
    1. 松耦合：Agent之间不直接通信，通过总线路由
    2. 可观测：所有消息都被记录，支持调试和审计
    3. 可扩展：新Agent只需注册到总线即可加入系统
    """

    def __init__(self, socketio=None):
        self._agents: Dict[AgentRole, BaseAgent] = {}
        self._subscribers: Dict[str, Set[AgentRole]] = defaultdict(set)
        self._message_log: List[AgentMessage] = []

    def register_agent(self, agent: 'BaseAgent'):
        self._agents[agent.role] = agent

    def dispatch(self, message: AgentMessage):
        self._message_log.append(message)

        if message.type == MessageType.BROADCAST:
            self._broadcast(message)
        elif message.type == MessageType.EVENT:
            self._publish_event(message)
        else:
            self._send_to_agent(message)

    def subscribe(self, event_type: str, role: AgentRole):
        self._subscribers[event_type].add(role)

    def publish_event(self, event_type: str, payload: Dict, sender: AgentRole):
        message = AgentMessage(
            type=MessageType.EVENT,
            sender=sender,
            action=event_type,
            payload=payload
        )
        self.dispatch(message)
```
### 4.2 Agent消息结构

```python
@dataclass
class AgentMessage:
    """Agent间通信的标准消息格式（与 protocol.py 对齐）"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    type: MessageType = MessageType.REQUEST
    sender: AgentRole = AgentRole.ORCHESTRATOR
    receiver: AgentRole = AgentRole.MAIN_AGENT
    action: str = ""                   # 动作名或事件名
    payload: Dict = field(default_factory=dict)
    correlation_id: Optional[str] = None
    priority: int = MessagePriority.NORMAL
    ttl: int = 60
    status: MessageStatus = MessageStatus.PENDING
```
### 4.3 通信流程示例

```
┌─────────────────────────────────────────────────────────────────────┐
│                    典型Agent通信流程                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Orchestrator 请求 RECOMMENDER(Planner语义) 给出建议              │
│     ┌────────────────────────────────────────────────────────────┐ │
│     │ {type: REQUEST, sender: ORCHESTRATOR, receiver: RECOMMENDER,│ │
│     │  payload: {state: {...}, evidence: {...}}}                 │ │
│     └────────────────────────────────────────────────────────────┘ │
│                              │                                      │
│                              ▼                                      │
│  2. RECOMMENDER 返回建议                                            │
│     ┌────────────────────────────────────────────────────────────┐ │
│     │ {type: RESPONSE, sender: RECOMMENDER, receiver: ORCHESTRATOR,││
│     │  payload: {action: "SET_T", value: -48, strategy: FOCUSED}}│ │
│     └────────────────────────────────────────────────────────────┘ │
│                              │                                      │
│                              ▼                                      │
│  3. Orchestrator 发布 EVENT（如 PLANNER_SUGGESTION / TOOL_CALL）    │
│     ┌────────────────────────────────────────────────────────────┐ │
│     │ {type: EVENT, sender: ORCHESTRATOR,                        │ │
│     │  action: "PLANNER_SUGGESTION",                            │ │
│     │  payload: {temperature: -50, phase_jump: 0.23}}            │ │
│     └────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```
---

## 5. 数字-物理桥接层

### 5.1 ControllerAdapter 设计

> **对应论文 Figure 1(c): Digital-Physical Bridge**

```python
class ControllerAdapter:
    """
    控制器适配器 - 数字世界与物理世界的桥梁
    
    职责:
    1. 将Agent的高级决策转换为硬件指令
    2. 将硬件反馈封装为Evidence
    3. 执行安全边界检查
    """
    
    def __init__(self, safety_limits: SafetyLimits):
        self.safety_limits = safety_limits
        self.hardware_interface = HardwareInterface()
        
    def execute_action(self, action: AgentAction) -> ActionResult:
        """
        执行动作 - 将Agent决策转为硬件操作
        
        支持的动作类型:
        - SET_T: 设置目标温度
        - WAIT_STABLE: 等待温度稳定
        - EIS_RUN: 执行EIS测量
        - ANALYZE_EIS: 分析EIS数据
        """
        # 安全检查
        if not self._check_safety(action):
            return ActionResult(success=False, error="Safety limit exceeded")
            
        # 执行硬件操作
        if action.type == "SET_T":
            result = self.hardware_interface.set_temperature(action.value)
        elif action.type == "EIS_RUN":
            result = self.hardware_interface.run_eis_measurement()
        # ...
        
        # 封装为Evidence
        evidence = self._package_evidence(action, result)
        return ActionResult(success=True, evidence=evidence)
```

### 5.2 安全边界约束

```python
@dataclass
class SafetyLimits:
    """安全边界 - 保护硬件和样品"""
    T_min: float = -120.0     # 最低温度 (°C)
    T_max: float = 100.0      # 最高温度 (°C)
    max_step: float = 10.0    # 最大步长 (°C)
    max_retries: int = 3      # 最大重测次数
    min_dwell_s: float = 30.0   # 最小稳定等待时间 (s)
    max_dwell_s: float = 600.0  # 最大稳定等待时间 (s)
```

### 5.3 支持的硬件动作

| 动作标识 | 功能 | 参数 | 硬件映射 |
|---------|------|------|---------|
| `SET_T` | 设置目标温度 | `value: float` | 温控器RS-232 |
| `WAIT_STABLE` | 等待温度稳定 | `tolerance: float` | 温控器读取 |
| `EIS_RUN` | 执行EIS测量 | `freq_range, amplitude` | CHI工作站 |
| `ANALYZE_EIS` | 分析EIS数据 | `raw_data_path` | 后端计算 |
| `ARRHENIUS_SEGMENT` | Arrhenius分段 | `sigma_T_data` | 后端计算 |
| `REFINE_SAMPLING` | 触发精细采样 | `T_center, T_range` | 调度逻辑 |
| `STOP` | 停止实验 | `reason` | 全局控制 |

---

## 6. 前端交互层设计

### 6.1 页面架构

> **对应论文 Figure S6: Platform User Interface**

当前前端路由（与 `frontend/src/App.jsx` 一致）：

- `/dashboard`：主控台（设备控制 + Agent思考链 + 工具调度）
- `/monitor`：实时监控（温度/电导率曲线 + 最新测量）
- `/arrhenius`：Arrhenius分析与相变点回看
- `/history`：实验历史、详情和报告展示（报告作为 history 页签功能，而非独立 `/report` 路由）

### 6.2 核心组件清单

| 组件路径 | 功能 | 数据源 | 论文对应 |
|---------|------|-------|---------|
| `src/components/agent/PlannerPanel.jsx` | Planner建议可视化 | `agentStore.plannerResult` | Fig 1(b) 左 |
| `src/components/agent/CriticPanel.jsx` | Critic评分与建议可视化 | `agentStore.criticResult` | Fig 1(b) 右 |
| `src/components/agent/ThoughtChainPanel.jsx` | 决策思维链可视化 | `agentStore.thoughtChain` | Fig 5(b) |
| `src/components/agent/ToolsPanel.jsx` | 工具调度状态面板 | `agentStore.activeTools` | Methods（执行可观测性） |
| `src/components/charts/TemperatureChart.jsx` | 温度曲线 | `dataStore.temperatureHistory` | Fig 2 / Fig S2 |
| `src/components/charts/ConductivityChart.jsx` | 电导率曲线 | `dataStore.conductivityHistory` | Fig 2 |
| `src/components/charts/ArrheniusChart.jsx` | Arrhenius图 | `dataStore.arrheniusData` | Fig 3 |
| `src/components/common/ConnectionStatus.jsx` | 连接状态 | `uiStore.wsConnected` | Fig S6 |

### 6.3 状态管理设计 (Zustand)

```javascript
// src/stores/agentStore.js (当前实现摘要)
import { create } from 'zustand'

export const useAgentStore = create((set, get) => ({
  // 会话与思考链
  runId: null,
  thoughtChain: [],
  isThinking: false,

  // Agent结果
  currentDecision: null,
  criticResult: null,
  plannerResult: null,

  // Agent状态
  agentStatus: {
    mainAgent: 'idle',
    criticAgent: 'idle',
    plannerAgent: 'idle',
  },

  // 工具调度可观测性
  activeTools: [],
  toolCallCounts: {},
  toolCallHistory: [],

  // 自动决策控制
  autoDecisionEnabled: false,

  // 核心动作
  setRunId: (runId) => set({ runId }),
  addThought: (thought) => set((state) => ({ thoughtChain: [...state.thoughtChain, thought] })),
  setCriticResult: (result) => set({ criticResult: result }),
  setPlannerResult: (result) => set({ plannerResult: result }),
  activateTool: (toolId) => set((state) => ({
    activeTools: state.activeTools.includes(toolId) ? state.activeTools : [...state.activeTools, toolId]
  })),
  deactivateTool: (toolId) => set((state) => ({
    activeTools: state.activeTools.filter((id) => id !== toolId)
  })),
}))
```

> AM写作建议：建议将 `thoughtChain + toolCallHistory + criticResult` 作为可解释性证据三元组，在 Methods 和 Fig 5 中对应展示。

### 6.4 布局设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Monitor 页面布局                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┬───────────────────────┬─────────────────────┐ │
│  │  物理世界监控    │      主代理工作台       │   数字世界思维链    │ │
│  │  (Physical)     │    (Orchestrator)      │    (Cognitive)     │ │
│  ├─────────────────┼───────────────────────┼─────────────────────┤ │
│  │                 │                       │                     │ │
│  │ ┌─────────────┐ │ ┌───────────────────┐ │ ┌─────────────────┐ │ │
│  │ │ 温度曲线    │ │ │ 当前步骤          │ │ │ Planner Panel   │ │ │
│  │ │ T_set/T_act │ │ │ Step: S0023       │ │ │ 策略: FOCUSED   │ │ │
│  │ └─────────────┘ │ │ State: ACT        │ │ │ 建议: -48°C     │ │ │
│  │                 │ └───────────────────┘ │ │ 置信度: 85%     │ │ │
│  │ ┌─────────────┐ │                       │ └─────────────────┘ │ │
│  │ │ Nyquist图   │ │ ┌───────────────────┐ │                     │ │
│  │ │ 当前EIS     │ │ │ 操作日志          │ │ ┌─────────────────┐ │ │
│  │ └─────────────┘ │ │ [14:23] SET_T -50 │ │ │ Critic Panel    │ │ │
│  │                 │ │ [14:25] EIS_RUN   │ │ │ 评分: B (0.88)  │ │ │
│  │ ┌─────────────┐ │ │ [14:28] QC Pass   │ │ │ R²: 0.92        │ │ │
│  │ │ 硬件状态    │ │ └───────────────────┘ │ │ 建议: 可接受    │ │ │
│  │ │ 🟢 Connected│ │                       │ └─────────────────┘ │ │
│  │ │ 🟢 Stable   │ │ ┌───────────────────┐ │                     │ │
│  │ └─────────────┘ │ │ [人机接管] [停止]  │ │ ┌─────────────────┐ │ │
│  │                 │ └───────────────────┘ │ │ ThoughtChain    │ │ │
│  │                 │                       │ │ "检测到相变..."  │ │ │
│  │                 │                       │ └─────────────────┘ │ │
│  └─────────────────┴───────────────────────┴─────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. 部署与环境配置

### 7.1 目录结构

```
d:\V1.0-qianduan-1.29\frontend_web\
├── backend/                          # 智能体后端 (Python)
│   ├── agents/                       # Agent核心实现
│   │   ├── orchestrator.py
│   │   ├── planner_agent.py
│   │   ├── critic_agent.py
│   │   ├── main_agent_client.py
│   │   ├── tools_eis.py
│   │   ├── literature_search.py
│   │   ├── arrhenius_segmentation.py
│   │   ├── protocol.py
│   │   └── message_bus.py
│   ├── api/                          # API蓝图
│   │   ├── main_agent.py
│   │   ├── autonomous_decision.py
│   │   ├── control.py
│   │   └── data.py
│   ├── knowledge/                    # 知识库与上下文
│   ├── app.py                        # Flask入口
│   ├── config.py                     # 配置来源
│   └── start_server.py               # 启动脚本
│
└── frontend/                         # 交互界面 (React)
    ├── src/
    │   ├── components/
    │   │   ├── agent/
    │   │   ├── charts/
    │   │   ├── layout/
    │   │   └── common/
    │   ├── pages/
    │   ├── stores/
    │   ├── api/
    │   ├── services/
    │   └── utils/
    ├── package.json
    └── vite.config.js
```
### 7.2 启动步骤

#### 第一步：启动智能体后端

```bash
cd frontend_web/backend

# 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 启动服务 (默认端口 5000)
python start_server.py
```

#### 第二步：启动前端界面

```bash
cd frontend_web/frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问地址: `http://localhost:5173`

> 前端代理默认指向 `http://localhost:5000`，见 `frontend/vite.config.js`。

### 7.3 配置文件

当前实现以 **Python配置模块 + 环境变量** 为主：

```python
# backend/config.py (节选)
class Config:
    HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
    PORT = int(os.environ.get("FLASK_PORT", 5000))
    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    SOCKETIO_ASYNC_MODE = "threading"
```

```bash
# 推荐运行时环境变量
set FLASK_ENV=development
set FLASK_PORT=5000
set MAIN_AGENT_USE_EXTERNAL=true
set OPENROUTER_API_KEY=your_key_here
```

Orchestrator侧关键参数在代码中注入（可在创建实例时覆盖）：
- `SafetyLimits`: `T_min/T_max/max_step/max_retries`
- `main_agent_config`: `use_external_api/base_url/model/timeout`
- `enable_literature_search`

## 8. AM投稿强化表达（基于当前实现）

1. **架构创新**：强调 `Orchestrator + Planner/Critic/Main + MessageBus` 的认知解耦，而不是“单模型优化器”。
2. **可执行创新**：强调决策事件可落地到 `TOOL_CALL/TOOL_RESULT`，形成“决策-执行”闭环证据。
3. **可审计创新**：强调 `thought_chain_event + orchestrator event log + message_log` 的多源审计链。
4. **可迁移创新**：强调 EIS工具链可替换，其余协调层可复用，支撑 Raman/XRD 等迁移叙事。
5. **前端贡献写法**：将 Dashboard/Monitor/Arrhenius/History 定位为“科学工作流可视化界面”，不是普通管理后台。

### 8.1 功能闭环映射（建议直接用于 Methods）

| 功能目标 | 后端实现 | 前端呈现 | 可审计证据 |
|---------|---------|---------|-----------|
| 自主决策 | `orchestrator.process_cycle()` + `main_agent.decide()` | `ThoughtChainPanel` 实时显示决策链 | `DECISION`, `UI_THOUGHT` |
| 质量守门 | `critic_agent.critique_decision/measurement` | `CriticPanel` 评分与建议 | `DECISION_CRITIQUE`, `MEASUREMENT_CRITIQUE` |
| 自适应采样 | `planner_agent.suggest_next_step()` | `PlannerPanel` 策略与置信度 | `PLANNER_SUGGESTION` |
| 执行动作 | `_execute_action()` + controller adapter | `ToolsPanel` 工具激活/完成态 | `TOOL_CALL`, `TOOL_RESULT` |
| 跨循环学习 | `knowledge/context_manager` 更新 | History 页面回看实验上下文 | `PATTERN_MATCH`, `LITERATURE_SEARCH` |

### 8.2 投稿措辞建议（避免“工程描述”）

1. 用 “traceable autonomous experimentation loop” 替代 “自动化流程”。
2. 用 “online quality gate by CriticAgent” 替代 “后处理质控”。
3. 用 “decision-to-actuation executable bridge” 替代 “接口联调”。
4. 每个创新点都配一条实现证据（代码入口 + 事件类型 + 图号）。
---

## 与论文Figure的对应关系

| 论文Figure | 本文档对应章节 | 核心内容 |
|-----------|--------------|---------|
| **Fig 1(a)** | §2.2, §3 | 多Agent架构全景图、Agent清单 |
| **Fig 1(b)** | §2.3 | Planner-Critic博弈机制 |
| **Fig 1(c)** | §5 | 数字-物理桥接 |
| **Fig 1(d)** | Part 2 §1 | Plan-Act-Observe-Learn 闭环 |
| **Fig 5(a)** | Part 2 §4 | Evidence Package结构 |
| **Fig 5(b)** | Part 2 §3 | Agent协商时间线 |
| **Fig S6** | §6 | UI界面截图 |

---

**下接 Part 2**: [Agent深度实现与Evidence系统](./FRONTEND_AGENT_GUIDE_PART2.md)
















