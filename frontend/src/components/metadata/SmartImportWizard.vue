<script setup lang="ts">
import { ref, onUnmounted, onMounted } from 'vue'
import { metadataV2Api } from '../../api/metadata_v2'
import { useToast } from '../../composables/useToast'
import axios from 'axios'
import request from '../../utils/axios'
import DatabaseImportModal from './DatabaseImportModal.vue'
import { 
  RocketLaunchIcon, BeakerIcon, XMarkIcon, 
  CircleStackIcon, TableCellsIcon, ArrowPathIcon,
  ChevronRightIcon, CommandLineIcon, TrashIcon, ExclamationTriangleIcon,
  CheckCircleIcon
} from '@heroicons/vue/24/outline'

const props = defineProps<{ 
  show: boolean, 
  dataSource?: string, 
  existingTables?: string[],
  targetDatasetId?: number 
}>()
const emit = defineEmits(['close', 'saved'])

const step = ref(1) // 1: Input, 2: Preview
const ddlText = ref('')
const analyzing = ref(false)
const saving = ref(false)
const datasetName = ref('')
const datasetDisplayName = ref('')
const internalDataSource = ref('')
const showDbImport = ref(false)
const isAiEnabled = ref(true)
const importSource = ref<'manual' | 'ddl' | 'profile'>('manual')
const profileImportTags = ref<string[]>([])
const analyzeMode = ref<'ai' | 'profile'>('ai')
const { showToast } = useToast()

// 耗时计时与中断控制
const elapsedSeconds = ref(0)
let elapsedTimer: any = null
let abortController: AbortController | null = null

const startElapsedTimer = () => {
  elapsedSeconds.value = 0
  elapsedTimer = setInterval(() => {
    elapsedSeconds.value++
  }, 1000)
}

const stopElapsedTimer = () => {
  if (elapsedTimer) clearInterval(elapsedTimer)
  elapsedTimer = null
}

const handleInterrupt = () => {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  analyzing.value = false
  stopFakeProgress()
  stopElapsedTimer()
  showToast('解析已中断', 'warning')
}

const checkAiStatus = async () => {
  try {
    const res = await request.get('/api/portal/system/config/ai')
    isAiEnabled.value = String(res.data.enabled).toLowerCase() === 'true'
  } catch (e) {
    isAiEnabled.value = false
  }
}

onMounted(() => {
  checkAiStatus()
})

// Progress Animation
const progress = ref(0)
const progressStatus = ref('')
let progressTimer: any = null

const startFakeProgress = () => {
  progress.value = 0
  progressStatus.value = 'AI 正在建立分析通道...'
  progressTimer = setInterval(() => {
    if (progress.value < 98) progress.value += (98 - progress.value) * 0.05
    if (progress.value > 20) progressStatus.value = '解析物理表结构...'
    if (progress.value > 50) progressStatus.value = '推断业务术语与描述...'
    if (progress.value > 80) progressStatus.value = '构建实体关联图谱...'
  }, 400)
}

const stopFakeProgress = () => {
  if (progressTimer) clearInterval(progressTimer)
  progressTimer = null
}

onUnmounted(stopFakeProgress)

// Preview Data
const previewData = ref<{ tables: any[] }>({
  tables: []
})

const mapToLogicType = (rawType: string): string => {
  if (!rawType) return 'String'
  const t = rawType.toUpperCase()

  if (t.includes('CHAR') || t.includes('TEXT') || t.includes('CLOB') || t.includes('STRING')) return 'String'
  if (t.includes('INT') || t.includes('LONG') || t.includes('SHORT') || t.includes('SMALLINT') || t.includes('BIGINT')) return 'Int64'
  if (t.includes('FLOAT') || t.includes('DOUBLE') || t.includes('DECIMAL') || t.includes('NUMBER') || t.includes('NUMERIC') || t.includes('REAL')) return 'Float64'
  if (t.includes('TIME') || t.includes('DATE') || t.includes('STAMP')) return 'DateTime'
  if (t.includes('BOOL') || t.includes('BIT')) return 'Boolean'

  if (['STRING', 'INT64', 'FLOAT64', 'DATETIME', 'BOOLEAN'].includes(t)) {
    const map: Record<string, string> = {
      STRING: 'String', INT64: 'Int64', FLOAT64: 'Float64', DATETIME: 'DateTime', BOOLEAN: 'Boolean',
    }
    return map[t] || 'String'
  }

  return 'String'
}

