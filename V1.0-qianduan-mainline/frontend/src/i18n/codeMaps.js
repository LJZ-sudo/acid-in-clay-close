const actionMap = {
  SET_T: 'actions.SET_T',
  WAIT_STABLE: 'actions.WAIT_STABLE',
  EIS_RUN: 'actions.EIS_RUN',
  RETEST: 'actions.RETEST',
  ABORT: 'actions.ABORT',
  BACKTRACK: 'actions.BACKTRACK',
  DENSIFY: 'actions.DENSIFY',
  RE_MEASURE: 'actions.RE_MEASURE',
}

const qcMap = {
  QC_UNKNOWN: 'qc.unknown',
  QC_PASS: 'qc.pass',
  QC_FAIL: 'qc.fail',
  A: 'qc.gradeA',
  B: 'qc.gradeB',
  C: 'qc.gradeC',
  D: 'qc.gradeD',
}

const riskMap = {
  ALLOW: 'risk.ALLOW',
  DENY: 'risk.DENY',
  CLAMPED: 'risk.CLAMPED',
  MAX_STEP_EXCEEDED: 'risk.MAX_STEP_EXCEEDED',
  OUT_OF_RANGE: 'risk.OUT_OF_RANGE',
}

export function actionCodeToKey(code) {
  const key = String(code || '').toUpperCase()
  return actionMap[key] || null
}

export function qcCodeToKey(code) {
  const key = String(code || '').toUpperCase()
  return qcMap[key] || null
}

export function riskCodeToKey(code) {
  const key = String(code || '').toUpperCase()
  return riskMap[key] || null
}

export function translateCode(t, code, mapper, fallback = 'common.unknown') {
  const key = mapper(code)
  if (key) return t(key)
  const raw = String(code || '').trim()
  return raw || t(fallback)
}
