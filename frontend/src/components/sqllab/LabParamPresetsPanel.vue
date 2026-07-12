<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'

export type ParamPreset = { id: string; name: string; params: Record<string, any> }

const PRESETS_KEY = 'sqllab_param_presets_v1'

const props = defineProps<{
  open: boolean
  sourceId: number | null
  currentParams: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'apply', params: Record<string, any>): void
}>()

const { showToast } = useToast()
const presets = ref<ParamPreset[]>([])
const presetName = ref('')

const storageKey = () => `${PRESETS_KEY}_${props.sourceId || 'default'}`

const load = () => {
  try {
    const raw = localStorage.getItem(storageKey())
    presets.value = raw ? JSON.parse(raw) : []
  } catch {
    presets.value = []
  }
}

const save = () => localStorage.setItem(storageKey(), JSON.stringify(presets.value))

watch(() => props.sourceId, load)
onMounted(load)

const saveCurrent = () => {
  if (!presetName.value.trim()) return
  presets.value.unshift({
    id: Math.random().toString(36).slice(2),
    name: presetName.value.trim(),
    params: { ...props.currentParams },
  })
  presetName.value = ''
  save()
  showToast('参数预设已保存', 'success')
}

const apply = (p: ParamPreset) => {
  emit('apply', { ...p.params })
  emit('close')
  showToast(`已应用预设「${p.name}」`, 'info')
}

const remove = (id: string) => {
  presets.value = presets.value.filter(p => p.id !== id)
  save()
}
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-[130] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm" @click.self="emit('close')">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[80vh] flex flex-col">
      <div class="px-6 py-4 border-b flex justify-between">
        <h3 class="font-bold text-gray-800">参数预设</h3>
        <button class="text-gray-400" @click="emit('close')">✕</button>
      </div>
      <div class="p-4 border-b flex gap-2">
        <input v-model="presetName" placeholder="预设名称（如：上周华东）" class="flex-1 px-3 py-2 text-sm border rounded-lg" />
        <button class="px-4 py-2 bg-blue-600 text-white text-sm font-bold rounded-lg" @click="saveCurrent">保存当前</button>
      </div>
      <div class="flex-1 overflow-y-auto p-3 space-y-2">
        <div v-if="!presets.length" class="text-center py-8 text-gray-400 text-sm">暂无预设</div>
        <button
          v-for="p in presets"
          :key="p.id"
          type="button"
          class="w-full text-left p-3 rounded-xl border hover:border-indigo-300 group flex justify-between"
          @click="apply(p)"
        >
          <div>
            <div class="font-bold text-sm">{{ p.name }}</div>
            <code class="text-[10px] text-gray-500">{{ JSON.stringify(p.params) }}</code>
          </div>
          <span class="text-red-400 text-xs opacity-0 group-hover:opacity-100" @click.stop="remove(p.id)">删</span>
        </button>
      </div>
    </div>
  </div>
</template>