const profileToTableMeta = (profile: any, physicalCols: any[] = []) => {
  const profileMap = Object.fromEntries(
    (profile.columns_profile || []).map((c: any) => [c.name, c])
  )

  const columns = physicalCols.length > 0
    ? physicalCols.map((c: any) => ({
        physical_name: c.name,
        term: profileMap[c.name]?.term || c.name,
        type: mapToLogicType(c.type),
        description: profileMap[c.name]?.desc || c.comment || '',
        synonyms: [],
        enums: [],
        examples: [],
      }))
    : (profile.columns_profile || []).map((c: any) => ({
        physical_name: c.name,
        term: c.term || c.name,
        type: 'String',
        description: c.desc || '',
        synonyms: [],
        enums: [],
        examples: [],
      }))

  return {
    physical_name: profile.table_name,
    term: profile.ai_term || profile.table_name,
    description: profile.ai_description || '',
    synonyms: profile.ai_tags || [],
    columns,
  }
}

const applyPreviewTables = (tables: any[]) => {
  previewData.value = { tables }
  if (tables.length > 0) {
    datasetName.value = tables[0].physical_name + '_ds'
    datasetDisplayName.value = (tables[0].term || tables[0].physical_name) + '语义库'
  }
  step.value = 2
}

const handleAnalyze = async () => {
  if (!ddlText.value.trim() || !isAiEnabled.value) return
  analyzing.value = true
  startFakeProgress()
  startElapsedTimer()
  
  abortController = new AbortController()
  
  try {
    const res = await request.post('/api/portal/meta/v2/datasets/analyze-ddl', 
      { content: ddlText.value },
      { signal: abortController.signal }
    )
    
    progress.value = 100
    progressStatus.value = '智能解析已完成！'
    
    setTimeout(() => {
      const data = res.data.data
      const rawTables = data.tables || []

      rawTables.forEach((table: any) => {
        if (table.columns) {
          table.columns.forEach((col: any) => {
            col.type = mapToLogicType(col.type)
          })
        }
      })

      applyPreviewTables(rawTables)
      analyzing.value = false
      stopFakeProgress()
      stopElapsedTimer()
    }, 800)
  } catch (e: any) {
    if (e.name === 'AbortError' || axios.isCancel(e)) {
      console.log('Request cancelled')
      return
    }
    stopFakeProgress()
    stopElapsedTimer()
    analyzing.value = false
    showToast(e.response?.data?.detail || '智能解析失败', 'error')
  } finally {
    abortController = null
  }
}

const loadFromProfiles = async (payload: {
  sourceName: string
  sourceId: number
  tableNames: string[]
}) => {
  analyzeMode.value = 'profile'
  analyzing.value = true
  progress.value = 0
  progressStatus.value = '正在加载摸排画像...'
  startElapsedTimer()

  try {
    const tables: any[] = []
    const tagSet = new Set<string>()

    await Promise.all(
      payload.tableNames.map(async (tableName) => {
        const [profileRes, columnsRes] = await Promise.all([
          request.get(
            `/api/portal/datasource/datasources/${payload.sourceId}/table-profiles/${encodeURIComponent(tableName)}`
          ),
          request.post('/api/portal/meta/datasource/columns', {
            data_source: payload.sourceName,
            table_name: tableName,
          }),
        ])
        const profile = profileRes.data
        ;(profile.ai_tags || []).forEach((tag: string) => {
          if (tag?.trim()) tagSet.add(tag.trim())
        })
        tables.push(profileToTableMeta(profile, columnsRes.data?.columns || []))
      })
    )

    tables.sort((a, b) => payload.tableNames.indexOf(a.physical_name) - payload.tableNames.indexOf(b.physical_name))
    profileImportTags.value = Array.from(tagSet).slice(0, 8)
    importSource.value = 'profile'
    progress.value = 100
    progressStatus.value = '摸排画像已就绪'
    applyPreviewTables(tables)
    showToast('已使用摸排画像，跳过 AI 重算', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '加载摸排画像失败', 'error')
  } finally {
    analyzing.value = false
    stopElapsedTimer()
  }
}

