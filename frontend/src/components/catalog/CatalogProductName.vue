<script setup lang="ts">
import { ref, computed } from 'vue'
import { DocumentDuplicateIcon, CheckIcon } from '@heroicons/vue/24/outline'
import { useToast } from '@/composables/useToast'
import { copyToClipboard } from '@/utils/clipboard'

const props = withDefaults(
  defineProps<{
    name: string
    size?: 'sm' | 'md' | 'lg'
    hoverHighlight?: boolean
  }>(),
  { size: 'sm', hoverHighlight: false },
)

const titleTag = computed(() => (props.size === 'lg' ? 'h1' : 'h3'))

const titleClass = computed(() => {
  if (props.size === 'lg') return 'text-lg sm:text-2xl font-bold text-gray-900 truncate'
  if (props.size === 'md') return 'text-lg font-bold text-gray-900 truncate'
  return 'text-base font-bold text-gray-900 truncate'
})

const { showToast } = useToast()
const copied = ref(false)

const copyName = async (e: Event) => {
  e.stopPropagation()
  const success = await copyToClipboard(props.name)
  if (success) {
    copied.value = true
    showToast('产品名称已复制', 'success')
    setTimeout(() => {
      copied.value = false
    }, 1500)
  } else {
    showToast('复制失败', 'error')
  }
}
</script>

<template>
  <div class="inline-flex items-center gap-1 min-w-0 max-w-full">
    <component
      :is="titleTag"
      :class="[titleClass, hoverHighlight && 'group-hover:text-indigo-600 transition-colors']"
    >
      {{ name }}
    </component>
    <button
      type="button"
      class="shrink-0 p-0.5 rounded text-gray-300 opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-indigo-600 hover:bg-indigo-50 transition-all"
      title="复制产品名称"
      aria-label="复制产品名称"
      @click="copyName"
    >
      <CheckIcon v-if="copied" class="w-3.5 h-3.5 text-green-600" />
      <DocumentDuplicateIcon v-else class="w-3.5 h-3.5" />
    </button>
  </div>
</template>
