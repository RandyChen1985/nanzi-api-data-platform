<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { metadataV2Api, type Dataset } from '../api/metadata_v2'
import axios from '../utils/axios'
import { 
  CircleStackIcon, PlusIcon, RocketLaunchIcon, 
  TrashIcon, Squares2X2Icon, ListBulletIcon,
  CommandLineIcon, BeakerIcon, XMarkIcon, ExclamationTriangleIcon,
  CloudArrowUpIcon, InformationCircleIcon, SparklesIcon,
  UserIcon, ClockIcon, ArrowPathIcon
} from '@heroicons/vue/24/outline'
import SmartImportWizard from '../components/metadata/SmartImportWizard.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { useToast } from '../composables/useToast'
import Tooltip from '../components/common/Tooltip.vue'
import ClearableInput from '../components/common/ClearableInput.vue'

const VECTOR_STATUS: Record<number, { label: string; class: string }> = {
  0: { label: '未同步', class: 'bg-gray-100 text-gray-600 ring-gray-200' },
  1: { label: '已同步', class: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  2: { label: '同步中', class: 'bg-blue-50 text-blue-700 ring-blue-200' },
  3: { label: '同步失败', class: 'bg-red-50 text-red-700 ring-red-200' },
  4: { label: '待更新', class: 'bg-amber-50 text-amber-700 ring-amber-200' },
}

const DEFAULT_VECTOR_META = { label: '未同步', class: 'bg-gray-100 text-gray-600 ring-gray-200' }

const getVectorMeta = (status?: number) => VECTOR_STATUS[status ?? 0] ?? DEFAULT_VECTOR_META

const router = useRouter()
const { showToast } = useToast()

// 权限检查辅助函数
const hasPerm = (code: string) => {
  const userInfoStr = localStorage.getItem('user_info')
  if (!userInfoStr) return false
  const user = JSON.parse(userInfoStr)
  if (user.role === 'admin') return true
  const perms = user.permissions?.elements || []
  return perms.includes(code)
}

const datasets = ref<Dataset[]>([])
const loading = ref(false)
const showImportModal = ref(false)
const searchQuery = ref('')
const statusFilter = ref<'ALL' | '1' | '0'>('ALL')
const vectorFilter = ref<'ALL' | '0' | '1' | '2' | '3' | '4'>('ALL')
const dataSourceFilter = ref('ALL')
const viewMode = ref<'grid' | 'list'>(
  (localStorage.getItem('metadata_view_mode') as 'grid' | 'list') || 'grid'
)
const showSpecModal = ref(false)
const activeSpecTab = ref('concept')
const showCreateModal = ref(false)
const isVectorSupported = ref(true)
const vectorDbWarning = ref('')
const isAiEnabled = ref(true)
const dismissAiWarning = ref(false)

// Delete State
const showDeleteConfirm = ref(false)
const deletingDataset = ref<Dataset | null>(null)

const confirmDialog = ref({
  show: false,
  title: '',
  message: '',
  type: 'warning' as 'danger' | 'warning' | 'info',
  confirmText: '确认',
  onConfirm: () => {},
})

const canManage = computed(() => hasPerm('element:metadata:manage'))
const canViewSimulator = computed(() => hasPerm('element:metadata:view'))

// Data Source State
const availableDataSources = ref<any[]>([])

const checkAiStatus = async () => {
  try {
    const res = await axios.get('/api/portal/system/config/ai')
    isAiEnabled.value = String(res.data.enabled).toLowerCase() === 'true'
  } catch (e) {
    isAiEnabled.value = false
  }
}

const checkVectorSupport = async () => {
  try {
    const res = await axios.post('/api/portal/system/test-connection/vector')
    isVectorSupported.value = res.data.status === 'success'
    
    // Check for DB 0 warning in logs
    if (res.data.logs) {
      const dbLog = res.data.logs.find((log: string) => log.includes('DB') && log.includes('0'))
      if (dbLog) {
        vectorDbWarning.value = dbLog
      }
    }
  } catch (e) {
    isVectorSupported.value = false
  }
}

const newDataset = ref({
  name: '',
  display_name: '',
  description: '',
  data_source: '',
  tags: [] as string[]
})
const tagInput = ref('')

const fetchDataSources = async () => {
  try {
    const res = await axios.get('/api/portal/datasource/datasources?status=active')
    const userInfoStr = localStorage.getItem('user_info')
    if (userInfoStr) {
      const user = JSON.parse(userInfoStr)
      if (user.role === 'admin') {
        availableDataSources.value = res.data
      } else {
        const allowed = user.permissions?.datasources || []
        availableDataSources.value = res.data.filter((ds: any) => allowed.includes(`ds:${ds.source_name}`))
      }
    }
    if (availableDataSources.value.length > 0) {
      newDataset.value.data_source = availableDataSources.value[0].source_name
    }
  } catch (e) {
    console.error('Failed to fetch datasources', e)
  }
}

const addTag = () => {
  if (tagInput.value && !newDataset.value.tags.includes(tagInput.value)) {
    newDataset.value.tags.push(tagInput.value)
    tagInput.value = ''
  }
}

const removeTag = (index: number) => {
  newDataset.value.tags.splice(index, 1)
}

const handleCreate = async () => {
  if (!newDataset.value.name) return showToast('请输入数据集编码', 'warning')
  try {
    await metadataV2Api.createDataset(newDataset.value)
    showCreateModal.value = false
    newDataset.value = { name: '', display_name: '', description: '', data_source: availableDataSources.value[0]?.source_name || '', tags: [] }
    fetchDatasets()
    showToast('数据集创建成功', 'success')
  } catch (e) {
    showToast('创建失败', 'error')
  }
}

const toggleStatus = async (ds: Dataset) => {
  const newStatus = ds.status === 1 ? 0 : 1
  const apply = async () => {
    try {
      await metadataV2Api.updateDataset(ds.id, { status: newStatus })
      ds.status = newStatus
      showToast(`数据集已${newStatus === 1 ? '启用' : '禁用'}`, 'success')
    } catch {
      showToast('状态更新失败', 'error')
    }
  }
  if (newStatus === 0) {
    openConfirm({
      title: '禁用数据集',
      message: `禁用后「${ds.display_name}」将不会被 AI 检索引用，确定禁用吗？`,
      type: 'warning',
      confirmText: '禁用',
      onConfirm: () => {
        confirmDialog.value.show = false
        apply()
      },
    })
    return
  }
  apply()
}

const fetchDatasets = async () => {
  loading.value = true
  try {
    const res = await metadataV2Api.getDatasets()
    datasets.value = res.data
    
    // 如果有正在同步的项目，开启短期轮询
    checkAndStartPolling()
  } catch (e) {
    console.error('Failed to fetch datasets', e)
    showToast('加载数据集失败', 'error')
  } finally {
    loading.value = false
  }
}

// 轮询管理
let pollTimer: any = null
const checkAndStartPolling = () => {
  const isSyncing = datasets.value.some(ds => ds.vector_status === 2)
  if (isSyncing && !pollTimer) {
    pollTimer = setInterval(async () => {
      try {
        const res = await metadataV2Api.getDatasets()
        datasets.value = res.data
        if (!datasets.value.some(ds => ds.vector_status === 2)) {
          stopPolling()
        }
      } catch (e) { stopPolling() }
    }, 3000)
  }
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const filteredDatasets = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return datasets.value.filter((ds) => {
    const matchesSearch =
      !q ||
      ds.name.toLowerCase().includes(q) ||
      ds.display_name.toLowerCase().includes(q) ||
      (ds.description || '').toLowerCase().includes(q) ||
      (ds.data_source || '').toLowerCase().includes(q) ||
      (ds.tags || []).some((t) => t.toLowerCase().includes(q))
    const matchesStatus = statusFilter.value === 'ALL' || String(ds.status) === statusFilter.value
    const matchesVector =
      vectorFilter.value === 'ALL' || String(ds.vector_status ?? 0) === vectorFilter.value
    const matchesDataSource =
      dataSourceFilter.value === 'ALL' || ds.data_source === dataSourceFilter.value
    return matchesSearch && matchesStatus && matchesVector && matchesDataSource
  })
})

