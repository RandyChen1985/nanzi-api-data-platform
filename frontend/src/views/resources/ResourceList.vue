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
import ClearableInput from '@/components/common/ClearableInput.vue'
import type { Resource, AccessLog, ResourceSortField, ResourceGroupTab } from '@/types/resource'
import { isSystemResourceGroup, sortResourceGroups, isLockedSystemResource, displayResourceMode } from '@/types/resource'
import { CircleStackIcon, ShieldCheckIcon } from '@heroicons/vue/24/outline'
import { Codemirror } from 'vue-codemirror'
import { sql } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'
import { copyToClipboard } from '@/utils/clipboard'

const router = useRouter()
const isSidebarCollapsed = ref(false)

const resources = ref<Resource[]>([])
const loading = ref(false)
const searchQuery = ref('')
const searchGroupQuery = ref('')
const statusFilter = ref<'ALL' | '1' | '0'>('ALL')
const catalogFilter = ref<'ALL' | '1' | '0' | '2' | 'NONE'>('ALL')
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
const catalogStatusMap = ref<Record<string, number>>({})
const showBatchPublishModal = ref(false)
const batchPublishResult = ref<{ published: number; skipped: { product_key: string; display_name: string; reason: string }[]; total: number } | null>(null)
const showUnpublishModal = ref(false)
const unpublishTarget = ref<Resource | null>(null)
const unpublishPreview = ref({ count: 0, holders: [] as { user_id: number; user_name: string }[] })
const unpublishRevoke = ref(false)
const unpublishing = ref(false)
const showAssignOwnerModal = ref(false)
const assignOwnerUserId = ref<number | null>(null)
const assignOwnerOnlyEmpty = ref(true)
const assignOwnerUsers = ref<{ id: number; user_name: string; remark?: string }[]>([])
const productsWithoutOwner = ref(0)
const catalogDraftCount = ref(0)
const showDraftPublishModal = ref(false)
const draftPublishPreview = ref<{
  count: number
  ready_count: number
  items: {
    product_key: string
    display_name: string
    domain?: string | null
    owner_name?: string | null
    ready: boolean
    block_reason?: string | null
  }[]
} | null>(null)
const draftPublishLoading = ref(false)
const draftPublishConfirming = ref(false)

type BatchConfirmAction = 'publish' | 'enable' | 'disable' | 'delete'
const showBatchConfirmModal = ref(false)
const batchConfirmAction = ref<BatchConfirmAction | null>(null)
const batchConfirmItems = ref<{ resource_key: string; resource_name: string; hint?: string }[]>([])
const batchConfirmSkipped = ref(0)
const batchConfirmLoading = ref(false)
const assigningOwner = ref(false)

const canManageCatalog = computed(() => isAdmin.value || hasPerm('element:catalog:manage'))
const canPublishToCatalog = computed(
  () => isAdmin.value || hasPerm('element:catalog:publish') || hasPerm('element:resource:edit'),
)

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

