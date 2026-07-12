<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { TableCellsIcon, ChevronRightIcon, ChevronDownIcon, CubeIcon, SparklesIcon, EyeIcon, StarIcon } from '@heroicons/vue/24/outline'
import ClearableInput from '../common/ClearableInput.vue'
import LabJoinDiagram from './LabJoinDiagram.vue'
import TableFavoriteActions, { type TableFavoriteInfo } from './TableFavoriteActions.vue'

type MergedColumn = {
  name: string
  type: string
  term?: string
  desc?: string
}

const props = defineProps<{
  tables: any[]
  loading: boolean
  modelValue: string[] // selectedTables
  collapsed: boolean
  flashTitle: boolean
  autoContext?: boolean 
  columnsCache?: Record<string, {name: string, type: string}[]>
  showAi?: boolean
  isAdmin?: boolean
  hasProfiled?: boolean
  tableProfilesMap?: Record<string, any>
  sourceId?: number | null
  joinPaths?: any[]
  tableFavorites?: Record<string, TableFavoriteInfo>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
  (e: 'update:autoContext', value: boolean): void 
  (e: 'refresh'): void
  (e: 'table-click', table: string): void
  (e: 'table-dblclick', table: string): void
  (e: 'table-profile-generate', table: string): void
  (e: 'fetch-columns', table: string): void
  (e: 'fetch-profile-detail', table: string): void
  (e: 'column-dblclick', column: string): void
  (e: 'table-ai', table: string): void
  (e: 'insert-join', snippet: string): void
  (e: 'toggle-favorite', tableName: string): void
  (e: 'toggle-pin', tableName: string): void
  (e: 'save-favorite-note', payload: { tableName: string; note: string }): void
}>()

const activeTab = ref<'tables' | 'favorites'>('tables')
const advancedMode = ref(false)

const search = ref('')
const tablesSortBy = ref<'name' | 'confidence_desc' | 'confidence_asc'>('name')
const expandedTables = ref<string[]>([])
const selectedProfileTag = ref<string | null>(null)
const showTagPicker = ref(false)
const tagSearch = ref('')
const TAGS_INLINE_LIMIT = 3

const getTableName = (t: any) => (typeof t === 'string' ? t : t.name)

