<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from '@/utils/axios'
import { buildPlaygroundRoute } from '@/utils/playground'
import { useToast } from '@/composables/useToast'
import CatalogProductRow from '@/components/catalog/CatalogProductRow.vue'
import CatalogFeaturedCard from '@/components/catalog/CatalogFeaturedCard.vue'

const { showToast } = useToast()

interface Product {
  id: number
  product_key: string
  display_name: string
  summary?: string
  domain: string
  tags: string[]
  status: number
  owner_name?: string
  primary_resource_key?: string
  resource_group?: string
  data_source?: string
  resource_mode?: string
  health_score?: number
  calls_7d: number
  has_access: boolean
  featured: boolean
  pending_requests?: number
  published_at?: string
}

const router = useRouter()
const loading = ref(false)
const products = ref<Product[]>([])
const totalProducts = ref(0)
const page = ref(1)
const pageSize = ref(24)
const domains = ref<{ domain: string; count: number }[]>([])
const sections = ref<{ hot: Product[]; newest: Product[]; featured: Product[] }>({
  hot: [],
  newest: [],
  featured: [],
})
const mineSummary = ref({ owned_products: 0, pending_review: 0 })

const searchQuery = ref('')
const activeDomain = ref('ALL')
const sortBy = ref('calls')
const viewTab = ref<'all' | 'mine'>('all')
const accessFilter = ref<'all' | 'yes' | 'no'>('all')
const exporting = ref(false)
const redundantCount = ref(0)

const canManageCatalog = computed(() => {
  try {
    const u = JSON.parse(localStorage.getItem('user_info') || '{}')
    if (u.role === 'admin') return true
    return (u.permissions?.elements || []).includes('element:catalog:manage')
  } catch {
    return false
  }
})

const showRedundantBanner = computed(
  () => redundantCount.value > 0 && (canManageCatalog.value || mineSummary.value.owned_products > 0),
)

const fetchRedundantCount = async () => {
  try {
    const res = await axios.get('/api/portal/catalog/products/redundant')
    redundantCount.value = res.data.length
  } catch {
    redundantCount.value = 0
  }
}

const isAdmin = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('user_info') || '{}').role === 'admin'
  } catch {
    return false
  }
})

const canExport = computed(() => {
  try {
    const u = JSON.parse(localStorage.getItem('user_info') || '{}')
    if (u.role === 'admin') return true
    const menus = u.permissions?.menus || []
    const elems = u.permissions?.elements || []
    return menus.includes('menu:asset-panorama') || elems.includes('element:catalog:manage')
  } catch {
    return false
  }
})

const showMineTab = computed(() => mineSummary.value.owned_products > 0 || isAdmin.value)

const canAccessRequests = computed(
  () => sessionStorage.getItem('catalog_can_access_requests') === '1',
)

const fetchData = async () => {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      q: searchQuery.value || undefined,
      domain: activeDomain.value === 'ALL' ? undefined : activeDomain.value,
      sort: viewTab.value === 'mine' ? (sortBy.value === 'calls' ? 'pending' : sortBy.value) : sortBy.value,
      mine_only: viewTab.value === 'mine',
      only_accessible: accessFilter.value === 'yes',
      only_no_access: accessFilter.value === 'no',
      page: page.value,
      page_size: pageSize.value,
    }
    const [listRes, summaryRes, domainRes, sectionRes] = await Promise.all([
      axios.get<{ items: Product[]; total: number; page: number; page_size: number }>(
        '/api/portal/catalog/products',
        { params },
      ),
      axios.get<{ owned_products: number; pending_review: number }>('/api/portal/catalog/products/mine-summary'),
      viewTab.value === 'all'
        ? axios.get<{ domain: string; count: number }[]>('/api/portal/catalog/domains')
        : Promise.resolve(null),
      viewTab.value === 'all'
        ? axios.get<{ hot: Product[]; newest: Product[]; featured: Product[] }>('/api/portal/catalog/products/sections')
        : Promise.resolve(null),
    ])
    products.value = listRes.data.items
    totalProducts.value = listRes.data.total
    page.value = listRes.data.page
    mineSummary.value = summaryRes.data
    if (domainRes) domains.value = domainRes.data
    if (sectionRes) sections.value = sectionRes.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const openDetail = (key: string) => {
  router.push(`/dashboard/catalog/${key}`)
}

