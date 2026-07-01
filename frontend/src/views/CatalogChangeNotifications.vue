<script setup lang="ts">
import { ref, onMounted, computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import axios from '@/utils/axios'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const { showToast } = useToast()
const refreshCatalogBadge = inject<(() => void) | undefined>('refreshCatalogBadge', undefined)
const loading = ref(true)
const marking = ref(false)
const notifications = ref<any[]>([])
const total = ref(0)
const unread = ref(0)
const unreadOnly = ref(false)
const page = ref(1)
const pageSize = 20

const actionLabel = (action: string) => {
  const map: Record<string, string> = { UPDATE: '配置更新', ROLLBACK: '配置回滚' }
  return map[action] || action
}

const actionClass = (action: string) => {
  if (action === 'ROLLBACK') return 'bg-purple-100 text-purple-800'
  return 'bg-blue-100 text-blue-800'
}

const fetchNotifications = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/portal/catalog/change-notifications', {
      params: {
        unread_only: unreadOnly.value,
        page: page.value,
        size: pageSize,
      },
    })
    notifications.value = res.data.items || []
    total.value = res.data.total || 0
    unread.value = res.data.unread || 0
  } catch (e: any) {
    notifications.value = []
    total.value = 0
    if (e.response?.status !== 403) {
      showToast(e.response?.data?.detail || '加载失败', 'error')
    }
  } finally {
    loading.value = false
  }
}

const markRead = async (ids?: number[]) => {
  marking.value = true
  try {
    const payload = ids?.length ? { ids } : { mark_all: true }
    await axios.post('/api/portal/catalog/change-notifications/mark-read', payload)
    await fetchNotifications()
    refreshCatalogBadge?.()
    showToast(ids?.length ? '已标记为已读' : '已全部标记为已读', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '操作失败', 'error')
  } finally {
    marking.value = false
  }
}

const openProduct = (productKey: string) => {
  router.push({ name: 'CatalogDetail', params: { key: productKey }, query: { tab: 'changes' } })
}

const openResourceHistory = (resourceKey: string) => {
  router.push({ name: 'ResourceEdit', params: { key: resourceKey }, query: { tab: 'history' } })
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const goPage = (p: number) => {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  fetchNotifications()
}

onMounted(fetchNotifications)
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-6 space-y-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 class="text-xl font-bold text-gray-900">配置变更提醒</h1>
        <p class="text-sm text-gray-500 mt-1">
          关联 API 资源被他人修改或回滚时，会在此通知您（产品负责人）。
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          :disabled="marking || unread === 0"
          @click="markRead()"
        >
          全部已读
        </button>
        <button
          type="button"
          class="px-3 py-1.5 text-sm border rounded-lg"
          :class="unreadOnly ? 'bg-indigo-50 border-indigo-200 text-indigo-700' : 'border-gray-200 hover:bg-gray-50'"
          @click="unreadOnly = !unreadOnly; page = 1; fetchNotifications()"
        >
          {{ unreadOnly ? '显示全部' : `仅未读 (${unread})` }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="py-16 text-center text-gray-400 text-sm">加载中...</div>

    <div v-else-if="!notifications.length" class="bg-white rounded-lg border border-gray-200 p-12 text-center">
      <p class="text-gray-500 text-sm">暂无变更提醒</p>
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="item in notifications"
        :key="item.id"
        class="bg-white rounded-lg border p-4 transition-colors"
        :class="item.is_read ? 'border-gray-100' : 'border-indigo-200 bg-indigo-50/30'"
      >
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div class="min-w-0 flex-1 space-y-1">
            <div class="flex flex-wrap items-center gap-2">
              <span v-if="!item.is_read" class="w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
              <span class="font-medium text-gray-900 truncate">{{ item.product_display_name }}</span>
              <span class="text-xs px-2 py-0.5 rounded-full" :class="actionClass(item.action_type)">
                {{ actionLabel(item.action_type) }}
              </span>
            </div>
            <p class="text-sm text-gray-600">
              API
              <button
                type="button"
                class="text-indigo-600 hover:underline font-mono"
                @click="openResourceHistory(item.resource_key)"
              >
                {{ item.resource_name || item.resource_key }}
              </button>
              发生配置变更
            </p>
            <p v-if="item.change_summary" class="text-sm text-gray-500">
              变更项：{{ item.change_summary }}
            </p>
            <p class="text-xs text-gray-400">
              {{ item.operator_name ? `${item.operator_name} · ` : '' }}{{ item.created_at }}
            </p>
          </div>
          <div class="flex flex-col gap-2 shrink-0">
            <button
              type="button"
              class="px-3 py-1.5 text-sm text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50"
              @click="openProduct(item.product_key)"
            >
              查看产品
            </button>
            <button
              v-if="!item.is_read"
              type="button"
              class="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              :disabled="marking"
              @click="markRead([item.id])"
            >
              标记已读
            </button>
          </div>
        </div>
      </div>

      <div v-if="totalPages > 1" class="flex items-center justify-center gap-3 pt-2 text-sm text-gray-500">
        <button
          type="button"
          class="px-2 py-1 border rounded disabled:opacity-40"
          :disabled="page <= 1"
          @click="goPage(page - 1)"
        >
          上一页
        </button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button
          type="button"
          class="px-2 py-1 border rounded disabled:opacity-40"
          :disabled="page >= totalPages"
          @click="goPage(page + 1)"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>