const hasActiveFilters = computed(
  () =>
    !!searchQuery.value.trim() ||
    statusFilter.value !== 'ALL' ||
    vectorFilter.value !== 'ALL' ||
    dataSourceFilter.value !== 'ALL'
)

const dataSourceOptions = computed(() => {
  const set = new Set(datasets.value.map((d) => d.data_source).filter(Boolean))
  return Array.from(set).sort()
})

const stats = computed(() => {
  const total = datasets.value.length
  const active = datasets.value.filter((d) => d.status === 1).length
  const synced = datasets.value.filter((d) => d.vector_status === 1).length
  const pending = datasets.value.filter((d) => [0, 3, 4].includes(d.vector_status ?? 0)).length
  return { total, active, synced, pending }
})

/** 需要向量同步的数据集：已启用且未同步 / 失败 / 待更新 */
const datasetsNeedingVectorSync = computed(() =>
  datasets.value.filter(
    (d) => d.status === 1 && [0, 3, 4].includes(d.vector_status ?? 0)
  )
)

const bulkSyncing = ref(false)

const canBulkSync = computed(
  () =>
    canManage.value &&
    isAiEnabled.value &&
    isVectorSupported.value &&
    datasetsNeedingVectorSync.value.length > 0 &&
    !bulkSyncing.value
)

const openConfirm = (opts: {
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
    type: opts.type || 'warning',
    confirmText: opts.confirmText || '确认',
    onConfirm: opts.onConfirm,
  }
}

const openDeleteModal = (ds: Dataset) => {
  deletingDataset.value = ds
  showDeleteConfirm.value = true
}

const confirmDelete = async () => {
  if (!deletingDataset.value) return
  try {
    await metadataV2Api.deleteDataset(deletingDataset.value.id)
    showDeleteConfirm.value = false
    deletingDataset.value = null
    fetchDatasets()
    showToast('已永久删除该数据集', 'success')
  } catch (e) {
    showToast('删除失败', 'error')
  }
}

const handleSyncVector = async (ds: Dataset) => {
  if (!isAiEnabled.value) {
    showToast('AI 功能未开启，无法同步', 'warning')
    return
  }
  if (!isVectorSupported.value) {
    showToast('Redis 不支持向量搜索，无法同步', 'error')
    return
  }
  try {
    ds.vector_status = 2 // 立即切换为同步中状态
    await metadataV2Api.syncVector(ds.id)
    showToast(`数据集 ${ds.display_name} 向量化同步任务已启动`, 'success')
    checkAndStartPolling()
    setTimeout(fetchDatasets, 1500)
  } catch (e) {
    showToast('同步启动失败', 'error')
    ds.vector_status = 3
  }
}

const runBulkVectorSync = async () => {
  const targets = datasetsNeedingVectorSync.value
  if (targets.length === 0) return

  bulkSyncing.value = true
  let ok = 0
  let fail = 0
  for (const ds of targets) {
    try {
      ds.vector_status = 2
      await metadataV2Api.syncVector(ds.id)
      ok++
    } catch {
      ds.vector_status = 3
      fail++
    }
  }
  bulkSyncing.value = false
  checkAndStartPolling()
  setTimeout(fetchDatasets, 1500)

  if (fail === 0) {
    showToast(`已为 ${ok} 个数据集启动向量同步`, 'success')
  } else if (ok === 0) {
    showToast(`${fail} 个数据集同步启动失败`, 'error')
  } else {
    showToast(`已启动 ${ok} 个，${fail} 个失败`, 'warning')
  }
}

const handleSyncAllPending = () => {
  if (!isAiEnabled.value) {
    showToast('AI 功能未开启，无法同步', 'warning')
    return
  }
  if (!isVectorSupported.value) {
    showToast('Redis 不支持向量搜索，无法同步', 'error')
    return
  }
  const targets = datasetsNeedingVectorSync.value
  if (targets.length === 0) {
    showToast('没有需要同步的数据集', 'info')
    return
  }

  openConfirm({
    title: '一键同步向量',
    message: `将为 ${targets.length} 个已启用数据集启动向量同步（含未同步、待更新、同步失败）。任务在后台执行，请稍后刷新查看状态。`,
    type: 'info',
    confirmText: '开始同步',
    onConfirm: () => {
      confirmDialog.value.show = false
      runBulkVectorSync()
    },
  })
}

const getDatasetEmoji = (name: string) => {
  const emojis = ['📊', '📈', '💿', '🗄️', '🧠', '🧊', '🌊', '⚡']
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return emojis[Math.abs(hash) % emojis.length]
}

onMounted(() => {
  fetchDatasets()
  fetchDataSources()
  checkVectorSupport()
  checkAiStatus()
})

watch(viewMode, (mode) => {
  localStorage.setItem('metadata_view_mode', mode)
})

onUnmounted(stopPolling)
</script>

