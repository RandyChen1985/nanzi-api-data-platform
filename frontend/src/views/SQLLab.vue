<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { 
  CircleStackIcon, SparklesIcon, XMarkIcon, CubeIcon,
  ChevronRightIcon, ChevronUpIcon, ChevronDownIcon, QuestionMarkCircleIcon, 
  ArrowsPointingOutIcon, ArrowsPointingInIcon, ExclamationTriangleIcon, BeakerIcon,
  ClipboardDocumentIcon, PlayIcon,
} from '@heroicons/vue/24/outline'

import axios from '../utils/axios'
import { useToast } from '../composables/useToast'
import { useFullscreen } from '../composables/useFullscreen'
import { isSystemResourceGroup, sortResourceGroups, SYSTEM_RESOURCE_GROUP } from '@/types/resource'
import * as XLSX from 'xlsx'
import { saveAs } from 'file-saver'

// Components
import SchemaSidebar from '../components/sqllab/SchemaSidebar.vue'
import SqlEditor from '../components/sqllab/SqlEditor.vue'
import ResultPanel from '../components/sqllab/ResultPanel.vue'
import ResizeHandle from '../components/common/ResizeHandle.vue'
import AnalysisChat from '../components/sqllab/AnalysisChat.vue'
import Tooltip from '../components/common/Tooltip.vue'

const { showToast } = useToast()
const { isFullscreen, toggleFullscreen } = useFullscreen()

// --- State ---
const labMode = ref<'api' | 'analyst'>((localStorage.getItem('sqllab_mode') as any) || 'api')
const showAnalysisChat = ref(false)
const showExportConfirm = ref(false)
const showModeToast = ref(false)
const modeToastMsg = ref('')
const showAiErrorModal = ref(false)
const aiErrorMessage = ref('')
const currentAbortController = ref<AbortController | null>(null)

const showTableDetailModal = ref(false)
const detailTable = ref('')
const detailLoading = ref(false)
const detailColumns = ref<{name: string, type: string, comment: string}[]>([])
const detailActiveTab = ref<'structure' | 'preview'>('structure')
const detailPreviewData = ref<any>(null)
const detailPreviewLoading = ref(false)
const detailPreviewError = ref('')

const setLabMode = (mode: 'api' | 'analyst') => {
  labMode.value = mode
  localStorage.setItem('sqllab_mode', mode)
  
  // Enforce layout based on mode
  sidebarCollapsed.value = mode === 'api'
  
  modeToastMsg.value = `已切换至 ${mode === 'api' ? '🛠️ API 调试' : '📊 自助取数'} 模式`
  showModeToast.value = true
  setTimeout(() => { showModeToast.value = false }, 2000)
}

// Layout State
const sidebarWidth = ref(260)
const editorHeight = ref(550)
const sqllabContainer = ref<HTMLElement | null>(null)

watch(isFullscreen, (val) => {
  if (val) editorHeight.value = window.innerHeight - 200
  else editorHeight.value = 550
})

const handleSidebarResize = (newX: number) => { if (newX > 150 && newX < 600) sidebarWidth.value = newX }
const handleEditorResize = (newY: number) => {
  const container = sqllabContainer.value
  if (container) {
    const rect = container.getBoundingClientRect()
    const newHeight = newY - rect.top - 180 
    if (newHeight > 150 && newHeight < 1500) editorHeight.value = newHeight
  }
}

const hasPerm = (code: string) => {
  const info = localStorage.getItem('user_info')
  if (!info) return false
  const user = JSON.parse(info)
  if (user.role === 'admin') return true
  return user.permissions?.elements?.includes(code)
}

const hasApiMode = computed(() => hasPerm('element:lab:mode_api'))
const hasAnalystMode = computed(() => hasPerm('element:lab:mode_analyst'))
const isAdmin = computed(() => {
  const info = localStorage.getItem('user_info')
  if (!info) return false
  const user = JSON.parse(info)
  return user.role === 'admin'
})
const noLabModeAccess = computed(() => !hasApiMode.value && !hasAnalystMode.value)

// --- Interfaces ---
interface DataSource { id: number; source_name: string; source_type: string }
interface PreviewResult { columns: { name: string; type: string }[]; rows: any[][]; execution_time_ms: number; scanned_rows: number }
interface QueryTab {
  id: string; name: string; sql: string; testParams: Record<string, any>; result: PreviewResult | null;
  error: string | null; executing: boolean; activeSubTab: 'result' | 'ai';
  aiContent: string; optimizedSql: string; aiDetectedParams: string[]; columnLabels: Record<string, string>;
  emptyTestPassed: boolean;
  recalledContext?: any[];
}

// --- Tab Management ---
const tabs = ref<QueryTab[]>([])
const activeTabIndex = ref(0)
const dataSources = ref<DataSource[]>([])
const selectedSourceId = ref<number | null>(null)
const loadingSources = ref(false)
const columnsCache = ref<Record<string, {name: string, type: string}[]>>({})

const aiPlaceholder = computed(() => {
  if (autoContext.value) {
    return "输入业务问题（如：查询最近7天各机房的PUE趋势），AI 将自动寻找关联表与指标..."
  }
  if (selectedTables.value.length > 0) {
    return `已锁定勾选的 ${selectedTables.value.length} 张表，请输入 SQL 指令...`
  }
  return "请在左侧勾选数据表，或开启“智能关联元数据”直接提问..."
})

const createTab = (initialSql?: string) => {
  const id = Math.random().toString(36).substring(7)
  tabs.value.push({
    id, name: `查询 ${tabs.value.length + 1}`, sql: initialSql || '',
    testParams: { user_pattern: '%' }, result: null, error: null, executing: false, activeSubTab: 'result',
    aiContent: '', optimizedSql: '', aiDetectedParams: [], columnLabels: {}, emptyTestPassed: false,
    recalledContext: []
  })
  activeTabIndex.value = tabs.value.length - 1
}

const closeTab = (index: number) => {
  if (tabs.value.length <= 1) return
  tabs.value.splice(index, 1)
  if (activeTabIndex.value >= tabs.value.length) activeTabIndex.value = tabs.value.length - 1
}

const closeAllTabs = () => {
  tabs.value = []
  createTab()
  activeTabIndex.value = 0
  showToast('已关闭所有查询标签页', 'info')
}

const closeOtherTabs = (index: number) => {
  if (index < 0 || index >= tabs.value.length) return
  const targetTab = tabs.value[index]
  if (targetTab) {
    tabs.value = [targetTab]
    activeTabIndex.value = 0
    showToast('已关闭其他标签页', 'info')
  }
}

// --- Sources & Metadata ---

const saveTabs = () => {
  const data = tabs.value.map(t => ({ name: t.name, sql: t.sql, testParams: t.testParams }))
  localStorage.setItem('sql_lab_tabs', JSON.stringify(data))
}

const loadTabs = () => {
  const saved = localStorage.getItem('sql_lab_tabs')
  if (saved) {
    try {
      const data = JSON.parse(saved)
      data.forEach((d: any) => {
        tabs.value.push({
          id: Math.random().toString(36).substring(7), name: d.name, sql: d.sql, testParams: d.testParams,
          result: null, error: null, executing: false, activeSubTab: 'result',
          aiContent: '', optimizedSql: '', aiDetectedParams: [], columnLabels: {}, emptyTestPassed: false,
          recalledContext: []
        })
      })
    } catch (e) { createTab() }
  }
  if (tabs.value.length === 0) createTab()
}
watch(tabs, saveTabs, { deep: true })

// --- AI Logic ---
const isAiEnabled = ref(false)
const aiLoading = ref(false)
const generating = ref(false)
const aiPrompt = ref('')
const aiInputRef = ref<HTMLInputElement | null>(null)
const sidebarCollapsed = ref(false)
const autoContext = ref(false)
const metaStats = ref({ dataset_count: 0, table_count: 0 })
const isVectorSupported = ref(true)

const checkVectorSupport = async () => {
  try {
    const res = await axios.post('/api/portal/system/test-connection/vector')
    isVectorSupported.value = res.data.status === 'success'
    // 如果不支持，强制关闭智能关联
    if (!isVectorSupported.value) {
      autoContext.value = false
    }
  } catch (e) {
    isVectorSupported.value = false
    autoContext.value = false
  }
}

const toggleAutoContext = () => {
  if (!isVectorSupported.value) return
  autoContext.value = !autoContext.value
  // 如果切换到开启状态，自动清除手动勾选的表，确保纯净的智能关联体验
  if (autoContext.value) {
    selectedTables.value = []
    showToast('已开启智能关联模式，AI 将自动寻找业务资产', 'info')
  } else {
    showToast('已关闭智能关联，您可以手动勾选左侧数据表', 'info')
  }
}

// --- AI Debug Logs ---
const aiLogs = ref<{timestamp: number, type: 'info' | 'error' | 'success', msg: string}[]>([])
const addAiLog = (msg: string, type: 'info' | 'error' | 'success' = 'info') => {
  aiLogs.value.push({ timestamp: Date.now(), type, msg })
  // Keep last 100 logs
  if (aiLogs.value.length > 100) aiLogs.value.shift()
}
const clearAiLogs = () => { aiLogs.value = [] }

// --- Tab Management ---
const availableTables = ref<any[]>([])
const selectedTables = ref<string[]>([])
const loadingTables = ref(false)
const showTableSelector = ref(false)
const flashTableTitle = ref(false)
const showSuggestionModal = ref(false)
const suggestions = ref<{title: string, description: string, sql: string}[]>([])
const loadingSuggestions = ref(false)
const aiContextTable = ref<string | null>(null)
const selectedSuggestionIdx = ref(0)
const queryHistory = ref<{sql: string, params: any, timestamp: number}[]>([])

