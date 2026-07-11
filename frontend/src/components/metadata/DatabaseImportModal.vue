<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from '../../utils/axios'
import { 
  CircleStackIcon, TableCellsIcon, XMarkIcon, 
  ChevronRightIcon, ArrowPathIcon, CheckIcon,
  MagnifyingGlassIcon
} from '@heroicons/vue/24/outline'

const props = defineProps<{ 
  show: boolean, 
  initialDataSource?: string,
  existingTableNames?: string[]
}>()
const emit = defineEmits<{
  close: []
  confirm: [
    | { mode: 'profile'; sourceName: string; sourceId: number; tableNames: string[] }
    | { mode: 'ddl'; sourceName: string; ddl: string }
  ]
}>()

const dataSources = ref<any[]>([])
const tables = ref<any[]>([])
const loading = ref(false)
const fetchingTables = ref(false)
const selectedSource = ref<any>(null)
const selectedTables = ref<string[]>([])
const tableSearchQuery = ref('')

const activeTab = ref<'system' | 'profile'>('system')
const tableProfiles = ref<any[]>([])
const loadingProfiles = ref(false)
const selectedProfileTag = ref<string | null>(null)
const tagsExpanded = ref(false)
const TAGS_COLLAPSED_LIMIT = 6

const filteredTables = computed(() => {
  if (!tableSearchQuery.value) return tables.value
  const query = tableSearchQuery.value.toLowerCase()
  return tables.value.filter(t => t.name.toLowerCase().includes(query))
})

// 判断表是否已被导入
const isAlreadyImported = (tableName: string) => {
  return props.existingTableNames?.includes(tableName) || false
}

const fetchDataSources = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/portal/datasource/datasources?status=active')
    const userInfoStr = localStorage.getItem('user_info')
    let allSources = []
    if (userInfoStr) {
      const user = JSON.parse(userInfoStr)
      if (user.role === 'admin') {
        allSources = res.data
      } else {
        const allowed = user.permissions?.datasources || []
        allSources = res.data.filter((ds: any) => allowed.includes(`ds:${ds.source_name}`))
      }
    }
    dataSources.value = allSources

    if (props.initialDataSource) {
      const match = allSources.find((ds: any) => ds.source_name === props.initialDataSource)
      if (match) {
        handleSourceSelect(match)
      }
    }
  } finally { loading.value = false }
}

const loadTableProfiles = async () => {
  if (!selectedSource.value) return
  loadingProfiles.value = true
  try {
    const res = await axios.get(`/api/portal/datasource/datasources/${selectedSource.value.id}/table-profiles`, {
      params: { summary: true, status: 2 },
    })
    tableProfiles.value = res.data || []
  } catch {
    tableProfiles.value = []
  } finally {
    loadingProfiles.value = false
  }
}

const handleSourceSelect = async (ds: any) => {
  selectedSource.value = ds
  selectedTables.value = []
  tableSearchQuery.value = ''
  fetchingTables.value = true
  selectedProfileTag.value = null
  tagsExpanded.value = false
  tableProfiles.value = []
  activeTab.value = 'system'
  try {
    const res = await axios.post('/api/portal/meta/datasource/tables', { data_source: ds.source_name })
    const allTables: any[] = res.data.tables || []
    tables.value = allTables
    
    await loadTableProfiles()
    if (tableProfiles.value.length > 0) {
      activeTab.value = 'profile'
    }
  } catch (e) {
    tables.value = []
  } finally { fetchingTables.value = false }
}

const toggleTable = (tableName: string) => {
  if (isAlreadyImported(tableName)) return 
  const idx = selectedTables.value.indexOf(tableName)
  if (idx > -1) {
    selectedTables.value.splice(idx, 1)
  } else {
    selectedTables.value.push(tableName)
  }
}

const toggleProfileTag = (tag: string) => {
  if (selectedProfileTag.value === tag) {
    selectedProfileTag.value = null
  } else {
    selectedProfileTag.value = tag
  }
}

