<script setup lang="ts">
import { ref, onMounted, computed, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from '../../utils/axios'
import Toast from '../../components/Toast.vue'
import { Codemirror } from 'vue-codemirror'
import { sql } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => route.params.key !== 'create')
const resourceKeyParam = route.params.key as string

const loading = ref(false)
const saving = ref(false)
const isAdmin = ref(false)

// Check user role
const userInfo = ref<any>(null)

const checkRole = () => {
    try {
        const userInfoStr = localStorage.getItem('user_info')
        if (userInfoStr) {
            userInfo.value = JSON.parse(userInfoStr)
            isAdmin.value = userInfo.value.role === 'admin'
        }
    } catch (e) {
        console.error('Failed to parse user info', e)
    }
}

const hasPerm = (code: string) => {
    if (isAdmin.value) return true
    return userInfo.value?.permissions?.elements?.includes(code)
}



// Form Data API Model
const form = ref({
    resource_key: '',
    resource_name: '',
    resource_group: '',
    data_source: '',
    resource_mode: 'TABLE', // TABLE or SQL
    table_name: '',
    custom_sql: '',
    fields_config: [] as {name: string, label: string, type: string}[],
    allowed_filters: [] as {name: string, label: string, type: string}[],
    default_sort: '',
    status: 1,
    remarks: '',
    reference_count: 0,
    cache_ttl: 0
})

// UI Helper State for JSON/List fields
// Deleted obsolete text helpers

// Toast
const toast = ref({ show: false, message: '', type: 'info' as any, key: 0 })
const showToast = (msg: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
  toast.value = { show: true, message: msg, type, key: toast.value.key + 1 }
}
const closeToast = () => { toast.value.show = false }

// Fetch Data
const fetchResource = async () => {
    if (!isEdit.value) return
    loading.value = true
    try {
        const response = await axios.get(`/api/portal/meta/resources`)
        const all = response.data
        const found = all.find((r: any) => r.resource_key === resourceKeyParam)
        if (found) {
            form.value = { ...found }
            // Ensure array structure for config fields
            if (!Array.isArray(form.value.fields_config)) form.value.fields_config = []
            if (!Array.isArray(form.value.allowed_filters)) form.value.allowed_filters = []
            
            // Populate Introspection Data if possible
            if (form.value.data_source) {
                 await fetchTables()
                 fetchColumns(true) // quiet fetch
            }
        } else {
            showToast('Resource not found', 'error')
        }
    } catch (e: any) {
        showToast(e.response?.data?.detail || 'Fetch failed', 'error')
    } finally {
        loading.value = false
    }
}

// Check for Imported Data
onMounted(() => {
    checkRole()
    fetchDataSources()
    fetchGroups()
    if (isEdit.value) {
        fetchResource()
    } else {
        // Check for router state data
        const state = history.state
        if (state && state.importedData) {
            const data = state.importedData
            // Remove ID-like fields to avoid conflicts
            delete data.id
            delete data.created_at
            delete data.updated_at
            // Pre-fill form
            form.value = { ...form.value, ...data, resource_key: data.resource_key + '_copy' }
            showToast('配置已导入，请修改标识并保存', 'success')
            
            // Normalize Types
             if (Array.isArray(form.value.fields_config)) {
               form.value.fields_config.forEach(f => f.type = normalizeType(f.type))
            }
             if (Array.isArray(form.value.allowed_filters)) {
               form.value.allowed_filters.forEach(f => f.type = normalizeType(f.type))
            }
        }
    }
})

// Introspection State
const availableTables = ref<any[]>([])
const availableColumns = ref<{name: string, type: string, comment?: string}[]>([])
const analyzing = ref(false)
const availableDataSources = ref<any[]>([])
const existingGroups = ref<string[]>([])

// Fetch Existing Groups
const fetchGroups = async () => {
    try {
        const res = await axios.get('/api/portal/meta/resources')
        const groups = new Set<string>()
        res.data.forEach((r: any) => {
            if (r.resource_group) groups.add(r.resource_group)
        })
        existingGroups.value = Array.from(groups).sort()
    } catch (e) {
        console.error("Failed to fetch groups", e)
    }
}

// Fetch Data Sources
const fetchDataSources = async () => {
  try {
    const res = await axios.get('/api/portal/datasource/datasources?status=active')
    availableDataSources.value = res.data        // Set default if creating new and list is not empty
        if (!isEdit.value && availableDataSources.value.length > 0 && !form.value.data_source) {
             form.value.data_source = availableDataSources.value[0].source_name
        }
    } catch (e) {
        console.error("Failed to load datasources", e)
    }
}

// Selectable Import Dialog State
const showImportDialog = ref(false)
const importTarget = ref<'fields_config' | 'allowed_filters'>('fields_config')
const selectedColumnNames = ref<string[]>([])
const showTemplateHelp = ref(false)

// Fetch Tables
const fetchTables = async () => {
    if (!form.value.data_source) return
    try {
        const res = await axios.post('/api/portal/meta/datasource/tables', {
            data_source: form.value.data_source
        })
        availableTables.value = res.data.tables
    } catch (e: any) {
        showToast('获取表列表失败', 'error')
    }
}

