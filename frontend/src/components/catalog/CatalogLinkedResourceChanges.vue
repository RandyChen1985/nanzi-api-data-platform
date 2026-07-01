<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import axios from '@/utils/axios'
import ResourceVersionDiff from '@/components/resources/ResourceVersionDiff.vue'

interface ResourceLink {
  resource_key: string
  resource_name?: string
  is_primary: boolean
}

const props = withDefaults(
  defineProps<{
    productKey: string
    linkedResources: ResourceLink[]
    readonly?: boolean
  }>(),
  { readonly: false },
)

const loading = ref(false)
const groups = ref<any[]>([])
const activeDiffKey = ref<string | null>(null)
const activeDiff = ref<any>(null)
const diffLoading = ref(false)

const actionTypeLabel = (action: string) => {
  const map: Record<string, string> = { CREATE: '创建', UPDATE: '更新', ROLLBACK: '回滚' }
  return map[action] || action
}

const actionClass = (action: string) => {
  if (action === 'ROLLBACK') return 'bg-amber-100 text-amber-700'
  if (action === 'CREATE') return 'bg-green-100 text-green-700'
  return 'bg-blue-100 text-blue-700'
}

const fetchChanges = async () => {
  if (!props.linkedResources.length) {
    groups.value = []
    activeDiff.value = null
    activeDiffKey.value = null
    return
  }
  loading.value = true
  try {
    const keys = props.linkedResources.map((r) => r.resource_key).join(',')
    const res = await axios.get(
      `/api/portal/catalog/products/${props.productKey}/linked-resource-versions`,
      { params: { keys, limit: 5 } },
    )
    const linkedMap = new Map(props.linkedResources.map((r) => [r.resource_key, r]))
    groups.value = (res.data.resources || []).map((g: any) => ({
      ...g,
      resource_name: g.resource_name || linkedMap.get(g.resource_key)?.resource_name,
      is_primary: linkedMap.get(g.resource_key)?.is_primary ?? g.is_primary,
    }))
  } catch {
    groups.value = []
  } finally {
    loading.value = false
  }
}

const loadDiff = async (resourceKey: string, versionId: number) => {
  const diffId = `${resourceKey}:${versionId}`
  if (activeDiffKey.value === diffId) {
    activeDiffKey.value = null
    activeDiff.value = null
    return
  }
  diffLoading.value = true
  activeDiffKey.value = diffId
  activeDiff.value = null
  try {
    const res = await axios.get(
      `/api/portal/meta/resources/${resourceKey}/versions/${versionId}/diff`,
      { params: { compare_target: 'current' } },
    )
    activeDiff.value = res.data
  } catch {
    activeDiffKey.value = null
  } finally {
    diffLoading.value = false
  }
}

const isDiffOpen = (resourceKey: string, versionId: number) =>
  activeDiffKey.value === `${resourceKey}:${versionId}`

watch(
  () => props.linkedResources.map((r) => `${r.resource_key}:${r.is_primary}`).join('|'),
  () => {
    activeDiffKey.value = null
    activeDiff.value = null
    fetchChanges()
  },
)

onMounted(fetchChanges)
</script>

<template>
  <div class="border border-gray-100 rounded-lg p-4 space-y-3 bg-gray-50/50">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div>
        <h3 class="text-sm font-medium text-gray-800">关联 API 最近变更</h3>
        <p class="text-xs text-gray-500 mt-0.5">
          <template v-if="readonly">
            查看关联接口近期的配置调整，了解字段与调用行为是否发生变化。
          </template>
          <template v-else>
            接口配置变更会影响本产品的字段说明与调用行为，可在此快速对比差异。
          </template>
        </p>
      </div>
      <button
        type="button"
        class="text-xs text-indigo-600 hover:text-indigo-800"
        :disabled="loading"
        @click="fetchChanges"
      >
        刷新
      </button>
    </div>

    <div v-if="!linkedResources.length" class="text-xs text-gray-400">
      关联 API 后可查看其配置变更记录。
    </div>
    <div v-else-if="loading" class="text-xs text-gray-400 py-2">加载变更记录...</div>
    <div v-else class="space-y-3">
      <div
        v-for="group in groups"
        :key="group.resource_key"
        class="bg-white border border-gray-100 rounded-lg overflow-hidden"
      >
        <div class="px-3 py-2 border-b border-gray-50 flex flex-wrap items-center gap-2">
          <span class="font-mono text-xs text-gray-800">{{ group.resource_key }}</span>
          <span v-if="group.resource_name" class="text-xs text-gray-500">{{ group.resource_name }}</span>
          <span
            v-if="group.is_primary"
            class="text-[10px] bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded"
          >
            主资源
          </span>
          <RouterLink
            v-if="!readonly"
            :to="`/dashboard/resources/${group.resource_key}?tab=history`"
            class="ml-auto text-[11px] text-indigo-600 hover:text-indigo-800"
          >
            完整历史 →
          </RouterLink>
        </div>

        <div v-if="!group.recent_versions?.length" class="px-3 py-3 text-xs text-gray-400">
          暂无版本记录（保存接口配置后将自动记录）
        </div>
        <ul v-else class="divide-y divide-gray-50">
          <li
            v-for="ver in group.recent_versions"
            :key="ver.id"
            class="px-3 py-2"
          >
            <div class="flex flex-wrap items-start justify-between gap-2">
              <div class="min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-xs font-semibold text-gray-800">v{{ ver.version_no }}</span>
                  <span class="text-[10px] px-1.5 py-0.5 rounded font-medium" :class="actionClass(ver.action_type)">
                    {{ actionTypeLabel(ver.action_type) }}
                  </span>
                </div>
                <p class="text-[11px] text-gray-500 mt-0.5">
                  {{ ver.operator_name || '系统' }} · {{ ver.created_at }}
                </p>
                <p v-if="ver.change_summary" class="text-[11px] text-gray-600 mt-0.5">
                  {{ ver.change_summary }}
                </p>
              </div>
              <button
                type="button"
                class="text-[11px] px-2 py-1 border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-50 shrink-0"
                :disabled="diffLoading"
                @click="loadDiff(group.resource_key, ver.id)"
              >
                {{ isDiffOpen(group.resource_key, ver.id) ? '收起对比' : '对比当前' }}
              </button>
            </div>
            <div v-if="isDiffOpen(group.resource_key, ver.id) && activeDiff" class="mt-3">
              <ResourceVersionDiff
                :version-no="activeDiff.version_no"
                :items="activeDiff.items || []"
                @close="activeDiffKey = null; activeDiff = null"
              />
            </div>
          </li>
        </ul>
        <p v-if="group.total_versions > group.recent_versions.length" class="px-3 py-2 text-[11px] text-gray-400 border-t border-gray-50">
          共 {{ group.total_versions }} 个版本，仅展示最近 {{ group.recent_versions.length }} 条
        </p>
      </div>
    </div>
  </div>
</template>
