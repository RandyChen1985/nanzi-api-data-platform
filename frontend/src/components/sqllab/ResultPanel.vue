<script setup lang="ts">
import { ref } from 'vue'
import { SparklesIcon, CommandLineIcon } from '@heroicons/vue/24/outline'
import MarkdownIt from 'markdown-it'
import Tooltip from '../common/Tooltip.vue'
import LabResultDataView from './LabResultDataView.vue'
import LabAiFeedbackBar from './LabAiFeedbackBar.vue'
import LabAiDebugPanel, { type AiLogEntry } from './LabAiDebugPanel.vue'
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
  total_count?: number
  offset?: number
  limit?: number
  risk_warnings?: { level: string; code: string; message: string }[]
}

const props = defineProps<{
  activeSubTab: 'result' | 'ai' | 'explain' | 'debug'
  result: PreviewResult | null
  explainResult: PreviewResult | null
  error: string | null
  executing: boolean
  aiLoading: boolean
  aiContent: string
  optimizedSql: string
  labMode?: 'api' | 'analyst'
  hasPerm: (code: string) => boolean
  isAiEnabled: boolean
  isAdmin?: boolean
  sql?: string
  recalledContext?: any[]
  previewLimit?: number
  previewOffset?: number
  totalCount?: number | null
  compareSnapshot?: PreviewResult | null
  lastAiPrompt?: string
  aiFeedbackRating?: number | null
  aiLogs?: AiLogEntry[]
}>()

const emit = defineEmits<{
  (e: 'update:activeSubTab', tab: 'result' | 'ai' | 'explain' | 'debug'): void
  (e: 'clear-result'): void
  (e: 'apply-ai-fix'): void
  (e: 'open-analysis'): void
  (e: 'export-excel'): void
  (e: 'export-async'): void
  (e: 'ai-fix-error'): void
  (e: 'page-change', offset: number): void
  (e: 'pin-baseline'): void
  (e: 'ai-feedback', rating: 1 | 2): void
  (e: 'clear-ai-logs'): void
}>()

const resultArea = ref<HTMLElement | null>(null)
const scrollToTop = () => { resultArea.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }

const formatCell = (value: unknown) => (value === null || value === undefined ? 'NULL' : String(value))

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
        <button v-if="explainResult" @click="emit('update:activeSubTab', 'explain')" 
          class="px-8 py-3 text-sm font-semibold transition-all" 
          :class="activeSubTab==='explain' ? 'text-amber-600 border-b-2 border-amber-600 bg-white' : 'text-gray-500 hover:text-gray-700'">执行计划</button>
        <button
          v-if="isAdmin"
          @click="emit('update:activeSubTab', 'debug')"
          class="px-8 py-3 text-sm font-semibold transition-all relative"
          :class="activeSubTab==='debug' ? 'text-gray-800 border-b-2 border-gray-700 bg-white' : 'text-gray-500 hover:text-gray-700'"
        >
          <span class="inline-flex items-center gap-1.5">
            <CommandLineIcon class="w-4 h-4" /> 调试日志
            <span v-if="aiLogs?.length" class="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
          </span>
        </button>
      </div>

      <div v-if="activeSubTab === 'result'" class="flex items-center gap-2">
        <LabAiFeedbackBar
          v-if="lastAiPrompt && hasPerm('element:lab:generate')"
          :prompt="lastAiPrompt"
          :rating="aiFeedbackRating ?? null"
          compact
          :class="result ? 'mr-2 pr-2 border-r border-gray-200' : ''"
          @rate="(r) => emit('ai-feedback', r)"
        />
        <template v-if="result">
        <Tooltip text="将当前结果设为对比基准" position="bottom" align="end">
          <button @click="emit('pin-baseline')" class="flex items-center px-3 py-1.5 bg-violet-50 text-violet-700 rounded-lg text-xs font-bold border border-violet-100 hover:bg-violet-100">
            固定基准
          </button>
        </Tooltip>
        <Tooltip text="基于当前结果集进行深度 AI 数据洞察" position="bottom" align="end">
          <button v-if="labMode === 'analyst' && isAiEnabled && hasPerm('element:lab:analysis')" @click="emit('open-analysis')" 
            class="flex items-center px-3 py-1.5 bg-indigo-50 text-indigo-600 rounded-lg text-xs font-bold border border-indigo-100 hover:bg-indigo-100 transition-all">
            <SparklesIcon class="w-3.5 h-3.5 mr-1.5" /> AI 智能分析
          </button>
        </Tooltip>
        <Tooltip text="将当前结果导出为 Excel 文件（预览数据）" position="bottom" align="end">
          <button v-if="labMode === 'analyst' && hasPerm('element:lab:export')" @click="emit('export-excel')" 
            class="flex items-center px-3 py-1.5 bg-green-50 text-green-600 rounded-lg text-xs font-bold border border-green-100 hover:bg-green-100 transition-all">
            <svg class="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4-4m0 0l-4 4m4-4v12" /></svg>
            导出 Excel
          </button>
        </Tooltip>
        <Tooltip text="后端异步全量导出（最多 5 万行）" position="bottom" align="end">
          <button v-if="hasPerm('element:lab:export')" @click="emit('export-async')" 
            class="flex items-center px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-lg text-xs font-bold border border-emerald-100 hover:bg-emerald-100 transition-all">
            异步导出
          </button>
        </Tooltip>
        </template>
      </div>
    </div>
    
    <div class="flex-1 min-h-0 bg-white">
      <div v-if="activeSubTab==='result'" class="h-full flex flex-col">
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
        <LabResultDataView
          v-else
          :result="result"
          :total-count="totalCount"
          :preview-limit="previewLimit"
          :preview-offset="previewOffset"
          :compare-snapshot="compareSnapshot"
          empty-text="运行查询以查看结果"
          class="flex-1 min-h-0"
          @clear="emit('clear-result')"
          @page-change="(o) => emit('page-change', o)"
          @clear-baseline="emit('pin-baseline')"
        />
      </div>

      <div v-else-if="activeSubTab === 'explain' && explainResult" class="h-full overflow-auto p-4">
        <table class="min-w-full text-xs font-mono">
          <thead class="bg-amber-50 sticky top-0"><tr>
            <th v-for="c in explainResult.columns" :key="c.name" class="px-3 py-2 text-left border-b">{{ c.name }}</th>
          </tr></thead>
          <tbody>
            <tr v-for="(row, i) in explainResult.rows" :key="i" class="hover:bg-gray-50">
              <td v-for="(cell, j) in row" :key="j" class="px-3 py-1.5 border-b whitespace-pre-wrap">{{ formatCell(cell) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <div v-else-if="activeSubTab === 'ai'" class="p-8 h-full flex flex-col">
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

      <div v-else-if="activeSubTab === 'debug'" class="h-full min-h-[400px]">
        <LabAiDebugPanel :logs="aiLogs || []" @clear="emit('clear-ai-logs')" />
      </div>
    </div>
  </div>
</template>
