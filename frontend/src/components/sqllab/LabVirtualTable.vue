<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  columns: { name: string; type: string }[]
  rows: any[][]
  rowHeight?: number
  sortColumn?: string | null
  sortDirection?: 'asc' | 'desc' | null
}>()

const emit = defineEmits<{
  (e: 'header-click', name: string): void
  (e: 'cell-click', payload: { row: number; col: number; value: string }): void
  (e: 'copy-column', idx: number): void
}>()

const ROW_H = props.rowHeight || 40
const containerRef = ref<HTMLElement | null>(null)
const scrollTop = ref(0)
const viewportH = ref(480)

const onScroll = () => {
  if (containerRef.value) scrollTop.value = containerRef.value.scrollTop
}

const updateViewport = () => {
  if (containerRef.value) viewportH.value = containerRef.value.clientHeight || 480
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
})
onUnmounted(() => window.removeEventListener('resize', updateViewport))

const startIdx = computed(() => Math.max(0, Math.floor(scrollTop.value / ROW_H) - 8))
const endIdx = computed(() => {
  const visible = Math.ceil(viewportH.value / ROW_H) + 16
  return Math.min(props.rows.length, startIdx.value + visible)
})

const topPad = computed(() => startIdx.value * ROW_H)
const bottomPad = computed(() => Math.max(0, (props.rows.length - endIdx.value) * ROW_H))
const visibleRows = computed(() => props.rows.slice(startIdx.value, endIdx.value))

const formatCell = (v: unknown) => (v === null || v === undefined ? 'NULL' : String(v))
</script>

<template>
  <div ref="containerRef" class="overflow-auto flex-1 min-h-0" @scroll="onScroll">
    <table class="min-w-full divide-y divide-gray-200">
      <thead class="bg-gray-50 sticky top-0 z-10">
        <tr>
          <th
            v-for="(c, ci) in columns"
            :key="c.name"
            class="px-6 py-3 text-left text-xs font-bold text-gray-500 border-b border-gray-200 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none"
            @click="emit('header-click', c.name)"
            @contextmenu.prevent="emit('copy-column', ci)"
          >
            {{ c.name }}
            <span v-if="sortColumn === c.name" class="ml-1 text-blue-500">{{ sortDirection === 'asc' ? '↑' : '↓' }}</span>
          </th>
        </tr>
      </thead>
      <tbody class="bg-white">
        <tr v-if="topPad > 0"><td :colspan="columns.length" :style="{ height: topPad + 'px', padding: 0, border: 'none' }" /></tr>
        <tr v-for="(r, i) in visibleRows" :key="startIdx + i" class="hover:bg-gray-50">
          <td
            v-for="(v, j) in r"
            :key="j"
            class="px-6 py-3 text-sm text-gray-600 font-mono border-b border-gray-100 whitespace-nowrap max-w-xs"
            style="height: 40px"
            @click="emit('cell-click', { row: startIdx + i, col: j, value: formatCell(v) })"
          >
            {{ formatCell(v).length > 120 ? formatCell(v).slice(0, 120) + '…' : formatCell(v) }}
          </td>
        </tr>
        <tr v-if="bottomPad > 0"><td :colspan="columns.length" :style="{ height: bottomPad + 'px', padding: 0, border: 'none' }" /></tr>
      </tbody>
    </table>
  </div>
</template>
