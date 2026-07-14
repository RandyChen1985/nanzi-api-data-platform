<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
    <div class="flex min-h-screen items-end sm:items-center justify-center p-0 sm:p-4 text-center sm:text-left">
      <div @click="close" class="fixed inset-0 bg-gray-500/75 transition-opacity" aria-hidden="true"></div>

      <div class="relative inline-flex w-full flex-col bg-white text-left shadow-xl sm:my-8 sm:max-w-4xl sm:rounded-lg sm:align-middle max-h-[100dvh] sm:max-h-[90vh] overflow-hidden">
        <div class="bg-white px-4 pt-4 pb-3 sm:p-6 sm:pb-4 flex-1 min-h-0 flex flex-col">
          <div class="flex items-start gap-3 sm:gap-4 shrink-0">
            <div class="flex-shrink-0 flex items-center justify-center h-9 w-9 sm:h-10 sm:w-10 rounded-full bg-blue-100">
              <svg class="h-5 w-5 sm:h-6 sm:w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 14l-1 1-1 1H3m9-9a6 6 0 019 9h9v1.8c0 .249-.088.485-.246.663l-4 4.062C8.6 20.2 8.3 20.3 8 20.5l-5-5-5-5L15 7z" />
              </svg>
            </div>
            <div class="flex-1 min-w-0 text-left">
              <h3 class="text-base sm:text-lg font-bold text-gray-900 truncate" id="modal-title">
                我的权限资产库
              </h3>
              <p class="text-xs text-gray-500 mt-0.5 sm:hidden">查看接口资源、数据资产与安全策略</p>
            </div>
            <button
              type="button"
              class="sm:hidden p-1.5 text-gray-400 hover:text-gray-600 rounded-lg shrink-0"
              aria-label="关闭"
              @click="close"
            >
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Mobile: tab selector -->
          <div class="mt-3 sm:hidden shrink-0">
            <label for="perm-tab-select" class="sr-only">权限分区</label>
            <select
              id="perm-tab-select"
              v-model="activeTab"
              class="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              <option value="resource">接口资源 ({{ resources.length }})</option>
              <option value="data">数据资产 ({{ datasourceList.length }})</option>
              <option value="security">安全策略</option>
              <option v-if="showChangeNotificationsTab" value="changes">
                配置变更{{ changeNotificationUnread > 0 ? ` (${changeNotificationUnread})` : '' }}
              </option>
              <option v-if="showAboutTab" value="about">联系我们</option>
            </select>
          </div>

          <!-- Desktop: tabs -->
          <div class="hidden sm:flex border-b border-gray-200 mt-4 shrink-0">
            <button @click="activeTab = 'resource'" class="px-4 py-2 text-sm font-bold border-b-2 transition-all" :class="activeTab === 'resource' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'">
              接口资源 ({{ resources.length }})
            </button>
            <button @click="activeTab = 'data'" class="px-4 py-2 text-sm font-bold border-b-2 transition-all" :class="activeTab === 'data' ? 'border-orange-600 text-orange-600' : 'border-transparent text-gray-500 hover:text-gray-700'">
              数据资产 ({{ datasourceList.length }})
            </button>
            <button @click="activeTab = 'security'" class="px-4 py-2 text-sm font-bold border-b-2 transition-all" :class="activeTab === 'security' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'">
              安全策略
            </button>
            <button
              v-if="showChangeNotificationsTab"
              @click="activeTab = 'changes'"
              class="px-4 py-2 text-sm font-bold border-b-2 transition-all relative"
              :class="activeTab === 'changes' ? 'border-teal-600 text-teal-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
            >
              配置变更
              <span
                v-if="changeNotificationUnread > 0"
                class="ml-1 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-[10px] font-black text-white"
              >
                {{ changeNotificationUnread > 99 ? '99+' : changeNotificationUnread }}
              </span>
            </button>
            <button
              v-if="showAboutTab"
              @click="activeTab = 'about'"
              class="px-4 py-2 text-sm font-bold border-b-2 transition-all"
              :class="activeTab === 'about' ? 'border-gray-800 text-gray-900' : 'border-transparent text-gray-500 hover:text-gray-700'"
            >
              联系我们
            </button>
          </div>

          <div v-if="activeTab === 'resource'" class="mt-3 sm:mt-4 shrink-0">
            <ClearableInput
              v-model="searchQuery"
              show-search-icon
              input-class="py-2 text-sm"
              placeholder="搜索资源名称、Key 或分组..."
            />
          </div>

          <div class="mt-2 flex-1 min-h-0 flex flex-col">
            <div class="overflow-y-auto flex-1 min-h-0 mt-3 sm:mt-4 pr-1 custom-scrollbar">
                  
                  <!-- Tab: Data Assets -->
                  <div v-if="activeTab === 'data'" class="space-y-4">
                    <div v-if="datasourceList.length === 0" class="py-10 text-center text-gray-400 italic">暂无数据资产访问权限</div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div v-for="ds in datasourceList" :key="ds" class="bg-orange-50 border border-orange-100 rounded-xl p-3 shadow-sm hover:shadow-md transition-shadow">
                        <div class="flex items-center justify-between mb-2">
                          <span class="text-sm font-bold text-orange-700 uppercase">{{ ds }}</span>
                          <span class="bg-orange-200 text-orange-800 px-1.5 py-0.5 rounded text-[9px] font-black">DATA SOURCE</span>
                        </div>
                        <div class="flex flex-wrap gap-1">
                          <template v-if="dataTableList.some(dt => dt.ds === ds && dt.table === '*')">
                            <span class="bg-white text-orange-600 px-2 py-0.5 rounded border border-orange-200 text-[10px] font-bold shadow-sm">所有表 (ALL)</span>
                          </template>
                          <template v-else>
                            <span v-for="dt in dataTableList.filter(dt => dt.ds === ds)" :key="dt.table" class="bg-white text-gray-600 px-2 py-0.5 rounded border border-gray-200 text-[10px] font-medium">
                              {{ dt.table }}
                            </span>
                            <span v-if="!dataTableList.some(dt => dt.ds === ds)" class="text-[10px] text-gray-400 italic">仅限特定 SQL 调用</span>
                          </template>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Tab: Security Policy -->
                  <div v-if="activeTab === 'security'" class="space-y-6 animate-in fade-in slide-in-from-top-2 duration-300">
                    <div class="bg-indigo-50 border border-indigo-100 rounded-2xl p-4 sm:p-6">
                      <h4 class="text-sm font-bold text-indigo-900 mb-4 flex items-center gap-2">
                        🛡️ 我的数据安全策略
                      </h4>
                      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="bg-white p-4 rounded-xl border border-indigo-100 shadow-sm">
                          <div class="flex items-center gap-3 mb-2">
                            <ShieldCheckIcon class="w-5 h-5 text-indigo-600" />
                            <span class="text-sm font-bold text-gray-700">脱敏规则状态</span>
                          </div>
                          <p class="text-xs text-gray-500 mb-3">定义您在查看敏感字段（如手机号、密码）时受到的自动脱敏限制。</p>
                          <span v-if="maskingStrategy === 'ENABLE'" class="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-red-100 text-red-700">
                            强制脱敏开启
                          </span>
                          <span v-else-if="maskingStrategy === 'DISABLE'" class="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-green-100 text-green-700">
                            已豁免脱敏 (显示明文)
                          </span>
                          <span v-else class="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-700">
                            跟随系统默认策略
                          </span>
                        </div>

                        <div class="bg-white p-4 rounded-xl border border-indigo-100 shadow-sm">
                          <div class="flex items-center gap-3 mb-2">
                            <BoltIcon class="w-5 h-5 text-amber-500" />
                            <span class="text-sm font-bold text-gray-700">接口流量配额</span>
                          </div>
                          <p class="text-xs text-gray-500 mb-3">您的 API 访问频率限制（按每分钟请求次数计算）。</p>
                          <div class="flex items-baseline gap-1">
                            <span v-if="rateLimit" class="text-2xl font-black text-amber-600">{{ rateLimit }}</span>
                            <span v-else class="text-lg font-bold text-gray-400">默认配额</span>
                            <span class="text-[10px] text-gray-400 font-bold uppercase">Requests / Min</span>
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    <div class="p-4 bg-gray-50 rounded-xl border border-gray-200">
                      <p class="text-[10px] text-gray-500 leading-relaxed">
                        ※ 提示：如果您的业务需要更高的访问配额或明文查看权限，请联系系统管理员申请。
                      </p>
                    </div>
                  </div>

                  <!-- Tab: Catalog Change Notifications -->
                  <div v-if="activeTab === 'changes' && showChangeNotificationsTab">
                    <CatalogChangeNotificationsPanel
                      embedded
                      :active="activeTab === 'changes'"
                      @read-changed="onChangeNotificationsRead"
                      @navigate-product="onNavigateProduct"
                      @navigate-resource="onNavigateResource"
                      @toast="(msg, type) => emit('show-toast', msg, type || 'info')"
                    />
                  </div>

                  <!-- Tab: About / Contact -->
                  <div v-if="activeTab === 'about' && showAboutTab" class="py-2">
                    <div
                      class="markdown-body prose prose-sm max-w-none text-gray-700 break-words"
                      v-html="contactHtml"
                    />
                  </div>

                  <!-- Tab: API Resources (Original) -->
                  <div v-if="activeTab === 'resource'" class="space-y-4">
                    <div v-if="filteredResources.length === 0" class="py-10 text-center text-gray-400 italic">未发现匹配的接口资源</div>
                    <div v-for="resource in filteredResources" :key="resource.resource_key"
                         class="border border-gray-200 rounded-lg p-3 sm:p-4 hover:shadow-sm transition-shadow">

                      <!-- Resource Header -->
                      <div class="flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-start mb-2">
                        <div class="min-w-0">
                          <div class="flex flex-wrap items-center gap-1.5 sm:gap-2">
                            <span v-if="resource.resource_mode === 'SYSTEM'" class="text-base sm:text-lg">⚡️</span>
                            <h4 class="text-sm sm:text-base font-bold text-gray-900">{{ resource.resource_name }}</h4>
                            <span class="px-1.5 sm:px-2 py-0.5 rounded text-[10px] sm:text-xs font-medium bg-gray-100 text-gray-600 shrink-0">
                               {{ resource.resource_group }}
                            </span>
                          </div>
                          <div class="flex items-center mt-1.5 text-xs sm:text-sm text-gray-500 group cursor-pointer max-w-full"
                               @click="copyText(resource.resource_key, '资源API Key')" title="点击复制 ID">
                            <code class="bg-gray-50 px-1.5 py-0.5 rounded text-gray-600 truncate max-w-full block">{{ resource.resource_key }}</code>
                          </div>
                        </div>
                        <div class="text-[10px] sm:text-xs text-gray-400 shrink-0">
                           更新: {{ formatDate(resource.updated_at) }}
                        </div>
                      </div>

                      <!-- Actions -->
                      <div v-if="resource.resource_mode !== 'SYSTEM'" class="flex flex-col sm:flex-row gap-2 sm:gap-3 mt-3 sm:mt-4">
                         <button @click="toggleFields(resource)" class="text-xs sm:text-sm text-blue-600 hover:text-blue-800 flex items-center justify-center sm:justify-start font-bold px-3 py-2 sm:px-0 sm:py-0 rounded-lg sm:rounded-none bg-blue-50 sm:bg-transparent">
                            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                            字段详情
                         </button>
                         <button @click="showExample(resource)" class="text-xs sm:text-sm text-green-600 hover:text-green-800 flex items-center justify-center sm:justify-start font-bold px-3 py-2 sm:px-0 sm:py-0 rounded-lg sm:rounded-none bg-green-50 sm:bg-transparent">
                            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path></svg>
                            调用示例
                         </button>
                      </div>
                      <div v-else class="mt-4 text-xs text-gray-400 italic">
                          系统功能组件，无需配置字段 (System Built-in Feature)
                      </div>

                      <!-- Field Config Popover/Collapse -->
                      <div v-if="activeFieldsResource === resource.resource_key" class="mt-4 bg-gray-50 p-3 rounded text-sm overflow-x-auto border border-gray-100">
                          <table class="min-w-full divide-y divide-gray-200">
                            <thead>
                              <tr>
                                <th class="px-3 py-2 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">字段名</th>
                                <th class="px-3 py-2 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">中文名</th>
                                <th class="px-3 py-2 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">类型</th>
                              </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-200">
                               <tr v-for="field in resource.fields_config" :key="field.name" class="group/row">
                                 <td class="px-3 py-2 whitespace-nowrap text-gray-900 font-mono text-xs flex items-center">
                                    {{ field.name }}
                                    <button @click="copyText(field.name, '字段名')" class="ml-2 text-gray-400 hover:text-blue-500 opacity-0 group-hover/row:opacity-100 transition-opacity" title="复制字段名">
                                        <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2"></path></svg>
                                    </button>
                                 </td>
                                 <td class="px-3 py-2 whitespace-nowrap text-gray-500">{{ field.label }}</td>
                                 <td class="px-3 py-2 whitespace-nowrap text-gray-500">{{ field.type }}</td>
                               </tr>
                            </tbody>
                          </table>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
        </div>
        <div class="hidden sm:flex bg-gray-50 px-4 py-3 sm:px-6 sm:flex-row-reverse shrink-0 border-t border-gray-100">
          <button type="button" @click="close" class="w-full sm:w-auto inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
            关闭
          </button>
        </div>
      </div>
    </div>

    <!-- Example Modal (Nested) -->
     <div v-if="exampleResource" class="fixed inset-0 z-[60] overflow-y-auto" role="dialog" aria-modal="true">
        <div class="flex items-end sm:items-center justify-center min-h-screen p-0 sm:p-4">
           <div class="fixed inset-0 bg-black/50" @click="closeExample"></div>
           <div class="relative bg-white rounded-t-2xl sm:rounded-lg shadow-xl w-full sm:max-w-3xl z-10 p-4 sm:p-6 max-h-[92dvh] sm:max-h-none overflow-y-auto">
              <div class="flex items-start justify-between gap-3 mb-4">
                <h3 class="text-base sm:text-lg font-medium text-gray-900 pr-8">调用示例: {{ exampleResource.resource_name }}</h3>
                <button @click="closeExample" class="absolute top-4 right-4 text-gray-400 hover:text-gray-500 p-1">
                 <svg class="h-5 w-5 sm:h-6 sm:w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
              </div>

              <!-- Mobile example tab -->
              <select
                v-model="exampleTab"
                class="sm:hidden w-full mb-4 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium"
              >
                <option value="universal">通用查询接口 (Query)</option>
                <option value="direct">资源接口 (Resource)</option>
              </select>

              <!-- Desktop example tabs -->
              <div class="hidden sm:block border-b border-gray-200 mb-4">
                 <nav class="-mb-px flex space-x-8 overflow-x-auto custom-scrollbar">
                    <button @click="exampleTab = 'universal'"
                            :class="[exampleTab === 'universal' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm shrink-0']">
                       通用查询接口 (Query)
                    </button>
                    <button @click="exampleTab = 'direct'"
                            :class="[exampleTab === 'direct' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm shrink-0']">
                       资源接口 (Resource)
                    </button>
                 </nav>
              </div>

              <!-- Documentation Hint -->
              <div class="mb-3 text-sm text-gray-500 bg-blue-50 p-2 rounded border border-blue-100 flex items-start">
                  <svg class="h-5 w-5 text-blue-400 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                  <div>
                    <p>详细使用方法请参考 <a href="/docs" target="_blank" class="text-blue-600 hover:underline">API 文档</a> 或使用 <router-link to="/dashboard/playground" class="text-blue-600 hover:underline" @click="closeExample">API 调试</router-link> 功能进行在线测试。</p>
                  </div>
              </div>

               <div class="bg-gray-900 rounded-lg p-4 font-mono text-sm text-green-400 overflow-x-auto relative group">
                  <pre class="whitespace-pre-wrap break-all">{{ getExampleCode(exampleResource) }}</pre>
                  <button @click="copyCode(getExampleCode(exampleResource))" class="absolute top-2 right-2 bg-gray-700 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                     复制
                  </button>
               </div>
           </div>
        </div>
     </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ShieldCheckIcon, BoltIcon } from '@heroicons/vue/24/outline'
