import { create } from 'zustand'
import { AGENT_EVENT_TYPES } from '../utils/constants'

/**
 * Agent store — main Agent decisions and thought chain
 */
const useAgentStore = create((set, get) => ({
  // ========== State ==========

  runId: null,

  thoughtChain: [],

  currentDecision: null,

  criticResult: null,

  plannerResult: null,

  agentStatus: {
    mainAgent: 'idle',
    criticAgent: 'idle',
    plannerAgent: 'idle',
  },

  autoDecisionEnabled: false,

  isThinking: false,

  error: null,

  // ========== Tool dispatch state ==========

  activeTools: [],

  toolCallCounts: {},

  toolCallHistory: [],

  // ========== Actions ==========

  /**
   * Set run ID
   */
  setRunId: (runId) => set({ runId }),

  /**
   * Append thought step
   */
  addThought: (thought) => set((state) => ({
    thoughtChain: [...state.thoughtChain, {
      ...thought,
      id: thought.id || `thought-${Date.now()}`,
      timestamp: thought.timestamp || new Date().toISOString(),
    }],
  })),

  /**
   * Clear thought chain
   */
  clearThoughtChain: () => set({ thoughtChain: [] }),

  /**
   * Set current decision
   */
  setDecision: (decision) => set({ currentDecision: decision }),

  /**
   * Set critic result
   */
  setCriticResult: (result) => set({
    criticResult: result,
    agentStatus: { ...get().agentStatus, criticAgent: 'completed' },
  }),

  /**
   * Set planner result
   */
  setPlannerResult: (result) => set({
    plannerResult: result,
    agentStatus: { ...get().agentStatus, plannerAgent: 'completed' },
  }),

  /**
   * Update agent status field
   */
  setAgentStatus: (agent, status) => set((state) => ({
    agentStatus: { ...state.agentStatus, [agent]: status },
  })),

  /**
   * Toggle autonomous decision
   */
  toggleAutoDecision: () => set((state) => ({
    autoDecisionEnabled: !state.autoDecisionEnabled,
  })),

  /**
   * Set autonomous decision enabled
   */
  setAutoDecision: (enabled) => set({ autoDecisionEnabled: enabled }),

  /**
   * Set thinking flag
   */
  setThinking: (isThinking) => set({ isThinking }),

  /**
   * Set error
   */
  setError: (error) => set({ error }),

  /**
   * Clear error
   */
  clearError: () => set({ error: null }),

  // ========== Tool dispatch actions ==========

  /**
   * Activate tool
   */
  activateTool: (toolId) => set((state) => ({
    activeTools: state.activeTools.includes(toolId)
      ? state.activeTools
      : [...state.activeTools, toolId],
    toolCallCounts: {
      ...state.toolCallCounts,
      [toolId]: (state.toolCallCounts[toolId] || 0) + 1,
    },
    toolCallHistory: [
      ...state.toolCallHistory,
      { toolId, timestamp: new Date().toISOString(), action: 'activate' },
    ],
  })),

  /**
   * Deactivate tool
   */
  deactivateTool: (toolId) => set((state) => ({
    activeTools: state.activeTools.filter((id) => id !== toolId),
    toolCallHistory: [
      ...state.toolCallHistory,
      { toolId, timestamp: new Date().toISOString(), action: 'deactivate' },
    ],
  })),

  /**
   * Clear all active tools
   */
  clearActiveTools: () => set({ activeTools: [] }),

  /**
   * Reset tool stats
   */
  resetToolStats: () => set({
    activeTools: [],
    toolCallCounts: {},
    toolCallHistory: [],
  }),

  /**
   * Handle SSE/WS events (supports type and event_type)
   */
  handleSSEEvent: (event) => {
    if (!event || typeof event !== 'object') return

    const rawType = event.type || event.event_type || event.eventType || ''
    const type = String(rawType).toUpperCase()
    const payload = (event.payload && typeof event.payload === 'object') ? event.payload : {}

    const message = event.message || event.content || payload.message || ''
    const agent = event.agent || payload.agent || 'System'
    const timestamp = event.ts || event.timestamp || payload.timestamp || new Date().toISOString()

    const merged = {
      ...payload,
      ...event,
      type,
      timestamp,
      content: message,
      agent,
    }

    const eventRunId = merged.run_id || merged.runId || null
    const activeRunId = get().runId
    const runScopedEventTypes = new Set([
      'PLAN',
      'TRIGGER',
      'ACTION',
      'DECISION',
      'AGENT_CALL',
      'TOOL_CALL',
      'TOOL_RESULT',
      'CRITIC',
      'DECISION_CRITIQUE',
      'MEASUREMENT_CRITIQUE',
      'PLANNER',
      'PLANNER_SUGGESTION',
      'COMPLETE',
      'STREAM_END',
      'STATE',
      'UI_THOUGHT',
    ])

    if (runScopedEventTypes.has(type)) {
      if (eventRunId && activeRunId && eventRunId !== activeRunId) {
        return
      }
      if (eventRunId && !activeRunId) {
        return
      }
    }

    const toolMapping = {
      // Legacy names
      eis_measure: 'eis_measurement',
      eis_analyze: 'eis_analysis',
      temperature_up: 'temperature_control',
      temperature_down: 'temperature_control',
      cooling: 'cooling_control',
      arrhenius_fit: 'arrhenius_analysis',
      phase_detect: 'phase_detection',
      generate_report: 'report_generation',
      save_data: 'data_storage',

      // Backend actions
      SET_T: 'temperature_control',
      WAIT_STABLE: 'temperature_control',
      EIS_RUN: 'eis_measurement',
      ANALYZE_EIS: 'eis_analysis',
      ARRHENIUS_SEGMENT: 'arrhenius_analysis',
      REFINE_SAMPLING: 'phase_detection',
      LITERATURE_SEARCH: 'report_generation',
    }

    const mapTool = (name) => {
      if (!name) return null
      return toolMapping[name] || toolMapping[String(name).toUpperCase()] || String(name).toLowerCase()
    }

    // Preserve the full backend event shape so downstream UI (AIThinkingPanel /
     // RawLog) can render `event_type`, `level`, `agent`, `message`, full
     // `payload` etc.  Without this every entry collapses to the UI-category
     // ('plan' / 'agent_call' / …) and the panel shows the same content on
     // every row — which is exactly the bug the user reported.
    const addThought = (thoughtType, extra = {}) => {
      get().addThought({
        ui_type: thoughtType,
        type: type || thoughtType,                 // keep original UPPER event type
        event_type: type || event.event_type,
        level: event.level || payload.level || 'INFO',
        agent,
        message: message || `${type} event`,
        content: message || `${type} event`,
        timestamp,
        payload,                                   // raw backend payload
        ...extra,
      })
    }

    if (merged.tool) {
      const toolId = mapTool(merged.tool)
      if (toolId) {
        get().activateTool(toolId)
        setTimeout(() => get().deactivateTool(toolId), 2000)
      }
    }

    switch (type) {
      case AGENT_EVENT_TYPES.PLAN:
        get().setAgentStatus('mainAgent', 'planning')
        addThought('plan')
        break

      case AGENT_EVENT_TYPES.TRIGGER:
      case 'PATTERN_MATCH':
      case 'LITERATURE_SEARCH':
        addThought('trigger')
        break

      case AGENT_EVENT_TYPES.ACTION:
      case 'DECISION':
        get().setDecision(merged)
        get().setAgentStatus('mainAgent', 'running')
        addThought('action')

        if (merged.action || merged.action_type) {
          const toolId = mapTool(merged.action || merged.action_type)
          if (toolId) {
            get().activateTool(toolId)
            setTimeout(() => get().deactivateTool(toolId), 2500)
          }
        }
        break

      case AGENT_EVENT_TYPES.AGENT_CALL:
      case 'STATE':
      case 'UI_THOUGHT':
      case 'CONNECTED':
        addThought('agent_call')
        break

      case AGENT_EVENT_TYPES.TOOL_CALL:
        {
          const toolName = merged.tool_id || merged.action_type || merged.action
          const toolId = mapTool(toolName)
          if (toolId) {
            get().activateTool(toolId)
          }

          addThought('tool_call', {
            content: message || `Invoke tool: ${toolName || 'unknown'}`,
            tool_id: toolId || toolName,
          })

          const duration = Number(merged.duration || 0)
          const delay = Number.isFinite(duration) && duration > 0 ? duration : 2000
          if (toolId) {
            setTimeout(() => get().deactivateTool(toolId), delay)
          }
        }
        break

      case 'TOOL_RESULT':
        {
          const toolName = merged.tool_id || merged.action_type || merged.action
          const toolId = mapTool(toolName)
          if (toolId) {
            get().deactivateTool(toolId)
          }
          addThought('tool_call', {
            content: message || `Tool completed: ${toolName || 'unknown'}`,
            data: merged.result || payload,
          })
        }
        break

      case AGENT_EVENT_TYPES.CRITIC:
      case 'DECISION_CRITIQUE':
      case 'MEASUREMENT_CRITIQUE':
        {
          const critique = merged.critique || {}
          const score = critique.score ?? merged.score
          const result = {
            score,
            grade: critique.grade || merged.grade,
            suggestions: critique.suggestions || merged.suggestions || [],
            issues: critique.issues || merged.issues || [],
            analysis: message,
            details: critique.details || merged.details,
            dimensions: critique.dimensions,
          }

          get().setCriticResult(result)
          addThought('critic', { score, data: critique })
        }
        break

      case AGENT_EVENT_TYPES.PLANNER:
      case 'PLANNER_SUGGESTION':
        {
          const planner = {
            action: merged.action,
            confidence: merged.confidence,
            reasoning: merged.reasoning || message,
            description: merged.description || message,
            nextParams: merged.parameters || merged.nextParams,
            triggers: merged.triggers,
          }
          get().setPlannerResult(planner)
          addThought('planner', { data: merged })
        }
        break

      case 'WARNING':
        addThought('trigger', { content: message || 'Warning event', data: merged })
        break

      case AGENT_EVENT_TYPES.ERROR:
      case 'ERROR':
        get().setError(message || 'An error occurred')
        addThought('error', { data: merged })
        get().clearActiveTools()
        break

      case AGENT_EVENT_TYPES.COMPLETE:
      case 'STREAM_END':
        get().setThinking(false)
        get().setAgentStatus('mainAgent', 'completed')
        addThought('complete', { content: message || 'Decision complete' })
        get().clearActiveTools()
        break

      default:
        if (message || type) {
          addThought('agent_call', { content: message || `${type} event`, data: merged })
        }
        break
    }
  },

  /**
   * Reset all state
   */
  reset: () => set({
    runId: null,
    thoughtChain: [],
    currentDecision: null,
    criticResult: null,
    plannerResult: null,
    agentStatus: {
      mainAgent: 'idle',
      criticAgent: 'idle',
      plannerAgent: 'idle',
    },
    isThinking: false,
    error: null,
    activeTools: [],
    toolCallCounts: {},
    toolCallHistory: [],
  }),

  /**
   * Demo tool dispatch (testing / showcase)
   */
  demoToolDispatch: async () => {
    const tools = [
      { id: 'temperature_control', name: 'Temperature control', delay: 0 },
      { id: 'eis_measurement', name: 'EIS measurement', delay: 800 },
      { id: 'eis_analysis', name: 'EIS analysis', delay: 1600 },
      { id: 'phase_detection', name: 'Phase detection', delay: 2400 },
      { id: 'arrhenius_analysis', name: 'Arrhenius analysis', delay: 3200 },
      { id: 'data_storage', name: 'Data storage', delay: 4000 },
    ]

    get().setThinking(true)
    get().addThought({
      type: 'plan',
      content: 'Main Agent starting decision flow, analyzing current experiment state...',
    })

    for (const tool of tools) {
      await new Promise((resolve) => setTimeout(resolve, tool.delay === 0 ? 500 : 800))

      get().activateTool(tool.id)
      get().addThought({
        type: 'tool_call',
        content: `Invoke tool: ${tool.name}`,
        tool_id: tool.id,
      })

      setTimeout(() => {
        get().deactivateTool(tool.id)
      }, 2000)
    }

    await new Promise((resolve) => setTimeout(resolve, 5000))
    get().setThinking(false)
    get().addThought({
      type: 'complete',
      content: 'Demo complete: tool dispatch showcase finished',
    })
    get().clearActiveTools()
  },
}))

export default useAgentStore
