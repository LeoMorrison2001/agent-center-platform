/**
 * 监控 WebSocket 连接管理
 * 用于接收平台实时状态变化事件
 */

import { ref, onUnmounted } from 'vue'

export interface MonitorEvent {
  type: 'instance.connected' | 'instance.disconnected' | 'monitor.connected' | 'task.created' | 'task.queued' | 'task.completed' | 'task.failed'
  agent_key?: string
  instance_id?: string
  delivery_target?: string
  message?: string
  task_id?: string
  task_content?: string
}

type EventHandler = (event: MonitorEvent) => void

class MonitorWebSocketManager {
  private ws: WebSocket | null = null
  private connected = ref(false)
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 2000

  private eventHandlers: Map<string, Set<EventHandler>> = new Map()

  constructor() {
    // 自动重连
    this.startAutoReconnect()
  }

  get isConnected() {
    return this.connected
  }

  /**
   * 连接到监控 WebSocket
   */
  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.VITE_WS_HOST || 'localhost:3150'
    // 更新为正确的 WebSocket 路径：/ws/platform/monitor
    const wsUrl = `${protocol}//${host}/ws/platform/monitor`

    console.log(`[Monitor] 连接中: ${wsUrl}`)
    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('[Monitor] 连接成功')
        this.connected.value = true
        this.reconnectAttempts = 0
        this.clearReconnectTimer()
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as MonitorEvent
          console.log('[Monitor] 收到事件:', data)
          this.emit(data.type, data)
        } catch (err) {
          console.error('[Monitor] 解析消息失败:', err)
        }
      }

      this.ws.onclose = () => {
        console.log('[Monitor] 连接关闭')
        this.connected.value = false
        this.scheduleReconnect()
      }

      this.ws.onerror = (error) => {
        console.error('[Monitor] 连接错误:', error)
      }
    } catch (error) {
      console.error('[Monitor] 创建连接失败:', error)
      this.scheduleReconnect()
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    this.clearReconnectTimer()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.connected.value = false
  }

  /**
   * 监听事件
   */
  on(eventType: string, handler: EventHandler) {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set())
    }
    this.eventHandlers.get(eventType)!.add(handler)

    return () => {
      this.off(eventType, handler)
    }
  }

  /**
   * 取消监听事件
   */
  off(eventType: string, handler: EventHandler) {
    const handlers = this.eventHandlers.get(eventType)
    if (handlers) {
      handlers.delete(handler)
      if (handlers.size === 0) {
        this.eventHandlers.delete(eventType)
      }
    }
  }

  /**
   * 触发事件
   */
  private emit(eventType: string, event: MonitorEvent) {
    const handlers = this.eventHandlers.get(eventType)
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(event)
        } catch (err) {
          console.error(`[Monitor] 事件处理器错误 (${eventType}):`, err)
        }
      })
    }
  }

  /**
   * 安排重连
   */
  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[Monitor] 达到最大重连次数，停止重连')
      return
    }

    this.clearReconnectTimer()

    const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts)
    console.log(`[Monitor] ${delay}ms 后尝试重连 (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`)

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++
      this.connect()
    }, delay)
  }

  /**
   * 清除重连定时器
   */
  private clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  /**
   * 启动自动重连
   */
  private startAutoReconnect() {
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && !this.connected.value) {
        console.log('[Monitor] 页面可见，尝试重新连接')
        this.reconnectAttempts = 0
        this.connect()
      }
    })
  }
}

let monitorManager: MonitorWebSocketManager | null = null

export function useMonitorWebSocket() {
  if (!monitorManager) {
    monitorManager = new MonitorWebSocketManager()
  }

  // 组件卸载时连接（默认行为）
  monitorManager.connect()

  onUnmounted(() => {
    // 可选：实现引用计数，最后一个组件卸载时才断开
  })

  return {
    connected: monitorManager.isConnected,
    on: monitorManager.on.bind(monitorManager),
    off: monitorManager.off.bind(monitorManager),
    disconnect: monitorManager.disconnect.bind(monitorManager)
  }
}