import CatalogChangeNotificationsPanel from '@/components/catalog/CatalogChangeNotificationsPanel.vue'
import ClearableInput from '@/components/common/ClearableInput.vue'
import { renderMarkdown } from '@/utils/markdown'
import { copyToClipboard } from '@/utils/clipboard'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    resources: any[]
    datasources?: string[]
    dataTables?: string[]
    maskingStrategy?: string
    rateLimit?: number | null
    showChangeNotificationsTab?: boolean
    changeNotificationUnread?: number
    showAboutTab?: boolean
    contactMarkdown?: string
    initialTab?: 'resource' | 'data' | 'security' | 'changes' | 'about'
  }>(),
  {
    showChangeNotificationsTab: false,
    changeNotificationUnread: 0,
    showAboutTab: false,
    contactMarkdown: '',
    initialTab: 'resource',
  },
)

const emit = defineEmits(['close', 'show-toast', 'change-notifications-read'])

const router = useRouter()
const activeTab = ref<'resource' | 'data' | 'security' | 'changes' | 'about'>('resource')
const activeFieldsResource = ref<string | null>(null)
const exampleResource = ref<any | null>(null)
const exampleTab = ref<'universal' | 'direct'>('universal')
const searchQuery = ref('')

const contactHtml = computed(() => renderMarkdown(props.contactMarkdown || ''))

