// API base path
export const API_BASE_URL = '/api'

// WebSocket event types
export const WS_EVENTS = {
  CONNECT: 'connect',
  DISCONNECT: 'disconnect',
  SUBSCRIBED: 'subscribed',
  HEARTBEAT: 'heartbeat',
  UNSTABLE: 'unstable',
  STATUS_CHANGE: 'status_change',
  TEMPERATURE_UPDATE: 'temperature_update',
  MEASUREMENT_COMPLETE: 'measurement_complete',
  PHASE_TRANSITION: 'phase_transition',
  THOUGHT_CHAIN_EVENT: 'thought_chain_event',
  LOG: 'log',
}

// Agent event types
export const AGENT_EVENT_TYPES = {
  PLAN: 'PLAN',
  TRIGGER: 'TRIGGER',
  ACTION: 'ACTION',
  AGENT_CALL: 'AGENT_CALL',
  TOOL_CALL: 'TOOL_CALL',
  CRITIC: 'CRITIC',
  PLANNER: 'PLANNER',
  ERROR: 'ERROR',
  COMPLETE: 'COMPLETE',
}

// Tool IDs
export const TOOL_IDS = {
  EIS_MEASUREMENT: 'eis_measurement',
  EIS_ANALYSIS: 'eis_analysis',
  TEMPERATURE_CONTROL: 'temperature_control',
  COOLING_CONTROL: 'cooling_control',
  ARRHENIUS_ANALYSIS: 'arrhenius_analysis',
  PHASE_DETECTION: 'phase_detection',
  REPORT_GENERATION: 'report_generation',
  DATA_STORAGE: 'data_storage',
}

// System status
export const SYSTEM_STATUS = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  RUNNING: 'running',
  PAUSED: 'paused',
  STOPPED: 'stopped',
  ERROR: 'error',
}

// Chart colors
export const CHART_COLORS = {
  temperature: '#3b82f6',
  conductivity: '#10b981',
  phase: '#f59e0b',
  arrhenius: '#8b5cf6',
}
