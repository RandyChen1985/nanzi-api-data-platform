<script setup lang="ts">
defineProps<{
  variant: 'no-resources' | 'no-results' | 'no-permission'
  canCreate: boolean
}>()

const emit = defineEmits<{ clearFilters: [] }>()
</script>

<template>
  <div class="px-6 py-16 text-center">
    <svg class="mx-auto h-14 w-14 text-gray-200 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>

    <template v-if="variant === 'no-resources'">
      <h3 class="text-base font-semibold text-gray-700 mb-1">还没有 API 资源</h3>
      <p class="text-sm text-gray-500 mb-6 max-w-md mx-auto">创建表映射或 SQL 资源，将数据封装为可治理的 RESTful 接口。</p>
      <div v-if="canCreate" class="flex flex-wrap justify-center gap-3">
        <router-link
          to="/dashboard/resources/create"
          class="inline-flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          新建资源
        </router-link>
        <router-link
          to="/dashboard/lab"
          class="inline-flex items-center gap-2 bg-white border border-gray-300 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50"
        >
          从 SQL 实验室发布
        </router-link>
      </div>
    </template>

    <template v-else-if="variant === 'no-results'">
      <h3 class="text-base font-semibold text-gray-700 mb-1">没有匹配的资源</h3>
      <p class="text-sm text-gray-500 mb-4">试试调整搜索关键词或筛选条件。</p>
      <button
        class="text-sm text-blue-600 hover:text-blue-800 font-medium underline"
        @click="emit('clearFilters')"
      >
        清除全部筛选
      </button>
    </template>

    <template v-else>
      <h3 class="text-base font-semibold text-gray-700 mb-1">暂无可访问的资源</h3>
      <p class="text-sm text-gray-500">请联系管理员为您开通接口资源权限。</p>
    </template>
  </div>
</template>
