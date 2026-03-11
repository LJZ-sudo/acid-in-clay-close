# 通用闭环多智能体自主阻抗谱平台：从架构设计到科学发现的完整写作指南

**文档版本**: v6.1 (Implementation-Aligned AM Submission Edition)  
**更新日期**: 2026-02-08  
**适用范围**: 用于整合 `frontend_web`（前后端与多Agent）、`close`（闭环验证）与平台说明文档，输出可直接投稿 AM/AFM/Nature Communications 的深度架构与写作框架  
**关键词**: Self-Driving Laboratory (SDL), Closed-Loop Autonomous Experimentation, Multi-Agent System (MAS), Electrochemical Impedance Spectroscopy (EIS), Digital-Physical Bridge, Evidence-Driven Decision Making, Bayesian-Compatible Framework

**目标期刊**: Advanced Materials (IF ~32) / Advanced Functional Materials (IF ~19) / Nature Communications (IF ~17)

---

# 第零章：文章定位与写作策略

## 0.1 SDL领域的学术定位

**自驱动实验室（Self-Driving Laboratory, SDL）** 是当前材料科学与化学领域最前沿的研究范式之一。根据 Nature Reviews Materials (2023) 的定义，SDL 是指"能够自主设计实验、执行测量、分析数据并迭代优化的闭环系统"。

**本平台的学术定位**：
- **不是**简单的实验自动化（Automation）
- **是**具有认知能力的自主科学发现系统（Autonomous Discovery System）
- **核心差异化**：引入"Planner-Critic 博弈机制"，模拟人类科学家的假设-验证循环

## 0.2 AM投稿的核心卖点（实现证据版）

| 卖点维度 | 论文主张（建议写法） | 代码与数据证据 |
|---------|--------------------|---------------|
| **架构创新** | 多智能体认知解耦，不是单一优化器 | `orchestrator.py` + `planner_agent.py` + `critic_agent.py` + `message_bus.py` |
| **科学发现** | ΔEa温度依赖关系可由闭环高质量数据稳定识别 | `close/phase3/step3_confinement_analysis.py` + 分段统计结果 |
| **可复现性** | 决策、执行、评估全链路可追溯 | `TOOL_CALL/TOOL_RESULT/DECISION_CRITIQUE/MEASUREMENT_CRITIQUE` 事件链 |
| **可迁移性** | 认知层与执行层解耦，便于迁移至Raman/FTIR/XRD | Orchestrator + ControllerAdapter + 可替换工具链 |

> 写法建议：核心卖点必须由“主张 + 证据”成对出现，避免只写概念不写实现入口。

## 0.3 写作时间规划（建议 5-7 天）

| 阶段 | 天数 | 任务 | 输出 |
|-----|-----|------|-----|
| **Day 1** | 1 | 搭建主线：Abstract + Introduction + Conclusion | 核心叙事框架 |
| **Day 2-3** | 2 | 填充 Results：Part 1-4 的实验验证 | 图表初稿 |
| **Day 4** | 1 | 完善 Methods：算法细节 + 代码映射 | SI 附录 |
| **Day 5-6** | 2 | Discussion + 润色 + 审稿人预判 | 完整初稿 |
| **Day 7** | 1 | 格式调整 + SI 整理 + Cover Letter | 投稿包 |

## 0.4 投稿前一致性红线（必须检查）

1. 角色命名：论文可称 Planner，但协议角色是 `RECOMMENDER`。
2. 状态机命名：统一写为 `IDLE → PLAN → ACT → OBSERVE → LEARN`。
3. 后端端口与前端代理：默认 `5000`，代理配置在 `frontend/vite.config.js`。
4. 配置来源：`backend/config.py` + 环境变量，不使用 `config.yaml` 叙事。
5. 路由声明：前端页面为 `/dashboard`、`/monitor`、`/arrhenius`、`/history`。

## 0.5 AM审稿人高频问题与应对

| 审稿人问题 | 风险点 | 建议证据 |
|-----------|-------|---------|
| 这是否只是自动化脚本？ | 创新性不足 | 强调 Planner-Critic-Orchestrator 的博弈仲裁和事件证据 |
| 决策是否黑箱？ | 可解释性不足 | 提供 Fig 5(b) 协商时间线 + 事件字段映射表 |
| 质量控制是否后处理？ | 方法贡献不足 | 说明 Critic 是在线质量门（决策前+测量后双评估） |
| 能否迁移到其他表征？ | 普适性不足 | 给出 ControllerAdapter + 工具替换路径和复用边界 |

> **写作核心句（必须出现在 Abstract 第2句和 Introduction 最后一段）**：
> *"We introduce an Orchestrator-ControllerAdapter architecture that bridges the Digital World (AI decision-making) and the Physical World (hardware execution), enabling evidence-driven autonomous experimentation—a defining characteristic of next-generation Self-Driving Laboratories."*

---

# 第一章：核心创新点深度解析（Part 1）

本章是文章的**灵魂**，必须在 Abstract（前100词）和 Introduction（第1-2段）中精准传达。

> **核心主张**：本平台的首要创新是**通用闭环多智能体自主实验架构（Universal Closed-Loop Multi-Agent Autonomous Experimentation Architecture）**，这是区别于传统单一算法驱动SDL的本质特征。

---

## 1.1 创新点一：多智能体协作系统架构（Multi-Agent Collaborative System）

### 1.1.1 为什么需要多智能体？——超越单一算法的范式创新

传统SDL系统的局限性：

| 传统方法 | 局限性 | 本平台解决方案 |
|---------|-------|--------------|
| **单一优化算法** (如BO/GP) | 只关注参数优化，忽视数据质量 | 专设 CriticAgent 守护数据质量 |
| **规则驱动自动化** | 缺乏对异常情况的适应性 | 多Agent协商实现柔性决策 |
| **端到端黑箱模型** | 决策不可解释，无法审计 | Agent间对话全程可追溯 |
| **单体式架构** | 难以扩展到新任务 | 模块化Agent可插拔替换 |

**本平台的核心主张**：科学发现是一个**协作过程**，需要多种认知能力的配合——规划、执行、批判、记忆、学习。我们通过多智能体系统（Multi-Agent System, MAS）将这些认知功能显式解耦，形成可协作、可审计、可扩展的自主实验架构。

