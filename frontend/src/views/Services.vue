<template>
  <div class="services">
    <t-card :bordered="false">
      <template #header>
        <div class="page-header">
          <h3>服务管理</h3>
          <t-button theme="primary" @click="showCreateDialog = true">
            <template #icon>
              <t-icon name="add" />
            </template>
            创建服务
          </t-button>
        </div>
      </template>

      <t-table
        :data="services"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        stripe
      >
        <template #type="{ row }">
          <t-tag>{{ row.type }}</t-tag>
        </template>

        <template #working_count="{ row }">
          <t-tag :theme="row.working_count > 0 ? 'success' : 'default'" variant="light">
            {{ row.working_count }} 实例
          </t-tag>
        </template>

        <template #created_at="{ row }">
          {{ formatDate(row.created_at) }}
        </template>

        <template #operation="{ row }">
          <t-space>
            <t-button
              size="small"
              variant="outline"
              @click="handleEdit(row)"
            >
              编辑
            </t-button>
            <t-button
              size="small"
              variant="outline"
              :disabled="row.working_count === 0"
              @click="openTestDialog(row)"
            >
              测试
            </t-button>
            <t-popconfirm
              :disabled="row.working_count > 0"
              :content="row.working_count > 0 ? '该服务有活跃实例，无法删除' : '确认删除该服务？'"
              @confirm="handleDelete(row)"
            >
              <t-button
                size="small"
                theme="danger"
                variant="outline"
                :disabled="row.working_count > 0"
              >
                删除
              </t-button>
            </t-popconfirm>
          </t-space>
        </template>
      </t-table>
    </t-card>

    <!-- 创建/编辑对话框 -->
    <t-dialog
      v-model:visible="showCreateDialog"
      :header="isEdit ? '编辑服务' : '创建服务'"
      width="700"
      placement="center"
      :attach="false"
      @confirm="handleConfirm"
    >
      <t-form
        ref="formRef"
        :data="formData"
        :rules="rules"
        label-width="120px"
      >
        <t-form-item label="智能体KEY" name="agent_key">
          <t-input
            v-model="formData.agent_key"
            placeholder="请输入唯一标识符（小写字母、数字、下划线）"
            :disabled="isEdit"
            @blur="validateAgentKey"
          />
        </t-form-item>

        <t-form-item label="服务名称" name="name">
          <t-input
            v-model="formData.name"
            placeholder="请输入服务名称"
            :maxlength="20"
          />
        </t-form-item>

        <t-form-item label="服务类型" name="type">
          <t-select
            v-model="formData.type"
            placeholder="请选择服务类型"
          >
            <t-option value="通用" label="通用" />
            <t-option value="智能家居" label="智能家居" />
            <t-option value="代码审查" label="代码审查" />
            <t-option value="电脑控制" label="电脑控制" />
            <t-option value="消息发送" label="消息发送" />
            <t-option value="自定义" label="自定义" />
          </t-select>
        </t-form-item>

        <t-form-item label="能力描述" name="description">
          <t-textarea
            v-model="formData.description"
            placeholder="请描述该智能体的能力"
            :autosize="{ minRows: 3, maxRows: 4 }"
            :maxlength="500"
          />
        </t-form-item>

        <!-- 模型配置 -->
        <t-divider content="模型配置" />

        <t-form-item label="模型名称" name="model_name">
          <t-input
            v-model="formData.model_name"
            placeholder="gemini-2.5-flash"
          />
        </t-form-item>

        <t-form-item label="模型提供商" name="model_provider">
          <t-select
            v-model="formData.model_provider"
            placeholder="请选择"
          >
            <t-option value="google" label="Google" />
            <t-option value="openai" label="OpenAI" />
            <t-option value="zhipu" label="智谱" />
          </t-select>
        </t-form-item>

        <t-form-item label="API Key" name="api_key">
          <t-input
            v-model="formData.api_key"
            placeholder="请输入 API Key"
            type="password"
          />
        </t-form-item>

        <t-form-item label="温度参数" name="temperature">
          <t-slider
            v-model="formData.temperature"
            :min="0"
            :max="1"
            :step="0.1"
            :marks="{0: '确定', 0.5: '平衡', 1: '创意'}"
          />
        </t-form-item>

        <t-form-item label="最大 Tokens" name="max_tokens">
          <t-input-number
            v-model="formData.max_tokens"
            :min="1024"
            :max="128000"
            :step="1024"
            placeholder="65536"
          />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- 测试对话框 -->
    <t-dialog
      v-model:visible="showTestDialog"
      header="测试智能体实例"
      width="600"
      @confirm="handleTestConfirm"
    >
      <div v-if="testLoading" class="loading-wrapper">
        <t-loading />
      </div>
      <div v-else>
        <t-form label-width="100px">
          <t-form-item label="选择实例">
            <t-select
              v-model="testForm.instance_id"
              placeholder="请选择要测试的实例"
            >
              <t-option
                v-for="inst in testInstances"
                :key="inst.instance_id"
                :value="inst.instance_id"
                :label="inst.instance_id"
              />
            </t-select>
          </t-form-item>

          <t-form-item label="测试任务">
            <t-input
              v-model="testForm.task_content"
              placeholder="请输入测试任务内容"
            />
          </t-form-item>
        </t-form>

        <div v-if="testResult" class="test-result">
          <div class="test-result-title">测试结果：</div>
          <div class="test-result-content">
            <t-tag theme="success" v-if="testResult.status === 'dispatched'">任务已发送</t-tag>
            <t-tag theme="danger" v-else>发送失败</t-tag>
            <div class="test-result-detail">
              任务ID: {{ testResult.task_id }}<br>
              实例: {{ testResult.instance_id }}
            </div>
          </div>
        </div>
      </div>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { api, type AgentService } from '@/api/services'
