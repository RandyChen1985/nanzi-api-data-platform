<script setup lang="ts">
import { ref, onMounted, computed, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { metadataV2Api } from '../api/metadata_v2'
import axios from '../utils/axios'
import {
  DocumentDuplicateIcon, CommandLineIcon,
  CircleStackIcon, UserIcon,
  PlusIcon, PencilSquareIcon, TrashIcon, XMarkIcon, ClockIcon,
  ShareIcon, HeartIcon, ExclamationCircleIcon, CheckCircleIcon,
  ShieldCheckIcon, ArrowPathIcon, InformationCircleIcon
} from '@heroicons/vue/24/outline'
import { useToast } from '../composables/useToast'
import { copyToClipboard } from '@/utils/clipboard'

// Components
import MetricList from '../components/metadata/MetricList.vue'
import RelationshipList from '../components/metadata/RelationshipList.vue'
import SchemaGraph from '../components/metadata/SchemaGraph.vue'
import ApiUsageList from '../components/metadata/ApiUsageList.vue'
import SmartImportWizard from '../components/metadata/SmartImportWizard.vue'
import ClearableInput from '../components/common/ClearableInput.vue'

const route = useRoute()
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

const datasetId = Number(route.params.id)

const dataset = ref<any>(null)
const tables = ref<any[]>([])
const loading = ref(false)
const activeTab = ref('tables')
const searchQuery = ref('')
const showEditModal = ref(false)
const showYamlModal = ref(false)
const showImportModal = ref(false)
const showDatasetEditModal = ref(false)
const showHealthModal = ref(false)
const showDescriptionModal = ref(false)
const yamlContent = ref('')
const editingTable = ref<any>(null)
const columnListRef = ref<HTMLElement | null>(null)
const aiGeneratingDesc = ref(false)
const aiEnriching = ref(false)
const refreshingHealth = ref(false)
const isAiEnabled = ref(true)

const checkAiStatus = async () => {
  try {
    const res = await axios.get('/api/portal/system/config/ai')
    isAiEnabled.value = String(res.data.enabled).toLowerCase() === 'true'
  } catch (e) {
    isAiEnabled.value = false
  }
}

const handleHealthCheck = async () => {
  if (refreshingHealth.value) return
  refreshingHealth.value = true
  try {
    await axios.post(`/api/portal/meta/v2/datasets/${datasetId}/health-check`)
    showToast('健康检查评估完成', 'success')
    fetchData()
  } catch (e) {
    showToast('评估失败', 'error')
  } finally {
    refreshingHealth.value = false
  }
}

// Table Delete State
const showTableDeleteConfirm = ref(false)
const deletingTable = ref<any>(null)

// Dataset Edit State
const editDatasetForm = ref({
  display_name: '',
  description: '',
  tags: [] as string[]
})
const tagInput = ref('')

const fetchData = async () => {
  loading.value = true
  try {
    const res = await metadataV2Api.getDataset(datasetId)
    const rawData = res.data
    dataset.value = rawData
    tables.value = rawData.tables || []
    
    // Fetch usage count separately
    const usageRes = await metadataV2Api.getDatasetUsage(datasetId)
    dataset.value.usage_count = usageRes.data.data.length
    
    // Initialize edit form
    editDatasetForm.value = {
      display_name: rawData.display_name,
      description: rawData.description,
      tags: Array.isArray(rawData.tags) ? rawData.tags : []
    }
  } catch (e) {
    console.error('Failed to fetch dataset', e)
    showToast('加载数据集失败', 'error')
  } finally {
    loading.value = false
  }
}

const filteredTables = computed(() => {
  if (!searchQuery.value) return tables.value
  const q = searchQuery.value.toLowerCase()
  return tables.value.filter((t: any) => 
    t.physical_name.toLowerCase().includes(q) || 
    (t.term && t.term.toLowerCase().includes(q))
  )
})

const existingTableNames = computed(() => tables.value.map((t: any) => t.physical_name))

const openEditModal = (table: any) => {
  editingTable.value = JSON.parse(JSON.stringify(table))
  showEditModal.value = true
}

const openCreateModal = () => {
  editingTable.value = {
    physical_name: '',
    term: '',
    description: '',
    synonyms: [],
    columns: []
  }
  showEditModal.value = true
}

const handleAiEnrich = async () => {
  if (aiEnriching.value) return
  aiEnriching.value = true
  try {
    await axios.post(`/api/portal/meta/v2/datasets/${datasetId}/ai-enrich`)
    showToast('AI 已自动填充缺失元数据', 'success')
    fetchData()
  } catch (e) {
    showToast('AI 自动修复失败', 'error')
  } finally {
    aiEnriching.value = false
  }
}

const handleUpdateTable = async () => {
  if (!editingTable.value) return
  
  // 严格校验表级信息
  if (!editingTable.value.physical_name?.trim()) {
    showToast('物理表名为必填项', 'warning')
    return
  }

  // 严格校验字段合法性
  const invalidCol = editingTable.value.columns.find((c: any) => !c.physical_name?.trim() || !c.term?.trim())
  if (invalidCol) {
    showToast('所有字段的“物理名”和“业务术语”均为必填项', 'warning')
    return
  }

  try {
    await metadataV2Api.saveTable(datasetId, editingTable.value)
    showEditModal.value = false
    editingTable.value = null
    fetchData()
    showToast('更新成功', 'success')
  } catch (e) {
    showToast('更新失败', 'error')
  }
}

const handleUpdateDataset = async () => {
  try {
    await metadataV2Api.updateDataset(datasetId, editDatasetForm.value)
    showDatasetEditModal.value = false
    fetchData()
    showToast('数据集配置已更新', 'success')
  } catch (e) {
    showToast('更新失败', 'error')
  }
}

const addTag = () => {
  if (tagInput.value && !editDatasetForm.value.tags.includes(tagInput.value)) {
    editDatasetForm.value.tags.push(tagInput.value)
    tagInput.value = ''
  }
}

const removeTag = (idx: number) => {
  editDatasetForm.value.tags.splice(idx, 1)
}

const fetchYaml = async () => {
  try {
    const res = await metadataV2Api.getDatasetYaml(datasetId)
    yamlContent.value = res.data.data
    showYamlModal.value = true
  } catch (e) {
    showToast('获取 YAML 失败', 'error')
  }
}

const copyYaml = async () => {
  const success = await copyToClipboard(yamlContent.value)
  if (success) {
    showToast('YAML 内容已复制', 'success')
  } else {
    showToast('复制失败', 'error')
  }
}

const addColumn = () => {
  if (!editingTable.value) return
  editingTable.value.columns.push({
    physical_name: '', term: '', type: 'String', description: '', enums: [], synonyms: []
  })
  
  // 自动滚动到最下方
  nextTick(() => {
    if (columnListRef.value) {
      columnListRef.value.scrollTop = columnListRef.value.scrollHeight
    }
  })
}

const removeColumn = (idx: any) => {
  editingTable.value.columns.splice(idx, 1)
}

const suggestDescription = async (target: 'table' | 'column', columnIdx?: number) => {
  if (!editingTable.value) return
  
  const payload: any = {}
  if (target === 'table') {
    payload.type = 'table'
    payload.name = editingTable.value.physical_name
    payload.term = editingTable.value.term
  } else if (columnIdx !== undefined) {
    const col = editingTable.value.columns[columnIdx]
    payload.type = 'column'
    payload.name = col.physical_name
    payload.term = col.term
    payload.table_name = editingTable.value.physical_name
  }

  const colIdx = columnIdx // Alias for closure
  
  aiGeneratingDesc.value = true
  try {
    const res = await axios.post('/api/portal/meta/v2/ai/suggest-description', payload)
    if (target === 'table') {
      editingTable.value.description = res.data.description
    } else if (colIdx !== undefined) {
      editingTable.value.columns[colIdx].description = res.data.description
    }
    showToast('AI 已完成润色', 'success')
  } catch (e) {
    showToast('AI 生成失败', 'error')
  } finally {
    aiGeneratingDesc.value = false
  }
}

const openTableDeleteModal = (table: any) => {
  deletingTable.value = table
  showTableDeleteConfirm.value = true
}

const confirmTableDelete = async () => {
  if (!deletingTable.value) return
  try {
    await metadataV2Api.deleteTable(datasetId, deletingTable.value.id)
    showToast('数据表定义已移除', 'success')
    showTableDeleteConfirm.value = false
    deletingTable.value = null
    fetchData()
  } catch (e) {
    showToast('移除失败', 'error')
  }
}

const getDatasetEmoji = (name: string) => {
  const emojis = ['📊', '📈', '💿', '🗄️', '🧠', '🧊', '🌊', '⚡']
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return emojis[Math.abs(hash) % emojis.length]
}

onMounted(() => {
  fetchData()
  checkAiStatus()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Breadcrumbs -->
    <nav class="flex mb-4 text-sm" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-2">
        <li>
          <router-link to="/dashboard/metadata" class="text-gray-400 hover:text-indigo-600 transition-colors flex items-center gap-1">
            <CircleStackIcon class="w-4 h-4" /> 元数据管理
          </router-link>
        </li>
        <li class="flex items-center gap-2">
          <svg class="w-4 h-4 text-gray-300" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"></path></svg>
          <span class="text-gray-900 font-bold">{{ dataset?.display_name || '数据集详情' }}</span>
        </li>
      </ol>
    </nav>

    <!-- Header Card -->
    <div v-if="dataset" class="bg-white p-6 rounded-2xl shadow-sm border border-gray-200 relative overflow-hidden flex justify-between items-center">
      <div class="absolute top-0 left-0 right-0 h-1 bg-indigo-600"></div>
      
      <div class="flex items-center gap-5 flex-1 min-w-0">
        <div class="w-16 h-16 rounded-xl bg-indigo-50 flex-shrink-0 flex items-center justify-center text-3xl shadow-inner border border-indigo-100">
          {{ getDatasetEmoji(dataset.name) }}
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-bold text-gray-900 truncate">{{ dataset.display_name }}</h1>
            <span class="px-2 py-0.5 bg-gray-100 text-gray-500 text-xs font-mono rounded flex-shrink-0">#{{ dataset.name }}</span>
            
            <!-- Health Score Badge -->
            <button @click="showHealthModal = true" 
              class="flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all hover:scale-105 active:scale-95 shadow-sm flex-shrink-0"
              :class="[
                dataset.health_score >= 80 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                dataset.health_score >= 60 ? 'bg-amber-50 text-amber-700 border-amber-200' :
                'bg-red-50 text-red-700 border-red-200'
              ]"
            >
              <HeartIcon class="w-3.5 h-3.5" :class="dataset.health_score < 60 ? 'animate-pulse' : ''" />
              <span class="text-xs font-black">AI 准备度: {{ dataset.health_score || 0 }}分</span>
            </button>
          </div>
          <p class="text-sm text-gray-500 mt-1 max-w-4xl leading-relaxed">
            <template v-if="dataset.description && dataset.description.length > 120">
              {{ dataset.description.slice(0, 120) }}...
              <button @click="showDescriptionModal = true" class="text-indigo-600 hover:text-indigo-700 font-bold ml-1 inline-flex items-center gap-0.5 whitespace-nowrap">
                [详情]
              </button>
            </template>
            <template v-else>
              {{ dataset.description || '暂无详细描述' }}
            </template>
          </p>
          <div class="flex items-center gap-4 mt-2 text-xs text-gray-400 font-mono">
             <span class="flex items-center gap-1">
               <CircleStackIcon class="w-3.5 h-3.5" /> {{ dataset.data_source }}
             </span>
             <span class="flex items-center gap-1">
               <UserIcon class="w-3.5 h-3.5 text-indigo-400/60" /> {{ dataset.creator_name || '系统' }}
             </span>
             <span class="flex items-center gap-1">
               <ClockIcon class="w-3.5 h-3.5 text-gray-300" /> {{ dataset.created_at ? new Date(dataset.created_at).toLocaleDateString() : '长期有效' }}
             </span>
          </div>
        </div>
      </div>

      <div class="flex gap-3 ml-8 flex-shrink-0 items-center">
        <button v-if="hasPerm('element:metadata:manage')" @click="showDatasetEditModal = true" class="bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 px-4 py-2.5 rounded-xl transition-all flex items-center gap-2 text-sm font-bold whitespace-nowrap shadow-sm active:scale-95">
          <PencilSquareIcon class="w-4 h-4 text-indigo-500" /> 编辑数据集
        </button>
        <button @click="fetchYaml" :disabled="!isAiEnabled" class="bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 px-4 py-2.5 rounded-xl transition-all flex items-center gap-2 text-sm font-bold whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed shadow-sm active:scale-95">
          <CommandLineIcon class="w-4 h-4 text-purple-500" /> AI YAML
        </button>
        <button v-if="hasPerm('element:metadata:manage')" @click="showImportModal = true" :disabled="!isAiEnabled" class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl transition shadow-md flex items-center gap-2 text-sm font-bold whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed active:scale-95">
          <ShareIcon class="w-4 h-4" /> 导入 DDL
        </button>
      </div>
    </div>

    <!-- Tabs -->
    <div class="border-b border-gray-200 bg-white rounded-t-2xl">
      <nav class="-mb-px flex space-x-8 px-8" aria-label="Tabs">
        <button @click="activeTab = 'tables'" :class="activeTab === 'tables' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'" class="whitespace-nowrap py-4 px-1 border-b-2 font-bold text-sm transition-all flex items-center gap-2">
          数据表 (Tables) <span class="bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full text-[10px]">{{ tables.length }}</span>
        </button>
        <button @click="activeTab = 'metrics'" :class="activeTab === 'metrics' ? 'border-amber-500 text-amber-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'" class="whitespace-nowrap py-4 px-1 border-b-2 font-bold text-sm transition-all flex items-center gap-2">
          业务指标 (Metrics) <span class="bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full text-[10px]">{{ dataset?.metrics?.length || 0 }}</span>
        </button>
        <button @click="activeTab = 'relationships'" :class="activeTab === 'relationships' ? 'border-purple-500 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'" class="whitespace-nowrap py-4 px-1 border-b-2 font-bold text-sm transition-all flex items-center gap-2">
          实体关系 (Relationships) <span class="bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full text-[10px]">{{ dataset?.relationships?.length || 0 }}</span>
        </button>
        <button @click="activeTab = 'visualization'" :class="activeTab === 'visualization' ? 'border-emerald-500 text-emerald-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'" class="whitespace-nowrap py-4 px-1 border-b-2 font-bold text-sm transition-all flex items-center gap-2">
          <ShareIcon class="w-4 h-4" /> 可视化 (Visual)
        </button>
        <button @click="activeTab = 'usage'" :class="activeTab === 'usage' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'" class="whitespace-nowrap py-4 px-1 border-b-2 font-bold text-sm transition-all flex items-center gap-2">
          API 接口 (Usage) <span class="bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full text-[10px]">{{ dataset?.usage_count || 0 }}</span>
        </button>
      </nav>
    </div>

    <div class="bg-white p-6 rounded-b-2xl border border-t-0 border-gray-200 shadow-sm min-h-[500px]">
        <!-- Tables Tab -->
        <div v-show="activeTab === 'tables'" class="space-y-6">
          <div class="flex justify-between items-center px-1">
            <ClearableInput
              v-model="searchQuery"
              show-search-icon
              wrapper-class="w-80"
              input-class="py-2 text-sm font-medium bg-gray-50"
              placeholder="搜索物理表名或术语..."
            />
            <button v-if="hasPerm('element:metadata:manage')" @click="openCreateModal" class="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg transition-all shadow-md flex items-center gap-2 text-sm font-bold active:scale-95">
               <PlusIcon class="w-5 h-5" /> 新建数据表
            </button>
          </div>

          <div v-if="loading" class="py-20 text-center text-gray-400">
             <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto mb-2"></div>
             <p class="text-xs">加载元数据中...</p>
          </div>

          <div v-else class="grid grid-cols-1 gap-4">
            <div v-for="table in filteredTables" :key="table.id" class="bg-white border border-gray-200 p-5 rounded-xl hover:shadow-md transition-all group">
               <div class="flex justify-between items-start mb-4">
                  <div>
                     <div class="flex items-center gap-3">
                        <h3 class="text-base font-bold text-gray-900">{{ table.physical_name }}</h3>
                        <span class="px-1.5 py-0.5 bg-indigo-50 text-indigo-600 text-[10px] font-bold rounded border border-indigo-100 uppercase">{{ table.term || '未命名' }}</span>
                        
                        <div class="flex items-center gap-3 text-[10px] text-gray-400">
                           <div class="flex items-center gap-1">
                              <UserIcon class="w-3 h-3 text-indigo-400/60" />
                              <span>{{ table.creator_name || '系统' }}</span>
                           </div>
                           <div class="flex items-center gap-1 border-l border-gray-100 pl-3">
                              <ClockIcon class="w-3 h-3 text-gray-300" />
                              <span>{{ table.created_at ? new Date(table.created_at).toLocaleDateString() : '长期' }}</span>
                           </div>
                        </div>
                     </div>
                     <p class="text-xs text-gray-500 mt-1 line-clamp-1">{{ table.description || '暂无描述' }}</p>
                  </div>
                  <div v-if="hasPerm('element:metadata:manage')" class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                     <button @click="openEditModal(table)" class="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all" title="编辑映射"><PencilSquareIcon class="w-5 h-5" /></button>
                     <button @click="openTableDeleteModal(table)" class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all" title="删除表定义"><TrashIcon class="w-5 h-5" /></button>
                  </div>
               </div>
               <div class="flex flex-wrap gap-1.5">
                  <div v-for="col in table.columns.slice(0, 15)" :key="col.id" class="px-2 py-0.5 bg-gray-50 text-[10px] font-mono rounded border border-gray-100 text-gray-500">
                     <span class="font-bold text-gray-700">{{ col.physical_name }}</span>
                     <span class="mx-1 text-gray-300">/</span>
                     <span class="text-indigo-600 font-medium">{{ col.term }}</span>
                  </div>
                  <div v-if="table.columns.length > 15" class="px-2 py-0.5 bg-gray-50 text-[10px] text-gray-400 rounded">
                    +{{ table.columns.length - 15 }} MORE
                  </div>
               </div>
            </div>
          </div>
        </div>

        <div v-show="activeTab === 'metrics'">
           <MetricList v-if="dataset" :dataset-id="datasetId" @saved="fetchData" />
        </div>

        <div v-show="activeTab === 'relationships'">
           <RelationshipList v-if="dataset" :dataset-id="datasetId" :tables="tables" @saved="fetchData" />
        </div>

        <div v-show="activeTab === 'visualization'">
           <SchemaGraph v-if="dataset" :dataset-id="datasetId" :tables="tables" :relationships="dataset.relationships || []" />
        </div>

        <div v-show="activeTab === 'usage'">
           <ApiUsageList :dataset-id="datasetId" />
        </div>
    </div>

    <!-- Edit Table Modal (Unified Style) -->
    <div v-if="showEditModal" class="fixed inset-0 z-[150] flex items-center justify-center p-4 bg-black bg-opacity-50 backdrop-blur-sm">
      <div class="bg-white rounded-3xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in duration-200">
        <div class="px-8 py-6 border-b bg-gray-50 flex justify-between items-center">
          <div class="flex items-center gap-3">
            <h2 class="text-xl font-bold text-gray-900">{{ editingTable.id ? '编辑元数据定义' : '手动新建数据表' }}</h2>
            <span v-if="editingTable.id" class="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded text-[10px] font-mono">{{ editingTable.physical_name }}</span>
          </div>
          <button @click="showEditModal = false" class="text-gray-400 hover:text-gray-600"><XMarkIcon class="w-6 h-6" /></button>
        </div>

        <div class="flex-1 overflow-y-auto p-8 bg-white space-y-6 custom-scrollbar">
           <div class="grid grid-cols-3 gap-6">
              <div>
                 <label class="block text-xs font-bold text-gray-500 uppercase mb-2">物理表名 (Name)</label>
                 <input v-model="editingTable.physical_name" :disabled="!!editingTable.id" class="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm font-mono focus:ring-2 focus:ring-indigo-500 outline-none transition-all disabled:bg-gray-100 disabled:text-gray-400" />
              </div>
              <div>
                 <label class="block text-xs font-bold text-gray-500 uppercase mb-2">业务术语 (Term)</label>
                 <input v-model="editingTable.term" class="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" />
              </div>
              <div>
                 <div class="flex items-center justify-between mb-2">
                    <label class="block text-xs font-bold text-gray-500 uppercase">描述 (Description)</label>
                    <button @click="suggestDescription('table')" :disabled="!isAiEnabled" class="text-[10px] text-indigo-600 hover:text-indigo-700 font-bold flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed">
                       <SparklesIcon class="w-3 h-3" /> AI 润色
                    </button>
                 </div>
                 <input v-model="editingTable.description" class="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" />
              </div>
           </div>

           <div class="border-t border-gray-100 pt-6">
              <div class="flex justify-between items-center mb-4">
                 <div class="flex items-center gap-2">
                    <div class="w-1 h-3 bg-indigo-600 rounded-full"></div>
                    <h3 class="text-sm font-bold text-gray-900">字段映射详情 (Mapping)</h3>
                 </div>
                 <button @click="addColumn" class="bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-lg text-xs font-bold border border-indigo-100 hover:bg-indigo-100 transition-all flex items-center gap-1">
                    <PlusIcon class="w-4 h-4" /> 添加字段
                 </button>
              </div>

              <!-- Column List Header -->
              <div class="grid grid-cols-12 gap-4 px-4 py-2 bg-gray-50 border border-gray-100 rounded-t-xl text-[10px] font-black text-gray-400 uppercase tracking-widest">
                 <div class="col-span-3">物理字段名</div>
                 <div class="col-span-2">数据类型</div>
                 <div class="col-span-3">业务术语</div>
                 <div class="col-span-3">描述</div>
                 <div class="col-span-1 text-right">操作</div>
              </div>

              <div ref="columnListRef" class="space-y-0 max-h-[400px] overflow-y-auto border-x border-b border-gray-100 rounded-b-xl custom-scrollbar bg-white">
                 <div v-for="(col, index) in editingTable.columns" :key="index" class="grid grid-cols-12 gap-4 items-center p-3 border-b last:border-b-0 border-gray-50 hover:bg-indigo-50/30 transition-all group/row">
                    <div class="col-span-3">
                       <input v-model="col.physical_name" class="w-full bg-transparent border-b border-transparent focus:border-indigo-300 text-xs font-mono px-1 transition-all" placeholder="物理名" />
                    </div>
                    <div class="col-span-2">
                       <select v-model="col.type" class="w-full bg-indigo-50 border-none rounded-lg text-[10px] text-indigo-700 font-bold focus:ring-0 px-2 py-1 cursor-pointer">
                          <option value="String">String</option>
                          <option value="Int64">Int64</option>
                          <option value="Float64">Float64</option>
                          <option value="DateTime">DateTime</option>
                          <option value="Boolean">Boolean</option>
                       </select>
                    </div>
                    <div class="col-span-3">
                       <input v-model="col.term" class="w-full bg-transparent border-b border-transparent focus:border-indigo-300 text-sm font-bold text-gray-900 px-1 transition-all" placeholder="业务术语" />
                    </div>
                    <div class="col-span-3 relative group/col-desc">
                       <input v-model="col.description" class="w-full bg-transparent border-b border-transparent focus:border-indigo-300 text-xs text-gray-500 px-1 pr-6 transition-all" placeholder="字段描述" />
                       <button @click="suggestDescription('column', Number(index))" :disabled="!isAiEnabled" class="absolute right-1 top-1/2 -translate-y-1/2 text-indigo-400 hover:text-indigo-600 opacity-0 group-hover/col-desc:opacity-100 transition-all disabled:hidden">
                          <SparklesIcon class="w-3.5 h-3.5" />
                       </button>
                    </div>
                    <div class="col-span-1 text-right">
                       <button @click="removeColumn(index)" class="text-gray-300 hover:text-red-500 p-1 transition-colors"><TrashIcon class="w-4 h-4" /></button>
                    </div>
                 </div>
              </div>
           </div>
        </div>

        <div class="px-8 py-6 bg-gray-50 border-t flex justify-end gap-3">
           <button @click="showEditModal = false" class="px-6 py-2.5 text-gray-500 font-bold hover:text-gray-700 transition-colors">取消</button>
           <button @click="handleUpdateTable" class="px-8 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-lg transition-all flex items-center gap-2">
              确认并保存
           </button>
        </div>
      </div>
    </div>

    <!-- YAML Modal (Unified Style) -->
    <div v-if="showYamlModal" class="fixed inset-0 z-[150] flex items-center justify-center p-4 bg-black bg-opacity-50 backdrop-blur-sm">
      <div class="bg-white rounded-3xl shadow-2xl w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden animate-in zoom-in duration-200">
        <div class="px-8 py-6 border-b bg-gray-50 flex justify-between items-center">
          <div class="flex items-center gap-3">
            <CommandLineIcon class="w-6 h-6 text-purple-600" />
            <h2 class="text-xl font-bold text-gray-900">AI 语义上下文 (YAML)</h2>
          </div>
          <button @click="showYamlModal = false" class="text-gray-400 hover:text-gray-600"><XMarkIcon class="w-6 h-6" /></button>
        </div>
        <div class="flex-1 bg-slate-900 p-0 overflow-hidden">
          <pre class="h-full w-full p-8 font-mono text-sm text-cyan-400 overflow-auto custom-scrollbar leading-relaxed select-all">{{ yamlContent }}</pre>
        </div>
        <div class="px-8 py-6 bg-gray-50 border-t flex justify-end gap-3">
           <button @click="copyYaml" class="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-lg transition-all flex items-center gap-2">
              <DocumentDuplicateIcon class="w-4 h-4" /> 复制内容
           </button>
           <button @click="showYamlModal = false" class="px-6 py-2.5 bg-white border border-gray-200 rounded-xl font-bold text-gray-500 hover:bg-gray-100 transition-all">关闭</button>
        </div>
      </div>
    </div>

    <SmartImportWizard 
      :show="showImportModal" 
      :data-source="dataset?.data_source" 
      :existing-tables="existingTableNames" 
      :target-dataset-id="datasetId"
      @close="showImportModal = false" 
      @saved="fetchData" 
    />

    <!-- Dataset Edit Modal -->
    <div v-if="showDatasetEditModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9990]" @click.self="showDatasetEditModal = false">
      <div class="bg-white rounded-3xl shadow-2xl w-full max-w-xl overflow-hidden transform transition-all flex flex-col">
        <div class="px-6 py-4 border-b bg-gray-50 flex justify-between items-center">
          <h2 class="text-lg font-bold text-gray-900">编辑数据集配置</h2>
          <button @click="showDatasetEditModal = false" class="text-gray-400 hover:text-gray-600 transition-colors"><XMarkIcon class="w-5 h-5" /></button>
        </div>
        <div class="p-6 space-y-4">
          <div>
            <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1 ml-1">显示名称</label>
            <input v-model="editDatasetForm.display_name" class="w-full border border-gray-300 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" />
          </div>
          <div>
            <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1 ml-1">业务描述</label>
            <textarea v-model="editDatasetForm.description" class="w-full border border-gray-300 rounded-xl px-4 py-2 text-xs focus:ring-2 focus:ring-indigo-500 outline-none transition-all" rows="3"></textarea>
          </div>
          <div>
            <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1 ml-1">标签管理 (回车添加)</label>
            <div class="flex gap-2 mb-3">
              <input v-model="tagInput" @keyup.enter="addTag" class="flex-1 border border-gray-300 rounded-xl px-4 py-2 text-sm outline-none focus:ring-1 focus:ring-indigo-500 bg-gray-50/50" placeholder="添加标签..." />
            </div>
            <div class="flex flex-wrap gap-2 min-h-[32px] p-2 bg-gray-50 rounded-xl border border-dashed border-gray-200">
              <span v-for="(tag, i) in editDatasetForm.tags" :key="i" class="px-2.5 py-1 bg-white text-indigo-600 text-[10px] font-bold rounded-lg border border-indigo-100 flex items-center gap-1.5 shadow-sm">
                {{ tag }}
                <button @click="removeTag(i)" class="text-gray-300 hover:text-red-500 transition-colors text-xs font-black">&times;</button>
              </span>
              <span v-if="editDatasetForm.tags.length === 0" class="text-[10px] text-gray-300 italic flex items-center px-1">暂无标签...</span>
            </div>
          </div>
        </div>
        <div class="px-6 py-4 bg-gray-50 border-t flex justify-end gap-3">
          <button @click="showDatasetEditModal = false" class="px-5 py-2 text-gray-500 font-bold hover:text-gray-700 transition-colors text-sm">取消</button>
          <button @click="handleUpdateDataset" class="px-8 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-lg transition-all text-sm">保存修改</button>
        </div>
      </div>
    </div>

    <!-- Table Delete Confirmation Modal -->
    <div v-if="showTableDeleteConfirm" class="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden transform transition-all animate-in zoom-in duration-200">
        <div class="p-6 text-center">
          <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 mb-4">
            <TrashIcon class="h-6 w-6 text-red-600" />
          </div>
          <h3 class="text-lg leading-6 font-bold text-gray-900 mb-2">确认删除表元数据?</h3>
          <p class="text-sm text-gray-500 mb-6 leading-relaxed">
            您即将删除 <span class="font-bold text-gray-800">{{ deletingTable?.physical_name }}</span> 的语义定义。
            <br/><span class="text-red-500 font-bold">此操作不可撤销</span>。
          </p>
          <div class="flex gap-3">
            <button @click="showTableDeleteConfirm = false" class="flex-1 py-2.5 bg-gray-100 text-gray-700 font-bold rounded-lg hover:bg-gray-200 transition-all text-sm">取消</button>
            <button @click="confirmTableDelete" class="flex-1 py-2.5 bg-red-600 text-white font-bold rounded-lg hover:bg-red-700 shadow-lg transition-all text-sm">确认删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Health Report Modal -->
    <div v-if="showHealthModal && dataset" class="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="showHealthModal = false">
      <div class="bg-white rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden animate-in zoom-in duration-200 flex flex-col">
        <div class="px-8 py-6 border-b bg-gray-50 flex justify-between items-center">
          <div class="flex items-center gap-3">
            <div class="p-2.5 rounded-xl text-white shadow-md" :class="dataset.health_score >= 80 ? 'bg-emerald-500' : 'bg-amber-500'">
              <ShieldCheckIcon class="w-6 h-6" />
            </div>
            <div>
              <h3 class="text-xl font-bold text-gray-900">AI 准备度健康报告</h3>
              <p class="text-[10px] text-gray-400 font-bold uppercase tracking-widest mt-0.5">Metadata Quality Assessment</p>
            </div>
          </div>
          <button @click="showHealthModal = false" class="text-gray-400 hover:text-gray-600 transition-colors"><XMarkIcon class="w-6 h-6" /></button>
        </div>

        <div class="p-8 bg-white space-y-6">
          <div class="flex items-center bg-gray-50 p-5 rounded-2xl border border-gray-100 relative group">
            <div class="text-center flex-1">
              <p class="text-[10px] font-black text-gray-400 uppercase">当前得分</p>
              <p class="text-4xl font-black" :class="dataset.health_score >= 80 ? 'text-emerald-600' : 'text-amber-600'">{{ dataset.health_score }}</p>
            </div>
            <div class="w-px h-10 bg-gray-200"></div>
            <div class="flex-1 px-6">
              <p class="text-[10px] font-black text-gray-400 uppercase mb-1">健康状态</p>
              <p class="text-sm font-bold text-gray-700">
                {{ dataset.health_score >= 80 ? '极佳 - 语义丰富' : dataset.health_score >= 60 ? '良好 - 仍可优化' : '急需优化' }}
              </p>
            </div>
            
            <!-- Standard Flow Re-evaluate Button -->
            <div class="pl-4 border-l border-gray-200">
              <button 
                @click="handleHealthCheck" 
                :disabled="refreshingHealth"
                class="bg-white border-2 border-indigo-100 shadow-sm px-4 py-2 rounded-xl flex items-center gap-2 hover:bg-indigo-600 hover:text-white hover:border-indigo-600 transition-all active:scale-95 group/btn disabled:opacity-50"
              >
                <ArrowPathIcon class="w-4 h-4" :class="refreshingHealth ? 'animate-spin' : 'text-indigo-500 group-hover/btn:text-white'" />
                <span class="text-xs font-bold">{{ refreshingHealth ? '评估中...' : '重新评估' }}</span>
              </button>
            </div>
          </div>

          <div class="space-y-3">
            <div class="flex items-center justify-between">
              <h4 class="text-xs font-black text-gray-500 uppercase tracking-tighter">优化建议清单</h4>
              <button 
                v-if="dataset.health_score < 100 && hasPerm('element:metadata:manage')"
                @click="handleAiEnrich"
                :disabled="aiEnriching || !isAiEnabled"
                class="px-3 py-1 bg-indigo-600 text-white text-[10px] font-bold rounded-lg hover:bg-indigo-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 shadow-sm active:scale-95"
              >
                <SparklesIcon v-if="!aiEnriching" class="w-3 h-3" />
                <div v-else class="w-2.5 h-2.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                {{ !isAiEnabled ? 'AI 已禁用' : (aiEnriching ? '正在极速修复中...' : 'AI 一键自动修复') }}
              </button>
            </div>
            <div v-if="dataset.health_report?.issues?.length" class="space-y-2">
              <div v-for="(issue, i) in dataset.health_report.issues" :key="i" class="flex items-start gap-3 p-3 bg-red-50/50 border border-red-100 rounded-xl group hover:bg-red-50 transition-all">
                <div class="mt-0.5"><ExclamationCircleIcon class="w-4 h-4 text-red-500" /></div>
                <div class="flex-1">
                  <p class="text-xs font-bold text-gray-800">{{ issue.msg }}</p>
                  <p class="text-[10px] text-red-400 font-medium mt-0.5">预计提升得分: +{{ issue.impact }}分</p>
                </div>
              </div>
            </div>
            <div v-else class="flex flex-col items-center py-6 bg-emerald-50/30 rounded-2xl border border-emerald-100 border-dashed">
              <CheckCircleIcon class="w-8 h-8 text-emerald-500 mb-2" />
              <p class="text-xs font-bold text-emerald-700 text-center">您的元数据质量非常完美！<br/>AI 能够精准理解所有业务意图。</p>
            </div>
          </div>

          <div class="grid grid-cols-4 gap-2">
            <div v-for="(val, key) in dataset.health_report?.stats" :key="key" class="text-center p-2 bg-gray-50 rounded-xl border border-gray-100">
              <p class="text-[10px] font-black text-gray-400 uppercase">{{ key }}</p>
              <p class="text-sm font-black text-gray-700">{{ val }}</p>
            </div>
          </div>
        </div>

        <div class="px-8 py-6 bg-gray-50 border-t text-center">
          <p class="text-[10px] text-gray-400 italic">※ 分数越高，AI 生成 SQL 的准确率和业务关联度越高</p>
        </div>
      </div>
    </div>

    <!-- Description Detail Modal -->
    <div v-if="showDescriptionModal && dataset" class="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="showDescriptionModal = false">
      <div class="bg-white rounded-3xl shadow-2xl w-full max-w-2xl overflow-hidden animate-in zoom-in duration-200 flex flex-col">
        <div class="px-8 py-6 border-b bg-gray-50 flex justify-between items-center">
          <div class="flex items-center gap-3">
            <div class="p-2.5 bg-indigo-100 rounded-xl text-indigo-600 shadow-sm">
              <InformationCircleIcon class="w-6 h-6" />
            </div>
            <div>
              <h3 class="text-xl font-bold text-gray-900">数据集详情描述</h3>
              <p class="text-[10px] text-gray-400 font-bold uppercase tracking-widest mt-0.5">Dataset Full Description</p>
            </div>
          </div>
          <button @click="showDescriptionModal = false" class="text-gray-400 hover:text-gray-600 transition-colors"><XMarkIcon class="w-6 h-6" /></button>
        </div>

        <div class="p-8 bg-white overflow-y-auto max-h-[60vh] custom-scrollbar">
          <div class="text-gray-600 leading-loose whitespace-pre-wrap text-base">
            {{ dataset.description }}
          </div>
        </div>

        <div class="px-8 py-6 bg-gray-50 border-t flex justify-end">
           <button @click="showDescriptionModal = false" class="px-6 py-2.5 bg-white border border-gray-200 rounded-xl font-bold text-gray-500 hover:bg-gray-100 transition-all">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 10px; }
</style>