const availableTags = computed(() => {
  if (!advancedMode.value || !props.tableProfilesMap) return []
  const counts: Record<string, number> = {}
  Object.values(props.tableProfilesMap).forEach((profile: any) => {
    if (profile?.is_ignored === 1) return
    if (Array.isArray(profile?.ai_tags)) {
      profile.ai_tags.forEach((tag: string) => {
        if (tag?.trim()) {
          const cleanTag = tag.trim()
          counts[cleanTag] = (counts[cleanTag] || 0) + 1
        }
      })
    }
  })
  return Object.entries(counts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})

const profiledTableCount = computed(() => {
  if (!props.tableProfilesMap) return 0
  return Object.values(props.tableProfilesMap).filter((p: any) => p?.is_ignored !== 1).length
})

const inlineTags = computed(() => availableTags.value.slice(0, TAGS_INLINE_LIMIT))

const hiddenTagCount = computed(() => Math.max(0, availableTags.value.length - TAGS_INLINE_LIMIT))

const selectedTagNotInline = computed(() => {
  if (!selectedProfileTag.value) return null
  return inlineTags.value.some(t => t.name === selectedProfileTag.value) ? null : selectedProfileTag.value
})

const filteredPickerTags = computed(() => {
  if (!tagSearch.value.trim()) return availableTags.value
  const q = tagSearch.value.trim().toLowerCase()
  return availableTags.value.filter(t => t.name.toLowerCase().includes(q))
})

const toggleProfileTag = (tag: string) => {
  selectedProfileTag.value = selectedProfileTag.value === tag ? null : tag
  showTagPicker.value = false
  tagSearch.value = ''
}

const openTagPicker = () => {
  showTagPicker.value = true
  tagSearch.value = ''
}

const closeTagPicker = () => {
  showTagPicker.value = false
  tagSearch.value = ''
}

// 摸排可用时默认开启高级模式；切换数据源时同步重置标签筛选
watch(() => props.hasProfiled, (profiled) => {
  advancedMode.value = !!profiled
  tablesSortBy.value = profiled ? 'confidence_desc' : 'name'
  selectedProfileTag.value = null
  showTagPicker.value = false
  tagSearch.value = ''
}, { immediate: true })

watch(advancedMode, (enabled) => {
  if (!enabled) {
    selectedProfileTag.value = null
    showTagPicker.value = false
    tagSearch.value = ''
  }
})

watch(showTagPicker, (open) => {
  if (!open) return
  const handler = () => {
    closeTagPicker()
    document.removeEventListener('click', handler)
  }
  setTimeout(() => document.addEventListener('click', handler), 0)
})

const getConfidenceScore = (tableName: string) =>
  props.tableProfilesMap?.[tableName]?.confidence_score ?? 0

const favoritePriority = (tableName: string) => {
  const f = props.tableFavorites?.[tableName]
  if (f?.is_pinned) return 0
  if (f) return 1
  return 2
}

const sortTableList = (list: any[]) => {
  const sorted = [...list]
  const byName = (a: any, b: any) => getTableName(a).localeCompare(getTableName(b))
  if (tablesSortBy.value === 'confidence_desc') {
    sorted.sort(
      (a, b) =>
        getConfidenceScore(getTableName(b)) - getConfidenceScore(getTableName(a)) || byName(a, b),
    )
  } else if (tablesSortBy.value === 'confidence_asc') {
    sorted.sort(
      (a, b) =>
        getConfidenceScore(getTableName(a)) - getConfidenceScore(getTableName(b)) || byName(a, b),
    )
  } else {
    sorted.sort(byName)
  }
  return sorted.sort((a, b) => {
    const pa = favoritePriority(getTableName(a))
    const pb = favoritePriority(getTableName(b))
    return pa - pb
  })
}

const filteredTables = computed(() => {
  let list = props.tables

  if (advancedMode.value) {
    if (selectedProfileTag.value) {
      list = list.filter(t => {
        const name = getTableName(t)
        const tags = props.tableProfilesMap?.[name]?.ai_tags
        return Array.isArray(tags) && tags.includes(selectedProfileTag.value!)
      })
    }
    if (search.value) {
      const query = search.value.toLowerCase()
      list = list.filter(t => {
        const name = getTableName(t)
        const profile = props.tableProfilesMap?.[name]
        return (
          name.toLowerCase().includes(query) ||
          (profile?.ai_term && profile.ai_term.toLowerCase().includes(query)) ||
          (profile?.ai_description && profile.ai_description.toLowerCase().includes(query))
        )
      })
    }
    return sortTableList(list)
  }

  if (!search.value) return sortTableList(list)
  const query = search.value.toLowerCase()
  return sortTableList(list.filter(t => getTableName(t).toLowerCase().includes(query)))
})

const handleTableDblClick = (table: string) => {
  emit('table-dblclick', table)
}

const toggleExpand = (table: string, event: Event) => {
  event.stopPropagation()
  const idx = expandedTables.value.indexOf(table)
  if (idx > -1) {
    expandedTables.value.splice(idx, 1)
  } else {
    expandedTables.value.push(table)
    if (!props.columnsCache?.[table]) {
      emit('fetch-columns', table)
    }
    if (advancedMode.value && props.sourceId && !props.tableProfilesMap?.[table]?.columns_profile) {
      emit('fetch-profile-detail', table)
    }
  }
}

const isExpanded = (table: string) => expandedTables.value.includes(table)

const getMergedColumns = (tableName: string): MergedColumn[] | null => {
  const physical = props.columnsCache?.[tableName]
  const profileCols = props.tableProfilesMap?.[tableName]?.columns_profile as
    | Array<{ name: string; term?: string; desc?: string }>
    | undefined

  if (!advancedMode.value || !profileCols?.length) {
    return physical ? physical.map(col => ({ ...col })) : null
  }

  const profileMap = Object.fromEntries(profileCols.map(c => [c.name, c]))

  if (physical) {
    return physical.map(col => ({
      name: col.name,
      type: col.type,
      term: profileMap[col.name]?.term,
      desc: profileMap[col.name]?.desc,
    }))
  }

  return profileCols.map(c => ({
    name: c.name,
    type: '',
    term: c.term,
    desc: c.desc,
  }))
}

const handleColumnDblClick = (colName: string) => {
  emit('column-dblclick', colName)
}

const handleDragStart = (event: DragEvent, name: string) => {
  if (event.dataTransfer) {
    // 使用自定义类型防止浏览器默认的 text 插入逻辑触发，从而避免重复
    event.dataTransfer.setData('application/x-sqllab-item', name)
    event.dataTransfer.dropEffect = 'copy'
  }
}

/** 紧凑展示：备注与 AI 描述各最多 1～2 行，减少单条占用高度 */
const descClampFor = (tableName: string) => {
  const hasNote = !!props.tableFavorites?.[tableName]?.note
  const hasDesc = !!props.tableProfilesMap?.[tableName]?.ai_description
  if (hasNote && hasDesc) return { note: 'line-clamp-1', desc: 'line-clamp-2' }
  if (hasNote) return { note: 'line-clamp-1', desc: '' }
  if (hasDesc) return { note: '', desc: 'line-clamp-2' }
  return { note: '', desc: '' }
}

const tableRowIndentClass = computed(() => (props.autoContext ? '' : 'pl-[1.375rem]'))

const favoriteTablesList = computed(() => {
  if (!props.tableFavorites) return []
  return Object.entries(props.tableFavorites)
    .map(([name, fav]) => ({
      name,
      ...fav,
      profile: props.tableProfilesMap?.[name],
    }))
    .sort((a, b) => {
      if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1
      return a.name.localeCompare(b.name)
    })
})

const favoriteCount = computed(() => favoriteTablesList.value.length)

const focusFavoriteTable = (tableName: string) => {
  activeTab.value = 'tables'
  if (!expandedTables.value.includes(tableName)) {
    expandedTables.value.push(tableName)
    if (!props.columnsCache?.[tableName]) emit('fetch-columns', tableName)
    if (advancedMode.value && props.sourceId && !props.tableProfilesMap?.[tableName]?.columns_profile) {
      emit('fetch-profile-detail', tableName)
    }
  }
}
</script>

<template>
  <div :class="collapsed ? 'lg:w-0 opacity-0 invisible' : 'lg:w-64 opacity-100 visible'" 
    class="bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col overflow-hidden transition-all duration-300 relative">
    <div class="h-full flex flex-col min-w-[280px]">
      <!-- Tab Switcher -->
      <div class="flex border-b bg-gray-100/50">
        <button 
          @click="activeTab = 'tables'"
          class="flex-1 py-2 text-[10px] font-black uppercase tracking-widest transition-all border-b-2"
          :class="activeTab === 'tables' ? 'bg-white border-blue-600 text-blue-600' : 'text-gray-400 border-transparent hover:text-gray-600'"
        >
          <div class="flex items-center justify-center gap-1.5">
            <TableCellsIcon class="w-3 h-3" /> 数据表
          </div>
        </button>
        <button
          @click="activeTab = 'favorites'"
          class="flex-1 py-2 text-[10px] font-black uppercase tracking-widest transition-all border-b-2 relative"
          :class="activeTab === 'favorites' ? 'bg-white border-amber-500 text-amber-600' : 'text-gray-400 border-transparent hover:text-gray-600'"
        >
          <div class="flex items-center justify-center gap-1.5">
            <StarIcon class="w-3 h-3" /> 我的收藏
            <span v-if="favoriteCount" class="text-[9px] font-bold opacity-80">({{ favoriteCount }})</span>
          </div>
        </button>
      </div>

      <template v-if="activeTab === 'tables'">
        <div class="p-3 border-b bg-gray-50 flex items-center justify-between transition-colors duration-500" :class="flashTitle ? 'bg-indigo-100' : ''">
          <div class="flex items-center gap-2">
            <!-- Checkbox only visible when autoContext is OFF -->
            <input 
              v-if="!autoContext"
              type="checkbox" 
              :checked="modelValue.length === tables.length && tables.length > 0"
              :indeterminate="modelValue.length > 0 && modelValue.length < tables.length"
              @change="(e) => {
                const checked = (e.target as HTMLInputElement).checked;
                emit('update:modelValue', checked ? tables.map(t => typeof t === 'string' ? t : t.name) : []);
              }"
              class="h-3.5 w-3.5 text-blue-600 rounded border-gray-300 focus:ring-blue-500 cursor-pointer animate-in zoom-in duration-200"
              title="全选/取消全选"
            />
            <span class="text-xs font-bold uppercase tracking-wider transition-colors duration-500" :class="flashTitle ? 'text-indigo-600' : 'text-gray-500'">库表资产</span>
            <span class="ml-0.5 px-1.5 py-0.5 bg-gray-200 text-gray-500 rounded text-[10px] font-bold">{{ filteredTables.length }}</span>
          </div>
          <div class="flex items-center gap-2">
            <!-- 高级模式胶囊开关（仅摸排完成时显示） -->
            <button
              v-if="hasProfiled"
              type="button"
              class="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border transition-all duration-200"
              :class="advancedMode
                ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                : 'bg-white text-gray-400 border-gray-200 hover:border-indigo-300 hover:text-indigo-500'"
              @click="advancedMode = !advancedMode"
              title="开启 AI 摸排高级模式"
            >
              <svg class="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>
              高级
            </button>
            <button @click="$emit('refresh')" class="text-gray-400 hover:text-blue-600">
              <svg class="w-3.5 h-3.5" :class="loading ? 'animate-spin' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            </button>
          </div>
        </div>

        <LabJoinDiagram v-if="joinPaths?.length" :join-paths="joinPaths || []" @insert="(s) => emit('insert-join', s)" />

        <div class="p-2 border-b space-y-2">
          <div class="flex gap-2">
            <ClearableInput
              v-model="search"
              wrapper-class="bg-gray-100 rounded flex-1 min-w-0"
              input-class="px-2 py-1 text-xs"
              :placeholder="advancedMode ? '搜索表名/术语/描述...' : '搜索资产...'"
            />
            <select
              v-if="hasProfiled"
              v-model="tablesSortBy"
              class="shrink-0 w-[88px] text-[10px] border border-gray-200 bg-gray-100 rounded px-1.5 py-1 text-gray-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30"
              title="排序方式"
            >
              <option value="confidence_desc">置信度↓</option>
              <option value="confidence_asc">置信度↑</option>
              <option value="name">表名</option>
            </select>
          </div>
        </div>

        <div v-if="advancedMode && availableTags.length > 0" class="relative px-2 pb-2 border-b" @click.stop>
            <div class="flex flex-wrap items-center gap-1">
              <button
                type="button"
                @click="selectedProfileTag = null"
                :class="[
                  'px-2 py-0.5 rounded-full text-[8px] font-semibold border transition-all shrink-0',
                  !selectedProfileTag
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-gray-100 border-gray-200 text-gray-500 hover:bg-gray-200'
                ]"
              >
                全部 ({{ profiledTableCount }})
              </button>

              <button
                v-for="tag in inlineTags"
                :key="tag.name"
                type="button"
                @click="toggleProfileTag(tag.name)"
                :class="[
                  'px-2 py-0.5 rounded-full text-[8px] font-semibold border transition-all max-w-[96px] truncate shrink-0',
                  selectedProfileTag === tag.name
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-gray-100 border-gray-200 text-gray-500 hover:bg-gray-200'
                ]"
                :title="`${tag.name} (${tag.count})`"
              >
                {{ tag.name }} ({{ tag.count }})
              </button>

              <button
                v-if="selectedTagNotInline"
                type="button"
                @click="toggleProfileTag(selectedTagNotInline)"
                class="px-2 py-0.5 rounded-full text-[8px] font-semibold border bg-indigo-600 text-white border-indigo-600 max-w-[96px] truncate shrink-0"
                :title="selectedTagNotInline"
              >
                {{ selectedTagNotInline }}
              </button>

              <button
                v-if="hiddenTagCount > 0"
                type="button"
                class="px-2 py-0.5 rounded-full text-[8px] font-semibold border border-dashed transition-all shrink-0"
                :class="showTagPicker
                  ? 'bg-indigo-50 text-indigo-600 border-indigo-300'
                  : 'border-gray-300 text-gray-400 hover:text-indigo-600 hover:border-indigo-300 hover:bg-indigo-50'"
                @click="showTagPicker ? closeTagPicker() : openTagPicker()"
              >
                {{ showTagPicker ? '收起' : `+${hiddenTagCount} 标签` }}
              </button>
            </div>

            <!-- 标签选择浮层 -->
            <div
              v-if="showTagPicker"
              class="absolute left-0 right-0 top-full mt-1 z-30 bg-white border border-gray-200 rounded-lg shadow-xl p-2 flex flex-col"
            >
              <div @click.stop>
                <ClearableInput
                  v-model="tagSearch"
                  input-class="px-2 py-1 text-[10px]"
                  placeholder="搜索标签..."
                />
              </div>
              <div class="mt-2 max-h-40 overflow-y-auto custom-scrollbar flex flex-wrap gap-1">
                <button
                  v-for="tag in filteredPickerTags"
                  :key="tag.name"
                  type="button"
                  @click="toggleProfileTag(tag.name)"
                  :class="[
                    'px-2 py-0.5 rounded-full text-[8px] font-semibold border transition-all max-w-full truncate',
                    selectedProfileTag === tag.name
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-gray-50 border-gray-200 text-gray-500 hover:bg-indigo-50 hover:border-indigo-200'
                  ]"
                  :title="`${tag.name} (${tag.count})`"
                >
                  {{ tag.name }} ({{ tag.count }})
                </button>
                <div v-if="filteredPickerTags.length === 0" class="w-full py-3 text-center text-[10px] text-gray-400 italic">
                  无匹配标签
                </div>
              </div>
            </div>
          </div>
        <div class="flex-1 overflow-y-auto p-1 custom-scrollbar">
          <div v-if="loading" class="p-4 text-center text-gray-400 text-xs italic">资源扫描中...</div>
          <div v-else-if="filteredTables.length === 0" class="p-4 text-center text-gray-400 text-xs">无匹配资产</div>
          
          <div v-for="t in filteredTables" :key="typeof t === 'string' ? t : t.name">
            <!-- 普通模式行 -->
            <div
              v-if="!advancedMode"
              @click="toggleExpand(typeof t === 'string' ? t : t.name, $event)" 
              @dblclick="handleTableDblClick(typeof t === 'string' ? t : t.name)"
              draggable="true"
              @dragstart="handleDragStart($event, typeof t === 'string' ? t : t.name)"
              class="px-3 py-2 text-xs text-gray-700 hover:bg-blue-50 hover:text-blue-700 rounded cursor-pointer transition-colors group relative"
              :class="[
                isExpanded(typeof t === 'string' ? t : t.name) ? 'bg-blue-50/50' : '',
                tableFavorites?.[(typeof t === 'string' ? t : t.name)] ? 'border-l-2 border-l-amber-300/80' : '',
              ]"
            >
              <div class="flex items-start justify-between gap-1">
                <div class="flex items-start overflow-hidden flex-1 min-w-0 pr-1">
                  <input 
                    v-if="!autoContext"
                    type="checkbox" 
                    :checked="modelValue.includes(typeof t === 'string' ? t : t.name)"
                    @change="(e) => {
                      const checked = (e.target as HTMLInputElement).checked;
                      const name = typeof t === 'string' ? t : t.name;
                      const newVal = checked ? [...modelValue, name] : modelValue.filter(x => x !== name);
                      emit('update:modelValue', newVal);
                    }"
                    @click.stop
                    class="mt-0.5 mr-2 h-3.5 w-3.5 text-blue-600 rounded border-gray-300 focus:ring-blue-500 shrink-0"
                  />
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-1.5 min-w-0">
                      <TableCellsIcon class="w-3 h-3 shrink-0" :class="modelValue.includes(typeof t === 'string' ? t : t.name) ? 'text-blue-500' : 'text-gray-400'" />
                      <span class="truncate font-medium" :class="modelValue.includes(typeof t === 'string' ? t : t.name) ? 'text-blue-700 font-bold' : ''" :title="typeof t === 'string' ? t : t.name">
                        {{ typeof t === 'string' ? t : t.name }}
                      </span>
                      <span v-if="typeof t !== 'string'" :class="t.type === 'VIEW' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'" class="text-[8px] px-1 py-0.5 rounded leading-none font-black shrink-0">
                        {{ t.type }}
                      </span>
                    </div>
                    <div
                      v-if="tableFavorites?.[(typeof t === 'string' ? t : t.name)]?.note"
                      class="text-[10px] text-blue-600 mt-px leading-snug pr-1 line-clamp-1"
                      :title="tableFavorites[(typeof t === 'string' ? t : t.name)]?.note || ''"
                    >📝 {{ tableFavorites[(typeof t === 'string' ? t : t.name)]?.note }}</div>
                  </div>
                </div>
                <div class="flex items-center shrink-0">
                  <button 
                    @click.stop="emit('table-click', typeof t === 'string' ? t : t.name)" 
                    class="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-all opacity-0 group-hover:opacity-100"
                    title="查看资产画像"
                  >
                    <EyeIcon class="w-3.5 h-3.5" />
                  </button>
                  <button 
                    v-if="showAi"
                    @click.stop="emit('table-ai', typeof t === 'string' ? t : t.name)" 
                    class="p-1 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded transition-all opacity-0 group-hover:opacity-100"
                    title="针对该表进行 AI 建模"
                  >
                    <SparklesIcon class="w-3.5 h-3.5" />
                  </button>
                  <component :is="isExpanded(typeof t === 'string' ? t : t.name) ? ChevronDownIcon : ChevronRightIcon" class="w-3 h-3 text-gray-400" />
                </div>
              </div>
              <TableFavoriteActions
                variant="corner"
                :table-name="typeof t === 'string' ? t : t.name"
                :favorite="tableFavorites?.[typeof t === 'string' ? t : t.name]"
                @toggle-favorite="emit('toggle-favorite', typeof t === 'string' ? t : t.name)"
                @toggle-pin="emit('toggle-pin', typeof t === 'string' ? t : t.name)"
                @save-note="(note) => emit('save-favorite-note', { tableName: typeof t === 'string' ? t : t.name, note })"
              />
            </div>

            <!-- 高级模式行：摸排信息展示 -->
            <div
              v-else
              @click="toggleExpand(typeof t === 'string' ? t : t.name, $event)"
              draggable="true"
              @dragstart="handleDragStart($event, typeof t === 'string' ? t : t.name)"
              class="px-2 py-1.5 rounded cursor-pointer transition-colors group border border-transparent relative"
              :class="[
                modelValue.includes(typeof t === 'string' ? t : t.name) ? 'border-indigo-200 bg-indigo-50/40' : 'hover:bg-blue-50/40 hover:border-blue-100',
                isExpanded(typeof t === 'string' ? t : t.name) ? 'bg-blue-50/30' : '',
                tableFavorites?.[(typeof t === 'string' ? t : t.name)]?.is_pinned ? 'border-l-2 border-l-indigo-400' : '',
                tableFavorites?.[(typeof t === 'string' ? t : t.name)] && !tableFavorites?.[(typeof t === 'string' ? t : t.name)]?.is_pinned ? 'border-l-2 border-l-amber-300/80' : '',
              ]"
            >
              <!-- 表头行：表名 + 徽章，操作按钮浮于右上 -->
              <div class="flex items-center gap-1.5 min-w-0 pr-14">
                <input
                  v-if="!autoContext"
                  type="checkbox"
                  :checked="modelValue.includes(typeof t === 'string' ? t : t.name)"
                  @change="(e) => {
                    const checked = (e.target as HTMLInputElement).checked;
                    const name = typeof t === 'string' ? t : t.name;
                    const newVal = checked ? [...modelValue, name] : modelValue.filter(x => x !== name);
                    emit('update:modelValue', newVal);
                  }"
                  @click.stop
                  class="h-3.5 w-3.5 text-blue-600 rounded border-gray-300 focus:ring-blue-500 shrink-0"
                />
                <div class="flex items-center gap-1 min-w-0 flex-1">
                  <span
                    class="text-xs font-mono font-semibold truncate"
                    :class="modelValue.includes(typeof t === 'string' ? t : t.name) ? 'text-indigo-700' : 'text-gray-800'"
                    :title="typeof t === 'string' ? t : t.name"
                  >{{ typeof t === 'string' ? t : t.name }}</span>
                  <span
                    v-if="typeof t !== 'string'"
                    :class="t.type === 'VIEW' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'"
                    class="text-[8px] px-1 py-0.5 rounded font-black leading-none shrink-0"
                  >{{ t.type }}</span>
                  <span
                    v-if="tableProfilesMap?.[(typeof t === 'string' ? t : t.name)]?.confidence_score != null"
                    class="text-[8px] px-1 py-0.5 rounded font-bold leading-none shrink-0"
                    :class="
                      tableProfilesMap[(typeof t === 'string' ? t : t.name)].confidence_score >= 80
                        ? 'bg-green-100 text-green-700'
                        : tableProfilesMap[(typeof t === 'string' ? t : t.name)].confidence_score >= 50
                          ? 'bg-yellow-100 text-yellow-700'
                          : 'bg-red-100 text-red-600'
                    "
                    :title="'置信度: ' + tableProfilesMap[(typeof t === 'string' ? t : t.name)].confidence_score"
                  >{{ tableProfilesMap[(typeof t === 'string' ? t : t.name)].confidence_score }}%</span>
                </div>
              </div>
              <div class="absolute top-1 right-1 flex items-center shrink-0 z-[1]">
                <button
                  @click.stop="emit('table-click', typeof t === 'string' ? t : t.name)"
                  class="p-0.5 text-gray-300 hover:text-blue-600 rounded opacity-0 group-hover:opacity-100 transition-all"
                  title="查看资产画像"
                ><EyeIcon class="w-3 h-3" /></button>
                <button
                  v-if="showAi"
                  @click.stop="emit('table-ai', typeof t === 'string' ? t : t.name)"
                  class="p-0.5 text-gray-300 hover:text-purple-600 hover:bg-purple-50 rounded opacity-0 group-hover:opacity-100 transition-all"
                  title="针对该表进行 AI 建模"
                >
                  <SparklesIcon class="w-3 h-3" />
                </button>
                <component :is="isExpanded(typeof t === 'string' ? t : t.name) ? ChevronDownIcon : ChevronRightIcon" class="w-3 h-3 text-gray-300 ml-0.5" />
              </div>

              <!-- 备注区：满宽展示，不与右侧按钮争列 -->
              <div
                v-if="tableProfilesMap?.[(typeof t === 'string' ? t : t.name)]?.ai_term
                  || tableFavorites?.[(typeof t === 'string' ? t : t.name)]?.note
                  || tableProfilesMap?.[(typeof t === 'string' ? t : t.name)]?.ai_description"
                class="mt-0.5 pr-1 table-desc-block"
                :class="tableRowIndentClass"
              >
                <div
                  v-if="tableProfilesMap?.[(typeof t === 'string' ? t : t.name)]?.ai_term"
                  class="text-[10px] text-indigo-600 font-semibold line-clamp-1 leading-snug"
                  :title="tableProfilesMap[(typeof t === 'string' ? t : t.name)].ai_term"
                >{{ tableProfilesMap[(typeof t === 'string' ? t : t.name)].ai_term }}</div>
                <div
                  v-if="tableFavorites?.[(typeof t === 'string' ? t : t.name)]?.note"
                  class="text-[10px] text-blue-600 leading-snug font-medium"
                  :class="[
                    descClampFor(typeof t === 'string' ? t : t.name).note,
                    tableProfilesMap?.[(typeof t === 'string' ? t : t.name)]?.ai_term ? 'mt-px' : '',
                  ]"
                  :title="tableFavorites[(typeof t === 'string' ? t : t.name)]?.note || ''"
                >📝 {{ tableFavorites[(typeof t === 'string' ? t : t.name)]?.note }}</div>
                <div
                  v-if="tableProfilesMap?.[(typeof t === 'string' ? t : t.name)]?.ai_description"
                  class="text-[10px] text-gray-500 leading-snug"
                  :class="[
                    descClampFor(typeof t === 'string' ? t : t.name).desc,
                    (tableFavorites?.[(typeof t === 'string' ? t : t.name)]?.note || tableProfilesMap?.[(typeof t === 'string' ? t : t.name)]?.ai_term) ? 'mt-px' : '',
                  ]"
                  :title="tableProfilesMap[(typeof t === 'string' ? t : t.name)].ai_description"
                >{{ tableProfilesMap[(typeof t === 'string' ? t : t.name)].ai_description }}</div>
              </div>
              <TableFavoriteActions
                variant="corner"
                :table-name="typeof t === 'string' ? t : t.name"
                :favorite="tableFavorites?.[typeof t === 'string' ? t : t.name]"
                @toggle-favorite="emit('toggle-favorite', typeof t === 'string' ? t : t.name)"
                @toggle-pin="emit('toggle-pin', typeof t === 'string' ? t : t.name)"
                @save-note="(note) => emit('save-favorite-note', { tableName: typeof t === 'string' ? t : t.name, note })"
              />
            </div>
            
            <!-- Columns Tree -->
            <div v-if="isExpanded(typeof t === 'string' ? t : t.name)" class="pl-4 border-l border-gray-100 ml-3 mb-1 max-h-96 overflow-y-auto custom-scrollbar">
               <div v-if="!getMergedColumns(typeof t === 'string' ? t : t.name)" class="py-1 text-[10px] text-gray-400 italic pl-4">读取 Schema...</div>
               <div v-else v-for="col in getMergedColumns(typeof t === 'string' ? t : t.name)!" :key="col.name" 
                  @dblclick.stop="handleColumnDblClick(col.name)"
                  draggable="true"
                  @dragstart.stop="handleDragStart($event, col.name)"
                  class="py-1 pl-2 pr-2 hover:bg-gray-50 cursor-pointer group/col rounded"
                  :class="advancedMode && (col.term || col.desc) ? 'flex flex-col gap-0.5' : 'flex items-center'"
               >
                  <div class="flex items-center min-w-0 w-full">
                    <CubeIcon class="w-2.5 h-2.5 mr-1.5 text-gray-300 group-hover/col:text-indigo-400 shrink-0" />
                    <span class="text-[10px] text-gray-500 group-hover/col:text-indigo-600 font-mono truncate">{{ col.name }}</span>
                    <span
                      v-if="advancedMode && col.term"
                      class="text-[9px] text-indigo-500 font-medium truncate ml-1 max-w-[80px]"
                      :title="col.term"
                    >{{ col.term }}</span>
                    <span v-if="col.type" class="text-[9px] text-gray-300 group-hover/col:text-indigo-300 ml-auto uppercase shrink-0">{{ col.type }}</span>
                  </div>
                  <div
                    v-if="advancedMode && col.desc"
                    class="text-[9px] text-gray-400 leading-snug line-clamp-2 pl-4"
                    :title="col.desc"
                  >{{ col.desc }}</div>
               </div>
            </div>
          </div>
        </div>
      </template>

      <!-- 我的收藏 Tab -->
      <template v-else>
        <div class="p-3 border-b bg-amber-50/60 flex items-center justify-between">
          <span class="text-xs font-bold text-amber-800">已收藏 {{ favoriteCount }} 张表</span>
          <span class="text-[10px] text-amber-600/80">点击定位到数据表</span>
        </div>
        <div class="flex-1 overflow-y-auto p-2 custom-scrollbar">
          <div v-if="!favoriteCount" class="py-12 text-center text-gray-400 text-xs px-4 leading-relaxed">
            暂无收藏<br />在「数据表」中点击 ⭐ 收藏常用表
          </div>
          <div
            v-for="item in favoriteTablesList"
            :key="item.name"
            class="mb-1.5 p-2 pt-1.5 rounded-lg border group relative cursor-pointer transition-colors hover:border-amber-200 hover:bg-amber-50/40"
            :class="item.is_pinned ? 'border-indigo-200 bg-indigo-50/30' : 'border-gray-100 bg-white'"
            @click="focusFavoriteTable(item.name)"
          >
            <div class="flex items-start justify-between gap-1 pr-1">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-1 flex-wrap">
                  <span class="text-xs font-mono font-bold text-gray-800 truncate" :title="item.name">{{ item.name }}</span>
                  <span v-if="item.is_pinned" class="text-[8px] px-1 py-0.5 rounded bg-indigo-100 text-indigo-700 font-black">置顶</span>
                </div>
                <div v-if="item.profile?.ai_term" class="text-[10px] text-indigo-600 font-semibold mt-px line-clamp-1 leading-snug">{{ item.profile.ai_term }}</div>
                <div v-if="item.note" class="text-[10px] text-blue-600 mt-px line-clamp-1 leading-snug">📝 {{ item.note }}</div>
                <div v-if="item.profile?.ai_description" class="text-[10px] text-gray-500 mt-px line-clamp-2 leading-snug">{{ item.profile.ai_description }}</div>
              </div>
            </div>
            <TableFavoriteActions
              variant="corner"
              :table-name="item.name"
              :favorite="tableFavorites?.[item.name]"
              @toggle-favorite="emit('toggle-favorite', item.name)"
              @toggle-pin="emit('toggle-pin', item.name)"
              @save-note="(note) => emit('save-favorite-note', { tableName: item.name, note })"
            />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: #f1f1f1; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
.table-desc-block {
  word-break: break-word;
}
</style>