import { useMonitorWebSocket } from '@/composables/useMonitorWebSocket'

const services = ref<AgentService[]>([])
const loading = ref(false)
const total = ref(0)

const currentPage = ref(1)
const pageSize = ref(10)

const showCreateDialog = ref(false)
const isEdit = ref(false)
const formRef = ref()

const formData = ref({
  agent_key: '',
  name: '',
  type: '',
  description: '',
  // 模型配置
  model_name: 'gemini-2.5-flash',
  model_provider: 'google',
  api_key: '',
  temperature: 0,
  max_tokens: 65536
})

// 测试相关状态
const showTestDialog = ref(false)
const testLoading = ref(false)
const testInstances = ref<Array<{ instance_id: string; connected_at: string; last_heartbeat: string }>>([])
const testForm = ref({
  instance_id: '',
  task_content: ''
})
const testResult = ref<{ task_id: string; instance_id: string; status: string } | null>(null)
const currentTestService = ref<AgentService | null>(null)

const rules = {
  agent_key: [
    { required: true, message: '请输入智能体KEY', type: 'error' },
    {
      pattern: /^[a-z0-9_]+$/,
      message: '只能包含小写字母、数字和下划线',
      type: 'warning'
    }
  ],
  name: [{ required: true, message: '请输入服务名称', type: 'error' }],
  type: [{ required: true, message: '请选择服务类型', type: 'error' }],
  description: [{ required: true, message: '请输入能力描述', type: 'error' }],
  // 模型配置验证（必填字段）
  model_name: [
    { required: true, message: '请输入模型名称', type: 'error' },
    { min: 1, message: '模型名称不能为空', type: 'error' }
  ],
  model_provider: [{ required: true, message: '请选择模型提供商', type: 'error' }],
  api_key: [
    { required: true, message: '请输入 API Key', type: 'error' },
    { min: 1, message: 'API Key 不能为空', type: 'error' }
  ],
  temperature: [{ required: true, message: '请设置温度参数', type: 'error' }],
  max_tokens: [{ required: true, message: '请设置最大 Tokens', type: 'error' }]
}

// 失焦点校验智能体KEY
const validateAgentKey = async () => {
  if (!formData.value.agent_key || isEdit.value) return

  try {
    const result = await api.validateAgentKey(formData.value.agent_key)

    if (!result.valid) {
      if (result.exists) {
        MessagePlugin.error(result.message)
      } else {
        MessagePlugin.warning(result.message)
      }
      // 触发表单校验错误
      if (formRef.value) {
        await formRef.value.validate(['agent_key'])
      }
    }
  } catch (error) {
    console.error('校验智能体KEY失败', error)
  }
}

const fetchServices = async () => {
  try {
    loading.value = true
    const result = await api.getServices({
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    })
    services.value = result.services
    total.value = result.total
  } catch (error) {
    MessagePlugin.error('获取服务列表失败')
  } finally {
    loading.value = false
  }
}

const columns = [
  { colKey: 'agent_key', title: '智能体KEY', width: 200 },
  { colKey: 'name', title: '名称', width: 150 },
  { colKey: 'type', title: '类型', width: 120 },
  { colKey: 'description', title: '描述', width: 250, ellipsis: true },
  { colKey: 'working_count', title: '智能体实例数', width: 120 },
  { colKey: 'created_at', title: '创建时间', width: 180 },
  { colKey: 'operation', title: '操作', width: 200 }
]