const handleDbImportConfirm = async (
  payload:
    | { mode: 'profile'; sourceName: string; sourceId: number; tableNames: string[] }
    | { mode: 'ddl'; sourceName: string; ddl: string }
) => {
  showDbImport.value = false
  internalDataSource.value = payload.sourceName
  profileImportTags.value = []
  importSource.value = payload.mode === 'profile' ? 'profile' : 'ddl'

  if (payload.mode === 'profile') {
    await loadFromProfiles(payload)
    return
  }

  ddlText.value = payload.ddl
  analyzeMode.value = 'ai'
}

const handleSave = async () => {
  if (previewData.value.tables.length === 0) return
  
  saving.value = true
  try {
    let datasetId = props.targetDatasetId

    // 如果没有目标 ID，则新建数据集
    if (!datasetId) {
      if (!datasetName.value.trim()) {
        showToast('请输入目标数据集编码', 'warning')
        saving.value = false
        return
      }
      const dsRes = await metadataV2Api.createDataset({
        name: datasetName.value.trim(),
        display_name: datasetDisplayName.value.trim() || previewData.value.tables[0].term + '语义库',
        description: importSource.value === 'profile' ? '摸排画像导入' : 'AI 自动导入生成',
        data_source: internalDataSource.value || props.dataSource || 'default',
        tags: importSource.value === 'profile'
          ? ['Profile-Import', ...profileImportTags.value]
          : ['AI-Import'],
      })
      datasetId = (dsRes.data as any).id
    }
    
    // 保存表和字段（此时 datasetId 确定存在）
    for (const table of previewData.value.tables) {
      await metadataV2Api.saveTable(datasetId!, table)
    }
    
    emit('saved')
    showToast(props.targetDatasetId ? '元数据已更新至当前数据集' : '元数据知识库构建成功', 'success')
    handleClose()
  } catch (e: any) {
    showToast('保存失败', 'error')
  } finally {
    saving.value = false
  }
}

const handleClose = () => {
  if (analyzing.value) return
  step.value = 1
  ddlText.value = ''
  internalDataSource.value = ''
  importSource.value = 'manual'
  profileImportTags.value = []
  analyzeMode.value = 'ai'
  previewData.value = { tables: [] }
  emit('close')
}

// Helpers
const removeTable = (idx: number) => previewData.value.tables.splice(idx, 1)
const removeColumn = (tIdx: number, cIdx: number) => {
  previewData.value.tables[tIdx].columns.splice(cIdx, 1)
}
</script>

