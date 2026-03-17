import { createApp } from 'vue'
import { createPinia } from 'pinia'
import TDesign from 'tdesign-vue-next'
import TDesignIcons from 'tdesign-icons-vue-next'
import App from './App.vue'
import router from './router'

import 'tdesign-vue-next/es/style/index.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(TDesign)
app.use(TDesignIcons)

app.mount('#app')
