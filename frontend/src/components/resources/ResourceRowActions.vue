<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  DocumentMagnifyingGlassIcon,
  CommandLineIcon,
  ClockIcon,
  PlayIcon,
  EllipsisVerticalIcon,
} from '@heroicons/vue/24/outline'
import type { Resource } from '@/types/resource'

const props = defineProps<{
  resource: Resource
  canEdit: boolean
  canDelete: boolean
  canExport: boolean
  canManageSpecial: boolean
}>()

const emit = defineEmits<{
  logs: []
  export: []
  delete: []
  previewSql: []
  openTtl: []
  openSqlTest: []
  copyApi: [type: 'resource' | 'query']
}>()

const menuOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)

const closeOnOutside = (e: MouseEvent) => {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) {
    menuOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', closeOnOutside))
onUnmounted(() => document.removeEventListener('click', closeOnOutside))

const isSystemSql = props.resource.resource_key === 'system.sql.execute'
</script>

<template>
  <div class="flex items-center justify-end gap-1 shrink-0 whitespace-nowrap" @click.stop>
    <router-link
      v-if="!isSystemSql"
      :to="`/dashboard/resources/${resource.resource_key}`"
      class="inline-flex items-center px-2.5 py-1 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-md transition-colors"
    >
      {{ canEdit ? '编辑' : '详情' }}
    </router-link>

    <router-link
      v-if="!isSystemSql"
      :to="`/dashboard/playground?resource=${resource.resource_key}`"
      class="inline-flex items-center px-2.5 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-md transition-colors"
      title="API 调试"
    >
      调试
    </router-link>

    <template v-if="isSystemSql && canManageSpecial">
      <button
        class="p-1.5 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg"
        title="设置 TTL"
        aria-label="设置 TTL"
        @click="emit('openTtl')"
      >
        <ClockIcon class="w-4 h-4" />
      </button>
      <button
        class="p-1.5 text-indigo-500 hover:text-indigo-700 hover:bg-indigo-50 rounded-lg"
        title="SQL 测试"
        aria-label="SQL 测试"
        @click="emit('openSqlTest')"
      >
        <PlayIcon class="w-4 h-4" />
      </button>
    </template>

    <div ref="menuRef" class="relative">
      <button
        class="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
        aria-label="更多操作"
        @click.stop="menuOpen = !menuOpen"
      >
        <EllipsisVerticalIcon class="w-4 h-4" />
      </button>
      <div
        v-if="menuOpen"
        class="absolute right-0 mt-1 w-44 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1 text-sm"
      >
        <button class="w-full text-left px-3 py-2 hover:bg-gray-50 flex items-center gap-2" @click="emit('logs'); menuOpen = false">
          <DocumentMagnifyingGlassIcon class="w-4 h-4 text-gray-400" /> 调用日志
        </button>
        <button
          v-if="resource.resource_mode === 'SQL'"
          class="w-full text-left px-3 py-2 hover:bg-gray-50 flex items-center gap-2"
          @click="emit('previewSql'); menuOpen = false"
        >
          <CommandLineIcon class="w-4 h-4 text-gray-400" /> 预览 SQL
        </button>
        <button class="w-full text-left px-3 py-2 hover:bg-gray-50" @click="emit('copyApi', 'resource'); menuOpen = false">
          复制资源接口 URL
        </button>
        <button class="w-full text-left px-3 py-2 hover:bg-gray-50" @click="emit('copyApi', 'query'); menuOpen = false">
          复制通用 Query URL
        </button>
        <button
          v-if="canExport"
          class="w-full text-left px-3 py-2 hover:bg-gray-50"
          @click="emit('export'); menuOpen = false"
        >
          导出配置 JSON
        </button>
        <hr v-if="canDelete && resource.resource_mode !== 'SYSTEM'" class="my-1 border-gray-100" />
        <button
          v-if="canDelete && resource.resource_mode !== 'SYSTEM'"
          class="w-full text-left px-3 py-2 hover:bg-red-50 text-red-600"
          @click="emit('delete'); menuOpen = false"
        >
          删除资源
        </button>
      </div>
    </div>
  </div>
</template>