### 1.1.2 多智能体系统全景架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    Universal Closed-Loop Multi-Agent SDL Platform               │
│                         通用闭环多智能体自主实验平台                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║                    🧠 Multi-Agent Cognitive Layer                          ║  │
│  ║                         多智能体认知层                                       ║  │
│  ╠═══════════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                            ║  │
│  ║   ┌────────────────────────────────────────────────────────────────────┐  ║  │
│  ║   │                    Orchestrator (中央调度器)                         │  ║  │
│  ║   │         • 全局状态管理  • 安全边界约束  • Agent协调调度               │  ║  │
│  ║   └────────────────────────┬───────────────────────────────────────────┘  ║  │
│  ║                            │                                               ║  │
│  ║           ┌────────────────┼────────────────┐                              ║  │
│  ║           │                │                │                              ║  │
│  ║           ▼                ▼                ▼                              ║  │
│  ║   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                       ║  │
│  ║   │  Planner    │  │  MainAgent  │  │   Critic    │                       ║  │
│  ║   │  (规划者)    │  │  (决策者)   │  │  (批判者)   │                       ║  │
│  ║   │             │  │             │  │             │                       ║  │
│  ║   │ • 采样策略  │  │ • 综合判断  │  │ • 质量评估  │                       ║  │
│  ║   │ • 探索优化  │  │ • 动作选择  │  │ • 风险预警  │                       ║  │
│  ║   │ • 停止判断  │  │ • 异常处理  │  │ • 重测建议  │                       ║  │
│  ║   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                       ║  │
│  ║          │                │                │                              ║  │
│  ║          └────────────────┼────────────────┘                              ║  │
│  ║                           │                                               ║  │
│  ║           ┌───────────────┴───────────────┐                               ║  │
│  ║           │        MessageBus (消息总线)    │                               ║  │
│  ║           │   • 松耦合通信  • 事件广播  • 审计日志                          │  ║  │
│  ║           └───────────────┬───────────────┘                               ║  │
│  ║                           │                                               ║  │
│  ║   ┌───────────────────────┼───────────────────────┐                       ║  │
│  ║   │                       │                       │                       ║  │
│  ║   ▼                       ▼                       ▼                       ║  │
│  ║ ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐                   ║  │
│  ║ │ Literature  │   │  Analysis   │   │   Knowledge     │                   ║  │
│  ║ │   Agent     │   │   Agent     │   │     Base        │                   ║  │
│  ║ │ (文献检索)  │   │ (数据分析)  │   │   (知识库)      │                   ║  │
│  ║ │             │   │             │   │                 │                   ║  │
│  ║ │ • 先验知识  │   │ • EIS拟合   │   │ • 材料先验      │                   ║  │
│  ║ │ • 相变参考  │   │ • Arrhenius │   │ • 历史模式      │                   ║  │
│  ║ │ • 机理文献  │   │ • 分段检测  │   │ • 洞见积累      │                   ║  │
│  ║ └─────────────┘   └─────────────┘   └─────────────────┘                   ║  │
│  ║                                                                            ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                      │                                          │
│                                      │ Digital-Physical Bridge                  │
│                                      ▼                                          │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║               ControllerAdapter (控制器适配层)                              ║  │
│  ║     • 策略→指令转换  • 硬件反馈→证据封装  • 安全边界检查                     ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                      │                                          │
│                                      ▼                                          │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║                    Physical Execution Layer (物理执行层)                    ║  │
│  ║         [温控系统]  ←→  [电化学工作站]  ←→  [样品单元]                       ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1.3 Agent角色定义与职责分工

**核心文件**: `frontend_web/backend/agents/protocol.py`

```python
class AgentRole(str, Enum):
    """当前实现的Agent角色"""
    ORCHESTRATOR = "orchestrator"   # 调度器
    MAIN_AGENT = "main_agent"       # 主决策
    ANALYSIS = "analysis"           # 分析（协议保留）
    LITERATURE = "literature"       # 文献检索
    CRITIC = "critic"               # 质量守门
    KNOWLEDGE = "knowledge"         # 长期知识
    EXECUTION = "execution"         # 执行代理（协议保留）
    SEGMENTATION = "segmentation"   # Arrhenius分段
    RECOVERY = "recovery"           # 异常恢复
    RECOMMENDER = "recommender"     # 规划建议（论文中对应Planner）

class MessageType(str, Enum):
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

> 投稿建议：正文可保持 “Planner” 术语，但 Methods/SI 应注明协议层角色为 `RECOMMENDER`，防止实现与叙事不一致。
### 1.1.4 Planner-Critic 博弈机制——科学决策的对抗性验证

**这是本平台最核心的创新**：引入**博弈论启发的决策机制**，模拟人类科学家的认知过程：

| Agent | 类比角色 | 决策倾向 | 风险偏好 | 核心职责 |
|-------|---------|---------|---------|---------|
| **Planner** | 探索型科学家 | 追求新发现 | Risk-Seeking | 提出下一步实验建议 |
| **Critic** | 保守型审稿人 | 确保质量 | Risk-Averse | 评估决策/测量质量 |
| **Orchestrator** | 实验室主管 | 平衡效率与质量 | Risk-Neutral | 协调Agent、执行决策 |

**博弈的科学意义**：
- **Planner** 倾向于探索（如：在相变区加密采样、尝试新温度点）
- **Critic** 倾向于稳健（如：要求重测低质量数据、拒绝高风险操作）
- **Orchestrator** 作为仲裁者，根据双方评估做出最终决策

这种设计避免了单一算法的"过拟合"和"盲目探索"问题。

### 1.1.5 完整的Agent协作流程

**核心文件**: `frontend_web/backend/agents/orchestrator.py`

```python
# Orchestrator 的核心循环实现 - Plan-Act-Observe-Learn 闭环
def process_cycle(self, current_state: Dict, current_evidence: Dict) -> Dict:
    """
    执行一个完整的 Plan → Act → Observe → Learn 循环
    
    这是SDL的核心：每个循环都是一个"假设-实验-验证"的微型科学发现过程
    体现了多Agent协作的完整流程
    """
    
    # ═══════════════════════════════════════════════════════════════════
    # PLAN 阶段：多Agent协商决策
    # ═══════════════════════════════════════════════════════════════════
    
    # Step 1: Planner 给出采样策略建议
    planner_suggestion = self.planner.suggest_next_step(state, evidence, history)
    #         ↑ 考虑：覆盖率、相变信号、数据质量趋势
    
    # Step 2: 检测到异常信号时，调用 Literature Agent 获取先验
    if evidence.phase_jump > 0.15:
        lit_results = self.literature_agent.search(
            query=f"phase transition {material_name} {temperature_range}",
            topk=5
        )
        # 将文献先验注入决策上下文
        enhanced_context = self._merge_literature(context, lit_results)
    
    # Step 3: MainAgent 综合所有信息做出最终决策
    decision = self.main_agent.decide(
        state=state,
        evidence=evidence,
        planner_suggestion=planner_suggestion,
        literature_context=enhanced_context,
        history=self.context_manager.get_recent_history()
    )
    
    # Step 4: Critic 评估决策质量（对抗性验证）
    decision_critique = self.critic.critique_decision(
        decision=decision,
        state=state,
        evidence=evidence
    )
    
    # Step 5: 根据 Critic 评估决定是否修正决策
    if decision_critique.score < 0.5:
        decision = self._modify_decision_based_on_critique(
            original_decision=decision,
            critique=decision_critique
        )
    
    # ═══════════════════════════════════════════════════════════════════
    # ACT 阶段：通过 ControllerAdapter 执行物理操作
    # ═══════════════════════════════════════════════════════════════════
    
    for action in decision.next_actions:
        action_result = self._execute_action(action)  # 硬件指令执行
        
    # ═══════════════════════════════════════════════════════════════════
    # OBSERVE 阶段：收集证据、更新状态
    # ═══════════════════════════════════════════════════════════════════
    
    new_evidence = self._collect_evidence(action_result)
    
    # Critic 再次评估测量质量
    measurement_critique = self.critic.critique_measurement(new_evidence)
    
    # 更新知识库和上下文
    self.knowledge_base.update(new_evidence)
    self.context_manager.add_step(...)
    
    return {"evidence": new_evidence, "critique": measurement_critique}
