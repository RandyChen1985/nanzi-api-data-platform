<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { ChevronDownIcon, ChevronRightIcon, ArrowsPointingOutIcon, XMarkIcon } from '@heroicons/vue/24/outline'

const props = defineProps<{
  joinPaths: any[]
}>()

const emit = defineEmits<{ (e: 'insert', snippet: string): void }>()

const collapsed = ref(false)
const showModal = ref(false)
const STORAGE_KEY = 'sqllab_join_diagram_collapsed'

onMounted(() => {
  collapsed.value = localStorage.getItem(STORAGE_KEY) === '1'
  window.addEventListener('keydown', onEsc)
})
onUnmounted(() => window.removeEventListener('keydown', onEsc))

const toggleCollapse = () => {
  collapsed.value = !collapsed.value
  localStorage.setItem(STORAGE_KEY, collapsed.value ? '1' : '0')
}

const nodes = computed(() => {
  const set = new Set<string>()
  props.joinPaths.forEach(p => {
    set.add(p.source_table)
    set.add(p.target_table)
  })
  return [...set]
})

type LayoutMode = 'compact' | 'expanded'

function buildLayout(mode: LayoutMode) {
  const list = nodes.value
  const count = list.length || 1
  const cols = mode === 'expanded'
    ? Math.min(5, Math.max(2, Math.ceil(Math.sqrt(count))))
    : Math.min(3, count)
  const nodeW = mode === 'expanded' ? 180 : 140
  const gapX = mode === 'expanded' ? 220 : 180
  const gapY = mode === 'expanded' ? 120 : 100
  const padX = mode === 'expanded' ? 48 : 40
  const padY = mode === 'expanded' ? 48 : 40

  const positions: Record<string, { x: number; y: number }> = {}
  list.forEach((name, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    positions[name] = { x: padX + col * gapX, y: padY + row * gapY }
  })

  const rows = Math.ceil(count / cols)
  const svgWidth = Math.max(mode === 'expanded' ? 720 : 360, padX * 2 + (cols - 1) * gapX + nodeW)
  const svgHeight = padY * 2 + (rows - 1) * gapY + (mode === 'expanded' ? 48 : 40)

  return { positions, nodeW, svgWidth, svgHeight, nodeH: mode === 'expanded' ? 48 : 40 }
}

const compactLayout = computed(() => buildLayout('compact'))
const expandedLayout = computed(() => buildLayout('expanded'))

function buildEdges(layout: ReturnType<typeof buildLayout>) {
  return props.joinPaths
    .map(p => ({
      ...p,
      from: layout.positions[p.source_table],
      to: layout.positions[p.target_table],
    }))
    .filter(e => e.from && e.to)
}

const compactEdges = computed(() => buildEdges(compactLayout.value))
const expandedEdges = computed(() => buildEdges(expandedLayout.value))

const truncateName = (name: string, mode: LayoutMode) => {
  const max = mode === 'expanded' ? 22 : 16
  return name.length > max ? name.slice(0, max - 1) + '…' : name
}

const onEsc = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && showModal.value) showModal.value = false
}
</script>

