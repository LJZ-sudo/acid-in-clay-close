import { create } from 'zustand'
import { SYSTEM_STATUS } from '../utils/constants'

/**
 * UI store — layout flags and system status
 */
const useUIStore = create((set, get) => ({
  // ========== State ==========

  wsConnected: false,

  systemStatus: SYSTEM_STATUS.IDLE,

  controllerConnected: false,

  experimentRunning: false,

  experimentPaused: false,

  sidebarCollapsed: false,

  activeTab: 'thought-chain',

  notifications: [],

  globalLoading: false,

  modals: {
    connect: false,
    settings: false,
  },

  // ========== Actions ==========

  /**
   * Set WebSocket connected flag
   */
  setWsConnected: (connected) => set({ wsConnected: connected }),

  /**
   * Set system status
   */
  setSystemStatus: (status) => set({ systemStatus: status }),

  /**
   * Set controller connected flag
   */
  setControllerConnected: (connected) => set({
    controllerConnected: connected,
    systemStatus: connected ? SYSTEM_STATUS.CONNECTED : SYSTEM_STATUS.IDLE,
  }),

  /**
   * Set experiment running flag
   */
  setExperimentRunning: (running) => set({
    experimentRunning: running,
    systemStatus: running
      ? SYSTEM_STATUS.RUNNING
      : (get().controllerConnected ? SYSTEM_STATUS.CONNECTED : SYSTEM_STATUS.IDLE),
  }),

  /**
   * Set experiment paused flag
   */
  setExperimentPaused: (paused) => set({
    experimentPaused: paused,
    systemStatus: paused ? SYSTEM_STATUS.PAUSED : SYSTEM_STATUS.RUNNING,
  }),

  /**
   * Toggle sidebar collapsed
   */
  toggleSidebar: () => set((state) => ({
    sidebarCollapsed: !state.sidebarCollapsed,
  })),

  /**
   * Set active tab
   */
  setActiveTab: (tab) => set({ activeTab: tab }),

  /**
   * Push notification
   */
  addNotification: (notification) => set((state) => ({
    notifications: [...state.notifications, {
      id: `notify-${Date.now()}`,
      timestamp: new Date().toISOString(),
      ...notification,
    }],
  })),

  /**
   * Remove notification by id
   */
  removeNotification: (id) => set((state) => ({
    notifications: state.notifications.filter((n) => n.id !== id),
  })),

  /**
   * Clear all notifications
   */
  clearNotifications: () => set({ notifications: [] }),

  /**
   * Set global loading flag
   */
  setGlobalLoading: (loading) => set({ globalLoading: loading }),

  /**
   * Open modal by name
   */
  openModal: (name) => set((state) => ({
    modals: { ...state.modals, [name]: true },
  })),

  /**
   * Close modal by name
   */
  closeModal: (name) => set((state) => ({
    modals: { ...state.modals, [name]: false },
  })),

  /**
   * Apply status payload from WebSocket
   */
  handleStatusUpdate: (data = {}) => {
    const statusText = String(data.status || '').toLowerCase()

    const connected = data.connected ?? data.controller_connected
    let running = data.running ?? data.is_running
    let paused = data.paused ?? data.is_paused

    // When only a status string is provided
    if (running === undefined && paused === undefined && statusText) {
      if (statusText.includes('pause')) {
        paused = true
        running = true
      } else if (statusText.includes('run')) {
        running = true
        paused = false
      } else if (statusText.includes('stop') || statusText.includes('idle')) {
        running = false
        paused = false
      } else if (statusText.includes('connect')) {
        running = false
        paused = false
      }
    }

    if (connected !== undefined) {
      get().setControllerConnected(Boolean(connected))
    }

    if (running !== undefined) {
      get().setExperimentRunning(Boolean(running))
    }

    if (paused !== undefined) {
      get().setExperimentPaused(Boolean(paused))
    }
  },

  /**
   * Reset store
   */
  reset: () => set({
    wsConnected: false,
    systemStatus: SYSTEM_STATUS.IDLE,
    controllerConnected: false,
    experimentRunning: false,
    experimentPaused: false,
    notifications: [],
    globalLoading: false,
  }),
}))

export default useUIStore
