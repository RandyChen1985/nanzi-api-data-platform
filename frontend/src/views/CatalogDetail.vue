<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from '@/utils/axios'
import { buildPlaygroundRoute } from '@/utils/playground'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useToast } from '@/composables/useToast'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import CatalogProductName from '@/components/catalog/CatalogProductName.vue'
import CatalogLinkedResourceChanges from '@/components/catalog/CatalogLinkedResourceChanges.vue'
import { renderMarkdown } from '@/utils/markdown'
import { toFeaturedBool, catalogShelfStatus } from '@/utils/catalog'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const { showToast } = useToast()

const route = useRoute()
const router = useRouter()
const productKey = computed(() => route.params.key as string)
const introHtml = computed(() => {
  const text = product.value?.description || product.value?.summary
  if (!text) return ''
  return renderMarkdown(text)
})
const loading = ref(true)
const product = ref<any>(null)
const accessHolders = ref<any[]>([])
const isAdmin = ref(false)
const requestMessage = ref('')
const requesting = ref(false)
const syncingAccess = ref(false)
const revokingUserId = ref<number | null>(null)
const activeTab = ref<'intro' | 'fields' | 'example' | 'stats' | 'changes' | 'access'>('intro')
const exampleTab = ref<'resource' | 'query'>('resource')
const selectedResourceKey = ref<string | null>(null)
const showUnpublishModal = ref(false)
const unpublishPreview = ref({ count: 0, holders: [] as any[] })
const unpublishRevoke = ref(false)
const unpublishing = ref(false)
const publishing = ref(false)
const confirmDialog = ref({
  show: false,
  title: '',
  message: '',
  type: 'warning' as 'danger' | 'warning' | 'info',
  confirmText: '确认',
  onConfirm: () => {},
})
let accessPollTimer: ReturnType<typeof setInterval> | null = null
let accessPollAttempts = 0

const fetchAccessHolders = async () => {
  if (!product.value?.can_manage_access) return
  try {
    const res = await axios.get(`/api/portal/catalog/products/${encodeURIComponent(productKey.value)}/access-holders`)
    accessHolders.value = res.data.holders || []
  } catch {
    accessHolders.value = []
  }
}

const fetchProduct = async () => {
  loading.value = true
  try {
    const res = await axios.get(`/api/portal/catalog/products/${productKey.value}`)
    product.value = res.data
    if (!selectedResourceKey.value && res.data.resources?.length) {
      const primary = res.data.resources.find((r: any) => r.is_primary) || res.data.resources[0]
      selectedResourceKey.value = primary.resource_key
    }
    if (res.data.can_manage_access) {
      await fetchAccessHolders()
    }
    setupAccessPoll()
  } catch {
    product.value = null
  } finally {
    loading.value = false
  }
}

const setupAccessPoll = () => {
  if (accessPollTimer) {
    clearInterval(accessPollTimer)
    accessPollTimer = null
  }
  accessPollAttempts = 0
  const needsPoll =
    product.value &&
    !product.value.has_access &&
    (product.value.access_request_status === 'approved' || product.value.access_request_status === 'pending')
  if (!needsPoll) return
  accessPollTimer = setInterval(async () => {
    accessPollAttempts += 1
    if (accessPollAttempts > 10) {
      if (accessPollTimer) clearInterval(accessPollTimer)
      return
    }
    try {
      const res = await axios.get(`/api/portal/catalog/products/${productKey.value}`)
      product.value = res.data
      if (res.data.has_access && accessPollTimer) {
        clearInterval(accessPollTimer)
        accessPollTimer = null
      }
    } catch { /* ignore */ }
  }, 3000)
}

const selectedResource = computed(() => {
  const list = product.value?.resources || []
  if (!list.length) return null
  return list.find((r: any) => r.resource_key === selectedResourceKey.value) || list[0]
})

const primaryResource = computed(() => product.value?.resources?.find((r: any) => r.is_primary) || product.value?.resources?.[0])

const linkedResourcesForChanges = computed(() =>
  (product.value?.resources || []).map((r: any) => ({
    resource_key: r.resource_key,
    resource_name: r.resource_name,
    is_primary: !!r.is_primary,
  })),
)