const availableTags = computed(() => {
  const counts: Record<string, number> = {}
  tableProfiles.value.forEach((p: any) => {
    if (p.is_ignored === 1) return
    if (p.ai_tags && Array.isArray(p.ai_tags)) {
      p.ai_tags.forEach((t: string) => {
        if (t && t.trim()) {
          const cleanTag = t.trim()
          counts[cleanTag] = (counts[cleanTag] || 0) + 1
        }
      })
    }
  })
  return Object.entries(counts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})

const filteredTableProfiles = computed(() => {
  // 过滤掉被忽略的表以防干扰
  let list = tableProfiles.value.filter(p => p.is_ignored !== 1)
  if (selectedProfileTag.value) {
    list = list.filter((t) => t.ai_tags && t.ai_tags.includes(selectedProfileTag.value))
  }
  if (tableSearchQuery.value) {
    const q = tableSearchQuery.value.trim().toLowerCase()
    list = list.filter((p) =>
      p.table_name.toLowerCase().includes(q) ||
      (p.ai_term && p.ai_term.toLowerCase().includes(q)) ||
      (p.ai_description && p.ai_description.toLowerCase().includes(q))
    )
  }
  return list
})

const selectableFilteredProfiles = computed(() => {
  return filteredTableProfiles.value.filter(t => !isAlreadyImported(t.table_name))
})

const toggleAll = () => {
  if (activeTab.value === 'system') {
    const operableTables = filteredTables.value.filter(t => !isAlreadyImported(t.name))
    const operableTableNames = operableTables.map(t => t.name)
    const currentlySelectedOperable = selectedTables.value.filter(name => operableTableNames.includes(name))

    if (currentlySelectedOperable.length === operableTableNames.length && operableTableNames.length > 0) {
      const idsToRemove = new Set(operableTableNames)
      selectedTables.value = selectedTables.value.filter(name => !idsToRemove.has(name))
    } else {
      const currentSet = new Set(selectedTables.value)
      operableTableNames.forEach(name => currentSet.add(name))
      selectedTables.value = Array.from(currentSet)
    }
  } else {
    const operableTableNames = selectableFilteredProfiles.value.map(t => t.table_name)
    const currentlySelectedOperable = selectedTables.value.filter(name => operableTableNames.includes(name))

    if (currentlySelectedOperable.length === operableTableNames.length && operableTableNames.length > 0) {
      const idsToRemove = new Set(operableTableNames)
      selectedTables.value = selectedTables.value.filter(name => !idsToRemove.has(name))
    } else {
      const currentSet = new Set(selectedTables.value)
      operableTableNames.forEach(name => currentSet.add(name))
      selectedTables.value = Array.from(currentSet)
    }
  }
}

const handleConfirm = async () => {
  const finalTables = selectedTables.value.filter(t => !isAlreadyImported(t))
  if (!selectedSource.value || finalTables.length === 0) return

  if (activeTab.value === 'profile') {
    emit('confirm', {
      mode: 'profile',
      sourceName: selectedSource.value.source_name,
      sourceId: selectedSource.value.id,
      tableNames: finalTables,
    })
    emit('close')
    return
  }

  loading.value = true
  try {
    let combinedDdl = ""
    for (const tableName of finalTables) {
      const res = await axios.post('/api/portal/meta/datasource/columns', {
        data_source: selectedSource.value.source_name,
        table_name: tableName,
      })
      const cols = res.data.columns
      const generatedDdl = `CREATE TABLE ${tableName} (\n` +
        cols.map((c: any) => `  ${c.name} ${c.type} COMMENT '${c.comment || ''}'`).join(',\n') +
        `\n);\n\n`
      combinedDdl += generatedDdl
    }
    emit('confirm', {
      mode: 'ddl',
      sourceName: selectedSource.value.source_name,
      ddl: combinedDdl.trim(),
    })
    emit('close')
  } finally { loading.value = false }
}

onMounted(fetchDataSources)
</script>

<template>
  <div v-if="props.show" class="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black bg-opacity-50 backdrop-blur-sm">
    <div class="bg-white rounded-3xl shadow-2xl w-full max-w-3xl overflow-hidden animate-in zoom-in duration-200 flex flex-col max-h-[85vh]">
      <!-- Header -->
      <div class="px-8 py-6 border-b bg-gray-50 flex justify-between items-center">
        <div class="flex items-center gap-4">
          <div class="p-3 bg-indigo-600 rounded-xl text-white shadow-md">
            <CircleStackIcon class="w-6 h-6" />
          </div>
          <div>
            <h2 class="text-xl font-bold text-gray-900">从现有数据源导入</h2>
            <p class="text-xs text-gray-400 mt-0.5 uppercase tracking-widest font-bold">Pick one or more tables to analyze</p>
          </div>
        </div>
        <button @click="emit('close')" class="text-gray-400 hover:text-gray-600 transition-colors"><XMarkIcon class="w-6 h-6" /></button>
      </div>

      <div class="flex-1 overflow-hidden grid grid-cols-12">
        <!-- Left: Sources (Hidden if initialDataSource is provided) -->
        <div v-if="!props.initialDataSource" class="col-span-5 p-6 border-r flex flex-col gap-4 bg-white overflow-y-auto custom-scrollbar">
          <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-1">1. 选择数据源</label>
          <div 
            v-for="ds in dataSources" :key="ds.id"
            @click="handleSourceSelect(ds)"
            :class="selectedSource?.id === ds.id ? 'bg-indigo-600 border-indigo-600 text-white shadow-lg' : 'bg-gray-50 border-gray-100 text-gray-600 hover:bg-gray-100'"
            class="p-4 rounded-xl border transition-all cursor-pointer flex justify-between items-center group"
          >
            <div class="flex items-center gap-3">
              <CircleStackIcon class="w-5 h-5 opacity-50" />
              <span class="text-sm font-bold">{{ ds.source_name }}</span>
            </div>
            <ChevronRightIcon class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>

        <!-- Right: Tables (Full width if no source list) -->
        <div :class="props.initialDataSource ? 'col-span-12' : 'col-span-7'" class="p-6 flex flex-col gap-4 bg-gray-50/50 overflow-y-auto custom-scrollbar">
          
          <!-- 双 Tab 切换 -->
          <div v-if="selectedSource" class="flex border-b border-gray-200 shrink-0">
            <button 
              type="button"
              :class="['px-4 py-2 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5', activeTab === 'system' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-400 hover:text-gray-600']"
              @click="activeTab = 'system'"
            >
              物理直连导入
            </button>
            <button 
              v-if="tableProfiles.length > 0"
              type="button"
              :class="['px-4 py-2 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5', activeTab === 'profile' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-400 hover:text-gray-600']"
              @click="activeTab = 'profile'"
            >
              AI 摸排资产导入
              <span class="px-1.5 py-0.5 text-[9px] bg-indigo-50 text-indigo-600 rounded-full font-bold">
                {{ tableProfiles.filter(p => p.is_ignored !== 1).length }}
              </span>
            </button>
          </div>

          <div class="flex justify-between items-center">
             <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-1">
                {{ props.initialDataSource ? `从 ${props.initialDataSource} 选择数据表` : '选择目标表' }} ({{ selectedTables.length }})
             </label>
             <button 
               v-if="tables.length > 0"
               @click="toggleAll" 
               class="text-[10px] font-bold text-indigo-600 hover:underline px-2 py-1"
             >
               {{ (activeTab === 'system' ? selectedTables.length === tables.length : selectedTables.length === selectableFilteredProfiles.length) ? '取消全选' : '选择当前全部' }}
             </button>
          </div>

          <!-- Search Input -->
          <div v-if="tables.length > 0" class="relative">
             <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <MagnifyingGlassIcon class="h-4 w-4 text-gray-400" />
             </div>
             <input 
               v-model="tableSearchQuery" 
               type="text" 
               placeholder="快速过滤表名..." 
               class="block w-full pl-10 pr-3 py-2 bg-white border border-gray-200 rounded-xl text-xs placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 transition-all shadow-sm"
             />
             <button v-if="tableSearchQuery" @click="tableSearchQuery = ''" class="absolute inset-y-0 right-0 pr-3 flex items-center">
                <XMarkIcon class="h-4 w-4 text-gray-300 hover:text-gray-500" />
             </button>
          </div>

          <!-- AI 标签过滤排（可折叠） -->
          <div v-if="activeTab === 'profile' && availableTags.length > 0" class="px-1 shrink-0">
            <div class="flex flex-wrap items-center gap-1.5">
              <!-- 全部按钮始终显示 -->
              <button
                type="button"
                @click="selectedProfileTag = null"
                :class="['px-2.5 py-1 rounded-full text-[9px] font-medium border transition-all cursor-pointer', !selectedProfileTag ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-gray-100 border-gray-200 text-gray-500 hover:bg-gray-200']"
              >
                全部 ({{ tableProfiles.filter(p => p.is_ignored !== 1).length }})
              </button>
              <!-- 折叠态：只显示前 N 个标签 -->
              <template v-if="!tagsExpanded">
                <button
                  type="button"
                  v-for="tag in availableTags.slice(0, TAGS_COLLAPSED_LIMIT)"
                  :key="tag.name"
                  @click="toggleProfileTag(tag.name)"
                  :class="['px-2.5 py-1 rounded-full text-[9px] font-medium border transition-all cursor-pointer', selectedProfileTag === tag.name ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-gray-100 border-gray-200 text-gray-500 hover:bg-gray-200']"
                >
                  {{ tag.name }} ({{ tag.count }})
                </button>
                <!-- 剩余数量指示 + 展开按钮 -->
                <button
                  v-if="availableTags.length > TAGS_COLLAPSED_LIMIT"
                  type="button"
                  class="px-2.5 py-1 rounded-full text-[9px] font-medium border border-dashed border-gray-300 text-gray-400 hover:text-indigo-600 hover:border-indigo-300 hover:bg-indigo-50 transition-all cursor-pointer flex items-center gap-1"
                  @click="tagsExpanded = true"
                >
                  <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                  +{{ availableTags.length - TAGS_COLLAPSED_LIMIT }} 更多
                </button>
              </template>
              <!-- 展开态：显示所有标签 -->
              <template v-else>
                <button
                  type="button"
                  v-for="tag in availableTags"
                  :key="tag.name"
                  @click="toggleProfileTag(tag.name)"
                  :class="['px-2.5 py-1 rounded-full text-[9px] font-medium border transition-all cursor-pointer', selectedProfileTag === tag.name ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-gray-100 border-gray-200 text-gray-500 hover:bg-gray-200']"
                >
                  {{ tag.name }} ({{ tag.count }})
                </button>
                <!-- 收起按钮 -->
                <button
                  type="button"
                  class="px-2.5 py-1 rounded-full text-[9px] font-medium border border-dashed border-gray-300 text-gray-400 hover:text-indigo-600 hover:border-indigo-300 hover:bg-indigo-50 transition-all cursor-pointer flex items-center gap-1"
                  @click="tagsExpanded = false"
                >
                  <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" /></svg>
                  收起
                </button>
              </template>
            </div>
          </div>

          <div v-if="fetchingTables" class="flex-1 flex flex-col items-center justify-center text-gray-400">
            <ArrowPathIcon class="w-8 h-8 animate-spin mb-2" />
            <span class="text-xs font-bold tracking-widest uppercase">Fetching Tables...</span>
          </div>

          <template v-else-if="tables.length > 0">
            <!-- 物理直连表列表 -->
            <div v-if="activeTab === 'system'">
              <div v-if="filteredTables.length > 0" class="grid grid-cols-1 gap-2">
                <div 
                  v-for="t in filteredTables" :key="t.name"
                  @click="toggleTable(t.name)"
                  :class="[
                    selectedTables.includes(t.name) ? 'bg-white border-indigo-600 ring-1 ring-indigo-600' : 'bg-white border-gray-200 text-gray-500 hover:border-indigo-300',
                    isAlreadyImported(t.name) ? 'opacity-40 grayscale cursor-not-allowed border-gray-100 bg-gray-50 ring-0' : 'cursor-pointer'
                  ]"
                  class="p-3 rounded-xl border text-xs font-mono transition-all flex items-center justify-between group shadow-sm"
                >
                  <div class="flex items-center gap-3">
                     <TableCellsIcon class="w-4 h-4 opacity-40" />
                     <span :class="selectedTables.includes(t.name) && !isAlreadyImported(t.name) ? 'text-indigo-600 font-bold' : ''">{{ t.name }}</span>
                     <span :class="t.type === 'VIEW' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'" class="text-[9px] px-1.5 py-0.5 rounded uppercase font-black ml-1 scale-90 origin-left">{{ t.type }}</span>
                     <span v-if="isAlreadyImported(t.name)" class="text-[9px] bg-gray-200 text-gray-500 px-1.5 py-0.5 rounded uppercase font-black">Already In</span>
                  </div>
                  <div v-if="selectedTables.includes(t.name)" :class="isAlreadyImported(t.name) ? 'bg-gray-300' : 'bg-indigo-600'" class="w-5 h-5 rounded-full flex items-center justify-center text-white animate-in zoom-in duration-200">
                     <CheckIcon class="w-3 h-3 stroke-[4]" />
                  </div>
                </div>
              </div>
              <div v-else class="flex-1 flex flex-col items-center justify-center py-12 text-gray-400">
                 <MagnifyingGlassIcon class="w-8 h-8 mb-2 opacity-20" />
                 <p class="text-xs font-bold uppercase tracking-widest">没有匹配的表</p>
              </div>
            </div>

            <!-- AI 摸排画像列表 -->
            <div v-else-if="activeTab === 'profile'">
              <div v-if="filteredTableProfiles.length > 0" class="grid grid-cols-1 gap-2">
                <div 
                  v-for="profile in filteredTableProfiles" :key="profile.table_name"
                  @click="toggleTable(profile.table_name)"
                  :class="[
                    selectedTables.includes(profile.table_name) ? 'bg-white border-indigo-600 ring-1 ring-indigo-600' : 'bg-white border-gray-200 hover:border-indigo-300',
                    isAlreadyImported(profile.table_name) ? 'opacity-40 grayscale cursor-not-allowed border-gray-100 bg-gray-50 ring-0' : 'cursor-pointer'
                  ]"
                  class="p-3.5 rounded-xl border transition-all flex flex-col gap-1.5 shadow-sm bg-white"
                >
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2 flex-wrap">
                      <TableCellsIcon class="w-4 h-4 opacity-40 shrink-0" />
                      <span class="text-xs font-mono font-bold" :class="selectedTables.includes(profile.table_name) && !isAlreadyImported(profile.table_name) ? 'text-indigo-600 font-bold' : 'text-gray-700'">{{ profile.table_name }}</span>
                      <span :class="profile.table_type === 'view' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'" class="text-[8px] px-1.5 py-0.2 rounded uppercase font-black">{{ profile.table_type === 'view' ? '视图' : '表' }}</span>
                      <span 
                        class="px-1 py-0.1 rounded text-[8px] font-black"
                        :class="profile.confidence_score >= 80 ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/50' : 'bg-amber-50 text-amber-700 border border-amber-200/50'"
                      >
                        {{ profile.confidence_score }} 分
                      </span>
                      <span v-if="isAlreadyImported(profile.table_name)" class="text-[9px] bg-gray-200 text-gray-500 px-1.5 py-0.5 rounded uppercase font-black">Already In</span>
                    </div>
                    <div v-if="selectedTables.includes(profile.table_name)" :class="isAlreadyImported(profile.table_name) ? 'bg-gray-300' : 'bg-indigo-600'" class="w-5 h-5 rounded-full flex items-center justify-center text-white shrink-0 animate-in zoom-in duration-200">
                       <CheckIcon class="w-3 h-3 stroke-[4]" />
                    </div>
                  </div>
                  
                  <!-- 摸排备注 -->
                  <div v-if="profile.ai_term" class="text-xs text-indigo-600 font-bold">
                    💡 {{ profile.ai_term }}
                  </div>
                  <!-- 摸排用途描述 -->
                  <div v-if="profile.ai_description" class="text-[11px] text-gray-500 leading-normal max-w-xl truncate">
                    {{ profile.ai_description }}
                  </div>
                  <!-- tags -->
                  <div v-if="profile.ai_tags && profile.ai_tags.length > 0" class="flex flex-wrap gap-1">
                    <span 
                      v-for="tag in profile.ai_tags" :key="tag"
                      class="px-1.5 py-0.2 rounded text-[8px] font-medium bg-gray-100 text-gray-500"
                    >
                      {{ tag }}
                    </span>
                  </div>
                </div>
              </div>
              <div v-else class="flex-1 flex flex-col items-center justify-center py-12 text-gray-400">
                 <MagnifyingGlassIcon class="w-8 h-8 mb-2 opacity-20" />
                 <p class="text-xs font-bold uppercase tracking-widest">没有匹配的表画像记录</p>
              </div>
            </div>
          </template>

          <div v-else class="flex-1 flex flex-col items-center justify-center text-gray-300 opacity-50">
             <TableCellsIcon class="w-12 h-12 mb-2" />
             <span class="text-xs font-bold uppercase tracking-widest">Select Source First</span>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-8 py-6 bg-gray-50 border-t flex gap-3 justify-end">
        <button @click="emit('close')" class="px-6 py-2.5 bg-white border border-gray-200 rounded-xl font-bold text-gray-500 hover:bg-gray-100 transition-all text-sm">取消</button>
        <button 
          @click="handleConfirm" :disabled="selectedTables.length === 0 || loading"
          class="px-10 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold shadow-lg transition-all active:scale-95 disabled:opacity-50 text-sm flex items-center gap-2"
        >
          <ArrowPathIcon v-if="loading" class="w-4 h-4 animate-spin" />
          <span>{{ loading ? '抓取结构中...' : (activeTab === 'profile' ? `导入摸排画像 (${selectedTables.length})` : `确认加载 (${selectedTables.length})`) }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 10px; }
</style>