const selectedSuggestion = computed(() => suggestions.value[selectedSuggestionIdx.value] ?? null)

const suggestionModalSubtitle = computed(() => {
  if (aiContextTable.value) return `基于表「${aiContextTable.value}」生成`
  if (selectedTables.value.length > 0) return `基于已选 ${selectedTables.value.length} 张表`
  return '基于当前数据源元数据智能推荐'
})

watch(showSuggestionModal, (open) => {
  if (open) selectedSuggestionIdx.value = 0
})

const adoptSuggestion = (sql: string) => {
  createTab(sql)
  showSuggestionModal.value = false
  showToast('已采用推荐查询', 'success')
}

const copySuggestionSql = async (sql: string) => {
  try {
    await navigator.clipboard.writeText(sql)
    showToast('SQL 已复制到剪贴板', 'success')
  } catch {
    showToast('复制失败，请手动选择复制', 'error')
  }
}

type AiTaskType = 'prompt' | 'profile' | 'suggest-global' | 'suggest-table' | null

const isAiProcessing = computed(() => generating.value || loadingSuggestions.value)
const aiTaskType = ref<AiTaskType>(null)
const profileGenerateTable = ref('')
const showAiStatusBar = ref(false)
const aiElapsedSec = ref(0)
let aiStatusDelayTimer: ReturnType<typeof setTimeout> | null = null
let aiElapsedTimer: ReturnType<typeof setInterval> | null = null

const aiProcessingTitle = computed(() => {
  switch (aiTaskType.value) {
    case 'profile':
      return `正在基于摸排画像生成分析 SQL`
    case 'suggest-table':
      return aiContextTable.value
        ? `正在为 [${aiContextTable.value}] 生成查询场景`
        : '正在生成专属查询场景'
    case 'suggest-global':
      return '正在挖掘业务洞察，生成智能推荐'
    case 'prompt':
    default:
      return '正在为您构建高质量 SQL 代码'
  }
})

const aiStatusSubtitle = computed(() => {
  switch (aiTaskType.value) {
    case 'profile':
      return profileGenerateTable.value
        ? `表 [${profileGenerateTable.value}] · 字段画像 / 样例数据 / DDL`
        : '基于 AI 摸排画像组装上下文'
    case 'suggest-table':
      return `单表精准建模 · ${labMode.value === 'api' ? 'API 调试模式' : '自助取数模式'}`
    case 'suggest-global':
      return selectedTables.value.length > 0
        ? `已选定 ${selectedTables.value.length} 张表作为推荐上下文`
        : '扫描全库元数据，匹配高价值查询场景'
    case 'prompt':
      if (autoContext.value) return '智能关联元数据 · 语义检索相关业务资产'
      if (selectedTables.value.length > 0) return `手动锁定 ${selectedTables.value.length} 张表作为生成上下文`
      return '基于基础表结构进行建模分析'
    default:
      return 'AI 引擎处理中'
  }
})

const latestAiLogMessage = computed(() => {
  const logs = aiLogs.value
  if (!logs.length) return ''
  return logs[logs.length - 1]?.msg || ''
})

watch(isAiProcessing, (processing) => {
  if (processing) {
    aiBarCollapsed.value = false
    aiElapsedSec.value = 0
    aiElapsedTimer = setInterval(() => { aiElapsedSec.value += 1 }, 1000)
    aiStatusDelayTimer = setTimeout(() => {
      if (isAiProcessing.value) showAiStatusBar.value = true
    }, 600)
  } else {
    if (aiStatusDelayTimer) clearTimeout(aiStatusDelayTimer)
    aiStatusDelayTimer = null
    if (aiElapsedTimer) clearInterval(aiElapsedTimer)
    aiElapsedTimer = null
    showAiStatusBar.value = false
    aiElapsedSec.value = 0
    aiTaskType.value = null
    profileGenerateTable.value = ''
  }
})

onUnmounted(() => {
  if (aiStatusDelayTimer) clearTimeout(aiStatusDelayTimer)
  if (aiElapsedTimer) clearInterval(aiElapsedTimer)
})

const aiExamples = [
  "查询最近 7 天注册的活跃用户数量",
  "按角色统计用户，并按创建时间降序排列",
  "找出所有状态为正常的管理员用户",
  "统计各部门的平均薪资及其占比情况",
  "查询重复的邮箱地址及其出现次数"
]
const showAiExamples = ref(false)
const AI_BAR_COLLAPSED_KEY = 'sqllab_ai_bar_collapsed_v2'
const aiBarCollapsed = ref(localStorage.getItem(AI_BAR_COLLAPSED_KEY) !== '0')

watch(aiBarCollapsed, (collapsed) => {
  localStorage.setItem(AI_BAR_COLLAPSED_KEY, collapsed ? '1' : '0')
})

const expandAiBar = () => {
  aiBarCollapsed.value = false
  nextTick(() => aiInputRef.value?.focus())
}

const selectAiExample = (example: string) => {
  aiPrompt.value = example
  showAiExamples.value = false
  nextTick(() => {
    aiInputRef.value?.focus()
  })
}

const clearAiPrompt = () => {
  aiPrompt.value = ''
  nextTick(() => {
    aiInputRef.value?.focus()
  })
}

const cancelAiTask = () => {
  if (currentAbortController.value) {
    currentAbortController.value.abort()
    currentAbortController.value = null
  }
  generating.value = false
  loadingSuggestions.value = false
  addAiLog("用户已中断 AI 任务", "error")
  showToast('任务已取消', 'info')
}


const currentTab = computed(() => tabs.value[activeTabIndex.value] || null)

const currentDataSourceInfo = computed(() => {
  const source = dataSources.value.find(ds => ds.id === selectedSourceId.value) as any
  if (!source) return undefined
  return {
    name: source.source_name,
    datasetsCount: source.datasets_count || 0,
  }
})
const noAccessToAnyDataSource = ref(false)

const fetchDataSources = async () => {
  loadingSources.value = true
  noAccessToAnyDataSource.value = false
  try {
    const aiRes = await axios.get('/api/portal/system/config/ai')
    isAiEnabled.value = String(aiRes.data.enabled).toLowerCase() === 'true'
    const res = await axios.get('/api/portal/datasource/datasources?status=active')
    let allSources = res.data
    const infoStr = localStorage.getItem('user_info')
    if (infoStr) {
      const user = JSON.parse(infoStr)
      // Check both root role and nested permissions role
      const currentRole = user.role || user.permissions?.role
      if (currentRole !== 'admin') {
        const allowedDS = user.permissions?.datasources || []
        allSources = allSources.filter((ds: any) => allowedDS.includes(`ds:${ds.source_name}`))
      }
    }
    dataSources.value = allSources
    if (dataSources.value.length > 0) selectedSourceId.value = dataSources.value[0]?.id || null
    else noAccessToAnyDataSource.value = true
  } catch (e: any) {
    if (e.response?.status === 403) noAccessToAnyDataSource.value = true
    else showToast('获取数据源失败', 'error')
  } finally { loadingSources.value = false }
}

const fetchMetaStats = async () => {
  metaStats.value = { dataset_count: 0, table_count: 0 }
  if (!selectedSourceId.value) return
  try {
    const source = dataSources.value.find(ds => ds.id === selectedSourceId.value)
    if (!source) return
    const res = await axios.get('/api/portal/meta/v2/stats', { params: { data_source: source.source_name } })
    metaStats.value = res.data
  } catch (e) { 
    console.error('获取元数据统计失败', e)
    metaStats.value = { dataset_count: 0, table_count: 0 }
  }
}

const tableProfilesMap = ref<Record<string, any>>({})
const hasProfiled = computed(() => Object.keys(tableProfilesMap.value).length > 0)

const fetchTableProfiles = async () => {
  if (!selectedSourceId.value) return
  try {
    const res = await axios.get(`/api/portal/datasource/datasources/${selectedSourceId.value}/table-profiles`, {
      params: { summary: true, status: 2 },
    })
    const profiles: any[] = Array.isArray(res.data) ? res.data : []
    const map: Record<string, any> = {}
    profiles.forEach((p: any) => { map[p.table_name] = p })
    tableProfilesMap.value = map
  } catch {
    tableProfilesMap.value = {}
  }
}

const fetchTableProfileDetail = async (tableName: string) => {
  if (!selectedSourceId.value || tableProfilesMap.value[tableName]?.columns_profile) return
  try {
    const res = await axios.get(
      `/api/portal/datasource/datasources/${selectedSourceId.value}/table-profiles/${encodeURIComponent(tableName)}`
    )
    tableProfilesMap.value[tableName] = {
      ...tableProfilesMap.value[tableName],
      ...res.data,
    }
  } catch {
    // 单表详情加载失败时保留摘要信息
  }
}

const fetchAvailableTables = async () => {
  if (!selectedSourceId.value) return
  loadingTables.value = true
  availableTables.value = []
  try {
    const source = dataSources.value.find(ds => ds.id === selectedSourceId.value)
    if (!source) return
    const res = await axios.post('/api/portal/meta/datasource/tables', { data_source: source.source_name })
    availableTables.value = res.data.tables || []
    
    // 获取 V2 元数据统计
    fetchMetaStats()
    // 异步拉取摸排画像
    fetchTableProfiles()

    // 自动预取前 30 张表的字段，用于优化编辑器补全提示
    if (availableTables.value.length > 0) {
      const topTables = availableTables.value.slice(0, 30)
      topTables.forEach(t => {
        const tableName = typeof t === 'string' ? t : t.name
        if (!columnsCache.value[tableName]) {
          fetchColumns(tableName)
        }
      })
    }
  } catch (e: any) {
    showToast('获取表列表失败', 'error')
  } finally { loadingTables.value = false }
}

