<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import axios from '@/utils/axios'
import Toast from '@/components/Toast.vue'
import ResourceGroupSidebar from '@/components/resources/ResourceGroupSidebar.vue'
import ResourceEmptyState from '@/components/resources/ResourceEmptyState.vue'
import ResourceRowActions from '@/components/resources/ResourceRowActions.vue'
import ResourceLogDrawer from '@/components/resources/ResourceLogDrawer.vue'
import ConfirmDeleteModal from '@/components/resources/ConfirmDeleteModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import type { Resource, AccessLog, ResourceSortField } from '@/types/resource'
import { CircleStackIcon, ShieldCheckIcon } from '@heroicons/vue/24/outline'
import { Codemirror } from 'vue-codemirror'
import { sql } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'

const router = useRouter()
const isSidebarCollapsed = ref(false)

const resources = ref<Resource[]>([])
const loading = ref(false)
const searchQuery = ref('')
const searchGroupQuery = ref('')
const statusFilter = ref<'ALL' | '1' | '0'>('ALL')
const activeTab = ref('ALL')
const onlyAuthorized = ref(false)
const importFile = ref<HTMLInputElement | null>(null)
const isAdmin = ref(false)
const userInfo = ref<Record<string, unknown> | null>(null)

const sortField = ref<ResourceSortField>('updated_at')
const sortDir = ref<'asc' | 'desc'>('desc')
const page = ref(1)
const pageSize = ref(20)

const selectedKeys = ref<Set<string>>(new Set())
const datasourcesMap = ref<Record<string, string>>({})

const extensions = [sql(), oneDark]

const checkIsAdmin = () => {
  try {
    const s = localStorage.getItem('user_info')
    if (s) {
      userInfo.value = JSON.parse(s)
      isAdmin.value = userInfo.value?.role === 'admin'
    }
  } catch {
    /* ignore */
  }
}

const hasPerm = (code: string) => {
  if (isAdmin.value) return true
  const perms = userInfo.value?.permissions as { elements?: string[] } | undefined
  return perms?.elements?.includes(code) ?? false
}

const toast = ref({ show: false, message: '', type: 'info' as 'success' | 'error' | 'warning' | 'info', key: 0 })
const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
  toast.value = { show: true, message, type, key: toast.value.key + 1 }
}
const closeToast = () => { toast.value.show = false }

const fetchResources = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/portal/meta/resources')
    resources.value = response.data
    page.value = 1
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

const groupTabs = computed(() => {
  const counts: Record<string, number> = {}
  resources.value.forEach((r) => {
    const g = r.resource_group || '默认分组'
    counts[g] = (counts[g] || 0) + 1
  })
  const tabs = Object.keys(counts).sort().map((g) => ({ name: g, label: g, count: counts[g] ?? 0 }))
  return [{ name: 'ALL', label: '全部资源', count: resources.value.length }, ...tabs]
})

const filteredGroupTabs = computed(() => {
  if (!searchGroupQuery.value) return groupTabs.value
  const q = searchGroupQuery.value.toLowerCase()
  return groupTabs.value.filter((t) => t.label.toLowerCase().includes(q))
})

const filteredResources = computed(() => {
  const q = searchQuery.value.toLowerCase()
  return resources.value.filter((r) => {
    const matchesSearch =
      !q ||
      r.resource_key.toLowerCase().includes(q) ||
      r.resource_name.toLowerCase().includes(q) ||
      (r.resource_group || '').toLowerCase().includes(q) ||
      (r.data_source || '').toLowerCase().includes(q) ||
      (r.remarks || '').toLowerCase().includes(q)

    const matchesStatus = statusFilter.value === 'ALL' || String(r.status) === statusFilter.value
    const groupName = r.resource_group || '默认分组'
    const matchesGroup = activeTab.value === 'ALL' || groupName === activeTab.value

    let matchesAuth = true
    if (onlyAuthorized.value && !isAdmin.value) {
      const userRes = (userInfo.value?.permissions as { resources?: string[] })?.resources || []
      matchesAuth = userRes.includes(r.resource_key)
    }
    return matchesSearch && matchesStatus && matchesGroup && matchesAuth
  })
})