// Fetch Columns (for Table or SQL)
const fetchColumns = async (quiet = false) => {
    if (!form.value.data_source) return
    if (form.value.resource_mode === 'TABLE' && !form.value.table_name) return
    if (form.value.resource_mode === 'SQL' && !form.value.custom_sql) return

    analyzing.value = true
    try {
        const res = await axios.post('/api/portal/meta/datasource/columns', {
            data_source: form.value.data_source,
            table_name: form.value.resource_mode === 'TABLE' ? form.value.table_name : undefined,
            custom_sql: form.value.resource_mode === 'SQL' ? form.value.custom_sql : undefined,
            params: testParams.value
        })
        availableColumns.value = res.data.columns
        if (!quiet) showToast('字段获取成功', 'success')
    } catch (e: any) {
        if (!quiet) showToast('获取字段失败: ' + (e.response?.data?.detail || e.message), 'error')
    } finally {
        analyzing.value = false
    }
}

// Selective import logic
const openImportDialog = async (target: 'fields_config' | 'allowed_filters') => {
    if (availableColumns.value.length === 0) {
        await fetchColumns(false)
    }
    if (availableColumns.value.length === 0) return

    importTarget.value = target
    // Pre-select columns already in the config
    selectedColumnNames.value = form.value[target].map(f => f.name)
    showImportDialog.value = true
}

const confirmImport = () => {
    const target = importTarget.value
    
    // Add new columns or update types for existing ones
    // We only keep what's selected
    const newConfig: {name: string, label: string, type: string}[] = []
    
    selectedColumnNames.value.forEach(name => {
        const col = availableColumns.value.find(c => c.name === name)
        if (!col) return

        const existing = form.value[target].find(f => f.name === name)
        if (existing) {
            newConfig.push({
                ...existing,
                type: col.type // Sync type
            })
        } else {
            newConfig.push({
                name: col.name,
                label: col.comment || col.name,
                type: normalizeType(col.type)
            })
        }
    })

    form.value[target] = newConfig
    showImportDialog.value = false
    showToast(`成功同步 ${newConfig.length} 个字段`, 'success')
}

const toggleAllColumns = () => {
    if (selectedColumnNames.value.length === availableColumns.value.length) {
        selectedColumnNames.value = []
    } else {
        selectedColumnNames.value = availableColumns.value.map(c => c.name)
    }
}

const removeField = (target: 'fields_config' | 'allowed_filters', index: number) => {
    form.value[target].splice(index, 1)
}

const normalizeType = (dbType: string): string => {
    const t = dbType.toLowerCase()
    if (t.includes('string') || t.includes('char') || t.includes('text')) return 'String'
    if (t.includes('int') || t.includes('float') || t.includes('double') || t.includes('decimal')) return 'Long'
    if (t.includes('date') || t.includes('time')) return 'Date'
    return 'String' // Default
}

// Watchers
import { watch } from 'vue'
watch(() => form.value.data_source, (val) => {
    if (val) fetchTables()
})
watch(() => form.value.table_name, () => {
    if (form.value.resource_mode === 'TABLE') fetchColumns()
})

// Save
const save = async () => {
    if (!form.value.default_sort) {
        showToast('请选择默认排序字段，以确保分页查询性能和结果稳定性', 'warning')
        return
    }
    saving.value = true
    try {
        if (isEdit.value) {
            await axios.put(`/api/portal/meta/resources/${resourceKeyParam}`, form.value)
            showToast('资源更新成功', 'success')
        } else {
            await axios.post('/api/portal/meta/resources', form.value)
            showToast('资源创建成功', 'success')
            router.push('/dashboard/resources')
        }
    } catch (e: any) {
        showToast(e.response?.data?.detail || '保存失败', 'error')
    } finally {
        saving.value = false
    }
}

// API URL Helper
const apiUrl = computed(() => {
    if (!form.value.resource_key) return ''
    const host = window.location.origin
    return `${host}/api/v1/resources/${form.value.resource_key}`
})

const copyApiUrl = async () => {
    try {
        await navigator.clipboard.writeText(apiUrl.value)
        showToast('连接已复制', 'success')
    } catch (e) {
        showToast('复制失败', 'error')
    }
}

// ----- Test Console Logic -----
const testParams = ref<Record<string, any>>({
    page: 1,
    size: 20
})
const testResult = ref<any>(null)
const testLoading = ref(false)
const activeTab = ref('config') // config | test

