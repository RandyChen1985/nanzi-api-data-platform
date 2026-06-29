<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'

withDefaults(
  defineProps<{
    product: {
      product_key: string
      display_name: string
      summary?: string
      domain: string
      status: number
      featured: boolean
      pending_requests?: number
      has_access: boolean
      data_source?: string
      resource_mode?: string
      owner_name?: string
      health_score?: number | null
    }
    viewTab: 'all' | 'mine'
    statusLabel: string
    statusClass: string
    playgroundRoute: RouteLocationRaw | null
    formatCalls: string
    variant?: 'row' | 'card'
  }>(),
  { variant: 'row' },
)

defineEmits<{ open: []; edit: [] }>()
</script>

<template>
  <div
    v-if="variant === 'card'"
    class="flex h-full flex-col"
  >
    <div class="flex-1 min-w-0 cursor-pointer" @click="$emit('open')">
      <div class="flex items-center gap-2 flex-wrap">
        <h3 class="text-base font-bold text-gray-900 line-clamp-1">{{ product.display_name }}</h3>
        <span class="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full shrink-0">{{ product.domain }}</span>
        <span v-if="viewTab === 'mine'" :class="statusClass" class="text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0">
          {{ statusLabel }}
        </span>
        <span v-if="product.featured" class="text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full shrink-0">精选</span>
        <span
          v-if="viewTab === 'mine' && (product.pending_requests || 0) > 0"
          class="text-[10px] bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium shrink-0"
        >
          {{ product.pending_requests }} 待审批
        </span>
        <span
          :class="product.has_access ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
          class="text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0"
        >
          {{ product.has_access ? '已授权' : '需申请' }}
        </span>
      </div>
      <p class="text-sm text-gray-600 mt-2 line-clamp-2">{{ product.summary || '暂无简介' }}</p>
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1 mt-3 text-xs text-gray-400">
        <span v-if="product.data_source">{{ product.data_source }}</span>
        <span v-if="product.resource_mode">{{ product.resource_mode }} 模式</span>
        <span v-if="product.owner_name">负责人 {{ product.owner_name }}</span>
        <span>{{ formatCalls }} 次/周</span>
        <span
          v-if="product.health_score != null"
          :class="product.health_score >= 80 ? 'text-green-600' : product.health_score >= 60 ? 'text-amber-600' : 'text-red-500'"
        >
          健康分 {{ product.health_score }}
        </span>
      </div>
    </div>
    <div class="mt-4 flex items-center justify-end gap-2" @click.stop>
      <router-link
        v-if="product.has_access && playgroundRoute"
        :to="playgroundRoute"
        class="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700"
      >
        在线试用
      </router-link>
      <button
        v-if="viewTab === 'mine'"
        class="px-3 py-1.5 border border-gray-200 rounded-lg text-xs hover:bg-gray-50"
        @click="$emit('edit')"
      >
        编辑
      </button>
      <button class="p-1.5 text-gray-300 hover:text-indigo-600" @click="$emit('open')">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  </div>
  <div v-else class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
    <div class="flex-1 min-w-0 cursor-pointer" @click="$emit('open')">
      <div class="flex items-center gap-2 flex-wrap">
        <h3 class="text-lg font-bold text-gray-900">{{ product.display_name }}</h3>
        <span class="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{{ product.domain }}</span>
        <span v-if="viewTab === 'mine'" :class="statusClass" class="text-[10px] px-2 py-0.5 rounded-full font-medium">
          {{ statusLabel }}
        </span>
        <span v-if="product.featured" class="text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">精选</span>
        <span
          v-if="viewTab === 'mine' && (product.pending_requests || 0) > 0"
          class="text-[10px] bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium"
        >
          {{ product.pending_requests }} 待审批
        </span>
        <span
          :class="product.has_access ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
          class="text-[10px] px-2 py-0.5 rounded-full font-medium"
        >
          {{ product.has_access ? '✅ 已授权' : '🔒 需申请权限' }}
        </span>
      </div>
      <p class="text-sm text-gray-600 mt-2 line-clamp-2">{{ product.summary || '暂无简介' }}</p>
      <div class="flex flex-wrap items-center gap-3 mt-3 text-xs text-gray-400">
        <span v-if="product.data_source">{{ product.data_source }}</span>
        <span v-if="product.resource_mode">{{ product.resource_mode }} 模式</span>
        <span v-if="product.owner_name">负责人 {{ product.owner_name }}</span>
        <span>{{ formatCalls }} 次/周</span>
        <span
          v-if="product.health_score != null"
          :class="product.health_score >= 80 ? 'text-green-600' : product.health_score >= 60 ? 'text-amber-600' : 'text-red-500'"
        >
          健康分 {{ product.health_score }}
        </span>
      </div>
    </div>
    <div class="flex items-center gap-2 flex-shrink-0">
      <router-link
        v-if="product.has_access && playgroundRoute"
        :to="playgroundRoute"
        class="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700"
        @click.stop
      >
        在线试用
      </router-link>
      <button
        v-if="viewTab === 'mine'"
        class="px-3 py-1.5 border border-gray-200 rounded-lg text-xs hover:bg-gray-50"
        @click.stop="$emit('edit')"
      >
        编辑
      </button>
      <button class="p-2 text-gray-300 hover:text-indigo-600" @click="$emit('open')">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  </div>
</template>
