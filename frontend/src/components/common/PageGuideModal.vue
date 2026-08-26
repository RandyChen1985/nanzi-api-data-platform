<script setup lang="ts">
import { QuestionMarkCircleIcon, XMarkIcon } from '@heroicons/vue/24/outline'

defineProps<{
  open: boolean
  title: string
  description: string
  steps: {
    icon: string
    title: string
    description: string
  }[]
  tip?: string
}>()

const emit = defineEmits<{
  close: []
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[200] flex items-center justify-center bg-gray-900/50 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      @click.self="emit('close')"
      @keydown.esc="emit('close')"
    >
      <div class="flex max-h-[min(720px,90vh)] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-2xl">
        <div class="flex items-start justify-between gap-4 border-b border-indigo-100 bg-gradient-to-r from-indigo-50/80 to-blue-50/50 px-6 py-5 sm:px-8">
          <div class="flex min-w-0 items-start gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-500/20">
              <QuestionMarkCircleIcon class="h-6 w-6" />
            </div>
            <div class="min-w-0">
              <h2 class="text-lg font-bold text-gray-900 sm:text-xl">{{ title }}</h2>
              <p class="mt-1 text-sm leading-6 text-gray-600">{{ description }}</p>
            </div>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-white hover:text-gray-600"
            title="关闭指引"
            aria-label="关闭指引"
            @click="emit('close')"
          >
            <XMarkIcon class="h-5 w-5" />
          </button>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto p-6 sm:p-8">
          <div class="grid gap-4 sm:grid-cols-2">
            <div
              v-for="(step, index) in steps"
              :key="`${step.title}-${index}`"
              class="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-colors hover:border-indigo-200 hover:bg-indigo-50/30"
            >
              <div class="flex items-start gap-3">
                <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-xl">
                  {{ step.icon }}
                </div>
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-indigo-500">{{ String(index + 1).padStart(2, '0') }}</span>
                    <h3 class="font-semibold text-gray-900">{{ step.title }}</h3>
                  </div>
                  <p class="mt-2 text-sm leading-6 text-gray-600">{{ step.description }}</p>
                </div>
              </div>
            </div>
          </div>

          <div v-if="tip" class="mt-5 rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-800">
            <span class="mr-1">💡</span>{{ tip }}
          </div>
        </div>

        <div class="flex justify-end border-t border-gray-100 bg-gray-50/70 px-6 py-4 sm:px-8">
          <button
            type="button"
            class="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700"
            @click="emit('close')"
          >
            知道了
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
