<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  TableCellsIcon, DocumentTextIcon, ArrowsRightLeftIcon, ChartBarIcon, MagnifyingGlassIcon, XMarkIcon,
} from '@heroicons/vue/24/outline'
import LabQuickChart from './LabQuickChart.vue'
import LabResultStats from './LabResultStats.vue'
import LabResultPivot from './LabResultPivot.vue'
import LabResultCompare from './LabResultCompare.vue'
import LabVirtualTable from './LabVirtualTable.vue'
import { useToast } from '../../composables/useToast'

export type PreviewResult = {
  columns: { name: string; type?: string }[]
  rows: any[][]
  execution_time_ms?: number
  scanned_rows?: number
  total_count?: number
  offset?: number
  limit?: number
  risk_warnings?: { level: string; code?: string; message: string }[]
}

type TypedResultColumn = { name: string; type: string }

const normalizeColumns = (columns: { name: string; type?: string }[]): TypedResultColumn[] =>
  columns.map(col => ({ name: col.name, type: col.type ?? '' }))

const normalizePreviewResult = (result: PreviewResult): PreviewResult & { columns: TypedResultColumn[] } => ({
  ...result,
  columns: normalizeColumns(result.columns),
})

const props = withDefaults(defineProps<{
  result: PreviewResult | null
  error?: string | null
  totalCount?: number | null
  previewLimit?: number
  previewOffset?: number
  compareSnapshot?: PreviewResult | null
  showClear?: boolean
  compact?: boolean
  emptyText?: string
}>(), {
  error: null,
  totalCount: null,
  previewLimit: undefined,
  previewOffset: 0,
  compareSnapshot: null,
  showClear: true,
  compact: false,
  emptyText: '暂无数据',
})

const emit = defineEmits<{
  (e: 'clear'): void
  (e: 'page-change', offset: number): void
  (e: 'clear-baseline'): void
}>()

const { showToast } = useToast()

const sortColumn = ref<string | null>(null)
const sortDirection = ref<'asc' | 'desc' | null>(null)
type ResultViewMode = 'table' | 'text' | 'transpose' | 'chart' | 'pivot' | 'stats'
const resultViewMode = ref<ResultViewMode>('table')
const columnFilter = ref('')
const expandedCell = ref<{ row: number; col: number; value: string } | null>(null)

const formatCell = (value: unknown) => (value === null || value === undefined ? 'NULL' : String(value))

const isJsonLike = (value: unknown) => {
  if (typeof value !== 'string') return false
  const t = value.trim()
  return (t.startsWith('{') && t.endsWith('}')) || (t.startsWith('[') && t.endsWith(']'))
}

const formatCellDisplay = (value: unknown) => {
  const s = formatCell(value)
  return s.length > 120 ? s.slice(0, 120) + '…' : s
}

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

const filteredRows = computed(() => {
  if (!props.result?.rows) return []
  if (!columnFilter.value.trim()) return props.result.rows
  const q = columnFilter.value.trim().toLowerCase()
  return props.result.rows.filter(row =>
    row.some(v => formatCell(v).toLowerCase().includes(q))
  )
})