```

### 1.1.6 消息总线：Agent通信的神经网络

**核心文件**: `frontend_web/backend/agents/message_bus.py`

```python
class MessageBus:
    """
    消息总线 - 多Agent系统的通信中枢
    
    设计原则（支撑通用性）:
    1. 松耦合：Agent之间不直接通信，通过总线路由（可随时替换Agent实现）
    2. 可观测：所有消息都被记录，支持调试和审计（满足可复现性要求）
    3. 可扩展：新Agent只需注册到总线即可加入系统（支持扩展到其他表征技术）
    """
    
    def register_agent(self, agent: 'BaseAgent'):
        """注册Agent - 新Agent加入系统的唯一入口"""
        
    def dispatch(self, message: AgentMessage):
        """分发消息 - 根据消息类型自动路由"""
        
    def subscribe(self, event_type: str, role: AgentRole):
        """订阅事件 - 实现发布-订阅模式"""
        
    def publish_event(self, event_type: str, payload: Dict, sender: AgentRole):
        """发布事件 - 广播给所有订阅者"""
```

### 1.1.7 AM写作建议——突出多智能体创新

**在 Abstract 第1-2句（最重要位置）的表述**：
> "We present a **Universal Closed-Loop Multi-Agent Platform** for autonomous electrochemical impedance spectroscopy (EIS), where specialized AI agents—Planner, Critic, and Orchestrator—collaborate through structured deliberation to drive scientific discovery. Unlike single-algorithm approaches, this multi-agent architecture explicitly decomposes the cognitive functions of scientific inquiry into cooperative, auditable, and extensible modules."

**在 Introduction 第1段的表述**：
> "The transition from automated experimentation to truly autonomous discovery requires systems that can not only execute experiments but also plan, evaluate, learn, and adapt. We argue that this cognitive complexity cannot be adequately captured by a single optimization algorithm. Instead, we propose a **Multi-Agent System (MAS)** paradigm where distinct agents embody different aspects of scientific reasoning: a risk-seeking Planner proposes experiments, a risk-averse Critic ensures data quality, and a neutral Orchestrator mediates their deliberation."

**Figure 1 建议**（最重要的图）：
- **(a)** 多Agent认知层全景图（突出 Planner-Critic-Orchestrator 三角关系）
- **(b)** Agent间消息流示意（展示 MessageBus 的路由机制）
- **(c)** 一个实际的博弈案例（如：Planner建议探索 vs Critic要求重测）
- **(d)** 与传统单算法SDL的对比图

---

## 1.2 创新点二：数字-物理可执行桥接（Digital-Physical Executable Bridge）

### 1.2.1 概念定义与学术意义

有了多智能体的"大脑"，还需要能够"手脚"——将AI决策转化为物理操作。传统自动化系统存在"决策-执行断层"：AI算法输出的是"建议"，需要人工转化为硬件指令。

本平台通过 **ControllerAdapter** 实现了"决策即执行"（Decision-as-Action）：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Digital World (数字世界)                          │
│                                                                         │
│  Multi-Agent Layer: [Planner] ⟷ [MainAgent] ⟷ [Critic]                │
│                          │                                              │
│                          ▼                                              │
│                    [Orchestrator]                                       │
│                          │                                              │
│  ════════════════════════╪══════════════════════════════════════════════│
│                          │  Digital-Physical Bridge                     │
│                          ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │              ControllerAdapter (控制器适配器)                        ││
│  │                                                                      ││
│  │  输入: Agent决策 (SET_T=200K, EIS_RUN, WAIT_STABLE)                 ││
│  │                         ↓                                            ││
│  │  转换: 策略 → 硬件指令 (串口命令、VISA协议、GUI操作)                  ││
│  │                         ↓                                            ││
│  │  输出: Evidence Package (原始数据、拟合结果、质量指标)                ││
│  │                                                                      ││
│  │  安全: 边界检查 (T∈[-120,100]°C, max_step≤10°C)                     ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                          │                                              │
│  ════════════════════════╪══════════════════════════════════════════════│
│                          ▼                                              │
│                        Physical World (物理世界)                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                          │
│  │ 温控系统  │───▶│ CHI工作站│───▶│ 样品单元 │                          │
│  │ (RS-232) │    │ (VISA/RPA)│    │ (EIS测量)│                          │
│  └──────────┘    └──────────┘    └──────────┘                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2.2 与贝叶斯优化框架的兼容性

本平台的多Agent架构天然兼容贝叶斯优化（Bayesian Optimization, BO）框架：

| BO组件 | 本平台对应模块 | 接口设计 |
|-------|--------------|---------|
| **Surrogate Model** | KnowledgeBase + 历史测量 | `get_knowledge_context()` 提供先验 |
| **Acquisition Function** | PlannerAgent | `suggest_next_step()` 实现 UCB/EI 类逻辑 |
| **Observation Model** | CriticAgent + QC系统 | `critique_measurement()` 提供观测不确定性 |
| **Search Space** | SafetyLimits | T_min, T_max, max_step 定义边界 |

**未来扩展（Discussion 中提及）**：
> "The current rule-based Planner can be seamlessly replaced with a Gaussian Process-based acquisition function, enabling Bayesian optimization over the temperature-composition space—while preserving the Critic's quality assurance role."

### 1.2.3 AM写作建议

**在 Methods 中的表述**：
> "The ControllerAdapter serves as the executable bridge between the digital multi-agent layer and the physical instrumentation. It translates high-level agent decisions (e.g., 'measure at 200K with fine resolution') into low-level hardware commands, while also packaging raw measurement data into structured Evidence objects for subsequent agent deliberation."

---

## 1.3 创新点三：证据驱动闭环与可审计性（Evidence-Driven Closed-Loop）

### 1.3.1 Evidence Package 的设计哲学

传统自动化实验的"黑箱"问题：
- 数据来源不透明
- 决策过程不可追溯
- 无法进行同行审计

本平台通过 **Evidence Package** 解决：

```
Evidence Package 结构（每个实验步骤生成一份）
├── MeasurementEvidence (测量证据)
│   ├── raw_data_path: 原始数据文件路径
│   ├── temperature_C: 测量温度
│   ├── rb_ohm: 体电阻值
│   ├── r_squared: 拟合优度
│   ├── fit_method: 使用的拟合方法
│   └── checksum: 数据完整性校验
│
├── TransitionEvidence (转变证据)
│   ├── change_point_T: 检测到的相变温度
│   ├── phase_jump_value: 相位跳变幅度
│   ├── detection_method: BIC-DP / AIC / F-test
│   └── confidence_interval: 置信区间
│
├── AgentDeliberationTrace (Agent协商轨迹) ← 多Agent特有
│   ├── planner_suggestion: Planner建议内容
│   ├── planner_confidence: Planner置信度
│   ├── critic_score: Critic评分
│   ├── critic_issues: Critic发现的问题
│   └── final_decision: 最终执行的决策
│
└── DecisionEvidence (决策证据)
    ├── trigger_type: 触发类型 (PHASE_JUMP / QC_FAIL / PLANNER_SUGGEST)
    ├── threshold_used: 使用的阈值
    └── final_action: 最终执行的动作
