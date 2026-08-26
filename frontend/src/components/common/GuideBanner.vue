<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ChevronDownIcon, ChevronUpIcon, EyeSlashIcon, SparklesIcon, XMarkIcon } from '@heroicons/vue/24/outline'

const props = defineProps<{
  storageKey: string
  title: string
  description?: string
  steps: {
    icon: string
    label: string
    description?: string
    actionText?: string
    actionType?: string
  }[]
  tip?: string
}>()

const emit = defineEmits<{
  close: []
  dismiss: []
  action: [type: string]
}>()

const dismissed = ref(false)
const collapsed = ref(true)

onMounted(() => {
  dismissed.value = localStorage.getItem(`${props.storageKey}:dismissed`) === '1'
  collapsed.value = localStorage.getItem(`${props.storageKey}:collapsed`) !== '0'
})

const close = () => {
  dismissed.value = true
  emit('close')
}

const dismiss = () => {
  dismissed.value = true
  localStorage.setItem(`${props.storageKey}:dismissed`, '1')
  emit('dismiss')
}

const toggleCollapse = () => {
  collapsed.value = !collapsed.value
  localStorage.setItem(`${props.storageKey}:collapsed`, collapsed.value ? '1' : '0')
}

const handleAction = (type?: string) => {
  if (type) emit('action', type)
}
</script>

<template>
  <section
    v-if="!dismissed"
    :aria-label="`${title}流程指引`"
    class="relative shrink-0 overflow-hidden rounded-2xl border border-indigo-100 bg-gradient-to-r from-indigo-50/70 via-blue-50/40 to-slate-50/60 p-4 shadow-sm transition-all sm:p-5"
  >
    <div
      class="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-indigo-200/30 blur-3xl"
      aria-hidden="true"
    ></div>
    <div
      class="pointer-events-none absolute left-1/3 -bottom-20 h-40 w-40 rounded-full bg-blue-200/25 blur-2xl"
      aria-hidden="true"
    ></div>

    <div class="relative z-10 flex flex-wrap items-center justify-between gap-3">
      <div class="flex min-w-0 items-center gap-3">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-600/30">
          <SparklesIcon class="h-5 w-5" />
        </div>
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="text-sm font-bold text-gray-900 sm:text-base">{{ title }}使用指引</h3>
            <span class="rounded-full bg-indigo-100/80 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
              {{ steps.length }} 步流程
            </span>
          </div>
          <p v-if="description" class="mt-0.5 text-xs leading-5 text-gray-500">{{ description }}</p>
        </div>
      </div>

      <div class="flex items-center gap-1.5 sm:gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white/80 px-2.5 py-1 text-xs font-medium text-gray-600 shadow-sm transition-colors hover:bg-white hover:text-gray-900"
          :title="collapsed ? '展开指引' : '收起指引'"
          @click="toggleCollapse"
        >
          <span>{{ collapsed ? '展开流程' : '收起' }}</span>
          <ChevronDownIcon v-if="collapsed" class="h-3.5 w-3.5" />
          <ChevronUpIcon v-else class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          class="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white/80 px-2.5 py-1 text-xs font-medium text-gray-500 shadow-sm transition-colors hover:bg-white hover:text-amber-600"
          title="下次进入不再主动弹出此引导"
          @click="dismiss"
        >
          <EyeSlashIcon class="h-3.5 w-3.5 text-gray-400" />
          <span>不再提示</span>
        </button>
        <button
          type="button"
          class="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-200/50 hover:text-gray-700"
          title="关闭本次指引"
          @click="close"
        >
          <XMarkIcon class="h-4 w-4" />
        </button>
      </div>
    </div>

    <div
      v-show="!collapsed"
      class="relative z-10 mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2"
      :class="steps.length <= 4 ? 'lg:grid-cols-4' : 'lg:grid-cols-5'"
    >
      <div
        v-for="(step, index) in steps"
        :key="`${step.label}-${index}`"
        class="group relative flex min-h-32 flex-col rounded-xl border border-white/80 bg-white/85 p-3 shadow-sm backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-indigo-200 hover:bg-indigo-50/70 hover:shadow-md"
      >
        <div class="flex items-start gap-2">
          <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-lg">{{ step.icon }}</span>
          <div class="min-w-0">
            <div class="flex items-center gap-1.5">
              <span class="text-[11px] font-bold text-indigo-500">{{ index + 1 }}</span>
              <span class="truncate text-xs font-bold leading-tight text-gray-900" :title="step.label">{{ step.label }}</span>
            </div>
            <p v-if="step.description" class="mt-2 text-[11px] leading-relaxed text-gray-500">{{ step.description }}</p>
          </div>
        </div>
        <div v-if="step.actionText && step.actionType" class="mt-auto border-t border-gray-100/80 pt-2.5">
          <button
            type="button"
            class="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 transition-colors hover:text-indigo-800"
            @click="handleAction(step.actionType)"
          >
            <span>{{ step.actionText }}</span>
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <p v-if="tip" class="relative z-10 mt-4 border-t border-indigo-100/70 pt-3 text-xs leading-5 text-indigo-500">
      <span class="mr-1">💡</span>{{ tip }}
    </p>
  </section>
</template>
