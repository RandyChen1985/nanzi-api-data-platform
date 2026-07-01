<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { login, ssoLogin, loginWithApiKey, getCurrentUser } from '@/api/auth'
import api from '@/utils/axios'
import { KeyIcon, UserIcon, GlobeAltIcon, CodeBracketIcon, ChartBarIcon, ServerIcon, ShieldCheckIcon, CpuChipIcon, CloudIcon } from '@heroicons/vue/24/outline'

const router = useRouter()
const activeTab = ref<'password' | 'apikey' | 'sso'>('password')
const apiKey = ref('')
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

// Reset inputs when switching tabs
watch(activeTab, () => {
  apiKey.value = ''
  username.value = ''
  password.value = ''
  error.value = ''
})

const toast = ref({

  show: false,
  message: '',
  type: 'info' as 'success' | 'error' | 'warning' | 'info',
  key: 0
})

const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {


  toast.value = {
    show: true,
    message,
    type,
    key: toast.value.key + 1
  }
}

const handleLogin = async () => {

  error.value = ''
  
  // Validation
  if (activeTab.value === 'apikey' && !apiKey.value) {
    error.value = '请输入您的 API 密钥'
    return
  }
  if (activeTab.value === 'password' && (!username.value || !password.value)) {
    error.value = '请输入用户名和密码'
    return
  }
  if (activeTab.value === 'sso' && (!username.value || !password.value)) {
    error.value = '请输入用户名和密码'
    return
  }
  
  loading.value = true
  
  try {
    let result
    if (activeTab.value === 'apikey') {
      result = await loginWithApiKey(apiKey.value)
    } else if (activeTab.value === 'sso') {
      result = await ssoLogin({ username: username.value, password: password.value })
    } else {
      result = await login({ username: username.value, password: password.value })
    }

    if (result && result.status === 'success') {
      const user = result.data
      localStorage.setItem('api_key', user.api_key ?? '')

      try {
        const authRes = await getCurrentUser()
        const permRes = await api.get('/api/portal/auth/permissions')
        const fullUserInfo = {
          ...authRes.data,
          permissions: permRes.data.permissions,
        }
        localStorage.setItem('user_info', JSON.stringify(fullUserInfo))
      } catch (e) {
        console.error('Failed to pre-fetch permissions', e)
      }

      const toastMsg = activeTab.value === 'sso' ? 'SSO 登录成功' : '登录成功'
      showToast(toastMsg, 'success')
      router.push('/dashboard/catalog')
    }
  } catch (e: any) {
    console.error(e)
    const msg = e.response?.data?.detail || e.response?.data?.message || '登录失败,请检查您的凭证'
    error.value = msg
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex bg-gray-50 overflow-hidden">
    <!-- Left: Infinite Scroll Showcase -->
    <div class="hidden lg:flex lg:flex-[11] relative bg-[#0f172a] overflow-hidden flex-col items-center justify-center">
      
      <!-- Overlay Gradient -->
      <div class="absolute inset-0 z-20 bg-gradient-to-t from-[#0f172a] via-transparent to-[#0f172a]"></div>
      <div class="absolute inset-0 z-20 bg-gradient-to-r from-[#0f172a] via-transparent to-[#0f172a]"></div>

      <!-- Main Title (Floating on top) -->
      <div class="absolute z-30 text-center px-8">
        <div class="inline-flex items-center justify-center p-3 mb-6 bg-blue-500/10 rounded-2xl backdrop-blur-sm border border-blue-500/20 shadow-2xl">
           <CloudIcon class="w-10 h-10 text-blue-400 mr-3" />
           <span class="text-white text-xl font-mono font-semibold tracking-wider">YUNSHU.DATA</span>
        </div>
        <h1 class="text-5xl md:text-6xl font-bold text-transparent bg-clip-text bg-gradient-to-br from-white via-blue-100 to-blue-400 mb-6 tracking-tight drop-shadow-2xl">
          云枢·数据服务平台
        </h1>
        <p class="text-lg text-slate-400 max-w-lg mx-auto leading-relaxed font-light tracking-wide">
          Yunshu API Data Platform
        </p>
      </div>

      <!-- Marquee Columns Container -->
      <div class="absolute inset-0 flex justify-center gap-6 opacity-40 rotate-12 scale-110 transform-gpu">
        
        <!-- Column 1: Slow Up -->
        <div class="marquee-col animate-scroll-up-slow">
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><CodeBracketIcon class="w-5 h-5 text-emerald-400"/><span>JSON API</span></div>
              <div class="card-body font-mono text-xs text-slate-400">
                { "status": "success", "data": [ ... ] }
              </div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><ServerIcon class="w-5 h-5 text-blue-400"/><span>ClickHouse</span></div>
              <div class="card-body">OLAP Engine Active<br/>Rows: 1.2B</div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><ShieldCheckIcon class="w-5 h-5 text-purple-400"/><span>Auth Guard</span></div>
              <div class="card-body">Role-Based Access Control</div>
           </div>
           <!-- Duplicate for infinite scroll -->
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><CodeBracketIcon class="w-5 h-5 text-emerald-400"/><span>JSON API</span></div>
              <div class="card-body font-mono text-xs text-slate-400">
                { "status": "success", "data": [ ... ] }
              </div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><ServerIcon class="w-5 h-5 text-blue-400"/><span>ClickHouse</span></div>
              <div class="card-body">OLAP Engine Active<br/>Rows: 1.2B</div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><ShieldCheckIcon class="w-5 h-5 text-purple-400"/><span>Auth Guard</span></div>
              <div class="card-body">Role-Based Access Control</div>
           </div>
        </div>

        <!-- Column 2: Fast Down -->
        <div class="marquee-col animate-scroll-down-fast mt-20">
           <div class="card bg-blue-900/20 border-blue-500/30">
              <div class="card-header"><ChartBarIcon class="w-5 h-5 text-cyan-400"/><span>Real-time</span></div>
              <div class="card-body">
                <div class="h-1 w-full bg-slate-700 rounded overflow-hidden">
                  <div class="h-full bg-cyan-400 w-3/4"></div>
                </div>
                <div class="mt-2 text-xs">QPS: 12,450</div>
              </div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><CpuChipIcon class="w-5 h-5 text-orange-400"/><span>Compute</span></div>
              <div class="card-body">Node Status: Healthy<br/>Latency: 12ms</div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><GlobeAltIcon class="w-5 h-5 text-pink-400"/><span>Global CDN</span></div>
              <div class="card-body">Edge Delivery: Enabled</div>
           </div>
           <!-- Duplicate -->
           <div class="card bg-blue-900/20 border-blue-500/30">
              <div class="card-header"><ChartBarIcon class="w-5 h-5 text-cyan-400"/><span>Real-time</span></div>
              <div class="card-body">
                <div class="h-1 w-full bg-slate-700 rounded overflow-hidden">
                  <div class="h-full bg-cyan-400 w-3/4"></div>
                </div>
                <div class="mt-2 text-xs">QPS: 12,450</div>
              </div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><CpuChipIcon class="w-5 h-5 text-orange-400"/><span>Compute</span></div>
              <div class="card-body">Node Status: Healthy<br/>Latency: 12ms</div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><GlobeAltIcon class="w-5 h-5 text-pink-400"/><span>Global CDN</span></div>
              <div class="card-body">Edge Delivery: Enabled</div>
           </div>
        </div>

        <!-- Column 3: Slow Up -->
        <div class="marquee-col animate-scroll-up-slow">
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><ServerIcon class="w-5 h-5 text-indigo-400"/><span>Microservices</span></div>
              <div class="card-body">Service Mesh: Linkerd</div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><CodeBracketIcon class="w-5 h-5 text-teal-400"/><span>GraphQL</span></div>
              <div class="card-body">Federated Schema<br/>v2.4.0</div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><CloudIcon class="w-5 h-5 text-sky-400"/><span>Cloud Native</span></div>
              <div class="card-body">K8s Deployment<br/>Replicas: 5</div>
           </div>
           <!-- Duplicate -->
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><ServerIcon class="w-5 h-5 text-indigo-400"/><span>Microservices</span></div>
              <div class="card-body">Service Mesh: Linkerd</div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><CodeBracketIcon class="w-5 h-5 text-teal-400"/><span>GraphQL</span></div>
              <div class="card-body">Federated Schema<br/>v2.4.0</div>
           </div>
           <div class="card bg-slate-800/80 border-slate-700/50">
              <div class="card-header"><CloudIcon class="w-5 h-5 text-sky-400"/><span>Cloud Native</span></div>
              <div class="card-body">K8s Deployment<br/>Replicas: 5</div>
           </div>
        </div>
      </div>
    </div>

    <!-- Right: Login Form -->
    <div class="w-full lg:flex-[4] flex items-center justify-center bg-gray-50 p-6 sm:p-12 relative z-10">
      <div class="w-full max-w-sm space-y-8">
        <div class="text-center">
          <div class="lg:hidden flex flex-col items-center mb-6">
            <img
              src="/favicon.png?v=20260629-2"
              alt="云枢数据服务平台"
              class="w-14 h-14 rounded-2xl shadow-md object-cover mb-3"
            />
            <h1 class="text-lg font-bold text-gray-900">云枢 · 数据服务平台</h1>
          </div>
          <div class="hidden lg:flex justify-center mb-4">
             <!-- Logo or Icon Animation -->
             <img
               src="/favicon.png?v=20260629-2"
               alt="云枢数据服务平台"
               class="w-20 h-20 rounded-2xl shadow-lg object-cover"
             />
          </div>
          <h2 class="text-2xl sm:text-3xl font-extrabold text-gray-900">
            欢迎回来
          </h2>
          <p class="mt-2 text-sm text-gray-600">
            请选择登录方式
          </p>
        </div>

        <!-- Tabs -->
        <div class="flex border-b border-gray-200 mb-6">
          <button 
            @click="activeTab = 'sso'"
            :class="[
              'flex-1 pb-4 text-sm font-medium text-center border-b-2 transition-colors duration-200',
              activeTab === 'sso' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            ]"
          >
            <div class="flex items-center justify-center space-x-2">
              <GlobeAltIcon class="w-4 h-4" />
              <span>SSO</span>
            </div>
          </button>
          <button 
            @click="activeTab = 'apikey'"
            :class="[
              'flex-1 pb-4 text-sm font-medium text-center border-b-2 transition-colors duration-200',
              activeTab === 'apikey' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            ]"
          >
            <div class="flex items-center justify-center space-x-2">
              <KeyIcon class="w-4 h-4" />
              <span>API Key</span>
            </div>
          </button>
          <button 
            @click="activeTab = 'password'"
            :class="[
              'flex-1 pb-4 text-sm font-medium text-center border-b-2 transition-colors duration-200',
              activeTab === 'password' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            ]"
          >
            <div class="flex items-center justify-center space-x-2">
              <UserIcon class="w-4 h-4" />
              <span>本地账号</span>
            </div>
          </button>
        </div>

        <form class="space-y-6" @submit.prevent="handleLogin">

          <!-- Password Form -->
          <div v-if="activeTab === 'password'" class="space-y-4 animate-fade-in-up">
            <div>
              <label for="username" class="block text-sm font-medium text-gray-700">用户名</label>
              <div class="mt-1">
                <input
                  id="username"
                  v-model="username"
                  type="text"
                  required
                  class="appearance-none block w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  placeholder="请输入用户名"
                />
              </div>
            </div>
            <div>
              <label for="password" class="block text-sm font-medium text-gray-700">密码</label>
              <div class="mt-1">
                <input
                  id="password"
                  v-model="password"
                  type="password"
                  required
                  class="appearance-none block w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  placeholder="请输入密码"
                />
              </div>
            </div>
          </div>

          <!-- API Key Form -->
          <div v-if="activeTab === 'apikey'" class="animate-fade-in-up">
            <label for="api-key" class="block text-sm font-medium text-gray-700">API 密钥</label>
            <div class="mt-1">
              <input
                id="api-key"
                v-model="apiKey"
                type="password"
                required
                class="appearance-none block w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                placeholder="请输入您的 API 密钥"
              />
            </div>
          </div>

          <!-- SSO Form -->
          <div v-if="activeTab === 'sso'" class="space-y-4 animate-fade-in-up">
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p class="text-sm text-blue-700">
                请用 Yes 用户登录
              </p>
            </div>
            <div>
              <label for="sso-username" class="block text-sm font-medium text-gray-700">用户名</label>
              <div class="mt-1">
                <input 
                  id="sso-username" 
                  v-model="username"
                  type="text" 
                  required 
                  class="appearance-none block w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  placeholder="请输入用户名"
                />
              </div>
            </div>
            <div>
              <label for="sso-password" class="block text-sm font-medium text-gray-700">密码</label>
              <div class="mt-1">
                <input 
                  id="sso-password" 
                  v-model="password"
                  type="password" 
                  required 
                  class="appearance-none block w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  placeholder="请输入密码"
                />
              </div>
            </div>
          </div>

          <div v-if="error" class="text-red-600 text-sm text-center bg-red-50 p-2 rounded">
             {{ error }}
          </div>

          <div>
            <button 
              type="submit" 
              :disabled="loading"
              class="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
            >
              <span v-if="loading">验证中...</span>
              <span v-else>立即登录</span>
            </button>
          </div>
        </form>
        
        <div class="mt-6">
          <div class="relative">
            <div class="absolute inset-0 flex items-center">
              <div class="w-full border-t border-gray-300"></div>
            </div>
            <div class="relative flex justify-center text-sm">
              <span class="px-2 bg-gray-50 text-gray-500">
                仅限授权人员访问
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.marquee-col {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.card {
  width: 260px;
  padding: 1.25rem;
  border-radius: 1rem;
  border-width: 1px;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  transition: transform 0.3s ease;
}

.card:hover {
  transform: translateY(-5px);
  border-color: rgba(96, 165, 250, 0.5); /* blue-400 */
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  font-weight: 600;
  color: #e2e8f0; /* slate-200 */
}

.card-body {
  font-size: 0.875rem;
  color: #94a3b8; /* slate-400 */
  line-height: 1.5;
}

@keyframes scroll-up {
  0% { transform: translateY(0); }
  100% { transform: translateY(-50%); }
}

@keyframes scroll-down {
  0% { transform: translateY(-50%); }
  100% { transform: translateY(0); }
}

.animate-scroll-up-slow {
  animation: scroll-up 40s linear infinite;
}

.animate-scroll-down-fast {
  animation: scroll-down 30s linear infinite;
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in-up {
  animation: fade-in-up 0.4s ease-out forwards;
}
</style>
