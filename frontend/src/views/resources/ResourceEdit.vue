<script setup lang="ts">
import { ref, onMounted, computed, shallowRef, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import axios from '../../utils/axios'
import Toast from '../../components/Toast.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import TablePicker from '@/components/resources/TablePicker.vue'
import ColumnPicker from '@/components/resources/ColumnPicker.vue'
import ResourceVersionDiff from '@/components/resources/ResourceVersionDiff.vue'
import { Codemirror } from 'vue-codemirror'
import { sql } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'
import { isSystemResourceGroup, sortResourceGroups, SYSTEM_RESOURCE_GROUP } from '@/types/resource'
import { copyToClipboard } from '@/utils/clipboard'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => route.params.key !== 'create')
const resourceKeyParam = route.params.key as string

const loading = ref(false)
const saving = ref(false)
const isAdmin = ref(false)
const showAdvanced = ref(false)
const fieldConfigTab = ref<'fields' | 'filters'>('fields')
const groupPickerValue = ref('')
const showValidationBanner = ref(false)
const hasSavedOnce = ref(false)
const initialFormSnapshot = ref('')
const pendingRouteNext = ref<((v?: boolean) => void) | null>(null)
const catalogPublished = ref(false)

const confirmDialog = ref({
  show: false,
  title: '',
  message: '',
  type: 'warning' as 'danger' | 'warning' | 'info',
  confirmText: '确认',
  onConfirm: () => {},
})

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
            syncGroupPickerFromForm()
            hasSavedOnce.value = true
            snapshotForm()
            
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

const fetchCatalogStatus = async () => {
    if (!isEdit.value) {
        catalogPublished.value = false
        return
    }
    try {
        const res = await axios.get('/api/portal/catalog/status-map')
        catalogPublished.value = res.data?.[resourceKeyParam] === 1
    } catch {
        catalogPublished.value = false
    }
}

const toggleResourceStatus = () => {
    if (!hasPerm('element:resource:edit')) return
    if (form.value.status === 1 && catalogPublished.value) {
        showToast('该资源已上架到目录，请先从目录下架后再禁用', 'warning')
        return
    }
    form.value.status = form.value.status === 1 ? 0 : 1
}

// Check for Imported Data
onMounted(() => {
    checkRole()
    fetchDataSources()
    fetchGroups()
    if (isEdit.value) {
        fetchResource().then(() => {
            fetchCatalogStatus()
            if (route.query.tab === 'history') switchToHistoryTab()
        })
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
            syncGroupPickerFromForm()
            snapshotForm()
        } else {
            snapshotForm()
        }
    }
})

onBeforeRouteLeave((_to, _from, next) => {
    if (!isDirty.value) {
        next()
        return
    }
    pendingRouteNext.value = next
    openConfirm({
        title: '未保存的更改',
        message: '离开将丢失未保存的修改，确定离开吗？',
        type: 'warning',
        confirmText: '离开',
        onConfirm: () => {
            confirmDialog.value.show = false
            const proceed = pendingRouteNext.value
            pendingRouteNext.value = null
            proceed?.(true)
        },
    })
    next(false)
})

// Introspection State
const availableTables = ref<any[]>([])
const availableColumns = ref<{name: string, type: string, comment?: string}[]>([])
const analyzing = ref(false)
const availableDataSources = ref<any[]>([])
const existingGroups = ref<string[]>([])

const selectableGroups = computed(() =>
  existingGroups.value.filter((g) => !isSystemResourceGroup(g))
)

const isBuiltinSystemResource = computed(
  () => form.value.resource_mode === 'SYSTEM' || form.value.resource_key.startsWith('system.')
)

// Fetch Existing Groups
const fetchGroups = async () => {
    try {
        const res = await axios.get('/api/portal/meta/resources')
        const groups = new Set<string>()
        res.data.forEach((r: any) => {
            if (r.resource_group && !isSystemResourceGroup(r.resource_group)) groups.add(r.resource_group)
        })
        existingGroups.value = sortResourceGroups(Array.from(groups))
    } catch (e) {
        console.error("Failed to fetch groups", e)
    }
}

const normalizeResourceGroup = () => {
    if (isBuiltinSystemResource.value) return true
    const trimmed = (form.value.resource_group || '').trim()
    if (isSystemResourceGroup(trimmed)) {
        form.value.resource_group = ''
        groupPickerValue.value = ''
        showToast(`${SYSTEM_RESOURCE_GROUP} 为系统内置分组，不可用于普通资源`, 'warning')
        return false
    }
    form.value.resource_group = trimmed
    return true
}

const snapshotForm = () => {
    initialFormSnapshot.value = JSON.stringify(form.value)
}

const isDirty = computed(() => {
    if (!initialFormSnapshot.value) return false
    return JSON.stringify(form.value) !== initialFormSnapshot.value
})

const keyError = computed(() => {
    if (isEdit.value) return ''
    const k = form.value.resource_key.trim()
    if (!k) return '请输入资源标识'
    if (!/^[a-z][a-z0-9_.]*$/.test(k)) return '仅支持小写字母、数字、点号与下划线，且以小写字母开头'
    return ''
})