// Computed Data Asset Views
const datasourceList = computed(() => {
  if (!props.datasources) return []
  return props.datasources.map(ds => ds.replace('ds:', ''))
})

const dataTableList = computed(() => {
  if (!props.dataTables) return []
  return props.dataTables.map(dt => {
    const parts = dt.split(':table:')
    return {
      ds: parts[0] ? parts[0].replace('ds:', '') : '',
      table: parts[1] || ''
    }
  })
})

// Filtered Resources
const filteredResources = computed(() => {
  if (!searchQuery.value) return props.resources
  const query = searchQuery.value.toLowerCase()
  return props.resources.filter(r => 
    r.resource_name.toLowerCase().includes(query) ||
    r.resource_key.toLowerCase().includes(query) ||
    (r.resource_group && r.resource_group.toLowerCase().includes(query))
  )
})

const close = () => {
  emit('close')
}

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      if (props.initialTab === 'changes' && props.showChangeNotificationsTab) {
        activeTab.value = 'changes'
      } else if (props.initialTab === 'about' && props.showAboutTab) {
        activeTab.value = 'about'
      } else {
        activeTab.value = 'resource'
      }
    }
  },
)

const onChangeNotificationsRead = (unread: number) => {
  emit('change-notifications-read', unread)
}

const onNavigateProduct = (productKey: string) => {
  close()
  router.push({ name: 'CatalogDetail', params: { key: productKey }, query: { tab: 'changes' } })
}

