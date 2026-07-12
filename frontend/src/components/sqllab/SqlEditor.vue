<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { 
  PlayIcon, ClockIcon, CommandLineIcon, SparklesIcon, CircleStackIcon, TrashIcon, XMarkIcon,
  ListBulletIcon, PencilSquareIcon, CalendarDaysIcon, QuestionMarkCircleIcon,
  BeakerIcon, TableCellsIcon, StopIcon, EyeIcon, BoltIcon, BookmarkIcon, CodeBracketIcon, AdjustmentsHorizontalIcon
} from '@heroicons/vue/24/outline'
import { Codemirror } from 'vue-codemirror'
import { sql as sqlLang, MySQL, PostgreSQL, MariaSQL } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'
import { autocompletion } from '@codemirror/autocomplete'
import { keymap, EditorView } from '@codemirror/view'
import { indentWithTab } from '@codemirror/commands'
import { formatLabSqlSafe } from '../../utils/formatLabSql'
import { useToast } from '../../composables/useToast'
import Tooltip from '../common/Tooltip.vue'
import LabShortcutsModal from './LabShortcutsModal.vue'
import LabSnippetsPanel from './LabSnippetsPanel.vue'
import LabParamPresetsPanel from './LabParamPresetsPanel.vue'

interface HistoryItem {
  sql: string
  params: any
  timestamp: number
  execution_time_ms?: number
  row_count?: number
  success?: boolean
}

const props = defineProps<{
  tabs: QueryTab[]
  activeTabIndex: number
  dataSources: DataSource[]
  selectedSourceId: number | null
  history: HistoryItem[]
  isAiEnabled: boolean
  executing: boolean
  aiLoading: boolean
  sidebarCollapsed: boolean
  hasPerm: (code: string) => boolean
  availableTables: string[]
  columnsCache: Record<string, {name: string, type: string}[]>
  noAccess?: boolean
  labMode: 'api' | 'analyst'
  recalledContext: any[]
  previewLimit: number
  unmask?: boolean
  isAdmin?: boolean
  sensitiveWarnings?: { level: string; message: string }[]
}>()

const emit = defineEmits<{
  (e: 'update:activeTabIndex', idx: number): void
  (e: 'update:selectedSourceId', id: number): void
  (e: 'update:previewLimit', value: number): void
  (e: 'create-tab'): void
  (e: 'close-tab', idx: number): void
  (e: 'close-all-tabs'): void
  (e: 'close-other-tabs', idx: number): void
  (e: 'update-tab-name', idx: number, name: string): void
  (e: 'run-query', sql?: string): void
  (e: 'run-ai-check'): void
  (e: 'open-publish'): void
  (e: 'restore-history', item: HistoryItem): void
  (e: 'delete-history', index: number): void
  (e: 'clear-history'): void
  (e: 'toggle-sidebar'): void
  (e: 'run-empty-test'): void
  (e: 'format-sql'): void
  (e: 'cancel-query'): void
  (e: 'run-explain'): void
  (e: 'update:unmask', value: boolean): void
  (e: 'open-saved-queries'): void
  (e: 'ai-edit-sql', instruction: string): void
  (e: 'save-history-as-template', item: HistoryItem): void
}>()

// Types
interface DataSource { id: number; source_name: string; source_type: string }
interface QueryTab { id: string; name: string; sql: string; testParams: Record<string, any>; result: any; error: any; executing: boolean; activeSubTab: 'result' | 'ai' | 'explain' | 'debug', emptyTestPassed: boolean }

const { showToast } = useToast()

// Context Menu State
const contextMenu = ref({
  show: false,
  x: 0,
  y: 0,
  index: -1
})

const openContextMenu = (event: MouseEvent, index: number) => {
  contextMenu.value = {
    show: true,
    x: event.clientX,
    y: event.clientY,
    index
  }
}

const closeContextMenu = () => {
  contextMenu.value.show = false
}

// Global click to close menu
watch(() => contextMenu.value.show, (show) => {
  if (show) {
    window.addEventListener('click', closeContextMenu, { once: true })
  }
})

const handleCloseTab = (idx: number) => {
  emit('close-tab', idx)
  closeContextMenu()
}

const handleCloseAll = () => {
  emit('close-all-tabs')
  closeContextMenu()
}

const handleCloseOthers = () => {
  if (contextMenu.value.index !== -1) {
    emit('close-other-tabs', contextMenu.value.index)
  }
  closeContextMenu()
}

const sqlSchema = computed(() => {
  const schema: Record<string, string[]> = {}
  props.availableTables.forEach(t => {
     schema[t] = props.columnsCache[t]?.map(c => c.name) || []
  })
  return schema
})

const currentDialect = computed(() => {
  const source = props.dataSources.find(ds => ds.id === props.selectedSourceId)
  if (!source) return MySQL
  const type = source.source_type.toLowerCase()
  if (type === 'postgresql') return PostgreSQL
  if (type === 'clickhouse') return MariaSQL
  if (type === 'oracle' || type === 'sqlserver') return MariaSQL
  return MySQL
})

const extensions = computed(() => [
  sqlLang({ 
    schema: sqlSchema.value,
    dialect: currentDialect.value,
    upperCaseKeywords: true
  }), 
  oneDark,
  EditorView.lineWrapping,
  autocompletion({
    activateOnTyping: true,
    icons: true,
    defaultKeymap: true
  }),
  keymap.of([
    indentWithTab,
    {
      key: 'Ctrl-Enter',
      run: () => { handleRunQuery(); return true },
      preventDefault: true
    },
    {
      key: 'Cmd-Enter',
      run: () => { handleRunQuery(); return true },
      preventDefault: true
    }
  ])
])

