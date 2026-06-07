import { io } from 'socket.io-client'
import { WS_EVENTS } from '../utils/constants'

const PING_INTERVAL_MS = 15_000
const STABLE_TIMEOUT_MS = 30_000
const HEALTH_CHECK_MS = 5_000

/**
 * WebSocket service - real-time data channel
 */
class WebSocketService {
  constructor() {
    this.socket = null
    this.listeners = new Map()
    this.connected = false
    this.stable = false
    this.lastHeartbeatAt = 0
    this.heartbeatTimer = null
    this.healthTimer = null
    this.pendingSubscribePayload = null
    this._coreHandlersRegistered = false
  }

  connect(url = '') {
    return new Promise((resolve, reject) => {
      if (this.socket && this.socket.connected) {
        resolve()
        return
      }

      this.socket = io(url, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 20_000,
        randomizationFactor: 0.5,
        timeout: 10_000,
      })

      this._registerCoreHandlers()
      this._registerDataHandlers()

      let settled = false

      this.socket.once('connect', () => {
        if (settled) return
        settled = true
        resolve()
      })

      this.socket.once('connect_error', (error) => {
        if (settled) return
        settled = true
        reject(error || new Error('WebSocket initial connect failed'))
      })
    })
  }

  disconnect() {
    this._stopTimers()
    this.connected = false
    this.stable = false
    this.lastHeartbeatAt = 0

    if (this.socket) {
      this.socket.disconnect()
      this.socket.removeAllListeners()
      this.socket = null
    }

    this._coreHandlersRegistered = false
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set())
    }
    this.listeners.get(event).add(callback)

    return () => {
      this.listeners.get(event)?.delete(callback)
    }
  }

  off(event, callback) {
    this.listeners.get(event)?.delete(callback)
  }

  emit(event, data) {
    if (this.socket && this.socket.connected) {
      this.socket.emit(event, data)
    }
  }

  subscribe(channelOrPayload, lastSeq = 0) {
    let payload = null
    if (typeof channelOrPayload === 'string') {
      payload = { channels: [channelOrPayload], last_seq: Number(lastSeq || 0) }
    } else if (Array.isArray(channelOrPayload)) {
      payload = { channels: channelOrPayload, last_seq: Number(lastSeq || 0) }
    } else if (channelOrPayload && typeof channelOrPayload === 'object') {
      payload = { ...channelOrPayload }
      if (payload.channel && !payload.channels) {
        payload.channels = [payload.channel]
      }
      if (payload.last_seq === undefined) {
        payload.last_seq = Number(lastSeq || 0)
      }
    } else {
      payload = { channels: [], last_seq: Number(lastSeq || 0) }
    }

    this.pendingSubscribePayload = payload
    this.emit('subscribe', payload)
  }

  isConnected() {
    return Boolean(this.connected && this.stable && this.socket?.connected)
  }

  _registerCoreHandlers() {
    if (!this.socket || this._coreHandlersRegistered) return
    this._coreHandlersRegistered = true

    this.socket.on('connect', () => {
      this.connected = true
      this.stable = true
      this.lastHeartbeatAt = Date.now()
      this._notifyListeners(WS_EVENTS.CONNECT, { connected: true, id: this.socket?.id })
      this._notifyListeners(WS_EVENTS.HEARTBEAT, { ts: this.lastHeartbeatAt })

      this._startTimers()

      if (this.pendingSubscribePayload) {
        this.emit('subscribe', this.pendingSubscribePayload)
      }
    })

    this.socket.on('disconnect', (reason) => {
      this.connected = false
      this.stable = false
      this._stopTimers()
      this._notifyListeners(WS_EVENTS.DISCONNECT, { reason })
    })

    this.socket.on('connect_error', (error) => {
      this._notifyListeners(WS_EVENTS.DISCONNECT, { reason: 'connect_error', error })
    })

    this.socket.on('pong', (payload = {}) => {
      this.lastHeartbeatAt = Date.now()
      const wasStable = this.stable
      this.stable = true
      this._notifyListeners(WS_EVENTS.HEARTBEAT, {
        ts: this.lastHeartbeatAt,
        payload,
      })
      if (!wasStable) {
        this._notifyListeners(WS_EVENTS.CONNECT, { connected: true, recovered: true })
      }
    })

    this.socket.on('heartbeat', (payload = {}) => {
      this.lastHeartbeatAt = Date.now()
      this.stable = true
      this._notifyListeners(WS_EVENTS.HEARTBEAT, {
        ts: this.lastHeartbeatAt,
        payload,
      })
    })

    this.socket.on('subscribed', (payload = {}) => {
      this.lastHeartbeatAt = Date.now()
      this.stable = true
      this._notifyListeners(WS_EVENTS.SUBSCRIBED, payload)
    })
  }

  _registerDataHandlers() {
    if (!this.socket) return

    this.socket.off(WS_EVENTS.STATUS_CHANGE)
    this.socket.off(WS_EVENTS.TEMPERATURE_UPDATE)
    this.socket.off(WS_EVENTS.MEASUREMENT_COMPLETE)
    this.socket.off(WS_EVENTS.PHASE_TRANSITION)
    this.socket.off(WS_EVENTS.THOUGHT_CHAIN_EVENT)
    this.socket.off(WS_EVENTS.LOG)

    this.socket.on(WS_EVENTS.STATUS_CHANGE, (data) => {
      this._notifyListeners(WS_EVENTS.STATUS_CHANGE, data)
    })

    this.socket.on(WS_EVENTS.TEMPERATURE_UPDATE, (data) => {
      this._notifyListeners(WS_EVENTS.TEMPERATURE_UPDATE, data)
    })

    this.socket.on(WS_EVENTS.MEASUREMENT_COMPLETE, (data) => {
      this._notifyListeners(WS_EVENTS.MEASUREMENT_COMPLETE, data)
    })

    this.socket.on(WS_EVENTS.PHASE_TRANSITION, (data) => {
      this._notifyListeners(WS_EVENTS.PHASE_TRANSITION, data)
    })

    this.socket.on(WS_EVENTS.THOUGHT_CHAIN_EVENT, (data) => {
      this._notifyListeners(WS_EVENTS.THOUGHT_CHAIN_EVENT, data)
    })

    this.socket.on(WS_EVENTS.LOG, (data) => {
      this._notifyListeners(WS_EVENTS.LOG, data)
    })
  }

  _startTimers() {
    this._stopTimers()

    this.heartbeatTimer = window.setInterval(() => {
      if (this.socket?.connected) {
        this.socket.emit('ping', { ts: Date.now() })
      }
    }, PING_INTERVAL_MS)

    this.healthTimer = window.setInterval(() => {
      if (!this.socket?.connected) return
      const age = Date.now() - Number(this.lastHeartbeatAt || 0)
      if (age >= STABLE_TIMEOUT_MS) {
        if (this.stable) {
          this.stable = false
          this._notifyListeners(WS_EVENTS.UNSTABLE, {
            age_ms: age,
            timeout_ms: STABLE_TIMEOUT_MS,
          })
        }
      }
    }, HEALTH_CHECK_MS)
  }

  _stopTimers() {
    if (this.heartbeatTimer) {
      window.clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
    if (this.healthTimer) {
      window.clearInterval(this.healthTimer)
      this.healthTimer = null
    }
  }

  _notifyListeners(event, data) {
    const callbacks = this.listeners.get(event)
    if (!callbacks) return
    callbacks.forEach((callback) => {
      try {
        callback(data)
      } catch (error) {
        // no-op
      }
    })
  }
}

export const wsService = new WebSocketService()
export default wsService