const onNavigateResource = (resourceKey: string) => {
  close()
  router.push({ name: 'ResourceEdit', params: { key: resourceKey }, query: { tab: 'history' } })
}

const toggleFields = (resource: any) => {
  if (activeFieldsResource.value === resource.resource_key) {
    activeFieldsResource.value = null
  } else {
    activeFieldsResource.value = resource.resource_key
  }
}

const showExample = (resource: any) => {
  exampleResource.value = resource
  exampleTab.value = 'universal'
}

const closeExample = () => {
    exampleResource.value = null
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  // Fix Safari compatibility & Timezone
  let dateInput = typeof dateStr === 'string' ? dateStr.replace(' ', 'T') : dateStr;
  if (typeof dateInput === 'string' && !dateInput.endsWith('Z') && !dateInput.includes('+')) {
      dateInput += 'Z';
  }
  return new Date(dateInput).toLocaleDateString()
}

const copyText = async (text: string, label: string = '内容') => {
  const success = await copyToClipboard(text)
  if (success) {
     emit('show-toast', `已复制 ${label}`, 'success')
  } else {
     emit('show-toast', '复制失败', 'error')
  }
}

const copyCode = async (code: string) => {
    const success = await copyToClipboard(code)
    if (success) {
        emit('show-toast', '代码已复制', 'success')
    } else {
        emit('show-toast', '复制失败', 'error')
    }
}

const getExampleCode = (resource: any) => {
   const baseUrl = window.location.origin
   const key = localStorage.getItem('api_key') || 'YOUR_API_KEY'
   
   if (exampleTab.value === 'universal') {
     return `curl -X POST "${baseUrl}/api/v1/query" \\
  -H "X-API-Key: ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "resource": "${resource.resource_key}",
    "filters": [],
    "page": 1,
    "size": 10
  }'`
   } else {
     return `curl -X GET "${baseUrl}/api/v1/resources/${resource.resource_key}?page=1&size=10" \\
  -H "X-API-Key: ${key}"`
   }
}

</script>
