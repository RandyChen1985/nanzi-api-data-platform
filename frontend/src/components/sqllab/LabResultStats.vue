<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  columns: { name: string; type: string }[]
  rows: any[][]
}>()

const toNum = (v: unknown): number | null => {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const stats = computed(() => {
  return props.columns.map((col, idx) => {
    const values = props.rows.map(r => r[idx])
    const nullCount = values.filter(v => v === null || v === undefined).length
    const nums = values.map(toNum).filter((n): n is number => n !== null)
    if (nums.length === 0) {
      const distinct = new Set(values.map(v => String(v ?? 'NULL'))).size
      return { name: col.name, kind: 'text' as const, nullCount, nullPct: values.length ? (nullCount / values.length) * 100 : 0, distinct }
    }
    const min = Math.min(...nums)
    const max = Math.max(...nums)
    const sum = nums.reduce((a, b) => a + b, 0)
    const avg = sum / nums.length
    return {
      name: col.name,
      kind: 'numeric' as const,
      nullCount,
      nullPct: values.length ? (nullCount / values.length) * 100 : 0,
      min,
      max,
      avg,
      count: nums.length,
    }
  })
})
</script>

<template>
  <div class="border-t border-gray-100 bg-slate-50/80 px-4 py-3 overflow-x-auto">
    <div class="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">列统计</div>
    <div class="flex gap-2 min-w-max">
      <div
        v-for="s in stats"
        :key="s.name"
        class="px-3 py-2 bg-white border border-slate-200 rounded-lg text-[10px] min-w-[140px]"
      >
        <div class="font-bold text-slate-800 truncate mb-1" :title="s.name">{{ s.name }}</div>
        <div v-if="s.kind === 'numeric'" class="text-slate-600 space-y-0.5 font-mono">
          <div>min {{ s.min?.toLocaleString() }} · max {{ s.max?.toLocaleString() }}</div>
          <div>avg {{ s.avg?.toFixed(2) }} · n={{ s.count }}</div>
        </div>
        <div v-else class="text-slate-600 font-mono">去重 {{ s.distinct }} 值</div>
        <div class="text-slate-400 mt-1">NULL {{ s.nullPct.toFixed(0) }}%</div>
      </div>
    </div>
  </div>
</template>
