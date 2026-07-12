<script setup lang="ts">
import { computed } from 'vue'

interface PreviewResult {
  columns: { name: string; type: string }[]
  rows: any[][]
  execution_time_ms?: number
}

const props = defineProps<{
  current: PreviewResult
  baseline: PreviewResult
  currentLabel?: string
  baselineLabel?: string
}>()

const emit = defineEmits<{ (e: 'clear-baseline'): void }>()

const fmt = (v: unknown) => (v === null || v === undefined ? 'NULL' : String(v))

const summary = computed(() => ({
  rowDelta: props.current.rows.length - props.baseline.rows.length,
  colDelta: props.current.columns.length - props.baseline.columns.length,
  timeDelta: (props.current.execution_time_ms || 0) - (props.baseline.execution_time_ms || 0),
}))

const diffRows = computed(() => {
  const max = Math.max(props.current.rows.length, props.baseline.rows.length)
  const cols = Math.max(props.current.columns.length, props.baseline.columns.length)
  const rows: { index: number; changed: boolean; left: string[]; right: string[] }[] = []
  for (let i = 0; i < Math.min(max, 50); i++) {
    const left = props.baseline.rows[i] || Array(cols).fill('—')
    const right = props.current.rows[i] || Array(cols).fill('—')
    const changed = left.some((v, j) => fmt(v) !== fmt(right[j]))
    rows.push({
      index: i + 1,
      changed,
      left: left.map(fmt),
      right: right.map(fmt),
    })
  }
  return rows
})
</script>

<template>
  <div class="border-t border-violet-100 bg-violet-50/30 p-4 space-y-3">
    <div class="flex items-center justify-between">
      <div class="text-xs font-bold text-violet-800">
        结果对比 · {{ baselineLabel || '基准' }} vs {{ currentLabel || '当前' }}
      </div>
      <button class="text-[10px] text-violet-600 hover:underline" @click="emit('clear-baseline')">清除基准</button>
    </div>
    <div class="flex gap-4 text-[11px] text-violet-700 font-mono">
      <span>行数 Δ {{ summary.rowDelta >= 0 ? '+' : '' }}{{ summary.rowDelta }}</span>
      <span>列数 Δ {{ summary.colDelta >= 0 ? '+' : '' }}{{ summary.colDelta }}</span>
      <span>耗时 Δ {{ summary.timeDelta >= 0 ? '+' : '' }}{{ summary.timeDelta.toFixed(1) }}ms</span>
    </div>
    <div class="overflow-auto max-h-80 border rounded-lg bg-white text-[10px] font-mono">
      <table class="min-w-full">
        <thead class="bg-gray-50 sticky top-0">
          <tr>
            <th class="px-2 py-1 border-b">#</th>
            <th class="px-2 py-1 border-b text-left" colspan="999">基准 → 当前（变更行高亮）</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in diffRows" :key="r.index" :class="r.changed ? 'bg-amber-50' : ''">
            <td class="px-2 py-1 border-b text-gray-400">{{ r.index }}</td>
            <td class="px-2 py-1 border-b whitespace-pre-wrap max-w-xl">{{ r.left.join(' | ') }}</td>
            <td class="px-2 py-1 border-b text-gray-300">→</td>
            <td class="px-2 py-1 border-b whitespace-pre-wrap max-w-xl">{{ r.right.join(' | ') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
