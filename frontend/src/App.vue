<template>
  <t-layout>
    <t-header class="header">
      <div class="header-content">
        <h1 class="title">智能体服务平台</h1>
      </div>
    </t-header>

    <t-layout>
      <t-aside class="sidebar">
        <t-menu
          :value="activeMenu"
          @change="handleMenuChange"
        >
          <t-menu-item value="dashboard">
            <template #icon>
              <t-icon name="dashboard" />
            </template>
            仪表盘
          </t-menu-item>
          <t-menu-item value="services">
            <template #icon>
              <t-icon name="server" />
            </template>
            服务管理
          </t-menu-item>
          <t-menu-item value="logs">
            <template #icon>
              <t-icon name="file" />
            </template>
            执行日志
          </t-menu-item>
          <t-menu-item value="docs">
            <template #icon>
              <t-icon name="book-open" />
            </template>
            API 文档
          </t-menu-item>
        </t-menu>
      </t-aside>

      <t-content class="content">
        <router-view />
      </t-content>
    </t-layout>
  </t-layout>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const activeMenu = computed(() => {
  const path = route.path
  if (!path) return 'dashboard'
  // 移除开头的 /
  return path.substring(1)
})

const handleMenuChange = (value: string) => {
  router.push(`/${value}`)
}
</script>

<style>
/* 全局样式 - 修复页面滚动条 */
html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  overflow: hidden;
}

#app {
  height: 100%;
  overflow: hidden;
}
</style>

<style scoped>
.header {
  background: #fff;
  border-bottom: 1px solid var(--td-component-border);
  padding: 0 24px;
  height: 64px;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  color: var(--td-text-color-primary);
}

.sidebar {
  background: #fff;
  border-right: 1px solid var(--td-component-border);
  width: 200px;
  overflow-y: auto;
  overflow-x: hidden;
}

.content {
  padding: 24px;
  background: var(--td-bg-color-container);
  min-height: calc(100vh - 64px);
  overflow-y: auto;
  height: calc(100vh - 64px);
}

/* TDesign 布局修复 */
:deep(.t-layout) {
  height: 100%;
  overflow: hidden;
}

:deep(.t-layout > .t-layout) {
  height: 100%;
  overflow: hidden;
}

:deep(.t-layout__body) {
  overflow: hidden;
}

:deep(.t-aside) {
  overflow-y: auto;
  overflow-x: hidden;
}

:deep(.t-content) {
  overflow-y: auto;
}
</style>