const validationIssues = computed(() => {
    const issues: { id: string; label: string }[] = []
    if (keyError.value) issues.push({ id: 'basic', label: keyError.value })
    if (!form.value.resource_name.trim()) issues.push({ id: 'basic', label: '请填写资源名称' })
    if (!form.value.data_source) issues.push({ id: 'basic', label: '请选择数据源' })
    if (!isBuiltinSystemResource.value && !form.value.resource_group.trim()) {
        issues.push({ id: 'basic', label: '请选择或输入分组' })
    }
    if (form.value.resource_mode === 'TABLE' && !form.value.table_name) {
        issues.push({ id: 'source', label: '请选择数据表' })
    }
    if (form.value.resource_mode === 'SQL' && !form.value.custom_sql.trim()) {
        issues.push({ id: 'source', label: '请填写自定义 SQL' })
    }
    if (form.value.fields_config.length === 0) {
        issues.push({ id: 'fields', label: '请至少配置 1 个返回字段' })
    }
    if (!form.value.default_sort) {
        issues.push({ id: 'sort', label: '请选择默认排序字段' })
    }
    return issues
})

const wizardSteps = computed(() => [
    {
        id: 'basic',
        label: '基础信息',
        done: !!(
            form.value.resource_key &&
            form.value.resource_name &&
            form.value.data_source &&
            (form.value.resource_group || isBuiltinSystemResource.value)
        ),
    },
    {
        id: 'source',
        label: '数据映射',
        done: form.value.resource_mode === 'TABLE'
            ? !!form.value.table_name
            : !!form.value.custom_sql.trim(),
    },
    { id: 'fields', label: '字段配置', done: form.value.fields_config.length > 0 },
    { id: 'sort', label: '排序保存', done: !!form.value.default_sort },
])

const canUseTestTab = computed(() => isEdit.value || hasSavedOnce.value)

const saveButtonLabel = computed(() => {
    if (saving.value) return '正在保存...'
    return isEdit.value ? '保存更改' : '创建资源'
})

const openConfirm = (opts: {
    title: string
    message: string
    type?: 'danger' | 'warning' | 'info'
    confirmText?: string
    onConfirm: () => void
}) => {
    confirmDialog.value = {
        show: true,
        title: opts.title,
        message: opts.message,
        type: opts.type || 'warning',
        confirmText: opts.confirmText || '确认',
        onConfirm: opts.onConfirm,
    }
}

