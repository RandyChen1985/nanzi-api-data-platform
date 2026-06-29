import { createApp } from 'vue'
import './style.css'
import App from '@/App.vue'
import router from '@/router'

// 初始化 axios 拦截器（401 统一处理）
import '@/utils/axios'

const app = createApp(App)
app.use(router)
app.mount('#app')