const showAiEditModal = ref(false)
const aiEditInstruction = ref('')
const showHistory = ref(false)
const historyDropdownRef = ref<HTMLElement | null>(null)
const showShortcuts = ref(false)
const showSnippets = ref(false)
const showParamPresets = ref(false)
const showRecallPanel = ref(false)
const showJinjaHelpModal = ref(false)
const showParamsPanel = ref(props.labMode === 'api')
const editorView = ref<any>(null)
const editingTabId = ref<string | null>(null)
const editName = ref('')

const currentTab = computed(() => props.tabs[props.activeTabIndex])

const sql = computed({
  get: () => currentTab.value?.sql || '',
  set: (v) => { if (currentTab.value) currentTab.value.sql = v }
})

watch(() => props.labMode, (newMode) => {
  if (newMode === 'api') {
    showParamsPanel.value = true
  } else {
    showParamsPanel.value = false
  }
}, { immediate: true })

const testParams = computed({
  get: () => currentTab.value?.testParams || {},
  set: (v) => { if (currentTab.value) currentTab.value.testParams = v }
})

// 记录用户手动强制设为文本模式的参数名
const paramModeOverrides = ref<Record<string, boolean>>({})

const toggleParamMode = (v: string) => {
  paramModeOverrides.value[v] = !paramModeOverrides.value[v]
}

// 自动格式化日期字符串，将 T 转换为 空格，方便 SQL 直接使用
watch(testParams, (newParams) => {
  Object.keys(newParams).forEach(key => {
    // 只有在非手动模式下才自动格式化日期
    if (paramModeOverrides.value[key]) return

    const val = newParams[key]
    if (typeof val === 'string' && val.includes('T') && (key.toLowerCase().includes('time'))) {
      newParams[key] = val.replace('T', ' ')
    }
  })
}, { deep: true })

