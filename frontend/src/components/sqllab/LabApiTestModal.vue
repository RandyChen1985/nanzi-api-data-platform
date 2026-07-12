<script setup lang="ts">
import { ref, watch } from 'vue'
import axios from '@/utils/axios'

const props = defineProps<{
  open: boolean
  resourceKey: string
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const loading = ref(false)
const result = ref<any>(null)
const error = ref('')

const runTest = async () => {
  if (!props.resourceKey) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const res = await axios.get(`/api/portal/meta/resources/${props.resourceKey}/test`, { params: { page: 1, size: 5 } })
    result.value = res.data
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

watch(() => props.open, (v) => { if (v) runTest() })
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-[150] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm" @click.self="emit('close')">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
      <div class="px-6 py-4 border-b flex justify-between">
        <h3 class="font-bold">API 在线调试 · {{ resourceKey }}</h3>
        <button @click="emit('close')">✕</button>
      </div>
      <div class="p-4 flex-1 overflow-auto">
        <div v-if="loading" class="text-center py-8 text-gray-400">请求中...</div>
        <div v-else-if="error" class="text-red-600 text-sm font-mono">{{ error }}</div>
        <pre v-else class="text-xs font-mono bg-gray-900 text-green-400 p-4 rounded-xl overflow-auto">{{ JSON.stringify(result, null, 2) }}</pre>
      </div>
      <div class="p-4 border-t flex gap-2 justify-end">
        <button class="px-4 py-2 border rounded-lg" @click="runTest">重新请求</button>
        <button class="px-4 py-2 bg-blue-600 text-white rounded-lg font-bold" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>
