import { create } from 'zustand'

const asFiniteNumber = (value) => {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

const sameConductivityIdentity = (left = {}, right = {}) => {
  const leftMeasurementId = String(left.measurement_id || left.measurementId || '').trim()
  const rightMeasurementId = String(right.measurement_id || right.measurementId || '').trim()
  if (leftMeasurementId && rightMeasurementId) {
    return leftMeasurementId === rightMeasurementId
  }

  const leftStep = asFiniteNumber(left.step_idx ?? left.stepIndex)
  const rightStep = asFiniteNumber(right.step_idx ?? right.stepIndex)
  if (leftStep !== null && rightStep !== null && leftStep > 0 && rightStep > 0) {
    return leftStep === rightStep
  }

  return false
}

/**
 * Data store — experiment and realtime measurement state
 */
const useDataStore = create((set, get) => ({
  // ========== State ==========

  currentTemperature: null,

  targetTemperature: null,

  // Temperature history (charts)
  temperatureHistory: [],

  conductivityHistory: [],

  measurements: [],

  phaseTransitions: [],

  arrheniusData: null,

  experiments: [],

  currentExperimentId: null,

  // Current experiment parameters (set on /control "start").  Used by Monitor
  // right-panel to display the temperature program + step sizes.
  experimentParams: {
    sample_id: null,
    t_start: null,
    t_end: null,
    coarse_step: null,
    fine_step: null,
    thickness_m: null,
    area_m2: null,
    material_note: null,
    R: null,
    N: null,
    campaign: null,
    chi: null,
  },

  loading: {
    measurements: false,
    arrhenius: false,
    experiments: false,
  },

  // ========== Actions ==========

  /**
   * Update temperature
   */
  setTemperature: (current, target = null) => set({
    currentTemperature: current,
    targetTemperature: target !== null ? target : get().targetTemperature,
  }),

  /**
   * Append temperature history point
   */
  addTemperaturePoint: (point) => set((state) => {
    const newHistory = [...state.temperatureHistory, {
      ...point,
      timestamp: point.timestamp || Date.now(),
    }]
    // Keep last 1000 points
    if (newHistory.length > 1000) {
      newHistory.shift()
    }
    return { temperatureHistory: newHistory }
  }),

  /**
   * Append conductivity history point
   */
  addConductivityPoint: (point) => set((state) => {
    const nextPoint = {
      ...point,
      timestamp: point.timestamp || Date.now(),
    }
    const newHistory = [...state.conductivityHistory]
    const existingIndex = newHistory.findIndex((item) => sameConductivityIdentity(item, nextPoint))
    if (existingIndex >= 0) {
      newHistory[existingIndex] = {
        ...newHistory[existingIndex],
        ...nextPoint,
      }
    } else {
      newHistory.push(nextPoint)
    }
    if (newHistory.length > 1000) {
      newHistory.shift()
    }
    return { conductivityHistory: newHistory }
  }),

  /**
   * Set measurements list
   */
  setMeasurements: (measurements) => set({ measurements }),

  /**
   * Append measurement
   */
  addMeasurement: (measurement) => set((state) => ({
    measurements: [...state.measurements, measurement]
  })),

  /**
   * Set phase transitions
   */
  setPhaseTransitions: (transitions) => set({ phaseTransitions: transitions }),

  /**
   * Append phase transition
   */
  addPhaseTransition: (transition) => set((state) => ({
    phaseTransitions: [...state.phaseTransitions, transition]
  })),

  /**
   * Set Arrhenius data
   */
  setArrheniusData: (data) => set({ arrheniusData: data }),

  /**
   * Set experiments list
   */
  setExperiments: (experiments) => set({ experiments }),

  /**
   * Set current experiment ID
   */
  setCurrentExperimentId: (id) => set({ currentExperimentId: id }),

  /**
   * Set / merge the active experiment parameters (used by Monitor sidebar).
   */
  setExperimentParams: (params) => set((state) => ({
    experimentParams: { ...state.experimentParams, ...(params || {}) },
  })),

  clearExperimentParams: () => set({
    experimentParams: {
      sample_id: null,
      t_start: null,
      t_end: null,
      coarse_step: null,
      fine_step: null,
      thickness_m: null,
      area_m2: null,
      material_note: null,
      R: null,
      N: null,
      campaign: null,
      chi: null,
    },
  }),

  /**
   * Set loading flag
   */
  setLoading: (key, value) => set((state) => ({
    loading: { ...state.loading, [key]: value }
  })),

  /**
   * Clear realtime series
   */
  clearRealtimeData: () => set({
    temperatureHistory: [],
    conductivityHistory: [],
    currentTemperature: null,
    targetTemperature: null,
  }),

  /**
   * Reset all data
   */
  reset: () => set({
    currentTemperature: null,
    targetTemperature: null,
    temperatureHistory: [],
    conductivityHistory: [],
    measurements: [],
    phaseTransitions: [],
    arrheniusData: null,
    experiments: [],
    currentExperimentId: null,
    loading: {
      measurements: false,
      arrhenius: false,
      experiments: false,
    },
  }),
}))

export default useDataStore