const sortedRows = computed(() => {
  if (!props.result || !filteredRows.value) return []
  if (!sortColumn.value || !sortDirection.value) return filteredRows.value

  const colIndex = props.result.columns.findIndex(c => c.name === sortColumn.value)
  if (colIndex === -1) return filteredRows.value

  const rows = [...filteredRows.value]
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

const effectiveTotal = computed(() => props.totalCount ?? props.result?.total_count ?? null)
const effectiveLimit = computed(() => props.previewLimit ?? props.result?.limit)

const totalPages = computed(() => {
  if (!effectiveTotal.value || !effectiveLimit.value) return 1
  return Math.ceil(effectiveTotal.value / effectiveLimit.value)
})

const currentPage = computed(() => {
  if (!effectiveLimit.value) return 1
  return Math.floor((props.previewOffset || 0) / effectiveLimit.value) + 1
})

const copyTextOutput = async () => {
  try {
    await navigator.clipboard.writeText(textOutput.value)
    showToast('结果已复制为文本', 'success')
  } catch {
    showToast('复制失败', 'error')
  }
}

const copyColumn = async (colIdx: number) => {
  if (!props.result) return
  const lines = sortedRows.value.map(r => formatCell(r[colIdx]))
  try {
    await navigator.clipboard.writeText(lines.join('\n'))
    showToast('列已复制', 'success')
  } catch {
    showToast('复制失败', 'error')
  }
}

const useVirtualScroll = computed(() => sortedRows.value.length > 60)

const typedColumns = computed(() => (props.result ? normalizeColumns(props.result.columns) : []))

const normalizedResult = computed(() => (props.result ? normalizePreviewResult(props.result) : null))

const normalizedCompareSnapshot = computed(() =>
  props.compareSnapshot ? normalizePreviewResult(props.compareSnapshot) : null
)

const onCellClick = (payload: { row: number; col: number; value: string }) => {
  const v = payload.value
  if ((v.startsWith('{') && v.endsWith('}')) || (v.startsWith('[') && v.endsWith(']'))) {
    expandedCell.value = { row: payload.row, col: payload.col, value: v }
  }
}

const cellPad = computed(() => (props.compact ? 'px-4 py-2' : 'px-6 py-3'))
</script>

<template>
  <div class="h-full flex flex-col min-h-0">
    <div
      v-if="result"
      class="bg-blue-50/50 border-b border-blue-100 flex items-center justify-between gap-3 text-[11px] text-blue-700 shrink-0"
      :class="compact ? 'px-3 py-1.5' : 'px-4 py-1.5'"
    >
      <div class="flex items-center gap-4 font-bold min-w-0 flex-wrap">
        <span v-if="result.execution_time_ms != null">耗时: {{ result.execution_time_ms.toFixed(2) }}ms</span>
        <span>返回: {{ result.rows.length }} 行</span>
        <span v-if="effectiveTotal != null" class="text-blue-500/80">共约 {{ effectiveTotal }} 行</span>
        <span v-if="effectiveLimit" class="text-blue-500/80 font-medium">上限 {{ effectiveLimit }} 行</span>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <div class="relative">
          <MagnifyingGlassIcon class="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-gray-400" />
          <input v-model="columnFilter" placeholder="筛选..." class="pl-7 pr-2 py-1 text-[10px] border rounded-md w-28" />
        </div>
        <div class="flex items-center p-0.5 bg-white/80 border border-blue-100 rounded-md">
          <button type="button" class="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold transition-colors" :class="resultViewMode === 'table' ? 'bg-blue-600 text-white' : 'text-blue-600 hover:bg-blue-50'" @click="resultViewMode = 'table'">
            <TableCellsIcon class="w-3 h-3" /> 表格
          </button>
          <button type="button" class="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold transition-colors" :class="resultViewMode === 'text' ? 'bg-blue-600 text-white' : 'text-blue-600 hover:bg-blue-50'" @click="resultViewMode = 'text'">
            <DocumentTextIcon class="w-3 h-3" /> 文本
          </button>
          <button type="button" class="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold transition-colors" :class="resultViewMode === 'chart' ? 'bg-blue-600 text-white' : 'text-blue-600 hover:bg-blue-50'" @click="resultViewMode = 'chart'">
            <ChartBarIcon class="w-3 h-3" /> 图表
          </button>
          <button type="button" class="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold transition-colors" :class="resultViewMode === 'pivot' ? 'bg-blue-600 text-white' : 'text-blue-600 hover:bg-blue-50'" @click="resultViewMode = 'pivot'">透视</button>
          <button type="button" class="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold transition-colors" :class="resultViewMode === 'stats' ? 'bg-blue-600 text-white' : 'text-blue-600 hover:bg-blue-50'" @click="resultViewMode = 'stats'">统计</button>
          <button type="button" class="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold transition-colors" :class="resultViewMode === 'transpose' ? 'bg-blue-600 text-white' : 'text-blue-600 hover:bg-blue-50'" @click="resultViewMode = 'transpose'">
            <ArrowsRightLeftIcon class="w-3 h-3" /> 行转列
          </button>
        </div>
        <button v-if="showClear" type="button" class="text-blue-400 hover:text-blue-600 transition-colors text-[10px]" @click="emit('clear')">清除结果</button>
      </div>
    </div>

    <div v-if="result?.risk_warnings?.length" class="px-4 py-2 bg-amber-50 border-b border-amber-100 text-[11px] space-y-1 shrink-0">
      <div v-for="(w, wi) in result.risk_warnings" :key="wi" :class="w.level === 'danger' ? 'text-red-700' : w.level === 'warn' ? 'text-amber-700' : 'text-gray-600'">
        ⚠ {{ w.message }}
      </div>
    </div>

    <div v-if="error" class="p-6 bg-red-50 m-4 rounded-xl border border-red-100 text-red-600 text-sm font-mono whitespace-pre-wrap">
      {{ error }}
    </div>

    <div v-else-if="result" class="flex-1 min-h-0 flex flex-col overflow-hidden">
      <LabResultCompare
        v-if="normalizedCompareSnapshot && normalizedResult"
        :baseline="normalizedCompareSnapshot"
        :current="normalizedResult"
        @clear-baseline="emit('clear-baseline')"
      />

      <LabVirtualTable
        v-if="resultViewMode === 'table' && useVirtualScroll"
        :columns="typedColumns"
        :rows="sortedRows"
        :sort-column="sortColumn"
        :sort-direction="sortDirection"
        @header-click="handleHeaderClick"
        @copy-column="copyColumn"
        @cell-click="onCellClick"
      />

      <div v-else-if="resultViewMode === 'table'" class="overflow-auto flex-1 min-h-0">
        <table class="min-w-full divide-y divide-gray-200 border-separate" style="border-spacing: 0">
          <thead class="bg-gray-50 sticky top-0 z-10">
            <tr>
              <th
                v-for="(c, ci) in result.columns"
                :key="c.name"
                :class="[cellPad, 'text-left text-xs font-bold text-gray-500 border-b border-gray-200 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none']"
                @click="handleHeaderClick(c.name)"
                @contextmenu.prevent="copyColumn(ci)"
                title="右键复制整列"
              >
                {{ c.name }}
                <span v-if="sortColumn === c.name" class="ml-1 text-blue-500">{{ sortDirection === 'asc' ? '↑' : '↓' }}</span>
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="(r, i) in sortedRows" :key="i" class="hover:bg-gray-50 transition-colors">
              <td v-for="(v, j) in r" :key="j" :class="[cellPad, 'text-sm text-gray-600 font-mono border-b border-gray-100 whitespace-nowrap max-w-xs']">
                <button v-if="isJsonLike(v)" class="text-blue-600 hover:underline text-left" @click="expandedCell = { row: i, col: j, value: formatCell(v) }">{{ formatCellDisplay(v) }}</button>
                <span v-else>{{ formatCellDisplay(v) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <LabQuickChart v-else-if="resultViewMode === 'chart'" :columns="typedColumns" :rows="sortedRows" />
      <LabResultPivot v-else-if="resultViewMode === 'pivot'" :columns="typedColumns" :rows="sortedRows" />
      <LabResultStats v-else-if="resultViewMode === 'stats'" :columns="typedColumns" :rows="sortedRows" />

      <div v-else-if="resultViewMode === 'text'" class="h-full flex flex-col overflow-auto">
        <div class="flex justify-end px-4 py-2 border-b border-gray-100 bg-gray-50/50">
          <button type="button" class="text-[11px] text-blue-600 hover:text-blue-800 font-medium" @click="copyTextOutput">复制文本</button>
        </div>
        <pre class="flex-1 p-4 text-xs leading-relaxed text-gray-700 font-mono whitespace-pre overflow-auto custom-scrollbar">{{ textOutput }}</pre>
      </div>

      <div v-else class="overflow-auto flex-1 min-h-0">
        <table class="min-w-full divide-y divide-gray-200 border-separate" style="border-spacing: 0">
          <thead class="bg-gray-50 sticky top-0 z-10">
            <tr>
              <th
                v-for="(header, idx) in transposedTable.headers"
                :key="header"
                class="px-4 py-3 text-left text-xs font-bold border-b border-gray-200 uppercase tracking-wider select-none"
                :class="idx === 0 ? 'text-gray-700 bg-gray-100' : 'text-gray-500'"
              >{{ header }}</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="(row, i) in transposedTable.rows" :key="i" class="hover:bg-gray-50 transition-colors">
              <td
                v-for="(cell, j) in row"
                :key="j"
                class="px-4 py-2.5 text-sm font-mono border-b border-gray-100"
                :class="j === 0 ? 'text-gray-800 font-semibold bg-gray-50/50 whitespace-nowrap' : 'text-gray-600 whitespace-nowrap'"
              >{{ cell }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else class="h-48 flex flex-col items-center justify-center text-gray-400 text-sm">
      {{ emptyText }}
    </div>

    <div
      v-if="result && effectiveTotal != null && totalPages > 1"
      class="border-t px-4 py-2 flex items-center justify-center gap-3 text-xs bg-gray-50 shrink-0"
    >
      <button :disabled="currentPage <= 1" class="px-3 py-1 border rounded disabled:opacity-40" @click="emit('page-change', Math.max(0, (previewOffset || 0) - (effectiveLimit || 100)))">上一页</button>
      <span class="text-gray-500">第 {{ currentPage }} / {{ totalPages }} 页</span>
      <button :disabled="currentPage >= totalPages" class="px-3 py-1 border rounded disabled:opacity-40" @click="emit('page-change', (previewOffset || 0) + (effectiveLimit || 100))">下一页</button>
    </div>

    <div v-if="expandedCell" class="fixed inset-0 z-[140] flex items-center justify-center p-4 bg-gray-900/60" @click.self="expandedCell = null">
      <div class="bg-white rounded-xl max-w-2xl w-full max-h-[70vh] flex flex-col shadow-2xl">
        <div class="px-4 py-3 border-b flex justify-between items-center">
          <span class="text-sm font-bold">字段详情</span>
          <button type="button" @click="expandedCell = null"><XMarkIcon class="w-5 h-5 text-gray-400" /></button>
        </div>
        <pre class="p-4 overflow-auto text-xs font-mono flex-1 custom-scrollbar">{{ expandedCell.value }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 6px; }
</style>
