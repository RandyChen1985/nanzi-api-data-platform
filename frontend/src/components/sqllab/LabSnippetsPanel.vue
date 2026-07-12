<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'

const SNIPPETS_KEY = 'sqllab_snippets_v1'

export type SqlSnippet = { id: string; name: string; sql: string; tags?: string[] }

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'insert', sql: string): void }>()

const { showToast } = useToast()
const snippets = ref<SqlSnippet[]>([])
const newName = ref('')
const newSql = ref('')

const DEFAULT_SNIPPETS: SqlSnippet[] = [
  { id: 'd1', name: 'WHERE 1=1 起始', sql: 'WHERE 1=1\n  {% if param %}\n  AND col = {{ param }}\n  {% endif %}' },
  { id: 'd2', name: '近7天日期', sql: "AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)" },
  { id: 'd3', name: '分页模板', sql: 'LIMIT {{ page_size }} OFFSET {{ offset }}' },
]

const load = () => {
  try {
    const raw = localStorage.getItem(SNIPPETS_KEY)
    snippets.value = raw ? JSON.parse(raw) : [...DEFAULT_SNIPPETS]
  } catch {
    snippets.value = [...DEFAULT_SNIPPETS]
  }
}

const save = () => {
  localStorage.setItem(SNIPPETS_KEY, JSON.stringify(snippets.value))
}

const addSnippet = () => {
  if (!newName.value.trim() || !newSql.value.trim()) return
  snippets.value.unshift({
    id: Math.random().toString(36).slice(2),
    name: newName.value.trim(),
    sql: newSql.value.trim(),
  })
  newName.value = ''
  newSql.value = ''
  save()
  showToast('片段已保存', 'success')
}

const remove = (id: string) => {
  snippets.value = snippets.value.filter(s => s.id !== id)
  save()
}

onMounted(load)
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-[130] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm" @click.self="emit('close')">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[85vh] flex flex-col">
      <div class="px-6 py-4 border-b flex justify-between items-center">
        <h3 class="font-bold text-gray-800">SQL 片段库</h3>
        <button class="text-gray-400" @click="emit('close')">✕</button>
      </div>
      <div class="p-4 border-b bg-gray-50 space-y-2">
        <input v-model="newName" placeholder="片段名称" class="w-full px-3 py-2 text-sm border rounded-lg" />
        <textarea v-model="newSql" rows="3" placeholder="SQL 片段内容..." class="w-full px-3 py-2 text-sm border rounded-lg font-mono" />
        <button class="px-4 py-2 bg-blue-600 text-white text-sm font-bold rounded-lg" @click="addSnippet">保存片段</button>
      </div>
      <div class="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
        <button
          v-for="s in snippets"
          :key="s.id"
          type="button"
          class="w-full text-left p-3 rounded-xl border hover:border-blue-300 hover:bg-blue-50/40 group"
          @click="emit('insert', s.sql); emit('close')"
        >
          <div class="flex justify-between items-start gap-2">
            <span class="font-bold text-sm text-gray-800">{{ s.name }}</span>
            <span class="text-[10px] text-red-400 opacity-0 group-hover:opacity-100" @click.stop="remove(s.id)">删除</span>
          </div>
          <code class="text-[10px] text-gray-500 line-clamp-2 font-mono mt-1 block">{{ s.sql }}</code>
        </button>
      </div>
    </div>
  </div>
</template>
