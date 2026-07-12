<script setup lang="ts">
import { computed, useAttrs, ref } from 'vue'
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/vue/24/outline'

defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    modelValue: string
    showSearchIcon?: boolean
    inputClass?: string
    wrapperClass?: string
    clearable?: boolean
  }>(),
  {
    showSearchIcon: false,
    inputClass: '',
    wrapperClass: '',
    clearable: true,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  input: [event: Event]
  clear: []
  keyup: [event: KeyboardEvent]
  keydown: [event: KeyboardEvent]
  focus: [event: FocusEvent]
  blur: [event: FocusEvent]
}>()

const attrs = useAttrs()
const inputRef = ref<HTMLInputElement | null>(null)

defineExpose({
  focus: () => inputRef.value?.focus(),
})

const hasValue = computed(() => props.modelValue.length > 0)

const resolvedInputClass = computed(() => {
  if (props.inputClass) return props.inputClass
  return 'py-2 text-sm'
})

const paddingClass = computed(() => {
  const left = props.showSearchIcon ? 'pl-9' : 'px-3'
  const right = props.clearable && hasValue.value ? 'pr-9' : (!props.showSearchIcon ? '' : 'pr-3')
  if (props.showSearchIcon) {
    return [left, right].filter(Boolean).join(' ')
  }
  return props.clearable && hasValue.value ? 'pr-9' : ''
})

const onInput = (event: Event) => {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
  emit('input', event)
}

const clearValue = () => {
  emit('update:modelValue', '')
  emit('clear')
  emit('input', new Event('input'))
}
</script>

<template>
  <div
    class="relative border border-gray-200 rounded-lg bg-white transition-[box-shadow,border-color] focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20"
    :class="wrapperClass"
  >
    <MagnifyingGlassIcon
      v-if="showSearchIcon"
      class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none z-[1]"
    />
    <input
      ref="inputRef"
      :value="modelValue"
      type="text"
      :class="[
        'block w-full border-0 bg-transparent focus:outline-none focus:ring-0 shadow-none',
        resolvedInputClass,
        paddingClass,
      ]"
      v-bind="attrs"
      @input="onInput"
      @keyup="emit('keyup', $event)"
      @keydown="emit('keydown', $event)"
      @focus="emit('focus', $event)"
      @blur="emit('blur', $event)"
    />
    <button
      v-if="clearable && hasValue"
      type="button"
      class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-300 hover:text-gray-500 transition-colors z-[1]"
      aria-label="清空"
      tabindex="-1"
      @mousedown.prevent
      @click="clearValue"
    >
      <XMarkIcon class="w-4 h-4" />
    </button>
  </div>
</template>