```

### 1.3.2 事件日志系统——完整的审计链

```python
@dataclass
class OrchestratorEvent:
    """调度器事件 - 用于审计和复现"""
    run_id: str                  # 运行ID
    timestamp: str               # ISO格式时间戳
    event_type: str              # 事件类型
    step: str                    # 步骤ID (如 S0001)
    payload: Dict                # 事件负载
    agent: str = "Orchestrator"  # 来源Agent
```

**事件类型完整列表**：

| 事件类型 | 触发场景 | 审计用途 |
|---------|---------|---------|
| `PLANNER_SUGGESTION` | Planner给出建议 | 审查规划逻辑 |
| `DECISION_CRITIQUE` | Critic评估决策 | 审查质量把关 |
| `AGENT_DEBATE` | Agent间协商 | 追溯决策形成过程 |
| `MEASUREMENT_CRITIQUE` | Critic评估测量 | 审查数据质量 |
| `TOOL_CALL` | 调用硬件工具 | 追溯硬件操作 |
| `TOOL_RESULT` | 硬件返回结果 | 验证执行结果 |
| `LITERATURE_SEARCH` | 文献检索完成 | 审查知识引用 |
| `PATTERN_MATCH` | 知识库匹配成功 | 审查先验利用 |

### 1.3.3 AM写作建议

**在 Methods 中的表述**：
> "To address the 'black-box' criticism of autonomous systems, we developed an Evidence Package framework that captures not only measurement data but also the complete deliberation trace of the multi-agent system. Each experimental decision is accompanied by the Planner's reasoning, the Critic's evaluation, and the Orchestrator's final judgment—enabling full reproducibility and peer auditing of autonomous experiments."

**对应 Nature 2024 社论要求**：
> *"Authors must provide sufficient information for others to reproduce their work"* — Evidence Package + Agent协商轨迹直接满足此要求。

---

## 1.4 创新点四：通用可扩展架构（Universal Extensible Architecture）

### 1.4.1 为什么是"通用"平台？

本平台的多Agent架构设计具有内在的通用性：

| 设计特性 | 通用性体现 | 实现方式 |
|---------|----------|---------|
| **Agent解耦** | 核心协调逻辑与具体分析逻辑分离 | MessageBus + Protocol |
| **接口标准化** | 统一的Agent通信协议 | AgentMessage + AgentRole |
| **分析可替换** | Analysis Agent 可针对不同技术重写 | 继承 BaseAgent |
| **知识可迁移** | 知识库支持不同材料体系 | KnowledgeBase 抽象接口 |

### 1.4.2 迁移到其他表征技术的路径

| 目标技术 | 需修改的模块 | 复用的模块 | 
|---------|------------|----------|
| **Raman光谱** | Analysis Agent (峰位识别) | Orchestrator, Planner, Critic, MessageBus |
| **XRD衍射** | Analysis Agent (相识别) | 同上 |
| **CV/LSV电化学** | Analysis Agent (峰电流提取) | 同上 |
| **热重分析TGA** | Analysis Agent (失重计算) | 同上 |

**核心复用率**: >70% 的代码（Orchestrator、Planner、Critic、MessageBus、Evidence系统）可直接复用。

### 1.4.3 知识库与长期记忆

```python
class KnowledgeBase:
    """知识库 - 跨实验的长期记忆，支持持续学习"""
    
    def get_material(self, material_name):
        """获取材料先验知识（已知相变点、典型Ea范围）"""
        
    def recommend_params(self, material_name):
        """基于历史数据推荐实验参数"""
        
    def match_pattern(self, pattern_data):
        """模式匹配：检测当前数据是否符合已知模式"""
        
    def extract_and_store_insight(self, experiment_report):
        """从实验报告中提取洞见并存储 - 实现持续学习"""
```

### 1.4.4 AM写作建议

**在 Discussion 中的表述**：
> "The key to universality lies in our multi-agent architecture: the coordination logic (Orchestrator, Planner, Critic, MessageBus) is decoupled from the domain-specific analysis logic. To extend this platform to Raman spectroscopy or XRD, one need only implement a new Analysis Agent—the remaining >70% of the codebase transfers directly."

**对应审稿人可能的问题**：
- Q: "Is this platform specific to EIS?"
- A: "No. The multi-agent architecture is domain-agnostic. We have demonstrated extensibility by designing agent interfaces for Raman and XRD, requiring only Analysis Agent modifications."

---

# 第二章：系统总览与技术实现

## 2.1 物理世界（Physical World）

### 2.1.1 硬件配置

| 组件 | 型号/规格 | 通信协议 | 控制方式 |
|-----|---------|---------|---------|
| **温控系统** | 自研/商用恒温台 | RS-232 串口 | PySerial |
| **电化学工作站** | CHI系列 | VISA / GUI | PyAutoGUI + OCR |
| **样品单元** | 自设计 | - | 手动装载 |

### 2.1.2 温度稳定性

- **标称精度**: ±0.5°C
- **实测稳定性**: ±0.6°C（来源：V2.0 验证文档）
- **稳定判据**: 连续10次读数偏差 < tolerance

```python
# 温度稳定判断逻辑
def wait_for_stable(self, target_T, tolerance=0.5, wait_time=180):
    stable_count = 0
    while time.time() - start_time < wait_time:
        current_T = self.read_current_temperature()
        if abs(current_T - target_T) < tolerance:
            stable_count += 1
            if stable_count >= 10:  # 连续10次稳定
                return True
        else:
            stable_count = 0
        time.sleep(2)
    return False
```

## 2.2 数字世界（Digital World）

### 2.2.1 Agent 清单与职责

| Agent/模块 | 文件位置 | 核心职责 | 主事件/消息 |
|-----------|---------|---------|-----------|
| **Orchestrator** | `orchestrator.py` | 全局调度、安全约束、事件日志 | `STATE`, `DECISION`, `TOOL_CALL`, `TOOL_RESULT` |
| **PlannerAgent (RECOMMENDER语义)** | `planner_agent.py` | 采样策略、停止建议、补点建议 | `PLANNER_SUGGESTION` |
| **CriticAgent** | `critic_agent.py` | 测量质量评估、决策评估、重测建议 | `DECISION_CRITIQUE`, `MEASUREMENT_CRITIQUE` |
| **MainAgent Client** | `main_agent_client.py` | 综合上下文生成下一步动作 | `DECISION`, `UI_THOUGHT` |
| **LiteratureAgent** | `literature_search.py` | 相变区域文献检索与摘要 | `LITERATURE_SEARCH` |
| **ArrheniusSegmenter** | `arrhenius_segmentation.py` | 分段拟合、变化点检测 | `ARRHENIUS_SEGMENT` 结果 |
| **Knowledge/Context** | `backend/knowledge/` | 模式匹配、长期记忆、上下文沉淀 | `PATTERN_MATCH` |

### 2.2.2 Orchestrator 状态机

```
IDLE ──start_run()──▶ PLAN ──▶ ACT ──▶ OBSERVE ──▶ LEARN ──▶ (next cycle)
  ▲                                │                                 │
  └────────────── stop_run()/STOP ─┴─────────────────────────────────┘
                                  ▼
                               STOPPED