const groupTotalCount = computed(() => {
  if (activeTab.value === 'ALL') return resources.value.length
  return resources.value.filter((r) => (r.resource_group || '默认分组') === activeTab.value).length
})

const sortedResources = computed(() => {
  const list = [...filteredResources.value]
  list.sort((a, b) => {
    let cmp = 0
    if (sortField.value === 'updated_at') {
      const ta = new Date(a.updated_at || a.created_at || 0).getTime()
      const tb = new Date(b.updated_at || b.created_at || 0).getTime()
      cmp = ta - tb
    } else if (sortField.value === 'resource_name') {
      cmp = a.resource_name.localeCompare(b.resource_name, 'zh-CN')
    } else if (sortField.value === 'status') {
      cmp = a.status - b.status
    } else if (sortField.value === 'resource_mode') {
      cmp = a.resource_mode.localeCompare(b.resource_mode)
    }
    return sortDir.value === 'asc' ? cmp : -cmp
  })
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(sortedResources.value.length / pageSize.value)))

const paginatedResources = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return sortedResources.value.slice(start, start + pageSize.value)
})

const allSelected = computed(
  () => paginatedResources.value.length > 0 && paginatedResources.value.every((r) => selectedKeys.value.has(r.resource_key))
)
const isIndeterminate = computed(() => {
  const n = paginatedResources.value.filter((r) => selectedKeys.value.has(r.resource_key)).length
  return n > 0 && n < paginatedResources.value.length
})

const emptyStateVariant = computed((): 'no-resources' | 'no-results' | 'no-permission' | null => {
  if (loading.value) return null
  if (resources.value.length === 0) return 'no-resources'
  if (filteredResources.value.length === 0) {
    if (onlyAuthorized.value && !isAdmin.value) return 'no-permission'
    return 'no-results'
  }
  return null
})

const hasActiveFilters = computed(
  () => !!searchQuery.value || statusFilter.value !== 'ALL' || (onlyAuthorized.value && !isAdmin.value)
)

const tableColSpan = computed(() => {
  let n = 7
  if (hasPerm('element:resource:edit') || hasPerm('element:resource:delete')) n += 1
  return n
})

const toggleSort = (field: ResourceSortField) => {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDir.value = field === 'updated_at' ? 'desc' : 'asc'
  }
}

const sortIndicator = (field: ResourceSortField) => {
  if (sortField.value !== field) return ''
  return sortDir.value === 'asc' ? ' ↑' : ' ↓'
}

const clearFilters = () => {
  searchQuery.value = ''
  statusFilter.value = 'ALL'
  onlyAuthorized.value = !isAdmin.value
  activeTab.value = 'ALL'
  page.value = 1
}

const toggleAll = () => {
  if (allSelected.value) {
    paginatedResources.value.forEach((r) => selectedKeys.value.delete(r.resource_key))
  } else {
    paginatedResources.value.forEach((r) => selectedKeys.value.add(r.resource_key))
  }
}

const toggleSelection = (key: string) => {
  if (selectedKeys.value.has(key)) selectedKeys.value.delete(key)
  else selectedKeys.value.add(key)
}

const navigateToResource = (res: Resource) => {
  if (res.resource_key === 'system.sql.execute') return
  router.push(`/dashboard/resources/${res.resource_key}`)
}

const modeLabel = (mode: string) => {
  if (mode === 'TABLE') return '表映射'
  if (mode === 'SQL') return '自定义 SQL'
  if (mode === 'SYSTEM') return '系统'
  return mode
}

// --- Confirm dialog (status change) ---
const confirmDialog = ref({
  show: false,
  title: '',
  message: '',
  type: 'warning' as 'danger' | 'warning' | 'info',
  confirmText: '确认',
  onConfirm: () => {},
})

const openConfirmDialog = (opts: {
  title: string
  message: string
  type?: 'danger' | 'warning' | 'info'
  confirmText?: string
  onConfirm: () => void
}) => {
  confirmDialog.value = {
    show: true,
    title: opts.title,
    message: opts.message,
    type: opts.type ?? 'warning',
    confirmText: opts.confirmText ?? '确认',
    onConfirm: opts.onConfirm,
  }
}

