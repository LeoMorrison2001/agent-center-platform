<template>
  <div class="dashboard">
    <t-row :gutter="16" class="stats-row">
      <!-- 统计卡片 -->
      <t-col :flex="1">
        <t-card :bordered="false">
          <t-statistic
            title="总服务数"
            :value="status?.statistics.total_services || 0"
            :formatter="(value) => value.toString()"
          >
            <template #prefix>
              <t-icon name="server" />
            </template>
          </t-statistic>
        </t-card>
      </t-col>

      <t-col :flex="1">
        <t-card :bordered="false">
          <t-statistic
            title="活跃服务"
            :value="status?.statistics.active_services || 0"
            :formatter="(value) => value.toString()"
          >
            <template #prefix>
              <t-icon name="check-circle" />
            </template>
          </t-statistic>
        </t-card>
      </t-col>

      <t-col :flex="1">
        <t-card :bordered="false">
          <t-statistic
            title="智能体实例总数"
            :value="status?.statistics.total_instances || 0"
            :formatter="(value) => value.toString()"
          >
            <template #prefix>
              <t-icon name="usergroup" />
            </template>
          </t-statistic>
        </t-card>
      </t-col>

      <t-col :flex="1">
        <t-card :bordered="false">
          <t-statistic
            title="正在运行"
            :value="status?.statistics.running_tasks || 0"
            :formatter="(value) => value.toString()"
          >
            <template #prefix>
              <t-icon name="play-circle" />
            </template>
          </t-statistic>
        </t-card>
      </t-col>
    </t-row>

    <!-- 活跃服务列表 -->
    <t-card :bordered="false" class="mt-16">
      <template #header>
        <div class="page-header">
          <h3>活跃服务</h3>
        </div>
      </template>
      <t-list :split="true">
        <t-list-item
          v-for="agentKey in status?.active_services_list || []"
          :key="agentKey"
        >
          <t-list-item-meta
            :title="getServiceName(agentKey)"
            :description="getServiceDescription(agentKey)"
          >
            <template #image>
              <t-tag theme="success" variant="light">
                在线
              </t-tag>
            </template>
          </t-list-item-meta>
        </t-list-item>
        <t-list-item v-if="!status?.active_services_list?.length">
          <t-list-item-meta
            title="暂无活跃服务"
            description="等待智能体连接..."
          />
        </t-list-item>
      </t-list>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { usePlatformStore } from '@/stores/platform'

const platformStore = usePlatformStore()

const status = computed(() => platformStore.status)

const getServiceName = (agentKey: string) => {
  const service = platformStore.services.find(s => s.agent_key === agentKey)
  return service?.name || agentKey
}

const getServiceDescription = (agentKey: string) => {
  const service = platformStore.services.find(s => s.agent_key === agentKey)
  return service?.description || ''
}

onMounted(async () => {
  await platformStore.refresh()
})
</script>

<style scoped>
.dashboard {
  width: 100%;
  min-width: 0;
}

.page-header {
  display: flex;
  align-items: center;
}

.page-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 32px;
  min-height: 32px;
}

.mt-16 {
  margin-top: 16px;
}

:deep(.t-statistic) {
  text-align: center;
}

:deep(.t-card__body) {
  padding: 16px;
}

:deep(.t-statistic) {
  text-align: center;
}

:deep(.t-statistic__title) {
  font-size: 14px;
}

:deep(.t-statistic__content) {
  font-size: 28px;
}
</style>