watch(selectedSourceId, () => {
  selectedTables.value = []
  availableTables.value = []
  columnsCache.value = {}
  tableProfilesMap.value = {}
  fetchAvailableTables()
})

const fetchColumns = async (table: string) => {
  if (!selectedSourceId.value || columnsCache.value[table]) return
  const source = dataSources.value.find(ds => ds.id === selectedSourceId.value)
  if (!source) return
  try {
    const res = await axios.post('/api/portal/meta/datasource/columns', { data_source: source.source_name, table_name: table })
    columnsCache.value[table] = res.data.columns
  } catch (e) { console.error(e) }
}

const handleColumnInsert = (colName: string) => { if (currentTab.value) currentTab.value.sql += ` ${colName}` }
const handleTabRename = (idx: number, name: string) => { if (tabs.value[idx]) tabs.value[idx].name = name }

const saveToHistory = (newSql: string, newParams: any) => {
  if (queryHistory.value.length > 0 && queryHistory.value[0]?.sql === newSql) return
  queryHistory.value.unshift({ sql: newSql, params: { ...newParams }, timestamp: Date.now() })
  if (queryHistory.value.length > 20) queryHistory.value = queryHistory.value.slice(0, 20)
  localStorage.setItem('sql_lab_history', JSON.stringify(queryHistory.value))
}
const loadHistory = () => {
  const saved = localStorage.getItem('sql_lab_history')
  if (saved) { try { queryHistory.value = JSON.parse(saved) } catch (e) {} }
}
const restoreHistory = (item: {sql: string, params: any}) => {
  if (currentTab.value) { currentTab.value.sql = item.sql; currentTab.value.testParams = { ...item.params }; showToast('已还原历史查询', 'success') }
}
const deleteHistory = (index: number) => {
  queryHistory.value.splice(index, 1)
  localStorage.setItem('sql_lab_history', JSON.stringify(queryHistory.value))
  showToast('已删除历史记录', 'info')
}

const PREVIEW_LIMIT_OPTIONS = [50, 100, 200] as const
type PreviewLimit = (typeof PREVIEW_LIMIT_OPTIONS)[number]

const loadPreviewLimit = (): PreviewLimit => {
  const saved = Number(localStorage.getItem('sqllab_preview_limit'))
  return (PREVIEW_LIMIT_OPTIONS as readonly number[]).includes(saved) ? (saved as PreviewLimit) : 100
}

const previewLimit = ref<PreviewLimit>(loadPreviewLimit())

watch(previewLimit, (value) => {
  localStorage.setItem('sqllab_preview_limit', String(value))
})

const resultPanelRef = ref<InstanceType<typeof ResultPanel> | null>(null)
const sqlEditorRef = ref<InstanceType<typeof SqlEditor> | null>(null)

const runQuery = async (overrideSql?: string) => {
  if (!selectedSourceId.value || !currentTab.value) return
  currentTab.value.activeSubTab = 'result'
  if (!isFullscreen.value) {
    nextTick(() => resultPanelRef.value?.scrollToTop())
  }
  currentTab.value.executing = true
  currentTab.value.result = null
  currentTab.value.error = null
  const sqlToRun = overrideSql || currentTab.value.sql
  try {
    const res = await axios.post('/api/portal/lab/preview', { source_id: selectedSourceId.value, sql: sqlToRun, params: currentTab.value.testParams, limit: previewLimit.value })
    currentTab.value.result = res.data
    saveToHistory(sqlToRun, currentTab.value.testParams)
  } catch (e: any) { currentTab.value.error = e.response?.data?.message || e.response?.data?.detail || e.message }
  finally { currentTab.value.executing = false }
}

