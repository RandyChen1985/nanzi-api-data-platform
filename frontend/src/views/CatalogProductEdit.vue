<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from '@/utils/axios'
import { useToast } from '@/composables/useToast'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import SearchSelect from '@/components/common/SearchSelect.vue'
import CatalogLinkedResourceChanges from '@/components/catalog/CatalogLinkedResourceChanges.vue'
import { renderMarkdown } from '@/utils/markdown'
import { toFeaturedBool } from '@/utils/catalog'

interface ResourceLink {
  resource_key: string
  resource_name?: string
  is_primary: boolean
}

const route = useRoute()
const router = useRouter()
const { showToast } = useToast()
const productKey = computed(() => route.params.key as string)
const loading = ref(true)
const saving = ref(false)
const meta = ref<any>(null)
const linkedResources = ref<ResourceLink[]>([])
const addResourceKey = ref('')
const form = ref({
  display_name: '',
  summary: '',
  description: '',
  domain: '默认域',
  tags: [] as string[],
  owner_user_id: null as number | null,
  dataset_id: null as number | null,
  featured: false,
})
const tagInput = ref('')
const resourceConflicts = ref<any[]>([])
const archivingConflict = ref<string | null>(null)
const descriptionPreviewHtml = computed(() => renderMarkdown(form.value.description))
const canSetFeatured = computed(
  () => meta.value?.is_admin || meta.value?.can_manage_catalog,
)

const fetchResourceConflicts = async () => {
  if (!linkedResources.value.length) {
    resourceConflicts.value = []
    return
  }
  try {
    const keys = linkedResources.value.map((r) => r.resource_key).join(',')
    const res = await axios.get(
      `/api/portal/catalog/products/${productKey.value}/resource-conflicts`,
      { params: { keys } },
    )
    resourceConflicts.value = res.data
  } catch {
    resourceConflicts.value = []
  }
}

const archiveConflict = async (item: any) => {
  archivingConflict.value = item.product_key
  try {
    await axios.post(`/api/portal/catalog/products/${item.product_key}/archive-redundant`, {
      revoke_permissions: item.status === 1,
    })
    showToast(`已归档冗余产品「${item.display_name}」`, 'success')
    await fetchResourceConflicts()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '归档失败', 'error')
  } finally {
    archivingConflict.value = null
  }
}

const confirmDialog = ref({
  show: false,
  title: '',
  message: '',
  type: 'warning' as 'danger' | 'warning' | 'info',
  confirmText: '确认',
  onConfirm: () => {},
})

const availableToAdd = computed(() => {
  const linked = new Set(linkedResources.value.map((r) => r.resource_key))
  return (meta.value?.available_resources || []).filter(
    (r: any) => !linked.has(r.resource_key),
  )
})

const availableResourceOptions = computed(() =>
  availableToAdd.value.map((r: any) => ({
    value: r.resource_key,
    label: r.resource_name || r.resource_key,
    sublabel: [r.resource_key, r.resource_group].filter(Boolean).join(' · '),
    keywords: r.resource_group,
  })),
)

const ownerOptions = computed(() =>
  (meta.value?.users || []).map((u: any) => ({
    value: u.id,
    label: u.user_name,
    sublabel: u.remark || undefined,
    keywords: u.remark,
  })),
)

const datasetOptions = computed(() =>
  (meta.value?.datasets || []).map((ds: any) => ({
    value: ds.id,
    label: ds.display_name || ds.name,
    sublabel: ds.data_source,
  })),
)

const load = async () => {
  loading.value = true
  try {
    const [productRes, metaRes] = await Promise.all([
      axios.get(`/api/portal/catalog/products/${productKey.value}`),
      axios.get(`/api/portal/catalog/products/${productKey.value}/edit-meta`),
    ])
    const p = productRes.data
    const m = metaRes.data
    form.value = {
      display_name: p.display_name || '',
      summary: p.summary || '',
      description: p.description || '',
      domain: p.domain || '默认域',
      tags: p.tags || [],
      owner_user_id: p.owner_user_id ?? null,
      dataset_id: p.dataset_id ?? null,
      featured: toFeaturedBool(m.featured ?? p.featured),
    }
    linkedResources.value = (p.resources || []).map((r: any) => ({
      resource_key: r.resource_key,
      resource_name: r.resource_name,
      is_primary: !!r.is_primary,
    }))
    meta.value = metaRes.data
    await fetchResourceConflicts()
  } catch {
    router.replace('/dashboard/catalog')
  } finally {
    loading.value = false
  }
}

const addTag = () => {
  const t = tagInput.value.trim()
  if (t && !form.value.tags.includes(t)) {
    form.value.tags.push(t)
  }
  tagInput.value = ''
}

const removeTag = (t: string) => {
  form.value.tags = form.value.tags.filter((x) => x !== t)
}