<template>
  <div class="space-y-6">
    <!-- AI Disabled Warning -->
    <div v-if="!isAiEnabled && !dismissAiWarning" class="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r-lg flex items-start justify-between gap-3 animate-in fade-in slide-in-from-top-2 duration-300">
      <div class="flex items-start gap-3">
        <div class="flex-shrink-0">
          <SparklesIcon class="h-5 w-5 text-amber-400" aria-hidden="true" />
        </div>
        <div>
          <p class="text-sm text-amber-700 font-bold">AI 功能未开启</p>
          <p class="text-xs text-amber-600 mt-1">
            当前系统 AI 模块已禁用。智能导入、自动描述润色及向量同步功能将不可用。
            <br>请在“系统设置”中启用 AI 模块以获得完整体验。
          </p>
        </div>
      </div>
      <button @click="dismissAiWarning = true" class="text-amber-400 hover:text-amber-600 transition-colors p-1">
        <XMarkIcon class="w-5 h-5" />
      </button>
    </div>

    <!-- Vector Support Warning -->
    <div v-if="isAiEnabled && !isVectorSupported" class="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r-lg flex items-start gap-3">
      <div class="flex-shrink-0">
        <ExclamationTriangleIcon class="h-5 w-5 text-amber-400" aria-hidden="true" />
      </div>
      <div>
        <p class="text-sm text-amber-700 font-bold">Redis 向量搜索不可用</p>
        <p class="text-xs text-amber-600 mt-1">
          检测到当前 Redis 实例不支持 RediSearch 模块。向量同步和语义检索功能已被禁用。
          <br>请升级到 <code class="bg-amber-100 px-1 py-0.5 rounded font-mono">redis/redis-stack</code> 镜像以启用完整 AI 能力。
        </p>
      </div>
    </div>

    <!-- Vector DB Warning -->
    <div v-if="isAiEnabled && isVectorSupported && vectorDbWarning" class="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-r-lg flex items-start gap-3 animate-in fade-in slide-in-from-left-2">
      <div class="flex-shrink-0">
        <InformationCircleIcon class="h-5 w-5 text-blue-400" aria-hidden="true" />
      </div>
      <div>
        <p class="text-sm text-blue-700 font-bold">Redis DB 配置风险提示</p>
        <p class="text-xs text-blue-600 mt-1">
          {{ vectorDbWarning }}
          <br>建议在配置文件中将 <code class="bg-blue-100 px-1 py-0.5 rounded font-mono">REDIS_DB</code> 设置为 0。
        </p>
      </div>
    </div>

    <!-- Header -->
    <div class="flex justify-between items-center">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <CircleStackIcon class="w-8 h-8 text-indigo-600" />
          语义元数据中心
        </h1>
        <p class="text-sm text-gray-500 mt-1">管理 AI 用于 Text2SQL 生成的业务知识库</p>
      </div>
      <div class="flex gap-2 flex-wrap">
        <button
          type="button"
          class="bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 px-3 py-2 rounded-lg transition-all flex items-center gap-2 font-medium text-sm shadow-sm"
          :disabled="loading"
          @click="fetchDatasets"
        >
          <ArrowPathIcon class="w-4 h-4" :class="loading ? 'animate-spin' : ''" />
          刷新
        </button>
        <button 
          v-if="canViewSimulator"
          @click="router.push('/dashboard/metadata/simulator')"
          class="bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 px-4 py-2 rounded-lg transition-all flex items-center gap-2 font-medium text-sm shadow-sm"
        >
          <BeakerIcon class="w-5 h-5 text-amber-500" />
          检索测试
        </button>
        <button 
          @click="showSpecModal = true"
          class="bg-white border border-indigo-100 text-indigo-600 hover:bg-indigo-50 px-4 py-2 rounded-lg transition-all flex items-center gap-2 font-medium text-sm shadow-sm"
        >
          <CommandLineIcon class="w-5 h-5" />
          设计规范
        </button>
        <button 
          v-if="canManage"
          @click="showImportModal = true"
          :disabled="!isAiEnabled"
          class="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg shadow-md transition-all active:scale-95 text-sm font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RocketLaunchIcon class="w-5 h-5" />
          智能导入
        </button>
        <button 
          v-if="canManage"
          @click="showCreateModal = true"
          class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg shadow-md transition-all active:scale-95 text-sm font-medium flex items-center gap-2"
        >
          <PlusIcon class="w-5 h-5" />
          新建数据集
        </button>
      </div>
    </div>

    <!-- Stats -->
    <div v-if="!loading && datasets.length > 0" class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="bg-white border border-gray-200 rounded-lg px-4 py-3">
        <p class="text-xs text-gray-500">全部数据集</p>
        <p class="text-2xl font-bold text-gray-900">{{ stats.total }}</p>
      </div>
      <div class="bg-white border border-green-200 rounded-lg px-4 py-3 bg-green-50/40">
        <p class="text-xs text-green-700">已启用</p>
        <p class="text-2xl font-bold text-green-700">{{ stats.active }}</p>
      </div>
      <div class="bg-white border border-emerald-200 rounded-lg px-4 py-3">
        <p class="text-xs text-emerald-700">向量已同步</p>
        <p class="text-2xl font-bold text-emerald-700">{{ stats.synced }}</p>
      </div>
      <div class="bg-white border border-amber-200 rounded-lg px-4 py-3 bg-amber-50/30">
        <div class="flex items-start justify-between gap-2">
          <div>
            <p class="text-xs text-amber-700">待同步/待更新</p>
            <p class="text-2xl font-bold text-amber-700">{{ stats.pending }}</p>
          </div>
          <button
            v-if="canManage && datasetsNeedingVectorSync.length > 0"
            type="button"
            class="shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :class="canBulkSync ? 'bg-amber-600 text-white hover:bg-amber-700' : 'bg-gray-200 text-gray-400 cursor-not-allowed'"
            :disabled="!canBulkSync"
            :title="!isAiEnabled ? 'AI 未开启' : !isVectorSupported ? '向量库不可用' : '同步所有待处理数据集'"
            @click="handleSyncAllPending"
          >
            <CloudArrowUpIcon class="w-3.5 h-3.5" :class="bulkSyncing ? 'animate-pulse' : ''" />
            {{ bulkSyncing ? '同步中...' : '一键同步' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="flex flex-col lg:flex-row justify-between items-stretch lg:items-center gap-4 bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
       <ClearableInput
          v-model="searchQuery"
          show-search-icon
          wrapper-class="flex-1 min-w-[200px] max-w-xl"
          input-class="py-2 sm:text-sm bg-gray-50"
          placeholder="搜索名称、编码、描述、数据源、标签..."
       />

       <div class="flex flex-wrap items-center gap-2">
          <select v-model="statusFilter" class="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white">
            <option value="ALL">全部状态</option>
            <option value="1">已启用</option>
            <option value="0">已禁用</option>
          </select>
          <select v-model="vectorFilter" class="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white">
            <option value="ALL">全部向量状态</option>
            <option value="1">已同步</option>
            <option value="0">未同步</option>
            <option value="4">待更新</option>
            <option value="2">同步中</option>
            <option value="3">同步失败</option>
          </select>
          <select v-if="dataSourceOptions.length > 1" v-model="dataSourceFilter" class="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white max-w-[160px]">
            <option value="ALL">全部数据源</option>
            <option v-for="ds in dataSourceOptions" :key="ds" :value="ds">{{ ds }}</option>
          </select>
          <button
            v-if="canManage && datasetsNeedingVectorSync.length > 0"
            type="button"
            class="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border transition-colors disabled:opacity-50"
            :class="canBulkSync ? 'border-amber-300 text-amber-800 bg-amber-50 hover:bg-amber-100' : 'border-gray-200 text-gray-400 bg-gray-50 cursor-not-allowed'"
            :disabled="!canBulkSync"
            @click="handleSyncAllPending"
          >
            <CloudArrowUpIcon class="w-4 h-4" />
            {{ bulkSyncing ? '批量同步中...' : `一键同步 (${datasetsNeedingVectorSync.length})` }}
          </button>
          <p v-if="hasActiveFilters" class="text-xs text-gray-400 whitespace-nowrap">
            {{ filteredDatasets.length }} / {{ datasets.length }} 项
          </p>
          <div class="flex bg-gray-100 p-1 rounded-lg ml-auto lg:ml-0">
            <button type="button" @click="viewMode = 'grid'" :class="viewMode === 'grid' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'" class="p-1.5 rounded-md transition-all" title="卡片视图"><Squares2X2Icon class="w-4 h-4" /></button>
            <button type="button" @click="viewMode = 'list'" :class="viewMode === 'list' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'" class="p-1.5 rounded-md transition-all" title="列表视图"><ListBulletIcon class="w-4 h-4" /></button>
          </div>
       </div>
    </div>

    <!-- Grid View -->
    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div v-for="i in 3" :key="i" class="h-64 bg-gray-100 rounded-xl animate-pulse"></div>
    </div>

    <div v-else-if="viewMode === 'grid' && filteredDatasets.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      <div 
        v-for="ds in filteredDatasets" :key="ds.id"
        class="bg-white rounded-2xl shadow-sm border border-gray-200 hover:shadow-md transition-all duration-300 cursor-pointer group flex flex-col"
        @click="router.push(`/dashboard/metadata/${ds.id}`)"
      >
        <div class="p-6 flex-1 flex flex-col">
           <div class="flex justify-between items-start mb-4">
              <div class="p-3 bg-indigo-50 rounded-xl text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition-all">
                <span class="text-2xl">{{ getDatasetEmoji(ds.name) }}</span>
              </div>
              <div class="flex items-center gap-1">
                <!-- Vector Sync Action -->
                <Tooltip 
                  v-if="canManage"
                  :text="!isAiEnabled ? 'AI 功能未开启' : 
                         !isVectorSupported ? 'Redis 不支持向量搜索' : 
                         ds.vector_status === 1 ? '已同步至语义库 (点击可重新同步)' : 
                         ds.vector_status === 2 ? '同步中... (点击可强制重试)' : 
                         ds.vector_status === 3 ? '同步失败 (点击重试)' : 
                         ds.vector_status === 4 ? '内容已变动，请点击更新语义库' :
                         '从未同步到语义库 (点击启动)'"
                  position="top"
                >
                  <button 
                    @click.stop="(isVectorSupported && isAiEnabled) ? handleSyncVector(ds) : null"
                    class="p-1.5 rounded-lg transition-all relative"
                    :class="[
                      (!isVectorSupported || !isAiEnabled) ? 'text-gray-300 cursor-not-allowed' :
                      ds.vector_status === 1 ? 'text-emerald-500 bg-emerald-50 hover:bg-emerald-100' : 
                      ds.vector_status === 2 ? 'text-blue-500 bg-blue-50 hover:bg-blue-100' :
                      ds.vector_status === 3 ? 'text-red-500 bg-red-50 hover:bg-red-100' :
                      ds.vector_status === 4 ? 'text-amber-500 bg-amber-50 hover:bg-amber-100 ring-1 ring-amber-200' :
                      'text-gray-400 bg-gray-50 hover:bg-gray-100'
                    ]"
                  >
                    <CloudArrowUpIcon v-if="ds.vector_status !== 4" class="w-5 h-5" :class="ds.vector_status === 2 ? 'animate-bounce-slow' : ''" />
                    <ExclamationTriangleIcon v-else class="w-5 h-5" />
                    <span v-if="ds.vector_status === 2" class="absolute -top-0.5 -right-0.5 w-2 h-2 bg-blue-500 rounded-full animate-ping"></span>
                  </button>
                </Tooltip>
                <button 
                  v-if="canManage"
                  @click.stop="openDeleteModal(ds)"
                  class="p-1.5 text-gray-400 hover:text-red-600 transition-colors"
                >
                  <TrashIcon class="w-5 h-5" />
                </button>
              </div>
           </div>

           <h3 class="text-lg font-bold text-gray-900 mb-1 truncate">{{ ds.display_name }}</h3>
           <p class="text-xs font-mono text-gray-400 mb-4 tracking-tight">#{{ ds.name }}</p>
           
           <div class="flex flex-wrap gap-2 mb-4">
              <div class="bg-gray-100 text-gray-600 px-2 py-1 rounded-lg text-[10px] font-bold border border-gray-200 uppercase font-mono flex items-center gap-1">
                <CircleStackIcon class="w-3 h-3 opacity-70" />
                {{ ds.data_source }}
              </div>
              <span
                class="px-2 py-1 rounded-lg text-[10px] font-bold ring-1"
                :class="getVectorMeta(ds.vector_status).class"
              >
                {{ getVectorMeta(ds.vector_status).label }}
              </span>
              <div class="bg-blue-50 text-blue-700 px-2 py-1 rounded-lg text-[10px] font-bold border border-blue-100">
                表:{{ ds.table_count || 0 }}
              </div>
              <div class="bg-amber-50 text-amber-700 px-2 py-1 rounded-lg text-[10px] font-bold border border-amber-100">
                指标:{{ ds.metric_count || 0 }}
              </div>
              <div class="bg-indigo-50 text-indigo-700 px-2 py-1 rounded-lg text-[10px] font-bold border border-indigo-100">
                接口:{{ ds.usage_count || 0 }}
              </div>
           </div>

           <p class="text-sm text-gray-500 line-clamp-2 leading-relaxed mb-4 flex-1">{{ ds.description || '无详细描述信息' }}</p>
           
           <div class="mt-auto pt-4 border-t border-gray-100 flex justify-between items-center">
              <!-- Left: Status Toggle -->
              <Tooltip 
                v-if="canManage"
                :text="`当前状态: ${ds.status === 1 ? '已启用 (可被 AI 检索)' : '已禁用 (AI 不可见)'}`"
                position="top"
              >
                <div 
                  class="flex items-center cursor-pointer group/toggle"
                  @click.stop="toggleStatus(ds)"
                >
                  <div 
                    class="relative inline-flex h-4 w-8 items-center rounded-full transition-colors duration-200 ease-in-out shadow-inner"
                    :class="ds.status === 1 ? 'bg-green-500' : 'bg-gray-300'"
                  >
                    <span
                      class="inline-block h-3 w-3 transform rounded-full bg-white transition-transform duration-200 ease-in-out shadow-md"
                      :class="ds.status === 1 ? 'translate-x-4.5' : 'translate-x-0.5'"
                    />
                  </div>
                </div>
              </Tooltip>
              <div v-else class="flex items-center">
                 <div class="h-2 w-2 rounded-full" :class="ds.status === 1 ? 'bg-green-500' : 'bg-gray-300'"></div>
              </div>
              
              <!-- Right: Creator & Time info (Professional Layout) -->
              <div class="flex items-center gap-3 text-[10px] text-gray-400 font-medium">
                 <div class="flex items-center gap-1">
                    <UserIcon class="w-3 h-3 text-indigo-400/60" />
                    <span>{{ ds.creator_name || '系统' }}</span>
                 </div>
                 <div class="flex items-center gap-1 border-l border-gray-100 pl-3">
                    <ClockIcon class="w-3 h-3 text-gray-300" />
                    <span>{{ ds.created_at ? new Date(ds.created_at).toLocaleDateString() : '长期' }}</span>
                 </div>
              </div>
           </div>
        </div>
      </div>
    </div>

    <!-- List View -->
    <div v-else-if="viewMode === 'list' && filteredDatasets.length > 0" class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
       <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50 text-xs font-bold text-gray-500 uppercase tracking-wider">
             <tr>
                <th class="px-6 py-4 text-left">数据集名称</th>
                <th class="px-6 py-4 text-left">创建人</th>
                <th class="px-6 py-4 text-left">关联数据源</th>
                <th class="px-6 py-4 text-center">启用</th>
                <th class="px-6 py-4 text-center">向量状态</th>
                <th class="px-6 py-4 text-center">统计</th>
                <th class="px-6 py-4 text-left">创建日期</th>
                <th class="px-6 py-4 text-right">操作</th>
             </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
             <tr v-for="ds in filteredDatasets" :key="ds.id" @click="router.push(`/dashboard/metadata/${ds.id}`)" class="hover:bg-gray-50 transition-colors cursor-pointer group">
                <td class="px-6 py-4">
                   <div class="flex items-center gap-3">
                      <span class="text-xl">{{ getDatasetEmoji(ds.name) }}</span>
                      <div>
                         <div class="text-sm font-bold text-gray-900">{{ ds.display_name }}</div>
                         <div class="text-xs text-gray-400 font-mono">{{ ds.name }}</div>
                      </div>
                   </div>
                </td>
                <td class="px-6 py-4">
                   <div class="flex items-center gap-2 text-xs text-gray-600 font-medium">
                      <div class="w-6 h-6 rounded-full bg-indigo-50 flex items-center justify-center text-[10px] text-indigo-600 font-black border border-indigo-100">
                        {{ (ds.creator_name || 'U').substring(0, 1).toUpperCase() }}
                      </div>
                      {{ ds.creator_name || '系统' }}
                   </div>
                </td>
                <td class="px-6 py-4">
                   <span class="px-2 py-1 bg-gray-100 text-gray-600 font-mono text-[10px] rounded border border-gray-200 uppercase font-bold flex items-center gap-1 w-fit">
                      <CircleStackIcon class="w-3 h-3 opacity-70" />
                      {{ ds.data_source }}
                   </span>
                </td>
                <td class="px-6 py-4 text-center">
                   <span
                     class="px-2 py-0.5 rounded text-[10px] font-bold border"
                     :class="ds.status === 1 ? 'bg-green-50 text-green-600 border-green-100' : 'bg-gray-50 text-gray-400 border-gray-200'"
                   >
                     {{ ds.status === 1 ? '已启用' : '已禁用' }}
                   </span>
                </td>
                <td class="px-6 py-4 text-center">
                   <span class="px-2 py-0.5 rounded text-[10px] font-bold ring-1" :class="getVectorMeta(ds.vector_status).class">
                     {{ getVectorMeta(ds.vector_status).label }}
                   </span>
                </td>
                <td class="px-6 py-4">
                   <div class="flex justify-center gap-2">
                      <span class="bg-blue-50 text-blue-700 px-2 py-0.5 rounded text-[10px] font-bold border border-blue-100">表:{{ ds.table_count || 0 }}</span>
                      <span class="bg-amber-50 text-amber-700 px-2 py-0.5 rounded text-[10px] font-bold border border-amber-100">指标:{{ ds.metric_count || 0 }}</span>
                      <span class="bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded text-[10px] font-bold border border-indigo-100">接口:{{ ds.usage_count || 0 }}</span>
                   </div>
                </td>
                <td class="px-6 py-4 text-xs text-gray-500 font-mono tracking-tighter">{{ ds.created_at ? new Date(ds.created_at).toLocaleDateString() : '-' }}</td>
                <td class="px-6 py-4 text-right" @click.stop>
                   <div class="flex justify-end gap-1">
                      <button
                        type="button"
                        class="px-2 py-1 text-xs text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-md"
                        @click="router.push(`/dashboard/metadata/${ds.id}`)"
                      >
                        详情
                      </button>
                      <Tooltip 
                        v-if="canManage"
                        :text="!isAiEnabled ? 'AI 功能未开启' : 
                               !isVectorSupported ? 'Redis 不支持向量搜索' : 
                               ds.vector_status === 1 ? '已同步' : 
                               ds.vector_status === 2 ? '同步中 (强制重试)' : 
                               ds.vector_status === 3 ? '失败' : 
                               ds.vector_status === 4 ? '待更新' : '未同步'"
                        position="left"
                      >
                        <button 
                          @click.stop="(isVectorSupported && isAiEnabled) ? handleSyncVector(ds) : null"
                          class="p-1.5 rounded-lg transition-all relative"
                          :class="[
                            (!isVectorSupported || !isAiEnabled) ? 'text-gray-300 cursor-not-allowed' :
                            ds.vector_status === 1 ? 'text-emerald-500 hover:bg-emerald-50' : 
                            ds.vector_status === 2 ? 'text-blue-500 hover:bg-blue-50' :
                            ds.vector_status === 3 ? 'text-red-500 hover:bg-red-50' :
                            ds.vector_status === 4 ? 'text-amber-500 bg-amber-50 hover:bg-amber-100 ring-1 ring-amber-200' :
                            'text-gray-400 hover:bg-gray-100'
                          ]"
                        >
                          <CloudArrowUpIcon v-if="ds.vector_status !== 4" class="w-5 h-5" :class="ds.vector_status === 2 ? 'animate-bounce-slow' : ''" />
                          <ExclamationTriangleIcon v-else class="w-5 h-5" />
                          <span v-if="ds.vector_status === 2" class="absolute -top-0.5 -right-0.5 w-2 h-2 bg-blue-500 rounded-full animate-ping"></span>
                        </button>
                      </Tooltip>
                      <button v-if="canManage" @click.stop="openDeleteModal(ds)" class="p-1.5 text-gray-400 hover:text-red-600 transition-colors"><TrashIcon class="w-5 h-5" /></button>
                   </div>
                </td>
             </tr>
          </tbody>
       </table>
    </div>

    <!-- No filter results -->
    <div v-else-if="!loading && datasets.length > 0 && filteredDatasets.length === 0" class="text-center py-16 bg-white rounded-xl border border-gray-200">
      <p class="text-gray-500 text-sm">没有匹配的数据集，请调整搜索或筛选条件</p>
      <button type="button" class="mt-3 text-sm text-indigo-600 hover:underline" @click="searchQuery = ''; statusFilter = 'ALL'; vectorFilter = 'ALL'; dataSourceFilter = 'ALL'">
        清除筛选
      </button>
    </div>

    <!-- Empty State -->
    <div v-else-if="!loading && datasets.length === 0" class="text-center py-24 bg-white rounded-3xl border-2 border-dashed border-gray-200">
      <div class="relative inline-block mb-6">
        <div class="w-24 h-24 bg-indigo-50 rounded-full flex items-center justify-center mx-auto text-5xl">📂</div>
        <div class="absolute -top-2 -right-2 w-8 h-8 bg-amber-400 rounded-lg flex items-center justify-center animate-bounce shadow-lg border-2 border-white">
           <SparklesIcon class="w-5 h-5 text-white" />
        </div>
      </div>
      <h3 class="text-xl font-black text-gray-900 tracking-tight">AI 的语义大脑还是空的</h3>
      <p class="text-sm text-gray-400 mt-2 mb-8 max-w-sm mx-auto">导入数据库 DDL 或手动创建数据集，为 AI 助手注入专业的业务知识和数据模型逻辑。</p>
      <button v-if="canManage" @click="showImportModal = true" class="bg-indigo-600 text-white px-10 py-3 rounded-xl hover:bg-indigo-700 transition shadow-xl font-bold active:scale-95">
        立即开启智能建模
      </button>
    </div>

    <SmartImportWizard :show="showImportModal" @close="showImportModal = false" @saved="fetchDatasets" />

    <!-- Create Modal (Aligned with Roles.vue - Compact) -->
    <div v-if="showCreateModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9990]" @click.self="showCreateModal = false">
      <div class="bg-white rounded-3xl shadow-2xl w-full max-w-2xl overflow-hidden transform transition-all flex flex-col">
        <div class="px-6 py-4 border-b bg-gray-50 flex justify-between items-center">
          <h2 class="text-lg font-bold text-gray-900">新建语义数据集</h2>
          <button @click="showCreateModal = false" class="text-gray-400 hover:text-gray-600 transition-colors"><XMarkIcon class="w-5 h-5" /></button>
        </div>
        <div class="p-6 space-y-4">
          <!-- Two Columns for basic fields -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1 ml-1">数据集编码</label>
              <input v-model="newDataset.name" class="w-full border border-gray-300 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" placeholder="如：ops_resources" />
            </div>
            <div>
              <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1 ml-1">显示名称</label>
              <input v-model="newDataset.display_name" class="w-full border border-gray-300 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" placeholder="如：资产管理数据集" />
            </div>
          </div>
          
          <div>
            <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1 ml-1">关联数据源</label>
            <select v-model="newDataset.data_source" class="w-full border border-gray-300 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all appearance-none bg-white">
               <option v-for="ds in availableDataSources" :key="ds.id" :value="ds.source_name">{{ ds.source_name }} ({{ ds.source_type }})</option>
            </select>
          </div>
          
          <div>
            <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1 ml-1">业务描述 (Description)</label>
            <textarea v-model="newDataset.description" class="w-full border border-gray-300 rounded-xl px-4 py-2 text-xs focus:ring-2 focus:ring-indigo-500 outline-none transition-all" rows="2" placeholder="简要描述业务逻辑内容..."></textarea>
          </div>
          
          <div>
            <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1 ml-1">标签管理</label>
            <div class="flex gap-2 mb-2">
              <input v-model="tagInput" @keyup.enter="addTag" class="flex-1 border border-gray-300 rounded-xl px-4 py-1.5 text-xs outline-none focus:ring-1 focus:ring-indigo-500" placeholder="按回车添加标签" />
            </div>
            <div class="flex flex-wrap gap-2 min-h-[24px]">
              <span v-for="(tag, i) in newDataset.tags" :key="i" class="px-2 py-0.5 bg-indigo-50 text-indigo-600 text-[10px] font-bold rounded-lg border border-indigo-100 flex items-center gap-1">
                {{ tag }}
                <button @click="removeTag(i)" class="hover:text-red-500">&times;</button>
              </span>
            </div>
          </div>
        </div>
        <div class="px-6 py-4 bg-gray-50 border-t flex justify-end gap-3">
          <button @click="showCreateModal = false" class="px-5 py-2 text-gray-500 font-bold hover:text-gray-700 transition-colors text-sm">取消</button>
          <button @click="handleCreate" :disabled="availableDataSources.length === 0" class="px-8 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-lg transition-all disabled:opacity-50 text-sm">确认创建</button>
        </div>
      </div>
    </div>

    <!-- Delete Modal (Aligned with Roles.vue) -->
    <div v-if="showDeleteConfirm" class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden transform transition-all animate-in zoom-in duration-200">
        <div class="p-6 text-center">
          <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 mb-4">
            <TrashIcon class="h-6 w-6 text-red-600" />
          </div>
          <h3 class="text-lg leading-6 font-bold text-gray-900 mb-2">确认删除数据集?</h3>
          <p class="text-sm text-gray-500 mb-6 leading-relaxed">
            您即将删除 <span class="font-bold text-gray-800">{{ deletingDataset?.display_name }}</span>。
            <br/><span class="text-red-500 font-bold">此操作不可撤销</span>，所有关联元数据将立即失效。
          </p>
          <div class="flex gap-3">
            <button @click="showDeleteConfirm = false" class="flex-1 py-2.5 bg-gray-100 text-gray-700 font-bold rounded-lg hover:bg-gray-200 transition-all text-sm">取消</button>
            <button @click="confirmDelete" class="flex-1 py-2.5 bg-red-600 text-white font-bold rounded-lg hover:bg-red-700 shadow-lg transition-all text-sm">确认删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Design Spec Modal (100% Replicated) -->
    <div v-if="showSpecModal" class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" @click.self="showSpecModal = false">
      <div class="bg-white rounded-[2rem] shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden border border-gray-100 animate-fade-in-up">
        <!-- Header -->
        <div class="p-6 border-b border-gray-100 flex justify-between items-center bg-purple-50/30">
          <div class="flex items-center gap-3">
             <div class="w-10 h-10 rounded-lg bg-purple-100 text-purple-600 flex items-center justify-center border border-purple-200">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>
             </div>
             <div>
               <h2 class="text-xl font-bold text-gray-900">元数据设计规范 (Semantic Layer Spec)</h2>
               <p class="text-xs text-gray-500 font-medium">构建 AI 可理解的业务语义层，提升 Text-to-SQL 准确率。</p>
             </div>
          </div>
          <button @click="showSpecModal = false" class="text-gray-400 hover:text-gray-600 transition-colors">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>

        <!-- Tabs -->
        <div class="flex border-b border-gray-200 bg-white px-6">
           <button 
             v-for="tab in ['concept', 'structure', 'fields', 'practice']" 
             :key="tab"
             @click="activeSpecTab = tab"
             class="px-4 py-3 text-sm font-medium border-b-2 transition-colors capitalize"
             :class="activeSpecTab === tab ? 'border-purple-600 text-purple-700' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
           >
             {{ tab === 'concept' ? '核心理念 (Concepts)' : 
                tab === 'structure' ? 'YAML 结构 (Schema)' : 
                tab === 'fields' ? '字段规范 (Fields)' : '最佳实践 (Best Practice)' }}
           </button>
        </div>

        <!-- Content -->
        <div class="flex-1 overflow-y-auto p-8 bg-gray-50/50 custom-scrollbar">
           
           <!-- Tab 1: Concepts -->
           <div v-if="activeSpecTab === 'concept'" class="space-y-6 max-w-4xl mx-auto">
              <div class="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg">
                 <h3 class="font-bold text-blue-800 mb-2">为什么需要 Semantic Layer?</h3>
                 <p class="text-sm text-blue-700 leading-relaxed">
                    单纯依赖数据库 Schema (DDL) 是不够的。大模型不知道 "pue" 代表 "能源利用效率"，也不知道 "status=1" 代表 "正常"。
                    元数据层通过注入<b>业务语义</b>、<b>枚举含义</b>和<b>计算逻辑</b>，弥补了这一鸿沟。
                 </p>
              </div>
              
              <div class="grid grid-cols-2 gap-6">
                 <div class="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
                    <div class="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center text-green-600 mb-3 font-bold text-xs">1</div>
                    <h4 class="font-bold text-gray-900 mb-2 text-sm">这是什么? (Definition)</h4>
                    <p class="text-xs text-gray-500 leading-relaxed">不仅提供表名，还提供通俗易懂的业务术语和描述。例如：将 `metrics_table` 标记为 "实时能耗监控表"。</p>
                 </div>
                 <div class="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
                    <div class="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-600 mb-3 font-bold text-xs">2</div>
                    <h4 class="font-bold text-gray-900 mb-2 text-sm">有哪些值? (Enums)</h4>
                    <p class="text-xs text-gray-500 leading-relaxed">对于分类字段（Status/Type），显式列出所有可能的枚举值及其含义。防止 AI 幻觉生成不存在的状态码。</p>
                 </div>
                 <div class="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
                    <div class="w-8 h-8 bg-amber-100 rounded-full flex items-center justify-center text-amber-600 mb-3 font-bold text-xs">3</div>
                    <h4 class="font-bold text-gray-900 mb-2 text-sm">什么关系? (Relationships)</h4>
                    <p class="text-xs text-gray-500 leading-relaxed">定义跨表的 Join 路径。即使数据库没有外键约束，这里也要告诉 AI 哪两个字段是可以关联的。</p>
                 </div>
                 <div class="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
                    <div class="w-8 h-8 bg-rose-100 rounded-full flex items-center justify-center text-rose-600 mb-3 font-bold text-xs">4</div>
                    <h4 class="font-bold text-gray-900 mb-2 text-sm">怎么计算? (Metrics)</h4>
                    <p class="text-xs text-gray-500 leading-relaxed">预定义复杂的计算公式（如 PUE 计算、同比环比）。AI 只需引用指标名，无需重写复杂 SQL。</p>
                 </div>
              </div>
           </div>

           <!-- Tab 2: Structure -->
           <div v-else-if="activeSpecTab === 'structure'" class="max-w-4xl mx-auto">
              <div class="bg-slate-900 rounded-xl overflow-hidden border border-slate-700 shadow-lg">
                 <div class="bg-slate-800 px-4 py-2 flex justify-between items-center border-b border-slate-700">
                    <span class="text-xs font-mono text-slate-400">sample_metadata.yaml</span>
                    <span class="text-[10px] text-slate-500 uppercase font-black">YAML Structure</span>
                 </div>
                 <pre class="p-6 text-sm font-mono text-emerald-400 overflow-x-auto leading-relaxed">version: "1.0"
