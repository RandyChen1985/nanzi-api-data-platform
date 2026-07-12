<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import axios from '@/utils/axios'
import { useToast } from '@/composables/useToast'
import {
  MagnifyingGlassIcon, XMarkIcon, TableCellsIcon, StarIcon,
  ClockIcon, TagIcon, ChevronLeftIcon, ChevronRightIcon, PlusIcon, CheckIcon,
} from '@heroicons/vue/24/outline'
import { StarIcon as StarSolidIcon } from '@heroicons/vue/24/solid'
import type { TableFavoriteInfo } from './TableFavoriteActions.vue'

export type ExplorerTableItem = {
  table_name: string
  table_type: string
  ai_term?: string | null
  ai_description?: string | null
  ai_tags?: string[]
  status?: number
  confidence_score?: number
  is_favorite?: boolean
  is_pinned?: boolean
  favorite_note?: string | null
}

const props = defineProps<{
  sourceId: number | null
  modelValue: string[]
  recentTables?: string[]
  tableFavorites?: Record<string, TableFavoriteInfo>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', tables: string[]): void
  (e: 'close'): void
  (e: 'table-preview', tableName: string): void
}>()

const { showToast } = useToast()

const searchQ = ref('')
const scope = ref<'all' | 'profiled' | 'favorites' | 'recent'>('all')
const selectedTag = ref<string | null>(null)
const items = ref<ExplorerTableItem[]>([])
const tags = ref<{ name: string; count: number }[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 40
const loading = ref(false)
const tagsLoading = ref(false)
const previewTable = ref<string | null>(null)
const previewDetail = ref<any>(null)
const previewLoading = ref(false)
const draftSelected = ref<string[]>([])

let searchTimer: ReturnType<typeof setTimeout> | null = null

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const previewItem = computed(() => items.value.find(i => i.table_name === previewTable.value))

const scopeOptions = [
  { id: 'all' as const, label: '全部表', icon: TableCellsIcon },
  { id: 'profiled' as const, label: '已摸排', icon: CheckIcon },
  { id: 'favorites' as const, label: '我的收藏', icon: StarIcon },
  { id: 'recent' as const, label: '最近使用', icon: ClockIcon },
]

const fetchTags = async () => {
  if (!props.sourceId) return
  tagsLoading.value = true
  try {
    const res = await axios.get('/api/portal/lab/table-tags', { params: { source_id: props.sourceId } })
    tags.value = Array.isArray(res.data) ? res.data : []
  } catch {
    tags.value = []
  } finally {
    tagsLoading.value = false
  }
}

const fetchResults = async () => {
  if (!props.sourceId) return
  loading.value = true
  try {
    const params: Record<string, any> = {
      source_id: props.sourceId,
      scope: scope.value,
      page: page.value,
      page_size: pageSize,
    }
    if (searchQ.value.trim()) params.q = searchQ.value.trim()
    if (selectedTag.value) params.tag = selectedTag.value
    if (scope.value === 'recent' && props.recentTables?.length) {
      params.recent = props.recentTables.join(',')
    }
    const res = await axios.get('/api/portal/lab/table-search', { params })
    items.value = res.data.items || []
    total.value = res.data.total || 0
    if (previewTable.value && !items.value.some(i => i.table_name === previewTable.value)) {
      previewTable.value = items.value[0]?.table_name || null
    } else if (!previewTable.value && items.value.length) {
      previewTable.value = items.value[0]?.table_name ?? null
    }
  } catch {
    showToast('搜索表失败', 'error')
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const scheduleSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchResults()
  }, 300)
}

const selectScope = (s: typeof scope.value) => {
  scope.value = s
  selectedTag.value = null
  page.value = 1
  fetchResults()
}

const selectTag = (tag: string | null) => {
  selectedTag.value = selectedTag.value === tag ? null : tag
  page.value = 1
  fetchResults()
}

const isInDraft = (name: string) => draftSelected.value.includes(name)

const toggleDraft = (name: string) => {
  if (isInDraft(name)) {
    draftSelected.value = draftSelected.value.filter(t => t !== name)
  } else {
    draftSelected.value = [...draftSelected.value, name]
  }
}

const loadPreviewDetail = async (tableName: string) => {
  if (!props.sourceId) return
  previewLoading.value = true
  previewDetail.value = null
  try {
    const res = await axios.get(
      `/api/portal/datasource/datasources/${props.sourceId}/table-profiles/${encodeURIComponent(tableName)}`
    )
    previewDetail.value = res.data
  } catch {
    previewDetail.value = null
  } finally {
    previewLoading.value = false
  }
}

const onRowClick = (item: ExplorerTableItem) => {
  previewTable.value = item.table_name
  loadPreviewDetail(item.table_name)
}

const confirmSelection = () => {
  emit('update:modelValue', [...draftSelected.value])
  emit('close')
}

const clearDraftSelection = () => {
  draftSelected.value = []
}

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => {
  draftSelected.value = [...props.modelValue]
  fetchTags()
  fetchResults()
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
  document.removeEventListener('keydown', onKeydown)
})

