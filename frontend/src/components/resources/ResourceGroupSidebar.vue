<script setup lang="ts">
import { FolderIcon, Cog6ToothIcon, ChevronDoubleLeftIcon, ChevronDoubleRightIcon } from '@heroicons/vue/24/outline'
import ClearableInput from '@/components/common/ClearableInput.vue'
import type { ResourceGroupTab } from '@/types/resource'

defineProps<{
  collapsed: boolean
  searchGroupQuery: string
  tabs: ResourceGroupTab[]
  activeTab: string
}>()

const emit = defineEmits<{
  'update:collapsed': [value: boolean]
  'update:searchGroupQuery': [value: string]
  'update:activeTab': [value: string]
}>()
</script>

<template>
  <div
    class="bg-gray-50/50 border-r border-gray-200 flex flex-col shrink-0 transition-all duration-300 ease-in-out relative group/sidebar"
    :class="collapsed ? 'w-14' : 'w-64'"
  >
    <div class="p-3 border-b border-gray-200 flex items-center justify-between h-14 bg-white">
      <div v-if="!collapsed" class="w-full">
        <h2 class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5">资源分组</h2>
        <ClearableInput
          :model-value="searchGroupQuery"
          show-search-icon
          wrapper-class="border-0 bg-gray-100 rounded"
          input-class="py-1 text-xs"
          placeholder="搜索分组..."
          @update:model-value="emit('update:searchGroupQuery', $event)"
        />
      </div>
      <button
        v-if="collapsed"
        class="mx-auto text-gray-400 hover:text-blue-600 p-1 hover:bg-gray-100 rounded"
        title="展开"
        @click="emit('update:collapsed', false)"
      >
        <FolderIcon class="w-5 h-5" />
      </button>
    </div>

    <button
      class="absolute -right-3 top-16 bg-white border border-gray-200 rounded-full p-1 shadow-sm text-gray-400 hover:text-blue-600 z-10 opacity-0 group-hover/sidebar:opacity-100 transition-opacity"
      :title="collapsed ? '展开侧边栏' : '折叠侧边栏'"
      @click="emit('update:collapsed', !collapsed)"
    >
      <component :is="collapsed ? ChevronDoubleRightIcon : ChevronDoubleLeftIcon" class="w-3 h-3" />
    </button>

    <div class="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
      <button
        v-for="tab in tabs"
        :key="tab.name"
        class="w-full flex items-center rounded-md transition-all duration-200 group relative"
        :class="[
          activeTab === tab.name
            ? (tab.isSystem ? 'bg-amber-50 text-amber-800 shadow-sm ring-1 ring-amber-200' : 'bg-white text-blue-600 shadow-sm ring-1 ring-gray-200')
            : 'text-gray-600 hover:bg-white hover:shadow-sm',
          collapsed ? 'justify-center py-2' : 'justify-between px-3 py-2',
        ]"
        :title="collapsed ? tab.label : ''"
        @click="emit('update:activeTab', tab.name)"
      >
        <div class="flex items-center overflow-hidden">
          <Cog6ToothIcon
            v-if="tab.isSystem"
            class="w-4 h-4 shrink-0"
            :class="[activeTab === tab.name ? 'text-amber-600' : 'text-amber-500', collapsed ? '' : 'mr-3']"
          />
          <FolderIcon
            v-else
            class="w-4 h-4 shrink-0"
            :class="[activeTab === tab.name ? 'text-blue-500' : 'text-gray-400', collapsed ? '' : 'mr-3']"
          />
          <span v-if="!collapsed" class="truncate text-sm font-medium">{{ tab.label }}</span>
        </div>
        <span
          v-if="!collapsed"
          class="ml-2 py-0.5 px-1.5 rounded text-[10px] font-bold"
          :class="tab.isSystem
            ? (activeTab === tab.name ? 'bg-amber-50 text-amber-700' : 'bg-amber-100 text-amber-700')
            : (activeTab === tab.name ? 'bg-blue-50 text-blue-600' : 'bg-gray-200 text-gray-500')"
        >
          {{ tab.count }}
        </span>
        <div
          v-if="collapsed"
          class="absolute left-full top-1/2 -translate-y-1/2 ml-2 bg-gray-900 text-white text-xs px-2 py-1 rounded shadow-lg whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none z-50"
        >
          {{ tab.label }} ({{ tab.count }})
        </div>
      </button>
    </div>
  </div>
</template>
