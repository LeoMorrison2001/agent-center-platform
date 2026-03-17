<template>
  <div class="api-docs">
    <t-card :bordered="false">
      <template #header>
        <div class="page-header">
          <h3>对外 API 接口文档</h3>
          <t-tag theme="success" variant="light">v0.2.0</t-tag>
        </div>
      </template>

      <!-- 接口列表 -->
      <div class="api-list">
        <!-- 发送任务接口 -->
        <div class="api-item">
          <div class="api-header">
            <t-tag theme="primary" shape="round">POST</t-tag>
            <code class="api-path">/api/platform/dispatch</code>
            <t-tag theme="success" variant="light">发送任务</t-tag>
          </div>

          <div class="api-content">
            <div class="api-section">
              <h4>接口说明</h4>
              <p>发送任务到智能体服务，平台自动生成任务ID并返回</p>
            </div>

            <div class="api-section">
              <h4>请求参数</h4>
              <t-table :data="dispatchRequestParams" :columns="paramColumns" size="small" bordered />
            </div>

            <div class="api-section">
              <h4>请求示例</h4>
              <pre class="code-block"><code>{{ dispatchRequestExample }}</code></pre>
            </div>

            <div class="api-section">
              <h4>响应示例</h4>
              <pre class="code-block"><code>{{ dispatchResponseExample }}</code></pre>
            </div>

            <div class="api-section">
              <h4>在线测试</h4>
              <t-form @submit.prevent="handleDispatchTest">
                <t-form-item label="智能体Key">
                  <t-input v-model="testForm.agent_key" placeholder="weather" />
                </t-form-item>
                <t-form-item label="任务内容">
                  <t-textarea v-model="testForm.task_content" placeholder="查询北京天气" />
                </t-form-item>
                <t-form-item>
                  <t-button theme="primary" type="submit" :loading="testLoading">发送测试</t-button>
                </t-form-item>
              </t-form>
              <div v-if="testResult" class="test-result">
                <h5>测试结果</h5>
                <pre class="code-block"><code>{{ JSON.stringify(testResult, null, 2) }}</code></pre>
              </div>
            </div>
          </div>
        </div>

        <!-- 查询结果接口 -->
        <div class="api-item">
          <div class="api-header">
            <t-tag theme="success" shape="round">GET</t-tag>
            <code class="api-path">/api/platform/logs/{task_id}</code>
            <t-tag theme="success" variant="light">查询结果</t-tag>
          </div>

          <div class="api-content">
            <div class="api-section">
              <h4>接口说明</h4>
              <p>根据任务ID查询任务执行状态和结果</p>
            </div>

            <div class="api-section">
              <h4>路径参数</h4>
              <t-table :data="logPathParams" :columns="paramColumns" size="small" bordered />
            </div>

            <div class="api-section">
              <h4>响应示例</h4>
              <pre class="code-block"><code>{{ logResponseExample }}</code></pre>
            </div>

            <div class="api-section">
              <h4>在线测试</h4>
              <t-space direction="vertical" style="width: 100%">
                <t-input v-model="queryTaskId" placeholder="请输入任务ID" />
                <t-space>
                  <t-button theme="primary" @click="handleQueryTest" :loading="queryLoading">查询</t-button>
                  <t-button v-if="testResult" theme="default" @click="useLastTaskId">使用上方任务ID</t-button>
                </t-space>
              </t-space>
              <div v-if="queryResult" class="test-result">
                <h5>查询结果</h5>
                <pre class="code-block"><code>{{ JSON.stringify(queryResult, null, 2) }}</code></pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'

const API_BASE = window.location.origin

// 参数表格列
const paramColumns = [
  { colKey: 'name', title: '参数名', width: 150 },
  { colKey: 'type', title: '类型', width: 100 },
  { colKey: 'required', title: '必填', width: 80 },
  { colKey: 'description', title: '说明' }
]

// 发送任务参数
const dispatchRequestParams = [
  { name: 'agent_key', type: 'string', required: '是', description: '智能体服务标识（如：weather）' },
  { name: 'task_content', type: 'string', required: '是', description: '任务内容' }
]