const accessBadge = computed(() => {
  const p = product.value
  if (!p) return { text: '', class: '' }
  if (p.has_access) return { text: '已授权', class: 'bg-green-100 text-green-700' }
  const st = p.access_request_status
  if (st === 'pending') return { text: '申请审批中', class: 'bg-amber-100 text-amber-700' }
  if (st === 'approved') return { text: '已通过，待同步', class: 'bg-green-100 text-green-700' }
  if (st === 'rejected') return { text: '申请已拒绝', class: 'bg-gray-100 text-gray-600' }
  if (st === 'revoked') return { text: '权限已收回', class: 'bg-red-100 text-red-700' }
  return { text: '需申请权限', class: 'bg-amber-100 text-amber-700' }
})

const shelfStatusBadge = computed(() => catalogShelfStatus(product.value?.status))

const playgroundRouteFor = (r: { resource_key: string; resource_group?: string }) =>
  buildPlaygroundRoute({ resource_key: r.resource_key, resource_group: r.resource_group })

const playgroundRoute = computed(() => {
  const r = selectedResource.value || primaryResource.value
  if (!r?.resource_key) return null
  return playgroundRouteFor(r)
})

const exampleCode = computed(() => {
  const r = selectedResource.value || primaryResource.value
  if (!r) return ''
  const host = window.location.origin
  if (exampleTab.value === 'resource') {
    return `curl -X GET "${host}/api/v1/resources/${r.resource_key}?page=1&page_size=10" \\
  -H "X-API-Key: YOUR_API_KEY"`
  }
  return `curl -X POST "${host}/api/v1/query" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "resource": "${r.resource_key}",
    "page": 1,
    "page_size": 10
  }'`
})

const trendOption = computed(() => {
  const trend = product.value?.calls_trend || []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: trend.map((t: any) => t.date) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'line', data: trend.map((t: any) => t.calls), smooth: true, areaStyle: { opacity: 0.1 }, itemStyle: { color: '#4f46e5' } }],
  }
})

const copyCode = async () => {
  await navigator.clipboard.writeText(exampleCode.value)
}

const openUnpublishModal = async () => {
  try {
    const res = await axios.get(
      `/api/portal/catalog/products/${encodeURIComponent(productKey.value)}/unpublish-preview`,
    )
    unpublishPreview.value = res.data
    unpublishRevoke.value = false
    showUnpublishModal.value = true
  } catch {
    showToast('无法获取下架预览信息', 'error')
  }
}

const confirmUnpublish = async () => {
  unpublishing.value = true
  try {
    await axios.post(`/api/portal/catalog/products/${encodeURIComponent(productKey.value)}/unpublish`, {
      revoke_permissions: unpublishRevoke.value,
    })
    showUnpublishModal.value = false
    showToast('已从目录下架', 'success')
    await fetchProduct()
  } catch {
    showToast('下架失败，请确认您是管理员', 'error')
  } finally {
    unpublishing.value = false
  }
}

const publishProduct = async () => {
  publishing.value = true
  try {
    await axios.post(`/api/portal/catalog/products/${encodeURIComponent(productKey.value)}/publish`)
    showToast(product.value?.status === 0 ? '已发布上架' : '已重新上架', 'success')
    await fetchProduct()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '上架失败', 'error')
  } finally {
    publishing.value = false
  }
}

const submitAccessRequest = async () => {
  requesting.value = true
  try {
    await axios.post(`/api/portal/catalog/products/${encodeURIComponent(productKey.value)}/access-request`, {
      message: requestMessage.value || undefined,
    })
    await fetchProduct()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '申请失败', 'error')
  } finally {
    requesting.value = false
  }
}

const syncProductAccess = async () => {
  syncingAccess.value = true
  try {
    const res = await axios.post(
      `/api/portal/catalog/products/${encodeURIComponent(productKey.value)}/sync-access`,
    )
    await fetchProduct()
    if (res.data.has_access) {
      showToast('权限已生效，可以试用 API', 'success')
    } else {
      showToast(
        `已同步 ${res.data.granted_count}/${res.data.required_count} 个资源权限，如仍不可用请联系管理员`,
        'warning',
      )
    }
  } catch (e: any) {
    showToast(e.response?.data?.detail || '权限同步失败', 'error')
  } finally {
    syncingAccess.value = false
  }
}