```

**对应实现要点**：
1. `PLAN`：Planner建议 + MainAgent决策 + Critic仲裁。
2. `ACT`：执行动作并记录 `TOOL_CALL/TOOL_RESULT`。
3. `OBSERVE`：接收测量并触发 Critic 质量评估。
4. `LEARN`：更新知识与上下文，支持跨循环记忆。

## 2.3 数字-物理链接（Digital-Physical Link）

### 2.3.1 ControllerAdapter 支持的动作

```python
# orchestrator.py 中实际执行/路由的动作
SET_T
WAIT_STABLE
EIS_RUN
ANALYZE_EIS
ARRHENIUS_SEGMENT
LITERATURE_SEARCH
DECIDE_AGAIN
STOP
```

### 2.3.2 安全边界约束

```python
@dataclass
class SafetyLimits:
    T_min: float = -120.0     # 最低温度 (°C)
    T_max: float = 100.0      # 最高温度 (°C)
    max_step: float = 10.0    # 最大步长 (°C)
    max_retries: int = 3      # 最大重测次数
    min_dwell_s: float = 30.0   # 最小稳定等待时间 (s)
    max_dwell_s: float = 600.0  # 最大稳定等待时间 (s)
``` 

## 2.4 前端可视化与人机协同（投稿可写）

### 2.4.1 页面与路由（实现对齐）

- `/dashboard`：运行概览、关键指标卡、实时曲线
- `/monitor`：实验过程监控、工具调用状态、思考链
- `/arrhenius`：分段与转折分析可视化
- `/history`：历史实验、详情与报告页签

### 2.4.2 状态管理与数据入口

- `agentStore`：`thoughtChain/currentDecision/plannerResult/criticResult/activeTools`
- `dataStore`：温度、测量、Arrhenius数据
- `uiStore`：连接状态、运行状态、通知
- 数据流：SSE (`/api/main-agent/stream`, `/api/autonomous/stream`) + WebSocket (`thought_chain_event`)

### 2.4.3 AM写作建议

将前端描述为“scientific workflow interface”，强调其对可解释性与可审计性的支撑，而非传统仪表盘。

---

# 第三章：闭环流程主线

## 3.1 完整闭环流程图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         闭环实验流程                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. 温控稳定 ──▶ 2. EIS采集 ──▶ 3. Rb拟合+QC ──▶ 4. σ(T)计算      │
│       │              │              │                │              │
│       ▼              ▼              ▼                ▼              │
│  [WAIT_STABLE]   [EIS_RUN]    [ANALYZE_EIS]    [计算电导率]         │
│                                     │                               │
│                                     ▼                               │
│  5. Arrhenius分段 ◀────────────────────────────────────────────────│
│       │                                                             │
│       ▼                                                             │
│  6. 变化点检测                                                       │
│       │                                                             │
│       ├── 检测到相变 ──▶ 触发 REFINE_SAMPLING (加密采样)            │
│       │                                                             │
│       ├── QC失败 ──▶ 触发 重测 / 回退                               │
│       │                                                             │
│       └── 正常 ──▶ 继续下一温度点                                    │
│                                                                     │
│  7. Evidence Package 输出 ──▶ 8. 新一轮调度                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 3.2 触发逻辑详解（实现对齐）

| 触发条件 | 阈值/规则 | 触发动作 | 代码入口 |
|---------|----------|---------|---------|
| **相变强信号** | `phase_jump > 0.20` 且 `phase=COARSE` | 切换精测、回退细扫 | `planner_agent.py` |
| **相变早期信号** | `phase_jump > 0.15` | 文献检索增强上下文 | `orchestrator.py` |
| **数据质量失败** | `qc == FAIL` 或 `r_squared < 0.90` | 重测建议 | `planner_agent.py` + `critic_agent.py` |
| **决策质量低** | `critic_score < 0.5` | 告警/建议修正 | `orchestrator.py` |
| **重测过多** | 同温点重测次数过高 | 系统级告警 | `critic_agent.py` |

## 3.3 API-事件-页面映射（建议写入SI）

| API/流入口 | 关键事件 | 前端落点 | 论文用途 |
|-----------|---------|---------|---------|
| `/api/main-agent/stream` | `UI_THOUGHT`, `DECISION` | Monitor / ThoughtChainPanel | 决策可解释性 |
| `/api/autonomous/stream` | 自主思考过程事件 | Monitor | 自治闭环可视化 |
| WebSocket `thought_chain_event` | `TOOL_CALL`, `TOOL_RESULT` | ToolsPanel | 执行链审计 |
| `/api/data/history` + `/api/data/report` | 历史结果与报告 | History | 可复现与复核 |
---

# 第四章：预测与报告模块（落脚点）

## 4.1 Phase 3: 机器学习预测

### 4.1.1 模型架构

| 模型 | 目标 | 特征 | 算法 | R² |
|-----|-----|-----|-----|-----|
| **S60基线** | Ea(R, T) | R, T | Ridge(α=20) | 0.90 |
| **S8限域** | Ea(R, N, T) | R, N, T, R×N, R×T, N×T | GradientBoosting | 0.97 |

### 4.1.2 限域效应量化

```python
# 核心公式
ΔEa = Ea_实际(S8) - Ea_预测(S60模型)
```

---

## 4.3 图表完整指南（Main Figures + Supporting Information）

### 4.3.1 AM/AFM/Nature Communications 图表规范

#### 技术规格要求

| 规格项 | AM/AFM 要求 | Nature Communications 要求 |
|-------|------------|--------------------------|
| **分辨率** | ≥300 dpi (位图), 矢量图优先 | ≥300 dpi, 矢量图优先 |
| **单栏宽度** | 8.5 cm (3.35 inch) | 8.8 cm |
| **双栏宽度** | 17.5 cm (6.89 inch) | 18.0 cm |
| **最大高度** | 24 cm | 24 cm |
| **文件格式** | TIFF, EPS, PDF (优先矢量) | TIFF, EPS, PDF |
| **色彩模式** | RGB (在线), CMYK (印刷) | RGB |
| **字体** | Arial, Helvetica, 6-8 pt | Arial, Helvetica, 5-7 pt |
| **线宽** | ≥0.5 pt | ≥0.25 pt |

#### 配色建议（色盲友好）

```
推荐配色方案 (Color-Blind Friendly):
├── 主色调: #0077BB (蓝), #EE7733 (橙), #009988 (青绿)
├── 辅助色: #CC3311 (红), #33BBEE (浅蓝), #EE3377 (粉)
├── 灰度备选: #BBBBBB, #888888, #444444
└── 背景: #FFFFFF (白), 避免纯黑背景
```

#### 子图标注规范

- 使用小写字母 **(a), (b), (c)** 标注子图（非大写）
- 标注位置：左上角，加粗，8-10 pt
- 子图间距：≥2 mm
- 每张主文图：建议 **2-4 个子图**，最多不超过 6 个

---

### 4.3.2 主文图清单（Main Figures: 4-5 张）

> **设计原则**: 主文图承载核心创新和关键结果，每张图应能独立讲述一个完整故事。AM建议主文图4-6张。

---

#### **Figure 1 | Multi-Agent System Architecture and Closed-Loop Workflow**
**（多智能体系统架构与闭环流程）**

**定位**: 本文最重要的图，展示核心创新——多Agent架构

**布局**: 双栏宽度 (17.5 cm × 12 cm)，3-4 个子图

| 子图 | 内容 | 详细要求 |
|-----|------|---------|
| **(a)** | **多Agent认知层架构图** | • 中心: Orchestrator（六边形）<br>• 上层三角: Planner ⟷ MainAgent ⟷ Critic<br>• 下层: Analysis, Literature, Knowledge Agents<br>• 连线: MessageBus 通信（虚线箭头）<br>• 标注: 每个Agent的核心职责（2-3词）|
| **(b)** | **Planner-Critic 博弈示意** | • 左右对比: Planner（探索倾向）vs Critic（稳健倾向）<br>• 中间: 决策冲突点（如：加密采样 vs 重测）<br>• 输出: Orchestrator 仲裁结果<br>• 用不同颜色区分风险偏好 |
| **(c)** | **数字-物理桥接** | • 上半: Digital World（Agent层）<br>• 分割线: ControllerAdapter<br>• 下半: Physical World（温控、CHI、样品）<br>• 双向箭头: 策略↓ / 证据↑ |
| **(d)** | **Plan-Act-Observe-Learn 闭环** | • 圆形流程: PLAN → ACT → OBSERVE → LEARN → (循环)<br>• 每个阶段标注关键操作<br>• 触发分支: 相变检测、QC失败 |

**图注要点（150-200词）**:
> "Overview of the multi-agent self-driving laboratory platform. (a) Cognitive architecture showing the Orchestrator coordinating specialized agents (Planner, Critic, Analysis, Literature, Knowledge) through a MessageBus. (b) Game-theoretic deliberation between risk-seeking Planner and risk-averse Critic before each experimental decision. (c) Digital-Physical bridge via ControllerAdapter translating agent decisions into hardware commands. (d) Closed-loop Plan-Act-Observe-Learn cycle with adaptive triggers for phase transitions and quality control failures."

---

#### **Figure 2 | Autonomous EIS Data Acquisition and Quality Control**
**（自主EIS数据采集与质量控制）**

**定位**: 展示平台的实际运行能力和数据质量保障

**布局**: 双栏宽度 (17.5 cm × 10 cm)，4 个子图

| 子图 | 内容 | 详细要求 |
|-----|------|---------|
| **(a)** | **代表性 Nyquist 图** | • 选取3个典型温度点（高/中/低温）<br>• 实验数据（散点）+ 拟合曲线（实线）<br>• 标注: 温度、R²值<br>• 插图: 等效电路模型 |
| **(b)** | **全温区 Rb(T) 曲线** | • 横轴: 温度 (K)<br>• 纵轴: log(Rb) (Ω)<br>• 展示单次实验的完整采集轨迹<br>• 标注: 粗测区 vs 精测区（步长变化）|
| **(c)** | **QC评分分布** | • 直方图: Critic评分分布 (0-1)<br>• 标注: A/B/C/D/F等级区间<br>• 垂直线: 重测阈值 (0.5) |
| **(d)** | **自适应采样示例** | • 时间轴上的采样点分布<br>• 标注: 触发事件（相变检测）<br>• 对比: 触发前后的采样密度变化 |

**图注要点**:
> "Autonomous data acquisition with real-time quality control. (a) Representative Nyquist plots at three temperatures with equivalent circuit fits (R² > 0.95). (b) Complete Rb(T) trajectory from a single autonomous run showing adaptive step-size switching. (c) Distribution of Critic quality scores across all measurements (n=XXX). (d) Adaptive sampling response to detected phase transition, demonstrating densification near T~215 K."

---

#### **Figure 3 | Arrhenius Analysis and Phase Transition Detection**
**（Arrhenius分析与相变检测）**

**定位**: 核心科学发现——相变检测和分段拟合

**布局**: 双栏宽度 (17.5 cm × 10 cm)，3-4 个子图

| 子图 | 内容 | 详细要求 |
|-----|------|---------|
| **(a)** | **典型样品 Arrhenius 图** | • 横轴: 1000/T (K⁻¹)<br>• 纵轴: ln(σT) (S·cm⁻¹·K)<br>• 分段拟合线 + 数据点<br>• 变化点用垂直虚线标注<br>• 每段标注 Ea 值 |
| **(b)** | **多样品变化点分布** | • 直方图: 变化点温度分布<br>• X轴: T (K), 范围 180-280 K<br>• 高亮: 215 K 附近的聚集<br>• 标注: 样品数量 |
| **(c)** | **分段数 vs 样品** | • 条形图: 各样品的分段数量<br>• 或饼图: 1段/2段/3段的比例<br>• 统计: 平均分段数 |
| **(d)** | **Ea 热力图**（可选） | • 横轴: R值, 纵轴: N值<br>• 色标: Ea (eV)<br>• 分温区展示（高温/低温）|

**图注要点**:
> "Arrhenius analysis revealing conduction mechanism transitions. (a) Representative ln(σT) vs 1000/T plot showing two-segment behavior with transition at 213 K (Ea₁=0.42 eV, Ea₂=0.28 eV). (b) Histogram of detected transition temperatures across all samples (n=XX), clustering around 210-220 K. (c) Distribution of segment counts per sample. (d) Activation energy heatmap as function of composition parameters (R, N)."

---

#### **Figure 4 | Machine Learning Prediction and Confinement Effect Quantification**
**（机器学习预测与限域效应量化）**

**定位**: 落脚点——从数据到科学发现

**布局**: 双栏宽度 (17.5 cm × 10 cm)，4 个子图

| 子图 | 内容 | 详细要求 |
|-----|------|---------|
| **(a)** | **S60基线模型性能** | • 预测 vs 实测 Ea 散点图<br>• 对角线参考<br>• 标注: R²=0.90, RMSE |
| **(b)** | **S8完整模型性能** | • 预测 vs 实测 Ea 散点图<br>• 标注: R²=0.97, RMSE<br>• 与(a)形成对比 |
| **(c)** | **ΔEa 限域效应** | • 箱线图: 低温区 vs 高温区 ΔEa<br>• 标注: p值（t检验）<br>• 或散点图: ΔEa vs T |
| **(d)** | **最优配比预测** | • 等高线图: Ea(R, N) 预测面<br>• 标注: 最优区域<br>• 分温区展示 |

**图注要点**:
> "Machine learning quantification of confinement effects. (a) Baseline model (S60 bulk) prediction performance (R²=0.90). (b) Full model (S8 confined) with enhanced accuracy (R²=0.97) by including confinement parameters. (c) Confinement effect ΔEa significantly larger at low temperature (0.20 eV) than high temperature (0.05 eV, p<0.001). (d) Predicted optimal composition regions for high-T and low-T applications."

---

#### **Figure 5 | Evidence-Driven Auditability and Agent Deliberation Trace**
**（证据驱动的可审计性与Agent协商轨迹）**——可选，如版面允许

**定位**: 回应可复现性关切，展示系统透明度

**布局**: 单栏或双栏 (8.5-17.5 cm × 8 cm)，2-3 个子图

| 子图 | 内容 | 详细要求 |
|-----|------|---------|
| **(a)** | **Evidence Package 结构** | • 树状结构图<br>• 四大组件: Measurement, Transition, Deliberation, Decision<br>• 每个组件列出2-3个关键字段 |
| **(b)** | **Agent协商时间线** | • 横轴: 实验步骤序列<br>• 纵轴: Agent参与情况<br>• 用色块表示: Planner建议、Critic评估、最终决策<br>• 标注: 关键决策节点 |
| **(c)** | **审计链示例** | • 选取一个决策节点<br>• 展示完整的: 触发→协商→执行→验证 链条 |

**图注要点**:
> "Evidence-driven auditability framework. (a) Structure of Evidence Package capturing measurement data, transition evidence, and agent deliberation traces. (b) Timeline of agent deliberations during a representative experiment, showing Planner suggestions (blue), Critic evaluations (orange), and final decisions (green). (c) Detailed audit chain for a single adaptive sampling trigger."

---

### 4.3.3 补充材料图清单（Supporting Information Figures）

> **设计原则**: SI图提供技术细节、方法验证、扩展数据，支撑主文结论但不重复主文内容。

---

#### **Figure S1 | Hardware Configuration and Communication Protocols**
**（硬件配置与通信协议）**

| 子图 | 内容 |
|-----|------|
| **(a)** | 完整硬件拓扑图：Host PC、温控器、CHI工作站、环境腔体 |
| **(b)** | 通信协议详情：RS-232参数、VISA配置、GUI-RPA流程 |
| **(c)** | 样品单元照片/示意图 |
| **(d)** | 系统实物照片 |

---

#### **Figure S2 | Temperature Control and Stability Validation**
**（温度控制与稳定性验证）**

| 子图 | 内容 |
|-----|------|
| **(a)** | 设定温度 vs 实际温度全程曲线（完整实验） |
| **(b)** | 稳定判据窗口放大图（±0.5°C 阈值示意） |
| **(c)** | 温度稳定时间分布（不同温区对比） |
| **(d)** | 长期稳定性测试数据 |

---

#### **Figure S3 | EIS Fitting Methods Comparison**
**（EIS拟合方法对比）**

| 子图 | 内容 |
|-----|------|
| **(a)** | 多策略拟合流程图（线性→逐步线性→圆弧→交点法） |
| **(b)** | 各方法在不同温区的适用性对比 |
| **(c)** | R²分布统计（全数据集） |
| **(d)** | 残差分布分析 |

---

#### **Figure S4 | Quality Control Criteria and Thresholds**
**（质量控制判据与阈值）**

| 子图 | 内容 |
|-----|------|
| **(a)** | CriticAgent 评分维度分解 |
| **(b)** | 各维度评分分布 |
| **(c)** | QC通过样例（Nyquist + Bode） |
| **(d)** | QC失败样例 + 触发动作标注 |

---

#### **Figure S5 | BIC/AIC Model Selection for Arrhenius Segmentation**
**（Arrhenius分段的模型选择）**

| 子图 | 内容 |
|-----|------|
| **(a)** | BIC vs 分段数曲线（典型样品） |
| **(b)** | 最优分段数分布（全数据集） |
| **(c)** | 变化点检测灵敏度分析 |

---

#### **Figure S6 | Platform User Interface Screenshots**
**（平台用户界面截图）**

| 子图 | 内容 |
|-----|------|
| **(a)** | Dashboard 主界面 |
| **(b)** | Real-time Monitor 页面 |
| **(c)** | Arrhenius Analysis 页面 |
| **(d)** | History/Report 页面 |

---

#### **Figure S7 | Extended ML Model Validation**
**（扩展ML模型验证）**

| 子图 | 内容 |
|-----|------|
| **(a)** | 特征重要性排序 |
| **(b)** | 交叉验证结果 |
| **(c)** | 残差分析 |
| **(d)** | 学习曲线 |

---

### 4.3.4 主文图 vs SI图分配总结

| 类别 | 主文图（强调创新与核心结果） | SI图（技术细节与方法验证） |
|-----|--------------------------|-------------------------|
| **系统架构** | Fig 1: 多Agent架构 + 闭环流程 | Fig S1: 硬件配置细节 |
| **数据采集** | Fig 2: EIS采集 + QC示例 | Fig S2: 温控稳定性验证 |
| **分析方法** | — | Fig S3: 拟合方法对比<br>Fig S4: QC判据详情 |
| **科学发现** | Fig 3: Arrhenius + 相变 | Fig S5: 模型选择细节 |
| **ML预测** | Fig 4: 预测性能 + 限域效应 | Fig S7: 扩展模型验证 |
| **可审计性** | Fig 5: Evidence + 协商轨迹 (可选) | Fig S6: UI界面截图 |

---

### 4.3.5 图表制作检查清单

#### 提交前必查项

- [ ] **分辨率**: 所有位图 ≥300 dpi
- [ ] **尺寸**: 符合期刊单栏/双栏要求
- [ ] **字体**: Arial/Helvetica, 6-8 pt, 无衬线
- [ ] **线宽**: ≥0.5 pt
- [ ] **配色**: 色盲友好，打印黑白可辨
- [ ] **子图标注**: 小写 (a), (b), (c)，左上角，加粗
- [ ] **坐标轴**: 标签完整（变量名 + 单位），刻度清晰
- [ ] **图例**: 简洁，避免遮挡数据
- [ ] **图注**: 独立可读，150-250词/图
- [ ] **格式**: 矢量格式优先（EPS, PDF），位图用TIFF

#### 常见错误避免

| 错误类型 | 具体问题 | 解决方案 |
|---------|---------|---------|
| **分辨率不足** | 放大后模糊 | 用矢量图或提高dpi |
| **字体过小** | 打印后无法阅读 | 最小6 pt |
| **颜色过多** | 视觉混乱 | 限制在4-5种主色 |
| **数据遮挡** | 数据点重叠 | 使用透明度或不同符号 |
| **坐标轴缺失** | 无单位或标签 | 检查所有轴 |
| **图注过短** | 无法独立理解 | 描述方法+关键结论 |

---

### 4.3.6 图注写作模板

```
Figure X | [简洁标题，<10词]