const runTest = async () => {
    // Need to save first? No, Universal API reads from DB.
    // So user MUST save changes before testing if they want to test NEW changes.
    // We should warn user if they changed form but didn't save.
    // For now, assume user saved.
    
    // Validation: If there are allowed filters, at least one must be filled
    if (form.value.allowed_filters && form.value.allowed_filters.length > 0) {
        const hasFilter = form.value.allowed_filters.some(f => {
            const val = testParams.value[f.name];
            return val !== undefined && val !== null && val.toString().trim() !== '';
        });
        
        if (!hasFilter) {
            showToast('为了防止全量查询，请至少输入一个过滤参数进行测试', 'warning');
            return;
        }
    }

    // Construct Query Params
    const key = isEdit.value ? resourceKeyParam : form.value.resource_key
    if (!key) return
    
    testLoading.value = true
    testResult.value = null
    
    try {
        const params = { ...testParams.value }
        const res = await axios.get(`/api/portal/meta/resources/${key}/test`, { params })
        testResult.value = res.data
    } catch (e: any) {
        testResult.value = { error: e.response?.data || e.message }
    } finally {
    testLoading.value = false
    }
}

const showJsonResult = ref(false)
const runTestJson = async () => {
    showJsonResult.value = true
    await runTest()
}

const copyText = async (text: string) => {
    try {
        await navigator.clipboard.writeText(text)
        showToast('已复制到剪贴板', 'success')
    } catch (e) {
        showToast('复制失败', 'error')
    }
}

// Codemirror Extensions
const extensions = shallowRef([sql(), oneDark])
const view = shallowRef()
const handleReady = (payload: any) => {
  view.value = payload.view
}

