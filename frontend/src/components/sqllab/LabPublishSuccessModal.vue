<script setup lang="ts">
import { ref, watch } from 'vue'
import axios from '@/utils/axios'
import LabSqlDiff from './LabSqlDiff.vue'

const props = defineProps<{
  open: boolean
  resourceKey: string
  labSql: string
}>()

const emit = defineEmits<{ (e: 'close'): void; (e: 'test'): void; (e: 'edit'): void }>()

const publishedSql = ref('')
const loading = ref(false)
const showDiff = ref(false)

watch(() => [props.open, props.resourceKey], async () => {
  if (!props.open || !props.resourceKey) return
  loading.value = true
  publishedSql.value = ''
  try {
    const res = await axios.get('/api/portal/meta/resources')
    const list = Array.isArray(res.data) ? res.data : res.data?.items || []
    const found = list.find((r: any) => r.resource_key === props.resourceKey)
    publishedSql.value = found?.custom_sql || ''
  } catch { /* ignore */ }
  finally { loading.value = false }
}, { immediate: true })
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-[140] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
      <h3 class="font-bold text-gray-900">API 发布成功</h3>
      <p class="text-sm text-gray-600 font-mono break-all">{{ resourceKey }}</p>
      <div class="flex flex-col gap-2">
        <button class="w-full py-2.5 bg-blue-600 text-white rounded-xl font-bold" @click="emit('test')">在线调试 API</button>
        <button class="w-full py-2.5 border rounded-xl font-bold text-gray-700" @click="emit('edit')">编辑资源配置</button>
        <button
          v-if="publishedSql && publishedSql !== labSql"
          class="w-full py-2.5 border border-violet-200 text-violet-700 rounded-xl font-bold"
          @click="showDiff = true"
        >与已发布 SQL 对比</button>
        <button class="w-full py-2 text-gray-500 text-sm" @click="emit('close')">关闭</button>
      </div>
    </div>
    <LabSqlDiff
      v-if="showDiff && publishedSql"
      :original="publishedSql"
      :modified="labSql"
      @apply="showDiff = false"
      @close="showDiff = false"
    />
  </div>
</template>