const groupTabs = computed((): ResourceGroupTab[] => {
  const counts: Record<string, number> = {}
  resources.value.forEach((r) => {
    const g = r.resource_group || '默认分组'
    counts[g] = (counts[g] || 0) + 1
  })
  const tabs = sortResourceGroups(Object.keys(counts)).map((g) => ({
    name: g,
    label: g,
    count: counts[g] ?? 0,
    isSystem: isSystemResourceGroup(g),
  }))
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

    const catalogStatus = catalogStatusMap.value[r.resource_key]
    let matchesCatalog = true
    if (catalogFilter.value === 'NONE') {
      matchesCatalog = catalogStatus === undefined
    } else if (catalogFilter.value !== 'ALL') {
      matchesCatalog = catalogStatus === Number(catalogFilter.value)
    }

    return matchesSearch && matchesStatus && matchesGroup && matchesAuth && matchesCatalog
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
  () =>
    !!searchQuery.value ||
    statusFilter.value !== 'ALL' ||
    catalogFilter.value !== 'ALL' ||
    (onlyAuthorized.value && !isAdmin.value)
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
  catalogFilter.value = 'ALL'
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
  if (isLockedSystemResource(res)) return
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

const isCatalogPublished = (key: string) => catalogStatusMap.value[key] === 1

const isCatalogPublishable = (key: string) => {
  const status = catalogStatusMap.value[key]
  return status === undefined || status === 0 || status === 2
}

const publishableKeys = (keys: string[]) =>
  keys.filter((key) => {
    const res = resources.value.find((r) => r.resource_key === key)
    return (
      res
      && !isLockedSystemResource(res)
      && (res.resource_group || '').toLowerCase() !== 'system'
      && isCatalogPublishable(key)
    )
  })

const selectedPublishableCount = computed(() =>
  publishableKeys(Array.from(selectedKeys.value)).length,
)

const editableKeys = (keys: string[]) =>
  keys.filter((key) => {
    const res = resources.value.find((r) => r.resource_key === key)
    return res && !isLockedSystemResource(res)
  })

const enableTargetKeys = (keys: string[]) =>
  editableKeys(keys).filter((key) => {
    const res = resources.value.find((r) => r.resource_key === key)
    return res && res.status !== 1
  })

const disableTargetKeys = (keys: string[]) =>
  editableKeys(keys).filter((key) => {
    const res = resources.value.find((r) => r.resource_key === key)
    return res && res.status === 1 && !isCatalogPublished(key)
  })

const selectedEnableCount = computed(() =>
  enableTargetKeys(Array.from(selectedKeys.value)).length,
)
const selectedDisableCount = computed(() =>
  disableTargetKeys(Array.from(selectedKeys.value)).length,
)

const deletableKeys = (keys: string[]) =>
  keys.filter((key) => {
    const res = resources.value.find((r) => r.resource_key === key)
    return res && !isLockedSystemResource(res) && !isCatalogPublished(key)
  })

const selectedDeletableCount = computed(() =>
  deletableKeys(Array.from(selectedKeys.value)).length,
)

const getCatalogStatusHint = (key: string) => {
  const s = catalogStatusMap.value[key]
  if (s === 1) return '已上架'
  if (s === 0) return '草稿'
  if (s === 2) return '已下架'
  return '未进目录'
}

const buildBatchConfirmItems = (
  keys: string[],
  hintFn?: (key: string, res: Resource) => string | undefined,
) =>
  keys.map((key) => {
    const res = resources.value.find((r) => r.resource_key === key)!
    return {
      resource_key: key,
      resource_name: res.resource_name || key,
      hint: hintFn?.(key, res),
    }
  })

const batchConfirmTitle = computed(() => {
  switch (batchConfirmAction.value) {
    case 'publish':
      return '确认批量发布到目录'
    case 'enable':
      return '确认批量启用'
    case 'disable':
      return '确认批量禁用'
    case 'delete':
      return '确认批量删除'
    default:
      return '确认操作'
  }
})

const batchConfirmSummary = computed(() => {
  const count = batchConfirmItems.value.length
  const skipped = batchConfirmSkipped.value
  switch (batchConfirmAction.value) {
    case 'publish':
      return skipped > 0
        ? `将发布 ${count} 个资源到数据产品目录，已跳过 ${skipped} 个已上架或系统资源。`
        : `将发布 ${count} 个资源到数据产品目录。`
    case 'enable':
      return skipped > 0
        ? `将启用 ${count} 个当前禁用的资源，已跳过 ${skipped} 个已启用或系统资源。`
        : `将启用 ${count} 个当前禁用的资源。`
    case 'disable':
      return skipped > 0
        ? `将禁用 ${count} 个当前启用的资源，禁用后对外 API 不可用；已跳过 ${skipped} 个已禁用、已上架或系统资源。`
        : `将禁用 ${count} 个资源，禁用后对外 API 将不可用。`
    case 'delete':
      return skipped > 0
        ? `将删除 ${count} 个资源，此操作不可撤销；已跳过 ${skipped} 个已上架或系统资源。`
        : `将删除 ${count} 个资源，此操作不可撤销，相关 API 将立即停止对外服务。`
    default:
      return ''
  }
})

const batchConfirmButtonClass = computed(() => {
  switch (batchConfirmAction.value) {
    case 'delete':
      return 'bg-red-600 hover:bg-red-700'
    case 'disable':
      return 'bg-yellow-500 hover:bg-yellow-600'
    case 'enable':
      return 'bg-green-600 hover:bg-green-700'
    default:
      return 'bg-indigo-600 hover:bg-indigo-700'
  }
})

const openBatchPublishConfirm = () => {
  const all = Array.from(selectedKeys.value)
  const keys = publishableKeys(all)
  if (!keys.length) {
    showToast('所选资源均已上架或为系统资源，无需发布', 'warning')
    return
  }
  batchConfirmAction.value = 'publish'
  batchConfirmSkipped.value = all.length - keys.length
  batchConfirmItems.value = buildBatchConfirmItems(keys, (key) => getCatalogStatusHint(key))
  showBatchConfirmModal.value = true
}

const openBatchEnableConfirm = () => {
  const all = Array.from(selectedKeys.value)
  const keys = enableTargetKeys(all)
  if (!keys.length) {
    showToast('所选资源均已启用或为系统资源', 'warning')
    return
  }
  batchConfirmAction.value = 'enable'
  batchConfirmSkipped.value = all.length - keys.length
  batchConfirmItems.value = buildBatchConfirmItems(keys, (_key, res) => (res.status === 1 ? '已启用' : '已禁用'))
  showBatchConfirmModal.value = true
}

const openBatchDisableConfirm = () => {
  const all = Array.from(selectedKeys.value)
  const keys = disableTargetKeys(all)
  if (!keys.length) {
    showToast('所选资源均已禁用或为系统资源', 'warning')
    return
  }
  batchConfirmAction.value = 'disable'
  batchConfirmSkipped.value = all.length - keys.length
  batchConfirmItems.value = buildBatchConfirmItems(keys, (_key, res) => (res.status === 1 ? '已启用' : '已禁用'))
  showBatchConfirmModal.value = true
}

const openBatchDeleteConfirm = () => {
  const all = Array.from(selectedKeys.value)
  const keys = deletableKeys(all)
  if (!keys.length) {
    showToast('所选资源均已上架到目录，请先下架后再删除', 'warning')
    return
  }
  batchConfirmAction.value = 'delete'
  batchConfirmSkipped.value = all.length - keys.length
  batchConfirmItems.value = buildBatchConfirmItems(keys, (key) => getCatalogStatusHint(key))
  showBatchConfirmModal.value = true
}

const confirmDeleteResource = (key: string) => {
  if (isCatalogPublished(key)) {
    showToast('该资源已上架到目录，请先从目录下架后再删除', 'warning')
    return
  }
  openDeleteModal([key])
}

const runBatchDelete = async (keys: string[]) => {
  let successCount = 0
  for (const key of keys) {
    try {
      await axios.delete(`/api/portal/meta/resources/${key}`)
      successCount++
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      showToast(err.response?.data?.detail || `删除 ${key} 失败`, 'error')
    }
  }
  showToast(`删除完成：成功 ${successCount}，失败 ${keys.length - successCount}`, successCount > 0 ? 'success' : 'warning')
  selectedKeys.value.clear()
  fetchResources()
  await fetchCatalogStatus()
}

const executeDelete = async () => {
  deleteLoading.value = true
  await runBatchDelete(deletableKeys(deleteModalKeys.value))
  showDeleteModal.value = false
  deleteModalKeys.value = []
  deleteLoading.value = false
}

const batchUpdateStatus = async (status: number, keys?: string[]) => {
  const targetKeys = keys ?? (status === 1
    ? enableTargetKeys(Array.from(selectedKeys.value))
    : disableTargetKeys(Array.from(selectedKeys.value)))
  if (!targetKeys.length) return
  loading.value = true
  let successCount = 0
  for (const key of targetKeys) {
    try {
      await axios.put(`/api/portal/meta/resources/${key}`, { status })
      successCount++
    } catch {
      /* continue */
    }
  }
  showToast(`批量更新：成功 ${successCount}，失败 ${targetKeys.length - successCount}`, successCount > 0 ? 'success' : 'warning')
  selectedKeys.value.clear()
  fetchResources()
  loading.value = false
}

const runBatchPublish = async (keys: string[]) => {
  const res = await axios.post('/api/portal/catalog/products/batch-publish-from-resources', {
    resource_keys: keys,
  })
  batchPublishResult.value = res.data
  if (res.data.skipped?.length) {
    showBatchPublishModal.value = true
  } else {
    showToast(`已批量发布 ${res.data.published} 个产品`, 'success')
  }
  await fetchCatalogStatus()
  selectedKeys.value.clear()
}

const confirmBatchAction = async () => {
  if (!batchConfirmAction.value || !batchConfirmItems.value.length) return
  batchConfirmLoading.value = true
  const keys = batchConfirmItems.value.map((item) => item.resource_key)
  try {
    switch (batchConfirmAction.value) {
      case 'publish':
        await runBatchPublish(keys)
        break
      case 'enable':
        await batchUpdateStatus(1, keys)
        break
      case 'disable':
        await batchUpdateStatus(0, keys)
        break
      case 'delete':
        await runBatchDelete(keys)
        break
    }
    showBatchConfirmModal.value = false
    batchConfirmAction.value = null
    batchConfirmItems.value = []
    batchConfirmSkipped.value = 0
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '操作失败', 'error')
  } finally {
    batchConfirmLoading.value = false
  }
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
  if (isLockedSystemResource(resource) || !hasPerm('element:resource:edit')) return
  const newStatus = resource.status === 1 ? 0 : 1
  if (newStatus === 0 && isCatalogPublished(resource.resource_key)) {
    showToast('该资源已上架到目录，请先从目录下架后再禁用', 'warning')
    return
  }
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

const fetchCatalogStatus = async () => {
  try {
    const res = await axios.get('/api/portal/catalog/status-map')
    catalogStatusMap.value = res.data
  } catch {
    catalogStatusMap.value = {}
  }
  await fetchDraftCount()
}

const fetchDraftCount = async () => {
  if (!isAdmin.value) {
    catalogDraftCount.value = 0
    return
  }
  try {
    const res = await axios.get('/api/portal/catalog/products/draft-count')
    catalogDraftCount.value = res.data.count ?? 0
  } catch {
    catalogDraftCount.value = 0
  }
}

const publishToCatalog = async (res: Resource, publish = true) => {
  try {
    await axios.post('/api/portal/catalog/products/publish-from-resource', {
      resource_key: res.resource_key,
      publish,
    })
    showToast(publish ? '已发布到数据产品目录' : '已保存目录草稿', 'success')
    await fetchCatalogStatus()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '发布失败', 'error')
  }
}

const unpublishFromCatalog = async (res: Resource) => {
  try {
    const preview = await axios.get(
      `/api/portal/catalog/products/${encodeURIComponent(res.resource_key)}/unpublish-preview`,
    )
    unpublishTarget.value = res
    unpublishPreview.value = preview.data
    unpublishRevoke.value = false
    showUnpublishModal.value = true
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '无法获取下架预览', 'error')
  }
}