<template>
  <div v-if="joinPaths.length" class="border-b bg-slate-50">
    <div class="px-3 py-2 flex items-center justify-between gap-2">
      <button
        type="button"
        class="flex items-center gap-1 min-w-0 text-left group"
        @click="toggleCollapse"
      >
        <component
          :is="collapsed ? ChevronRightIcon : ChevronDownIcon"
          class="w-3.5 h-3.5 text-slate-400 shrink-0 group-hover:text-indigo-500"
        />
        <span class="text-[9px] font-black text-slate-600 uppercase tracking-widest truncate">表关联图</span>
        <span class="text-[9px] text-slate-400 font-bold shrink-0">({{ joinPaths.length }})</span>
      </button>
      <div class="flex items-center gap-1 shrink-0">
        <button
          type="button"
          class="p-1 rounded-md text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
          title="放大查看"
          @click.stop="showModal = true"
        >
          <ArrowsPointingOutIcon class="w-4 h-4" />
        </button>
      </div>
    </div>

    <div v-show="!collapsed" class="px-3 pb-2">
      <div class="overflow-x-auto">
        <svg :width="compactLayout.svgWidth" height="160" class="bg-white rounded-lg border min-w-full">
          <defs>
            <marker id="join-arrow-compact" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L6,3 L0,6 Z" fill="#6366f1" />
            </marker>
          </defs>
          <line
            v-for="(e, i) in compactEdges"
            :key="'ce-' + i"
            :x1="(e.from?.x ?? 0) + compactLayout.nodeW / 2"
            :y1="(e.from?.y ?? 0) + compactLayout.nodeH / 2"
            :x2="(e.to?.x ?? 0) + compactLayout.nodeW / 2"
            :y2="(e.to?.y ?? 0) + compactLayout.nodeH / 2"
            stroke="#a5b4fc"
            stroke-width="2"
            marker-end="url(#join-arrow-compact)"
          />
          <g v-for="name in nodes" :key="'cn-' + name">
            <rect
              :x="compactLayout.positions[name]?.x ?? 0"
              :y="compactLayout.positions[name]?.y ?? 0"
              :width="compactLayout.nodeW"
              :height="compactLayout.nodeH"
              rx="8"
              fill="#eef2ff"
              stroke="#6366f1"
              stroke-width="1.5"
            />
            <title>{{ name }}</title>
            <text
              :x="(compactLayout.positions[name]?.x ?? 0) + compactLayout.nodeW / 2"
              :y="(compactLayout.positions[name]?.y ?? 0) + compactLayout.nodeH / 2 + 4"
              text-anchor="middle"
              class="text-[10px] fill-indigo-900 font-bold pointer-events-none"
            >
              {{ truncateName(name, 'compact') }}
            </text>
          </g>
        </svg>
      </div>
      <div class="mt-2 space-y-1">
        <button
          v-for="(p, i) in joinPaths.slice(0, 3)"
          :key="i"
          type="button"
          class="w-full text-left text-[10px] px-2 py-1 rounded bg-white border hover:border-indigo-300 font-mono text-gray-600 truncate"
          :title="`${p.source_table} → ${p.target_table}: ${p.condition}`"
          @click="emit('insert', p.snippet)"
        >
          {{ p.source_table }} → {{ p.target_table }}: {{ p.condition }}
        </button>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="showModal"
        class="fixed inset-0 z-[135] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm"
        @click.self="showModal = false"
      >
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[88vh] overflow-hidden flex flex-col">
          <div class="px-5 py-4 border-b flex justify-between items-center shrink-0">
            <div>
              <h3 class="font-bold text-gray-800">表关联图</h3>
              <p class="text-xs text-gray-500 mt-0.5">{{ nodes.length }} 张表 · {{ joinPaths.length }} 条 JOIN 路径 · 点击下方路径可插入 SQL</p>
            </div>
            <button class="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100" @click="showModal = false">
              <XMarkIcon class="w-5 h-5" />
            </button>
          </div>

          <div class="flex-1 overflow-auto p-5 custom-scrollbar">
            <div class="overflow-x-auto rounded-xl border bg-slate-50/50 p-4 mb-4">
              <svg :width="expandedLayout.svgWidth" :height="expandedLayout.svgHeight" class="bg-white rounded-lg border mx-auto block">
                <defs>
                  <marker id="join-arrow-expanded" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto">
                    <path d="M0,0 L8,4 L0,8 Z" fill="#6366f1" />
                  </marker>
                </defs>
                <line
                  v-for="(e, i) in expandedEdges"
                  :key="'ee-' + i"
                  :x1="(e.from?.x ?? 0) + expandedLayout.nodeW / 2"
                  :y1="(e.from?.y ?? 0) + expandedLayout.nodeH / 2"
                  :x2="(e.to?.x ?? 0) + expandedLayout.nodeW / 2"
                  :y2="(e.to?.y ?? 0) + expandedLayout.nodeH / 2"
                  stroke="#818cf8"
                  stroke-width="2.5"
                  marker-end="url(#join-arrow-expanded)"
                />
                <g v-for="name in nodes" :key="'en-' + name">
                  <rect
                    :x="expandedLayout.positions[name]?.x ?? 0"
                    :y="expandedLayout.positions[name]?.y ?? 0"
                    :width="expandedLayout.nodeW"
                    :height="expandedLayout.nodeH"
                    rx="10"
                    fill="#eef2ff"
                    stroke="#6366f1"
                    stroke-width="2"
                  />
                  <title>{{ name }}</title>
                  <text
                    :x="(expandedLayout.positions[name]?.x ?? 0) + expandedLayout.nodeW / 2"
                    :y="(expandedLayout.positions[name]?.y ?? 0) + expandedLayout.nodeH / 2 + 5"
                    text-anchor="middle"
                    class="text-xs fill-indigo-900 font-bold pointer-events-none"
                  >
                    {{ truncateName(name, 'expanded') }}
                  </text>
                </g>
              </svg>
            </div>

            <div class="space-y-2">
              <div class="text-[10px] font-black text-slate-500 uppercase tracking-widest">JOIN 路径</div>
              <button
                v-for="(p, i) in joinPaths"
                :key="'path-' + i"
                type="button"
                class="w-full text-left p-3 rounded-xl border border-gray-100 bg-gray-50/80 hover:border-indigo-300 hover:bg-indigo-50/40 transition-colors group"
                @click="emit('insert', p.snippet); showModal = false"
              >
                <div class="flex items-center justify-between gap-2 mb-1">
                  <span class="text-sm font-bold text-gray-800">{{ p.source_table }} → {{ p.target_table }}</span>
                  <span v-if="p.confidence != null" class="text-[10px] text-indigo-600 font-bold shrink-0">
                    置信度 {{ Math.round(p.confidence * 100) }}%
                  </span>
                </div>
                <div class="text-xs font-mono text-gray-600 break-all">{{ p.condition }}</div>
                <div class="text-[10px] text-indigo-500 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">点击插入 JOIN 片段</div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