const scrollToSection = (id: string) => {
    document.getElementById(`section-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const onGroupPickerChange = () => {
    if (groupPickerValue.value === '__new__') {
        form.value.resource_group = ''
        return
    }
    form.value.resource_group = groupPickerValue.value
}

const syncGroupPickerFromForm = () => {
    const g = (form.value.resource_group || '').trim()
    if (!g) {
        groupPickerValue.value = ''
        return
    }
    if (selectableGroups.value.includes(g)) {
        groupPickerValue.value = g
    } else {
        groupPickerValue.value = '__new__'
    }
}

const goBack = () => {
    router.back()
}

const handleLeaveConfirm = () => {
    confirmDialog.value.onConfirm()
}

const handleLeaveCancel = () => {
    confirmDialog.value.show = false
    pendingRouteNext.value = null
}

const switchToTestTab = () => {
    if (!canUseTestTab.value) {
        showToast('请先保存资源后再进行测试', 'warning')
        return
    }
    activeTab.value = 'test'
}

// Fetch Data Sources
const fetchDataSources = async () => {
  try {
    const res = await axios.get('/api/portal/datasource/datasources?status=active')
    availableDataSources.value = res.data
    if (!isEdit.value && availableDataSources.value.length > 0 && !form.value.data_source) {
      form.value.data_source = availableDataSources.value[0].source_name
    }
    // 默认数据源异步写入后刷新快照，避免未编辑也被判为 dirty
    if (!isEdit.value && initialFormSnapshot.value) {
      snapshotForm()
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
const activeTab = ref('config') // config | test | history

// Version history
const versions = ref<any[]>([])
const versionsTotal = ref(0)
const versionsLoading = ref(false)
const versionDiff = ref<any>(null)
const versionDiffLoading = ref(false)
const rollbackLoadingId = ref<number | null>(null)

const actionTypeLabel = (action: string) => {
  const map: Record<string, string> = { CREATE: '创建', UPDATE: '更新', ROLLBACK: '回滚' }
  return map[action] || action
}

const fetchVersions = async () => {
  if (!isEdit.value) return
  versionsLoading.value = true
  try {
    const res = await axios.get(`/api/portal/meta/resources/${resourceKeyParam}/versions`, {
      params: { page: 1, size: 50 },
    })
    versions.value = res.data.items || []
    versionsTotal.value = res.data.total || 0
  } catch (e: any) {
    showToast(e.response?.data?.detail || '加载版本历史失败', 'error')
  } finally {
    versionsLoading.value = false
  }
}

const loadVersionDiff = async (versionId: number) => {
  versionDiffLoading.value = true
  versionDiff.value = null
  try {
    const res = await axios.get(
      `/api/portal/meta/resources/${resourceKeyParam}/versions/${versionId}/diff`,
      { params: { compare_target: 'current' } }
    )
    versionDiff.value = res.data
  } catch (e: any) {
    showToast(e.response?.data?.detail || '加载差异失败', 'error')
  } finally {
    versionDiffLoading.value = false
  }
}

const switchToHistoryTab = () => {
  activeTab.value = 'history'
  fetchVersions()
}

const confirmRollback = (version: any) => {
  openConfirm({
    title: '回滚资源配置',
    message: `确认将资源回滚至版本 v${version.version_no}？当前配置会先被记录为新版本。`,
    type: 'warning',
    confirmText: '确认回滚',
    onConfirm: () => doRollback(version.id),
  })
}

const doRollback = async (versionId: number) => {
  rollbackLoadingId.value = versionId
  try {
    const res = await axios.post(
      `/api/portal/meta/resources/${resourceKeyParam}/versions/${versionId}/rollback`
    )
    form.value = { ...res.data }
    if (!Array.isArray(form.value.fields_config)) form.value.fields_config = []
    if (!Array.isArray(form.value.allowed_filters)) form.value.allowed_filters = []
    syncGroupPickerFromForm()
    snapshotForm()
    showToast('已回滚至选定版本', 'success')
    await fetchVersions()
    versionDiff.value = null
  } catch (e: any) {
    showToast(e.response?.data?.detail || '回滚失败', 'error')
  } finally {
    rollbackLoadingId.value = null
  }
}

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
                type: normalizeType(col.type)
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

const buildColumnsConfig = (names: string[], target: 'fields_config' | 'allowed_filters') => {
    return names.map((name) => {
        const col = availableColumns.value.find((c) => c.name === name)
        const existing = form.value[target].find((f) => f.name === name)
        if (existing) {
            return { ...existing, type: col ? normalizeType(col.type) : existing.type }
        }
        return {
            name,
            label: col?.comment || name,
            type: col ? normalizeType(col.type) : 'String',
        }
    })
}

const autoImportAllFields = (quiet = false) => {
    if (availableColumns.value.length === 0) return
    form.value.fields_config = buildColumnsConfig(
        availableColumns.value.map((c) => c.name),
        'fields_config'
    )
    if (!form.value.default_sort && form.value.fields_config.length > 0) {
        const preferred = form.value.fields_config.find((f) =>
            ['id', 'updated_at', 'created_at', 'rowkey'].includes(f.name)
        )
        form.value.default_sort = preferred?.name || form.value.fields_config[0]?.name || ''
    }
    if (!quiet) showToast(`已导入 ${form.value.fields_config.length} 个返回字段`, 'success')
}

const onTableSelected = async () => {
    if (form.value.resource_mode !== 'TABLE' || !form.value.table_name) return
    await fetchColumns(true)
    if (!isEdit.value && form.value.fields_config.length === 0 && availableColumns.value.length > 0) {
        autoImportAllFields(true)
        showToast('已自动导入全部返回字段，请确认过滤字段与默认排序', 'info')
    }
}

const copyFieldsToFilters = () => {
    if (form.value.fields_config.length === 0) {
        showToast('请先配置返回字段', 'warning')
        return
    }
    form.value.allowed_filters = form.value.fields_config.map((f) => ({ ...f }))
    fieldConfigTab.value = 'filters'
    showToast('已从返回字段复制到过滤字段', 'success')
}

const requestClearFields = () => {
    openConfirm({
        title: '清空返回字段',
        message: '确定清空所有返回字段配置吗？此操作不可撤销。',
        type: 'danger',
        confirmText: '清空',
        onConfirm: () => {
            form.value.fields_config = []
            confirmDialog.value.show = false
        },
    })
}

const requestClearFilters = () => {
    openConfirm({
        title: '清空过滤字段',
        message: '确定清空所有允许过滤字段吗？',
        type: 'danger',
        confirmText: '清空',
        onConfirm: () => {
            form.value.allowed_filters = []
            confirmDialog.value.show = false
        },
    })
}

const requestModeChange = (mode: 'TABLE' | 'SQL') => {
    if (form.value.resource_mode === mode) return
    const hasContent =
        !!form.value.table_name ||
        !!form.value.custom_sql.trim() ||
        form.value.fields_config.length > 0 ||
        form.value.allowed_filters.length > 0
    if (!hasContent) {
        form.value.resource_mode = mode
        return
    }
    openConfirm({
        title: '切换资源模式',
        message: '切换模式后，请重新确认数据表/SQL 与字段配置是否一致。',
        type: 'warning',
        onConfirm: () => {
            form.value.resource_mode = mode
            confirmDialog.value.show = false
        },
    })
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

watch(() => form.value.data_source, (val) => {
    if (val) fetchTables()
})
watch(existingGroups, () => {
    if (form.value.resource_group) syncGroupPickerFromForm()
})
watch(() => form.value.table_name, () => {
    if (form.value.resource_mode === 'TABLE') onTableSelected()
})

const validateBeforeSave = (): boolean => {
    showValidationBanner.value = true
    if (validationIssues.value.length > 0) {
        const first = validationIssues.value[0]
        if (first) {
            scrollToSection(first.id)
            showToast(
                `还有 ${validationIssues.value.length} 项未完成：${first.label}`,
                'warning'
            )
        }
        return false
    }
    if (!isBuiltinSystemResource.value && !normalizeResourceGroup()) return false
    return true
}

// Save
const save = async (redirectToTest = false) => {
    if (!validateBeforeSave()) return
    saving.value = true
    try {
        if (isEdit.value) {
            await axios.put(`/api/portal/meta/resources/${resourceKeyParam}`, form.value)
            showToast('资源更新成功', 'success')
            snapshotForm()
            showValidationBanner.value = false
            if (redirectToTest) activeTab.value = 'test'
            if (activeTab.value === 'history') fetchVersions()
        } else {
            await axios.post('/api/portal/meta/resources', form.value)
            showToast('资源创建成功', 'success')
            hasSavedOnce.value = true
            snapshotForm()
            showValidationBanner.value = false
            if (redirectToTest) {
                await router.replace(`/dashboard/resources/${form.value.resource_key}`)
                activeTab.value = 'test'
            } else {
                router.push('/dashboard/resources')
            }
        }
    } catch (e: any) {
        showToast(e.response?.data?.detail || '保存失败', 'error')
    } finally {
        saving.value = false
    }
}

const saveAndTest = () => save(true)

// API URL Helper
const apiUrl = computed(() => {
    if (!form.value.resource_key) return ''
    const host = window.location.origin
    return `${host}/api/v1/resources/${form.value.resource_key}`
})

const copyApiUrl = async () => {
    const success = await copyToClipboard(apiUrl.value)
    if (success) {
        showToast('连接已复制', 'success')
    } else {
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
    const success = await copyToClipboard(text)
    if (success) {
        showToast('已复制到剪贴板', 'success')
    } else {
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
  <div class="space-y-6 pb-24">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center space-x-4">
            <button type="button" @click="goBack" class="bg-white p-2 rounded-lg shadow-sm border border-gray-200 text-gray-500 hover:text-blue-600 hover:border-blue-300 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/></svg>
            </button>
            <div>
                <h1 class="text-2xl font-bold text-gray-900">{{ isEdit ? '编辑资源' : '新建资源' }}</h1>
                <p class="text-sm text-gray-500 mt-0.5">{{ isEdit ? '管理接口元数据与数据源映射' : '按步骤完成：基础信息 → 选表/SQL → 字段 → 排序 → 保存' }}</p>
            </div>
        </div>
        
        <div class="flex items-center flex-wrap gap-3">
            <div class="flex bg-gray-200/50 p-1 rounded-xl">
                <button 
                    type="button"
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
                    type="button"
                    :disabled="!canUseTestTab"
                    @click="switchToTestTab"
                    class="px-4 py-2 rounded-lg text-sm font-bold transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                    :class="activeTab === 'test' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500 hover:text-gray-700'"
                    :title="canUseTestTab ? '' : '请先保存资源后再测试'"
                >
                  <span class="flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
                    测试控制台
                  </span>
                </button>
                <button
                    v-if="isEdit"
                    type="button"
                    @click="switchToHistoryTab"
                    class="px-4 py-2 rounded-lg text-sm font-bold transition-all"
                    :class="activeTab === 'history' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500 hover:text-gray-700'"
                >
                  <span class="flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    变更历史
                  </span>
                </button>
            </div>
            
            <template v-if="activeTab === 'config' && hasPerm('element:resource:edit')">
                <button 
                    type="button"
                    @click="save(false)" 
                    :disabled="saving"
                    class="px-5 py-2 bg-blue-600 text-white font-bold rounded-lg hover:bg-blue-700 shadow-md shadow-blue-200 transition-all disabled:opacity-50 flex items-center gap-2"
                >
                    <span v-if="saving" class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
                    {{ saveButtonLabel }}
                </button>
                <button
                    v-if="!isEdit"
                    type="button"
                    @click="saveAndTest"
                    :disabled="saving"
                    class="px-4 py-2 border border-blue-200 text-blue-700 font-medium rounded-lg hover:bg-blue-50 transition-all disabled:opacity-50"
                >
                    保存并测试
                </button>
            </template>
        </div>
    </div>

    <!-- Wizard steps -->
    <div v-if="activeTab === 'config' && !loading" class="bg-white border border-gray-200 rounded-lg px-4 py-3 shadow-sm">
        <div class="flex flex-wrap gap-2">
            <button
                v-for="(step, idx) in wizardSteps"
                :key="step.id"
                type="button"
                class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm transition-colors"
                :class="step.done ? 'bg-green-50 text-green-700 ring-1 ring-green-200' : 'bg-gray-50 text-gray-600 ring-1 ring-gray-200 hover:bg-gray-100'"
                @click="scrollToSection(step.id)"
            >
                <span class="w-5 h-5 rounded-full text-xs font-bold flex items-center justify-center" :class="step.done ? 'bg-green-500 text-white' : 'bg-gray-300 text-white'">{{ idx + 1 }}</span>
                {{ step.label }}
            </button>
        </div>
    </div>

    <!-- Validation banner -->
    <div
        v-if="showValidationBanner && validationIssues.length > 0 && activeTab === 'config'"
        class="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800"
    >
        <p class="font-medium mb-1">还有 {{ validationIssues.length }} 项需要完成：</p>
        <ul class="list-disc pl-5 space-y-0.5">
            <li v-for="issue in validationIssues" :key="issue.label">
                <button type="button" class="underline hover:text-amber-900" @click="scrollToSection(issue.id)">{{ issue.label }}</button>
            </li>
        </ul>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="bg-white rounded-lg border border-gray-200 p-6 space-y-4 animate-pulse">
        <div class="h-6 bg-gray-200 rounded w-1/3"></div>
        <div class="grid grid-cols-2 gap-4">
            <div class="h-10 bg-gray-100 rounded"></div>
            <div class="h-10 bg-gray-100 rounded"></div>
        </div>
        <div class="h-32 bg-gray-100 rounded"></div>
    </div>

    <!-- Config Form -->
    <div v-show="activeTab === 'config' && !loading" class="bg-white shadow rounded-lg p-6 space-y-6">
        <!-- Basic Info -->
        <div id="section-basic" class="scroll-mt-24">
        <h2 class="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">1. 基础信息</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 flex items-center">
                    资源标识 (Key)
                    <span class="custom-tooltip" data-tooltip="英文唯一标识，用于 API 路径。示例：ccg.containers">
                        <svg class="w-4 h-4 ml-1 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </span>
                </label>
                <input
                  v-model="form.resource_key"
                  :disabled="isEdit || !hasPerm('element:resource:edit')"
                  type="text"
                  placeholder="例如：ccg.containers"
                  class="mt-1 block w-full border rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm font-mono disabled:bg-gray-50"
                  :class="showValidationBanner && keyError ? 'border-red-300' : 'border-gray-300'"
                />
                <p v-if="showValidationBanner && keyError" class="mt-1 text-xs text-red-600">{{ keyError }}</p>
                <p v-else class="mt-1 text-xs text-gray-500">小写字母开头，可含数字、点号与下划线。</p>
                <div v-if="apiUrl" class="mt-2 bg-gray-50 p-2 rounded border border-gray-200">
                    <p class="text-[10px] text-gray-400 uppercase mb-1">API 地址预览</p>
                    <div class="flex gap-1">
                        <code class="text-xs text-gray-600 truncate flex-1">{{ apiUrl }}</code>
                        <button type="button" class="text-xs text-blue-600 shrink-0" @click="copyApiUrl">复制</button>
                    </div>
                </div>
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
                    <span class="custom-tooltip" data-tooltip="用于资源列表侧栏分组，请从已有分组中选择">
                        <svg class="w-4 h-4 ml-1 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </span>
                </label>
                <div class="mt-1 space-y-2">
                  <select
                    v-model="groupPickerValue"
                    :disabled="!hasPerm('element:resource:edit') || isBuiltinSystemResource"
                    class="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm disabled:bg-gray-50"
                    @change="onGroupPickerChange"
                  >
                    <option value="">选择分组...</option>
                    <option v-for="g in selectableGroups" :key="g" :value="g">{{ g }}</option>
                    <option value="__new__">+ 新建分组...</option>
                  </select>
                  <input
                    v-if="groupPickerValue === '__new__'"
                    v-model="form.resource_group"
                    :disabled="!hasPerm('element:resource:edit')"
                    type="text"
                    placeholder="输入新分组名"
                    class="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm"
                    @blur="normalizeResourceGroup()"
                  />
                </div>
                <p class="mt-1 text-xs text-gray-400">
                  「{{ SYSTEM_RESOURCE_GROUP }}」为系统内置分组，不可选用。
                </p>
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
        </div>

        <!-- Advanced settings -->
        <div class="border border-gray-200 rounded-lg overflow-hidden">
            <button
                type="button"
                class="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 text-sm font-medium text-gray-700"
                @click="showAdvanced = !showAdvanced"
            >
                <span>高级设置（状态 / 缓存）</span>
                <svg class="w-4 h-4 transition-transform" :class="showAdvanced ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
            </button>
            <div v-show="showAdvanced" class="p-4 grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-gray-200">
             <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">资源状态</label>
                <div class="flex items-center space-x-6">
                    <div class="flex items-center">
                        <button 
                            type="button"
                            :disabled="!hasPerm('element:resource:edit') || (form.status === 1 && catalogPublished)"
                            :title="form.status === 1 && catalogPublished ? '已上架到目录，请先从目录下架后再禁用' : undefined"
                            @click="toggleResourceStatus"
                            :class="[
                              'relative inline-flex h-6 w-11 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none',
                              form.status === 1 ? 'bg-green-500' : 'bg-gray-200',
                              (!hasPerm('element:resource:edit') || (form.status === 1 && catalogPublished))
                                ? 'opacity-50 cursor-not-allowed'
                                : 'cursor-pointer',
                            ]"
                        >
                            <span 
                            :class="form.status === 1 ? 'translate-x-5' : 'translate-x-0'"
                            class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
                            ></span>
                        </button>
                        <span class="ml-3 text-sm text-gray-900">{{ form.status === 1 ? '启用' : '禁用' }}</span>
                    </div>
                    <div class="flex items-center space-x-2 border-l border-gray-200 pl-6">
                        <label class="block text-sm font-medium text-gray-700 whitespace-nowrap">缓存 (秒)</label>
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
        </div>

        <hr class="border-gray-200" />

        <!-- Mode & Source -->
        <div id="section-source" class="scroll-mt-24">
        <h2 class="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">2. 数据映射</h2>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-2 flex items-center">
                资源模式
                <span class="custom-tooltip" data-tooltip="TABLE：直接查物理表；SQL：自定义 SQL 子查询">
                    <svg class="w-4 h-4 ml-1 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </span>
            </label>
            <div class="flex items-center space-x-4">
                <label class="inline-flex items-center cursor-pointer">
                    <input type="radio" :checked="form.resource_mode === 'TABLE'" :disabled="!hasPerm('element:resource:edit')" class="form-radio text-primary disabled:opacity-50" @change="requestModeChange('TABLE')" />
                    <span class="ml-2" :class="!hasPerm('element:resource:edit') ? 'text-gray-400' : ''">直接表 (TABLE)</span>
                </label>
                <label class="inline-flex items-center cursor-pointer">
                    <input type="radio" :checked="form.resource_mode === 'SQL'" :disabled="!hasPerm('element:resource:edit')" class="form-radio text-primary disabled:opacity-50" @change="requestModeChange('SQL')" />
                    <span class="ml-2" :class="!hasPerm('element:resource:edit') ? 'text-gray-400' : ''">自定义 SQL (SQL)</span>
                </label>
            </div>
        </div>

        <div v-if="form.resource_mode === 'TABLE'">
            <label class="block text-sm font-medium text-gray-700">表名</label>
            <div class="mt-1 flex gap-2 items-stretch">
                <TablePicker
                  v-model="form.table_name"
                  :tables="availableTables"
                  :disabled="!hasPerm('element:resource:edit')"
                  placeholder="选择表..."
                />
                <button
                  v-if="hasPerm('element:resource:edit')"
                  type="button"
                  class="shrink-0 whitespace-nowrap px-3 flex items-center border border-gray-300 rounded-md bg-gray-50 hover:bg-gray-100 text-gray-600 text-sm"
                  @click="fetchTables"
                >
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
            <div class="mt-2 flex flex-wrap justify-between items-start gap-2">
               <div class="bg-yellow-50 border-l-4 border-yellow-400 p-2 text-xs text-yellow-700 max-w-lg">
                   警告：不要包含分号 (; )。SQL 将作为子查询执行。
               </div>
               <div class="flex flex-wrap gap-2 shrink-0">
               <button v-if="hasPerm('element:resource:edit')" type="button" @click="() => fetchColumns(false)" :disabled="analyzing" class="px-4 py-2 bg-indigo-100 text-indigo-700 rounded-md hover:bg-indigo-200 text-sm font-medium">
                   {{ analyzing ? '解析中...' : '解析 SQL 获取字段' }}
               </button>
               <router-link to="/dashboard/lab" class="px-4 py-2 text-sm text-blue-600 hover:bg-blue-50 rounded-md border border-blue-100 inline-flex items-center">
                   在 SQL 实验室调试
               </router-link>
               </div>
            </div>
            
            <!-- Template Help Moved -->
        </div>
        </div>

        <hr class="border-gray-200" />

        <!-- Fields Config -->
        <div id="section-fields" class="scroll-mt-24 space-y-4">
            <div class="flex flex-wrap justify-between items-center gap-3">
                <h2 class="text-sm font-bold text-gray-500 uppercase tracking-wider">3. 字段与过滤</h2>
                <div v-if="hasPerm('element:resource:edit')" class="flex flex-wrap gap-2">
                    <button
                        v-if="form.resource_mode === 'TABLE' && availableColumns.length > 0"
                        type="button"
                        class="px-3 py-1 bg-green-50 text-green-700 text-sm font-medium rounded hover:bg-green-100"
                        @click="autoImportAllFields(false)"
                    >
                        一键导入全部字段
                    </button>
                </div>
            </div>

            <div class="flex border-b border-gray-200">
                <button
                    type="button"
                    class="px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors"
                    :class="fieldConfigTab === 'fields' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                    @click="fieldConfigTab = 'fields'"
                >
                    返回字段 ({{ form.fields_config.length }})
                </button>
                <button
                    type="button"
                    class="px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors"
                    :class="fieldConfigTab === 'filters' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                    @click="fieldConfigTab = 'filters'"
                >
                    允许过滤 ({{ form.allowed_filters.length }})
                </button>
            </div>

            <!-- Fields tab -->
            <div v-show="fieldConfigTab === 'fields'" class="space-y-3">
                <div v-if="hasPerm('element:resource:edit')" class="flex flex-wrap gap-2">
                    <button type="button" @click="openImportDialog('fields_config')" class="px-3 py-1 bg-indigo-50 text-indigo-700 text-sm font-medium rounded hover:bg-indigo-100">
                        从数据库选择导入
                    </button>
                    <button type="button" @click="requestClearFields" class="px-3 py-1 bg-red-50 text-red-700 text-sm font-medium rounded hover:bg-red-100">
                        清空
                    </button>
                </div>
                <div class="border border-gray-200 rounded-lg overflow-hidden">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">字段名</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">中文名称</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">类型</th>
                                <th v-if="hasPerm('element:resource:edit')" class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            <tr v-for="(field, index) in form.fields_config" :key="field.name">
                                <td class="px-4 py-2 text-sm font-mono text-gray-900">{{ field.name }}</td>
                                <td class="px-4 py-2">
                                    <input v-model="field.label" :disabled="!hasPerm('element:resource:edit')" type="text" class="w-full border border-gray-300 rounded px-2 py-1 text-sm" />
                                </td>
                                <td class="px-4 py-2">
                                    <select v-model="field.type" :disabled="!hasPerm('element:resource:edit')" class="w-full border border-gray-300 rounded px-2 py-1 text-sm font-mono text-xs">
                                        <option value="String">String</option>
                                        <option value="Long">Long</option>
                                        <option value="Date">Date</option>
                                    </select>
                                </td>
                                <td v-if="hasPerm('element:resource:edit')" class="px-4 py-2 text-right">
                                    <button type="button" @click="removeField('fields_config', index)" class="text-red-600 hover:text-red-900">
                                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                    </button>
                                </td>
                            </tr>
                            <tr v-if="form.fields_config.length === 0">
                                <td :colspan="hasPerm('element:resource:edit') ? 4 : 3" class="px-4 py-8 text-center text-sm text-gray-500">选表后将自动导入，或点击「从数据库选择导入」</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Filters tab -->
            <div v-show="fieldConfigTab === 'filters'" class="space-y-3">
                <div v-if="hasPerm('element:resource:edit')" class="flex flex-wrap gap-2">
                    <button type="button" @click="openImportDialog('allowed_filters')" class="px-3 py-1 bg-indigo-50 text-indigo-700 text-sm font-medium rounded hover:bg-indigo-100">
                        从数据库选择导入
                    </button>
                    <button type="button" @click="copyFieldsToFilters" class="px-3 py-1 bg-blue-50 text-blue-700 text-sm font-medium rounded hover:bg-blue-100">
                        从返回字段复制
                    </button>
                    <button type="button" @click="requestClearFilters" class="px-3 py-1 bg-red-50 text-red-700 text-sm font-medium rounded hover:bg-red-100">
                        清空
                    </button>
                </div>
                <div class="border border-gray-200 rounded-lg overflow-hidden">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">字段名</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">中文名称</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">类型</th>
                                <th v-if="hasPerm('element:resource:edit')" class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            <tr v-for="(field, index) in form.allowed_filters" :key="field.name">
                                <td class="px-4 py-2 text-sm font-mono text-gray-900">{{ field.name }}</td>
                                <td class="px-4 py-2">
                                    <input v-model="field.label" :disabled="!hasPerm('element:resource:edit')" type="text" class="w-full border border-gray-300 rounded px-2 py-1 text-sm" />
                                </td>
                                <td class="px-4 py-2">
                                    <select v-model="field.type" :disabled="!hasPerm('element:resource:edit')" class="w-full border border-gray-300 rounded px-2 py-1 text-sm font-mono text-xs">
                                        <option value="String">String</option>
                                        <option value="Long">Long</option>
                                        <option value="Date">Date</option>
                                    </select>
                                </td>
                                <td v-if="hasPerm('element:resource:edit')" class="px-4 py-2 text-right">
                                    <button type="button" @click="removeField('allowed_filters', index)" class="text-red-600 hover:text-red-900">
                                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                    </button>
                                </td>
                            </tr>
                            <tr v-if="form.allowed_filters.length === 0">
                                <td :colspan="hasPerm('element:resource:edit') ? 4 : 3" class="px-4 py-8 text-center text-sm text-gray-500">可从返回字段复制，或从数据库选择导入</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <hr class="border-gray-200" />

        <div id="section-sort" class="scroll-mt-24">
        <h2 class="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">4. 默认排序</h2>
        <div>
            <label class="block text-sm font-medium text-gray-700">默认排序字段 <span class="text-red-500">*</span></label>
            <p class="text-xs text-gray-400 mb-1">分页查询必须指定排序字段，以保证结果稳定。</p>
            <div class="mt-1 max-w-md" :class="showValidationBanner && !form.default_sort ? 'ring-1 ring-red-300 rounded-md' : ''">
                <ColumnPicker
                  v-model="form.default_sort"
                  :columns="form.fields_config.length ? form.fields_config.map(f => ({ name: f.name, type: f.type, comment: f.label })) : availableColumns"
                  :disabled="!hasPerm('element:resource:edit')"
                  empty-label="请选择..."
                />
            </div>
        </div>
        </div>
    </div>

    <!-- Version History -->
    <div v-show="activeTab === 'history'" class="bg-white shadow rounded-lg p-6 space-y-4">
        <div class="flex items-center justify-between gap-3">
            <div>
                <h3 class="text-lg font-semibold text-gray-900">变更历史</h3>
                <p class="text-sm text-gray-500 mt-1">每次保存或回滚都会记录完整配置快照，最多保留 100 个版本。</p>
            </div>
            <button
                type="button"
                @click="fetchVersions"
                :disabled="versionsLoading"
                class="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
                刷新
            </button>
        </div>

        <div v-if="versionsLoading" class="py-12 text-center text-gray-500 text-sm">加载中...</div>
        <div v-else-if="versions.length === 0" class="py-12 text-center text-gray-500 text-sm border border-dashed border-gray-200 rounded-lg">
            暂无版本记录，保存一次配置后将自动开始记录。
        </div>
        <div v-else class="space-y-3">
            <div
                v-for="ver in versions"
                :key="ver.id"
                class="border border-gray-100 rounded-xl p-4 hover:border-blue-100 transition-colors"
            >
                <div class="flex flex-wrap items-start justify-between gap-3">
                    <div>
                        <div class="flex items-center gap-2 flex-wrap">
                            <span class="font-semibold text-gray-900">v{{ ver.version_no }}</span>
                            <span
                                class="text-xs px-2 py-0.5 rounded-full"
                                :class="ver.action_type === 'ROLLBACK' ? 'bg-amber-100 text-amber-700' : ver.action_type === 'CREATE' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'"
                            >
                                {{ actionTypeLabel(ver.action_type) }}
                            </span>
                        </div>
                        <p class="text-sm text-gray-600 mt-1">
                            {{ ver.operator_name || '系统' }}
                            <span class="text-gray-400 mx-2">·</span>
                            {{ ver.created_at }}
                        </p>
                        <p v-if="ver.change_summary" class="text-xs text-gray-500 mt-1">
                            变更：{{ ver.change_summary }}
                        </p>
                    </div>
                    <div class="flex flex-wrap gap-2">
                        <button
                            type="button"
                            @click="loadVersionDiff(ver.id)"
                            :disabled="versionDiffLoading"
                            class="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                        >
                            对比当前
                        </button>
                        <button
                            v-if="hasPerm('element:resource:edit')"
                            type="button"
                            @click="confirmRollback(ver)"
                            :disabled="rollbackLoadingId === ver.id"
                            class="px-3 py-1.5 text-sm bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
                        >
                            {{ rollbackLoadingId === ver.id ? '回滚中...' : '回滚到此版本' }}
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <ResourceVersionDiff
            v-if="versionDiff"
            :version-no="versionDiff.version_no"
            :items="versionDiff.items || []"
            @close="versionDiff = null"
        />
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
            <p v-if="!canUseTestTab" class="text-xs text-amber-700 mt-1">新建资源请先保存，或使用顶部「保存并测试」。</p>
            <p v-else class="text-xs text-blue-600 mt-1">测试读取已保存的配置；修改后请先保存再测试。</p>
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

    <!-- Sticky save bar -->
    <div
      v-if="activeTab === 'config' && !loading && hasPerm('element:resource:edit')"
      class="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur border-t border-gray-200 px-4 md:px-8 py-3 flex flex-wrap items-center justify-between gap-3 shadow-[0_-4px_20px_rgba(0,0,0,0.06)]"
    >
      <div class="text-sm">
        <span v-if="isDirty" class="text-amber-600 font-medium">有未保存的更改</span>
        <span v-else-if="validationIssues.length === 0" class="text-green-600">配置项已完成，可以保存</span>
        <span v-else class="text-gray-500">还差 {{ validationIssues.length }} 项未完成</span>
      </div>
      <div class="flex gap-2">
        <button type="button" class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg" @click="goBack">取消</button>
        <button
          type="button"
          :disabled="saving"
          class="px-5 py-2 bg-blue-600 text-white text-sm font-bold rounded-lg hover:bg-blue-700 disabled:opacity-50"
          @click="save(false)"
        >
          {{ saveButtonLabel }}
        </button>
        <button
          v-if="!isEdit"
          type="button"
          :disabled="saving"
          class="px-4 py-2 border border-blue-200 text-blue-700 text-sm font-medium rounded-lg hover:bg-blue-50 disabled:opacity-50"
          @click="saveAndTest"
        >
          保存并测试
        </button>
      </div>
    </div>

    <ConfirmDialog
      :show="confirmDialog.show"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :type="confirmDialog.type"
      :confirm-text="confirmDialog.confirmText"
      @confirm="handleLeaveConfirm"
      @cancel="handleLeaveCancel"
    />
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