domain: "IDC_Energy" 
entities:
  - name: "metrics_realtime"
    term: "实时能耗指标表"
    description: "存储各机房实时电力数据，每分钟更新。"
    synonyms: ["实时数据", "监控表"]
    columns:
      - name: "pue"
        term: "PUE值"
        type: "float"
        description: "越低越好 (Total Power / IT Power)"
        examples: [1.2, 1.5]
        
      - name: "room_id"
        term: "机房ID"
        foreign_key: "rooms.id"

      - name: "metric_type"
        term: "指标类型"
        enums:
          - value: "voltage"
            description: "电压 (V)"
          - value: "current"
            description: "电流 (A)"

business_metrics:
  - name: "avg_pue"
    display_name: "平均PUE"
    logic: "AVG(pue)"
    desc: "统计周期内的能效平均值"
  - name: "total_power"
    display_name: "总用电量"
    logic: "SUM(power_consumption)"
    desc: "物理电表累计读数"

relationships:
  - source: "metrics_realtime.room_id"
    target: "rooms.id"
    type: "many_to_one"
    description: "指标归属机房"</pre>
              </div>
           </div>

           <!-- Tab 3: Fields -->
           <div v-else-if="activeSpecTab === 'fields'" class="max-w-4xl mx-auto space-y-6">
              <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
                 <table class="min-w-full text-sm text-left">
                    <thead class="bg-gray-50 text-gray-700 font-bold uppercase text-[10px] tracking-widest">
                       <tr>
                          <th class="px-6 py-4 border-b">Scope</th>
                          <th class="px-6 py-4 border-b">Field</th>
                          <th class="px-6 py-4 border-b">Required</th>
                          <th class="px-6 py-4 border-b">Description</th>
                       </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100 text-xs">
                       <tr class="hover:bg-gray-50 transition-colors">
                          <td class="px-6 py-4 font-bold text-gray-900 bg-gray-50/30" rowspan="4">Entity (Table)</td>
                          <td class="px-6 py-4 font-mono text-purple-600 font-bold">name</td>
                          <td class="px-6 py-4 text-red-500 font-black">YES</td>
                          <td class="px-6 py-4 text-gray-500">数据库物理表名 (e.g. `res_room`)</td>
                       </tr>
                       <tr class="hover:bg-gray-50 transition-colors">
                          <td class="px-6 py-4 font-mono text-purple-600 font-bold">term</td>
                          <td class="px-6 py-4 text-red-500 font-black">YES</td>
                          <td class="px-6 py-4 text-gray-500">业务术语 (e.g. "机房基础信息表")</td>
                       </tr>
                       <tr class="hover:bg-gray-50 transition-colors">
                          <td class="px-6 py-4 font-mono text-purple-600 font-bold">description</td>
                          <td class="px-6 py-4 text-red-500 font-black">YES</td>
                          <td class="px-6 py-4 text-gray-500">详细描述，包含数据粒度、更新频率等</td>
                       </tr>
                       <tr class="hover:bg-gray-50 transition-colors">
                          <td class="px-6 py-4 font-mono text-purple-600 font-bold">synonyms</td>
                          <td class="px-6 py-4 text-gray-400">Optional</td>
                          <td class="px-6 py-4 text-gray-500">同义词列表，用于增强 RAG 检索命中率</td>
                       </tr>

                       <!-- Columns -->
                       <tr class="hover:bg-gray-50 transition-colors">
                          <td class="px-6 py-4 font-bold text-gray-900 bg-indigo-50/20" rowspan="4">Column (Field)</td>
                          <td class="px-6 py-4 font-mono text-blue-600 font-bold">name / term</td>
                          <td class="px-6 py-4 text-red-500 font-black">YES</td>
                          <td class="px-6 py-4 text-gray-500">物理列名与业务术语</td>
                       </tr>
                       <tr class="hover:bg-gray-50 transition-colors">
                          <td class="px-6 py-4 font-mono text-blue-600 font-bold">enums</td>
                          <td class="px-6 py-4 text-amber-600 font-black">VITAL</td>
                          <td class="px-6 py-4 text-gray-500">枚举值列表。极大地帮助 LLM 生成正确的 WHERE 条件。</td>
                       </tr>
                       <tr class="hover:bg-gray-50 transition-colors">
                          <td class="px-6 py-4 font-mono text-blue-600 font-bold">examples</td>
                          <td class="px-6 py-4 text-gray-400">Optional</td>
                          <td class="px-6 py-4 text-gray-500">典型值示例 (Few-shot)，帮助 AI 锚定查询格式。</td>
                       </tr>
                       <tr class="hover:bg-gray-50 transition-colors">
                          <td class="px-6 py-4 font-mono text-blue-600 font-bold">foreign_key</td>
                          <td class="px-6 py-4 text-gray-400">Optional</td>
                          <td class="px-6 py-4 text-gray-500">显式关联指针 (e.g. `rooms.id`)</td>
                       </tr>
                    </tbody>
                 </table>
              </div>
           </div>

           <!-- Tab 4: Practice -->
           <div v-else-if="activeSpecTab === 'practice'" class="max-w-4xl mx-auto space-y-10">
              <section>
                 <h3 class="text-base font-black text-gray-900 mb-4 flex items-center gap-2">
                    <span class="w-1 h-5 bg-purple-600 rounded-full"></span>
                    📂 文件组织与命名建议
                 </h3>
                 <div class="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
                    <p class="text-sm text-gray-600 mb-6">
                       建议采用 <b>按业务域 (Domain-Driven)</b> 分组的策略。将逻辑紧密相关的表定义在同一个数据集（Dataset）中。
                    </p>
                    <div class="grid grid-cols-2 gap-6 text-xs">
                       <div class="bg-emerald-50 p-4 rounded-xl border border-emerald-100">
                          <h5 class="font-black text-emerald-700 uppercase mb-3 flex items-center gap-2">
                             <CheckCircleIcon class="w-4 h-4" /> 推荐做法
                          </h5>
                          <ul class="space-y-2 text-emerald-800 font-medium">
                             <li>• meta/billing_core.yaml (计费核心)</li>
                             <li>• meta/resource_ops.yaml (运维资源)</li>
                             <li>• 物理名保持原样，业务名尽量简短</li>
                          </ul>
                       </div>
                       <div class="bg-rose-50 p-4 rounded-xl border border-rose-100">
                          <h5 class="font-black text-rose-700 uppercase mb-3 flex items-center gap-2">
                             <XMarkIcon class="w-4 h-4" /> 避免做法
                          </h5>
                          <ul class="space-y-2 text-rose-800 font-medium">
                             <li>• 🚫 整个数据库合并为一个大文件</li>
                             <li>• 🚫 一张表单独作为一个数据集</li>
                             <li>• 🚫 在描述中使用模糊的“该表记录了一些信息”</li>
                          </ul>
                       </div>
                    </div>
                 </div>
              </section>

              <section>
                 <h3 class="text-base font-black text-gray-900 mb-4 flex items-center gap-2">
                    <span class="w-1 h-5 bg-indigo-600 rounded-full"></span>
                    🤖 AI 检索与召回路径 (Workflow)
                 </h3>
                 <div class="bg-indigo-50/50 p-8 rounded-2xl border border-indigo-100 relative overflow-hidden">
                    <div class="absolute top-0 right-0 p-4 opacity-10">
                       <CommandLineIcon class="w-32 h-32" />
                    </div>
                    <ol class="relative space-y-8">
                       <li class="flex items-start gap-4">
                          <span class="flex-shrink-0 w-6 h-6 bg-indigo-600 text-white rounded-full flex items-center justify-center text-xs font-black">1</span>
                          <div>
                             <h4 class="font-black text-gray-900 text-sm">用户提问解析</h4>
                             <p class="text-xs text-gray-500 mt-1 leading-relaxed">系统接收自然语言（如：“查一下上个月上海机房的电费”），提取关键词“上海机房”、“电费”。</p>
                          </div>
                       </li>
                       <li class="flex items-start gap-4">
                          <span class="flex-shrink-0 w-6 h-6 bg-indigo-600 text-white rounded-full flex items-center justify-center text-xs font-black">2</span>
                          <div>
                             <h4 class="font-black text-gray-900 text-sm">语义检索 (Retrieval)</h4>
                             <p class="text-xs text-gray-500 mt-1 leading-relaxed">在向量库中命中对应的表片段 `res_room` 和 `bill_details` 的 YAML 定义。</p>
                          </div>
                       </li>
                       <li class="flex items-start gap-4">
                          <span class="flex-shrink-0 w-6 h-6 bg-indigo-600 text-white rounded-full flex items-center justify-center text-xs font-black">3</span>
                          <div>
                             <h4 class="font-black text-gray-900 text-sm">上下文注入 (Injection)</h4>
                             <p class="text-xs text-gray-500 mt-1 leading-relaxed">
                                AI 仅获得 <b>命中的这几张表</b> 的详细字段语义。精简的上下文极大提升了生成 SQL 的成功率并降低了 Token 成本。
                             </p>
                          </div>
                       </li>
                    </ol>
                 </div>
              </section>
           </div>

        </div>
        
        <div class="px-8 py-6 bg-gray-50 border-t flex justify-end">
           <button @click="showSpecModal = false" class="px-8 py-2.5 bg-indigo-600 text-white font-bold rounded-xl shadow-lg hover:bg-indigo-700 transition-all text-sm">已深度了解设计规范</button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :show="confirmDialog.show"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :type="confirmDialog.type"
      :confirm-text="confirmDialog.confirmText"
      @confirm="confirmDialog.onConfirm()"
      @cancel="confirmDialog.show = false"
    />
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: #f1f1f1; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
</style>
