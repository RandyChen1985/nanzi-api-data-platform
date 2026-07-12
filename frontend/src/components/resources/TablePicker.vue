<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ChevronUpDownIcon } from '@heroicons/vue/24/outline'
import ClearableInput from '../common/ClearableInput.vue'

export interface TableOption {
  name: string
  type?: string
  term?: string
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    tables: (TableOption | string)[]
    disabled?: boolean
    placeholder?: string
  }>(),
  { placeholder: '选择表...' }
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const searchInputRef = ref<InstanceType<typeof ClearableInput> | null>(null)
const searchQuery = ref('')

const normalizedTables = computed((): TableOption[] =>
  props.tables.map((t) => (typeof t === 'string' ? { name: t, type: 'TABLE' } : t))
)

const filteredTables = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return normalizedTables.value
  return normalizedTables.value.filter((t) => {
    const name = t.name.toLowerCase()
    const term = (t.term || '').toLowerCase()
    const type = (t.type || '').toLowerCase()
    return name.includes(q) || term.includes(q) || type.includes(q)
  })
})

const selectedTable = computed(() => normalizedTables.value.find((t) => t.name === props.modelValue))

const closeOnOutside = (e: MouseEvent) => {
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', closeOnOutside))
onUnmounted(() => document.removeEventListener('click', closeOnOutside))

watch(open, (isOpen) => {
  if (isOpen) {
    searchQuery.value = ''
    nextTick(() => searchInputRef.value?.focus())
  }
})

const toggleOpen = () => {
  if (props.disabled) return
  open.value = !open.value
}

const selectTable = (name: string) => {
  emit('update:modelValue', name)
  open.value = false
}
</script>

<template>
  <div ref="rootRef" class="relative flex-1 min-w-0">
    <button
      type="button"
      :disabled="disabled"
      class="w-full flex items-center justify-between gap-2 border border-gray-300 rounded-md shadow-sm py-2 px-3 text-left disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed hover:border-gray-400 focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
      @click.stop="toggleOpen"
    >
      <div class="min-w-0 flex-1">
        <template v-if="selectedTable">
          <div class="font-mono text-sm text-gray-900 truncate leading-tight">{{ selectedTable.name }}</div>
          <div class="text-xs text-gray-500 truncate leading-tight mt-0.5">
            {{ selectedTable.term || '暂无中文名' }}
          </div>
        </template>
        <span v-else class="text-sm text-gray-400">{{ placeholder }}</span>
      </div>
      <ChevronUpDownIcon class="w-4 h-4 shrink-0 text-gray-400" />
    </button>

    <div
      v-if="open"
      class="absolute z-30 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden"
    >
      <div class="sticky top-0 z-10 bg-white border-b border-gray-100 px-2 py-2">
        <div @click.stop>
          <ClearableInput
            ref="searchInputRef"
            v-model="searchQuery"
            show-search-icon
            input-class="py-1.5 text-sm"
            placeholder="搜索表名或中文名..."
            @keydown.esc.prevent="open = false"
          />
        </div>
        <p v-if="searchQuery.trim()" class="mt-1 px-1 text-[11px] text-gray-400">
          共 {{ filteredTables.length }} / {{ normalizedTables.length }} 项
        </p>
      </div>

      <div class="max-h-60 overflow-y-auto custom-scrollbar py-1">
        <button
          v-for="t in filteredTables"
          :key="t.name"
          type="button"
          class="w-full text-left px-3 py-2.5 hover:bg-blue-50 transition-colors border-b border-gray-50 last:border-b-0"
          :class="{ 'bg-blue-50/80': modelValue === t.name }"
          @click="selectTable(t.name)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="font-mono text-sm text-gray-900 truncate leading-tight">{{ t.name }}</div>
              <div class="text-xs text-gray-500 truncate leading-tight mt-0.5">
                {{ t.term || '暂无中文名' }}
              </div>
            </div>
            <span
              v-if="t.type"
              class="shrink-0 text-[10px] px-1.5 py-0.5 rounded font-semibold whitespace-nowrap"
              :class="t.type === 'VIEW' ? 'bg-amber-50 text-amber-700 border border-amber-100' : 'bg-gray-100 text-gray-600'"
            >
              {{ t.type }}
            </span>
          </div>
        </button>
        <div v-if="filteredTables.length === 0" class="px-3 py-6 text-center text-sm text-gray-400">
          没有匹配的表
        </div>
      </div>
    </div>
  </div>
</template>
