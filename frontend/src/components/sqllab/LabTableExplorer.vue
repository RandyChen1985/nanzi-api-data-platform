<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted, nextTick } from 'vue'
import axios from '@/utils/axios'
import { useToast } from '@/composables/useToast'
import {
  MagnifyingGlassIcon, XMarkIcon, TableCellsIcon, StarIcon,
  ClockIcon, TagIcon, ChevronLeftIcon, ChevronRightIcon, PlusIcon, CheckIcon, EyeIcon,
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
  is_ignored?: boolean
  is_temporary?: boolean
  confidence_reason?: string | null
}

const props = withDefaults(defineProps<{
  sourceId: number | null
  modelValue?: string[]
  recentTables?: string[]
  tableFavorites?: Record<string, TableFavoriteInfo>
  mode?: 'select' | 'browse'
  sourceName?: string
  subtitle?: string
  includeIgnored?: boolean
  allowIgnoreToggle?: boolean
  defaultScope?: 'all' | 'profiled'
}>(), {
  modelValue: () => [],
  mode: 'select',
  includeIgnored: false,
  allowIgnoreToggle: false,
  defaultScope: 'profiled',
})

const emit = defineEmits<{
  (e: 'update:modelValue', tables: string[]): void
  (e: 'close'): void
}>()

const { showToast } = useToast()