const handleConfirmDialog = () => {
  confirmDialog.value.onConfirm()
  confirmDialog.value.show = false
}

// --- Delete modals ---
const showDeleteModal = ref(false)
const deleteModalKeys = ref<string[]>([])
const deleteLoading = ref(false)

const openDeleteModal = (keys: string[]) => {
  deleteModalKeys.value = keys
  showDeleteModal.value = true
}

const confirmDeleteResource = (key: string) => openDeleteModal([key])
const confirmBatchDelete = () => openDeleteModal(Array.from(selectedKeys.value))

const executeDelete = async () => {
  deleteLoading.value = true
  let successCount = 0
  const keys = [...deleteModalKeys.value]
  for (const key of keys) {
    try {
      await axios.delete(`/api/portal/meta/resources/${key}`)
      successCount++
    } catch {
      /* continue */
    }
  }
  showToast(`删除完成：成功 ${successCount}，失败 ${keys.length - successCount}`, successCount > 0 ? 'success' : 'warning')
  selectedKeys.value.clear()
  showDeleteModal.value = false
  deleteModalKeys.value = []
  deleteLoading.value = false
  fetchResources()
}

const batchUpdateStatus = async (status: number) => {
  if (selectedKeys.value.size === 0) return
  loading.value = true
  let successCount = 0
  const keys = Array.from(selectedKeys.value)
  for (const key of keys) {
    try {
      await axios.put(`/api/portal/meta/resources/${key}`, { status })
      successCount++
    } catch {
      /* continue */
    }
  }
  showToast(`批量更新：成功 ${successCount}，失败 ${keys.length - successCount}`, successCount > 0 ? 'success' : 'warning')
  selectedKeys.value.clear()
  fetchResources()
}

const requestBatchDisable = () => {
  if (selectedKeys.value.size === 0) return
  openConfirmDialog({
    title: `确认禁用 ${selectedKeys.value.size} 个资源？`,
    message: '禁用后这些资源的对外 API 将不可用。',
    type: 'warning',
    confirmText: '确认禁用',
    onConfirm: () => batchUpdateStatus(0),
  })
}

const applyStatusChange = async (resource: Resource, newStatus: number) => {
  const original = resource.status
  resource.status = newStatus
  try {
    await axios.put(`/api/portal/meta/resources/${resource.resource_key}`, { status: newStatus })
    showToast(`资源已${newStatus === 1 ? '启用' : '禁用'}`, 'success')
  } catch (e: unknown) {
    resource.status = original
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '状态更新失败', 'error')
  }
}

const toggleStatus = (resource: Resource) => {
  if (resource.resource_mode === 'SYSTEM' || !hasPerm('element:resource:edit')) return
  const newStatus = resource.status === 1 ? 0 : 1
  if (newStatus === 0) {
    openConfirmDialog({
      title: '确认禁用资源？',
      message: `禁用后「${resource.resource_name}」对外 API 将不可用。`,
      type: 'warning',
      confirmText: '确认禁用',
      onConfirm: () => applyStatusChange(resource, 0),
    })
    return
  }
  applyStatusChange(resource, 1)
}

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  const dateInput = dateStr.replace(' ', 'T')
  return new Date(dateInput).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

const fetchDatasources = async () => {
  try {
    const response = await axios.get('/api/portal/datasource/datasources?status=active')
    const map: Record<string, string> = {}
    response.data.forEach((ds: { source_name: string; description?: string }) => {
      map[ds.source_name] = ds.description || '无描述'
    })
    datasourcesMap.value = map
  } catch {
    /* ignore */
  }
}

