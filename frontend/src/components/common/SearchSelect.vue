<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ChevronUpDownIcon } from '@heroicons/vue/24/outline'
import ClearableInput from './ClearableInput.vue'

export interface SearchSelectOption {
  value: string | number
  label: string
  sublabel?: string
  keywords?: string
}

const props = withDefaults(
  defineProps<{
    modelValue: string | number | null
    options: SearchSelectOption[]
    disabled?: boolean
    placeholder?: string
    searchPlaceholder?: string
    emptyLabel?: string
    allowEmpty?: boolean
    emptyValue?: string | number | null
  }>(),
  {
    placeholder: '请选择...',
    searchPlaceholder: '搜索...',
    emptyLabel: '请选择',
    allowEmpty: false,
    emptyValue: null,
  },
)

const emit = defineEmits<{ 'update:modelValue': [value: string | number | null] }>()

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const searchInputRef = ref<InstanceType<typeof ClearableInput> | null>(null)
const searchQuery = ref('')

const filteredOptions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.options
  return props.options.filter((opt) => {
    const haystack = [opt.label, opt.sublabel, opt.keywords, String(opt.value)]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return haystack.includes(q)
  })
})

const selectedOption = computed(() =>
  props.modelValue == null || props.modelValue === ''
    ? null
    : props.options.find((opt) => opt.value === props.modelValue) ?? null,
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

const selectOption = (value: string | number | null) => {
  emit('update:modelValue', value)
  open.value = false
}

const showEmptyOption = computed(() => {
  if (!props.allowEmpty) return false
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return true
  return props.emptyLabel.toLowerCase().includes(q)
})
</script>

<template>
  <div ref="rootRef" class="relative w-full">
    <button
      type="button"
      :disabled="disabled"
      class="w-full flex items-center justify-between gap-2 border border-gray-200 rounded-lg py-2 px-3 text-left disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed hover:border-gray-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
      @click.stop="toggleOpen"
    >
      <div class="min-w-0 flex-1">
        <template v-if="selectedOption">
          <div class="text-sm text-gray-900 truncate leading-tight">{{ selectedOption.label }}</div>
          <div v-if="selectedOption.sublabel" class="text-xs text-gray-500 truncate leading-tight mt-0.5">
            {{ selectedOption.sublabel }}
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
            :placeholder="searchPlaceholder"
            @keydown.esc.prevent="open = false"
          />
        </div>
        <p v-if="searchQuery.trim()" class="mt-1 px-1 text-[11px] text-gray-400">
          共 {{ filteredOptions.length + (showEmptyOption ? 1 : 0) }} / {{ options.length + (allowEmpty ? 1 : 0) }} 项
        </p>
      </div>

      <div class="max-h-60 overflow-y-auto custom-scrollbar py-1">
        <button
          v-if="showEmptyOption"
          type="button"
          class="w-full text-left px-3 py-2.5 hover:bg-indigo-50 transition-colors border-b border-gray-100"
          :class="{ 'bg-indigo-50/80': modelValue == null || modelValue === '' }"
          @click="selectOption(emptyValue)"
        >
          <div class="text-sm text-gray-500">{{ emptyLabel }}</div>
        </button>
        <button
          v-for="opt in filteredOptions"
          :key="String(opt.value)"
          type="button"
          class="w-full text-left px-3 py-2.5 hover:bg-indigo-50 transition-colors border-b border-gray-50 last:border-b-0"
          :class="{ 'bg-indigo-50/80': modelValue === opt.value }"
          @click="selectOption(opt.value)"
        >
          <div class="min-w-0">
            <div class="text-sm text-gray-900 truncate leading-tight">{{ opt.label }}</div>
            <div v-if="opt.sublabel" class="text-xs text-gray-500 truncate leading-tight mt-0.5">
              {{ opt.sublabel }}
            </div>
          </div>
        </button>
        <div
          v-if="filteredOptions.length === 0 && !showEmptyOption"
          class="px-3 py-6 text-center text-sm text-gray-400"
        >
          没有匹配的选项
        </div>
      </div>
    </div>
  </div>
</template>