const handleClearResult = () => {
  if (currentTab.value) {
    currentTab.value.result = null
    nextTick(() => {
      // 1. Focus Editor
      sqlEditorRef.value?.focus()
      
      // 2. Scroll to Top (Only in normal mode)
      if (!isFullscreen.value) {
        window.scrollTo({ top: 0, behavior: 'smooth' })
        sqllabContainer.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    })
  }
}

const runEmptyParamTest = async () => {
  if (!currentTab.value) return
  currentTab.value.emptyTestPassed = false
  const oldParams = { ...currentTab.value.testParams }
  Object.keys(currentTab.value.testParams).forEach(k => { currentTab.value!.testParams[k] = undefined })
  await runQuery()
  if (currentTab.value.result && !currentTab.value.error) {
    currentTab.value.emptyTestPassed = true
    showToast('空参测试通过', 'success')
  }
  currentTab.value.testParams = oldParams
}

watch(() => currentTab.value?.sql, (newVal) => {
  if (currentTab.value) {
    currentTab.value.emptyTestPassed = false
    // 如果 SQL 被清空，同步清空 AI 召回上下文
    if (!newVal || newVal.trim() === '') {
      currentTab.value.recalledContext = []
    }
  }
})

const submitAiTask = async () => {
  const promptVal = aiPrompt.value.trim()
  const sourceId = selectedSourceId.value
  
  if (!promptVal || !sourceId) return
  if (!hasPerm('element:lab:generate')) return showToast('暂无 AI 生成权限', 'error')
  if (isAiProcessing.value) return
  
  // 始终开启智能关联提示
  if (!autoContext.value && selectedTables.value.length === 0) {
    return showToast('请先开启“智能关联元数据”后再提问，以便 AI 获取业务背景', 'warning')
  }

  addAiLog(`启动 AI 智能 SQL 生成任务...`, 'info')
  addAiLog(`用户 Prompt: "${promptVal}"`, 'info')

  aiTaskType.value = 'prompt'
  generating.value = true
  currentAbortController.value = new AbortController()
  const source = dataSources.value.find(ds => ds.id === sourceId)
  
  try {
    const endpoint = '/api/portal/lab/ai/generate'
    
    if (autoContext.value) {
      addAiLog("开启智能关联元数据模式，正在通过语义引擎检索相关元数据...", "info")
    } else if (selectedTables.value.length > 0) {
      addAiLog(`强制使用用户手动选中的 ${selectedTables.value.length} 张表作为上下文`, "info")
    }

    const res = await axios.post(endpoint, { 
      prompt: promptVal, 
      source_id: sourceId, 
      source_type: source?.source_type || 'mysql',
      tables: autoContext.value ? null : selectedTables.value.slice(0, 10), 
      mode: labMode.value 
    }, {
      signal: currentAbortController.value.signal
    })
    
    if (res.data?.sql) { 
      // 成功后再决定是否新建 Tab
      if (currentTab.value && currentTab.value.sql?.trim().length > 10) {
        createTab()
        await nextTick()
      }

      const targetTab = currentTab.value
      if (!targetTab) return

      targetTab.sql = res.data.sql
      targetTab.recalledContext = res.data.recalled_context || []
      targetTab.name = promptVal.slice(0, 10) + (promptVal.length > 10 ? '...' : '')
      
      const debug = res.data.debug_info
      if (debug) {
        addAiLog(`[DEBUG] 检索链路: 命中 ${debug.recalled_items_count} 个潜在业务资产`, 'info')
        if (debug.raw_recall_details?.length) {
          debug.raw_recall_details.forEach((item: any) => {
            const scoreText = item.score ? `Score: ${item.score.toFixed(4)}` : ''
            addAiLog(`[DEBUG] -> 资产: ${item.name} (${item.type}) | 归因: ${item.reason} ${scoreText}`, 'info')
            if (isAdmin.value) console.log('RAG Raw Item:', item)
          })
          if (isAdmin.value) {
            addAiLog(`[DEBUG] RAW_RAG_JSON: ${JSON.stringify(debug.raw_recall_details, null, 2)}`, 'info')
          }
        }
        addAiLog(`[DEBUG] 提示词上下文长度: ${debug.schema_context_len} chars`, 'info')
      }

      addAiLog(`AI 生成 SQL 成功，耗时 ${res.headers?.['x-process-time'] || 'N/A'}ms`, 'success')
      aiPrompt.value = ''
      showToast('SQL 已生成', 'success') 
    }
  } catch (e: any) { 
    const errorMsg = e.response?.data?.detail || e.message || '未知错误'
    addAiLog(`AI 请求失败: ${errorMsg}`, 'error')
    
    if (e.response?.status === 400) {
      aiErrorMessage.value = errorMsg
      showAiErrorModal.value = true
    } else {
      showToast('AI 请求失败: ' + errorMsg, 'error') 
    }
  }
  finally { 
    generating.value = false 
    currentAbortController.value = null
  }
}

const runAiAction = async () => {
  const targetTab = currentTab.value
  if (!targetTab?.sql?.trim() || !selectedSourceId.value) return
  
  addAiLog("启动 AI 语义校验任务...", "info")
  const source = dataSources.value.find(ds => ds.id === selectedSourceId.value)
  
  targetTab.activeSubTab = 'ai'
  if (!isFullscreen.value) {
    nextTick(() => resultPanelRef.value?.scrollToTop())
  }
  
  aiLoading.value = true
  try {
    const res = await axios.post('/api/portal/lab/ai/check', { 
      sql: targetTab.sql, 
      source_type: source?.source_type || 'mysql' 
    })
    
    if (!tabs.value.find(t => t.id === targetTab.id)) return

    targetTab.aiContent = res.data.content
    targetTab.optimizedSql = res.data.content.match(/```sql([\s\S]*?)```/)?.[1]?.trim() || ''
    addAiLog("AI 校验完成，已生成优化建议与纠错报告", "success")
  } catch (e: any) { 
    addAiLog(`语义校验失败: ${e.message}`, "error")
    targetTab.aiContent = `❌ 失败: ${e.message}` 
  }
  finally { 
    aiLoading.value = false 
  }
}

const handleAiFixError = async () => {
  const targetTab = currentTab.value
  const sql = targetTab?.sql
  const error = targetTab?.error
  
  if (!targetTab || !sql || !error || !selectedSourceId.value) return
  
  targetTab.activeSubTab = 'ai'
  if (!isFullscreen.value) {
    nextTick(() => resultPanelRef.value?.scrollToTop())
  }
  
  aiLoading.value = true
  try {
    const res = await axios.post('/api/portal/lab/ai/fix-error', { 
      sql: sql, 
      error: error,
      source_id: selectedSourceId.value
    })
    
    if (!tabs.value.find(t => t.id === targetTab.id)) return

    targetTab.aiContent = res.data.content
    targetTab.optimizedSql = res.data.content.match(/```sql([\s\S]*?)```/)?.[1]?.trim() || ''
  } catch (e: any) { 
    targetTab.aiContent = `❌ 纠错请求失败: ${e.message}` 
  } finally { 
    aiLoading.value = false 
  }
}

const applyAiFix = () => {
  if (currentTab.value?.optimizedSql) {
    currentTab.value.sql = currentTab.value.optimizedSql
    currentTab.value.activeSubTab = 'result'
    nextTick(() => {
      // 1. Focus Editor
      sqlEditorRef.value?.focus()
      
      // 2. Scroll to Top (Only in normal mode)
      if (!isFullscreen.value) {
        window.scrollTo({ top: 0, behavior: 'smooth' })
        sqllabContainer.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    })
  }
}

const openSuggestionModal = async () => {
  if (!selectedSourceId.value) return showToast('请先选择数据源', 'warning')
  if (isAiProcessing.value) return

  aiTaskType.value = 'suggest-global'
  aiContextTable.value = null
  loadingSuggestions.value = true
  currentAbortController.value = new AbortController()
  
  const hasSelected = selectedTables.value.length > 0
  const logMsg = hasSelected 
    ? `触发“一键推荐”任务 [模式: ${labMode.value}]，正在基于选定的 ${selectedTables.value.length} 张表生成专属查询场景...`
    : `触发“一键推荐”任务 [模式: ${labMode.value}]，正在扫描全库元数据生成查询场景...`
  
  addAiLog(logMsg, "info")
  
  try {
    const res = await axios.post('/api/portal/lab/ai/suggest-queries', {
      source_id: selectedSourceId.value,
      tables: selectedTables.value.length > 0 ? selectedTables.value : null,
      mode: labMode.value
    }, {
      signal: currentAbortController.value.signal
    })
    suggestions.value = res.data || []
    addAiLog(`推荐成功，已发现 ${suggestions.value.length} 个潜在业务查询场景`, "success")
    
    // 只有在获取成功后才显示弹窗
    if (suggestions.value.length > 0) {
      showSuggestionModal.value = true
    } else {
      showToast('未发现可推荐场景，请尝试补充元数据描述', 'info')
    }
  } catch (e: any) {
    const errorMsg = e.response?.data?.detail || e.message
    addAiLog(`推荐任务失败: ${errorMsg}`, "error")
    showToast('获取推荐失败: ' + errorMsg, 'error')
  } finally {
    loadingSuggestions.value = false
    currentAbortController.value = null
  }
}

const openTableAiSuggestion = async (table: string) => {
  if (!selectedSourceId.value) return
  if (!hasPerm('element:lab:generate')) return showToast('暂无智能推荐权限', 'error')
  if (isAiProcessing.value) return

  aiContextTable.value = table
  aiTaskType.value = 'suggest-table'
  loadingSuggestions.value = true
  currentAbortController.value = new AbortController()
  suggestions.value = []

  addAiLog(`针对单表 [${table}] 触发“AI 建模”任务，正在生成专属业务查询场景...`, "info")
  
  try {
    const res = await axios.post('/api/portal/lab/ai/suggest-queries', { 
      source_id: selectedSourceId.value, 
      tables: [table],
      mode: labMode.value
    }, {
      signal: currentAbortController.value.signal
    })
    
    suggestions.value = res.data || []
    
    if (suggestions.value.length > 0) {
      addAiLog(`推荐成功，已发现 ${suggestions.value.length} 个关于表 [${table}] 的潜在查询场景`, "success")
      showSuggestionModal.value = true
    } else {
      addAiLog(`表 [${table}] 暂无推荐场景，建议检查该表的元数据描述是否完整`, "error")
      showToast('未发现可推荐场景', 'info')
    }
  } catch (e: any) {
    const errorMsg = e.response?.data?.detail || e.message
    addAiLog(`推荐任务失败: ${errorMsg}`, "error")
    showToast('获取推荐失败: ' + errorMsg, 'error')
  } finally { 
    loadingSuggestions.value = false 
    currentAbortController.value = null
  }
}

const openTableDetail = async (table: string) => {
  detailTable.value = table
  detailActiveTab.value = 'structure'
  detailPreviewData.value = null
  detailPreviewError.value = ''
  showTableDetailModal.value = true
  detailLoading.value = true
  const source = dataSources.value.find(ds => ds.id === selectedSourceId.value)
  try {
    const colRes = await axios.post('/api/portal/meta/datasource/columns', { data_source: source?.source_name, table_name: table })
    detailColumns.value = colRes.data.columns
  } finally { detailLoading.value = false }
}

const handleTableProfileGenerate = async (table: string) => {
  if (!selectedSourceId.value) return showToast('请先选择数据源', 'warning')
  if (!isAiEnabled.value) return showToast('AI 功能未启用', 'warning')
  if (!hasPerm('element:lab:generate')) return showToast('暂无 AI 生成权限', 'error')

  const profile = tableProfilesMap.value[table]
  if (!profile) return showToast(`表 [${table}] 暂无摸排画像`, 'warning')
  if (isAiProcessing.value) return

  addAiLog(`高级模式：基于表 [${table}] 摸排画像生成分析 SQL...`, 'info')
  aiTaskType.value = 'profile'
  profileGenerateTable.value = table
  generating.value = true
  currentAbortController.value = new AbortController()

  try {
    const res = await axios.post('/api/portal/lab/ai/generate-from-profile', {
      source_id: selectedSourceId.value,
      table_name: table,
      mode: labMode.value,
    }, {
      signal: currentAbortController.value.signal,
    })

    if (res.data?.sql) {
      if (currentTab.value && currentTab.value.sql?.trim().length > 10) {
        createTab()
        await nextTick()
      }

      const targetTab = currentTab.value
      if (!targetTab) return

      targetTab.sql = res.data.sql
      targetTab.recalledContext = []
      const label = res.data.profile_summary?.ai_term || table
      targetTab.name = `${label} 分析`

      addAiLog(`已基于摸排画像生成表 [${table}] 的分析 SQL`, 'success')
      showToast('分析 SQL 已生成', 'success')
      nextTick(() => sqlEditorRef.value?.focus())
    }
  } catch (e: any) {
    if (e.name === 'CanceledError' || e.code === 'ERR_CANCELED') return
    const errorMsg = e.response?.data?.detail || e.message || '未知错误'
    addAiLog(`摸排 SQL 生成失败: ${errorMsg}`, 'error')
    showToast('生成失败: ' + errorMsg, 'error')
  } finally {
    generating.value = false
    currentAbortController.value = null
  }
}

const fetchTablePreview = async () => {
  if (!detailTable.value || !selectedSourceId.value) return
  detailActiveTab.value = 'preview'
  if (detailPreviewData.value) return // Already loaded

  detailPreviewLoading.value = true
  detailPreviewError.value = ''
  try {
    const res = await axios.post('/api/portal/lab/preview', { 
      source_id: selectedSourceId.value, 
      sql: `SELECT * FROM ${detailTable.value}`,
      params: {}, 
      limit: 50 
    })
    detailPreviewData.value = res.data
  } catch (e: any) {
    detailPreviewError.value = e.response?.data?.message || e.message
  } finally {
    detailPreviewLoading.value = false
  }
}

const exportToExcel = async () => {
  if (!currentTab.value?.result) return
  if (!hasPerm('element:lab:export')) return showToast('暂无导出权限', 'error')
  showExportConfirm.value = true
}

const executeExport = async () => {
  showExportConfirm.value = false
  if (!currentTab.value?.result) return
  const rows = currentTab.value.result.rows
  const dataToExport = rows.slice(0, 5000)
  try {
    const wb = XLSX.utils.book_new()
    const source = dataSources.value.find(ds => ds.id === selectedSourceId.value)
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([['数据源', source?.source_name], ['SQL', currentTab.value.sql]]), "说明")
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([currentTab.value.result.columns.map(c => c.name), ...dataToExport]), "数据")
    saveAs(new Blob([XLSX.write(wb, { bookType: 'xlsx', type: 'array' })]), `export_${Date.now()}.xlsx`)
    await axios.post('/api/portal/audit/logs/custom_export', { sql: currentTab.value.sql, row_count: dataToExport.length, data_source: source?.source_name || '', format: 'xlsx' })
    showToast('导出成功', 'success')
  } catch (e) { showToast('导出失败', 'error') }
}

const openAiAnalysis = () => { 
  if (!hasPerm('element:lab:analysis')) return showToast('暂无 AI 分析权限', 'error')
  if (currentTab.value?.result) showAnalysisChat.value = true 
}