watch(() => props.sourceId, () => {
  page.value = 1
  fetchTags()
  fetchResults()
})

watch(page, fetchResults)
</script>

<template>
  <div class="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm" @click.self="emit('close')">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-6xl h-[82vh] flex flex-col overflow-hidden">
      <!-- Header -->
      <div class="px-5 py-3.5 border-b flex items-center justify-between shrink-0 bg-gradient-to-r from-indigo-50/80 to-white">
        <div class="flex items-center gap-2.5">
          <div class="p-1.5 rounded-lg bg-indigo-600 text-white">
            <TableCellsIcon class="w-5 h-5" />
          </div>
          <div>
            <h3 class="font-bold text-gray-800 text-sm">表探索器</h3>
            <p class="text-[10px] text-gray-500">关键词搜索 · 标签筛选 · 加入侧栏已选表</p>
          </div>
        </div>
        <button type="button" class="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg" @click="emit('close')">
          <XMarkIcon class="w-5 h-5" />
        </button>
      </div>

      <!-- Search bar -->
      <div class="px-5 py-3 border-b shrink-0">
        <div class="relative">
          <MagnifyingGlassIcon class="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            v-model="searchQ"
            type="text"
            placeholder="搜索表名 / 中文术语 / 描述 / 标签 / 个人备注..."
            class="w-full pl-9 pr-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 outline-none"
            @input="scheduleSearch"
          />
        </div>
      </div>

      <div class="flex flex-1 min-h-0">
        <!-- Left filters -->
        <div class="w-44 shrink-0 border-r bg-gray-50/80 flex flex-col overflow-y-auto custom-scrollbar">
          <div class="p-2 space-y-0.5">
            <button
              v-for="opt in scopeOptions"
              :key="opt.id"
              type="button"
              class="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs font-semibold transition-colors"
              :class="scope === opt.id && !selectedTag ? 'bg-indigo-600 text-white' : 'text-gray-600 hover:bg-white'"
              @click="selectScope(opt.id)"
            >
              <component :is="opt.icon" class="w-3.5 h-3.5 shrink-0" />
              {{ opt.label }}
            </button>
          </div>
          <div v-if="tags.length" class="border-t mt-1 p-2">
            <div class="flex items-center gap-1 px-1 mb-1.5 text-[10px] font-bold text-gray-400 uppercase">
              <TagIcon class="w-3 h-3" /> 标签
            </div>
            <div v-if="tagsLoading" class="text-[10px] text-gray-400 px-2 py-2">加载中...</div>
            <button
              v-for="t in tags.slice(0, 30)"
              :key="t.name"
              type="button"
              class="w-full text-left px-2 py-1 rounded-md text-[11px] truncate transition-colors"
              :class="selectedTag === t.name ? 'bg-indigo-100 text-indigo-700 font-bold' : 'text-gray-600 hover:bg-white'"
              :title="`${t.name} (${t.count})`"
              @click="selectTag(t.name)"
            >
              {{ t.name }} <span class="text-gray-400">({{ t.count }})</span>
            </button>
          </div>
        </div>

        <!-- Results list -->
        <div class="flex-1 flex flex-col min-w-0">
          <div class="px-4 py-2 border-b flex items-center justify-between text-[11px] text-gray-500 shrink-0">
            <span>共 {{ total }} 张表</span>
            <div v-if="totalPages > 1" class="flex items-center gap-2">
              <button type="button" class="p-1 rounded hover:bg-gray-100 disabled:opacity-40" :disabled="page <= 1" @click="page--">
                <ChevronLeftIcon class="w-4 h-4" />
              </button>
              <span>{{ page }} / {{ totalPages }}</span>
              <button type="button" class="p-1 rounded hover:bg-gray-100 disabled:opacity-40" :disabled="page >= totalPages" @click="page++">
                <ChevronRightIcon class="w-4 h-4" />
              </button>
            </div>
          </div>

          <div class="flex-1 overflow-y-auto custom-scrollbar">
            <div v-if="loading" class="py-16 text-center text-gray-400 text-sm">搜索中...</div>
            <div v-else-if="scope === 'recent' && !recentTables?.length" class="py-16 text-center text-gray-400 text-xs px-6">
              暂无最近使用的表<br />从探索器或侧栏选中表后会记录在这里
            </div>
            <div v-else-if="!items.length" class="py-16 text-center text-gray-400 text-xs">无匹配结果，换个关键词试试</div>

            <div
              v-for="item in items"
              :key="item.table_name"
              class="px-4 py-2.5 border-b cursor-pointer transition-colors flex items-start gap-3 group"
              :class="previewTable === item.table_name ? 'bg-indigo-50/60 border-l-2 border-l-indigo-500' : 'hover:bg-gray-50 border-l-2 border-l-transparent'"
              @click="onRowClick(item)"
            >
              <button
                type="button"
                class="mt-0.5 shrink-0 w-6 h-6 rounded-md border flex items-center justify-center transition-colors"
                :class="isInDraft(item.table_name) ? 'bg-indigo-600 border-indigo-600 text-white' : 'border-gray-200 text-gray-400 hover:border-indigo-400 hover:text-indigo-600'"
                :title="isInDraft(item.table_name) ? '移出已选' : '加入已选'"
                @click.stop="toggleDraft(item.table_name)"
              >
                <CheckIcon v-if="isInDraft(item.table_name)" class="w-3.5 h-3.5" />
                <PlusIcon v-else class="w-3.5 h-3.5" />
              </button>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span class="text-sm font-mono font-bold text-gray-800">{{ item.table_name }}</span>
                  <span class="text-[9px] px-1 py-0.5 rounded font-black" :class="item.table_type === 'VIEW' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'">{{ item.table_type || 'TABLE' }}</span>
                  <span v-if="item.confidence_score != null" class="text-[9px] px-1 py-0.5 rounded font-bold bg-green-100 text-green-700">{{ item.confidence_score }}%</span>
                  <StarSolidIcon v-if="item.is_favorite" class="w-3.5 h-3.5 text-amber-500" />
                </div>
                <div v-if="item.ai_term" class="text-xs text-indigo-600 font-semibold mt-0.5 truncate">{{ item.ai_term }}</div>
                <div v-if="item.ai_description" class="text-[11px] text-gray-500 mt-0.5 line-clamp-2 leading-snug">{{ item.ai_description }}</div>
                <div v-if="item.favorite_note" class="text-[11px] text-blue-600 mt-0.5 line-clamp-1">📝 {{ item.favorite_note }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Preview panel -->
        <div class="w-72 shrink-0 border-l bg-gray-50/50 flex flex-col overflow-hidden">
          <div class="px-3 py-2 border-b text-[11px] font-bold text-gray-500 shrink-0">表预览</div>
          <div v-if="!previewTable" class="flex-1 flex items-center justify-center text-gray-400 text-xs px-4 text-center">点击左侧表查看详情</div>
          <div v-else class="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2">
            <div class="font-mono text-sm font-bold text-gray-800 break-all">{{ previewTable }}</div>
            <template v-if="previewItem">
              <div v-if="previewItem.ai_term" class="text-xs text-indigo-600 font-semibold">{{ previewItem.ai_term }}</div>
              <div v-if="previewItem.ai_description" class="text-[11px] text-gray-600 leading-relaxed">{{ previewItem.ai_description }}</div>
              <div v-if="previewItem.ai_tags?.length" class="flex flex-wrap gap-1">
                <span v-for="tg in previewItem.ai_tags" :key="tg" class="text-[9px] px-1.5 py-0.5 bg-white border rounded-full text-gray-600">{{ tg }}</span>
              </div>
            </template>
            <div v-if="previewLoading" class="text-[11px] text-gray-400 italic">加载字段...</div>
            <div v-else-if="previewDetail?.columns_profile?.length" class="mt-2">
              <div class="text-[10px] font-bold text-gray-400 mb-1">字段 ({{ previewDetail.columns_profile.length }})</div>
              <div
                v-for="col in previewDetail.columns_profile.slice(0, 25)"
                :key="col.name || col.column_name"
                class="text-[10px] py-0.5 border-b border-gray-100 last:border-0"
              >
                <span class="font-mono text-gray-700">{{ col.name || col.column_name }}</span>
                <span v-if="col.term" class="text-indigo-500 ml-1">{{ col.term }}</span>
              </div>
              <div v-if="previewDetail.columns_profile.length > 25" class="text-[10px] text-gray-400 mt-1">还有 {{ previewDetail.columns_profile.length - 25 }} 个字段...</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-5 py-3 border-t bg-white shrink-0 flex items-center gap-3">
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-2 mb-1">
            <span class="text-[10px] text-gray-400">已选 {{ draftSelected.length }} 张表（同步到侧栏勾选）</span>
            <button
              v-if="draftSelected.length"
              type="button"
              class="text-[10px] font-bold text-red-600 hover:text-red-700 hover:bg-red-50 px-2 py-0.5 rounded transition-colors shrink-0"
              @click="clearDraftSelection"
            >清空全部</button>
          </div>
          <div class="flex flex-wrap gap-1 max-h-12 overflow-y-auto custom-scrollbar">
            <span
              v-for="t in draftSelected"
              :key="t"
              class="text-[10px] px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full font-mono cursor-pointer hover:bg-indigo-200"
              @click="toggleDraft(t)"
            >{{ t }} ×</span>
            <span v-if="!draftSelected.length" class="text-[11px] text-gray-400 italic">暂未选择</span>
          </div>
        </div>
        <button type="button" class="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50" @click="emit('close')">取消</button>
        <button
          type="button"
          class="px-5 py-2 text-sm font-bold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm"
          @click="confirmSelection"
        >确认并关闭</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 6px; }
</style>
