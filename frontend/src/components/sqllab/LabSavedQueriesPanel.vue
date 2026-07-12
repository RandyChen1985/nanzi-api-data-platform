<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import axios from '@/utils/axios'
import { useToast } from '@/composables/useToast'
import { BookmarkIcon, TrashIcon } from '@heroicons/vue/24/outline'

const props = defineProps<{
  sourceId: number | null
  labMode: string
  currentSql: string
  testParams: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'load', item: any): void
  (e: 'close'): void
}>()

const { showToast } = useToast()
const queries = ref<any[]>([])
const loading = ref(false)
const saveName = ref('')

const fetchQueries = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/portal/lab/saved-queries', {
      params: props.sourceId ? { source_id: props.sourceId } : {},
    })
    queries.value = res.data
  } catch {
    showToast('加载保存的查询失败', 'error')
  } finally {
    loading.value = false
  }
}

const saveCurrent = async () => {
  if (!saveName.value.trim() || !props.sourceId) return
  try {
    await axios.post('/api/portal/lab/saved-queries', {
      name: saveName.value.trim(),
      sql: props.currentSql,
      source_id: props.sourceId,
      lab_mode: props.labMode,
      test_params: props.testParams,
    })
    showToast('查询已保存', 'success')
    saveName.value = ''
    await fetchQueries()
  } catch {
    showToast('保存失败', 'error')
  }
}

const remove = async (id: number) => {
  try {
    await axios.delete(`/api/portal/lab/saved-queries/${id}`)
    queries.value = queries.value.filter(q => q.id !== id)
    showToast('已删除', 'info')
  } catch {
    showToast('删除失败', 'error')
  }
}

onMounted(fetchQueries)
watch(() => props.sourceId, fetchQueries)
</script>

<template>
  <div class="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col">
      <div class="px-6 py-4 border-b flex justify-between items-center">
        <div class="flex items-center gap-2">
          <BookmarkIcon class="w-5 h-5 text-blue-600" />
          <h3 class="font-bold text-gray-800">我的查询</h3>
        </div>
        <button class="text-gray-400 hover:text-gray-600" @click="emit('close')">✕</button>
      </div>

      <div class="p-4 border-b bg-gray-50 flex gap-2">
        <input v-model="saveName" placeholder="为当前 SQL 命名..." class="flex-1 px-3 py-2 text-sm border rounded-lg" />
        <button class="px-4 py-2 bg-blue-600 text-white text-sm font-bold rounded-lg" :disabled="!saveName.trim()" @click="saveCurrent">保存</button>
      </div>

      <div class="flex-1 overflow-y-auto p-2 custom-scrollbar">
        <div v-if="loading" class="text-center py-8 text-gray-400 text-sm">加载中...</div>
        <div v-else-if="!queries.length" class="text-center py-8 text-gray-400 text-sm">暂无保存的查询</div>
        <div
          v-for="q in queries"
          :key="q.id"
          class="p-3 m-2 rounded-xl border hover:border-blue-200 hover:bg-blue-50/30 cursor-pointer group flex justify-between items-start gap-2"
          @click="emit('load', q)"
        >
          <div class="min-w-0 flex-1">
            <div class="font-bold text-sm text-gray-800 truncate">{{ q.name }}</div>
            <code class="text-[10px] text-gray-500 line-clamp-2 font-mono">{{ q.sql_text }}</code>
            <div class="text-[9px] text-gray-400 mt-1">{{ q.is_shared ? '团队共享' : '仅自己' }} · {{ q.lab_mode }}</div>
          </div>
          <button class="p-1 text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100" @click.stop="remove(q.id)">
            <TrashIcon class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
