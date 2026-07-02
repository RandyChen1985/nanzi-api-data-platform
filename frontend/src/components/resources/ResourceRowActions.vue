<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import {
  DocumentMagnifyingGlassIcon,
  CommandLineIcon,
  ClockIcon,
  PlayIcon,
  EllipsisVerticalIcon,
} from '@heroicons/vue/24/outline'
import type { Resource } from '@/types/resource'
import { getSystemResourceActionKind, isLockedSystemResource } from '@/types/resource'
import { buildPlaygroundRoute } from '@/utils/playground'

const props = defineProps<{
  resource: Resource
  canEdit: boolean
  canDelete: boolean
  canExport: boolean
  canManageSpecial: boolean
  catalogStatus?: number | null
  canUnpublishCatalog?: boolean
}>()

const emit = defineEmits<{
  logs: []
  export: []
  delete: []
  previewSql: []
  openTtl: []
  openSqlTest: []
  copyApi: [type: 'resource' | 'query']
  publishCatalog: []
  unpublishCatalog: []
}>()

const MENU_WIDTH = 176
const VIEWPORT_PADDING = 8

const menuOpen = ref(false)
const triggerRef = ref<HTMLElement | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
const menuStyle = ref({ top: '0px', left: '0px' })

const updateMenuPosition = () => {
  const trigger = triggerRef.value
  if (!trigger) return

  const rect = trigger.getBoundingClientRect()
  const menuHeight = dropdownRef.value?.offsetHeight ?? 240

  let top = rect.bottom + 4
  let left = rect.right - MENU_WIDTH

  if (top + menuHeight > window.innerHeight - VIEWPORT_PADDING) {
    top = rect.top - menuHeight - 4
  }
  top = Math.max(VIEWPORT_PADDING, top)
  left = Math.max(VIEWPORT_PADDING, Math.min(left, window.innerWidth - MENU_WIDTH - VIEWPORT_PADDING))

  menuStyle.value = { top: `${top}px`, left: `${left}px` }
}

watch(menuOpen, async (open) => {
  if (!open) return
  await nextTick()
  updateMenuPosition()
  await nextTick()
  updateMenuPosition()
})

const closeOnOutside = (e: MouseEvent) => {
  const target = e.target as Node
  if (triggerRef.value?.contains(target)) return
  if (dropdownRef.value?.contains(target)) return
  menuOpen.value = false
}

const onScrollOrResize = () => {
  if (menuOpen.value) updateMenuPosition()
}

onMounted(() => {
  document.addEventListener('click', closeOnOutside)
  window.addEventListener('scroll', onScrollOrResize, true)
  window.addEventListener('resize', onScrollOrResize)
})
onUnmounted(() => {
  document.removeEventListener('click', closeOnOutside)
  window.removeEventListener('scroll', onScrollOrResize, true)
  window.removeEventListener('resize', onScrollOrResize)
})

const onDeleteClick = () => {
  if (props.catalogStatus === 1) return
  emit('delete')
  menuOpen.value = false
}
const showEditLink = computed(() => !actionKind.value)
const showDebugLink = computed(() => !actionKind.value || actionKind.value === 'metadata_search_debug_only')
const showMoreMenu = computed(() => !actionKind.value || actionKind.value === 'sql_execute')
</script>

<template>
  <div class="flex items-center justify-end gap-1 shrink-0 whitespace-nowrap" @click.stop>
    <router-link
      v-if="showEditLink"
      :to="`/dashboard/resources/${resource.resource_key}`"
      class="inline-flex items-center px-2.5 py-1 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-md transition-colors"
    >
      {{ canEdit ? '编辑' : '详情' }}
    </router-link>

    <router-link
      v-if="showDebugLink"
      :to="buildPlaygroundRoute(resource)"
      class="inline-flex items-center px-2.5 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-md transition-colors"
      title="API 调试"
    >
      调试
    </router-link>

    <template v-if="actionKind === 'sql_execute' && canManageSpecial">
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

    <div v-if="showMoreMenu" class="relative">
      <button
        ref="triggerRef"
        class="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
        aria-label="更多操作"
        @click.stop="menuOpen = !menuOpen"
      >
        <EllipsisVerticalIcon class="w-4 h-4" />
      </button>
      <Teleport to="body">
        <div
          v-if="menuOpen"
          ref="dropdownRef"
          class="fixed w-44 bg-white border border-gray-200 rounded-lg shadow-lg z-[200] py-1 text-sm"
          :style="menuStyle"
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
            v-if="canEdit && resource.resource_group?.toLowerCase() !== 'system'"
            class="w-full text-left px-3 py-2 hover:bg-indigo-50 text-indigo-700"
            @click="emit('publishCatalog'); menuOpen = false"
          >
            {{ catalogStatus === 1 ? '更新目录信息' : catalogStatus === 0 ? '发布到目录' : '重新发布到目录' }}
          </button>
          <button
            v-if="canUnpublishCatalog && catalogStatus === 1"
            class="w-full text-left px-3 py-2 hover:bg-amber-50 text-amber-700"
            @click="emit('unpublishCatalog'); menuOpen = false"
          >
            从目录下架
          </button>
          <button
            v-if="canExport"
            class="w-full text-left px-3 py-2 hover:bg-gray-50"
            @click="emit('export'); menuOpen = false"
          >
            导出配置 JSON
          </button>
          <hr v-if="canDelete && !isLockedSystemResource(resource)" class="my-1 border-gray-100" />
          <button
            v-if="canDelete && !isLockedSystemResource(resource)"
            class="w-full text-left px-3 py-2"
            :class="catalogStatus === 1 ? 'text-gray-400 cursor-not-allowed' : 'hover:bg-red-50 text-red-600'"
            :disabled="catalogStatus === 1"
            :title="catalogStatus === 1 ? '已上架到目录，请先从目录下架后再删除' : undefined"
            @click="onDeleteClick"
          >
            删除资源
          </button>
        </div>
      </Teleport>
    </div>
  </div>
</template>
