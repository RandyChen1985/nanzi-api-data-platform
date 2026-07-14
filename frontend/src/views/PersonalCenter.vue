<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from '@/utils/axios'
import Toast from '@/components/Toast.vue'
import { copyToClipboard } from '@/utils/clipboard'

const userInfo = ref({
  id: 0,
  user_name: '',
  role: '',
  created_at: '',
  remark: '',
})

const userApiKey = ref('')
const loadingApiKey = ref(false)
const loadingPassword = ref(false)
const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const toast = ref({
  show: false,
  message: '',
  type: 'info' as 'success' | 'error' | 'warning' | 'info',
  key: 0,
})

const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
  toast.value = { show: true, message, type, key: toast.value.key + 1 }
}

const fetchUserInfo = async () => {
  try {
    const response = await axios.get('/api/portal/auth/me')
    if (response.data?.status === 'success') {
      userInfo.value = response.data.data
    }
  } catch (e) {
    console.error('Failed to fetch user info', e)
  }
}

const fetchApiKey = async () => {
  if (!userInfo.value.id) return
  loadingApiKey.value = true
  try {
    const response = await axios.get(`/api/portal/management/api-key/${userInfo.value.id}`)
    userApiKey.value = response.data.api_key
  } catch (error: any) {
    showToast(error.response?.data?.detail || '获取 API Key 失败', 'error')
  } finally {
    loadingApiKey.value = false
  }
}

const copyApiKey = async () => {
  if (!userApiKey.value) return
  const success = await copyToClipboard(userApiKey.value)
  if (success) {
    showToast('API Key 已复制', 'success')
  } else {
    showToast('复制失败', 'error')
  }
}

const submitChangePassword = async () => {
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    showToast('两次输入的密码不一致', 'warning')
    return
  }
  loadingPassword.value = true
  try {
    await axios.post('/api/portal/auth/change-password', {
      old_password: passwordForm.value.oldPassword,
      new_password: passwordForm.value.newPassword,
    })
    showToast('密码修改成功', 'success')
    passwordForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  } catch (e: any) {
    showToast(e.response?.data?.detail || '密码修改失败', 'error')
  } finally {
    loadingPassword.value = false
  }
}

onMounted(async () => {
  await fetchUserInfo()
  if (userInfo.value.id) {
    await fetchApiKey()
  }
})
</script>

<template>
  <div class="max-w-3xl mx-auto space-y-6">
    <div>
      <h1 class="text-xl sm:text-2xl font-bold text-gray-900">个人中心</h1>
      <p class="text-sm text-gray-500 mt-1">查看账号信息与修改密码</p>
    </div>

    <div class="bg-white rounded-xl border border-gray-100 p-4 sm:p-6 space-y-6">
      <div class="flex items-center gap-4">
        <div class="h-14 w-14 rounded-full bg-indigo-600 flex items-center justify-center text-lg font-bold text-white uppercase shrink-0">
          {{ userInfo.user_name ? userInfo.user_name.substring(0, 2) : 'U' }}
        </div>
        <div class="min-w-0">
          <h2 class="text-lg font-semibold text-gray-900 truncate">{{ userInfo.user_name || '-' }}</h2>
          <span
            class="inline-flex mt-1 items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
            :class="userInfo.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'"
          >
            {{ userInfo.role === 'admin' ? '管理员' : '普通用户' }}
          </span>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        <div>
          <p class="text-gray-500">用户名</p>
          <p class="mt-1 font-medium text-gray-900">{{ userInfo.user_name }}</p>
        </div>
        <div>
          <p class="text-gray-500">创建时间</p>
          <p class="mt-1 font-medium text-gray-900">{{ userInfo.created_at || '-' }}</p>
        </div>
        <div v-if="userInfo.remark" class="sm:col-span-2">
          <p class="text-gray-500">备注</p>
          <p class="mt-1 font-medium text-gray-900">{{ userInfo.remark }}</p>
        </div>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">API Key</label>
        <div class="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            :value="userApiKey || '加载中...'"
            readonly
            class="flex-1 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 text-xs sm:text-sm font-mono"
          />
          <button
            v-if="!userApiKey"
            type="button"
            class="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            :disabled="loadingApiKey"
            @click="fetchApiKey"
          >
            {{ loadingApiKey ? '加载中...' : '查看' }}
          </button>
          <button
            v-else
            type="button"
            class="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700"
            @click="copyApiKey"
          >
            复制
          </button>
        </div>
        <p class="mt-1 text-xs text-gray-400">API Key 支持重复查看和复制，请妥善保管</p>
      </div>
    </div>

    <div class="bg-white rounded-xl border border-gray-100 p-4 sm:p-6">
      <h3 class="text-base font-semibold text-gray-900 mb-4">修改密码</h3>
      <form class="space-y-4" @submit.prevent="submitChangePassword">
        <div>
          <label class="block text-sm font-medium text-gray-700">旧密码</label>
          <input
            v-model="passwordForm.oldPassword"
            type="password"
            class="mt-1 block w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
            placeholder="首次设置请留空"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">新密码</label>
          <input
            v-model="passwordForm.newPassword"
            type="password"
            required
            minlength="6"
            class="mt-1 block w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
            placeholder="至少 6 位"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700">确认新密码</label>
          <input
            v-model="passwordForm.confirmPassword"
            type="password"
            required
            class="mt-1 block w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
          />
        </div>
        <button
          type="submit"
          class="w-full sm:w-auto px-5 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          :disabled="loadingPassword"
        >
          {{ loadingPassword ? '提交中...' : '确认修改' }}
        </button>
      </form>
    </div>

    <Toast
      v-if="toast.show"
      :key="toast.key"
      :message="toast.message"
      :type="toast.type"
      @close="toast.show = false"
    />
  </div>
</template>