const confirmUnpublishFromCatalog = async () => {
  const res = unpublishTarget.value
  if (!res) return
  unpublishing.value = true
  try {
    await axios.post(`/api/portal/catalog/products/${encodeURIComponent(res.resource_key)}/unpublish`, {
      revoke_permissions: unpublishRevoke.value,
    })
    showToast('已从数据产品目录下架', 'success')
    showUnpublishModal.value = false
    unpublishTarget.value = null
    await fetchCatalogStatus()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '下架失败', 'error')
  } finally {
    unpublishing.value = false
  }
}

const batchPublishAllDrafts = async () => {
  try {
    const res = await axios.post('/api/portal/catalog/products/batch-publish')
    batchPublishResult.value = res.data
    showDraftPublishModal.value = false
    draftPublishPreview.value = null
    if (res.data.skipped?.length || res.data.total === 0) {
      showBatchPublishModal.value = true
    } else {
      showToast(`已上架全部草稿：${res.data.published} 个`, 'success')
    }
    await fetchCatalogStatus()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '批量上架草稿失败', 'error')
  }
}

const openBatchPublishAllDraftsModal = async () => {
  draftPublishLoading.value = true
  try {
    const res = await axios.get('/api/portal/catalog/products/draft-preview')
    draftPublishPreview.value = res.data
    if (!res.data.count) {
      showToast('当前没有目录草稿', 'info')
      await fetchDraftCount()
      return
    }
    showDraftPublishModal.value = true
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '加载草稿列表失败', 'error')
  } finally {
    draftPublishLoading.value = false
  }
}

