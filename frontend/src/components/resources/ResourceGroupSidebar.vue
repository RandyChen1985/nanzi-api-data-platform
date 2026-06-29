<script setup lang="ts">
import { FolderIcon, ChevronDoubleLeftIcon, ChevronDoubleRightIcon } from '@heroicons/vue/24/outline'

defineProps<{
  collapsed: boolean
  searchGroupQuery: string
  tabs: { name: string; label: string; count: number }[]
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
        <div class="relative">
          <input
            :value="searchGroupQuery"
            type="text"
            placeholder="搜索分组..."
            class="w-full pl-7 pr-2 py-1 bg-gray-100 border-none rounded text-xs focus:ring-1 focus:ring-blue-500 outline-none"
            @input="emit('update:searchGroupQuery', ($event.target as HTMLInputElement).value)"
          />
          <svg class="w-3 h-3 text-gray-400 absolute left-2 top-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
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
          activeTab === tab.name ? 'bg-white text-blue-600 shadow-sm ring-1 ring-gray-200' : 'text-gray-600 hover:bg-white hover:shadow-sm',
          collapsed ? 'justify-center py-2' : 'justify-between px-3 py-2',
        ]"
        :title="collapsed ? tab.label : ''"
        @click="emit('update:activeTab', tab.name)"
      >
        <div class="flex items-center overflow-hidden">
          <FolderIcon
            class="w-4 h-4 shrink-0"
            :class="[activeTab === tab.name ? 'text-blue-500' : 'text-gray-400', collapsed ? '' : 'mr-3']"
          />
          <span v-if="!collapsed" class="truncate text-sm font-medium">{{ tab.label }}</span>
        </div>
        <span
          v-if="!collapsed"
          class="ml-2 py-0.5 px-1.5 rounded text-[10px] font-bold"
          :class="activeTab === tab.name ? 'bg-blue-50 text-blue-600' : 'bg-gray-200 text-gray-500'"
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