const playgroundRoute = (p: Product) => {
  const key = p.primary_resource_key || p.product_key
  if (!key) return null
  return buildPlaygroundRoute({ resource_key: key, resource_group: p.resource_group })
}

const formatCalls = (n: number) => {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

const statusLabel = (s: number) => {
  if (s === 1) return '已上架'
  if (s === 0) return '草稿'
  if (s === 2) return '已下线'
  return '未知'
}

const statusClass = (s: number) => {
  if (s === 1) return 'bg-green-100 text-green-700'
  if (s === 0) return 'bg-gray-100 text-gray-600'
  return 'bg-amber-100 text-amber-700'
}

const exportCatalog = async () => {
  exporting.value = true
  try {
    const res = await axios.get('/api/portal/catalog/products/export', { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `catalog_products_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    showToast('导出失败，请确认您有导出权限', 'error')
  } finally {
    exporting.value = false
  }
}

const showSections = computed(
  () => viewTab.value === 'all' && !searchQuery.value && activeDomain.value === 'ALL' && accessFilter.value === 'all'
)

const resetPageAndFetch = () => {
  page.value = 1
  fetchData()
}

const totalPages = computed(() => Math.max(1, Math.ceil(totalProducts.value / pageSize.value)))

const goPage = (p: number) => {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  fetchData()
}

onMounted(async () => {
  await fetchData()
  await fetchRedundantCount()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">数据产品目录</h1>
        <p class="text-sm text-gray-500 mt-1">浏览、发现与试用已发布的数据 API 产品</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          v-if="canExport"
          :disabled="exporting"
          class="text-sm border border-gray-200 px-3 py-1.5 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          @click="exportCatalog"
        >
          {{ exporting ? '导出中...' : '导出清单' }}
        </button>
        <router-link
          to="/dashboard/asset-panorama"
          class="inline-flex items-center text-sm text-indigo-600 hover:text-indigo-800 font-medium"
        >
          查看资产全景 →
        </router-link>
      </div>
    </div>

    <div
      v-if="showRedundantBanner"
      class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <span>检测到 <strong>{{ redundantCount }}</strong> 个因 API 合并产生的冗余产品，建议清理以免目录重复展示。</span>
      <router-link
        to="/dashboard/catalog-redundant"
        class="font-medium text-amber-800 hover:text-amber-950 whitespace-nowrap"
      >
        去清理 →
      </router-link>
    </div>

    <!-- View tabs -->
    <div class="flex gap-2 border-b border-gray-200">
      <button
        :class="viewTab === 'all' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500'"
        class="px-4 py-2 border-b-2 text-sm font-medium"
        @click="viewTab = 'all'; resetPageAndFetch()"
      >
        全部产品
      </button>
      <button
        v-if="showMineTab"
        :class="viewTab === 'mine' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500'"
        class="px-4 py-2 border-b-2 text-sm font-medium flex items-center gap-2"
        @click="viewTab = 'mine'; resetPageAndFetch()"
      >
        我的产品
        <span v-if="mineSummary.pending_review" class="text-[10px] bg-red-500 text-white px-1.5 py-0.5 rounded-full">
          {{ mineSummary.pending_review }}
        </span>
      </button>
      <router-link
        v-if="canAccessRequests && mineSummary.pending_review > 0"
        to="/dashboard/catalog-requests"
        class="ml-auto text-sm text-amber-600 hover:text-amber-800 self-center"
      >
        {{ mineSummary.pending_review }} 条待审批 →
      </router-link>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 space-y-4">
      <div class="flex flex-col md:flex-row gap-3">
        <div class="relative flex-1">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索产品名称、关键词、业务域..."
            class="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            @keyup.enter="resetPageAndFetch"
          />
          <svg class="absolute left-3 top-2.5 h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <select v-model="sortBy" class="border border-gray-200 rounded-lg px-3 py-2.5 text-sm" @change="resetPageAndFetch">
          <option v-if="viewTab === 'mine'" value="pending">按待审批</option>
          <option value="calls">按调用量</option>
          <option value="newest">按上架时间</option>
          <option value="name">按名称</option>
        </select>
        <button
          class="px-4 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
          @click="resetPageAndFetch"
        >
          搜索
        </button>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <template v-if="viewTab === 'all'">
          <button
            :class="activeDomain === 'ALL' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            class="px-3 py-1 rounded-full text-xs font-medium transition-colors"
            @click="activeDomain = 'ALL'; resetPageAndFetch()"
          >
            全部
          </button>
          <button
            v-for="d in domains"
            :key="d.domain"
            :class="activeDomain === d.domain ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
            class="px-3 py-1 rounded-full text-xs font-medium transition-colors"
            @click="activeDomain = d.domain; resetPageAndFetch()"
          >
            {{ d.domain }} ({{ d.count }})
          </button>
        </template>
        <div class="ml-auto flex items-center gap-1 text-xs">
          <span class="text-gray-400 mr-1">权限:</span>
          <button
            v-for="opt in [{ v: 'all', l: '全部' }, { v: 'yes', l: '有权限' }, { v: 'no', l: '无权限' }]"
            :key="opt.v"
            :class="accessFilter === opt.v ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-500'"
            class="px-2.5 py-1 rounded-full font-medium"
            @click="accessFilter = opt.v as any; resetPageAndFetch()"
          >
            {{ opt.l }}
          </button>
        </div>
      </div>
    </div>

    <!-- Featured sections -->
    <div v-if="showSections && !loading" class="space-y-6">
      <div v-if="sections.featured.length">
        <h2 class="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">精选推荐</h2>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          <CatalogFeaturedCard
            v-for="p in sections.featured.slice(0, 3)"
            :key="p.product_key"
            :product="p"
            :playground-route="playgroundRoute(p)"
            :format-calls="formatCalls(p.calls_7d)"
            class="cursor-pointer"
            @open="openDetail(p.product_key)"
          />
        </div>
      </div>
    </div>

    <!-- Product list -->
    <div v-if="loading" class="text-center py-16 text-gray-400">加载中...</div>
    <div v-else-if="products.length === 0" class="text-center py-16 text-gray-400">
      <template v-if="viewTab === 'mine'">您暂未负责任何数据产品</template>
      <template v-else>暂无已发布的数据产品。管理员可在「接口管理」中发布资源到目录。</template>
    </div>
    <div v-else class="space-y-3">
      <p class="text-sm text-gray-500">共 {{ totalProducts }} 个产品</p>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div
          v-for="p in products"
          :key="p.product_key"
          class="bg-white rounded-xl border border-gray-100 p-5 hover:border-indigo-200 hover:shadow-sm transition-all h-full"
        >
          <CatalogProductRow
            variant="card"
            :product="p"
            :view-tab="viewTab"
            :status-label="statusLabel(p.status)"
            :status-class="statusClass(p.status)"
            :playground-route="playgroundRoute(p)"
            :format-calls="formatCalls(p.calls_7d)"
            @open="openDetail(p.product_key)"
            @edit="router.push(`/dashboard/catalog/${p.product_key}/edit`)"
          />
        </div>
      </div>
      <div v-if="totalPages > 1" class="flex items-center justify-center gap-3 pt-4">
        <button
          :disabled="page <= 1"
          class="px-3 py-1.5 text-sm border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50"
          @click="goPage(page - 1)"
        >
          上一页
        </button>
        <span class="text-sm text-gray-500">{{ page }} / {{ totalPages }}</span>
        <button
          :disabled="page >= totalPages"
          class="px-3 py-1.5 text-sm border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50"
          @click="goPage(page + 1)"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>