const confirmBatchPublishAllDrafts = async () => {
  draftPublishConfirming.value = true
  try {
    await batchPublishAllDrafts()
  } finally {
    draftPublishConfirming.value = false
  }
}

const fetchWithoutOwnerCount = async () => {
  if (!canManageCatalog.value) return
  try {
    const res = await axios.get('/api/portal/catalog/products/without-owner-count')
    productsWithoutOwner.value = res.data.count ?? 0
  } catch {
    productsWithoutOwner.value = 0
  }
}

const openAssignOwnerModal = async () => {
  assignOwnerUserId.value = null
  assignOwnerOnlyEmpty.value = true
  try {
    const res = await axios.get('/api/portal/catalog/assign-owner-users')
    assignOwnerUsers.value = res.data
    showAssignOwnerModal.value = true
  } catch {
    showToast('加载用户列表失败', 'error')
  }
}

const submitAssignOwner = async () => {
  if (!assignOwnerUserId.value) {
    showToast('请选择负责人', 'warning')
    return
  }
  const selectedCatalogKeys = Array.from(selectedKeys.value).filter((k) => catalogStatusMap.value[k] !== undefined)
  assigningOwner.value = true
  try {
    const res = await axios.post('/api/portal/catalog/products/batch-assign-owner', {
      owner_user_id: assignOwnerUserId.value,
      product_keys: selectedCatalogKeys.length ? selectedCatalogKeys : undefined,
      only_without_owner: assignOwnerOnlyEmpty.value,
    })
    showToast(`已指定 ${res.data.updated} 个产品负责人`, 'success')
    showAssignOwnerModal.value = false
    await fetchWithoutOwnerCount()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '指定负责人失败', 'error')
  } finally {
    assigningOwner.value = false
  }
}