<template>
  <div v-if="show" class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black bg-opacity-50 backdrop-blur-sm">
    <div class="bg-white rounded-3xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col overflow-hidden animate-in zoom-in duration-200 relative">
      
      <!-- Analysis Overlay (Confined inside the modal) -->
      <div v-if="analyzing" class="absolute inset-0 z-[110] bg-white bg-opacity-95 flex flex-col items-center justify-center">
         <div class="w-full max-w-sm space-y-8 text-center">
            <div class="relative inline-block">
               <div class="w-20 h-20 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin"></div>
               <RocketLaunchIcon class="w-8 h-8 text-indigo-600 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
               <div class="absolute -bottom-2 -right-2 bg-indigo-600 text-white text-[10px] font-black px-2 py-1 rounded-lg shadow-lg">
                  {{ elapsedSeconds }}s
               </div>
            </div>
            <div>
               <h2 class="text-2xl font-black text-gray-900 tracking-tight">
                 {{ analyzeMode === 'profile' ? '摸排画像加载中...' : 'AI 智能解析中...' }}
               </h2>
               <p class="text-sm text-gray-500 mt-2 font-medium">{{ progressStatus }}</p>
               <p class="text-[10px] text-indigo-400 mt-1 uppercase font-black tracking-widest animate-pulse">已耗时 {{ elapsedSeconds }} 秒</p>
            </div>
            <div class="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
               <div class="h-full bg-indigo-600 transition-all duration-500 shadow-[0_0_10px_rgba(79,70,229,0.5)]" :style="{ width: `${progress}%` }"></div>
            </div>
            <button 
              @click="handleInterrupt"
              v-if="analyzeMode === 'ai'"
              class="px-6 py-2 border-2 border-gray-100 text-gray-400 hover:text-red-500 hover:border-red-100 hover:bg-red-50 rounded-xl text-xs font-black transition-all flex items-center gap-2 mx-auto uppercase tracking-widest"
            >
              <XMarkIcon class="w-4 h-4" /> 中断解析
            </button>
         </div>
      </div>

      <!-- Header -->
      <div class="px-8 py-6 border-b bg-gray-50 flex justify-between items-center">
        <div class="flex items-center gap-4">
          <div class="p-3 bg-indigo-600 rounded-xl text-white shadow-md">
            <CommandLineIcon class="w-6 h-6" />
          </div>
          <div>
            <h2 class="text-xl font-bold text-gray-900">智能元数据导入</h2>
            <div class="flex items-center gap-4 mt-1">
               <div class="flex items-center gap-2">
                  <div :class="step >= 1 ? 'bg-indigo-600 text-white' : 'bg-green-500 text-white'" class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold">1</div>
                  <span :class="step >= 1 ? 'text-indigo-600 font-bold' : 'text-green-600'" class="text-xs uppercase tracking-wider">{{ step >= 1 ? '输入定义' : '第一步已完成' }}</span>
               </div>
               <ChevronRightIcon class="w-3 h-3 text-gray-300" />
               <div class="flex items-center gap-2">
                  <div :class="step >= 2 ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-400'" class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold">2</div>
                  <span :class="step >= 2 ? 'text-indigo-600 font-bold' : 'text-gray-400'" class="text-xs uppercase tracking-wider">预览优化</span>
               </div>
            </div>
          </div>
        </div>
        <button @click="handleClose" class="text-gray-400 hover:text-gray-600 p-2 transition-colors"><XMarkIcon class="w-6 h-6" /></button>
      </div>

      <!-- Step 1: Input -->
      <div v-if="step === 1" class="flex-1 p-8 flex flex-col gap-6 overflow-hidden bg-white">
        <div v-if="!isAiEnabled" class="bg-amber-50 border border-amber-100 p-4 rounded-xl flex items-start gap-3">
           <ExclamationTriangleIcon class="w-5 h-5 text-amber-600 shrink-0" />
           <p class="text-sm text-amber-700"><b>AI 功能未开启</b>。智能导入依赖大语言模型，请先在“系统设置”中启用 AI 模块。</p>
        </div>

        <div class="flex-1 relative">
          <textarea 
            v-model="ddlText" :disabled="analyzing || !isAiEnabled"
            class="w-full h-full bg-gray-50 border border-gray-200 rounded-2xl p-6 font-mono text-sm text-gray-800 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 focus:bg-white transition-all outline-none resize-none shadow-inner custom-scrollbar disabled:opacity-50"
            placeholder="粘贴 SQL DDL (CREATE TABLE...) 或自然语言描述..."
          ></textarea>
          <div class="absolute top-4 right-4">
             <button @click="showDbImport = true" :disabled="!isAiEnabled" class="bg-white border border-gray-200 text-indigo-600 px-4 py-2 rounded-xl text-xs font-bold hover:bg-indigo-50 transition-all shadow-sm flex items-center gap-2 disabled:opacity-50">
               <CircleStackIcon class="w-4 h-4" /> 从数据库读取
             </button>
          </div>
          <div class="absolute bottom-6 right-8 flex items-center gap-4 text-[10px] font-bold uppercase tracking-widest text-gray-400">
             <span class="font-mono">{{ ddlText.length }} CHARS</span>
             <span class="bg-gray-100 px-1.5 py-0.5 rounded text-[9px]">SQL, MARKDOWN, NATURAL LANGUAGE</span>
          </div>
        </div>
        
        <div class="flex justify-center">
          <button @click="handleAnalyze" :disabled="analyzing || !ddlText || !isAiEnabled" class="px-12 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold shadow-lg transition-all active:scale-95 disabled:opacity-50 flex items-center gap-2">
            <BeakerIcon class="w-5 h-5" /> 开始 AI 解析
          </button>
        </div>
      </div>

      <!-- Step 2: Preview -->
      <div v-else class="flex-1 flex overflow-hidden bg-gray-50">
        <!-- Sidebar -->
        <div class="w-72 bg-white border-r p-6 flex flex-col gap-6">
          <div v-if="!props.targetDatasetId" class="space-y-4">
            <div>
              <label class="block text-[10px] font-black text-gray-400 uppercase tracking-widest mb-2 ml-1">数据集编码 (ID)</label>
              <input v-model="datasetName" class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-bold text-indigo-600 focus:ring-1 focus:ring-indigo-500 outline-none transition-all" />
            </div>
            <div>
              <label class="block text-[10px] font-black text-gray-400 uppercase tracking-widest mb-2 ml-1">显示名称 (Name)</label>
              <input v-model="datasetDisplayName" class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-bold text-gray-800 focus:ring-1 focus:ring-indigo-500 outline-none transition-all" />
            </div>
          </div>
          <div v-else class="p-4 bg-indigo-50 rounded-xl border border-indigo-100">
             <p class="text-[10px] font-bold text-indigo-400 uppercase tracking-widest mb-1">目标对象</p>
             <p class="text-xs font-bold text-indigo-700">正在追加至当前数据集</p>
          </div>
          
          <div class="space-y-3 flex-1">
            <div class="p-4 rounded-xl bg-white border border-gray-200 shadow-sm flex items-center justify-between">
              <div class="flex items-center gap-3">
                <TableCellsIcon class="w-5 h-5 text-gray-400" />
                <span class="text-xs font-bold text-gray-600">识别数据表</span>
              </div>
              <span class="font-black text-indigo-600">{{ previewData.tables.length }}</span>
            </div>
          </div>

          <button @click="step = 1" class="py-3 border border-gray-200 rounded-xl text-xs font-bold text-gray-400 hover:text-indigo-600 transition-all uppercase tracking-widest">← 返回修改</button>
        </div>

        <!-- Main Area -->
        <div class="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
          <section v-if="previewData.tables.length > 0" class="space-y-4">
            <h3 class="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
              <span class="w-4 h-0.5 bg-indigo-600 rounded-full"></span>
              数据表与字段定义
            </h3>
            <div class="grid gap-6">
              <div v-for="(table, tIdx) in previewData.tables" :key="tIdx" class="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm group">
                <div class="flex justify-between items-center mb-4">
                  <div class="flex items-center gap-3">
                    <span class="px-2 py-0.5 bg-gray-900 text-white font-mono text-[10px] rounded">{{ table.physical_name }}</span>
                    <input v-model="table.term" class="text-lg font-bold border-b border-transparent focus:border-indigo-500 focus:ring-0 p-0 text-gray-900 bg-transparent transition-all" />
                  </div>
                  <button @click="removeTable(Number(tIdx))" class="text-gray-300 hover:text-red-500 p-1"><TrashIcon class="w-5 h-5" /></button>
                </div>
                <div class="mb-6">
                   <textarea v-model="table.description" rows="2" class="w-full bg-gray-50 border border-transparent rounded-xl px-4 py-2 text-xs text-gray-500 font-medium focus:bg-white focus:border-indigo-100 focus:ring-0 transition-all resize-none" placeholder="表业务描述..." />
                </div>
                
                <!-- Column Details with Header -->
                <div class="border-t border-gray-100 mt-6 pt-4">
                   <div class="flex items-center gap-2 mb-4">
                      <div class="w-1 h-3 bg-indigo-600 rounded-full"></div>
                      <h4 class="text-[11px] font-black text-gray-900 uppercase tracking-widest">字段映射详情 (Mapping)</h4>
                   </div>
                   
                   <!-- Table Header Section -->
                   <div class="flex flex-col border border-gray-100 rounded-xl overflow-hidden bg-white shadow-sm">
                      <div class="grid grid-cols-12 gap-4 px-4 py-3 bg-gray-50 border-b border-gray-100 text-[9px] font-black text-gray-400 uppercase tracking-widest">
                         <div class="col-span-3 flex items-center gap-1.5">
                            <CommandLineIcon class="w-3 h-3 text-gray-400" />
                            物理字段
                         </div>
                         <div class="col-span-2">类型</div>
                         <div class="col-span-3">业务术语</div>
                         <div class="col-span-3">业务描述</div>
                         <div class="col-span-1 text-right">操作</div>
                      </div>

                      <div class="divide-y divide-gray-50">
                         <div v-for="(col, cIdx) in table.columns" :key="cIdx" class="grid grid-cols-12 gap-4 items-center p-3 hover:bg-indigo-50/40 transition-all">
                            <div class="col-span-3">
                               <span class="text-[11px] font-mono text-gray-600 block truncate font-bold" :title="col.physical_name">{{ col.physical_name }}</span>
                            </div>
                            <div class="col-span-2">
                               <select v-model="col.type" class="w-full bg-indigo-50 border-none rounded-lg text-[10px] text-indigo-700 font-black focus:ring-0 px-2 py-1 cursor-pointer">
                                  <option value="String">STRING</option>
                                  <option value="Int64">INT64</option>
                                  <option value="Float64">FLOAT64</option>
                                  <option value="DateTime">DATETIME</option>
                                  <option value="Boolean">BOOLEAN</option>
                               </select>
                            </div>
                            <div class="col-span-3">
                               <input v-model="col.term" class="w-full bg-transparent border-b border-transparent focus:border-indigo-300 text-sm font-bold text-gray-900 px-1 py-1 transition-all placeholder:font-normal placeholder:text-gray-300" placeholder="映射术语..." />
                            </div>
                            <div class="col-span-3">
                               <input v-model="col.description" class="w-full bg-transparent border-b border-transparent focus:border-indigo-300 text-xs text-gray-500 px-1 py-1 transition-all placeholder:font-normal placeholder:text-gray-300" placeholder="字段功能描述" />
                            </div>
                            <div class="col-span-1 text-right">
                               <button @click="removeColumn(Number(tIdx), Number(cIdx))" class="text-gray-300 hover:text-red-500 transition-colors p-1"><TrashIcon class="w-4 h-4" /></button>
                            </div>
                         </div>
                      </div>
                   </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <!-- Footer -->
      <div v-if="step === 2" class="px-8 py-6 bg-gray-50 border-t flex justify-end gap-4">
        <button @click="handleClose" class="px-6 py-2.5 bg-white border border-gray-200 rounded-xl font-bold text-gray-500 hover:bg-gray-100 transition-all text-sm">取消并放弃</button>
        <button @click="handleSave" :disabled="saving" class="px-10 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold shadow-md transition-all disabled:opacity-50 flex items-center gap-2 text-sm">
          <ArrowPathIcon v-if="saving" class="w-4 h-4 animate-spin" />
          <CheckCircleIcon v-else class="w-5 h-5" />
          <span>{{ saving ? '正在构建知识库...' : '确认部署到语义层' }}</span>
        </button>
      </div>
    </div>

    <DatabaseImportModal :show="showDbImport" :initial-data-source="props.dataSource" :existing-table-names="props.existingTables" @close="showDbImport = false" @confirm="handleDbImportConfirm" />
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 10px; }
</style>