[第1句：展示什么] [第2-3句：如何生成/方法] [第4-5句：关键观察] 
[第6句：与主文的联系或意义]

Subfigure descriptions:
(a) [描述子图a内容，标注关键数值]
(b) [描述子图b内容]
...

[可选：统计信息，如 n=XX, error bars represent s.d.]
```

**示例**:
> **Figure 1 | Multi-agent architecture for autonomous EIS experimentation.** The platform implements a cognitive layer where specialized AI agents collaborate through structured deliberation. (a) System architecture showing the Orchestrator coordinating Planner, Critic, Analysis, Literature, and Knowledge agents via a MessageBus. (b) Game-theoretic interaction between risk-seeking Planner and risk-averse Critic, resolved by the Orchestrator. (c) Digital-Physical bridge translating agent decisions into hardware commands (SET_T, EIS_RUN, WAIT_STABLE). (d) Closed-loop Plan-Act-Observe-Learn cycle with adaptive branching for phase transitions and quality control failures. All agent communications are logged for full auditability.

**ΔEa统计模板（可放Results或SI）**:
- 整体: `0.123 ± 0.067 eV`
- 低温 (`<230 K`): `0.198 eV (n=39)`
- 高温 (`>270 K`): `0.046 eV (n=42)`
- 低温 vs 高温: `t-test p<0.001`

## 4.2 Phase 2: AI 机理报告

### 4.2.1 报告结构

```markdown
# S8 材料深度机理分析