const isBrowse = computed(() => props.mode === 'browse')
const searchQ = ref('')
const scope = ref<'all' | 'profiled' | 'favorites' | 'recent'>('all')
const selectedTag = ref<string | null>(null)
const items = ref<ExplorerTableItem[]>([])
const tags = ref<{ name: string; count: number }[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 40
const SORT_OPTIONS = [
  { value: 'default', label: '默认排序' },
  { value: 'relevance', label: '相关度优先' },
  { value: 'confidence_desc', label: '置信度 ↓' },
  { value: 'confidence_asc', label: '置信度 ↑' },
  { value: 'name_asc', label: '表名 A→Z' },
  { value: 'name_desc', label: '表名 Z→A' },
  { value: 'term_asc', label: '中文术语 A→Z' },
] as const
type SortOptionValue = (typeof SORT_OPTIONS)[number]['value']

const loadSortOption = (): SortOptionValue => {
  const saved = localStorage.getItem('sqllab_table_explorer_sort') || ''
  return SORT_OPTIONS.some(o => o.value === saved) ? (saved as SortOptionValue) : 'default'
}

const sortOption = ref<SortOptionValue>(loadSortOption())

const parseSortParams = (key: SortOptionValue): { sort_by: string; sort_order: string } => {
  switch (key) {
    case 'relevance':
      return { sort_by: 'relevance', sort_order: 'desc' }
    case 'confidence_desc':
      return { sort_by: 'confidence', sort_order: 'desc' }
    case 'confidence_asc':
      return { sort_by: 'confidence', sort_order: 'asc' }
    case 'name_asc':
      return { sort_by: 'name', sort_order: 'asc' }
    case 'name_desc':
      return { sort_by: 'name', sort_order: 'desc' }
    case 'term_asc':
      return { sort_by: 'term', sort_order: 'asc' }
    default:
      return { sort_by: 'default', sort_order: 'desc' }
  }
}

const onSortChange = () => {
  localStorage.setItem('sqllab_table_explorer_sort', sortOption.value)
  page.value = 1
  fetchResults()
}
const loading = ref(false)
const tagsLoading = ref(false)
const previewTable = ref<string | null>(null)
const previewDetail = ref<any>(null)
const previewLoading = ref(false)
const expandedDataTable = ref<string | null>(null)
const dataPreviewLoading = ref(false)
const dataPreviewError = ref('')
const DATA_PREVIEW_LIMIT = 10
const dataPreviewData = ref<{ columns: { name: string }[]; rows: any[][]; total_count?: number | null } | null>(null)
const draftSelected = ref<string[]>([])
const togglingIgnore = ref<Record<string, boolean>>({})
const resultsListRef = ref<HTMLElement | null>(null)

let searchTimer: ReturnType<typeof setTimeout> | null = null

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const rowSerial = (idx: number) => (page.value - 1) * pageSize + idx + 1

const scrollResultsToTop = () => {
  nextTick(() => {
    if (resultsListRef.value) resultsListRef.value.scrollTop = 0
  })
}
const previewItem = computed(() => items.value.find(i => i.table_name === previewTable.value))

const allScopeOptions = [
  { id: 'all' as const, label: '全部表', icon: TableCellsIcon },
  { id: 'profiled' as const, label: '已摸排', icon: CheckIcon },
  { id: 'favorites' as const, label: '我的收藏', icon: StarIcon },
  { id: 'recent' as const, label: '最近使用', icon: ClockIcon },
]

const visibleScopeOptions = computed(() =>
  isBrowse.value
    ? allScopeOptions.filter(o => o.id === 'all' || o.id === 'profiled')
    : allScopeOptions,
)

const tagsUrl = computed(() =>
  isBrowse.value && props.sourceId
    ? `/api/portal/datasource/datasources/${props.sourceId}/table-profiles/tags`
    : '/api/portal/lab/table-tags',
)

const listIndentClass = computed(() => (isBrowse.value ? 'ml-4' : 'ml-9'))

const fetchTags = async () => {
  if (!props.sourceId) return
  tagsLoading.value = true
  try {
    const params = isBrowse.value ? undefined : { source_id: props.sourceId }
    const res = await axios.get(tagsUrl.value, { params })
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
    const sortParams = parseSortParams(sortOption.value)
    if (isBrowse.value) {
      const params: Record<string, any> = {
        scope: scope.value,
        page: page.value,
        page_size: pageSize,
        include_ignored: props.includeIgnored,
        sort_by: sortParams.sort_by,
        sort_order: sortParams.sort_order,
      }
      if (searchQ.value.trim()) params.q = searchQ.value.trim()
      if (selectedTag.value) params.tag = selectedTag.value
      const res = await axios.get(
        `/api/portal/datasource/datasources/${props.sourceId}/table-profiles/search`,
        { params },
      )
      items.value = res.data.items || []
      total.value = res.data.total || 0
    } else {
      const params: Record<string, any> = {
        source_id: props.sourceId,
        scope: scope.value,
        page: page.value,
        page_size: pageSize,
        sort_by: sortParams.sort_by,
        sort_order: sortParams.sort_order,
      }
      if (searchQ.value.trim()) params.q = searchQ.value.trim()
      if (selectedTag.value) params.tag = selectedTag.value
      if (scope.value === 'recent' && props.recentTables?.length) {
        params.recent = props.recentTables.join(',')
      }
      const res = await axios.get('/api/portal/lab/table-search', { params })
      items.value = res.data.items || []
      total.value = res.data.total || 0
    }

    if (expandedDataTable.value && !items.value.some(i => i.table_name === expandedDataTable.value)) {
      expandedDataTable.value = null
      dataPreviewData.value = null
      dataPreviewError.value = ''
    }
    if (previewTable.value && !items.value.some(i => i.table_name === previewTable.value)) {
      previewTable.value = items.value[0]?.table_name || null
      if (previewTable.value) loadPreviewDetail(previewTable.value)
    } else if (!previewTable.value && items.value.length) {
      previewTable.value = items.value[0]?.table_name ?? null
      if (previewTable.value) loadPreviewDetail(previewTable.value)
    }
  } catch {
    showToast('搜索表失败', 'error')
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
    scrollResultsToTop()
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

const colName = (col: string | { name: string }) => (typeof col === 'string' ? col : col.name)

const toggleDataPreview = async (tableName: string) => {
  if (expandedDataTable.value === tableName) {
    expandedDataTable.value = null
    dataPreviewData.value = null
    dataPreviewError.value = ''
    return
  }
  if (!props.sourceId) return
  expandedDataTable.value = tableName
  dataPreviewLoading.value = true
  dataPreviewError.value = ''
  dataPreviewData.value = null
  try {
    const res = await axios.post('/api/portal/lab/preview', {
      source_id: props.sourceId,
      sql: `SELECT * FROM ${tableName}`,
      params: {},
      limit: DATA_PREVIEW_LIMIT,
      include_total: true,
    })
    dataPreviewData.value = res.data
  } catch (e: any) {
    dataPreviewError.value = e.response?.data?.detail || e.response?.data?.message || e.message || '预览失败'
  } finally {
    dataPreviewLoading.value = false
  }
}

const toggleIgnore = async (item: ExplorerTableItem) => {
  if (!props.sourceId || !props.allowIgnoreToggle || togglingIgnore.value[item.table_name]) return
  const nextVal = item.is_ignored ? 0 : 1
  togglingIgnore.value[item.table_name] = true
  try {
    await axios.put(
      `/api/portal/datasource/datasources/${props.sourceId}/table-profiles/ignore`,
      { table_name: item.table_name, is_ignored: nextVal },
    )
    item.is_ignored = nextVal === 1
    showToast(`已${nextVal === 1 ? '忽略' : '启用'}表 “${item.table_name}”`, 'success')
  } catch {
    showToast('更新忽略状态失败', 'error')
  } finally {
    togglingIgnore.value[item.table_name] = false
  }
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
  draftSelected.value = [...(props.modelValue || [])]
  scope.value = isBrowse.value ? props.defaultScope : 'all'
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
  <div
    class="fixed inset-0 flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm"
    :class="isBrowse ? 'z-[9990]' : 'z-[120]'"
    @click.self="emit('close')"
  >
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-6xl h-[82vh] flex flex-col overflow-hidden">
      <!-- Header -->
      <div class="px-5 py-3.5 border-b flex items-center justify-between shrink-0 bg-gradient-to-r from-indigo-50/80 to-white">
        <div class="flex items-center gap-2.5">
          <div class="p-1.5 rounded-lg bg-indigo-600 text-white">
            <TableCellsIcon class="w-5 h-5" />
          </div>
          <div>
            <h3 class="font-bold text-gray-800 text-sm">
              {{ isBrowse ? `摸排资产浏览${sourceName ? `：${sourceName}` : ''}` : '表探索器' }}
            </h3>
            <p class="text-[10px] text-gray-500">
              {{ isBrowse ? '关键词搜索 · 标签筛选 · 字段画像 · 数据预览' : '关键词搜索 · 标签筛选 · 加入侧栏已选表' }}
            </p>
            <p v-if="isBrowse && subtitle" class="text-[10px] text-indigo-600/80 font-medium mt-0.5">{{ subtitle }}</p>
          </div>
        </div>
        <button type="button" class="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg" @click="emit('close')">
          <XMarkIcon class="w-5 h-5" />
        </button>
      </div>

      <!-- Search bar -->
      <div class="px-5 py-3 border-b shrink-0">
        <div class="flex items-center gap-2">
          <div class="relative flex-1 min-w-0">
            <MagnifyingGlassIcon class="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              v-model="searchQ"
              type="text"
              :placeholder="isBrowse ? '搜索表名 / 中文术语 / 描述 / 标签...' : '搜索表名 / 中文术语 / 描述 / 标签 / 个人备注...'"
              class="w-full pl-9 pr-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 outline-none"
              @input="scheduleSearch"
            />
          </div>
          <select
            v-model="sortOption"
            class="shrink-0 h-[42px] px-2.5 text-xs border border-gray-200 rounded-xl bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
            title="排序方式"
            @change="onSortChange"
          >
            <option v-for="opt in SORT_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>
      </div>

      <div class="flex flex-1 min-h-0">
        <!-- Left filters -->
        <div class="w-44 shrink-0 border-r bg-gray-50/80 flex flex-col overflow-y-auto custom-scrollbar">
          <div class="p-2 space-y-0.5">
            <button
              v-for="opt in visibleScopeOptions"
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

          <div ref="resultsListRef" class="flex-1 overflow-y-auto custom-scrollbar">
            <div v-if="loading" class="py-16 text-center text-gray-400 text-sm">搜索中...</div>
            <div v-else-if="!isBrowse && scope === 'recent' && !recentTables?.length" class="py-16 text-center text-gray-400 text-xs px-6">
              暂无最近使用的表<br />从探索器或侧栏选中表后会记录在这里
            </div>
            <div v-else-if="!items.length" class="py-16 text-center text-gray-400 text-xs">无匹配结果，换个关键词试试</div>

            <div
              v-for="(item, idx) in items"
              :key="item.table_name"
              class="border-b"
              :class="[
                previewTable === item.table_name ? 'bg-indigo-50/40' : '',
                item.is_ignored ? 'opacity-70' : '',
              ]"
            >
              <div
                class="px-4 py-2.5 cursor-pointer transition-colors flex items-start gap-2 group"
                :class="previewTable === item.table_name ? 'border-l-2 border-l-indigo-500' : 'hover:bg-gray-50 border-l-2 border-l-transparent'"
                @click="onRowClick(item)"
              >
                <span
                  class="shrink-0 w-8 text-right text-[10px] font-semibold text-gray-400 tabular-nums pt-1"
                  :title="`第 ${rowSerial(idx)} 条`"
                >{{ rowSerial(idx) }}</span>
                <button
                  v-if="!isBrowse"
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
                  <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0 flex-1 flex items-center gap-1.5 flex-wrap">
                      <button
                        v-if="isBrowse && allowIgnoreToggle"
                        type="button"
                        class="relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border border-transparent transition-colors duration-200"
                        :class="item.is_ignored ? 'bg-red-500' : 'bg-emerald-500'"
                        :disabled="togglingIgnore[item.table_name]"
                        :title="item.is_ignored ? '已忽略，点击恢复' : '已启用，点击忽略'"
                        @click.stop="toggleIgnore(item)"
                      >
                        <span
                          class="pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow transition duration-200"
                          :class="item.is_ignored ? 'translate-x-3' : 'translate-x-0'"
                        />
                      </button>
                      <span class="text-sm font-mono font-bold text-gray-800 break-all">{{ item.table_name }}</span>
                      <span class="text-[9px] px-1 py-0.5 rounded font-black shrink-0" :class="(item.table_type || '').toUpperCase() === 'VIEW' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'">{{ item.table_type || 'TABLE' }}</span>
                      <span v-if="item.confidence_score != null" class="text-[9px] px-1 py-0.5 rounded font-bold bg-green-100 text-green-700 shrink-0">{{ item.confidence_score }}%</span>
                      <span v-if="item.status === 3" class="text-[9px] px-1 py-0.5 rounded font-bold bg-red-100 text-red-600 shrink-0">分析失败</span>
                      <span v-if="item.is_temporary" class="text-[9px] px-1 py-0.5 rounded font-bold bg-amber-100 text-amber-800 shrink-0">临时表</span>
                      <StarSolidIcon v-if="item.is_favorite" class="w-3.5 h-3.5 text-amber-500 shrink-0" />
                    </div>
                    <button
                      type="button"
                      class="shrink-0 flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-semibold border transition-colors"
                      :class="expandedDataTable === item.table_name
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-white text-gray-500 border-gray-200 opacity-0 group-hover:opacity-100 hover:border-indigo-300 hover:text-indigo-600'"
                      :title="expandedDataTable === item.table_name ? '收起数据预览' : `预览前 ${DATA_PREVIEW_LIMIT} 条并统计总行数`"
                      @click.stop="toggleDataPreview(item.table_name)"
                    >
                      <EyeIcon class="w-3.5 h-3.5" />
                      预览数据
                    </button>
                  </div>
                  <div v-if="item.ai_term" class="text-xs text-indigo-600 font-semibold mt-0.5 break-words">{{ item.ai_term }}</div>
                  <div v-if="item.ai_description" class="text-[11px] text-gray-500 mt-0.5 break-words leading-relaxed">{{ item.ai_description }}</div>
                  <div v-if="item.confidence_reason && isBrowse" class="text-[10px] text-gray-400 mt-0.5 break-words">原因：{{ item.confidence_reason }}</div>
                  <div v-if="item.favorite_note && !isBrowse" class="text-[11px] text-blue-600 mt-0.5 break-words">📝 {{ item.favorite_note }}</div>
                </div>
              </div>

              <div
                v-if="expandedDataTable === item.table_name"
                :class="['px-4 pb-3 mr-4', listIndentClass]"
                @click.stop
              >
                <div v-if="dataPreviewLoading" class="py-4 text-center text-gray-400 text-xs">
                  <div class="inline-block w-4 h-4 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mr-2 align-middle" />
                  正在加载数据...
                </div>
                <div v-else-if="dataPreviewError" class="py-2 px-3 bg-red-50 border border-red-100 rounded-lg text-red-600 text-[11px]">
                  {{ dataPreviewError }}
                </div>
                <div v-else-if="dataPreviewData" class="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                  <div class="px-3 py-1.5 border-b bg-gray-50 flex items-center justify-between">
                    <span class="text-[10px] font-bold text-gray-400">数据预览 (最多 {{ DATA_PREVIEW_LIMIT }} 行)</span>
                    <span class="text-[10px] text-gray-500 font-medium tabular-nums">
                      <template v-if="dataPreviewData.total_count != null">
                        {{ dataPreviewData.rows?.length || 0 }}/{{ dataPreviewData.total_count }} 条
                      </template>
                      <template v-else>
                        {{ dataPreviewData.rows?.length || 0 }} 行
                      </template>
                    </span>
                  </div>
                  <div class="overflow-x-auto custom-scrollbar max-h-48">
                    <table class="min-w-full divide-y divide-gray-100">
                      <thead class="bg-gray-50 sticky top-0">
                        <tr>
                          <th
                            v-for="col in dataPreviewData.columns"
                            :key="colName(col)"
                            class="px-2 py-1.5 text-left text-[9px] font-bold text-gray-400 uppercase whitespace-nowrap"
                          >{{ colName(col) }}</th>
                        </tr>
                      </thead>
                      <tbody class="divide-y divide-gray-50">
                        <tr v-for="(row, rIdx) in dataPreviewData.rows" :key="rIdx" class="hover:bg-gray-50/80">
                          <td
                            v-for="(cell, cIdx) in row"
                            :key="cIdx"
                            class="px-2 py-1 text-[10px] text-gray-600 whitespace-nowrap max-w-[160px] truncate"
                            :title="cell === null || cell === undefined ? 'NULL' : String(cell)"
                          >{{ cell === null || cell === undefined ? 'NULL' : cell }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-if="!dataPreviewData.rows?.length" class="py-6 text-center text-gray-400 text-[11px] italic">表中暂无数据</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Preview panel -->
        <div class="shrink-0 border-l bg-gray-50/50 flex flex-col overflow-hidden" :class="isBrowse ? 'w-80' : 'w-72'">
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
              <div class="text-[10px] font-bold text-gray-400 mb-1">字段画像 ({{ previewDetail.columns_profile.length }})</div>
              <div v-if="isBrowse" class="border border-gray-100 rounded-lg overflow-hidden">
                <table class="w-full text-left text-[10px]">
                  <thead class="bg-gray-50 text-gray-400">
                    <tr>
                      <th class="px-2 py-1 font-bold">字段</th>
                      <th class="px-2 py-1 font-bold">术语</th>
                      <th class="px-2 py-1 font-bold">说明</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-50">
                    <tr v-for="col in previewDetail.columns_profile" :key="col.name || col.column_name">
                      <td class="px-2 py-1 font-mono text-gray-700">{{ col.name || col.column_name }}</td>
                      <td class="px-2 py-1 text-indigo-600">{{ col.term || '-' }}</td>
                      <td class="px-2 py-1 text-gray-500">{{ col.desc || '-' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <template v-else>
                <div
                  v-for="col in previewDetail.columns_profile.slice(0, 25)"
                  :key="col.name || col.column_name"
                  class="text-[10px] py-0.5 border-b border-gray-100 last:border-0"
                >
                  <span class="font-mono text-gray-700">{{ col.name || col.column_name }}</span>
                  <span v-if="col.term" class="text-indigo-500 ml-1">{{ col.term }}</span>
                </div>
                <div v-if="previewDetail.columns_profile.length > 25" class="text-[10px] text-gray-400 mt-1">还有 {{ previewDetail.columns_profile.length - 25 }} 个字段...</div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div v-if="isBrowse" class="px-5 py-3 border-t bg-white shrink-0 flex justify-end">
        <button type="button" class="px-5 py-2 text-sm font-bold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm" @click="emit('close')">关闭</button>
      </div>
      <div v-else class="px-5 py-3 border-t bg-white shrink-0 flex items-center gap-3">
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