const pagination = ref({
  current: currentPage,
  pageSize,
  total,
  showTotal: true,
  onChange: (page: number) => {
    currentPage.value = page
    fetchServices()
  },
  onPageSizeChange: (size: number) => {
    pageSize.value = size
    currentPage.value = 1
    fetchServices()
  }
})

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const resetForm = () => {
  formData.value = {
    agent_key: '',
    name: '',
    type: '',
    description: '',
    // 模型配置
    model_name: 'gemini-2.5-flash',
    model_provider: 'google',
    api_key: '',
    temperature: 0,
    max_tokens: 65536
  }
}

const handleEdit = (service: AgentService) => {
  isEdit.value = true
  formData.value = {
    agent_key: service.agent_key,
    name: service.name,
    type: service.type,
    description: service.description,
    // 模型配置
    model_name: service.model_name || 'gemini-2.5-flash',
    model_provider: service.model_provider || 'google',
    api_key: service.api_key || '',
    temperature: service.temperature ?? 0,
    max_tokens: service.max_tokens ?? 65536
  }
  showCreateDialog.value = true
}

const handleDelete = async (service: AgentService) => {
  try {
    await api.deleteService(service.agent_key)
    MessagePlugin.success('删除成功')
    await fetchServices()
  } catch (error) {
    MessagePlugin.error('删除失败')
  }
}

const handleConfirm = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return

  try {
    if (isEdit.value) {
      await api.updateService(formData.value.agent_key, formData.value)
      MessagePlugin.success('更新成功')
      await fetchServices()
    } else {
      await api.createService(formData.value)
      MessagePlugin.success('创建成功')
      await fetchServices()
    }
    showCreateDialog.value = false
    resetForm()
  } catch (error) {
    MessagePlugin.error(isEdit.value ? '编辑失败' : '创建失败')
  }
}

// 测试相关方法
const openTestDialog = async (service: AgentService) => {
  currentTestService.value = service
  testResult.value = null
  testForm.value.instance_id = ''
  testForm.value.task_content = '测试任务'
  showTestDialog.value = true

  // 加载实例列表
  try {
    testLoading.value = true
    const result = await api.getServiceInstances(service.agent_key)
    testInstances.value = result.instances
  } catch (error) {
    MessagePlugin.error('获取实例列表失败')
  } finally {
    testLoading.value = false
  }
}

const handleTestConfirm = async () => {
  if (!testForm.value.instance_id) {
    MessagePlugin.warning('请选择要测试的实例')
    return
  }

  if (!currentTestService.value) return

  try {
    const result = await api.testServiceInstance(
      currentTestService.value.agent_key,
      {
        instance_id: testForm.value.instance_id,
        task_content: testForm.value.task_content
      }
    )
    testResult.value = result
    MessagePlugin.success('测试任务已发送')
  } catch (error) {
    MessagePlugin.error('发送测试任务失败')
  }
}

// 监控 WebSocket 事件处理
const { on: onMonitorEvent, off: offMonitorEvent } = useMonitorWebSocket()

let unmonitorInstanceConnected: (() => void) | null = null
let unmonitorInstanceDisconnected: (() => void) | null = null

onMounted(async () => {
  await fetchServices()

  // 监听智能体实例连接事件
  unmonitorInstanceConnected = onMonitorEvent('instance.connected', async (event) => {
    console.log('[Services] 智能体实例连接:', event)
    await fetchServices()
  })

  // 监听智能体实例断开事件
  unmonitorInstanceDisconnected = onMonitorEvent('instance.disconnected', async (event) => {
    console.log('[Services] 智能体实例断开:', event)
    await fetchServices()
  })
})

onUnmounted(() => {
  // 清理事件监听
  if (unmonitorInstanceConnected) unmonitorInstanceConnected()
  if (unmonitorInstanceDisconnected) unmonitorInstanceDisconnected()
})
</script>

<style scoped>
.services {
  max-width: 1400px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.page-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 32px;
  min-height: 32px;
}

.loading-wrapper {
  padding: 40px 0;
  text-align: center;
}

.test-result {
  margin-top: 20px;
  padding: 16px;
  background: var(--td-bg-color-container);
  border-radius: 4px;
}

.test-result-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.test-result-detail {
  margin-top: 8px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
</style>

<style>
/* 对话框滚动条最佳实践 */
.services .t-dialog__body {
  max-height: none !important;
}
</style>