</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
        <div class="flex items-center space-x-4">
            <button @click="router.back()" class="bg-white p-2 rounded-lg shadow-sm border border-gray-200 text-gray-500 hover:text-blue-600 hover:border-blue-300 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/></svg>
            </button>
            <div>
                <h1 class="text-2xl font-bold text-gray-900">{{ isEdit ? '编辑资源' : '新建资源' }}</h1>
                <p class="text-sm text-gray-500 mt-0.5">{{ isEdit ? '管理接口元数据与数据源映射' : '定义新的数据资源接口' }}</p>
            </div>
        </div>
        
        <div class="flex items-center space-x-4">
            <!-- Tabs (Styled like Users filters or segmented control) -->
            <div class="flex bg-gray-200/50 p-1 rounded-xl">
                <button 
                    @click="activeTab = 'config'"
                    class="px-4 py-2 rounded-lg text-sm font-bold transition-all"
                    :class="activeTab === 'config' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500 hover:text-gray-700'"
                >
                  <span class="flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /></svg>
                    基础配置
                  </span>
                </button>
                <button 
                    @click="activeTab = 'test'"
                    class="px-4 py-2 rounded-lg text-sm font-bold transition-all"
                    :class="activeTab === 'test' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500 hover:text-gray-700'"
                >
                  <span class="flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
                    测试控制台
                  </span>
                </button>
            </div>
            
            <button 
                v-if="activeTab === 'config' && hasPerm('element:resource:edit')"
                @click="save" 
                :disabled="saving"
                class="px-6 py-2 bg-blue-600 text-white font-bold rounded-lg hover:bg-blue-700 shadow-md shadow-blue-200 transition-all disabled:opacity-50 flex items-center gap-2"
            >
                <svg v-if="!saving" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" /></svg>
                <span v-else class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
                {{ saving ? '正在保存...' : '保存更改' }}
            </button>
        </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-10">加载中...</div>

    <!-- Config Form -->
    <div v-show="activeTab === 'config' && !loading" class="bg-white shadow rounded-lg p-6 space-y-6">
        <!-- Basic Info -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 flex items-center">
                    资源标识 (Key)
                    <span class="custom-tooltip" data-tooltip="资源标识：对于接口的名称，英文。例如 'yunshu_rooms'">
                        <svg class="w-4 h-4 ml-1 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </span>
                </label>
                <input v-model="form.resource_key" :disabled="isEdit || !hasPerm('element:resource:edit')" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm disabled:bg-gray-50" />
                <p class="mt-1 text-xs text-gray-500">唯一标识符，用于 API 路径。</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 flex items-center">
                    资源名称 (中文)
                    <span class="custom-tooltip" data-tooltip="资源名称：用于在界面显示的中文描述。">
                        <svg class="w-4 h-4 ml-1 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </span>
                </label>
                <input v-model="form.resource_name" :disabled="!hasPerm('element:resource:edit')" type="text" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm disabled:bg-gray-50" />
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 flex items-center">
                    分组
                    <span class="custom-tooltip" data-tooltip="分组：用于 API 文档的分组导航。例如：智服平台, 动环数据">
                        <svg class="w-4 h-4 ml-1 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </span>
                </label>
                <input
                  v-model="form.resource_group"
                  :disabled="!hasPerm('element:resource:edit')"
                  list="group-suggestions"
                  type="text"
                  placeholder="从列表选择或输入新分组（建议英文/下划线）"
                  class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm disabled:bg-gray-50"
                  @blur="form.resource_group = (form.resource_group || '').trim()"
                />
                <p class="mt-1 text-xs text-gray-400">请优先从已有分组中选择，避免「SQL-LAB」与「SQL_LAB」等重复分组。</p>
                <datalist id="group-suggestions">
                    <option v-for="g in existingGroups" :key="g" :value="g"></option>
                </datalist>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700">数据源</label>
                <select v-model="form.data_source" :disabled="!hasPerm('element:resource:edit')" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm disabled:bg-gray-50">
                    <option value="" disabled>选择数据源...</option>
                    <option v-for="ds in availableDataSources" :key="ds.id" :value="ds.source_name">
                        {{ ds.source_name }} ({{ ds.source_type }})
                    </option>
                </select>
            </div>
            <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700">备注</label>
                <textarea v-model="form.remarks" :disabled="!hasPerm('element:resource:edit')" rows="2" placeholder="在此输入资源的补充说明信息 (非必填)" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm disabled:bg-gray-50"></textarea>
            </div>
        </div>

        <!-- API URL Display -->
        <div v-if="isEdit" class="bg-gray-50 p-4 rounded-md border border-gray-200">
             <label class="block text-xs font-medium text-gray-500 uppercase">Universal API URL</label>
             <div class="mt-1 flex rounded-md shadow-sm">
                 <input type="text" :value="apiUrl" readonly class="flex-1 min-w-0 block w-full px-3 py-2 rounded-none rounded-l-md border border-gray-300 bg-white text-sm text-gray-500" />
                 <button @click="copyApiUrl" class="inline-flex items-center px-3 py-2 border border-l-0 border-gray-300 rounded-r-md bg-gray-100 text-gray-500 hover:bg-gray-200 text-sm font-medium">
                     复制
                 </button>
             </div>
        </div>
        
        <!-- Status & Stats -->
         <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
             <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">资源状态</label>
                <div class="flex items-center space-x-6">
                    <div class="flex items-center">
                        <button 
                            @click="hasPerm('element:resource:edit') && (form.status = form.status === 1 ? 0 : 1)" 
                            type="button"
                            :class="[form.status === 1 ? 'bg-green-500' : 'bg-gray-200', !hasPerm('element:resource:edit') ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer']"
                            class="relative inline-flex h-6 w-11 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none"
                        >
                            <span 
                            :class="form.status === 1 ? 'translate-x-5' : 'translate-x-0'"
                            class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
                            ></span>
                        </button>
                        <span class="ml-3 text-sm text-gray-900">{{ form.status === 1 ? '启用' : '禁用' }}</span>
                    </div>

                    <!-- Cache TTL Input (Moved here for better layout) -->
                    <div class="flex items-center space-x-2 border-l border-gray-200 pl-6">
                        <label class="block text-sm font-medium text-gray-700 whitespace-nowrap flex items-center">
                            <span class="mr-1">⚡️ 缓存 (秒)</span>
                             <span class="custom-tooltip" data-tooltip="查询结果缓存时间 (TTL)。0 表示不缓存。设置后，通过 universal API 查询时将返回 X-Cache: HIT。适合更新频率低的数据。">
                                <svg class="w-4 h-4 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                            </span>
                        </label>
                        <input 
                            v-model.number="form.cache_ttl" 
                            :disabled="!hasPerm('element:resource:edit')"
                            type="number" 
                            min="0"
                            class="block w-24 border border-gray-300 rounded-md shadow-sm py-1 px-2 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm text-right font-mono"
                        />
                    </div>
                </div>
             </div>
             <div v-if="isEdit">
                 <label class="block text-sm font-medium text-gray-700">引用统计</label>
                 <div class="mt-1 text-sm text-gray-900 font-mono bg-gray-50 px-3 py-2 rounded-md inline-block">
                     {{ form.reference_count || 0 }} 个用户
                 </div>
             </div>
         </div>

        <hr class="border-gray-200" />

        <!-- Mode & Source -->
        <!-- Mode & Source -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-2 flex items-center">
                资源模式
                <span class="custom-tooltip" data-tooltip="资源模式：TABLE (直接查询物理表，支持自动分页/排序/过滤) 或 SQL (使用自定义 SQL 作为驱动子查询)。">
                    <svg class="w-4 h-4 ml-1 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                </span>
            </label>
            <div class="flex items-center space-x-4">
                <label class="inline-flex items-center">
                    <input type="radio" v-model="form.resource_mode" :disabled="!hasPerm('element:resource:edit')" value="TABLE" class="form-radio text-primary disabled:opacity-50" />
                    <span class="ml-2" :class="!hasPerm('element:resource:edit') ? 'text-gray-400' : ''">直接表 (TABLE)</span>
                </label>
                <label class="inline-flex items-center">
                    <input type="radio" v-model="form.resource_mode" :disabled="!hasPerm('element:resource:edit')" value="SQL" class="form-radio text-primary disabled:opacity-50" />
                    <span class="ml-2" :class="!hasPerm('element:resource:edit') ? 'text-gray-400' : ''">自定义 SQL (SQL)</span>
                </label>
            </div>
        </div>

        <div v-if="form.resource_mode === 'TABLE'">
            <label class="block text-sm font-medium text-gray-700">表名</label>
            <div class="mt-1 flex gap-2">
                <select v-model="form.table_name" :disabled="!hasPerm('element:resource:edit')" class="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm disabled:bg-gray-50 disabled:text-gray-500">
                    <option value="" disabled>选择表...</option>
                    <option v-for="t in availableTables" :key="typeof t === 'string' ? t : t.name" :value="typeof t === 'string' ? t : t.name">
                        {{ typeof t === 'string' ? t : `${t.name} [${t.type}]` }}
                    </option>
                </select>
                <button v-if="hasPerm('element:resource:edit')" @click="fetchTables" class="px-3 py-2 border border-gray-300 rounded-md bg-gray-50 hover:bg-gray-100 text-gray-600">
                    刷新
                </button>
            </div>
        </div>
        <div v-else>
            <!-- Template Help -->
            <div class="mt-4 mb-4 bg-gray-50 p-4 rounded-md border border-gray-200">
                <div class="flex justify-between items-center cursor-pointer" @click="showTemplateHelp = !showTemplateHelp">
                    <h4 class="text-sm font-bold text-gray-700 flex items-center gap-2">
                        <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        SQL 模板注入指南 (高级)
                    </h4>
                    <svg class="w-4 h-4 text-gray-500 transform transition-transform" :class="showTemplateHelp ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                </div>
                <div v-if="showTemplateHelp" class="mt-3 text-xs text-gray-600 space-y-2">
                    <p>支持使用 <strong>Jinja2 模板语法</strong> 动态注入过滤条件，极大提升聚合查询性能。</p>
                    <div v-pre class="bg-gray-800 text-gray-200 p-3 rounded font-mono overflow-x-auto">
                        <div class="text-green-400">-- 示例：仅当传入 city 参数时才添加过滤</div>
                        <div>SELECT * FROM my_table</div>
                        <div>WHERE 1=1</div>
                        <div>{% if city %}</div>
                        <div class="pl-4">AND city = {city}  <span class="text-gray-500">-- {city} 为参数占位符，安全防注入</span></div>
                        <div>{% endif %}</div>
                        <div>{% if start_time %}</div>
                        <div class="pl-4">AND metric_time >= {start_time}</div>
                        <div>{% endif %}</div>
                    </div>
                    <ul class="list-disc pl-5 space-y-1">
                        <li><strong>逻辑控制：</strong>使用 <code>{% if param %} ... {% endif %}</code> 判断参数是否存在。</li>
                        <li><strong>参数绑定：</strong>使用 <code>{param}</code> 插入参数值（ClickHouse 语法）。</li>
                        <li><strong>自动剔除：</strong>在此处手动引用的参数，系统将<strong>不会</strong>再次在外层自动生成 WHERE 条件。</li>
                        <li><strong>注意：</strong>参数名必须与“允许过滤配置”中的字段名一致。</li>
                    </ul>
                    
                    <div class="mt-4 pt-4 border-t border-gray-300">
                        <p class="text-green-600 font-semibold mb-2">---多个值的情况：</p>
                        <div v-pre class="bg-gray-800 text-gray-200 p-3 rounded font-mono overflow-x-auto text-xs">
                            <div class="text-green-400">-- 支持单值或多值过滤，如 rowkey=xxx 或 rowkey=["111","222"]</div>
                            <div class="text-green-400">-- 示例：多值 IN 查询（rowkey 参数为数组）</div>
                            <div>SELECT *</div>
                            <div>FROM yovole_dm_clickhouse_prod.ck_fact_donghuan_real_metric_hbase</div>
                            <div>WHERE toYYYYMMDD(toDateTime(toInt64(metric_time))) = toYYYYMMDD(today())</div>
                            <div></div>
                            <div>{% if rowkey %}</div>
                            <div>AND rowkey IN (</div>
                            <div class="pl-4">{% if rowkey is string or rowkey is number %}</div>
                            <div class="pl-8">'{{ rowkey }}'</div>
                            <div class="pl-4">{% else %}</div>
                            <div class="pl-8">{% for key in rowkey %}</div>
                            <div class="pl-12">'{{ key }}'{% if not loop.last %},{% endif %}</div>
                            <div class="pl-8">{% endfor %}</div>
                            <div class="pl-4">{% endif %}</div>
                            <div>)</div>
                            <div>{% endif %}</div>
                            <div></div>
                            <div>ORDER BY rowkey ASC, metric_time DESC</div>
                            <div>LIMIT 1 BY rowkey</div>
                        </div>
                        <ul class="list-disc pl-5 space-y-1 mt-2">
                            <li><strong>数组判断：</strong>使用 <code>{% if rowkey and rowkey|length > 0 %}</code> 检查数组是否存在且非空。</li>
                            <li><strong>循环遍历：</strong>使用 <code>{% for key in rowkey %}</code> 遍历数组元素。</li>
                            <li><strong>条件逗号：</strong>使用 <code>{% if not loop.last %},{% endif %}</code> 在元素间添加逗号。</li>
                            <li><strong>变量引用：</strong>使用 <code v-pre>{{ key }}</code> 输出数组元素的值。</li>
                        </ul>
                    </div>
                </div>
            </div>

            <label class="block text-sm font-medium text-gray-700 mb-1">自定义 SQL</label>
            <div class="border border-gray-300 rounded-md shadow-sm overflow-hidden">
                <codemirror
                    v-model="form.custom_sql"
                    :disabled="!hasPerm('element:resource:edit')"
                    placeholder="SELECT * FROM table JOIN ..."
                    :style="{ height: '300px' }"
                    :autofocus="true"
                    :indent-with-tab="true"
                    :tab-size="4"
                    :extensions="extensions"
                    @ready="handleReady"
                />
            </div>
            <div class="mt-2 flex justify-between items-start">
               <div class="bg-yellow-50 border-l-4 border-yellow-400 p-2 text-xs text-yellow-700 max-w-lg">
                   警告：不要包含分号 (; )。SQL 将作为子查询执行。
               </div>
               <button v-if="hasPerm('element:resource:edit')" @click="() => fetchColumns(false)" :disabled="analyzing" class="px-4 py-2 bg-indigo-100 text-indigo-700 rounded-md hover:bg-indigo-200 text-sm font-medium">
                   {{ analyzing ? '解析中...' : '解析 SQL 获取字段' }}
               </button>
            </div>
            
            <!-- Template Help Moved -->
        </div>

        <hr class="border-gray-200" />

        <!-- Fields Config -->
        <div class="space-y-4">
            <div class="flex justify-between items-center">
                <label class="block text-lg font-semibold text-gray-900 flex items-center">
                    字段配置 (Fields Config)
                    <span class="custom-tooltip" data-tooltip="字段配置：定义 API 返回的列及其展示标签。配置中文名称和数据类型以便于生成文档和模型查阅。">
                        <svg class="w-4 h-4 ml-2 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </span>
                </label>
                <div v-if="hasPerm('element:resource:edit')" class="space-x-2">
                    <button @click="openImportDialog('fields_config')" class="px-3 py-1 bg-indigo-50 text-indigo-700 text-sm font-medium rounded hover:bg-indigo-100">
                        从数据库导入/同步
                    </button>
                    <button @click="form.fields_config = []" class="px-3 py-1 bg-red-50 text-red-700 text-sm font-medium rounded hover:bg-red-100">
                        清空
                    </button>
                </div>
            </div>
            
            <div class="border border-gray-200 rounded-lg overflow-hidden">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">字段名 (Name)</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">中文名称 (Label)</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">数据类型 (DataType)</th>
                            <th v-if="hasPerm('element:resource:edit')" class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        <tr v-for="(field, index) in form.fields_config" :key="field.name">
                            <td class="px-4 py-2 text-sm font-mono text-gray-900">{{ field.name }}</td>
                            <td class="px-4 py-2">
                                <input v-model="field.label" :disabled="!hasPerm('element:resource:edit')" type="text" class="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:ring-primary focus:border-primary" />
                            </td>
                            <td class="px-4 py-2">
                                <select v-model="field.type" :disabled="!hasPerm('element:resource:edit')" class="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:ring-primary focus:border-primary font-mono text-xs">
                                    <option value="String">String</option>
                                    <option value="Long">Long</option>
                                    <option value="Date">Date</option>
                                </select>
                            </td>
                            <td v-if="hasPerm('element:resource:edit')" class="px-4 py-2 text-right">
                                <button @click="removeField('fields_config', index)" class="text-red-600 hover:text-red-900">
                                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                </button>
                            </td>
                        </tr>
                        <tr v-if="form.fields_config.length === 0">
                            <td colspan="4" class="px-4 py-8 text-center text-sm text-gray-500 italic">暂无已选字段，点击同步从数据库获取</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <hr class="border-gray-200" />

        <!-- Filters Config -->
        <div class="space-y-4">
            <div class="flex justify-between items-center">
                <label class="block text-lg font-semibold text-gray-900 flex items-center">
                    允许过滤配置 (Allowed Filters)
                    <span class="custom-tooltip" data-tooltip="过滤配置：允许客户端进行筛选的字段集合。配置中文标签以便快速理解查询参数。">
                        <svg class="w-4 h-4 ml-2 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </span>
                </label>
                <div v-if="hasPerm('element:resource:edit')" class="space-x-2">
                    <button @click="openImportDialog('allowed_filters')" class="px-3 py-1 bg-indigo-50 text-indigo-700 text-sm font-medium rounded hover:bg-indigo-100">
                        从数据库导入/同步
                    </button>
                    <button @click="form.allowed_filters = []" class="px-3 py-1 bg-red-50 text-red-700 text-sm font-medium rounded hover:bg-red-100">
                        清空
                    </button>
                </div>
            </div>
            
            <div class="border border-gray-200 rounded-lg overflow-hidden">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">字段名 (Name)</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">中文名称 (Label)</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">数据类型 (DataType)</th>
                            <th v-if="hasPerm('element:resource:edit')" class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        <tr v-for="(field, index) in form.allowed_filters" :key="field.name">
                            <td class="px-4 py-2 text-sm font-mono text-gray-900">{{ field.name }}</td>
                            <td class="px-4 py-2">
                                <input v-model="field.label" :disabled="!hasPerm('element:resource:edit')" type="text" class="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:ring-primary focus:border-primary" />
                            </td>
                            <td class="px-4 py-2">
                                <select v-model="field.type" :disabled="!hasPerm('element:resource:edit')" class="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:ring-primary focus:border-primary font-mono text-xs">
                                    <option value="String">String</option>
                                    <option value="Long">Long</option>
                                    <option value="Date">Date</option>
                                </select>
                            </td>
                            <td v-if="hasPerm('element:resource:edit')" class="px-4 py-2 text-right">
                                <button @click="removeField('allowed_filters', index)" class="text-red-600 hover:text-red-900">
                                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                </button>
                            </td>
                        </tr>
                        <tr v-if="form.allowed_filters.length === 0">
                            <td colspan="4" class="px-4 py-8 text-center text-sm text-gray-500 italic">暂无已选过滤字段，点击同步从数据库获取</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <hr class="border-gray-200" />

        <div>
            <label class="block text-sm font-medium text-gray-700">默认排序字段</label>
            <select v-model="form.default_sort" :disabled="!hasPerm('element:resource:edit')" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm">
                <option value="">无</option>
                <option v-for="col in availableColumns" :key="col.name" :value="col.name">{{ col.name }}</option>
                <option v-if="form.default_sort && !availableColumns.find(c => c.name === form.default_sort)" :value="form.default_sort">{{ form.default_sort }} (Custom)</option>
            </select>
        </div>
    </div>

    <!-- Test Console -->
    <div v-show="activeTab === 'test'" class="bg-white shadow rounded-lg p-6">
        <div class="mb-4">
             <label class="block text-xs font-medium text-gray-500 uppercase">测试接口 API URL</label>
             <div class="mt-1 flex rounded-md shadow-sm">
                 <input type="text" :value="apiUrl" readonly class="flex-1 min-w-0 block w-full px-3 py-2 rounded-none rounded-l-md border border-gray-300 bg-white text-sm text-gray-500" />
                 <button @click="copyApiUrl" class="inline-flex items-center px-3 py-2 border border-l-0 border-gray-300 rounded-r-md bg-gray-100 text-gray-500 hover:bg-gray-200 text-sm font-medium">
                     复制
                 </button>
             </div>
        </div>

        <div class="mb-4 bg-blue-50 p-4 rounded-md">
            <h3 class="text-sm font-medium text-blue-800">测试控制台</h3>
            <p class="text-xs text-blue-600 mt-1">请先保存配置，再运行测试。</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
             <!-- Standard Params -->
             <div>
                <label class="block text-xs font-medium text-gray-500 uppercase">页码 (Page)</label>
                <input v-model.number="testParams.page" type="number" class="mt-1 block w-full border border-gray-300 rounded-md px-2 py-1 text-sm"/>
             </div>
             <div>
                <label class="block text-xs font-medium text-gray-500 uppercase">每页条数 (Size)</label>
                <input v-model.number="testParams.size" type="number" class="mt-1 block w-full border border-gray-300 rounded-md px-2 py-1 text-sm"/>
             </div>
        </div>

        <!-- Dynamic Filter inputs -->
        <div class="mb-4">
            <h4 class="text-xs font-medium text-gray-500 uppercase mb-2">过滤参数 (Filters)</h4>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div v-for="filter in form.allowed_filters" :key="filter.name">
                    <label class="block text-xs text-gray-600">{{ filter.label || filter.name }}</label>
                    <input v-model="testParams[filter.name]" type="text" placeholder="值" class="mt-1 block w-full border border-gray-300 rounded-md px-2 py-1 text-sm"/>
                </div>
            </div>
        </div>

        <div class="flex space-x-2">
            <button @click="runTest" :disabled="testLoading" class="flex-1 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 mb-6 font-medium">
                {{ testLoading ? '执行中...' : '运行测试 (Table View)' }}
            </button>
             <button @click="runTestJson" :disabled="testLoading" class="flex-1 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 mb-6 font-medium">
                {{ testLoading ? '执行中...' : '运行测试 (JSON View)' }}
            </button>
        </div>

        <!-- Result -->
        <div v-if="testResult">
            <div v-if="testResult.error" class="bg-red-50 p-4 rounded text-red-700">
                Error: {{ testResult.error }}
            </div>
            <div v-else>
                 <!-- Generated SQL View (for debugging) -->
                 <div v-if="testResult.data?.generated_sql" class="mb-6">
                    <div class="flex items-center justify-between mb-2">
                        <h4 class="text-xs font-bold text-indigo-500 uppercase flex items-center gap-1">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
                            实际执行的 SQL (调试用)
                        </h4>
                        <button @click="copyText(testResult.data.generated_sql)" class="text-xs text-indigo-600 hover:underline">复制 SQL</button>
                    </div>
                    <pre class="bg-gray-50 border border-gray-200 text-gray-700 p-4 rounded-lg text-[13px] font-mono overflow-auto max-h-48 whitespace-pre-wrap leading-relaxed shadow-inner">{{ testResult.data.generated_sql }}</pre>
                 </div>

                 <div class="flex justify-between items-center mb-2">
                     <span class="text-sm font-medium">Total: {{ testResult.data?.total }}</span>
                     <span class="text-xs text-gray-500">Page {{ testResult.data?.page }} / {{ testResult.data?.pages }}</span>
                 </div>
                 <div class="overflow-x-auto border border-gray-200 rounded">
                     <table class="min-w-full divide-y divide-gray-200">
                         <thead class="bg-gray-50">
                             <tr>
                                 <th v-for="col in (form.fields_config.length ? form.fields_config.map(f => f.name) : Object.keys(testResult.data?.items[0] || {}))" :key="col" class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap">
                                     {{ col }}
                                 </th>
                             </tr>
                         </thead>
                         <tbody class="bg-white divide-y divide-gray-200">
                             <tr v-for="(row, idx) in testResult.data?.items" :key="idx">
                                 <td v-for="col in (form.fields_config.length ? form.fields_config.map(f => f.name) : Object.keys(row))" :key="col" class="px-4 py-2 text-sm text-gray-900 whitespace-nowrap">
                                     {{ row[col] }}
                                 </td>
                             </tr>
                         </tbody>
                     </table>
                     <div v-if="testResult.data?.items?.length === 0" class="p-4 text-center text-gray-500 text-sm">暂无数据</div>
                 </div>
                 
                 <!-- JSON View -->
                 <div v-if="showJsonResult" class="mt-4">
                    <h4 class="text-xs font-medium text-gray-500 uppercase mb-2">JSON 响应结果</h4>
                    <pre class="bg-gray-800 text-green-400 p-4 rounded text-xs font-mono overflow-auto max-h-96">{{ JSON.stringify(testResult, null, 2) }}</pre>
                 </div>
            </div>
        </div>
    </div>

    <!-- Teleported Toast -->
    <teleport to="body">
      <Toast v-if="toast.show" :key="toast.key" :message="toast.message" :type="toast.type" @close="closeToast" />

      <!-- Selective Import Dialog -->
      <div v-if="showImportDialog" class="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
        <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
          <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" @click="showImportDialog = false"></div>
          <span class="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
          <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-xl sm:w-full">
            <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
              <div class="sm:flex sm:items-start">
                <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left w-full">
                  <h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    选择导入字段 ({{ importTarget === 'fields_config' ? '字段配置' : '允许过滤' }})
                  </h3>
                  <div class="mt-4">
                    <div class="flex justify-between items-center mb-2">
                        <span class="text-sm text-gray-500">检测到 {{ availableColumns.length }} 个字段</span>
                        <button @click="toggleAllColumns" class="text-sm text-primary hover:text-primary-dark font-medium">
                            {{ selectedColumnNames.length === availableColumns.length ? '取消全选' : '全选' }}
                        </button>
                    </div>
                    <div class="max-h-96 overflow-y-auto border border-gray-200 rounded-md">
                        <table class="min-w-full divide-y divide-gray-200">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">选择</th>
                                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">列名</th>
                                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">备注/类型</th>
                                </tr>
                            </thead>
                            <tbody class="bg-white divide-y divide-gray-200">
                                <tr v-for="col in availableColumns" :key="col.name" @click="() => {
                                    const idx = selectedColumnNames.indexOf(col.name);
                                    if(idx > -1) selectedColumnNames.splice(idx, 1);
                                    else selectedColumnNames.push(col.name);
                                }" class="cursor-pointer hover:bg-gray-50">
                                    <td class="px-4 py-2">
                                        <input type="checkbox" :value="col.name" v-model="selectedColumnNames" @click.stop class="rounded border-gray-300 text-primary focus:ring-primary h-4 w-4" />
                                    </td>
                                    <td class="px-4 py-2 text-sm font-mono text-gray-900">{{ col.name }}</td>
                                    <td class="px-4 py-2 text-xs text-gray-500">
                                        <div>{{ col.comment || '-' }}</div>
                                        <div class="text-gray-400 font-mono">{{ col.type }}</div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
              <button @click="confirmImport" type="button" class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-primary text-base font-medium text-white hover:bg-primary-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:ml-3 sm:w-auto sm:text-sm">
                确认导入 ({{ selectedColumnNames.length }})
              </button>
              <button @click="showImportDialog = false" type="button" class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm">
                取消
              </button>
            </div>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<style scoped>
.custom-tooltip {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.custom-tooltip::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: 150%;
  left: 50%;
  transform: translateX(-50%);
  background-color: rgba(31, 41, 55, 0.95);
  color: white;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  width: max-content;
  max-width: 300px;
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 9999;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  pointer-events: none;
  font-weight: normal;
}

.custom-tooltip::before {
  content: '';
  position: absolute;
  bottom: 120%;
  left: 50%;
  transform: translateX(-50%);
  border-width: 6px;
  border-style: solid;
  border-color: rgba(31, 41, 55, 0.95) transparent transparent transparent;
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 9999;
}

.custom-tooltip:hover::after {
  opacity: 1;
  visibility: visible;
  bottom: 160%;
}

.custom-tooltip:hover::before {
  opacity: 1;
  visibility: visible;
  bottom: 130%;
}
</style>
