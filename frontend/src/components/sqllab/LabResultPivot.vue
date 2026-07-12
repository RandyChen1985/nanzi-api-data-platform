<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  columns: { name: string; type: string }[]
  rows: any[][]
}>()

const rowField = ref('')
const colField = ref('')
const valueField = ref('')
const agg = ref<'sum' | 'count' | 'avg'>('sum')

const colNames = computed(() => props.columns.map(c => c.name))

const initFields = () => {
  if (!rowField.value && colNames.value[0]) rowField.value = colNames.value[0]
  if (!colField.value && colNames.value[1]) colField.value = colNames.value[1]
  if (!valueField.value && colNames.value[2]) valueField.value = colNames.value[2]
}
initFields()

const pivotTable = computed(() => {
  const ri = props.columns.findIndex(c => c.name === rowField.value)
  const ci = props.columns.findIndex(c => c.name === colField.value)
  const vi = props.columns.findIndex(c => c.name === valueField.value)
  if (ri < 0 || ci < 0) return { headers: [] as string[], rows: [] as string[][] }

  const bucket: Record<string, Record<string, number[]>> = {}
  const colSet = new Set<string>()

  for (const row of props.rows) {
    const rk = String(row[ri] ?? 'NULL')
    const ck = String(row[ci] ?? 'NULL')
    colSet.add(ck)
    bucket[rk] ??= {}
    bucket[rk][ck] ??= []
    if (vi >= 0) {
      const n = Number(row[vi])
      bucket[rk][ck].push(Number.isFinite(n) ? n : 0)
    } else {
      bucket[rk][ck].push(1)
    }
  }

  const colHeaders = [...colSet].sort()
  const headers = [rowField.value || '行', ...colHeaders]

  const aggregate = (arr: number[]) => {
    if (!arr.length) return '—'
    if (agg.value === 'count') return String(arr.length)
    if (agg.value === 'avg') return (arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(2)
    return arr.reduce((a, b) => a + b, 0).toLocaleString()
  }

  const rows = Object.keys(bucket).sort().map(rk => [
    rk,
    ...colHeaders.map(ck => aggregate(bucket[rk]?.[ck] || [])),
  ])

  return { headers, rows }
})
</script>

<template>
  <div class="p-4 space-y-3 border-t border-gray-100 bg-gray-50/50">
    <div class="flex flex-wrap items-center gap-2 text-xs">
      <span class="font-bold text-gray-500">透视表</span>
      <select v-model="rowField" class="px-2 py-1 border rounded-md bg-white">
        <option v-for="c in colNames" :key="'r-' + c" :value="c">行: {{ c }}</option>
      </select>
      <select v-model="colField" class="px-2 py-1 border rounded-md bg-white">
        <option v-for="c in colNames" :key="'c-' + c" :value="c">列: {{ c }}</option>
      </select>
      <select v-model="valueField" class="px-2 py-1 border rounded-md bg-white">
        <option value="">计数</option>
        <option v-for="c in colNames" :key="'v-' + c" :value="c">值: {{ c }}</option>
      </select>
      <select v-model="agg" class="px-2 py-1 border rounded-md bg-white">
        <option value="sum">求和</option>
        <option value="avg">平均</option>
        <option value="count">计数</option>
      </select>
    </div>
    <div class="overflow-auto max-h-96 border rounded-lg bg-white">
      <table class="min-w-full text-xs font-mono">
        <thead class="bg-gray-50 sticky top-0">
          <tr>
            <th v-for="h in pivotTable.headers" :key="h" class="px-3 py-2 text-left border-b font-bold text-gray-600">{{ h }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in pivotTable.rows" :key="i" class="hover:bg-gray-50">
            <td v-for="(cell, j) in row" :key="j" class="px-3 py-1.5 border-b" :class="j === 0 ? 'font-semibold text-gray-800' : 'text-gray-600'">{{ cell }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