const sqlVariables = computed(() => {
  const vars = new Set<string>()
  
  // Pre-process: Remove SQL comments to avoid extracting variables from them
  // 1. Remove single-line comments (-- ...)
  // 2. Remove multi-line comments (/* ... */)
  // 3. Remove Jinja comments ({# ... #})
  const cleanSql = sql.value
    .replace(/--.*$/gm, '') 
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\{#[\s\S]*?#\}/g, '')

  // 1. Match {{ variable }}
  const interpolationMatches = cleanSql.match(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g)
  if (interpolationMatches) {
    interpolationMatches.forEach(m => vars.add(m.replace(/\{\{\s*|\s*\}\}/g, '').trim()))
  }

  // 2. Match {% if variable %} or {% if variable is defined %}
  // Extract the first identifier after 'if' or 'if not'
  const ifMatches = cleanSql.match(/\{%\s*if\s+(?:not\s+)?([a-zA-Z0-9_]+)/g)
  if (ifMatches) {
    ifMatches.forEach(m => {
      const match = m.match(/if\s+(?:not\s+)?([a-zA-Z0-9_]+)/)
      if (match && match[1]) vars.add(match[1])
    })
  }

  return [...vars]
})

watch(sqlVariables, (newVars) => {
  newVars.forEach(v => { if (!(v in testParams.value)) testParams.value[v] = '' })
  // Only auto-show panel if in API mode
  if (newVars.length > 0 && props.labMode === 'api') showParamsPanel.value = true
}, { immediate: true })

const handleEditorReady = (payload: any) => { editorView.value = payload.view }

const insertAtCursor = (text: string) => {
  const view = editorView.value
  if (!view) {
    sql.value = (sql.value ? sql.value + '\n' : '') + text
    return
  }
  const pos = view.state.selection.main.head
  view.dispatch({
    changes: { from: pos, insert: text },
    selection: { anchor: pos + text.length },
  })
  view.focus()
}

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === '?' && !e.ctrlKey && !e.metaKey && !(e.target as HTMLElement)?.matches('input, textarea')) {
    showShortcuts.value = true
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

const formatHistoryTime = (ts: number) => {
  const d = new Date(ts)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

const formatSql = () => {
  if (!sql.value.trim()) return
  try {
    const source = props.dataSources.find(ds => ds.id === props.selectedSourceId)
    sql.value = formatLabSqlSafe(sql.value, source?.source_type || 'mysql')
    showToast('SQL 已美化', 'success')
  } catch (e: any) {
    console.error('SQL Format Error:', e)
    showToast(`格式化失败: ${e.message || '未知语法错误'}`, 'warning')
  }
}

const clearSql = () => {
  sql.value = ''
  showToast('编辑器已清空', 'info')
}

const handleRestoreHistory = (item: HistoryItem) => { emit('restore-history', item); showHistory.value = false }

const onHistoryOutsideClick = (e: MouseEvent) => {
  if (!showHistory.value) return
  const el = historyDropdownRef.value
  if (el && !el.contains(e.target as Node)) showHistory.value = false
}

const onHistoryEscape = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && showHistory.value) showHistory.value = false
}

watch(showHistory, (open) => {
  if (open) {
    setTimeout(() => {
      document.addEventListener('click', onHistoryOutsideClick)
      document.addEventListener('keydown', onHistoryEscape)
    }, 0)
  } else {
    document.removeEventListener('click', onHistoryOutsideClick)
    document.removeEventListener('keydown', onHistoryEscape)
  }
})

onUnmounted(() => {
  document.removeEventListener('click', onHistoryOutsideClick)
  document.removeEventListener('keydown', onHistoryEscape)
})
const handleDeleteHistory = (idx: number, event: Event) => {
  event.stopPropagation()
  emit('delete-history', idx)
}
const handleClearHistory = (event: Event) => {
  event.stopPropagation()
  if (!props.history.length) return
  if (!window.confirm(`确定清空全部 ${props.history.length} 条查询历史？此操作不可恢复。`)) return
  emit('clear-history')
  showHistory.value = false
}
const startRename = (tab: QueryTab) => {
  editingTabId.value = tab.id; editName.value = tab.name;
  nextTick(() => { document.getElementById(`tab-input-${tab.id}`)?.focus() })
}
const finishRename = (idx: number) => {
  if (editingTabId.value && editName.value.trim()) emit('update-tab-name', idx, editName.value.trim())
  editingTabId.value = null; editName.value = ''
}

const jinjaExample1 = '{{ user_id }}'
const jinjaExample2 = '{% if ... %}'

const isSemicolonOutsideString = (doc: string, index: number): boolean => {
  if (doc[index] !== ';') return false
  let inSingle = false
  let inDouble = false
  for (let i = 0; i < index; i++) {
    const ch = doc[i]
    if (ch === "'" && !inDouble) {
      if (inSingle && doc[i + 1] === "'") {
        i++
        continue
      }
      inSingle = !inSingle
    } else if (ch === '"' && !inSingle) {
      if (inDouble && doc[i + 1] === '"') {
        i++
        continue
      }
      inDouble = !inDouble
    }
  }
  return !inSingle && !inDouble
}

const extractStatementAtCursor = (doc: string, cursor: number): string => {
  const pos = Math.max(0, Math.min(cursor, doc.length))
  let start = 0
  let end = doc.length

  for (let i = pos - 1; i >= 0; i--) {
    if (isSemicolonOutsideString(doc, i)) {
      start = i + 1
      break
    }
  }
  for (let i = pos; i < doc.length; i++) {
    if (isSemicolonOutsideString(doc, i)) {
      end = i
      break
    }
  }

  return doc.slice(start, end).trim()
}

type SqlRunScope = 'selection' | 'cursor' | 'all'

const resolveSqlToRun = (): { sql: string; scope: SqlRunScope } => {
  const fullSql = sql.value.trim()
  if (!editorView.value) {
    return { sql: fullSql, scope: 'all' }
  }

  const view = editorView.value
  const selection = view.state.selection.main

  if (!selection.empty) {
    const selectedText = view.state.sliceDoc(selection.from, selection.to).trim()
    if (selectedText) {
      return { sql: selectedText, scope: 'selection' }
    }
  }

  const doc = view.state.doc.toString()
  const statementAtCursor = extractStatementAtCursor(doc, selection.from)
  if (statementAtCursor && statementAtCursor !== fullSql) {
    return { sql: statementAtCursor, scope: 'cursor' }
  }

  return { sql: fullSql, scope: 'all' }
}

const handleRunQuery = () => {
  const { sql: querySql, scope } = resolveSqlToRun()
  if (!querySql) {
    showToast('请输入 SQL', 'warning')
    return
  }
  if (scope === 'selection') {
    showToast('执行选中的 SQL 片段', 'info')
  } else if (scope === 'cursor') {
    showToast('执行光标所在 SQL 语句', 'info')
  }
  emit('run-query', querySql)
}

const handleDrop = (event: DragEvent) => {
  const text = event.dataTransfer?.getData('application/x-sqllab-item')
  if (text && editorView.value) {
    event.preventDefault()
    event.stopPropagation()
    const pos = editorView.value.posAtCoords({ x: event.clientX, y: event.clientY })
    if (pos !== null) {
      editorView.value.dispatch({
        changes: { from: pos, to: pos, insert: text },
        selection: { anchor: pos + text.length }
      })
      editorView.value.focus()
    }
  }
  // 如果不是我们的自定义类型，则允许默认行为（例如从外部拖入普通文本）
}

const focus = () => {
  if (editorView.value) {
    editorView.value.focus()
  }
}

defineExpose({ focus })
</script>

<template>
  <div class="flex-1 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col overflow-hidden relative">
    <div class="flex items-center bg-gray-100 border-b overflow-x-auto custom-scrollbar no-scrollbar relative">
      <transition-group name="tab-list">
        <div v-for="(tab, idx) in tabs" :key="tab.id" 
          @click="emit('update:activeTabIndex', idx)" @dblclick="startRename(tab)"
          @contextmenu.prevent="openContextMenu($event, idx)"
          :class="activeTabIndex === idx ? 'bg-white text-blue-600 font-bold border-b-white z-10' : 'bg-gray-100 text-gray-500 hover:bg-gray-200 border-b-gray-200'"
          class="flex items-center px-4 py-2.5 cursor-pointer transition-all min-w-[120px] max-w-[200px] border-r border-gray-200 select-none relative group h-10">
          
          <div v-if="activeTabIndex === idx" class="absolute top-0 left-0 right-0 h-0.5 bg-blue-600 rounded-full"></div>
          
          <input v-if="editingTabId === tab.id" :id="`tab-input-${tab.id}`" v-model="editName" @blur="finishRename(idx)" @keydown.enter="finishRename(idx)" @click.stop class="flex-1 text-xs border rounded px-1" />
          <span v-else class="truncate flex-1 text-xs">{{ tab.name || `查询 ${idx + 1}` }}</span>
          
          <button @click.stop="emit('close-tab', idx)" class="ml-2 p-0.5 rounded-full hover:bg-red-100 hover:text-red-500 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity">
            <XMarkIcon class="w-3 h-3" />
          </button>
        </div>
      </transition-group>
      
      <button @click="emit('create-tab')" class="px-3 py-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors h-10 flex items-center justify-center sticky right-0 bg-gradient-to-l from-gray-100 via-gray-100 to-transparent pl-6">
        <span class="text-xl font-light leading-none">+</span>
      </button>
    </div>

    <div class="p-3 border-b bg-gray-50 flex justify-between items-center">
      <div class="flex items-center space-x-3">
        <Tooltip text="展开/收起左侧数据表" position="right">
          <button @click="emit('toggle-sidebar')" :class="!sidebarCollapsed ? 'bg-blue-100 text-blue-600' : 'text-gray-400'" class="p-1.5 rounded-lg"><CircleStackIcon class="w-4 h-4" /></button>
        </Tooltip>
        <div class="flex items-center gap-2">
          <span class="text-xs font-bold text-gray-500">数据源:</span>
          <select :value="selectedSourceId" @change="emit('update:selectedSourceId', Number(($event.target as HTMLSelectElement).value))" class="py-1 text-sm border-gray-300 rounded-md bg-transparent focus:ring-blue-500 focus:border-blue-500">
            <option v-for="ds in dataSources" :key="ds.id" :value="ds.id">{{ ds.source_name }}</option>
          </select>
        </div>
      </div>
      <div class="flex items-center space-x-2">
        <Tooltip text="SQL 片段库" position="bottom">
          <button @click="showSnippets = true" class="p-1.5 text-gray-500 hover:text-blue-600"><CodeBracketIcon class="w-4 h-4" /></button>
        </Tooltip>
        <Tooltip v-if="labMode === 'api'" text="参数预设" position="bottom">
          <button @click="showParamPresets = true" class="p-1.5 text-gray-500 hover:text-blue-600"><AdjustmentsHorizontalIcon class="w-4 h-4" /></button>
        </Tooltip>
        <Tooltip text="快捷键 (?)" position="bottom">
          <button @click="showShortcuts = true" class="p-1.5 text-gray-500 hover:text-blue-600"><QuestionMarkCircleIcon class="w-4 h-4" /></button>
        </Tooltip>
        <Tooltip text="我的查询（云端保存）" position="bottom">
          <button @click="emit('open-saved-queries')" class="p-1.5 text-gray-500 hover:text-blue-600"><BookmarkIcon class="w-4 h-4" /></button>
        </Tooltip>
        <div ref="historyDropdownRef" class="relative">
          <Tooltip text="查看最近 20 条查询历史" position="bottom">
            <button type="button" @click.stop="showHistory = !showHistory" class="p-1.5 text-gray-500 hover:text-blue-600" :class="showHistory ? 'text-blue-600 bg-blue-50 rounded-lg' : ''"><ClockIcon class="w-4 h-4" /></button>
          </Tooltip>
          <div v-if="showHistory" class="absolute right-0 mt-2 w-96 bg-white rounded-xl shadow-2xl border z-[100] py-2 max-h-96 overflow-y-auto custom-scrollbar">
            <div class="px-4 py-2 border-b flex items-center justify-between sticky top-0 bg-white z-10">
              <span class="text-[11px] font-bold text-gray-500">最近 {{ history.length }} 条</span>
              <div class="flex items-center gap-1">
                <button
                  v-if="history.length > 0"
                  type="button"
                  class="text-[11px] font-bold text-red-600 hover:text-red-700 hover:bg-red-50 px-2 py-1 rounded-md transition-colors"
                  @click="handleClearHistory"
                >清空全部</button>
                <button
                  type="button"
                  class="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                  title="关闭"
                  @click="showHistory = false"
                >
                  <XMarkIcon class="w-4 h-4" />
                </button>
              </div>
            </div>
            <div v-if="history.length === 0" class="px-4 py-8 text-center text-gray-400 text-xs italic">暂无查询历史</div>
            <div v-for="(item, idx) in history" :key="idx" @click="handleRestoreHistory(item)" 
              class="px-4 py-3 hover:bg-blue-50 cursor-pointer border-b last:border-none group/hist">
              <div class="flex justify-between items-start gap-2">
                <code class="text-xs text-gray-600 line-clamp-2 font-mono flex-1">{{ item.sql }}</code>
                <button @click="handleDeleteHistory(idx, $event)" class="text-gray-300 hover:text-red-500 opacity-0 group-hover/hist:opacity-100 transition-all p-1 shrink-0">
                  <TrashIcon class="w-3.5 h-3.5" />
                </button>
              </div>
              <div class="flex items-center gap-2 mt-1 text-[10px] text-gray-400">
                <span>{{ formatHistoryTime(item.timestamp) }}</span>
                <span v-if="item.execution_time_ms != null">{{ item.execution_time_ms.toFixed(0) }}ms</span>
                <span v-if="item.row_count != null">{{ item.row_count }} 行</span>
                <span :class="item.success === false ? 'text-red-500' : 'text-green-600'">{{ item.success === false ? '失败' : '成功' }}</span>
                <button
                  class="ml-auto text-indigo-600 hover:underline opacity-0 group-hover/hist:opacity-100"
                  @click.stop="emit('save-history-as-template', item)"
                >另存模板</button>
              </div>
            </div>
          </div>
        </div>
        <Tooltip text="美化 SQL 代码" position="bottom">
          <button @click="formatSql" class="p-1.5 text-gray-500 hover:text-blue-600"><CommandLineIcon class="w-4 h-4" /></button>
        </Tooltip>
        <Tooltip text="管理 SQL 测试变量" position="bottom" v-if="labMode !== 'analyst'">
          <button @click="showParamsPanel = !showParamsPanel" :disabled="labMode === 'api'" :class="showParamsPanel ? 'text-blue-600 bg-blue-50' : 'text-gray-500'" class="p-1.5 rounded-lg hover:bg-blue-100 transition-all disabled:opacity-50 disabled:cursor-not-allowed"><ListBulletIcon class="w-4 h-4" /></button>
        </Tooltip>
        <Tooltip text="清空当前编辑器内容" position="bottom">
          <button @click="clearSql" class="p-1.5 text-gray-500 hover:text-red-600"><TrashIcon class="w-4 h-4" /></button>
        </Tooltip>

        <Tooltip v-if="isAdmin" text="Admin：查看明文（跳过脱敏）" position="bottom">
          <button
            @click="emit('update:unmask', !unmask)"
            :class="unmask ? 'text-amber-600 bg-amber-50' : 'text-gray-500'"
            class="p-1.5 rounded-lg hover:bg-amber-100 transition-all"
          ><EyeIcon class="w-4 h-4" /></button>
        </Tooltip>

        <Tooltip text="预览返回行数上限" position="bottom" align="end">
          <select
            v-if="hasPerm('element:lab:generate')"
            :value="previewLimit"
            class="h-8 px-2 text-xs border border-gray-200 rounded-md bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            @change="emit('update:previewLimit', Number(($event.target as HTMLSelectElement).value))"
          >
            <option :value="50">50 行</option>
            <option :value="100">100 行</option>
            <option :value="200">200 行</option>
            <option :value="500">500 行</option>
            <option :value="1000">1000 行</option>
          </select>
        </Tooltip>

        <Tooltip text="查看执行计划 (EXPLAIN)" position="bottom">
          <button @click="emit('run-explain')" :disabled="executing || !sql.trim()" class="p-1.5 text-gray-500 hover:text-amber-600 disabled:opacity-40"><BoltIcon class="w-4 h-4" /></button>
        </Tooltip>

        <Tooltip v-if="isAiEnabled && hasPerm('element:lab:generate')" text="AI 增量编辑当前 SQL" position="bottom">
          <button @click="showAiEditModal = true" :disabled="!sql.trim()" class="p-1.5 text-gray-500 hover:text-purple-600 disabled:opacity-40"><PencilSquareIcon class="w-4 h-4" /></button>
        </Tooltip>

        <Tooltip text="执行查询 (Ctrl/Cmd+Enter)" position="bottom" align="end">
          <button 
            v-if="hasPerm('element:lab:generate') && !executing" 
            @mousedown.prevent
            @click="handleRunQuery" 
            class="px-4 py-1.5 bg-blue-600 text-white rounded-md text-sm font-medium flex items-center transition-all shadow-sm hover:bg-blue-700"
          >
            <PlayIcon class="w-4 h-4 mr-1" /> 运行
          </button>
        </Tooltip>
        <button
          v-if="executing"
          @click="emit('cancel-query')"
          class="px-4 py-1.5 bg-red-600 text-white rounded-md text-sm font-medium flex items-center shadow-sm hover:bg-red-700"
        >
          <StopIcon class="w-4 h-4 mr-1" /> 取消
        </button>
      </div>
    </div>

    <div class="flex-1 bg-[#1e1e1e] overflow-hidden text-sm relative group/editor flex flex-row">
       <div v-if="noAccess" class="absolute inset-0 z-50 flex items-center justify-center bg-gray-900/90 backdrop-blur-sm">
         <div class="text-center p-8 max-w-md"><h3 class="text-xl font-bold text-white mb-2">暂无权限</h3><p class="text-gray-400">请联系管理员分配数据资产权限。</p></div>
       </div>
       <div class="flex-1 relative" @drop="handleDrop" @dragover.prevent>
         <codemirror v-model="sql" :style="{ height: '100%' }" :extensions="extensions" @ready="handleEditorReady" />
         
         <!-- Floating RAG Context Badge (NEW) -->
         <div v-if="recalledContext?.length" class="absolute top-4 right-4 z-[30]">
            <Tooltip text="AI 参考知识库背景 (RAG Insights)" position="left">
               <button 
                 @click="showRecallPanel = !showRecallPanel"
                 class="w-10 h-10 bg-indigo-600/90 text-white rounded-full shadow-2xl flex items-center justify-center hover:bg-indigo-700 transition-all active:scale-90 border-2 border-indigo-400 animate-in zoom-in duration-300"
               >
                  <SparklesIcon class="w-5 h-5" />
                  <span class="absolute -bottom-1 -right-1 bg-amber-400 text-gray-900 text-[10px] font-black w-5 h-5 rounded-full border-2 border-white flex items-center justify-center">{{ recalledContext.length }}</span>
               </button>
            </Tooltip>
         </div>

         <!-- RAG Context Side Panel -->
         <transition name="slide-fade">
            <div v-if="showRecallPanel" class="absolute top-4 right-16 w-80 bg-white/95 backdrop-blur-md rounded-2xl shadow-2xl border border-indigo-100 z-[40] overflow-hidden flex flex-col max-h-[calc(100%-32px)]">
               <div class="p-4 border-b bg-indigo-50/50 flex justify-between items-center">
                  <div class="flex items-center gap-2">
                     <SparklesIcon class="w-4 h-4 text-indigo-600" />
                     <span class="text-xs font-black text-indigo-900 uppercase tracking-widest">AI 建模背景参考</span>
                  </div>
                  <button @click="showRecallPanel = false" class="text-gray-400 hover:text-gray-600"><XMarkIcon class="w-4 h-4" /></button>
               </div>
               <div class="p-4 overflow-y-auto custom-scrollbar space-y-3">
                  <div v-for="(item, idx) in recalledContext" :key="idx" 
                    class="p-3 bg-white border border-gray-100 rounded-xl shadow-sm hover:border-indigo-300 transition-all group">
                     <div class="flex items-center justify-between mb-1.5">
                        <div class="flex items-center gap-2">
                           <component :is="item.type === 'metric' ? BeakerIcon : TableCellsIcon" class="w-3.5 h-3.5 text-indigo-500" />
                           <span class="text-xs font-bold text-gray-800 font-mono">{{ item.name }}</span>
                        </div>
                        <span class="text-[9px] font-black text-indigo-100 bg-indigo-600 px-1.5 py-0.5 rounded uppercase">{{ item.type }}</span>
                     </div>
                     <p class="text-[10px] text-gray-500 leading-relaxed">{{ item.debug_info || item.reason }}</p>
                     <div v-if="item.score" class="mt-2 flex items-center gap-2">
                        <div class="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden">
                           <div class="h-full bg-indigo-500" :style="{ width: `${item.score * 100}%` }"></div>
                        </div>
                        <span class="text-[9px] font-mono text-gray-400">{{ (item.score * 100).toFixed(1) }}%</span>
                     </div>
                  </div>
               </div>
               <div class="p-3 bg-gray-50 border-t text-center">
                  <p class="text-[9px] text-gray-400 italic font-medium">※ 基于当前对话语义自动召回的业务上下文</p>
               </div>
            </div>
         </transition>
       </div>
       <div v-if="showParamsPanel" class="w-72 p-4 bg-white border-l transition-all flex flex-col relative z-20 shrink-0">
        <div class="flex items-center justify-between mb-1">
          <h3 class="text-xs font-bold text-gray-500 uppercase">测试参数</h3>
          <div class="flex items-center gap-1">
            <button 
              v-if="labMode === 'api'"
              @click="showJinjaHelpModal = true" 
              class="p-1 text-gray-400 hover:text-blue-600 transition-colors"
              title="查看 Jinja2 语法帮助"
            >
              <QuestionMarkCircleIcon class="w-4 h-4" />
            </button>
            <button v-if="labMode !== 'api'" @click="showParamsPanel = false" class="text-gray-400 hover:text-gray-600"><XMarkIcon class="w-4 h-4" /></button>
          </div>
        </div>
        <p class="text-[10px] text-gray-400 mb-3 leading-relaxed">配置 SQL 变量并验证发布兼容性</p>

        <Tooltip text="智能校验 SQL 是否符合 API 发布规范" position="bottom" class="w-full">
          <button 
            v-if="isAiEnabled && labMode === 'api' && hasPerm('element:lab:generate')" 
            @click="emit('run-ai-check')" 
            :disabled="aiLoading || !sql.trim()" 
            class="w-full mb-4 flex items-center justify-center px-3 py-2 rounded-lg text-[11px] font-bold bg-purple-50 text-purple-700 hover:bg-purple-100 disabled:opacity-50 border border-purple-100 transition-all shadow-sm"
          >
            <SparklesIcon class="w-3.5 h-3.5 mr-2" /> AI 智能校验 SQL
          </button>
        </Tooltip>

        <div class="overflow-y-auto flex-1 custom-scrollbar">
          <div v-if="sqlVariables.length === 0" class="p-6 border-2 border-dashed border-gray-100 rounded-xl text-center bg-gray-50/50">
            <CommandLineIcon class="w-8 h-8 text-gray-300 mx-auto mb-2 opacity-50" />
            <p class="text-xs text-gray-400 font-medium">未检测到 SQL 变量</p>
            <p class="text-[10px] text-gray-400 mt-1 leading-relaxed">发布 API 必须包含动态参数<br/>(如 {{ jinjaExample1 }} 或 {{ jinjaExample2 }})</p>
          </div>
          
          <div v-for="v in sqlVariables" :key="v" class="mb-4 last:mb-0">
            <div class="flex items-center justify-between group/pitem">
              <label class="text-xs text-gray-500 font-semibold">{{ v }}:</label>
              <!-- 切换模式按钮 -->
              <button 
                v-if="v.toLowerCase().includes('time') || v.toLowerCase().includes('date') || v.toLowerCase().includes('day')"
                @click="toggleParamMode(v)" 
                class="text-[10px] text-gray-400 hover:text-blue-500 flex items-center gap-1 transition-colors"
                :title="paramModeOverrides[v] ? '切回智能日期模式' : '切为普通文本模式'"
              >
                <component :is="paramModeOverrides[v] ? CalendarDaysIcon : PencilSquareIcon" class="w-3 h-3" />
                <span>{{ paramModeOverrides[v] ? '自动' : '文本' }}</span>
              </button>
            </div>

            <!-- 自动根据变量名渲染不同类型的输入框 (受手动模式控制) -->
            <input 
              v-if="!paramModeOverrides[v] && v.toLowerCase().includes('time')"
              type="datetime-local"
              v-model="testParams[v]" 
              class="w-full mt-1 px-3 py-1.5 bg-gray-50 border rounded text-sm font-mono focus:ring-blue-500 transition-all" 
            />
            <input 
              v-else-if="!paramModeOverrides[v] && (v.toLowerCase().includes('date') || v.toLowerCase().includes('day'))"
              type="date"
              v-model="testParams[v]" 
              class="w-full mt-1 px-3 py-1.5 bg-gray-50 border rounded text-sm font-mono focus:ring-blue-500 transition-all" 
            />
            <input 
              v-else
              v-model="testParams[v]" 
              placeholder="输入参数值..."
              class="w-full mt-1 px-3 py-1.5 bg-gray-50 border rounded text-sm font-mono focus:ring-blue-500 transition-all" 
            />
          </div>

          <div class="mt-6 pt-4 border-t space-y-3">
            <p v-if="sqlVariables.length > 0" class="text-[10px] text-gray-400 font-medium text-center mb-1">请执行测试以验证 SQL 的准确性</p>
            
            <Tooltip text="测试所有参数为空时的查询结果" position="top" class="w-full">
              <button @click="emit('run-empty-test')" :disabled="executing || sqlVariables.length === 0" 
                :class="[
                  'w-full py-2.5 rounded-lg font-bold border transition-all flex items-center justify-center gap-2 group',
                  sqlVariables.length > 0 
                    ? 'bg-gray-50 hover:bg-white hover:shadow-sm border-gray-200' 
                    : 'bg-gray-50/50 text-gray-300 border-gray-100 cursor-not-allowed'
                ]">
                <span :class="sqlVariables.length > 0 ? 'bg-blue-100 text-blue-600 border-blue-200 group-hover:bg-blue-600 group-hover:text-white' : 'bg-gray-100 text-gray-300 border-gray-200'" 
                  class="w-5 h-5 rounded-full flex items-center justify-center text-[11px] border transition-colors">1</span>
                <span class="text-[11px]" :class="sqlVariables.length > 0 ? 'text-gray-700' : 'text-gray-300'">运行空参数测试</span>
              </button>
            </Tooltip>
            
            <Tooltip text="将此 SQL 发布为永久可用的 REST API" position="top" class="w-full">
              <button 
                v-if="labMode === 'api' && hasPerm('element:lab:publish')" 
                @click="emit('open-publish')" 
                :disabled="!currentTab?.emptyTestPassed || sqlVariables.length === 0"
                :class="[
                  'w-full py-2.5 rounded-lg font-bold border transition-all flex items-center justify-center gap-2',
                  (currentTab?.emptyTestPassed && sqlVariables.length > 0)
                    ? 'bg-green-600 text-white hover:bg-green-700 shadow-md border-transparent' 
                    : 'bg-gray-50/50 text-gray-300 border-gray-100 cursor-not-allowed'
                ]"
              >
                <span :class="(currentTab?.emptyTestPassed && sqlVariables.length > 0) ? 'bg-white/20 text-white border-white/30' : 'bg-gray-100 text-gray-300 border-gray-200'" 
                  class="w-5 h-5 rounded-full flex items-center justify-center text-[11px] border">2</span>
                <span class="text-[11px]">发布为 API</span>
              </button>
            </Tooltip>
          </div>
        </div>
      </div>
    </div>
    <!-- Jinja2 Help Modal -->
    <div v-if="showJinjaHelpModal" class="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm" @click.self="showJinjaHelpModal = false">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden animate-in zoom-in duration-200 flex flex-col max-h-[85vh]">
        <div class="p-5 border-b bg-gray-50 flex justify-between items-center">
          <h3 class="text-lg font-bold text-gray-900 flex items-center gap-2">
            <SparklesIcon class="w-6 h-6 text-purple-600" /> Jinja2 模板语法指南
          </h3>
          <button @click="showJinjaHelpModal = false" class="text-gray-400 hover:text-gray-600 transition-colors"><XMarkIcon class="w-6 h-6" /></button>
        </div>
        
        <div class="p-6 overflow-y-auto custom-scrollbar space-y-6">
          <!-- 1. Basic Variable -->
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-bold uppercase">基础变量</span>
              <h4 class="text-sm font-bold text-gray-800">变量注入与默认值</h4>
            </div>
            <p class="text-xs text-gray-500">使用双大括号注入变量。如果变量未传，系统自动渲染为 <code class="bg-gray-100 px-1 rounded">NULL</code> 以防报错。</p>
            <div v-pre class="bg-gray-900 rounded-lg p-3 border border-gray-700">
              <code class="text-xs font-mono block text-green-400">SELECT * FROM users WHERE id = <span class="text-yellow-300">{{ id }}</span></code>
            </div>
          </div>

          <!-- 2. String Quoting (Critical) -->
          <div class="space-y-2 p-4 bg-red-50 rounded-xl border border-red-100">
            <div v-pre class="flex items-center gap-2 text-red-600">
              <span class="px-2 py-0.5 bg-red-200 text-red-800 rounded text-xs font-bold uppercase">重要限制</span>
              <h4 class="text-sm font-bold">必须手动添加引号</h4>
            </div>
            <p class="text-xs text-red-500 leading-relaxed">
              当前版本不支持自动参数化转义。如果变量是字符串类型，<strong>必须</strong>在模板中手动包裹单引号，否则会报 SQL 语法错误。
            </p>
            <div v-pre class="grid grid-cols-2 gap-4 mt-2">
              <div class="bg-white p-3 rounded border border-red-200">
                <div class="text-[10px] font-bold text-red-500 mb-1 uppercase">❌ 错误写法</div>
                <code class="text-xs font-mono text-gray-600">name = <span class="text-red-500">{{ name }}</span></code>
              </div>
              <div class="bg-white p-3 rounded border border-green-200">
                <div class="text-[10px] font-bold text-green-600 mb-1 uppercase">✅ 正确写法</div>
                <code class="text-xs font-mono text-gray-600">name = <span class="text-green-600">'{{ name }}'</span></code>
              </div>
            </div>
          </div>

          <!-- 3. Logic Control -->
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-bold uppercase">逻辑控制</span>
              <h4 class="text-sm font-bold text-gray-800">条件判断 (If/Else)</h4>
            </div>
            <div v-pre class="bg-gray-900 rounded-lg p-3 border border-gray-700 text-xs font-mono text-gray-300 leading-relaxed">
              <span class="text-purple-400">{% if status == 'active' %}</span><br/>
              &nbsp;&nbsp;AND status = 1<br/>
              <span class="text-purple-400">{% elif status == 'banned' %}</span><br/>
              &nbsp;&nbsp;AND status = 0<br/>
              <span class="text-purple-400">{% else %}</span><br/>
              &nbsp;&nbsp;AND 1=1<br/>
              <span class="text-purple-400">{% endif %}</span>
            </div>
          </div>

          <!-- 4. Loops -->
          <div class="space-y-2" v-pre>
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs font-bold uppercase">循环遍历</span>
              <h4 class="text-sm font-bold text-gray-800">列表生成 (IN 查询)</h4>
            </div>
            <p class="text-xs text-gray-500">不支持直接 <code>IN {{ list }}</code>，需使用循环手动构建。</p>
            <div class="bg-gray-900 rounded-lg p-3 border border-gray-700 text-xs font-mono text-gray-300">
              AND id IN (<br/>
              &nbsp;&nbsp;<span class="text-orange-400">{% for id in ids %}</span><br/>
              &nbsp;&nbsp;&nbsp;&nbsp;{{ id }}<span class="text-orange-400">{{ "," if not loop.last }}</span><br/>
              &nbsp;&nbsp;<span class="text-orange-400">{% endfor %}</span><br/>
              )
            </div>
          </div>

          <!-- 5. Object Access -->
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-bold uppercase">对象访问</span>
            </div>
            <div v-pre class="flex gap-4">
              <div class="flex-1 bg-gray-50 p-3 rounded border text-xs">
                <div class="font-bold text-gray-500 mb-1">点号访问</div>
                <code class="font-mono text-blue-600">{{ user.profile.email }}</code>
              </div>
              <div class="flex-1 bg-gray-50 p-3 rounded border text-xs">
                <div class="font-bold text-gray-500 mb-1">下标访问</div>
                <code class="font-mono text-blue-600">{{ tags[0] }}</code>
              </div>
            </div>
          </div>
        </div>
        
        <div class="p-5 bg-gray-50 border-t text-center">
          <button @click="showJinjaHelpModal = false" class="px-8 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 transition-colors shadow-sm text-sm">
            我已知晓
          </button>
        </div>
      </div>
    </div>

    <!-- Tab Context Menu -->
    <teleport to="body">
      <div v-if="contextMenu.show" 
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
        class="fixed z-[9999] bg-white rounded-lg shadow-xl border border-gray-100 py-1 min-w-[120px] animate-in fade-in zoom-in duration-100"
      >
        <button @click="handleCloseTab(contextMenu.index)" class="w-full px-4 py-2 text-left text-xs text-gray-700 hover:bg-gray-50 flex items-center gap-2">
          <XMarkIcon class="w-3.5 h-3.5 text-gray-400" /> 关闭标签页
        </button>
        <button @click="handleCloseOthers" class="w-full px-4 py-2 text-left text-xs text-gray-700 hover:bg-gray-50 flex items-center gap-2">
          <CircleStackIcon class="w-3.5 h-3.5 text-gray-400" /> 关闭其他标签页
        </button>
        <div class="h-px bg-gray-100 my-1"></div>
        <button @click="handleCloseAll" class="w-full px-4 py-2 text-left text-xs text-red-600 hover:bg-red-50 flex items-center gap-2">
          <TrashIcon class="w-3.5 h-3.5" /> 关闭所有标签页
        </button>
      </div>
    </teleport>

    <div v-if="sensitiveWarnings?.length" class="px-3 py-1.5 bg-amber-50 border-t border-amber-100 text-[10px] text-amber-800 flex flex-wrap gap-2">
      <span v-for="(w, i) in sensitiveWarnings" :key="i">⚠ {{ w.message }}</span>
    </div>

    <div v-if="showAiEditModal" class="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
        <h3 class="font-bold text-gray-800">AI 增量编辑</h3>
        <textarea v-model="aiEditInstruction" rows="3" placeholder="描述要如何修改当前 SQL..." class="w-full border rounded-xl p-3 text-sm" />
        <div class="flex gap-2 justify-end">
          <button class="px-4 py-2 border rounded-lg text-sm" @click="showAiEditModal = false">取消</button>
          <button class="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-bold" :disabled="!aiEditInstruction.trim()" @click="emit('ai-edit-sql', aiEditInstruction); showAiEditModal = false; aiEditInstruction = ''">生成修改</button>
        </div>
      </div>
    </div>
    <LabShortcutsModal :open="showShortcuts" @close="showShortcuts = false" />
    <LabSnippetsPanel :open="showSnippets" @close="showSnippets = false" @insert="insertAtCursor" />
    <LabParamPresetsPanel
      :open="showParamPresets"
      :source-id="selectedSourceId"
      :current-params="testParams"
      @close="showParamPresets = false"
      @apply="(p) => { testParams = p }"
    />
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #e5e7eb;
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #d1d5db;
}

.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;  /* IE and Edge */
  scrollbar-width: none;  /* Firefox */
}

/* Tab Animation */
.tab-list-move,
.tab-list-enter-active,
.tab-list-leave-active {
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.5, 1);
}

.tab-list-enter-from,
.tab-list-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.95);
}

.tab-list-leave-active {
  position: absolute; /* Ensure smooth removal layout flow */
}

/* Slide Fade for Recall Panel */
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.2s cubic-bezier(1, 0.5, 0.8, 1);
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateX(20px);
  opacity: 0;
}
</style>