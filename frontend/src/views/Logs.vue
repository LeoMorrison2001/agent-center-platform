<template>
  <div class="logs">
    <t-card :bordered="false">
      <template #header>
        <div class="page-header">
          <h3>执行日志</h3>
        </div>
      </template>

      <!-- 筛选条件 -->
      <t-form class="filter-form" :data="filters" @submit="handleFilter">
        <t-row :gutter="16">
          <t-col :span="3">
            <t-select
              v-model="filters.status"
              placeholder="全部状态"
              clearable
              @change="handleFilter"
            >
              <t-option value="" label="全部状态" />
              <t-option value="queued" label="排队中" />
              <t-option value="completed" label="已完成" />
              <t-option value="failed" label="失败" />
            </t-select>
          </t-col>

          <t-col :span="3">
            <t-select
              v-model="filters.agent_key"
              placeholder="全部智能体"
              clearable
              @change="handleFilter"
            >
              <t-option value="" label="全部智能体" />
              <t-option
                v-for="service in services"
                :key="service.agent_key"
                :value="service.agent_key"
                :label="service.name"
              />
            </t-select>
          </t-col>

          <t-col :span="3">
            <t-button theme="primary" type="submit">
              查询
            </t-button>
          </t-col>
        </t-row>
      </t-form>

      <!-- 统计卡片 -->
      <t-row :gutter="[16, 16]" class="stats-row">
        <t-col :span="3">
          <t-statistic
            title="总任务数"
            :value="stats.total || 0"
          />
        </t-col>
        <t-col :span="3">
          <t-statistic
            title="已完成"
            :value="stats.completed || 0"
          />
        </t-col>
        <t-col :span="3">
          <t-statistic
            title="失败"
            :value="stats.failed || 0"
          />
        </t-col>
        <t-col :span="3">
          <t-statistic
            title="成功率"
            :value="stats.success_rate || 0"
            suffix="%"
            :formatter="(value) => value.toString()"
          />
        </t-col>
      </t-row>

      <!-- 日志表格 -->
      <t-table
        :data="logs"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        stripe
        size="small"
      >
        <template #status="{ row }">
          <t-tag
            :theme="getStatusTheme(row.status)"
            variant="light"
          >
            {{ getStatusText(row.status) }}
          </t-tag>
        </template>

        <template #task_content="{ row }">
          <div class="task-content">{{ row.task_content }}</div>
        </template>

        <template #duration="{ row }">
          <span v-if="row.duration_ms">{{ row.duration_ms }} ms</span>
          <span v-else class="text-muted">-</span>
        </template>

        <template #created_at="{ row }">
          {{ formatDate(row.created_at) }}
        </template>

        <template #operation="{ row }">
          <t-space>
            <t-button
              size="small"
              variant="outline"
              @click="showRequestResponse(row)"
            >
              请求/响应
            </t-button>
            <t-button
              size="small"
              variant="outline"
              @click="showDetail(row)"
            >
              详情
            </t-button>
          </t-space>
        </template>
      </t-table>
    </t-card>

    <!-- 详情对话框 -->
    <t-dialog
      v-model:visible="showDetailDialog"
      header="任务详情"
      width="700"
      placement="center"
      :attach="false"
    >
      <t-descriptions :column="2" bordered v-if="currentLog">
        <t-descriptions-item label="任务ID">
          {{ currentLog.task_id }}
        </t-descriptions-item>
        <t-descriptions-item label="智能体">
          {{ getServiceName(currentLog.agent_key) }}
        </t-descriptions-item>
        <t-descriptions-item label="实例ID">
          {{ currentLog.instance_id || '-' }}
        </t-descriptions-item>
        <t-descriptions-item label="状态">
          <t-tag
            :theme="getStatusTheme(currentLog.status)"
            variant="light"
          >
            {{ getStatusText(currentLog.status) }}
          </t-tag>
        </t-descriptions-item>
        <t-descriptions-item label="任务内容" :span="2">
          {{ currentLog.task_content }}
        </t-descriptions-item>
        <t-descriptions-item label="执行结果" :span="2" v-if="currentLog.result">
          <div class="result-content">{{ currentLog.result }}</div>
        </t-descriptions-item>
        <t-descriptions-item label="错误信息" :span="2" v-if="currentLog.error_message">
          <div class="error-content">{{ currentLog.error_message }}</div>
        </t-descriptions-item>
        <t-descriptions-item label="创建时间">
          {{ formatDateTime(currentLog.created_at) }}
        </t-descriptions-item>
        <t-descriptions-item label="完成时间">
          {{ formatDateTime(currentLog.completed_at) }}
        </t-descriptions-item>
        <t-descriptions-item label="执行耗时">
          {{ currentLog.duration_ms ? `${currentLog.duration_ms} ms` : '-' }}
        </t-descriptions-item>
      </t-descriptions>
    </t-dialog>

    <!-- 请求/响应对话框 -->
    <t-dialog
      v-model:visible="showRequestResponseDialog"
      header="请求 / 响应"
      width="700"
      placement="center"
      :attach="false"
    >
      <div v-if="currentLog" class="request-response">
        <!-- 请求 -->
        <div class="section">
          <div class="section-header">请求</div>
          <pre class="code-content">{{ currentLog.task_content }}</pre>
        </div>

        <!-- 响应 -->
        <div class="section">
          <div class="section-header">响应</div>
          <div v-if="currentLog.result">
            <pre class="code-content">{{ currentLog.result }}</pre>
          </div>
          <div v-else-if="currentLog.error_message">
            <pre class="code-content error">{{ currentLog.error_message }}</pre>
          </div>
          <div v-else class="text-muted">暂无响应</div>
        </div>
      </div>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { usePlatformStore } from '@/stores/platform'