const exportResource = (res: Resource) => {
  const dataStr = JSON.stringify(res, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${res.resource_key}_config.json`
  link.click()
  URL.revokeObjectURL(url)
  showToast('导出成功', 'success')
}

const copyApiUrl = (key: string, type: 'resource' | 'query') => {
  const origin = window.location.origin
  const url = type === 'resource' ? `${origin}/api/v1/resources/${key}` : `${origin}/api/v1/query`
  navigator.clipboard.writeText(url)
  showToast(type === 'resource' ? '资源接口 URL 已复制' : '通用 Query URL 已复制', 'success')
}

const handleImport = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const json = JSON.parse(e.target?.result as string)
      router.push({ path: '/dashboard/resources/create', state: { importedData: json } })
    } catch {
      showToast('文件解析失败，请确保是有效的 JSON', 'error')
    }
  }
  reader.readAsText(input.files[0]!)
  input.value = ''
}

// SQL preview
const showSqlPreviewModal = ref(false)
const previewSqlContent = ref('')
const openSqlPreview = (sqlContent: string) => {
  previewSqlContent.value = sqlContent || '-- 无自定义 SQL'
  showSqlPreviewModal.value = true
}

// Logs drawer
const showLogDrawer = ref(false)
const currentLogResource = ref('')
const accessLogs = ref<AccessLog[]>([])
const loadingLogs = ref(false)
const selectedLog = ref<AccessLog | null>(null)

const openLogDrawer = async (resourceKey: string) => {
  currentLogResource.value = resourceKey
  showLogDrawer.value = true
  selectedLog.value = null
  await fetchAccessLogs(resourceKey)
}

const fetchAccessLogs = async (resourceKey: string) => {
  loadingLogs.value = true
  try {
    const response = await axios.get('/api/portal/logs/access', { params: { resource_key: resourceKey, limit: 50 } })
    accessLogs.value = response.data
  } catch {
    showToast('获取日志失败', 'error')
  } finally {
    loadingLogs.value = false
  }
}

// SQL test / TTL modals (system.sql.execute)
const showSqlTestModal = ref(false)
const showTtlModal = ref(false)
const editingTtl = ref(30)
const loadingTtl = ref(false)
const testSqlForm = reactive({ dataSource: '', sql: 'SELECT 1', cacheTtl: 30 })
const testResult = ref('')
const loadingTest = ref(false)
const showCodeModal = ref(false)
const codeSnippet = ref('')
const codeLanguage = ref('bash')

const openTtlModal = (res: Resource) => {
  editingTtl.value = res.cache_ttl || 30
  showTtlModal.value = true
}

const saveTtl = async () => {
  loadingTtl.value = true
  try {
    await axios.put('/api/portal/meta/resources/system.sql.execute', { cache_ttl: editingTtl.value })
    showToast('缓存时间设置成功', 'success')
    showTtlModal.value = false
    fetchResources()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '保存失败', 'error')
  } finally {
    loadingTtl.value = false
  }
}

const openSqlTestModal = () => {
  const keys = Object.keys(datasourcesMap.value)
  if (keys.length && !testSqlForm.dataSource) testSqlForm.dataSource = keys[0] ?? ''
  testResult.value = ''
  showSqlTestModal.value = true
}

const runSqlTest = async () => {
  if (!testSqlForm.dataSource || !testSqlForm.sql.trim()) {
    showToast('请填写数据源和 SQL', 'warning')
    return
  }
  loadingTest.value = true
  testResult.value = 'Running...'
  try {
    const response = await axios.post('/api/v1/sql/execute', {
      data_source: testSqlForm.dataSource,
      sql: testSqlForm.sql,
      cache_ttl: testSqlForm.cacheTtl,
    })
    testResult.value = JSON.stringify(response.data, null, 2)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: unknown } }; message?: string }
    testResult.value = `Error: ${JSON.stringify(err.response?.data?.detail ?? err.message)}`
  } finally {
    loadingTest.value = false
  }
}

const generateCode = (type: 'curl' | 'python' | 'js') => {
  const url = `${window.location.origin}/api/v1/sql/execute`
  const body = { data_source: testSqlForm.dataSource, sql: testSqlForm.sql, cache_ttl: testSqlForm.cacheTtl || undefined }
  if (type === 'curl') {
    codeLanguage.value = 'bash'
    codeSnippet.value = `curl -X POST "${url}" \\\n  -H "X-API-Key: YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify(body)}'`
  } else if (type === 'python') {
    codeLanguage.value = 'python'
    codeSnippet.value = `import requests\n\nrequests.post("${url}", headers={"X-API-Key": "YOUR_API_KEY"}, json=${JSON.stringify(body, null, 4)}).json()`
  } else {
    codeLanguage.value = 'javascript'
    codeSnippet.value = `fetch("${url}", { method: "POST", headers: { "X-API-Key": "YOUR_API_KEY", "Content-Type": "application/json" }, body: JSON.stringify(${JSON.stringify(body, null, 4)}) })`
  }
  showCodeModal.value = true
}

