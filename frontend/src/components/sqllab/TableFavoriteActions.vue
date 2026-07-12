<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { StarIcon, MapPinIcon, ChatBubbleLeftEllipsisIcon } from '@heroicons/vue/24/outline'
import { StarIcon as StarSolidIcon, MapPinIcon as MapPinSolidIcon } from '@heroicons/vue/24/solid'

export type TableFavoriteInfo = {
  id: number
  is_pinned: boolean
  note?: string | null
}

const props = withDefaults(defineProps<{
  tableName: string
  favorite?: TableFavoriteInfo | null
  variant?: 'inline' | 'corner'
}>(), {
  variant: 'corner',
})

const emit = defineEmits<{
  (e: 'toggle-favorite'): void
  (e: 'toggle-pin'): void
  (e: 'save-note', note: string): void
}>()

const showNote = ref(false)
const noteDraft = ref('')
const noteInputRef = ref<HTMLTextAreaElement | null>(null)
const pendingNoteOpen = ref(false)

const isCorner = () => props.variant === 'corner'

watch(() => props.favorite, (f) => {
  if (f && pendingNoteOpen.value) {
    pendingNoteOpen.value = false
    noteDraft.value = f.note || ''
    showNote.value = true
    nextTick(() => noteInputRef.value?.focus())
  }
})

const openNote = () => {
  if (!props.favorite) {
    pendingNoteOpen.value = true
    emit('toggle-favorite')
    return
  }
  noteDraft.value = props.favorite.note || ''
  showNote.value = true
  nextTick(() => noteInputRef.value?.focus())
}

watch(showNote, (open) => {
  if (!open) return
  const handler = () => {
    showNote.value = false
    document.removeEventListener('click', handler)
  }
  setTimeout(() => document.addEventListener('click', handler), 0)
})

const saveNote = () => {
  emit('save-note', noteDraft.value.trim())
  showNote.value = false
}

const hoverHidden = 'opacity-0 group-hover:opacity-100 transition-opacity'
const cornerWrap = 'absolute bottom-0 right-0 z-10 flex items-center gap-0.5 px-0.5 py-px rounded-md bg-white/90 border border-gray-100/80 shadow-sm backdrop-blur-sm'
</script>

<template>
  <div
    class="shrink-0"
    :class="isCorner() ? [cornerWrap, showNote ? 'opacity-100' : hoverHidden] : 'flex items-center'"
    @click.stop
  >
    <button
      type="button"
      class="p-0.5 rounded transition-colors"
      :class="favorite
        ? 'text-amber-500 hover:text-amber-600'
        : (isCorner() ? 'text-gray-400 hover:text-amber-500' : 'text-gray-300 hover:text-amber-500 ' + hoverHidden)"
      :title="favorite ? '取消收藏' : '收藏此表'"
      @click="emit('toggle-favorite')"
    >
      <component :is="favorite ? StarSolidIcon : StarIcon" class="w-3.5 h-3.5" />
    </button>
    <button
      v-if="favorite"
      type="button"
      class="p-0.5 rounded transition-colors"
      :class="favorite.is_pinned ? 'text-indigo-600' : 'text-gray-400 hover:text-indigo-500'"
      :title="favorite.is_pinned ? '取消置顶' : '置顶'"
      @click="emit('toggle-pin')"
    >
      <component :is="favorite.is_pinned ? MapPinSolidIcon : MapPinIcon" class="w-3.5 h-3.5" />
    </button>
    <div class="relative">
      <button
        type="button"
        class="p-0.5 rounded transition-colors"
        :class="favorite?.note
          ? 'text-blue-500 hover:text-blue-600'
          : (isCorner() ? 'text-gray-400 hover:text-blue-500' : 'text-gray-300 hover:text-blue-500 ' + hoverHidden)"
        :title="favorite?.note ? '编辑备注' : '添加备注（将自动收藏）'"
        @click="openNote"
      >
        <ChatBubbleLeftEllipsisIcon class="w-3.5 h-3.5" />
      </button>
      <div
        v-if="showNote && favorite"
        class="absolute right-0 z-[200] w-52 p-2 bg-white rounded-lg shadow-xl border border-gray-200"
        :class="isCorner() ? 'bottom-full mb-1' : 'top-full mt-1'"
        @click.stop
      >
        <textarea
          ref="noteInputRef"
          v-model="noteDraft"
          rows="3"
          maxlength="500"
          placeholder="个人备注，仅自己可见..."
          class="w-full text-[11px] border border-gray-200 rounded-md p-2 resize-none focus:ring-1 focus:ring-indigo-500 outline-none"
          @keydown.enter.ctrl.prevent="saveNote"
        />
        <div class="flex justify-end gap-1 mt-1.5">
          <button type="button" class="px-2 py-0.5 text-[10px] text-gray-500" @click="showNote = false">取消</button>
          <button type="button" class="px-2 py-0.5 text-[10px] bg-indigo-600 text-white rounded font-bold" @click="saveNote">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>
