import request from './index'

// 平台状态接口
export interface PlatformStatus {
  status: string
  timestamp: string
  statistics: {
    total_services: number
    active_services: number
    total_instances: number
    running_tasks: number
  }
  active_services_list: string[]
}

// 智能体服务接口
export interface AgentService {
  id: number
  agent_key: string
  name: string
  type: string
  description: string
  created_at: string
  working_count: number
}

// 创建服务请求
export interface CreateServiceRequest {
  agent_key: string
  name: string
  type: string
  description: string
}

// 工具描述接口
export interface ToolDescription {
  agent_key: string
  name: string
  description: string
  type: string
}

export interface AgentKeyValidationResponse {
  valid: boolean
  exists: boolean
  message: string
}

// 任务日志接口
export interface TaskLog {
  id: number
  task_id: string
  agent_key: string
  instance_id: string | null
  task_content: string
  status: 'queued' | 'completed' | 'failed'
  result: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
}

export interface TaskLogsResponse {
  total: number
  logs: TaskLog[]
}

export interface TaskStats {
  total: number
  completed: number
  failed: number
  queued: number
  success_rate: number
}

export interface DispatchTaskRequest {
  agent_key: string
  task_content: string
}

export interface DispatchTaskResponse {
  task_id: string
  agent_key: string
  status: 'queued'
  message: string
}

export interface ServiceInstancesResponse {
  agent_key: string
  instances: Array<{ instance_id: string }>
}

// 日志查询参数
export interface TaskLogsParams {
  skip?: number
  limit?: number
  agent_key?: string
  status?: string
}

// API 函数
export const api = {
  // 获取平台状态
  getStatus(): Promise<PlatformStatus> {
    return request.get('/api/platform/status')
  },

  // 获取所有服务
  getServices(params?: { skip?: number; limit?: number }): Promise<{ total: number; services: AgentService[] }> {
    return request.get('/api/platform/services', { params })
  },

  // 创建服务
  createService(data: CreateServiceRequest): Promise<AgentService> {
    return request.post('/api/platform/services', data)
  },

  // 更新服务
  updateService(agentKey: string, data: CreateServiceRequest): Promise<AgentService> {
    return request.put(`/api/platform/services/${agentKey}`, data)
  },

  // 删除服务
  deleteService(agentKey: string): Promise<{ message: string }> {
    return request.delete(`/api/platform/services/${agentKey}`)
  },

  // 校验智能体KEY是否可用
  validateAgentKey(agentKey: string): Promise<AgentKeyValidationResponse> {
    return request.get(`/api/platform/services/validate/${agentKey}`)
  },

  // 获取可用工具列表
  getTools(): Promise<ToolDescription[]> {
    return request.get('/api/platform/tools')
  },

  // 获取任务日志列表
  getTaskLogs(params?: TaskLogsParams): Promise<TaskLogsResponse> {
    return request.get('/api/platform/logs', { params })
  },

  // 获取单个任务详情
  getTaskLog(taskId: string): Promise<TaskLog> {
    return request.get(`/api/platform/logs/${taskId}`)
  },

  // 获取任务统计
  getTaskStats(): Promise<TaskStats> {
    return request.get('/api/platform/logs/stats/summary')
  },

  // 获取服务的所有实例
  getServiceInstances(agentKey: string): Promise<ServiceInstancesResponse> {
    return request.get(`/api/platform/services/${agentKey}/instances`)
  },

  // 向指定服务发送测试任务
  testServiceInstance(agentKey: string, data: { task_content?: string }): Promise<DispatchTaskResponse> {
    return request.post(`/api/platform/services/${agentKey}/test`, data)
  },

  dispatchTask(data: DispatchTaskRequest): Promise<DispatchTaskResponse> {
    return request.post('/api/platform/dispatch', data)
  }
}

export default api