const doRevokeUserAccess = async (userId: number) => {
  revokingUserId.value = userId
  try {
    await axios.post(`/api/portal/catalog/products/${encodeURIComponent(productKey.value)}/revoke-access`, {
      user_id: userId,
    })
    showToast('已收回访问权限', 'success')
    await fetchAccessHolders()
  } catch (e: any) {
    const detail = e.response?.data?.detail
    showToast(typeof detail === 'string' ? detail : '收回权限失败', 'error')
  } finally {
    revokingUserId.value = null
  }
}

const revokeUserAccess = (userId: number, userName: string) => {
  confirmDialog.value = {
    show: true,
    title: '收回权限',
    message: `确认收回用户「${userName}」对该产品的 API 访问权限？`,
    type: 'danger',
    confirmText: '收回',
    onConfirm: () => doRevokeUserAccess(userId),
  }
}

watch(productKey, () => {
  selectedResourceKey.value = null
  fetchProduct()
})

onMounted(() => {
  try {
    const u = localStorage.getItem('user_info')
    if (u) isAdmin.value = JSON.parse(u).role === 'admin'
  } catch { /* ignore */ }
  fetchProduct()
})

onUnmounted(() => {
  if (accessPollTimer) clearInterval(accessPollTimer)
})
</script>

<template>
  <div class="space-y-6">
    <button class="text-sm text-gray-500 hover:text-indigo-600 flex items-center gap-1" @click="router.push('/dashboard/catalog')">
      ← 返回目录
    </button>

    <div v-if="loading" class="text-center py-20 text-gray-400">加载中...</div>
    <div v-else-if="!product" class="text-center py-20 text-gray-400">产品不存在或未发布</div>
    <template v-else>
      <div class="group bg-white rounded-xl border border-gray-100 p-6">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div class="flex items-center gap-2 flex-wrap">
              <CatalogProductName :name="product.display_name" size="lg" />
              <span v-if="toFeaturedBool(product.featured)" class="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded-full font-medium">精选</span>
              <span class="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full">{{ product.domain }}</span>
              <span
                v-if="product.can_edit && shelfStatusBadge.text"
                :class="shelfStatusBadge.class"
                class="text-xs px-2 py-1 rounded-full font-medium"
              >
                {{ shelfStatusBadge.text }}
              </span>
              <span
                v-if="accessBadge.text"
                :class="accessBadge.class"
                class="text-xs px-2 py-1 rounded-full font-medium"
              >
                {{ accessBadge.text }}
              </span>
              <span v-if="(product.resources?.length || 0) > 1" class="text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded-full">
                {{ product.resources.length }} 个 API
              </span>
            </div>
            <p class="text-gray-600 mt-3">{{ product.summary }}</p>
            <div class="flex flex-wrap gap-4 mt-4 text-sm text-gray-500">
              <span v-if="product.owner_name">👤 {{ product.owner_name }}</span>
              <span v-if="product.data_source">数据源 {{ product.data_source }}</span>
              <span>{{ product.calls_7d }} 次/周</span>
              <span v-if="product.health_score != null">健康分 {{ product.health_score }}</span>
            </div>
          </div>
          <div class="flex gap-2 flex-wrap">
            <router-link
              v-if="product.can_edit"
              :to="`/dashboard/catalog/${productKey}/edit`"
              class="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium hover:bg-gray-50"
            >
              编辑产品
            </router-link>
            <router-link
              v-if="product.has_access && playgroundRoute"
              :to="playgroundRoute"
              class="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
            >
              在线试用
            </router-link>
            <template v-else-if="product.access_request_status === 'pending'">
              <span class="px-4 py-2 bg-amber-50 text-amber-700 rounded-lg text-sm font-medium">申请审批中</span>
            </template>
            <template v-else-if="product.access_request_status === 'approved' && !product.has_access">
              <button
                type="button"
                class="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                :disabled="syncingAccess"
                @click="syncProductAccess"
              >
                {{ syncingAccess ? '同步中...' : '刷新权限' }}
              </button>
            </template>
            <template v-else-if="product.access_request_status === 'approved' && product.has_access">
              <router-link
                v-if="playgroundRoute"
                :to="playgroundRoute"
                class="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
              >
                在线试用
              </router-link>
            </template>
            <template v-else-if="product.access_request_status === 'rejected' || product.access_request_status === 'revoked'">
              <button
                type="button"
                class="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
                :disabled="requesting"
                @click="submitAccessRequest"
              >
                重新申请
              </button>
            </template>
            <button
              v-else-if="!product.has_access"
              type="button"
              class="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
              :disabled="requesting"
              @click="submitAccessRequest"
            >
              {{ requesting ? '提交中...' : '申请访问' }}
            </button>
            <button
              v-if="isAdmin && product.status === 1"
              type="button"
              class="px-4 py-2 border border-amber-300 text-amber-700 rounded-lg text-sm font-medium hover:bg-amber-50"
              @click="openUnpublishModal"
            >
              从目录下架
            </button>
            <button
              v-if="isAdmin && (product.status === 2 || product.status === 0)"
              type="button"
              class="px-4 py-2 border border-green-300 text-green-700 rounded-lg text-sm font-medium hover:bg-green-50 disabled:opacity-50"
              :disabled="publishing"
              @click="publishProduct"
            >
              {{ publishing ? '上架中...' : (product.status === 0 ? '发布上架' : '重新上架') }}
            </button>
          </div>
        </div>
      </div>

      <div class="border-b border-gray-200">
        <nav class="flex gap-6 flex-wrap">
          <button
            v-for="tab in [
              { id: 'intro', label: '产品介绍' },
              { id: 'fields', label: '字段说明' },
              { id: 'example', label: '调用示例' },
              { id: 'stats', label: '使用情况' },
              { id: 'changes', label: '配置变更' },
              ...(product.can_manage_access ? [{ id: 'access', label: '访问权限' }] : []),
            ]"
            :key="tab.id"
            :class="activeTab === tab.id ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500'"
            class="py-3 border-b-2 text-sm font-medium"
            @click="activeTab = tab.id as any"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>

      <div class="bg-white rounded-xl border border-gray-100 p-6 min-h-[300px]">
        <div v-if="activeTab === 'intro'">
          <div
            v-if="introHtml"
            class="markdown-body prose prose-sm max-w-none text-gray-700 break-words"
            v-html="introHtml"
          />
          <p v-else class="text-sm text-gray-500">暂无详细介绍</p>
          <div v-if="product.resources?.length" class="mt-6">
            <h3 class="text-sm font-semibold text-gray-700 mb-3">关联 API 资源</h3>
            <div class="space-y-2">
              <div
                v-for="r in product.resources"
                :key="r.resource_key"
                class="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-50 rounded-lg text-sm"
              >
                <div>
                  <span class="font-mono text-xs text-gray-800">{{ r.resource_key }}</span>
                  <span v-if="r.resource_name" class="text-gray-500 ml-2">{{ r.resource_name }}</span>
                  <span v-if="r.is_primary" class="ml-2 text-[10px] bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded">主资源</span>
                </div>
                <router-link
                  v-if="product.has_access"
                  :to="playgroundRouteFor(r)!"
                  class="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                >
                  试用 →
                </router-link>
              </div>
            </div>
          </div>
          <div v-if="product.dataset_name" class="mt-6 p-4 bg-blue-50 rounded-lg text-sm text-blue-800">
            关联语义数据集：<strong>{{ product.dataset_name }}</strong>
          </div>
        </div>

        <div v-if="activeTab === 'fields'">
          <div v-if="(product.resources?.length || 0) > 1" class="flex flex-wrap gap-2 mb-4">
            <button
              v-for="r in product.resources"
              :key="r.resource_key"
              :class="selectedResourceKey === r.resource_key ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-600'"
              class="px-3 py-1 rounded-full text-xs font-medium"
              @click="selectedResourceKey = r.resource_key"
            >
              {{ r.resource_name || r.resource_key }}
            </button>
          </div>
          <template v-if="selectedResource">
            <table class="min-w-full text-sm">
              <thead>
                <tr class="border-b text-left text-gray-500">
                  <th class="py-2 pr-4">字段</th>
                  <th class="py-2 pr-4">中文名</th>
                  <th class="py-2">类型</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in selectedResource.fields_config" :key="f.name" class="border-b border-gray-50">
                  <td class="py-2 pr-4 font-mono text-xs">{{ f.name }}</td>
                  <td class="py-2 pr-4">{{ f.label }}</td>
                  <td class="py-2 text-gray-500">{{ f.type }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!selectedResource.fields_config?.length" class="text-gray-400">暂无字段配置</p>
          </template>
        </div>

        <div v-if="activeTab === 'example'">
          <div v-if="(product.resources?.length || 0) > 1" class="flex flex-wrap gap-2 mb-4">
            <button
              v-for="r in product.resources"
              :key="r.resource_key"
              :class="selectedResourceKey === r.resource_key ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-600'"
              class="px-3 py-1 rounded-full text-xs font-medium"
              @click="selectedResourceKey = r.resource_key"
            >
              {{ r.resource_name || r.resource_key }}
            </button>
          </div>
          <div class="flex gap-4 mb-4 border-b">
            <button :class="exampleTab === 'resource' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'" class="pb-2 text-sm" @click="exampleTab = 'resource'">资源直连接口</button>
            <button :class="exampleTab === 'query' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'" class="pb-2 text-sm" @click="exampleTab = 'query'">通用 Query 接口</button>
          </div>
          <div class="relative">
            <pre class="bg-gray-900 text-green-400 p-4 rounded-lg text-xs overflow-x-auto">{{ exampleCode }}</pre>
            <button class="absolute top-2 right-2 text-xs bg-gray-700 text-white px-2 py-1 rounded" @click="copyCode">复制</button>
          </div>
        </div>

        <div v-if="activeTab === 'stats'">
          <p class="text-sm text-gray-500 mb-4">近 7 天调用趋势（全平台）</p>
          <VChart v-if="product.calls_trend?.length" :option="trendOption" style="height: 240px" autoresize />
          <p v-else class="text-gray-400 text-sm">暂无调用数据</p>
        </div>

        <div v-if="activeTab === 'changes'">
          <CatalogLinkedResourceChanges
            :product-key="productKey"
            :linked-resources="linkedResourcesForChanges"
            readonly
          />
        </div>

        <div v-if="activeTab === 'access'">
          <p class="text-sm text-gray-500 mb-4">通过审批获得该产品 API 访问权限的用户（{{ accessHolders.length }} 人）</p>
          <div v-if="!accessHolders.length" class="text-gray-400 text-sm">暂无授权用户</div>
          <div v-else class="space-y-2">
            <div
              v-for="h in accessHolders"
              :key="h.user_id"
              class="flex items-center justify-between p-3 bg-gray-50 rounded-lg text-sm"
            >
              <div>
                <strong>{{ h.user_name }}</strong>
                <span v-if="h.remark" class="text-gray-400 ml-2">{{ h.remark }}</span>
                <span class="text-gray-400 ml-2">已授权 {{ h.granted_resources }} 个资源</span>
              </div>
              <button
                :disabled="revokingUserId === h.user_id"
                class="text-xs text-red-600 hover:text-red-800 border border-red-200 px-2 py-1 rounded disabled:opacity-50"
                @click="revokeUserAccess(h.user_id, h.user_name)"
              >
                收回权限
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-if="showUnpublishModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
        <h3 class="text-lg font-bold text-gray-900">确认下架</h3>
        <p class="text-sm text-gray-600">
          下架后业务方将无法在目录中看到「{{ product?.display_name }}」。
        </p>
        <p v-if="unpublishPreview.count > 0" class="text-sm text-amber-700 bg-amber-50 rounded-lg p-3">
          仍有 <strong>{{ unpublishPreview.count }}</strong> 个用户持有该产品的 API 访问权限。
        </p>
        <label v-if="unpublishPreview.count > 0" class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input v-model="unpublishRevoke" type="checkbox" class="rounded border-gray-300" />
          同时收回全部用户权限
        </label>
        <div class="flex justify-end gap-2 pt-2">
          <button class="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50" @click="showUnpublishModal = false">
            取消
          </button>
          <button
            :disabled="unpublishing"
            class="px-4 py-2 text-sm bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
            @click="confirmUnpublish"
          >
            {{ unpublishing ? '下架中...' : '确认下架' }}
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :show="confirmDialog.show"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :type="confirmDialog.type"
      :confirm-text="confirmDialog.confirmText"
      @confirm="confirmDialog.onConfirm(); confirmDialog.show = false"
      @cancel="confirmDialog.show = false"
    />
  </div>
</template>
