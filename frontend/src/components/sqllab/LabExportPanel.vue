<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import axios from '@/utils/axios'
import { useToast } from '@/composables/useToast'
import { ArrowDownTrayIcon, XMarkIcon } from '@heroicons/vue/24/outline'

const props = defineProps<{
  sourceId: number | null
  sql: string
  testParams: Record<string, any>
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const { showToast } = useToast()
const format = ref<'csv' | 'xlsx'>('csv')
const submitting = ref(false)
const jobs = ref<any[]>([])
const loading = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const STATUS_LABEL: Record<number, string> = {
  0: '排队中',
  1: '处理中',
  2: '已完成',
  3: '失败',
}

const fetchJobs = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/portal/lab/export')
    jobs.value = res.data
  } catch {
    showToast('加载导出任务失败', 'error')
  } finally {
    loading.value = false
  }
}

const downloadJob = async (job: { id: number; format: string }) => {
  try {
    const res = await axios.get(`/api/portal/lab/export/${job.id}/download`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.download = `lab_export_${job.id}.${job.format || 'csv'}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    showToast('下载已开始', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '下载失败，文件可能已过期', 'error')
  }
}

const startExport = async () => {
  if (!props.sourceId || !props.sql.trim()) return
  submitting.value = true
  try {
    const res = await axios.post('/api/portal/lab/export', {
      source_id: props.sourceId,
      sql: props.sql,
      params: props.testParams,
      format: format.value,
    })
    showToast(`导出任务 #${res.data.job_id} 已创建`, 'success')
    await fetchJobs()
  } catch {
    showToast('创建导出任务失败', 'error')
  } finally {
    submitting.value = false
  }
}

const pollPending = () => {
  const hasPending = jobs.value.some(j => j.status === 0 || j.status === 1)
  if (hasPending) fetchJobs()
}

onMounted(() => {
  fetchJobs()
  pollTimer = setInterval(pollPending, 3000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col">
      <div class="px-6 py-4 border-b flex justify-between items-center">
        <div class="flex items-center gap-2">
          <ArrowDownTrayIcon class="w-5 h-5 text-emerald-600" />
          <h3 class="font-bold text-gray-800">异步导出</h3>
        </div>
        <button class="text-gray-400 hover:text-gray-600" @click="emit('close')">
          <XMarkIcon class="w-5 h-5" />
        </button>
      </div>

      <div class="p-4 border-b bg-gray-50 space-y-3">
        <p class="text-xs text-gray-500">后端全量导出（最多 5 万行），支持 CSV / Excel 格式。</p>
        <div class="flex items-center gap-3">
          <label class="text-sm font-medium text-gray-700">格式</label>
          <select v-model="format" class="px-3 py-1.5 text-sm border rounded-lg">
            <option value="csv">CSV</option>
            <option value="xlsx">Excel (.xlsx)</option>
          </select>
          <button
            class="ml-auto px-4 py-2 bg-emerald-600 text-white text-sm font-bold rounded-lg disabled:opacity-50"
            :disabled="submitting || !sourceId"
            @click="startExport"
          >
            {{ submitting ? '提交中...' : '开始导出' }}
          </button>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto p-2 custom-scrollbar">
        <div v-if="loading && !jobs.length" class="text-center py-8 text-gray-400 text-sm">加载中...</div>
        <div v-else-if="!jobs.length" class="text-center py-8 text-gray-400 text-sm">暂无导出记录</div>
        <div
          v-for="job in jobs"
          :key="job.id"
          class="p-3 m-2 rounded-xl border flex justify-between items-center gap-2"
          :class="job.status === 3 ? 'border-red-100 bg-red-50/30' : 'hover:border-emerald-200'"
        >
          <div class="min-w-0 flex-1">
            <div class="font-bold text-sm text-gray-800">#{{ job.id }} · {{ job.format?.toUpperCase() }}</div>
            <div class="text-[10px] text-gray-500 mt-0.5">
              {{ STATUS_LABEL[job.status] ?? '未知' }}
              <span v-if="job.row_count"> · {{ job.row_count }} 行</span>
              · {{ job.created_at }}
            </div>
            <p v-if="job.status === 3 && job.error_message" class="text-[10px] text-red-600 mt-1 truncate">
              {{ job.error_message }}
            </p>
          </div>
          <button
            v-if="job.status === 2"
            class="px-3 py-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg hover:bg-emerald-100 shrink-0"
            @click="downloadJob(job)"
          >
            下载
          </button>
          <span v-else-if="job.status === 1" class="text-[10px] text-amber-600 font-bold shrink-0 animate-pulse">处理中...</span>
        </div>
      </div>
    </div>
  </div>
</template>
