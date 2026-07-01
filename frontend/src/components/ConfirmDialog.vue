<script setup lang="ts">
defineProps<{
  show: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  type?: 'danger' | 'warning' | 'info'
  zIndex?: number
}>()

defineEmits(['confirm', 'cancel'])
</script>

<template>
  <teleport to="body">
    <transition name="fade">
      <div
        v-if="show"
        class="fixed inset-0 flex items-center justify-center p-4"
        :style="{ zIndex: zIndex ?? 100 }"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black bg-opacity-50 transition-opacity" @click="$emit('cancel')"></div>
        
        <!-- Dialog -->
        <div class="bg-white rounded-lg shadow-xl max-w-md w-full z-10 transform transition-all p-6">
          <div class="flex items-start">
            <div class="flex-shrink-0">
              <!-- Icons based on type -->
              <svg v-if="type === 'danger'" class="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <svg v-else-if="type === 'warning'" class="h-6 w-6 text-yellow-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <svg v-else class="h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div class="ml-3 flex-1">
              <h3 class="text-lg font-medium text-gray-900">{{ title }}</h3>
              <p class="mt-2 text-sm text-gray-500">{{ message }}</p>
            </div>
          </div>
          <div class="mt-6 flex justify-end space-x-3">
            <button
              @click="$emit('cancel')"
              class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none"
            >
              {{ cancelText || '取消' }}
            </button>
            <button
              @click="$emit('confirm')"
              class="px-4 py-2 text-sm font-medium text-white rounded-md focus:outline-none shadow-sm"
              :class="[
                type === 'danger' ? 'bg-red-600 hover:bg-red-700' : 
                type === 'warning' ? 'bg-yellow-500 hover:bg-yellow-600' : 'bg-primary hover:bg-primary-dark'
              ]"
            >
              {{ confirmText || '确认' }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