// 日志路径参数
const logPathParams = [
  { name: 'task_id', type: 'string', required: '是', description: '任务ID（由dispatch接口返回）' }
]

// 请求示例
const dispatchRequestExample = `POST /api/platform/dispatch
Content-Type: application/json

{
  "agent_key": "weather",
  "task_content": "查询北京天气"
}`

// 响应示例
const dispatchResponseExample = `{
  "task_id": "task_20250317_103045_abc123",
  "agent_key": "weather",
  "status": "queued",
  "message": "任务已加入队列"
}`

const logResponseExample = `{
  "task_id": "task_20250317_103045_abc123",
  "agent_key": "weather",
  "task_content": "查询北京天气",
  "status": "completed",
  "result": "北京当前天气：晴，温度15°C",
  "created_at": "2025-03-17T10:30:45.123000",
  "started_at": "2025-03-17T10:30:45.500000",
  "completed_at": "2025-03-17T10:30:47.456000",
  "duration_ms": 2333
}`

// 测试表单
const testForm = ref({
  agent_key: 'weather',
  task_content: '查询北京天气'
})
const testLoading = ref(false)
const testResult = ref<any>(null)

const queryTaskId = ref('')
const queryLoading = ref(false)
const queryResult = ref<any>(null)

// 发送任务测试
const handleDispatchTest = async () => {
  testLoading.value = true
  testResult.value = null
  queryResult.value = null

  try {
    const response = await fetch(`${API_BASE}/api/platform/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(testForm.value)
    })

    const data = await response.json()
    testResult.value = data

    if (response.ok) {
      MessagePlugin.success(`任务已提交，ID: ${data.task_id}`)
    } else {
      MessagePlugin.error(data.detail || '请求失败')
    }
  } catch (error) {
    MessagePlugin.error('网络错误')
    console.error(error)
  } finally {
    testLoading.value = false
  }
}

// 使用上次的任务ID
const useLastTaskId = () => {
  if (testResult.value?.task_id) {
    queryTaskId.value = testResult.value.task_id
  }
}

// 查询结果测试
const handleQueryTest = async () => {
  if (!queryTaskId.value) {
    MessagePlugin.warning('请输入任务ID')
    return
  }

  queryLoading.value = true
  queryResult.value = null

  try {
    const response = await fetch(`${API_BASE}/api/platform/logs/${queryTaskId.value}`)
    const data = await response.json()
    queryResult.value = data

    if (response.ok) {
      MessagePlugin.success('查询成功')
    } else {
      MessagePlugin.error(data.detail || '查询失败')
    }
  } catch (error) {
    MessagePlugin.error('网络错误')
    console.error(error)
  } finally {
    queryLoading.value = false
  }
}
</script>

<style scoped>
.api-docs {
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

.api-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.api-item {
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-default);
  overflow: hidden;
}

.api-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--td-bg-color-container);
  border-bottom: 1px solid var(--td-component-border);
}

.api-path {
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 14px;
  color: var(--td-text-color-primary);
  background: var(--td-bg-color-page);
  padding: 4px 12px;
  border-radius: 4px;
  flex: 1;
}

.api-content {
  padding: 20px;
}

.api-section {
  margin-bottom: 24px;
}

.api-section:last-child {
  margin-bottom: 0;
}

.api-section h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: var(--td-text-color-primary);
}

.api-section h5 {
  font-size: 14px;
  font-weight: 600;
  margin: 12px 0 8px 0;
  color: var(--td-text-color-primary);
}

.api-section p {
  margin: 0;
  color: var(--td-text-color-secondary);
}

.code-block {
  background: var(--td-bg-color-page);
  border: 1px solid var(--td-component-border);
  border-radius: var(--td-radius-default);
  padding: 16px;
  overflow-x: auto;
  margin: 0;
}

.code-block code {
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--td-text-color-primary);
}

.test-result {
  margin-top: 16px;
}
</style>
