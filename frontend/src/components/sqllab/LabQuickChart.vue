<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const props = defineProps<{
  columns: { name: string; type: string }[]
  rows: any[][]
}>()

const chartType = ref<'bar' | 'line' | 'pie'>('bar')
const xColumn = ref('')
const yColumn = ref('')

watch(() => props.columns, (cols) => {
  if (cols.length && !xColumn.value) xColumn.value = cols[0]?.name || ''
  if (cols.length > 1 && !yColumn.value) yColumn.value = cols[1]?.name || cols[0]?.name || ''
}, { immediate: true })

const chartOption = computed(() => {
  if (!xColumn.value || !yColumn.value || !props.rows.length) return null
  const xi = props.columns.findIndex(c => c.name === xColumn.value)
  const yi = props.columns.findIndex(c => c.name === yColumn.value)
  if (xi < 0 || yi < 0) return null

  const labels = props.rows.map(r => String(r[xi] ?? ''))
  const values = props.rows.map(r => Number(r[yi]) || 0)

  if (chartType.value === 'pie') {
    return {
      tooltip: { trigger: 'item' },
      series: [{ type: 'pie', radius: '55%', data: labels.map((n, i) => ({ name: n, value: values[i] })) }],
    }
  }
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: labels.length > 8 ? 30 : 0 } },
    yAxis: { type: 'value' },
    series: [{ type: chartType.value, data: values, smooth: chartType.value === 'line' }],
  }
})
</script>

<template>
  <div class="border-t border-gray-100 bg-gray-50/50 p-4 space-y-3">
    <div class="flex flex-wrap items-center gap-2 text-xs">
      <span class="font-bold text-gray-500">快速图表</span>
      <select v-model="chartType" class="px-2 py-1 border rounded-md bg-white">
        <option value="bar">柱状图</option>
        <option value="line">折线图</option>
        <option value="pie">饼图</option>
      </select>
      <select v-model="xColumn" class="px-2 py-1 border rounded-md bg-white">
        <option v-for="c in columns" :key="c.name" :value="c.name">X: {{ c.name }}</option>
      </select>
      <select v-model="yColumn" class="px-2 py-1 border rounded-md bg-white">
        <option v-for="c in columns" :key="'y-' + c.name" :value="c.name">Y: {{ c.name }}</option>
      </select>
    </div>
    <div v-if="chartOption" class="h-64 bg-white rounded-lg border">
      <VChart :option="chartOption" autoresize class="h-full w-full" />
    </div>
    <p v-else class="text-xs text-gray-400 text-center py-6">请选择数值列以生成图表</p>
  </div>
</template>
