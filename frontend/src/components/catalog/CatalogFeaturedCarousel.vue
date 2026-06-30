<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/vue/24/outline'
import CatalogFeaturedCard from '@/components/catalog/CatalogFeaturedCard.vue'
import type { CatalogPlaygroundProduct } from '@/utils/catalog'

interface FeaturedProduct {
  product_key: string
  display_name: string
  summary?: string
  domain: string
  featured?: boolean
  has_access: boolean
  owner_name?: string
  data_source?: string
  health_score?: number | null
  calls_7d: number
  resource_group?: string
  primary_resource_key?: string
}

const props = defineProps<{
  products: FeaturedProduct[]
  playgroundRoute: (p: CatalogPlaygroundProduct) => RouteLocationRaw | null
  formatCalls: (n: number) => string
}>()

const emit = defineEmits<{ open: [key: string] }>()

const trackRef = ref<HTMLElement | null>(null)
const paused = ref(false)
const visibleCount = ref(3)

const updateVisibleCount = () => {
  const w = window.innerWidth
  if (w >= 1024) visibleCount.value = 3
  else if (w >= 768) visibleCount.value = 2
  else visibleCount.value = 1
}

const canScroll = computed(() => props.products.length > visibleCount.value)

const getScrollStep = () => {
  const el = trackRef.value
  if (!el) return 0
  const card = el.querySelector('[data-featured-card]') as HTMLElement | null
  if (!card) return el.clientWidth
  const gap = 12
  return card.offsetWidth + gap
}

const scrollByCards = (direction: 1 | -1) => {
  const el = trackRef.value
  if (!el) return
  const step = getScrollStep()
  const maxScroll = Math.max(0, el.scrollWidth - el.clientWidth)
  let next = el.scrollLeft + direction * step
  if (next > maxScroll + 2) next = 0
  else if (next < 0) next = maxScroll
  el.scrollTo({ left: next, behavior: 'smooth' })
}

let autoTimer: ReturnType<typeof setInterval> | null = null

const stopAuto = () => {
  if (autoTimer) {
    clearInterval(autoTimer)
    autoTimer = null
  }
}

const startAuto = () => {
  stopAuto()
  if (!canScroll.value || paused.value) return
  autoTimer = setInterval(() => scrollByCards(1), 5000)
}

const onUserInteract = () => {
  paused.value = true
  stopAuto()
  window.setTimeout(() => {
    paused.value = false
    startAuto()
  }, 8000)
}

onMounted(() => {
  updateVisibleCount()
  window.addEventListener('resize', updateVisibleCount)
  nextTick(startAuto)
})

onUnmounted(() => {
  stopAuto()
  window.removeEventListener('resize', updateVisibleCount)
})

watch(
  () => props.products.length,
  () => nextTick(startAuto),
)
watch(canScroll, (v) => (v ? startAuto() : stopAuto()))
</script>

<template>
  <div
    class="group/carousel relative"
    @mouseenter="paused = true; stopAuto()"
    @mouseleave="paused = false; startAuto()"
  >
    <button
      v-if="canScroll"
      type="button"
      class="absolute left-0 top-1/2 -translate-y-1/2 z-10 -ml-3 hidden sm:flex h-9 w-9 items-center justify-center rounded-full border border-gray-200 bg-white shadow-md text-gray-600 hover:text-indigo-600 hover:border-indigo-200 opacity-0 pointer-events-none group-hover/carousel:opacity-100 group-hover/carousel:pointer-events-auto transition-opacity duration-200"
      aria-label="向左滚动"
      @click="scrollByCards(-1); onUserInteract()"
    >
      <ChevronLeftIcon class="w-5 h-5" />
    </button>

    <div
      ref="trackRef"
      class="featured-carousel-track flex gap-3 overflow-x-auto scroll-smooth snap-x snap-mandatory custom-scrollbar pb-1 -mx-1 px-1"
      @wheel.passive="onUserInteract"
      @touchstart.passive="onUserInteract"
    >
      <div
        v-for="p in products"
        :key="p.product_key"
        data-featured-card
        class="featured-carousel-card shrink-0 snap-start cursor-pointer"
      >
        <CatalogFeaturedCard
          :product="p"
          :playground-route="playgroundRoute(p)"
          :format-calls="formatCalls(p.calls_7d)"
          @open="emit('open', p.product_key)"
        />
      </div>
    </div>

    <button
      v-if="canScroll"
      type="button"
      class="absolute right-0 top-1/2 -translate-y-1/2 z-10 -mr-3 hidden sm:flex h-9 w-9 items-center justify-center rounded-full border border-gray-200 bg-white shadow-md text-gray-600 hover:text-indigo-600 hover:border-indigo-200 opacity-0 pointer-events-none group-hover/carousel:opacity-100 group-hover/carousel:pointer-events-auto transition-opacity duration-200"
      aria-label="向右滚动"
      @click="scrollByCards(1); onUserInteract()"
    >
      <ChevronRightIcon class="w-5 h-5" />
    </button>

    <p v-if="canScroll" class="mt-2 text-center text-[11px] text-gray-400 sm:hidden">
      左右滑动查看更多精选产品
    </p>
  </div>
</template>

<style scoped>
.featured-carousel-card {
  width: calc(100% - 0.5rem);
}

@media (min-width: 768px) {
  .featured-carousel-card {
    width: calc((100% - 0.75rem) / 2);
  }
}

@media (min-width: 1024px) {
  .featured-carousel-card {
    width: calc((100% - 1.5rem) / 3);
  }
}
</style>