import { api, type TaskLog, type TaskStats } from '@/api/services'
import { useMonitorWebSocket } from '@/composables/useMonitorWebSocket'

const platformStore = usePlatformStore()

const logs = ref<TaskLog[]>([])
const stats = ref<TaskStats>({
  total: 0,
  completed: 0,
  failed: 0,
  queued: 0,
  success_rate: 0
})

const loading = ref(false)
const showDetailDialog = ref(false)
const showRequestResponseDialog = ref(false)
const currentLog = ref<TaskLog | null>(null)

const filters = ref({
  status: '',
  agent_key: ''
})

const currentPage = ref(1)
const pageSize = ref(20)

const services = computed(() => platformStore.services)

const columns = [
  { colKey: 'task_id', title: '任务ID', width: 200 },
  { colKey: 'agent_key', title: '智能体', width: 150 },
  { colKey: 'task_content', title: '任务内容', ellipsis: true },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'duration', title: '耗时', width: 100 },
  { colKey: 'created_at', title: '创建时间', width: 180 },
  { colKey: 'operation', title: '操作', width: 180 }
]

const pagination = computed(() => ({
  defaultPageSize: pageSize.value,
  defaultCurrentPage: currentPage.value,
  total: stats.value.total
}))

const getStatusText = (status: string) => {
  const map = {
    queued: '排队中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

const getStatusTheme = (status: string) => {
  const map = {
    queued: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'default'
}

const getServiceName = (agentKey: string) => {
  const service = services.value.find(s => s.agent_key === agentKey)
  return service?.name || agentKey
}

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const formatDateTime = (dateStr: string | null) => {
  if (!dateStr) return '-'
  return formatDate(dateStr)
}

const fetchLogs = async () => {
  try {
    loading.value = true
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
      ...(filters.value.status && { status: filters.value.status }),
      ...(filters.value.agent_key && { agent_key: filters.value.agent_key })
    }

    const response = await api.getTaskLogs(params)
    logs.value = response.logs

    // 同时获取统计数据
    await fetchStats()
  } catch (error) {
    MessagePlugin.error('获取日志失败')
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    stats.value = await api.getTaskStats()
  } catch (error) {
    console.error('获取统计数据失败', error)
  }
}

const handleFilter = () => {
  currentPage.value = 1
  fetchLogs()
}

const showDetail = (log: TaskLog) => {
  currentLog.value = log
  showDetailDialog.value = true
}

const showRequestResponse = (log: TaskLog) => {
  currentLog.value = log
  showRequestResponseDialog.value = true
}

// 监控 WebSocket 事件处理
const { on: onMonitorEvent, off: offMonitorEvent } = useMonitorWebSocket()

let unmonitorTaskCreated: (() => void) | null = null
let unmonitorTaskQueued: (() => void) | null = null
let unmonitorTaskCompleted: (() => void) | null = null
let unmonitorTaskFailed: (() => void) | null = null

onMounted(async () => {
  await platformStore.fetchServices()
  await fetchLogs()

  // 监听任务创建事件
  unmonitorTaskCreated = onMonitorEvent('task.created', async () => {
    console.log('[Logs] 任务创建，刷新日志和统计')
    await fetchLogs()
  })

  // 监听任务分发事件
  unmonitorTaskQueued = onMonitorEvent('task.queued', async () => {
    console.log('[Logs] 任务入队，刷新日志和统计')
    await fetchLogs()
  })

  // 监听任务完成事件
  unmonitorTaskCompleted = onMonitorEvent('task.completed', async () => {
    console.log('[Logs] 任务完成，刷新日志和统计')
    await fetchLogs()
  })

  // 监听任务失败事件
  unmonitorTaskFailed = onMonitorEvent('task.failed', async () => {
    console.log('[Logs] 任务失败，刷新日志和统计')
    await fetchLogs()
  })
})

onUnmounted(() => {
  // 清理事件监听
  if (unmonitorTaskCreated) unmonitorTaskCreated()
  if (unmonitorTaskQueued) unmonitorTaskQueued()
  if (unmonitorTaskCompleted) unmonitorTaskCompleted()
  if (unmonitorTaskFailed) unmonitorTaskFailed()
})
</script>

<style scoped>
.logs {
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

.filter-form {
  margin-bottom: 16px;
}

.stats-row {
  margin-bottom: 16px;
}

.task-content {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-content {
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}

.error-content {
  color: var(--td-error-color);
  white-space: pre-wrap;
}

.text-muted {
  color: var(--td-text-color-secondary);
}

.request-response {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section {
  display: flex;
  flex-direction: column;
}

.section-header {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
  color: var(--td-text-color-primary);
}

.code-content {
  background: var(--td-bg-color-container-hover);
  padding: 16px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.code-content.error {
  color: var(--td-error-color);
  background: var(--td-error-color-1);
}
</style>