// --- Publish Modal ---
const showPublishModal = ref(false)
const publishing = ref(false)
const showMockPreview = ref(false)
const existingGroups = ref<string[]>([])
const selectableGroups = computed(() => existingGroups.value.filter((g) => !isSystemResourceGroup(g)))
const showGroupDropdown = ref(false)
const selectedFilters = ref<string[]>([])
const hideGroupDropdown = () => { setTimeout(() => { showGroupDropdown.value = false }, 200) }
const publishForm = ref({
  resource_key: '',
  resource_name: '',
  resource_group: 'SQL_LAB',
  cache_ttl: 300,
  remarks: '',
})

const fetchResourceGroups = async () => {
  try {
    const res = await axios.get('/api/portal/dashboard/my-resources')
    const data = Array.isArray(res.data) ? res.data : (res.data?.items || [])
    const groups = new Set<string>()
    data.forEach((r: any) => { if (r.resource_group && !isSystemResourceGroup(r.resource_group)) groups.add(r.resource_group) })
    existingGroups.value = sortResourceGroups(Array.from(groups))
  } catch (e) { console.error('Failed to fetch groups', e) }
}

const suggestLabels = async () => {
  if (!currentTab.value?.result || !currentTab.value.sql) return
  try {
    const res = await axios.post('/api/portal/lab/ai/suggest-labels', { 
      sql: currentTab.value.sql, 
      columns: currentTab.value.result.columns.map(c => c.name) 
    })
    if (res.data) currentTab.value.columnLabels = res.data
  } catch (e) {}
}

const openPublishModal = () => {
  if (!currentTab.value?.result) { showToast('请先运行查询成功后再发布 API', 'warning'); return }
  currentTab.value.columnLabels = {}
  showMockPreview.value = false
  fetchResourceGroups()
  
  if (isAiEnabled.value) suggestLabels()
  
  const sql = currentTab.value.sql
  const vars = new Set<string>()
  const matches = sql.match(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g)
  if (matches) matches.forEach(m => vars.add(m.replace(/\{\{\s*|\s*\}\}/g, '')))
  
  const allParams = new Set([...currentTab.value.aiDetectedParams, ...vars])
  selectedFilters.value = [...allParams]
  
  publishForm.value.resource_key = 'lab.' + Math.random().toString(36).substring(7)
  publishForm.value.resource_name = ''
  showPublishModal.value = true
}

