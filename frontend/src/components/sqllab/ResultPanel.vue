<script setup lang="ts">
import { ref, computed } from 'vue'
import { PlayIcon, SparklesIcon, TableCellsIcon, DocumentTextIcon, ArrowsRightLeftIcon } from '@heroicons/vue/24/outline'
import MarkdownIt from 'markdown-it'
import Tooltip from '../common/Tooltip.vue'
import { useToast } from '../../composables/useToast'

const { showToast } = useToast()

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
})

interface PreviewResult {
  columns: { name: string; type: string }[]
  rows: any[][]
  execution_time_ms: number
  scanned_rows: number
}

const props = defineProps<{
  activeSubTab: 'result' | 'ai'
  result: PreviewResult | null
  error: string | null
  executing: boolean
  aiLoading: boolean
  aiContent: string
  optimizedSql: string
  labMode?: 'api' | 'analyst'
  hasPerm: (code: string) => boolean
  isAiEnabled: boolean
  sql?: string
  recalledContext?: any[]
  previewLimit?: number
}>()

const emit = defineEmits<{
  (e: 'update:activeSubTab', tab: 'result' | 'ai'): void
  (e: 'clear-result'): void
  (e: 'apply-ai-fix'): void
  (e: 'open-analysis'): void
  (e: 'export-excel'): void
  (e: 'ai-fix-error'): void
}>()

// Sorting Logic
const sortColumn = ref<string | null>(null)
const sortDirection = ref<'asc' | 'desc' | null>(null)
type ResultViewMode = 'table' | 'text' | 'transpose'
const resultViewMode = ref<ResultViewMode>('table')

const formatCell = (value: unknown) => (value === null || value === undefined ? 'NULL' : String(value))

const handleHeaderClick = (colName: string) => {
  if (sortColumn.value === colName) {
    if (sortDirection.value === 'asc') sortDirection.value = 'desc'
    else if (sortDirection.value === 'desc') sortDirection.value = null
    else sortDirection.value = 'asc'
  } else {
    sortColumn.value = colName
    sortDirection.value = 'asc'
  }
}

const sortedRows = computed(() => {
  if (!props.result || !props.result.rows) return []
  if (!sortColumn.value || !sortDirection.value) return props.result.rows

  const colIndex = props.result.columns.findIndex(c => c.name === sortColumn.value)
  if (colIndex === -1) return props.result.rows

  const rows = [...props.result.rows]
  rows.sort((a, b) => {
    const valA = a[colIndex]; const valB = b[colIndex]
    if (valA === valB) return 0
    if (valA === null) return 1
    if (valB === null) return -1
    if (valA < valB) return sortDirection.value === 'asc' ? -1 : 1
    return sortDirection.value === 'asc' ? 1 : -1
  })
  return rows
})

const textOutput = computed(() => {
  if (!props.result) return ''
  const header = props.result.columns.map(c => c.name).join('\t')
  const body = sortedRows.value.map(row => row.map(formatCell).join('\t')).join('\n')
  return body ? `${header}\n${body}` : header
})

const transposedTable = computed(() => {
  if (!props.result) return { headers: [] as string[], rows: [] as string[][] }
  const colNames = props.result.columns.map(c => c.name)
  const headers = ['字段', ...sortedRows.value.map((_, i) => `行 ${i + 1}`)]
  const rows = colNames.map((name, colIdx) => [
    name,
    ...sortedRows.value.map(row => formatCell(row[colIdx])),
  ])
  return { headers, rows }
})

const copyTextOutput = async () => {
  try {
    await navigator.clipboard.writeText(textOutput.value)
    showToast('结果已复制为文本', 'success')
  } catch {
    showToast('复制失败', 'error')
  }
}

const resultArea = ref<HTMLElement | null>(null)
const scrollToTop = () => { resultArea.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }

defineExpose({ scrollToTop })
</script>