## 四、最优配比推荐

### 高温区 (T ≥ 270 K)
- **R值**: 0.3 - 0.4 (酸水摩尔比)
- **N值**: 3.5 - 4.5 (液固比)

### 低温区 (T < 230 K)
- **R值**: 0.5 - 0.7
- **N值**: 2.0 - 3.0
```

### 4.2.2 ML-AI 交叉验证

从 AI 报告解析推荐区间，与 ML 预测对比：

| 温区 | AI推荐 | ML最优 | 一致性 |
|-----|--------|-------|-------|
| 高温 | R∈[0.3,0.4], N∈[3.5,4.5] | R=0.35, N=4.0 | ✓ |
| 低温 | R∈[0.5,0.7], N∈[2,3] | R=0.6, N=2.5 | ✓ |

---

# 第五章：论文写作规范与投稿指南

## 5.1 Abstract 模板（250词以内）

> **Background**: The discovery of advanced functional materials requires efficient exploration of vast compositional and processing parameter spaces. Self-Driving Laboratories (SDLs) promise to accelerate this process through closed-loop automation, yet existing systems often lack transparent decision-making and struggle with complex spectroscopic data.
>
> **Methods**: We present a Multi-Agent SDL platform for autonomous electrochemical impedance spectroscopy (EIS). The system implements an Orchestrator-ControllerAdapter architecture bridging digital AI decision-making with physical hardware execution. A Planner-Critic deliberation mechanism—where a risk-seeking Planner proposes experiments and a risk-averse Critic ensures data quality—mimics human scientific reasoning.
>
> **Results**: Validated on clay-acid proton conductor datasets, the platform analyzed **78 samples** and extracted **232 Arrhenius segments** under unified quality gates, revealing a significant temperature-dependent confinement signature (`ΔEa_lowT=0.198 eV`, `ΔEa_highT=0.046 eV`, `p<0.001`). ML models (R² up to 0.97) further linked composition-temperature descriptors to activation barriers and generated actionable formulation windows.
>
> **Significance**: The Evidence Package framework ensures 100% auditability, addressing reproducibility concerns in autonomous experimentation. The modular architecture enables extension to other spectroscopic techniques, positioning this platform as generalizable SDL infrastructure for materials discovery.

## 5.2 学术影响力指标要求

| 指标 | AM要求 | 本工作 |
|-----|-------|-------|
| **数据量** | 显著 | 78 samples × 232 segments |
| **统计验证** | p<0.05 | p<0.001 |
| **可复现性** | 提供代码 | GitHub + Evidence Package |
| **创新性** | 首创/显著改进 | Multi-Agent + Evidence闭环架构 |

## 5.3 Cover Letter 要点

1. **开篇**：强调 SDL 是 Materials Science 的前沿方向
2. **创新点**：突出 Planner-Critic 博弈机制的独特性
3. **影响力**：强调模块化设计的可迁移价值
4. **审稿人建议**：提供 3-5 位相关领域专家

## 5.4 投稿策略（AM导向）

1. **主文聚焦“方法创新 + 科学发现”**：Figure 1-4 讲清自治架构与ΔEa机制发现，UI细节放 SI。
2. **Methods 强调可执行与可审计**：给出 `API → Event → Store → Figure` 映射，避免“只给概念”。
3. **避免过度首创表述**：建议使用 “to our knowledge” + 对比表，而非绝对化措辞。
4. **给出失败案例处理**：补充 QC_FAIL、低评分决策、重测上限触发的处理流程，提升可信度。
5. **统一术语**：正文可用 Planner/Critic，但 SI 注释协议角色 `RECOMMENDER` 与事件名。

---

# 附录：关键文件索引

| 文件路径 | 功能 | 对应章节 |
|---------|-----|---------|
| `frontend_web/backend/agents/orchestrator.py` | 核心调度与事件发射 | 1.1, 2.2, 3.2 |
| `frontend_web/backend/agents/planner_agent.py` | 采样策略与停止建议 | 1.1, 3.2 |
| `frontend_web/backend/agents/critic_agent.py` | 决策/测量质量门控 | 1.1, 3.2 |
| `frontend_web/backend/agents/protocol.py` | Agent角色与消息协议 | 1.1 |
| `frontend_web/backend/agents/message_bus.py` | 总线与订阅分发 | 1.1, 2.2 |
| `frontend_web/backend/api/main_agent.py` | 主决策SSE接口 | 3.3 |
| `frontend_web/backend/api/autonomous_decision.py` | 自主思考/自动决策API | 3.3 |
| `frontend_web/frontend/src/App.jsx` | 页面路由定义 | 2.4 |
| `frontend_web/frontend/src/stores/agentStore.js` | 决策链与工具状态 | 2.4, 3.3 |
| `frontend_web/frontend/src/api/mainAgent.js` | 主Agent前端接口 | 3.3 |
| `frontend_web/frontend/src/api/autonomous.js` | 自主决策前端接口 | 3.3 |
| `close/phase3/step3_confinement_analysis.py` | 限域效应量化 | 4.1 |
| `close/phase2/core/enhanced_deep_analyzer.py` | AI机理报告 | 4.2 |

---

**文档维护**:
- 最后更新: 2026-02-08
- 维护者: SDL Platform Team
- 版本: v6.1






















