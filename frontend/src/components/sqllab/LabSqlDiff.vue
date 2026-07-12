<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  original: string
  modified: string
}>()

const emit = defineEmits<{ (e: 'apply'): void; (e: 'close'): void }>()

const diffLines = computed(() => {
  const orig = props.original.split('\n')
  const mod = props.modified.split('\n')
  const max = Math.max(orig.length, mod.length)
  const lines: { type: 'same' | 'removed' | 'added'; text: string }[] = []
  for (let i = 0; i < max; i++) {
    const o = orig[i]
    const m = mod[i]
    if (o === m) {
      if (o !== undefined) lines.push({ type: 'same', text: o })
    } else {
      if (o !== undefined) lines.push({ type: 'removed', text: o })
      if (m !== undefined) lines.push({ type: 'added', text: m })
    }
  }
  return lines
})
</script>

<template>
  <div class="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col">
      <div class="px-6 py-4 border-b flex justify-between items-center">
        <h3 class="font-bold text-gray-800">SQL 修改对比</h3>
        <button class="text-gray-400 hover:text-gray-600" @click="emit('close')">✕</button>
      </div>
      <pre class="flex-1 overflow-auto p-4 text-xs font-mono leading-relaxed custom-scrollbar"><code
        v-for="(line, i) in diffLines"
        :key="i"
        :class="{
          'block bg-red-50 text-red-800': line.type === 'removed',
          'block bg-green-50 text-green-800': line.type === 'added',
          'block text-gray-600': line.type === 'same',
        }"
      >{{ line.type === 'removed' ? '- ' : line.type === 'added' ? '+ ' : '  ' }}{{ line.text }}</code></pre>
      <div class="px-6 py-4 border-t flex gap-3 justify-end">
        <button class="px-4 py-2 border rounded-lg text-sm" @click="emit('close')">取消</button>
        <button class="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold" @click="emit('apply')">应用修改</button>
      </div>
    </div>
  </div>
</template>
