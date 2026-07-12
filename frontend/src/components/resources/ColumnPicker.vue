<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ChevronUpDownIcon } from '@heroicons/vue/24/outline'
import ClearableInput from '../common/ClearableInput.vue'

export interface ColumnOption {
  name: string
  type?: string
  comment?: string
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    columns: ColumnOption[]
    disabled?: boolean
    placeholder?: string
    emptyLabel?: string
    allowEmpty?: boolean
  }>(),
  {
    placeholder: '选择字段...',
    emptyLabel: '无',
    allowEmpty: true,
  }
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const searchInputRef = ref<InstanceType<typeof ClearableInput> | null>(null)
const searchQuery = ref('')

const options = computed((): ColumnOption[] => {
  const cols = [...props.columns]
  if (props.modelValue && !cols.some((c) => c.name === props.modelValue)) {
    cols.push({ name: props.modelValue, comment: '自定义字段' })
  }
  return cols
})

const filteredOptions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return options.value
  return options.value.filter((c) => {
    const name = c.name.toLowerCase()
    const comment = (c.comment || '').toLowerCase()
    const type = (c.type || '').toLowerCase()
    return name.includes(q) || comment.includes(q) || type.includes(q)
  })
})

const selectedColumn = computed(() =>
  props.modelValue ? options.value.find((c) => c.name === props.modelValue) : null
)

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

const selectColumn = (name: string) => {
  emit('update:modelValue', name)
  open.value = false
}
</script>

<template>
  <div ref="rootRef" class="relative w-full">
    <button
      type="button"
      :disabled="disabled"
      class="w-full flex items-center justify-between gap-2 border border-gray-300 rounded-md shadow-sm py-2 px-3 text-left disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed hover:border-gray-400 focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
      @click.stop="toggleOpen"
    >
      <div class="min-w-0 flex-1">
        <template v-if="selectedColumn">
          <div class="font-mono text-sm text-gray-900 truncate leading-tight">{{ selectedColumn.name }}</div>
          <div class="text-xs text-gray-500 truncate leading-tight mt-0.5">
            {{ selectedColumn.comment || '暂无备注' }}
          </div>
        </template>
        <span v-else class="text-sm text-gray-400">{{ allowEmpty ? emptyLabel : placeholder }}</span>
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
            placeholder="搜索字段名或中文名..."
            @keydown.esc.prevent="open = false"
          />
        </div>
        <p v-if="searchQuery.trim()" class="mt-1 px-1 text-[11px] text-gray-400">
          共 {{ filteredOptions.length }} / {{ options.length }} 项
        </p>
      </div>

      <div class="max-h-60 overflow-y-auto custom-scrollbar py-1">
        <button
          v-if="allowEmpty && (!searchQuery.trim() || emptyLabel.toLowerCase().includes(searchQuery.trim().toLowerCase()))"
          type="button"
          class="w-full text-left px-3 py-2.5 hover:bg-blue-50 transition-colors border-b border-gray-100"
          :class="{ 'bg-blue-50/80': !modelValue }"
          @click="selectColumn('')"
        >
          <div class="text-sm text-gray-500">{{ emptyLabel }}</div>
        </button>
        <button
          v-for="col in filteredOptions"
          :key="col.name"
          type="button"
          class="w-full text-left px-3 py-2.5 hover:bg-blue-50 transition-colors border-b border-gray-50 last:border-b-0"
          :class="{ 'bg-blue-50/80': modelValue === col.name }"
          @click="selectColumn(col.name)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="font-mono text-sm text-gray-900 truncate leading-tight">{{ col.name }}</div>
              <div class="text-xs text-gray-500 truncate leading-tight mt-0.5">
                {{ col.comment || '暂无备注' }}
              </div>
            </div>
            <span
              v-if="col.type"
              class="shrink-0 text-[10px] px-1.5 py-0.5 rounded font-semibold whitespace-nowrap bg-gray-100 text-gray-600"
            >
              {{ col.type }}
            </span>
          </div>
        </button>
        <div v-if="filteredOptions.length === 0 && (searchQuery.trim() || !allowEmpty)" class="px-3 py-6 text-center text-sm text-gray-400">
          没有匹配的字段
        </div>
      </div>
    </div>
  </div>
</template>
