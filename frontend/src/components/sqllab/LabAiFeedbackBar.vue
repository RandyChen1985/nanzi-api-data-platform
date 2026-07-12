<script setup lang="ts">
import { HandThumbUpIcon, HandThumbDownIcon } from '@heroicons/vue/24/outline'

defineProps<{
  prompt?: string
  rating?: number | null
  compact?: boolean
}>()

defineEmits<{ (e: 'rate', rating: 1 | 2): void }>()

const truncate = (s: string, n: number) => (s.length > n ? s.slice(0, n) + '…' : s)
</script>

<template>
  <div
    class="flex items-center gap-2 min-w-0"
    :class="compact ? 'text-[11px]' : 'text-xs'"
  >
    <span v-if="rating === 2" class="inline-flex items-center gap-1 text-emerald-700 font-semibold shrink-0">
      <HandThumbUpIcon class="w-3.5 h-3.5" /> 已反馈：满意
    </span>
    <span v-else-if="rating === 1" class="inline-flex items-center gap-1 text-amber-700 font-semibold shrink-0">
      <HandThumbDownIcon class="w-3.5 h-3.5" /> 已反馈：待改进
    </span>
    <template v-else>
      <span class="text-gray-600 font-medium shrink-0">AI 生成满意吗？</span>
      <button
        type="button"
        class="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 font-bold transition-colors shrink-0"
        title="满意"
        @click="$emit('rate', 2)"
      >
        <HandThumbUpIcon class="w-3.5 h-3.5" />
        <span v-if="!compact">满意</span>
      </button>
      <button
        type="button"
        class="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100 font-bold transition-colors shrink-0"
        title="不满意"
        @click="$emit('rate', 1)"
      >
        <HandThumbDownIcon class="w-3.5 h-3.5" />
        <span v-if="!compact">不满意</span>
      </button>
    </template>
    <span
      v-if="prompt && !compact"
      class="text-gray-400 truncate hidden sm:inline"
      :title="prompt"
    >针对：{{ truncate(prompt, 48) }}</span>
  </div>
</template>