const handlePublish = async () => {
  if (!selectedSourceId.value || !currentTab.value?.result) return
  if (isSystemResourceGroup(publishForm.value.resource_group)) {
    showToast(`${SYSTEM_RESOURCE_GROUP} 为系统内置分组，不可用于普通资源`, 'warning')
    return
  }
  publishing.value = true
  
  const fields_config = currentTab.value.result.columns.map(col => ({ 
    name: col.name, 
    label: currentTab.value!.columnLabels[col.name] || col.name, 
    type: 'String'
  }))
  
  const allowed_filters = selectedFilters.value.map(v => ({ 
    name: v, 
    label: currentTab.value!.columnLabels[v] || v, 
    type: 'String'
  }))
  
  const source = dataSources.value.find(ds => ds.id === selectedSourceId.value)
  const payload = { 
    ...publishForm.value, 
    data_source: source?.source_name || 'default', 
    resource_mode: 'SQL', 
    custom_sql: currentTab.value.sql, 
    fields_config, 
    allowed_filters, 
    default_sort: fields_config[0]?.name || '', 
    status: 1 
  }

  try {
    await axios.post('/api/portal/lab/publish', payload)
    showToast('API 发布成功', 'success')
    showPublishModal.value = false
  } catch (e: any) {
    showToast('发布失败: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    publishing.value = false
  }
}

const mockJsonResponse = computed(() => {
  if (!currentTab.value?.result || currentTab.value.result.columns.length === 0) return null
  const sampleItem: Record<string, any> = {}
  currentTab.value.result.columns.forEach((col, idx) => {
    const val = (currentTab.value!.result?.rows && currentTab.value!.result.rows[0]) ? currentTab.value!.result.rows[0][idx] : "..."
    sampleItem[col.name] = val
  })
  return { code: 200, message: "success", data: { items: [sampleItem], total: 1, page: 1, size: 20 }, trace_id: "req_xxxxxx" }
})

onMounted(() => { 
  fetchDataSources(); loadHistory(); loadTabs(); checkVectorSupport()
  
  if (labMode.value === 'api' && !hasApiMode.value && hasAnalystMode.value) {
    labMode.value = 'analyst'
  } else if (labMode.value === 'analyst' && !hasAnalystMode.value && hasApiMode.value) {
    labMode.value = 'api'
  }
})
</script>

<template>
  <div ref="sqllabContainer" class="space-y-1.5 flex flex-col relative" 
    :class="[
      (noLabModeAccess || noAccessToAnyDataSource) ? 'h-[calc(100vh-64px)] overflow-hidden -m-8' : 'pb-20',
      isFullscreen ? 'fixed inset-0 z-[9999] bg-gray-50 p-6 overflow-auto h-screen' : ''
    ]">
    
    <!-- No Access State (Lab Modes) - z-5 to be under global header -->
    <div v-if="noLabModeAccess" class="absolute inset-0 z-[5] bg-gray-50/60 backdrop-blur-xl flex flex-col items-center justify-center p-6 animate-in fade-in duration-700">
      <div class="text-center max-w-md">
        <div class="w-20 h-20 bg-red-50/50 border border-red-100 rounded-2xl flex items-center justify-center mx-auto mb-6 text-red-500/80">
          <svg class="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
        </div>
        <h2 class="text-2xl font-black mb-3 text-gray-800 tracking-tight">暂无实验室模式权限</h2>
        <p class="text-gray-500 mb-8 leading-relaxed px-8 text-sm font-medium">您的账号尚未被授予访问权限。请联系管理员进行功能分配。</p>
        <button @click="fetchDataSources" class="px-8 py-3 bg-indigo-600/90 text-white rounded-xl font-bold shadow-lg shadow-indigo-200/50 hover:bg-indigo-700 transition-all active:scale-95">刷新权限状态</button>
      </div>
    </div>

    <!-- No Data Source State - z-5 to be under global header -->
    <div v-if="noAccessToAnyDataSource" class="absolute inset-0 z-[5] bg-gray-50/60 backdrop-blur-xl flex flex-col items-center justify-center p-6 animate-in fade-in duration-700">
      <div class="text-center max-w-md">
        <div class="w-20 h-20 bg-orange-50/50 border border-orange-100 rounded-2xl flex items-center justify-center mx-auto mb-6 text-orange-500/80">
          <CircleStackIcon class="w-10 h-10" />
        </div>
        <h2 class="text-2xl font-black mb-3 text-gray-800 tracking-tight">暂无数据源访问权限</h2>
        <p class="text-gray-500 mb-8 leading-relaxed px-8 text-sm font-medium">当前账号下未发现可用资产。请联系管理员在“数据源管理”中分配查询权限。</p>
        <button @click="fetchDataSources" class="px-8 py-3 bg-orange-600/90 text-white rounded-xl font-bold shadow-lg shadow-orange-200/50 hover:bg-orange-700 transition-all active:scale-95">重新加载资产</button>
      </div>
    </div>

    <!-- AI 任务状态条（非阻塞，延迟 600ms 显示） -->
    <teleport to="body">
      <transition enter-active-class="transition ease-out duration-300" enter-from-class="opacity-0 -translate-y-3" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-200" leave-from-class="opacity-100" leave-to-class="opacity-0 -translate-y-3">
        <div v-if="showAiStatusBar" class="fixed top-20 left-1/2 -translate-x-1/2 z-[100001] w-full max-w-2xl px-4 pointer-events-auto">
          <div class="bg-white/95 border border-indigo-100 rounded-2xl shadow-xl backdrop-blur-md px-4 py-3 flex items-start gap-3">
            <div class="relative shrink-0 mt-0.5">
              <div class="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
              <SparklesIcon class="w-3.5 h-3.5 text-indigo-500 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between gap-2">
                <p class="text-sm font-black text-indigo-900 truncate">{{ aiProcessingTitle }}</p>
                <span class="text-[10px] text-gray-400 font-mono shrink-0 tabular-nums">{{ aiElapsedSec }}s</span>
              </div>
              <p class="text-[11px] text-indigo-600/80 mt-0.5 truncate">{{ aiStatusSubtitle }}</p>
              <p
                v-if="latestAiLogMessage"
                class="text-[10px] text-gray-400 mt-1 truncate"
                :title="latestAiLogMessage"
              >{{ latestAiLogMessage }}</p>
            </div>
            <button
              @click="cancelAiTask"
              class="shrink-0 px-3 py-1.5 text-[10px] font-bold text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg border border-transparent hover:border-red-100 transition-all flex items-center gap-1"
            >
              <XMarkIcon class="w-3.5 h-3.5" />
              取消
            </button>
          </div>
        </div>
      </transition>
    </teleport>

    <!-- Mode Change Toast (Sleek Top Bar) -->
    <teleport to="body">
      <transition enter-active-class="transition ease-out duration-300" enter-from-class="opacity-0 -translate-y-10" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-200" leave-from-class="opacity-100" leave-to-class="opacity-0 -translate-y-10">
        <div v-if="showModeToast" class="fixed top-6 left-1/2 -translate-x-1/2 z-[100001] pointer-events-none">
          <div class="bg-white/90 border border-indigo-100 px-6 py-2.5 rounded-full shadow-xl backdrop-blur-md flex items-center gap-3">
            <div class="w-2 h-2 bg-indigo-500 rounded-full animate-ping"></div>
            <span class="text-sm font-black text-indigo-900 tracking-tight">{{ modeToastMsg }}</span>
          </div>
        </div>
      </transition>
    </teleport>

    <div class="flex-shrink-0 flex justify-between items-center gap-3" :class="{ 'blur-sm grayscale opacity-50': noAccessToAnyDataSource || noLabModeAccess }">
      <div class="flex items-center gap-2 min-w-0">
        <h1 class="text-base font-bold text-gray-900 flex items-center shrink-0">
          <BeakerIcon class="w-5 h-5 text-blue-600 mr-1.5" /> SQL 实验室
        </h1>
        <span
          v-if="labMode === 'api'"
          class="px-2 py-0.5 bg-blue-50 text-blue-600 text-[10px] font-semibold rounded border border-blue-100 shrink-0"
        >API 调试</span>
        <span
          v-else
          class="px-2 py-0.5 bg-orange-50 text-orange-600 text-[10px] font-semibold rounded border border-orange-100 shrink-0"
        >自助取数</span>
        <span class="text-[10px] text-gray-400 truncate hidden xl:inline">
          {{ labMode === 'api' ? '开发调试与发布 API' : '自助查询分析 · 支持 AI 自然语言' }}
        </span>
      </div>
      <div class="flex items-center gap-1.5 bg-white px-1 py-0.5 rounded-lg shadow-sm border border-gray-200 shrink-0">
        <div class="flex p-0.5 bg-gray-100 rounded-md">
          <button v-if="hasApiMode" @click="setLabMode('api')" :class="labMode === 'api' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500'" class="px-2.5 py-1 text-[11px] font-semibold rounded transition-all">🛠️ API 调试</button>
          <button v-if="hasAnalystMode" @click="setLabMode('analyst')" :class="labMode === 'analyst' ? 'bg-white text-orange-600 shadow-sm' : 'text-gray-500'" class="px-2.5 py-1 text-[11px] font-semibold rounded transition-all">📊 自助取数</button>
        </div>
        <div class="w-px h-5 bg-gray-200" />
        <Tooltip :text="isFullscreen ? '退出全屏' : '全屏模式'" position="bottom">
          <button @click="toggleFullscreen(sqllabContainer!)" class="p-1.5 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-md transition-all">
            <component :is="isFullscreen ? ArrowsPointingInIcon : ArrowsPointingOutIcon" class="w-4 h-4" />
          </button>
        </Tooltip>
      </div>
    </div>

    <div
      v-if="isAiEnabled && (hasPerm('element:lab:generate') || hasPerm('element:lab:analysis'))"
      class="relative transition-all"
      :class="[
        noAccessToAnyDataSource || noLabModeAccess ? 'blur-sm grayscale opacity-50 pointer-events-none' : '',
        isAiProcessing ? 'opacity-70' : ''
      ]"
    >
      <!-- 收起态：单行胶囊，节省垂直空间 -->
      <button
        v-if="aiBarCollapsed"
        type="button"
        class="w-full flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg shadow-sm hover:border-indigo-200 hover:bg-indigo-50/30 transition-all text-left"
        @click="expandAiBar"
      >
        <SparklesIcon class="w-4 h-4 text-indigo-500 shrink-0" />
        <span class="text-xs text-gray-500 truncate flex-1">
          {{ aiPrompt ? aiPrompt : 'AI 自然语言查表 · 点击展开' }}
        </span>
        <span
          v-if="autoContext"
          class="text-[9px] px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-600 font-bold shrink-0"
        >智能关联</span>
        <ChevronDownIcon class="w-3.5 h-3.5 text-gray-400 shrink-0" />
      </button>

      <!-- 展开态：紧凑单行工具栏 -->
      <div
        v-else
        class="bg-white px-2 py-1.5 rounded-xl border border-gray-200 shadow-sm flex items-center gap-2 relative"
        :class="isAiProcessing ? 'pointer-events-none' : ''"
      >
        <SparklesIcon class="w-4 h-4 text-purple-600 shrink-0" />

        <Tooltip
          :text="!isVectorSupported ? 'Redis 不支持向量搜索' : `智能关联元数据 · ${metaStats.dataset_count} 个可用数据集`"
          position="bottom"
        >
          <button
            type="button"
            @click="toggleAutoContext"
            class="shrink-0 flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-bold border transition-all"
            :class="[
              autoContext ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-gray-100 text-gray-500 border-gray-200 hover:bg-gray-200',
              !isVectorSupported ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'
            ]"
          >
            <CubeIcon class="w-3 h-3" />
            智能关联
          </button>
        </Tooltip>

        <div class="flex-1 relative flex items-center min-w-0 group/ai">
          <input
            v-if="hasPerm('element:lab:generate')"
            ref="aiInputRef"
            v-model="aiPrompt"
            :disabled="isAiProcessing"
            @keyup.enter="submitAiTask"
            :placeholder="isAiProcessing ? 'AI 任务进行中...' : aiPlaceholder"
            class="w-full py-1.5 pl-3 pr-16 bg-gray-50 border border-gray-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all placeholder:text-gray-400 disabled:cursor-not-allowed disabled:opacity-60"
          />

          <div class="absolute right-1.5 flex items-center gap-0.5">
            <Tooltip v-if="aiPrompt" text="清空输入" position="top">
              <button @click="clearAiPrompt" class="text-gray-400 hover:text-red-500 transition-colors p-1">
                <XMarkIcon class="w-3.5 h-3.5" />
              </button>
            </Tooltip>
            <Tooltip text="试试这些提问示例" position="top" align="end">
              <button
                v-if="hasPerm('element:lab:generate')"
                @click="showAiExamples = !showAiExamples"
                class="text-gray-400 hover:text-indigo-600 transition-colors p-1"
              >
                <QuestionMarkCircleIcon class="w-4 h-4" />
              </button>
            </Tooltip>
          </div>

          <div v-if="showAiExamples" @click="showAiExamples = false" class="fixed inset-0 z-[99]"></div>
          <div
            v-if="showAiExamples"
            class="absolute top-full left-0 right-0 mt-1.5 z-[100] bg-white border border-gray-200 rounded-xl shadow-2xl overflow-hidden"
          >
            <div class="px-3 py-2 bg-gray-50 border-b flex justify-between items-center">
              <span class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">提问示例</span>
              <button @click="showAiExamples = false" class="text-gray-400 hover:text-gray-600"><XMarkIcon class="w-3.5 h-3.5" /></button>
            </div>
            <div class="max-h-48 overflow-y-auto">
              <div
                v-for="(example, eIdx) in aiExamples"
                :key="eIdx"
                @click="selectAiExample(example)"
                class="px-3 py-2 text-xs text-gray-600 hover:bg-indigo-50 hover:text-indigo-700 cursor-pointer border-b last:border-none"
              >{{ example }}</div>
            </div>
          </div>
        </div>

        <Tooltip v-if="labMode !== 'api' && hasPerm('element:lab:generate')" text="智能推荐 12 个查询场景" position="top" align="end">
          <button
            :disabled="isAiProcessing"
            @click="openSuggestionModal"
            class="shrink-0 p-1.5 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <SparklesIcon class="w-4 h-4" />
          </button>
        </Tooltip>

        <Tooltip text="收起 AI 栏" position="top" align="end">
          <button
            type="button"
            @click="aiBarCollapsed = true"
            class="shrink-0 p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-all"
          >
            <ChevronUpIcon class="w-4 h-4" />
          </button>
        </Tooltip>
      </div>
    </div>

    <div class="flex flex-col flex-1 min-h-0 space-y-4" :class="{ 'blur-sm grayscale opacity-50 pointer-events-none': noAccessToAnyDataSource || noLabModeAccess }">
      <div class="flex flex-row overflow-hidden" :style="{ height: isFullscreen ? 'calc(100vh - 350px)' : `${editorHeight}px` }">
        <SchemaSidebar 
          v-show="!sidebarCollapsed" :style="{ width: `${sidebarWidth}px` }" class="flex-shrink-0"
          :tables="availableTables" :loading="loadingTables" :collapsed="sidebarCollapsed" :columns-cache="columnsCache" :flash-title="flashTableTitle"
          v-model="selectedTables" v-model:auto-context="autoContext" :ai-logs="aiLogs"
          :data-source-info="currentDataSourceInfo" :is-admin="isAdmin"
          :table-profiles-map="tableProfilesMap" :has-profiled="hasProfiled"
          :source-id="selectedSourceId"
          @refresh="fetchAvailableTables" @table-click="openTableDetail" @fetch-columns="fetchColumns" @column-dblclick="handleColumnInsert"
          @fetch-profile-detail="fetchTableProfileDetail"
          @table-profile-generate="handleTableProfileGenerate"
          @table-ai="openTableAiSuggestion" :show-ai="isAiEnabled && hasPerm('element:lab:generate')"
          @clear-logs="clearAiLogs"
        />
        <ResizeHandle v-if="!sidebarCollapsed" direction="horizontal" @resize="handleSidebarResize" />
        <div class="flex-1 flex flex-col min-w-0">
          <SqlEditor 
            v-if="tabs.length > 0" ref="sqlEditorRef" :tabs="tabs" v-model:activeTabIndex="activeTabIndex" v-model:selectedSourceId="selectedSourceId"
            v-model:preview-limit="previewLimit"
            :data-sources="dataSources" :history="queryHistory" :is-ai-enabled="isAiEnabled" :executing="currentTab?.executing || false"
            :ai-loading="aiLoading" :sidebar-collapsed="sidebarCollapsed" :has-perm="hasPerm" :available-tables="availableTables" :columns-cache="columnsCache"
            class="h-full" :lab-mode="labMode" :recalled-context="currentTab?.recalledContext || []"
            @create-tab="createTab" @close-tab="closeTab" @close-all-tabs="closeAllTabs" @close-other-tabs="closeOtherTabs" @update-tab-name="handleTabRename" @run-query="runQuery" @run-ai-check="runAiAction" @open-publish="openPublishModal" @restore-history="restoreHistory" @delete-history="deleteHistory" @toggle-sidebar="sidebarCollapsed = !sidebarCollapsed" @run-empty-test="runEmptyParamTest"
          />
        </div>
      </div>

      <div class="flex-1 min-h-[300px] flex flex-col">
        <ResizeHandle direction="vertical" @resize="handleEditorResize" />
        <ResultPanel 
          v-if="currentTab" ref="resultPanelRef" v-model:activeSubTab="currentTab.activeSubTab"
          :result="currentTab.result" :error="currentTab.error" :executing="currentTab.executing" :ai-loading="aiLoading"
          :ai-content="currentTab.aiContent" :optimized-sql="currentTab.optimizedSql" :lab-mode="labMode" :has-perm="hasPerm"
          :is-ai-enabled="isAiEnabled" :sql="currentTab.sql" :recalled-context="currentTab.recalledContext"
          :preview-limit="previewLimit"
          class="flex-1"
          @clear-result="handleClearResult" @apply-ai-fix="applyAiFix" @open-analysis="openAiAnalysis" @export-excel="exportToExcel"
          @ai-fix-error="handleAiFixError"
          @copy-success="showToast('Markdown 已复制到剪贴板', 'success')"
        />
      </div>
    </div>

    <AnalysisChat :is-open="showAnalysisChat" :initial-query="currentTab?.sql" :data="currentTab?.result?.rows" :columns="currentTab?.result?.columns" @close="showAnalysisChat = false" />
    
    <!-- AI Meta Error Modal -->
    <div v-if="showAiErrorModal" class="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm" @click.self="showAiErrorModal = false">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden transform transition-all animate-in zoom-in duration-200">
        <div class="p-6 text-center">
          <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-amber-100 mb-4">
            <ExclamationTriangleIcon class="h-6 w-6 text-amber-600" />
          </div>
          <h3 class="text-lg leading-6 font-bold text-gray-900 mb-2">生成受阻</h3>
          <p class="text-sm text-gray-500 mb-6 leading-relaxed px-2">
            {{ aiErrorMessage }}
          </p>
          <div class="flex flex-col gap-2">
            <button @click="showAiErrorModal = false" class="w-full py-2.5 bg-indigo-600 text-white font-bold rounded-lg hover:bg-indigo-700 shadow-lg transition-all text-sm">我知道了</button>
            <router-link to="/dashboard/metadata" class="w-full py-2.5 bg-gray-100 text-gray-700 font-bold rounded-lg hover:bg-gray-200 transition-all text-sm text-center">前往元数据中心</router-link>
          </div>
        </div>
      </div>
    </div>

    <!-- Inline Publish Modal -->
    <div v-if="showPublishModal" class="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in duration-200">
        <div class="p-6 border-b bg-gray-50 flex justify-between items-center text-gray-900">
          <div class="flex items-center gap-3">
            <h3 class="text-lg font-bold">发布为 API</h3>
            <span v-if="selectedFilters.length" class="text-[10px] bg-purple-100 text-purple-600 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">自动识别参数</span>
          </div>
          <button @click="showPublishModal = false" class="text-gray-400 hover:text-gray-600 transition-colors"><XMarkIcon class="w-6 h-6" /></button>
        </div>
        <div class="p-6 space-y-4 max-h-[70vh] overflow-y-auto custom-scrollbar">
          <div class="space-y-1">
            <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">资源标识 (Key)</label>
            <input v-model="publishForm.resource_key" placeholder="例如: user.list" class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none font-mono transition-all" />
          </div>
          <div class="space-y-1">
            <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">接口名称</label>
            <input v-model="publishForm.resource_name" placeholder="输入易于理解的名称..." class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all" />
          </div>
          <div class="space-y-1 relative">
            <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">接口分组</label>
            <div class="relative">
              <input 
                v-model="publishForm.resource_group" 
                @focus="showGroupDropdown = true"
                @blur="hideGroupDropdown"
                placeholder="输入或选择分组..." 
                class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all" 
              />
              <div v-if="showGroupDropdown && selectableGroups.length > 0" class="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-xl max-h-48 overflow-y-auto">
                <div 
                  v-for="group in selectableGroups" :key="group"
                  @mousedown="publishForm.resource_group = group; showGroupDropdown = false"
                  class="px-4 py-2 text-sm text-gray-700 hover:bg-blue-50 cursor-pointer transition-colors"
                >
                  {{ group }}
                </div>
              </div>
            </div>
          </div>

          <div class="space-y-1">
            <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">缓存时间 (秒)</label>
            <input v-model.number="publishForm.cache_ttl" type="number" placeholder="例如: 300" class="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none font-mono transition-all" />
          </div>

          <!-- JSON Mock Preview -->
          <div v-if="mockJsonResponse" class="border rounded-xl overflow-hidden mt-4">
            <button @click="showMockPreview = !showMockPreview" class="w-full px-4 py-2 bg-gray-50 flex items-center justify-between hover:bg-gray-100 transition-colors">
              <span class="text-[10px] font-bold text-gray-500 uppercase">响应预览 (JSON)</span>
              <ChevronRightIcon class="w-4 h-4 text-gray-400 transition-transform" :class="showMockPreview ? 'rotate-90' : ''" />
            </button>
            <div v-if="showMockPreview" class="bg-gray-900 p-4">
              <pre class="text-[10px] text-green-400 font-mono overflow-auto max-h-48 custom-scrollbar">{{ JSON.stringify(mockJsonResponse, null, 2) }}</pre>
            </div>
          </div>

          <!-- Filter Confirmation -->
          <div v-if="selectedFilters.length > 0" class="space-y-2 mt-4">
            <label class="text-xs font-bold text-gray-500 uppercase tracking-wider">确认公开的过滤参数</label>
            <div class="bg-gray-50 rounded-xl p-3 border border-gray-100 space-y-2">
              <label v-for="v in selectedFilters" :key="v" class="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" :value="v" checked disabled class="h-4 w-4 text-blue-600 rounded border-gray-300" />
                <span class="text-xs text-gray-600 font-mono">{{ v }}</span>
              </label>
            </div>
          </div>
        </div>
        <div class="p-6 bg-gray-50 border-t flex gap-3">
          <button @click="showPublishModal = false" class="flex-1 py-2.5 bg-white border border-gray-200 rounded-xl font-bold text-gray-600 hover:bg-gray-100 transition-colors">取消</button>
          <button @click="handlePublish" :disabled="publishing || !publishForm.resource_name || !publishForm.resource_key" class="flex-1 py-2.5 bg-blue-600 text-white rounded-xl font-bold hover:bg-blue-700 disabled:opacity-50 transition-all shadow-md">
            {{ publishing ? '发布中...' : '确认发布' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showTableSelector" class="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
      <div class="bg-white rounded-2xl p-6 w-full max-w-lg relative shadow-2xl">
        <button @click="showTableSelector = false" class="absolute top-4 right-4 text-gray-400 hover:text-gray-600"><XMarkIcon class="w-6 h-6" /></button>
        <h3 class="font-bold mb-2 flex items-center gap-2"><CircleStackIcon class="w-5 h-5 text-indigo-600" /> 选择 SQL 上下文表</h3>
        <p class="text-[10px] text-gray-400 mb-4 uppercase tracking-wider font-bold">勾选的表将作为 AI 生成 SQL 的元数据参考</p>
        
        <div class="flex items-center gap-3 mb-3 px-2 py-2 bg-gray-50 rounded-lg border border-gray-100">
          <input 
            type="checkbox" 
            :checked="selectedTables.length === availableTables.length && availableTables.length > 0"
            :indeterminate="selectedTables.length > 0 && selectedTables.length < availableTables.length"
            @change="(e) => {
              const checked = (e.target as HTMLInputElement).checked;
              selectedTables = checked ? availableTables.map(t => typeof t === 'string' ? t : t.name) : [];
            }"

            id="modal-select-all"
            class="h-4 w-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500 cursor-pointer" 
          />
          <label for="modal-select-all" class="text-xs font-black text-indigo-900 cursor-pointer">全选所有表 ({{ availableTables.length }})</label>
        </div>

        <div class="max-h-60 overflow-y-auto space-y-2 mb-6 border rounded-xl p-2 bg-gray-50 custom-scrollbar">
          <label v-for="t in availableTables" :key="typeof t === 'string' ? t : t.name" class="flex items-center gap-3 p-2 hover:bg-white hover:shadow-sm rounded-lg transition-all cursor-pointer group">
            <input type="checkbox" :value="typeof t === 'string' ? t : t.name" v-model="selectedTables" class="h-4 w-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500" />
            <div class="flex items-center justify-between flex-1">
              <span class="text-sm text-gray-700 group-hover:text-indigo-600 font-medium">{{ typeof t === 'string' ? t : t.name }}</span>
              <span v-if="typeof t !== 'string'" :class="t.type === 'VIEW' ? 'bg-amber-100 text-amber-600' : 'bg-blue-100 text-blue-600'" class="text-[9px] px-1.5 py-0.5 rounded uppercase font-black">{{ t.type }}</span>
            </div>
          </label>
        </div>

        <button @click="showTableSelector = false" class="w-full py-3 bg-indigo-600 text-white font-bold rounded-xl shadow-lg hover:bg-indigo-700 transition-all">确认选择</button>
      </div>
    </div>

    <div v-if="showExportConfirm" class="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in duration-200">
        <div class="p-6 text-center">
          <div class="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4"><ArrowsPointingOutIcon class="w-6 h-6 text-green-600" /></div>
          <h3 class="text-lg font-bold mb-2">确认导出结果?</h3>
          <div class="bg-gray-50 rounded-xl p-4 mb-6 text-sm space-y-2">
            <div class="flex justify-between"><span class="text-gray-500">预计行数</span><span class="font-mono font-bold">{{ currentTab?.result?.rows.length }} 行</span></div>
            <div class="flex justify-between"><span class="text-gray-500">导出格式</span><span class="font-bold text-green-600">Excel (.xlsx)</span></div>
          </div>
          <div class="flex gap-3">
            <button @click="showExportConfirm = false" class="flex-1 py-2.5 bg-gray-100 text-gray-700 font-bold rounded-lg hover:bg-gray-200">取消</button>
            <button @click="executeExport" class="flex-1 py-2.5 bg-green-600 text-white font-bold rounded-lg hover:bg-green-700 shadow-md">开始导出</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showSuggestionModal" class="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm" @click.self="showSuggestionModal = false">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-5xl flex flex-col max-h-[88vh] overflow-hidden animate-in zoom-in duration-300 border border-gray-100">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between gap-4 shrink-0">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center shrink-0">
              <SparklesIcon class="w-5 h-5 text-indigo-600" />
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <h3 class="text-lg font-bold text-gray-900">AI 智能查询推荐</h3>
                <span class="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 text-[11px] font-semibold">
                  {{ suggestions.length }} 个场景
                </span>
              </div>
              <p class="text-xs text-gray-500 mt-0.5 truncate">{{ suggestionModalSubtitle }}</p>
            </div>
          </div>
          <button type="button" @click="showSuggestionModal = false" class="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors shrink-0">
            <XMarkIcon class="w-5 h-5" />
          </button>
        </div>

        <!-- Master-Detail Body -->
        <div class="flex-1 min-h-0 flex flex-col md:flex-row">
          <!-- Left: scenario list -->
          <div class="md:w-[280px] lg:w-[320px] shrink-0 border-b md:border-b-0 md:border-r border-gray-100 bg-gray-50/80 flex flex-col min-h-0">
            <div class="px-4 py-2.5 text-[10px] font-bold text-gray-400 uppercase tracking-wider border-b border-gray-100">
              推荐场景
            </div>
            <div class="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
              <button
                v-for="(item, idx) in suggestions"
                :key="idx"
                type="button"
                class="w-full text-left px-3 py-2.5 rounded-lg border transition-all"
                :class="selectedSuggestionIdx === idx
                  ? 'bg-white border-indigo-200 shadow-sm ring-1 ring-indigo-100'
                  : 'border-transparent hover:bg-white hover:border-gray-200'"
                @click="selectedSuggestionIdx = idx"
              >
                <div class="flex items-start gap-2">
                  <span
                    class="shrink-0 w-5 h-5 rounded-md text-[10px] font-bold flex items-center justify-center mt-0.5"
                    :class="selectedSuggestionIdx === idx ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-500'"
                  >{{ idx + 1 }}</span>
                  <span class="text-xs font-semibold leading-snug line-clamp-2" :class="selectedSuggestionIdx === idx ? 'text-indigo-900' : 'text-gray-700'">
                    {{ item.title }}
                  </span>
                </div>
              </button>
            </div>
          </div>

          <!-- Right: detail panel -->
          <div v-if="selectedSuggestion" class="flex-1 flex flex-col min-w-0 min-h-0 bg-white">
            <div class="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-5">
              <div>
                <h4 class="text-base font-bold text-gray-900 leading-snug">{{ selectedSuggestion.title }}</h4>
                <p class="mt-2 text-sm text-gray-600 leading-relaxed">{{ selectedSuggestion.description }}</p>
              </div>

              <div>
                <div class="flex items-center justify-between mb-2">
                  <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">SQL 预览</span>
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 text-[11px] text-gray-500 hover:text-indigo-600 transition-colors"
                    @click="copySuggestionSql(selectedSuggestion.sql)"
                  >
                    <ClipboardDocumentIcon class="w-3.5 h-3.5" />
                    复制 SQL
                  </button>
                </div>
                <div class="rounded-xl border border-gray-800 bg-[#1e1e1e] overflow-hidden">
                  <pre class="p-4 text-[12px] leading-relaxed text-emerald-400 font-mono overflow-x-auto custom-scrollbar whitespace-pre-wrap max-h-[min(42vh,360px)]"><code>{{ selectedSuggestion.sql }}</code></pre>
                </div>
              </div>
            </div>

            <!-- Footer actions -->
            <div class="shrink-0 px-6 py-4 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between gap-3">
              <p class="text-[11px] text-gray-400 hidden sm:block">采用后将新建查询标签页并填入 SQL</p>
              <div class="flex items-center gap-2 ml-auto">
                <button
                  type="button"
                  class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
                  @click="showSuggestionModal = false"
                >
                  关闭
                </button>
                <button
                  type="button"
                  class="inline-flex items-center gap-1.5 px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors"
                  @click="adoptSuggestion(selectedSuggestion.sql)"
                >
                  <PlayIcon class="w-4 h-4" />
                  采用此查询
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Table Detail Modal (Structure & Preview) -->
    <div v-if="showTableDetailModal" class="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
      <div class="bg-white rounded-3xl shadow-2xl w-full max-w-5xl flex flex-col max-h-[85vh] overflow-hidden animate-in zoom-in duration-300">
        <div class="p-6 border-b bg-gray-50 flex justify-between items-center text-gray-900">
          <div class="flex items-center gap-3">
            <div class="p-2 bg-indigo-100 rounded-xl text-indigo-600"><TableCellsIcon class="w-6 h-6" /></div>
            <div>
              <h3 class="text-xl font-bold">{{ detailTable }}</h3>
              <p class="text-[10px] text-gray-400 uppercase font-black tracking-widest">数据表详情与预览</p>
            </div>
          </div>
          <button @click="showTableDetailModal = false" class="text-gray-400 hover:text-gray-600 transition-all"><XMarkIcon class="w-7 h-7" /></button>
        </div>

        <!-- Tab Header -->
        <div class="px-6 bg-white border-b flex gap-8">
          <button 
            @click="detailActiveTab = 'structure'"
            :class="detailActiveTab === 'structure' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
            class="py-4 border-b-2 font-bold text-sm transition-all"
          >
            表结构 ({{ detailColumns.length }})
          </button>
          <button 
            @click="fetchTablePreview"
            :class="detailActiveTab === 'preview' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
            class="py-4 border-b-2 font-bold text-sm transition-all flex items-center gap-2"
          >
            数据预览
            <div v-if="detailPreviewLoading" class="w-3 h-3 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
          </button>
        </div>

        <div class="flex-1 overflow-auto p-6 bg-gray-50/30 custom-scrollbar">
          <!-- Structure View -->
          <div v-if="detailActiveTab === 'structure'">
            <div v-if="detailLoading" class="flex flex-col items-center justify-center py-20 space-y-4">
              <div class="w-10 h-10 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin"></div>
              <p class="text-sm text-gray-400 italic">正在读取表结构...</p>
            </div>
            <table v-else class="min-w-full divide-y divide-gray-200 bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-6 py-3 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest">字段名</th>
                  <th class="px-6 py-3 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest">物理类型</th>
                  <th class="px-6 py-3 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest">描述/注释</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="col in detailColumns" :key="col.name" class="hover:bg-indigo-50/30 transition-colors">
                  <td class="px-6 py-4 text-sm font-bold text-gray-900 font-mono">{{ col.name }}</td>
                  <td class="px-6 py-4 text-xs text-indigo-600 font-medium">
                    <span class="px-2 py-0.5 bg-indigo-50 rounded-full border border-indigo-100">{{ col.type }}</span>
                  </td>
                  <td class="px-6 py-4 text-sm text-gray-500">{{ col.comment || '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Preview View -->
          <div v-else class="h-full">
            <div v-if="detailPreviewLoading" class="flex flex-col items-center justify-center py-20 space-y-4">
              <div class="w-10 h-10 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin"></div>
              <p class="text-sm text-gray-400 italic">正在查询前 50 条数据...</p>
            </div>
            <div v-else-if="detailPreviewError" class="p-6 bg-red-50 border border-red-100 rounded-2xl text-red-600 text-sm flex items-center gap-3">
              <svg class="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              {{ detailPreviewError }}
            </div>
            <div v-else-if="detailPreviewData" class="space-y-4">
              <div class="flex justify-between items-center mb-2">
                <span class="text-xs font-bold text-gray-400">查询结果预览 (Limit 50)</span>
                <span class="text-[10px] bg-green-50 text-green-600 px-2 py-0.5 rounded-full font-bold">SUCCESS</span>
              </div>
              <div class="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
                <div class="overflow-x-auto custom-scrollbar">
                  <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                      <tr>
                        <th v-for="col in detailPreviewData.columns" :key="col.name" class="px-4 py-3 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest whitespace-nowrap">
                          {{ col.name }}
                        </th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100">
                      <tr v-for="(row, rIdx) in detailPreviewData.rows" :key="rIdx" class="hover:bg-gray-50 transition-colors">
                        <td v-for="(cell, cIdx) in row" :key="cIdx" class="px-4 py-2.5 text-xs text-gray-600 truncate max-w-[200px]" :title="String(cell)">
                          {{ cell === null ? 'NULL' : cell }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-if="detailPreviewData.rows.length === 0" class="py-20 text-center text-gray-400 italic text-sm">
                  表中暂无数据
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="p-6 border-t bg-gray-50 flex justify-end">
          <button @click="showTableDetailModal = false" class="px-8 py-2.5 bg-indigo-600 text-white font-bold rounded-xl shadow-lg hover:bg-indigo-700 transition-all">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>
