<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { CommandLineIcon, TrashIcon } from '@heroicons/vue/24/outline'

export type AiLogEntry = { timestamp: number; type: 'info' | 'error' | 'success'; msg: string }

const props = defineProps<{
  logs: AiLogEntry[]
}>()

const emit = defineEmits<{ (e: 'clear'): void }>()

const logContainerRef = ref<HTMLElement | null>(null)

const formatTime = (ts: number) => {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

watch(
  () => props.logs.length,
  () => {
    nextTick(() => {
      if (logContainerRef.value) {
        logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
      }
    })
  },
)
</script>

<template>
  <div class="h-full flex flex-col min-h-[320px]">
    <div class="px-4 py-2 border-b bg-gray-900 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <CommandLineIcon class="w-4 h-4 text-green-400" />
        <span class="text-xs font-bold text-gray-100 uppercase tracking-wider">AI 核心日志</span>
        <span class="text-[10px] text-gray-500">({{ logs.length }})</span>
      </div>
      <button type="button" class="p-1 text-gray-500 hover:text-red-400 transition-colors" title="清空日志" @click="emit('clear')">
        <TrashIcon class="w-4 h-4" />
      </button>
    </div>
    <div ref="logContainerRef" class="flex-1 overflow-y-auto bg-black p-4 font-mono custom-scrollbar min-h-0">
      <div v-if="!logs.length" class="text-gray-600 text-xs italic">等待 AI 任务触发...</div>
      <div v-for="(log, idx) in logs" :key="idx" class="mb-3">
        <div class="flex items-start gap-2">
          <span class="text-[10px] text-gray-500 flex-shrink-0 whitespace-nowrap mt-0.5">{{ formatTime(log.timestamp) }}</span>
          <div class="flex-1 min-w-0">
            <span
              class="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-tighter mr-1.5"
              :class="{
                'bg-blue-900/50 text-blue-400 border border-blue-800/50': log.type === 'info',
                'bg-red-900/50 text-red-400 border border-red-800/50': log.type === 'error',
                'bg-green-900/50 text-green-400 border border-green-800/50': log.type === 'success',
              }"
            >{{ log.type }}</span>
            <span
              class="text-xs break-words leading-relaxed"
              :class="{
                'text-gray-300': log.type === 'info',
                'text-red-300': log.type === 'error',
                'text-green-300': log.type === 'success',
              }"
            >{{ log.msg }}</span>
          </div>
        </div>
      </div>
    </div>
    <div class="px-3 py-1.5 border-t bg-gray-900/90 text-[10px] text-gray-500 text-center font-mono shrink-0">
      INTERNAL ENGINE DEBUG MODE V2
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 6px; }
</style>
