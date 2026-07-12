<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import axios from '@/utils/axios'
import { useToast } from '@/composables/useToast'
import { BookmarkIcon, TrashIcon, PencilIcon, XMarkIcon } from '@heroicons/vue/24/outline'

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
const saveTags = ref('')
const saveShared = ref(false)
const editingId = ref<number | null>(null)
const editName = ref('')
const editTags = ref('')
const editShared = ref(false)

const parseTags = (raw: string) =>
  raw.split(/[,，]/).map(t => t.trim()).filter(Boolean)

const formatTags = (tags: string[] | null | undefined) =>
  (tags || []).join(', ')

const editingQuery = computed(() =>
  editingId.value != null ? queries.value.find(q => q.id === editingId.value) : null
)

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
      tags: parseTags(saveTags.value),
      is_shared: saveShared.value,
    })
    showToast('查询已保存', 'success')
    saveName.value = ''
    saveTags.value = ''
    saveShared.value = false
    await fetchQueries()
  } catch {
    showToast('保存失败', 'error')
  }
}

const startEdit = (q: any) => {
  editingId.value = q.id
  editName.value = q.name
  editTags.value = formatTags(q.tags)
  editShared.value = !!q.is_shared
}

const cancelEdit = () => {
  editingId.value = null
}

const saveEdit = async () => {
  if (!editingQuery.value || !editName.value.trim()) return
  const q = editingQuery.value
  try {
    await axios.put(`/api/portal/lab/saved-queries/${q.id}`, {
      name: editName.value.trim(),
      sql: q.sql_text,
      source_id: q.source_id,
      lab_mode: q.lab_mode,
      test_params: q.test_params || {},
      tags: parseTags(editTags.value),
      is_shared: editShared.value,
    })
    showToast('已更新', 'success')
    editingId.value = null
    await fetchQueries()
  } catch {
    showToast('更新失败', 'error')
  }
}

const remove = async (id: number) => {
  try {
    await axios.delete(`/api/portal/lab/saved-queries/${id}`)
    queries.value = queries.value.filter(q => q.id !== id)
    if (editingId.value === id) editingId.value = null
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
        <button class="text-gray-400 hover:text-gray-600" @click="emit('close')">
          <XMarkIcon class="w-5 h-5" />
        </button>
      </div>

      <div class="p-4 border-b bg-gray-50 space-y-2">
        <div class="flex gap-2">
          <input v-model="saveName" placeholder="为当前 SQL 命名..." class="flex-1 px-3 py-2 text-sm border rounded-lg" />
          <button class="px-4 py-2 bg-blue-600 text-white text-sm font-bold rounded-lg shrink-0" :disabled="!saveName.trim()" @click="saveCurrent">保存</button>
        </div>
        <div class="flex items-center gap-3 text-xs">
          <input v-model="saveTags" placeholder="标签，逗号分隔" class="flex-1 px-2 py-1.5 border rounded-lg" />
          <label class="flex items-center gap-1.5 text-gray-600 whitespace-nowrap cursor-pointer">
            <input v-model="saveShared" type="checkbox" class="rounded" />
            团队共享
          </label>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto p-2 custom-scrollbar">
        <div v-if="loading" class="text-center py-8 text-gray-400 text-sm">加载中...</div>
        <div v-else-if="!queries.length" class="text-center py-8 text-gray-400 text-sm">暂无保存的查询</div>

        <div
          v-for="q in queries"
          :key="q.id"
          class="p-3 m-2 rounded-xl border group"
          :class="editingId === q.id ? 'border-blue-300 bg-blue-50/20' : 'hover:border-blue-200 hover:bg-blue-50/30 cursor-pointer'"
          @click="editingId === q.id ? undefined : emit('load', q)"
        >
          <template v-if="editingId === q.id">
            <div class="space-y-2" @click.stop>
              <input v-model="editName" class="w-full px-2 py-1.5 text-sm border rounded-lg font-bold" />
              <input v-model="editTags" placeholder="标签，逗号分隔" class="w-full px-2 py-1.5 text-xs border rounded-lg" />
              <label class="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
                <input v-model="editShared" type="checkbox" class="rounded" />
                团队共享
              </label>
              <div class="flex gap-2 justify-end">
                <button class="px-3 py-1 text-xs border rounded-lg" @click="cancelEdit">取消</button>
                <button class="px-3 py-1 text-xs bg-blue-600 text-white rounded-lg font-bold" @click="saveEdit">保存</button>
              </div>
            </div>
          </template>
          <template v-else>
            <div class="flex justify-between items-start gap-2">
              <div class="min-w-0 flex-1">
                <div class="font-bold text-sm text-gray-800 truncate">{{ q.name }}</div>
                <code class="text-[10px] text-gray-500 line-clamp-2 font-mono">{{ q.sql_text }}</code>
                <div class="flex flex-wrap items-center gap-1.5 mt-1">
                  <span class="text-[9px] text-gray-400">{{ q.is_shared ? '团队共享' : '仅自己' }} · {{ q.lab_mode }}</span>
                  <span
                    v-for="tag in (q.tags || [])"
                    :key="tag"
                    class="text-[9px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded"
                  >{{ tag }}</span>
                </div>
              </div>
              <div class="flex gap-0.5 opacity-0 group-hover:opacity-100 shrink-0">
                <button class="p-1 text-gray-300 hover:text-blue-600" title="编辑" @click.stop="startEdit(q)">
                  <PencilIcon class="w-4 h-4" />
                </button>
                <button class="p-1 text-gray-300 hover:text-red-500" title="删除" @click.stop="remove(q.id)">
                  <TrashIcon class="w-4 h-4" />
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