const catalogStatusLabel = (key: string) => {
  const s = catalogStatusMap.value[key]
  if (s === 1) return '已上架'
  if (s === 0) return '草稿'
  if (s === 2) return '已下线'
  return null
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

const copyApiUrl = async (key: string, type: 'resource' | 'query') => {
  const origin = window.location.origin
  const url = type === 'resource' ? `${origin}/api/v1/resources/${key}` : `${origin}/api/v1/query`
  const success = await copyToClipboard(url)
  if (success) {
    showToast(type === 'resource' ? '资源接口 URL 已复制' : '通用 Query URL 已复制', 'success')
  } else {
    showToast('复制失败', 'error')
  }
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
  fetchCatalogStatus()
  fetchWithoutOwnerCount()
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
            <button
              v-if="isAdmin && catalogDraftCount > 0"
              class="text-indigo-600 border border-indigo-200 px-3 py-2 rounded-lg hover:bg-indigo-50 text-sm relative disabled:opacity-50"
              :disabled="draftPublishLoading"
              :title="`上架目录中 ${catalogDraftCount} 个草稿产品（与勾选无关）`"
              @click="openBatchPublishAllDraftsModal"
            >
              {{ draftPublishLoading ? '加载中...' : '上架全部草稿' }}
              <span
                class="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-1 rounded-full bg-indigo-500 text-white text-[10px] leading-4 text-center"
              >
                {{ catalogDraftCount > 99 ? '99+' : catalogDraftCount }}
              </span>
            </button>
            <button
              v-if="canManageCatalog"
              class="text-indigo-600 border border-indigo-200 px-3 py-2 rounded-lg hover:bg-indigo-50 text-sm relative"
              @click="openAssignOwnerModal"
            >
              批量指定负责人
              <span
                v-if="productsWithoutOwner > 0"
                class="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-1 rounded-full bg-amber-500 text-white text-[10px] leading-4 text-center"
              >
                {{ productsWithoutOwner > 99 ? '99+' : productsWithoutOwner }}
              </span>
            </button>
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
          v-if="selectedKeys.size > 0 && (hasPerm('element:resource:edit') || hasPerm('element:resource:delete') || canPublishToCatalog)"
          class="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center justify-between"
        >
          <span class="text-sm font-medium text-blue-700">已选 {{ selectedKeys.size }} 项</span>
          <div class="flex gap-2">
            <button
              v-if="canPublishToCatalog"
              class="px-3 py-1 text-sm bg-indigo-100 text-indigo-700 rounded hover:bg-indigo-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="selectedPublishableCount === 0"
              :title="selectedPublishableCount === 0 ? '所选资源均已上架或为系统资源' : `将发布 ${selectedPublishableCount} 个未上架资源`"
              @click="openBatchPublishConfirm"
            >
              批量发布目录 ({{ selectedPublishableCount }})
            </button>
            <button
              v-if="hasPerm('element:resource:edit')"
              class="px-3 py-1 text-sm bg-green-100 text-green-700 rounded hover:bg-green-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="selectedEnableCount === 0"
              :title="selectedEnableCount === 0 ? '所选资源均已启用或为系统资源' : `将启用 ${selectedEnableCount} 个当前禁用的资源`"
              @click="openBatchEnableConfirm"
            >
              批量启用 ({{ selectedEnableCount }})
            </button>
            <button
              v-if="hasPerm('element:resource:edit')"
              class="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="selectedDisableCount === 0"
              :title="selectedDisableCount === 0 ? '所选资源均已禁用、已上架或为系统资源' : `将禁用 ${selectedDisableCount} 个当前启用的资源`"
              @click="openBatchDisableConfirm"
            >
              批量禁用 ({{ selectedDisableCount }})
            </button>
            <button
              v-if="hasPerm('element:resource:delete')"
              class="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="selectedDeletableCount === 0"
              :title="selectedDeletableCount === 0 ? '所选资源均已上架到目录，请先下架' : `将删除 ${selectedDeletableCount} 个资源`"
              @click="openBatchDeleteConfirm"
            >
              批量删除 ({{ selectedDeletableCount }})
            </button>
            <button class="text-xs text-blue-500 underline ml-2" @click="selectedKeys.clear()">取消</button>
          </div>
        </div>

        <!-- Filters -->
        <div class="bg-white border border-gray-200 rounded-lg p-4">
          <div class="flex flex-wrap items-center gap-3">
            <ClearableInput
              v-model="searchQuery"
              show-search-icon
              wrapper-class="flex-1 min-w-[200px] max-w-md"
              input-class="py-2 text-sm"
              placeholder="搜索 Key、名称、数据源、备注..."
              @input="page = 1"
            />
            <select v-model="statusFilter" class="border border-gray-300 rounded-lg px-3 py-2 text-sm" @change="page = 1">
              <option value="ALL">全部状态</option>
              <option value="1">已启用</option>
              <option value="0">已禁用</option>
            </select>
            <select v-model="catalogFilter" class="border border-gray-300 rounded-lg px-3 py-2 text-sm" @change="page = 1">
              <option value="ALL">目录：全部</option>
              <option value="1">目录：已上架</option>
              <option value="0">目录：草稿</option>
              <option value="2">目录：已下线</option>
              <option value="NONE">目录：未入目录</option>
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
                  class="hover:bg-blue-50/40 transition-colors"
                  :class="[
                    { 'bg-blue-50/60': selectedKeys.has(res.resource_key) },
                    isLockedSystemResource(res) ? '' : 'cursor-pointer',
                  ]"
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
                          <span v-if="catalogStatusLabel(res.resource_key)" class="shrink-0 text-[10px] px-1 py-0.5 rounded font-bold" :class="catalogStatusMap[res.resource_key] === 1 ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-500'">{{ catalogStatusLabel(res.resource_key) }}</span>
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
                        :class="displayResourceMode(res) === 'SQL' ? 'bg-amber-50 text-amber-700 border-amber-200' : displayResourceMode(res) === 'SYSTEM' ? 'bg-gray-100 text-gray-600' : 'bg-emerald-50 text-emerald-700 border-emerald-200'"
                      >
                        {{ modeLabel(displayResourceMode(res)) }}
                      </span>
                    </div>
                    <div class="text-[11px] text-gray-500 mt-1 truncate" :title="res.data_source">
                      <CircleStackIcon class="w-3 h-3 inline-block align-text-bottom mr-0.5" />{{ res.data_source }}
                    </div>
                  </td>
                  <td class="px-3 py-3 whitespace-nowrap">
                    <div class="inline-flex items-center gap-1 text-xs text-gray-500">
                      <span class="inline-flex items-center gap-1">
                        <span class="inline-flex items-center justify-center min-w-[1.125rem] h-5 px-1.5 rounded-full bg-blue-50 text-blue-700 text-[11px] font-semibold tabular-nums border border-blue-100">
                          {{ Array.isArray(res.fields_config) ? res.fields_config.length : 0 }}
                        </span>
                        字段
                      </span>
                      <span class="text-gray-300 select-none">·</span>
                      <span class="inline-flex items-center gap-1">
                        <span class="inline-flex items-center justify-center min-w-[1.125rem] h-5 px-1.5 rounded-full bg-violet-50 text-violet-700 text-[11px] font-semibold tabular-nums border border-violet-100">
                          {{ Array.isArray(res.allowed_filters) ? res.allowed_filters.length : 0 }}
                        </span>
                        过滤
                      </span>
                    </div>
                  </td>
                  <td class="px-3 py-3 text-xs text-gray-500 truncate hidden xl:table-cell" :title="res.remarks || ''">
                    {{ res.remarks || '—' }}
                  </td>
                  <td class="px-3 py-3 whitespace-nowrap" @click.stop>
                    <button
                      :disabled="isLockedSystemResource(res) || !hasPerm('element:resource:edit') || (res.status === 1 && isCatalogPublished(res.resource_key))"
                      class="relative inline-flex h-5 w-10 rounded-full transition-colors"
                      :class="[
                        res.status === 1 ? 'bg-green-500' : 'bg-gray-300',
                        (isLockedSystemResource(res) || !hasPerm('element:resource:edit') || (res.status === 1 && isCatalogPublished(res.resource_key)))
                          ? 'opacity-50 cursor-not-allowed'
                          : 'cursor-pointer',
                      ]"
                      :title="res.status === 1 && isCatalogPublished(res.resource_key) ? '已上架到目录，请先从目录下架后再禁用' : (res.status === 1 ? '已启用' : '已禁用')"
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
                      :catalog-status="catalogStatusMap[res.resource_key] ?? null"
                      :can-unpublish-catalog="isAdmin"
                      @logs="openLogDrawer(res.resource_key)"
                      @export="exportResource(res)"
                      @delete="confirmDeleteResource(res.resource_key)"
                      @preview-sql="openSqlPreview(res.custom_sql || '')"
                      @open-ttl="openTtlModal(res)"
                      @open-sql-test="openSqlTestModal"
                      @copy-api="copyApiUrl(res.resource_key, $event)"
                      @publish-catalog="publishToCatalog(res)"
                      @unpublish-catalog="unpublishFromCatalog(res)"
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

      <!-- Batch assign owner -->
      <div v-if="showAssignOwnerModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40" @click="showAssignOwnerModal = false" />
        <div class="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6">
          <h3 class="text-lg font-semibold text-gray-900">批量指定产品负责人</h3>
          <p class="text-sm text-gray-500 mt-2">
            {{ selectedKeys.size ? `已选 ${selectedKeys.size} 个资源中在目录内的产品` : `将对全部未指定负责人的目录产品生效（当前 ${productsWithoutOwner} 个）` }}
          </p>
          <div class="mt-4 space-y-3">
            <select v-model="assignOwnerUserId" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              <option :value="null">选择负责人</option>
              <option v-for="u in assignOwnerUsers" :key="u.id" :value="u.id">
                {{ u.user_name }}{{ u.remark ? ` (${u.remark})` : '' }}
              </option>
            </select>
            <label class="flex items-center gap-2 text-sm text-gray-600">
              <input v-model="assignOwnerOnlyEmpty" type="checkbox" class="rounded text-indigo-600" />
              仅更新尚未指定负责人的产品
            </label>
          </div>
          <div class="mt-5 flex gap-2 justify-end">
            <button class="px-4 py-2 text-sm border rounded-lg" @click="showAssignOwnerModal = false">取消</button>
            <button
              :disabled="assigningOwner"
              class="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg disabled:opacity-50"
              @click="submitAssignOwner"
            >
              {{ assigningOwner ? '保存中...' : '确认' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Catalog unpublish -->
      <div v-if="showUnpublishModal && unpublishTarget" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40" @click="showUnpublishModal = false" />
        <div class="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
          <h3 class="text-lg font-bold text-gray-900">确认下架</h3>
          <p class="text-sm text-gray-600">
            确认将「{{ unpublishTarget.resource_name }}」从数据产品目录下架？
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
              @click="confirmUnpublishFromCatalog"
            >
              {{ unpublishing ? '下架中...' : '确认下架' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Batch action confirm -->
      <div v-if="showBatchConfirmModal && batchConfirmAction" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40" @click="!batchConfirmLoading && (showBatchConfirmModal = false)" />
        <div class="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6 max-h-[80vh] flex flex-col">
          <h3 class="text-lg font-semibold text-gray-900">{{ batchConfirmTitle }}</h3>
          <p class="text-sm text-gray-500 mt-2">{{ batchConfirmSummary }}</p>
          <div class="mt-4 flex-1 min-h-0 overflow-y-auto border border-gray-100 rounded-lg divide-y divide-gray-100">
            <div
              v-for="item in batchConfirmItems"
              :key="item.resource_key"
              class="px-3 py-2.5 text-sm"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="font-medium text-gray-900 truncate">{{ item.resource_name }}</p>
                  <p class="text-xs text-gray-500 font-mono truncate mt-0.5">{{ item.resource_key }}</p>
                </div>
                <span v-if="item.hint" class="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                  {{ item.hint }}
                </span>
              </div>
            </div>
          </div>
          <div class="mt-5 flex justify-end gap-2 pt-2">
            <button
              class="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
              :disabled="batchConfirmLoading"
              @click="showBatchConfirmModal = false"
            >
              取消
            </button>
            <button
              class="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50"
              :class="batchConfirmButtonClass"
              :disabled="batchConfirmLoading"
              @click="confirmBatchAction"
            >
              {{ batchConfirmLoading ? '处理中...' : `确认 (${batchConfirmItems.length})` }}
            </button>
          </div>
        </div>
      </div>

      <!-- Draft publish confirm -->
      <div v-if="showDraftPublishModal && draftPublishPreview" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40" @click="!draftPublishConfirming && (showDraftPublishModal = false)" />
        <div class="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6 max-h-[80vh] flex flex-col">
          <h3 class="text-lg font-semibold text-gray-900">确认上架全部草稿</h3>
          <p class="text-sm text-gray-500 mt-2">
            共 <strong class="text-gray-800">{{ draftPublishPreview.count }}</strong> 个草稿，
            其中 <strong class="text-green-600">{{ draftPublishPreview.ready_count }}</strong> 个信息完整可上架
            <template v-if="draftPublishPreview.count > draftPublishPreview.ready_count">
              ，<strong class="text-amber-600">{{ draftPublishPreview.count - draftPublishPreview.ready_count }}</strong> 个可能因信息不全被跳过
            </template>
          </p>
          <div class="mt-4 flex-1 min-h-0 overflow-y-auto border border-gray-100 rounded-lg divide-y divide-gray-100">
            <div
              v-for="item in draftPublishPreview.items"
              :key="item.product_key"
              class="px-3 py-2.5 text-sm"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="font-medium text-gray-900 truncate">{{ item.display_name }}</p>
                  <p class="text-xs text-gray-500 font-mono truncate mt-0.5">{{ item.product_key }}</p>
                  <p class="text-xs text-gray-400 mt-0.5">
                    {{ item.domain || '默认域' }}
                    <span v-if="item.owner_name"> · 负责人 {{ item.owner_name }}</span>
                  </p>
                  <p v-if="!item.ready && item.block_reason" class="text-xs text-amber-700 mt-1">
                    {{ item.block_reason }}
                  </p>
                </div>
                <span
                  class="shrink-0 text-[10px] px-1.5 py-0.5 rounded font-medium"
                  :class="item.ready ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'"
                >
                  {{ item.ready ? '可上架' : '需补全' }}
                </span>
              </div>
            </div>
          </div>
          <div class="mt-5 flex justify-end gap-2 pt-2">
            <button
              class="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
              :disabled="draftPublishConfirming"
              @click="showDraftPublishModal = false"
            >
              取消
            </button>
            <button
              class="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
              :disabled="draftPublishConfirming || draftPublishPreview.ready_count === 0"
              @click="confirmBatchPublishAllDrafts"
            >
              {{ draftPublishConfirming ? '上架中...' : `确认上架 (${draftPublishPreview.ready_count})` }}
            </button>
          </div>
        </div>
      </div>

      <!-- Batch publish result -->
      <div v-if="showBatchPublishModal && batchPublishResult" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40" @click="showBatchPublishModal = false" />
        <div class="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6 max-h-[80vh] overflow-y-auto">
          <h3 class="text-lg font-semibold text-gray-900">批量发布结果</h3>
          <p class="text-sm text-gray-500 mt-2">
            成功 <strong class="text-green-600">{{ batchPublishResult.published }}</strong> /
            共 {{ batchPublishResult.total }} 项
          </p>
          <div v-if="batchPublishResult.skipped?.length" class="mt-4 space-y-2">
            <p class="text-sm font-medium text-amber-700">以下产品需补全信息后再发布：</p>
            <div
              v-for="s in batchPublishResult.skipped"
              :key="s.product_key"
              class="flex items-start justify-between gap-3 p-3 bg-amber-50 rounded-lg text-sm"
            >
              <div class="min-w-0">
                <p class="font-medium text-gray-800 truncate">{{ s.display_name }}</p>
                <p class="text-xs text-amber-700 mt-0.5">{{ s.reason }}</p>
              </div>
              <button
                class="flex-shrink-0 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                @click="router.push(`/dashboard/catalog/${s.product_key}/edit`); showBatchPublishModal = false"
              >
                去编辑
              </button>
            </div>
          </div>
          <button class="mt-5 w-full py-2 bg-gray-100 rounded-lg text-sm hover:bg-gray-200" @click="showBatchPublishModal = false">
            关闭
          </button>
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
