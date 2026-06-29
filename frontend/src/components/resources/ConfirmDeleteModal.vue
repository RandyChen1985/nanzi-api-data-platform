<script setup lang="ts">
defineProps<{
  open: boolean
  title: string
  description: string
  keys: string[]
  loading?: boolean
}>()

const emit = defineEmits<{ close: []; confirm: [] }>()
</script>

<template>
  <teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/40" @click="emit('close')" />
      <div class="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6">
        <div class="flex gap-4">
          <div class="shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
            <svg class="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <h3 class="text-lg font-semibold text-gray-900">{{ title }}</h3>
            <p class="text-sm text-gray-500 mt-1">{{ description }}</p>
            <ul v-if="keys.length" class="mt-3 max-h-32 overflow-y-auto text-xs font-mono bg-gray-50 rounded-lg p-2 space-y-1">
              <li v-for="k in keys.slice(0, 8)" :key="k" class="text-gray-700 truncate">{{ k }}</li>
              <li v-if="keys.length > 8" class="text-gray-400">…还有 {{ keys.length - 8 }} 项</li>
            </ul>
          </div>
        </div>
        <div class="mt-6 flex justify-end gap-3">
          <button
            class="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
            :disabled="loading"
            @click="emit('close')"
          >
            取消
          </button>
          <button
            class="px-4 py-2 text-sm text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
            :disabled="loading"
            @click="emit('confirm')"
          >
            {{ loading ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </teleport>
</template>