const addResource = () => {
  const key = addResourceKey.value
  if (!key) return
  const found = (meta.value?.available_resources || []).find((r: any) => r.resource_key === key)
  if (!found) {
    showToast('请选择有效的 API 资源', 'warning')
    return
  }
  linkedResources.value.push({
    resource_key: found.resource_key,
    resource_name: found.resource_name,
    is_primary: linkedResources.value.length === 0,
  })
  addResourceKey.value = ''
  fetchResourceConflicts()
}

const setPrimary = (key: string) => {
  linkedResources.value = linkedResources.value.map((r) => ({
    ...r,
    is_primary: r.resource_key === key,
  }))
}

const removeResource = (key: string) => {
  const target = linkedResources.value.find((r) => r.resource_key === key)
  if (!target) return
  const doRemove = () => {
    const wasPrimary = target.is_primary
    linkedResources.value = linkedResources.value.filter((r) => r.resource_key !== key)
    if (wasPrimary && linkedResources.value.length) {
      linkedResources.value = linkedResources.value.map((r, i) => ({
        ...r,
        is_primary: i === 0,
      }))
    }
  }
  if (linkedResources.value.length <= 1) {
    showToast('至少保留一个关联 API', 'warning')
    return
  }
  confirmDialog.value = {
    show: true,
    title: '移除关联 API',
    message: `确认从产品移除「${target.resource_name || key}」？`,
    type: 'warning',
    confirmText: '移除',
    onConfirm: () => {
      doRemove()
      fetchResourceConflicts()
    },
  }
}

