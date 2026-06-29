<script setup lang="ts">
import type { AccessLog } from '@/types/resource'

defineProps<{
  open: boolean
  resourceKey: string
  logs: AccessLog[]
  loading: boolean
  selectedLog: AccessLog | null
  formatDate: (dateStr?: string) => string
}>()

const emit = defineEmits<{
  close: []
  refresh: []
  selectLog: [log: AccessLog | null]
}>()

const formatParams = (raw?: string) => {
  try {
    return JSON.stringify(JSON.parse(raw || '{}'), null, 2)
  } catch {
    return raw || '{}'
  }
}
</script>

<template>
  <teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex justify-end">
      <div class="absolute inset-0 bg-black/40" @click="emit('close')" />
      <div class="relative w-full max-w-4xl bg-white shadow-2xl flex flex-col h-full animate-slide-in">
        <div class="px-5 py-4 border-b border-gray-200 flex items-center justify-between shrink-0">
          <div>
            <h3 class="text-lg font-semibold text-gray-900">调用日志</h3>
            <p class="text-xs text-gray-500 font-mono mt-0.5">{{ resourceKey }}</p>
          </div>
          <div class="flex gap-2">
            <button
              class="px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-lg"
              @click="emit('refresh')"
            >
              刷新
            </button>
            <button
              class="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
              @click="emit('close')"
            >
              关闭
            </button>
          </div>
        </div>

        <div class="flex flex-1 min-h-0">
          <div class="flex-1 overflow-auto border-r border-gray-100">
            <table class="min-w-full divide-y divide-gray-200 text-xs">
              <thead class="bg-gray-50 sticky top-0">
                <tr>
                  <th class="px-3 py-2 text-left text-gray-500 font-medium">时间</th>
                  <th class="px-3 py-2 text-left text-gray-500 font-medium">用户</th>
                  <th class="px-3 py-2 text-left text-gray-500 font-medium">状态</th>
                  <th class="px-3 py-2 text-left text-gray-500 font-medium">耗时</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-if="loading">
                  <td colspan="4" class="px-6 py-12 text-center text-gray-500">加载中...</td>
                </tr>
                <tr v-else-if="logs.length === 0">
                  <td colspan="4" class="px-6 py-12 text-center text-gray-400 italic">暂无最近访问记录</td>
                </tr>
                <tr
                  v-for="log in logs"
                  :key="log.id"
                  class="cursor-pointer hover:bg-gray-50"
                  :class="{ 'bg-blue-50': selectedLog?.id === log.id }"
                  @click="emit('selectLog', log)"
                >
                  <td class="px-3 py-2 text-gray-500 whitespace-nowrap">{{ formatDate(log.created_at) }}</td>
                  <td class="px-3 py-2 font-medium text-gray-900">{{ log.user_name }}</td>
                  <td class="px-3 py-2">
                    <span
                      class="px-1.5 py-0.5 rounded text-[10px] font-medium"
                      :class="log.status_code >= 400 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'"
                    >
                      {{ log.status_code }}
                    </span>
                  </td>
                  <td class="px-3 py-2 text-gray-500">{{ log.process_time_ms.toFixed(0) }}ms</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="selectedLog" class="w-80 shrink-0 overflow-y-auto bg-gray-50 p-4 text-sm">
            <h4 class="font-semibold text-gray-800 mb-3">请求详情</h4>
            <p class="text-[10px] font-mono text-gray-400 mb-3 break-all">{{ selectedLog.trace_id }}</p>
            <div class="space-y-3">
              <div class="bg-white p-2 rounded border border-gray-100">
                <span class="text-xs text-gray-500">请求</span>
                <div class="font-medium text-xs break-all">{{ selectedLog.method }} {{ selectedLog.endpoint }}</div>
              </div>
              <div class="bg-white p-2 rounded border border-gray-100">
                <span class="text-xs text-gray-500">客户端</span>
                <div class="font-medium text-xs">{{ selectedLog.client_ip }} / {{ selectedLog.user_name }}</div>
              </div>
              <div>
                <span class="text-xs text-gray-500">请求参数</span>
                <pre class="mt-1 bg-gray-900 text-green-400 text-[10px] p-2 rounded max-h-48 overflow-auto">{{ formatParams(selectedLog.request_params) }}</pre>
              </div>
            </div>
            <button class="mt-4 text-xs text-gray-500 hover:text-gray-700" @click="emit('selectLog', null)">收起详情</button>
          </div>
          <div v-else class="w-48 shrink-0 flex items-center justify-center text-xs text-gray-400 p-4 text-center bg-gray-50">
            点击左侧记录查看详情
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
@keyframes slide-in {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}
.animate-slide-in {
  animation: slide-in 0.2s ease-out;
}
</style>