onMounted(() => {
  checkIsAdmin()
  if (!isAdmin.value) onlyAuthorized.value = true
  fetchResources()
  fetchDatasources()
})
</script>

<template>
  <div class="bg-white rounded-lg shadow h-[calc(100vh-8rem)] flex overflow-hidden border border-gray-200">
    <ResourceGroupSidebar
      :collapsed="isSidebarCollapsed"
      :search-group-query="searchGroupQuery"
      :tabs="filteredGroupTabs"
      :active-tab="activeTab"
      @update:collapsed="isSidebarCollapsed = $event"
      @update:search-group-query="searchGroupQuery = $event"
      @update:active-tab="activeTab = $event; page = 1"
    />

    <div class="flex-1 flex flex-col min-w-0 bg-white">
      <div class="p-6 space-y-4 flex-1 overflow-y-auto custom-scrollbar">
        <!-- Header -->
        <div class="flex justify-between items-start gap-4">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">{{ activeTab === 'ALL' ? '全部资源' : activeTab }}</h1>
            <p class="text-sm text-gray-500 mt-1">管理系统内所有的 API 资源接口</p>
          </div>
          <div class="flex gap-2 shrink-0">
            <template v-if="hasPerm('element:resource:import')">
              <input ref="importFile" type="file" class="hidden" accept=".json" @change="handleImport" />
              <button
                class="text-gray-600 border border-gray-300 px-3 py-2 rounded-lg hover:bg-gray-50 text-sm"
                @click="importFile?.click()"
              >
                导入
              </button>
            </template>
            <router-link
              v-if="hasPerm('element:resource:create')"
              to="/dashboard/resources/create"
              class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm font-medium shadow-sm"
            >
              + 新建资源
            </router-link>
            <div v-else-if="!hasPerm('element:resource:create')" class="text-xs text-gray-400 bg-gray-100 px-3 py-2 rounded-lg flex items-center gap-1">
              <ShieldCheckIcon class="w-4 h-4" /> 只读
            </div>
          </div>
        </div>

        <!-- Batch bar -->
        <div
          v-if="selectedKeys.size > 0 && (hasPerm('element:resource:edit') || hasPerm('element:resource:delete'))"
          class="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center justify-between"
        >
          <span class="text-sm font-medium text-blue-700">已选 {{ selectedKeys.size }} 项</span>
          <div class="flex gap-2">
            <button class="px-3 py-1 text-sm bg-green-100 text-green-700 rounded hover:bg-green-200" @click="batchUpdateStatus(1)">批量启用</button>
            <button class="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300" @click="requestBatchDisable">批量禁用</button>
            <button class="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200" @click="confirmBatchDelete">批量删除</button>
            <button class="text-xs text-blue-500 underline ml-2" @click="selectedKeys.clear()">取消</button>
          </div>
        </div>

        <!-- Filters -->
        <div class="bg-white border border-gray-200 rounded-lg p-4">
          <div class="flex flex-wrap items-center gap-3">
            <div class="flex-1 min-w-[200px] max-w-md relative">
              <input
                v-model="searchQuery"
                type="search"
                placeholder="搜索 Key、名称、数据源、备注..."
                class="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                @input="page = 1"
              />
              <svg class="w-4 h-4 text-gray-400 absolute left-3 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <select v-model="statusFilter" class="border border-gray-300 rounded-lg px-3 py-2 text-sm" @change="page = 1">
              <option value="ALL">全部状态</option>
              <option value="1">已启用</option>
              <option value="0">已禁用</option>
            </select>
            <label v-if="!isAdmin" class="flex items-center gap-2 text-sm text-gray-600">
              <input v-model="onlyAuthorized" type="checkbox" class="rounded text-blue-600" @change="page = 1" />
              仅我有权限的
            </label>
            <button v-if="hasActiveFilters" class="text-sm text-blue-600 hover:underline" @click="clearFilters">清除筛选</button>
            <span class="text-sm text-gray-500 ml-auto">
              筛选 <strong class="text-gray-800">{{ filteredResources.length }}</strong> / 本组 {{ groupTotalCount }}
            </span>
          </div>
        </div>

        <!-- Table -->
        <div class="border border-gray-200 rounded-lg overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full min-w-[1080px] table-fixed divide-y divide-gray-200">
              <colgroup>
                <col v-if="hasPerm('element:resource:edit') || hasPerm('element:resource:delete')" class="w-10" />
                <col class="w-[24%]" />
                <col class="w-[16%]" />
                <col class="w-[11%]" />
                <col class="w-[14%]" />
                <col class="w-14" />
                <col class="w-[13%]" />
                <col class="w-[168px]" />
              </colgroup>
              <thead class="bg-gray-50">
                <tr>
                  <th v-if="hasPerm('element:resource:edit') || hasPerm('element:resource:delete')" class="px-3 py-3">
                    <input type="checkbox" :checked="allSelected" :indeterminate="isIndeterminate" class="rounded" @change="toggleAll" />
                  </th>
                  <th class="px-3 py-3 text-left text-xs font-semibold text-gray-500 cursor-pointer whitespace-nowrap" @click="toggleSort('resource_name')">
                    资源详情{{ sortIndicator('resource_name') }}
                  </th>
                  <th class="px-3 py-3 text-left text-xs font-semibold text-gray-500 cursor-pointer whitespace-nowrap" @click="toggleSort('resource_mode')">
                    模式 / 数据源{{ sortIndicator('resource_mode') }}
                  </th>
                  <th class="px-3 py-3 text-left text-xs font-semibold text-gray-500 whitespace-nowrap">配置</th>
                  <th class="px-3 py-3 text-left text-xs font-semibold text-gray-500 whitespace-nowrap hidden xl:table-cell">备注</th>
                  <th class="px-3 py-3 text-left text-xs font-semibold text-gray-500 cursor-pointer whitespace-nowrap" @click="toggleSort('status')">
                    状态{{ sortIndicator('status') }}
                  </th>
                  <th class="px-3 py-3 text-left text-xs font-semibold text-gray-500 cursor-pointer whitespace-nowrap" @click="toggleSort('updated_at')">
                    更新时间{{ sortIndicator('updated_at') }}
                  </th>
                  <th class="px-3 py-3 text-right text-xs font-semibold text-gray-500 whitespace-nowrap">操作</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-if="loading">
                  <td :colspan="tableColSpan" class="px-6 py-16 text-center text-gray-500">
                    <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-2" />
                    <p class="text-sm">加载资源列表...</p>
                  </td>
                </tr>
                <tr v-else-if="emptyStateVariant">
                  <td :colspan="tableColSpan">
                    <ResourceEmptyState
                      :variant="emptyStateVariant"
                      :can-create="hasPerm('element:resource:create')"
                      @clear-filters="clearFilters"
                    />
                  </td>
                </tr>
                <tr
                  v-for="res in paginatedResources"
                  :key="res.resource_key"
                  class="hover:bg-blue-50/40 transition-colors cursor-pointer"
                  :class="{ 'bg-blue-50/60': selectedKeys.has(res.resource_key) }"
                  @click="navigateToResource(res)"
                >
                  <td v-if="hasPerm('element:resource:edit') || hasPerm('element:resource:delete')" class="px-3 py-3" @click.stop>
                    <input type="checkbox" :checked="selectedKeys.has(res.resource_key)" class="rounded" @change="toggleSelection(res.resource_key)" />
                  </td>
                  <td class="px-3 py-3 overflow-hidden">
                    <div class="flex items-center gap-2 min-w-0">
                      <div class="w-2 h-2 rounded-full shrink-0" :class="res.status === 1 ? 'bg-green-500' : 'bg-gray-300'" />
                      <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-1.5 min-w-0">
                          <span class="text-sm font-semibold text-gray-900 truncate" :title="res.resource_name">{{ res.resource_name }}</span>
                          <span v-if="res.resource_key === 'system.sql.execute'" class="shrink-0 text-[10px] px-1 py-0.5 bg-red-100 text-red-700 rounded font-bold">高危</span>
                        </div>
                        <p class="text-[11px] text-gray-400 font-mono truncate" :title="res.resource_key">{{ res.resource_key }}</p>
                      </div>
                    </div>
                  </td>
                  <td class="px-3 py-3 overflow-hidden">
                    <div class="whitespace-nowrap">
                      <span
                        class="inline-block text-[10px] font-bold px-1.5 py-0.5 rounded border"
                        :class="res.resource_mode === 'SQL' ? 'bg-amber-50 text-amber-700 border-amber-200' : res.resource_mode === 'SYSTEM' ? 'bg-gray-100 text-gray-600' : 'bg-emerald-50 text-emerald-700 border-emerald-200'"
                      >
                        {{ modeLabel(res.resource_mode) }}
                      </span>
                    </div>
                    <div class="text-[11px] text-gray-500 mt-1 truncate" :title="res.data_source">
                      <CircleStackIcon class="w-3 h-3 inline-block align-text-bottom mr-0.5" />{{ res.data_source }}
                    </div>
                  </td>
                  <td class="px-3 py-3 whitespace-nowrap">
                    <span class="text-xs text-gray-600 tabular-nums">
                      {{ Array.isArray(res.fields_config) ? res.fields_config.length : 0 }}字段 · {{ Array.isArray(res.allowed_filters) ? res.allowed_filters.length : 0 }}过滤
                    </span>
                  </td>
                  <td class="px-3 py-3 text-xs text-gray-500 truncate hidden xl:table-cell" :title="res.remarks || ''">
                    {{ res.remarks || '—' }}
                  </td>
                  <td class="px-3 py-3 whitespace-nowrap" @click.stop>
                    <button
                      :disabled="res.resource_mode === 'SYSTEM' || !hasPerm('element:resource:edit')"
                      class="relative inline-flex h-5 w-10 rounded-full transition-colors"
                      :class="[res.status === 1 ? 'bg-green-500' : 'bg-gray-300', (res.resource_mode === 'SYSTEM' || !hasPerm('element:resource:edit')) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer']"
                      :aria-label="res.status === 1 ? '已启用' : '已禁用'"
                      @click="toggleStatus(res)"
                    >
                      <span class="inline-block h-4 w-4 bg-white rounded-full shadow transform transition" :class="res.status === 1 ? 'translate-x-5' : 'translate-x-0.5'" />
                    </button>
                  </td>
                  <td class="px-3 py-3 text-xs text-gray-500 tabular-nums whitespace-nowrap">
                    {{ formatDate(res.updated_at || res.created_at) }}
                  </td>
                  <td class="px-3 py-3 whitespace-nowrap" @click.stop>
                    <ResourceRowActions
                      :resource="res"
                      :can-edit="hasPerm('element:resource:edit')"
                      :can-delete="hasPerm('element:resource:delete')"
                      :can-export="hasPerm('element:resource:export')"
                      :can-manage-special="hasPerm('element:resource:manage_special')"
                      @logs="openLogDrawer(res.resource_key)"
                      @export="exportResource(res)"
                      @delete="confirmDeleteResource(res.resource_key)"
                      @preview-sql="openSqlPreview(res.custom_sql || '')"
                      @open-ttl="openTtlModal(res)"
                      @open-sql-test="openSqlTestModal"
                      @copy-api="copyApiUrl(res.resource_key, $event)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div v-if="!loading && sortedResources.length > pageSize" class="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-600">
            <span>第 {{ page }} / {{ totalPages }} 页，共 {{ sortedResources.length }} 条</span>
            <div class="flex gap-2">
              <button class="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-40" :disabled="page <= 1" @click="page--">上一页</button>
              <button class="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-40" :disabled="page >= totalPages" @click="page++">下一页</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <teleport to="body">
      <Toast v-if="toast.show" :key="toast.key" :message="toast.message" :type="toast.type" @close="closeToast" />

      <ConfirmDialog
        :show="confirmDialog.show"
        :title="confirmDialog.title"
        :message="confirmDialog.message"
        :type="confirmDialog.type"
        :confirm-text="confirmDialog.confirmText"
        @confirm="handleConfirmDialog"
        @cancel="confirmDialog.show = false"
      />

      <ConfirmDeleteModal
        :open="showDeleteModal"
        :title="deleteModalKeys.length > 1 ? `确认删除 ${deleteModalKeys.length} 个资源？` : '确认删除资源？'"
        description="此操作无法撤销，相关 API 将立即停止对外服务。"
        :keys="deleteModalKeys"
        :loading="deleteLoading"
        @close="showDeleteModal = false"
        @confirm="executeDelete"
      />

      <ResourceLogDrawer
        :open="showLogDrawer"
        :resource-key="currentLogResource"
        :logs="accessLogs"
        :loading="loadingLogs"
        :selected-log="selectedLog"
        :format-date="formatDate"
        @close="showLogDrawer = false"
        @refresh="fetchAccessLogs(currentLogResource)"
        @select-log="selectedLog = $event"
      />

      <!-- SQL Preview -->
      <div v-if="showSqlPreviewModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40" @click="showSqlPreviewModal = false" />
        <div class="relative bg-white rounded-xl shadow-xl max-w-4xl w-full p-5">
          <h3 class="text-lg font-semibold mb-3">SQL 预览</h3>
          <codemirror v-model="previewSqlContent" :disabled="true" :style="{ height: '360px' }" :extensions="extensions" />
          <div class="mt-4 text-right">
            <button class="px-4 py-2 text-sm border rounded-lg" @click="showSqlPreviewModal = false">关闭</button>
          </div>
        </div>
      </div>

      <!-- SQL Test Modal (simplified) -->
      <div v-if="showSqlTestModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40" @click="showSqlTestModal = false" />
        <div class="relative bg-white rounded-xl shadow-xl max-w-2xl w-full p-5 max-h-[90vh] overflow-y-auto">
          <h3 class="text-lg font-semibold mb-4">SQL 在线测试</h3>
          <div class="space-y-3">
            <select v-model="testSqlForm.dataSource" class="w-full border rounded-lg px-3 py-2 text-sm">
              <option v-for="(desc, name) in datasourcesMap" :key="name" :value="name">{{ name }} ({{ desc }})</option>
            </select>
            <textarea v-model="testSqlForm.sql" rows="4" class="w-full border rounded-lg px-3 py-2 text-sm font-mono" />
            <div class="flex gap-2">
              <button class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg" :disabled="loadingTest" @click="runSqlTest">{{ loadingTest ? '执行中...' : '执行' }}</button>
              <button class="text-xs text-blue-600" @click="generateCode('curl')">cURL</button>
            </div>
            <pre v-if="testResult" class="bg-gray-900 text-green-400 text-xs p-3 rounded-lg max-h-48 overflow-auto">{{ testResult }}</pre>
          </div>
          <button class="mt-4 text-sm text-gray-600" @click="showSqlTestModal = false">关闭</button>
        </div>
      </div>

      <!-- TTL Modal -->
      <div v-if="showTtlModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40" @click="showTtlModal = false" />
        <div class="relative bg-white rounded-xl shadow-xl max-w-sm w-full p-5">
          <h3 class="font-semibold mb-3">默认缓存 TTL（秒）</h3>
          <input v-model.number="editingTtl" type="number" min="0" class="w-full border rounded-lg px-3 py-2" />
          <div class="mt-4 flex justify-end gap-2">
            <button class="px-4 py-2 text-sm border rounded-lg" @click="showTtlModal = false">取消</button>
            <button class="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg" :disabled="loadingTtl" @click="saveTtl">保存</button>
          </div>
        </div>
      </div>

      <!-- Code modal -->
      <div v-if="showCodeModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40" @click="showCodeModal = false" />
        <div class="relative bg-white rounded-xl shadow-xl max-w-2xl w-full p-5">
          <h3 class="font-semibold mb-3">调用示例</h3>
          <codemirror v-model="codeSnippet" :disabled="true" :style="{ height: '240px' }" :extensions="extensions" />
          <button class="mt-3 text-sm" @click="showCodeModal = false">关闭</button>
        </div>
      </div>
    </teleport>
  </div>
</template>