<template>
  <div ref="resultArea" class="bg-white rounded-xl shadow-sm border border-gray-200 min-h-[600px] flex-1 flex flex-col scroll-mt-6">
    <div class="flex border-b border-gray-200 bg-gray-50 justify-between items-center pr-4">
      <div class="flex">
        <button @click="emit('update:activeSubTab', 'result')" 
          class="px-8 py-3 text-sm font-semibold transition-all" 
          :class="activeSubTab==='result' ? 'text-blue-600 border-b-2 border-blue-600 bg-white' : 'text-gray-500 hover:text-gray-700'">
          执行结果 <span v-if="result" class="text-xs font-normal text-gray-400 ml-1">({{ result.rows.length }}行)</span>
        </button>
        <button v-if="isAiEnabled && labMode === 'api' && hasPerm('element:lab:generate')" @click="emit('update:activeSubTab', 'ai')" 
          class="px-8 py-3 text-sm font-semibold transition-all" 
          :class="activeSubTab==='ai' ? 'text-purple-600 border-b-2 border-purple-600 bg-white' : 'text-gray-500 hover:text-gray-700'">AI 校验报告</button>
      </div>

      <div v-if="result && activeSubTab === 'result'" class="flex items-center gap-2">
        <Tooltip text="基于当前结果集进行深度 AI 数据洞察" position="bottom" align="end">
          <button v-if="labMode === 'analyst' && isAiEnabled && hasPerm('element:lab:analysis')" @click="emit('open-analysis')" 
            class="flex items-center px-3 py-1.5 bg-indigo-50 text-indigo-600 rounded-lg text-xs font-bold border border-indigo-100 hover:bg-indigo-100 transition-all">
            <SparklesIcon class="w-3.5 h-3.5 mr-1.5" /> AI 智能分析
          </button>
        </Tooltip>
        <Tooltip text="将当前结果导出为 Excel 文件" position="bottom" align="end">
          <button v-if="labMode === 'analyst' && hasPerm('element:lab:export')" @click="emit('export-excel')" 
            class="flex items-center px-3 py-1.5 bg-green-50 text-green-600 rounded-lg text-xs font-bold border border-green-100 hover:bg-green-100 transition-all">
            <svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4-4m0 0l-4 4m4-4v12" /></svg>
            导出 Excel
          </button>
        </Tooltip>
      </div>
    </div>
    
    <div class="flex-1 min-h-0 bg-white">
      <div v-if="activeSubTab==='result'" class="h-full flex flex-col">
        <div v-if="result" class="bg-blue-50/50 border-b border-blue-100 px-4 py-1.5 flex items-center justify-between gap-3 text-[11px] text-blue-700">
          <div class="flex items-center gap-4 font-bold min-w-0">
            <span>耗时: {{ result.execution_time_ms.toFixed(2) }}ms</span>
            <span>返回: {{ result.rows.length }} 行</span>
            <span v-if="previewLimit" class="text-blue-500/80 font-medium">上限 {{ previewLimit }} 行</span>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <div class="flex items-center p-0.5 bg-white/80 border border-blue-100 rounded-md">
              <button
                type="button"
                class="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold transition-colors"
                :class="resultViewMode === 'table' ? 'bg-blue-600 text-white' : 'text-blue-600 hover:bg-blue-50'"
                @click="resultViewMode = 'table'"
              >
                <TableCellsIcon class="w-3 h-3" /> 表格
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold transition-colors"
                :class="resultViewMode === 'text' ? 'bg-blue-600 text-white' : 'text-blue-600 hover:bg-blue-50'"
                @click="resultViewMode = 'text'"
              >
                <DocumentTextIcon class="w-3 h-3" /> 文本
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold transition-colors"
                :class="resultViewMode === 'transpose' ? 'bg-blue-600 text-white' : 'text-blue-600 hover:bg-blue-50'"
                @click="resultViewMode = 'transpose'"
              >
                <ArrowsRightLeftIcon class="w-3 h-3" /> 行转列
              </button>
            </div>
            <Tooltip text="清空当前查询结果并聚焦编辑器" position="bottom" align="end">
              <button @click="emit('clear-result')" class="text-blue-400 hover:text-blue-600 transition-colors">清除结果</button>
            </Tooltip>
          </div>
        </div>
        
        <div v-if="error" class="p-6 bg-red-50 m-4 rounded-xl border border-red-100 flex flex-col gap-4">
          <div class="text-red-600 text-sm font-mono whitespace-pre-wrap">{{ error }}</div>
          <div v-if="isAiEnabled && hasPerm('element:lab:generate')" class="flex justify-end">
            <Tooltip text="分析报错原因并自动提供修复建议" position="top" align="end">
              <button @click="emit('ai-fix-error')" :disabled="aiLoading"
                class="flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-bold shadow-md hover:bg-indigo-700 transition-all disabled:opacity-50">
                <SparklesIcon class="w-3.5 h-3.5 mr-2" />
                AI 智能纠错
              </button>
            </Tooltip>
          </div>
        </div>
        
        <div v-else-if="result" class="overflow-auto flex-1 min-h-0">
          <!-- 表格视图 -->
          <table v-if="resultViewMode === 'table'" class="min-w-full divide-y divide-gray-200 border-separate" style="border-spacing: 0">
            <thead class="bg-gray-50 sticky top-0 z-10">
              <tr>
                <th v-for="c in result.columns" :key="c.name" @click="handleHeaderClick(c.name)" class="px-6 py-3 text-left text-xs font-bold text-gray-500 border-b border-gray-200 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none">
                  {{ c.name }}
                  <span v-if="sortColumn === c.name" class="ml-1 text-blue-500">{{ sortDirection === 'asc' ? '↑' : '↓' }}</span>
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="(r, i) in sortedRows" :key="i" class="hover:bg-gray-50 transition-colors">
                <td v-for="(v, j) in r" :key="j" class="px-6 py-3 text-sm text-gray-600 font-mono border-b border-gray-100 whitespace-nowrap">{{ formatCell(v) }}</td>
              </tr>
            </tbody>
          </table>

          <!-- 文本视图（TSV） -->
          <div v-else-if="resultViewMode === 'text'" class="h-full flex flex-col">
            <div class="flex justify-end px-4 py-2 border-b border-gray-100 bg-gray-50/50">
              <button type="button" class="text-[11px] text-blue-600 hover:text-blue-800 font-medium" @click="copyTextOutput">复制文本</button>
            </div>
            <pre class="flex-1 p-4 text-xs leading-relaxed text-gray-700 font-mono whitespace-pre overflow-auto custom-scrollbar">{{ textOutput }}</pre>
          </div>

          <!-- 行转列视图 -->
          <table v-else class="min-w-full divide-y divide-gray-200 border-separate" style="border-spacing: 0">
            <thead class="bg-gray-50 sticky top-0 z-10">
              <tr>
                <th
                  v-for="(header, idx) in transposedTable.headers"
                  :key="header"
                  class="px-4 py-3 text-left text-xs font-bold border-b border-gray-200 uppercase tracking-wider select-none"
                  :class="idx === 0 ? 'text-gray-700 bg-gray-100' : 'text-gray-500'"
                >
                  {{ header }}
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="(row, i) in transposedTable.rows" :key="i" class="hover:bg-gray-50 transition-colors">
                <td
                  v-for="(cell, j) in row"
                  :key="j"
                  class="px-4 py-2.5 text-sm font-mono border-b border-gray-100"
                  :class="j === 0 ? 'text-gray-800 font-semibold bg-gray-50/50 whitespace-nowrap' : 'text-gray-600 whitespace-nowrap'"
                >
                  {{ cell }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        
        <div v-else class="h-80 flex flex-col items-center justify-center text-gray-400">
          <PlayIcon class="w-12 h-12 mb-3 opacity-20" /><p>运行查询以查看结果</p>
        </div>
      </div>
      
      <div v-else class="p-8 h-full flex flex-col">
        <!-- Knowledge Recall Report -->
        <div v-if="recalledContext && recalledContext.length > 0 && !aiLoading" class="mb-6 p-4 bg-indigo-50/30 border border-indigo-100/50 rounded-2xl animate-in slide-in-from-top-2">
           <div class="flex items-center gap-2 mb-3">
              <SparklesIcon class="w-4 h-4 text-indigo-600" />
              <span class="text-xs font-black text-indigo-900 uppercase tracking-widest">本次 AI 生成参考的业务元数据 (RAG)</span>
           </div>
           <div class="flex flex-wrap gap-2">
              <div v-for="(item, idx) in recalledContext" :key="idx" 
                class="px-3 py-1.5 bg-white border border-indigo-100 rounded-xl shadow-sm flex flex-col gap-0.5">
                 <div class="flex items-center gap-1.5">
                    <span class="text-[9px] font-black text-indigo-500 uppercase">{{ item.type }}</span>
                    <span class="text-[11px] font-bold text-gray-800 font-mono">{{ item.name }}</span>
                 </div>
                 <span class="text-[8px] text-gray-400 font-medium">{{ item.reason }}</span>
              </div>
           </div>
        </div>

        <div v-if="aiLoading" class="flex-1 flex flex-col items-center justify-center text-gray-400 animate-pulse"><SparklesIcon class="w-12 h-12 mb-4 text-purple-300" /><p>AI 正在分析中...</p></div>
        <div v-else-if="aiContent" class="h-full flex flex-col">
          <div v-if="optimizedSql" class="flex justify-end mb-4">
            <Tooltip text="将 AI 建议的 SQL 应用到当前编辑器" position="top" align="end">
              <button @click="emit('apply-ai-fix')" class="flex items-center px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-bold shadow-lg hover:bg-purple-700 transition-all">应用建议</button>
            </Tooltip>
          </div>
          <div class="prose prose-purple max-w-none text-gray-700 bg-purple-50/50 p-10 rounded-3xl border border-purple-100 overflow-auto flex-1"><div class="markdown-body" v-html="md.render(aiContent)"></div></div>
        </div>
      </div>
    </div>
  </div>
</template>