const save = async () => {
  if (!form.value.display_name.trim()) {
    showToast('请填写产品展示名称', 'warning')
    return
  }
  if (!linkedResources.value.length) {
    showToast('至少关联一个 API 资源', 'warning')
    return
  }
  if (!linkedResources.value.some((r) => r.is_primary)) {
    showToast('请指定一个主资源', 'warning')
    return
  }
  saving.value = true
  try {
    await axios.put(`/api/portal/catalog/products/${productKey.value}`, form.value)
    await axios.put(`/api/portal/catalog/products/${productKey.value}/resources`, {
      resources: linkedResources.value.map((r) => ({
        resource_key: r.resource_key,
        is_primary: r.is_primary,
      })),
    })
    await fetchResourceConflicts()
    if (resourceConflicts.value.length) {
      showToast('保存成功，请归档下方冗余产品', 'warning')
      return
    }
    showToast('保存成功', 'success')
    router.push(`/dashboard/catalog/${productKey.value}`)
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <button class="text-sm text-gray-500 hover:text-indigo-600" @click="router.push(`/dashboard/catalog/${productKey}`)">
      ← 返回产品详情
    </button>

    <div v-if="loading" class="text-center py-20 text-gray-400">加载中...</div>
    <template v-else>
      <h1 class="text-lg sm:text-2xl font-bold text-gray-900">编辑数据产品</h1>
      <p class="text-sm text-gray-500">完善简介、负责人与关联 API 后方可发布上架</p>

      <div
        v-if="resourceConflicts.length"
        class="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-3"
      >
        <p class="text-sm font-medium text-amber-900">
          以下 API 仍存在独立的冗余产品记录，建议归档以免目录重复展示：
        </p>
        <div
          v-for="c in resourceConflicts"
          :key="c.product_key"
          class="flex flex-wrap items-center justify-between gap-2 text-sm bg-white/80 rounded-lg p-3"
        >
          <span>
            <strong>{{ c.display_name }}</strong>
            <span class="text-gray-500">（{{ c.product_key }}）</span>
          </span>
          <button
            type="button"
            class="text-xs px-3 py-1.5 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
            :disabled="archivingConflict === c.product_key"
            @click="archiveConflict(c)"
          >
            {{ archivingConflict === c.product_key ? '归档中...' : '一键归档' }}
          </button>
        </div>
        <router-link to="/dashboard/catalog-redundant" class="text-xs text-amber-800 hover:text-amber-950 font-medium">
          查看全部冗余产品 →
        </router-link>
      </div>

      <form class="bg-white rounded-xl border border-gray-100 p-6 space-y-5" @submit.prevent="save">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">展示名称 *</label>
          <input v-model="form.display_name" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" required />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">一句话简介 *</label>
          <input v-model="form.summary" maxlength="500" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" placeholder="面向业务方的一句话说明" />
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-sm font-medium text-gray-700">详细介绍</label>
            <span class="text-xs text-gray-400">支持 Markdown</span>
          </div>
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <textarea
              v-model="form.description"
              rows="10"
              class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono resize-y min-h-[200px]"
              placeholder="支持标题、列表、链接、粗体等 Markdown 语法"
            />
            <div class="border border-gray-200 rounded-lg bg-gray-50/80 flex flex-col min-h-[200px] overflow-hidden">
              <div class="px-3 py-2 border-b border-gray-200 bg-white text-xs font-medium text-gray-500">
                实时预览
              </div>
              <div class="flex-1 overflow-auto p-3">
                <div
                  v-if="descriptionPreviewHtml"
                  class="markdown-body prose prose-sm max-w-none text-gray-700 break-words"
                  v-html="descriptionPreviewHtml"
                />
                <p v-else class="text-sm text-gray-400">输入内容后将在此显示渲染效果</p>
              </div>
            </div>
          </div>
        </div>

        <div class="border border-gray-100 rounded-lg p-4 space-y-3">
          <div class="flex items-center justify-between">
            <label class="text-sm font-medium text-gray-700">关联 API 资源 *</label>
            <span class="text-xs text-gray-400">{{ linkedResources.length }} 个</span>
          </div>
          <div v-if="!linkedResources.length" class="text-sm text-gray-400">暂无关联资源</div>
          <div v-else class="space-y-2">
            <div
              v-for="r in linkedResources"
              :key="r.resource_key"
              class="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-50 rounded-lg text-sm"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span class="font-mono text-xs truncate">{{ r.resource_key }}</span>
                <span v-if="r.resource_name" class="text-gray-500 truncate">{{ r.resource_name }}</span>
                <span v-if="r.is_primary" class="text-[10px] bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded shrink-0">主资源</span>
              </div>
              <div class="flex items-center gap-2 shrink-0">
                <button
                  v-if="!r.is_primary"
                  type="button"
                  class="text-xs text-indigo-600 hover:text-indigo-800"
                  @click="setPrimary(r.resource_key)"
                >
                  设为主资源
                </button>
                <button type="button" class="text-xs text-red-600 hover:text-red-800" @click="removeResource(r.resource_key)">
                  移除
                </button>
              </div>
            </div>
          </div>
          <div class="flex gap-2 pt-1">
            <div class="flex-1 min-w-0">
              <SearchSelect
                v-model="addResourceKey"
                :options="availableResourceOptions"
                placeholder="选择要添加的 API..."
                search-placeholder="搜索 API 名称或 key..."
                allow-empty
                empty-label="选择要添加的 API..."
                :empty-value="''"
              />
            </div>
            <button type="button" class="px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 shrink-0" @click="addResource">
              添加
            </button>
          </div>
          <CatalogLinkedResourceChanges
            :product-key="productKey"
            :linked-resources="linkedResources"
          />
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">业务域</label>
            <input v-model="form.domain" list="domain-list" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            <datalist id="domain-list">
              <option v-for="d in meta?.domains || []" :key="d" :value="d" />
            </datalist>
          </div>
          <div v-if="meta?.can_assign_owner">
            <label class="block text-sm font-medium text-gray-700 mb-1">负责人 *</label>
            <SearchSelect
              v-model="form.owner_user_id"
              :options="ownerOptions"
              placeholder="请选择"
              search-placeholder="搜索用户名或备注..."
              allow-empty
              empty-label="请选择"
              :empty-value="null"
            />
          </div>
        </div>

        <div v-if="meta?.is_admin">
          <label class="block text-sm font-medium text-gray-700 mb-1">关联语义数据集</label>
          <SearchSelect
            v-model="form.dataset_id"
            :options="datasetOptions"
            placeholder="不关联"
            search-placeholder="搜索数据集名称或数据源..."
            allow-empty
            empty-label="不关联"
            :empty-value="null"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">标签</label>
          <div class="flex flex-wrap gap-2 mb-2">
            <span
              v-for="t in form.tags"
              :key="t"
              class="text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded-full flex items-center gap-1"
            >
              {{ t }}
              <button type="button" class="hover:text-indigo-900" @click="removeTag(t)">×</button>
            </span>
          </div>
          <div class="flex gap-2">
            <input v-model="tagInput" class="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm" placeholder="输入后回车添加" @keydown.enter.prevent="addTag" />
            <button type="button" class="px-3 py-2 text-sm border rounded-lg hover:bg-gray-50" @click="addTag">添加</button>
          </div>
        </div>

        <label v-if="canSetFeatured" class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input v-model="form.featured" type="checkbox" class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
          设为精选产品
        </label>

        <div class="flex gap-3 pt-2">
          <button type="submit" :disabled="saving" class="px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {{ saving ? '保存中...' : '保存' }}
          </button>
          <button type="button" class="px-5 py-2 border border-gray-200 rounded-lg text-sm" @click="router.push(`/dashboard/catalog/${productKey}`)">
            取消
          </button>
        </div>
      </form>
    </template>

    <ConfirmDialog
      :show="confirmDialog.show"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :type="confirmDialog.type"
      :confirm-text="confirmDialog.confirmText"
      @confirm="confirmDialog.onConfirm(); confirmDialog.show = false"
      @cancel="confirmDialog.show = false"
    />
  </div>
</template>
