<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'

defineProps<{
  product: {
    product_key: string
    display_name: string
    summary?: string
    domain: string
    has_access: boolean
    owner_name?: string
    data_source?: string
    health_score?: number | null
    calls_7d: number
  }
  playgroundRoute: RouteLocationRaw | null
  formatCalls: string
}>()

defineEmits<{ open: [] }>()
</script>

<template>
  <article
    class="group relative flex h-full flex-col overflow-hidden rounded-xl border border-gray-100 bg-white p-5 transition-all hover:border-amber-200/80 hover:shadow-sm"
    @click="$emit('open')"
  >
    <!-- subtle featured accent -->
    <div class="absolute inset-y-0 left-0 w-1 bg-amber-400/70" aria-hidden="true" />

    <div class="flex items-start justify-between gap-3 pl-1">
      <div class="flex flex-wrap items-center gap-2 min-w-0">
        <h3 class="text-base font-bold text-gray-900 truncate group-hover:text-indigo-600 transition-colors">
          {{ product.display_name }}
        </h3>
        <span class="text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full shrink-0">精选</span>
        <span class="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full shrink-0">{{ product.domain }}</span>
      </div>
      <span
        :class="product.has_access ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
        class="text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0"
      >
        {{ product.has_access ? '已授权' : '需申请' }}
      </span>
    </div>

    <p class="mt-2 pl-1 text-sm text-gray-600 line-clamp-2 flex-1">
      {{ product.summary || '暂无产品简介' }}
    </p>

    <div class="mt-3 pl-1 flex flex-wrap items-center gap-3 text-xs text-gray-400">
      <span v-if="product.data_source">{{ product.data_source }}</span>
      <span v-if="product.owner_name">负责人 {{ product.owner_name }}</span>
      <span>{{ formatCalls }} 次/周</span>
      <span
        v-if="product.health_score != null"
        :class="product.health_score >= 80 ? 'text-green-600' : product.health_score >= 60 ? 'text-amber-600' : 'text-red-500'"
      >
        健康分 {{ product.health_score }}
      </span>
    </div>

    <div class="mt-4 pl-1 flex justify-end" @click.stop>
      <router-link
        v-if="product.has_access && playgroundRoute"
        :to="playgroundRoute"
        class="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700"
      >
        在线试用
      </router-link>
      <button
        v-else
        type="button"
        class="px-3 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 hover:bg-gray-50"
        @click="$emit('open')"
      >
        查看详情
      </button>
    </div>
  </article>
</template>
