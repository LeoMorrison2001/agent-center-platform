import { defineStore } from 'pinia'
import { ref } from 'vue'
import api, { type PlatformStatus, type AgentService } from '@/api/services'

export const usePlatformStore = defineStore('platform', () => {
  // 状态
  const status = ref<PlatformStatus | null>(null)
  const services = ref<AgentService[]>([])
  const loading = ref(false)

  // 获取平台状态
  const fetchStatus = async () => {
    try {
      loading.value = true
      status.value = await api.getStatus()
    } catch (error) {
      console.error('Failed to fetch status:', error)
    } finally {
      loading.value = false
    }
  }

  // 获取服务列表
  const fetchServices = async () => {
    try {
      loading.value = true
      const result = await api.getServices()
      services.value = result.services
    } catch (error) {
      console.error('Failed to fetch services:', error)
    } finally {
      loading.value = false
    }
  }

  // 创建服务
  const createService = async (data: { agent_key: string; name: string; type: string; description: string }) => {
    try {
      const newService = await api.createService(data)
      services.value.push(newService)
      return newService
    } catch (error) {
      console.error('Failed to create service:', error)
      throw error
    }
  }

  // 删除服务
  const deleteService = async (agentKey: string) => {
    try {
      await api.deleteService(agentKey)
      services.value = services.value.filter(s => s.agent_key !== agentKey)
    } catch (error) {
      console.error('Failed to delete service:', error)
      throw error
    }
  }

  // 刷新所有数据
  const refresh = async () => {
    await Promise.all([fetchStatus(), fetchServices()])
  }

  return {
    status,
    services,
    loading,
    fetchStatus,
    fetchServices,
    createService,
    deleteService,
    refresh
  }
})
