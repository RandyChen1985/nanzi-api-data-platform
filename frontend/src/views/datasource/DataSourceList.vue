<script setup lang="ts">
import { ref, computed, onMounted, reactive, onUnmounted } from 'vue'
import draggable from 'vuedraggable'
import axios from '@/utils/axios'
import Toast from '@/components/Toast.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import Switch from '@/components/Switch.vue'
import ClearableInput from '@/components/common/ClearableInput.vue'
import LabTableExplorer from '@/components/sqllab/LabTableExplorer.vue'
import {
  PencilSquareIcon,
  TrashIcon,
  PlayIcon,
  CircleStackIcon,
  Bars3Icon,
  PlusIcon,
  ArrowPathIcon,
  DocumentDuplicateIcon,
  ShieldCheckIcon,
} from '@heroicons/vue/24/outline'
import type { DataSource } from '@/types/datasource'
import { copyToClipboard } from '@/utils/clipboard'
import {
  DATA_SOURCE_TYPE_LABELS,
  dataSourceTypeClass,
  defaultPortForType,
} from '@/types/datasource'

const loading = ref(false)
const datasources = ref<DataSource[]>([])
const searchQuery = ref('')
const typeFilter = ref<'ALL' | 'clickhouse' | 'mysql' | 'oracle' | 'sqlserver'>('ALL')
const statusFilter = ref<'ALL' | '1' | '0'>('ALL')

const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showTestDialog = ref(false)
const testingItem = ref<DataSource | null>(null)

type SqlServerExtraParams = {
  compat_mode: 'modern' | 'sqlserver_2014'
  encrypt: boolean
  trust_server_certificate: boolean
  odbc_driver: string
}

type DataSourceForm = {
  source_name: string
  source_type: string
  host: string
  port: number
  database_name: string
  username: string
  password: string
  extra_params: SqlServerExtraParams
  description: string
  status: number
}

const DEFAULT_SQLSERVER_EXTRA_PARAMS: SqlServerExtraParams = {
  compat_mode: 'modern',
  encrypt: false,
  trust_server_certificate: true,
  odbc_driver: 'ODBC Driver 18 for SQL Server',
}

const SQLSERVER_DRIVER_17 = 'ODBC Driver 17 for SQL Server'
const SQLSERVER_DRIVER_18 = 'ODBC Driver 18 for SQL Server'

const booleanParam = (value: unknown, fallback: boolean): boolean => {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    if (value.toLowerCase() === 'true') return true
    if (value.toLowerCase() === 'false') return false
  }
  return fallback
}

const normalizeSqlServerExtraParams = (value?: Record<string, unknown> | null): SqlServerExtraParams => ({
  compat_mode:
    value?.compat_mode === 'sqlserver_2014' ||
    (typeof value?.odbc_driver === 'string' && value.odbc_driver.includes('ODBC Driver 17'))
      ? 'sqlserver_2014'
      : 'modern',
  encrypt: booleanParam(value?.encrypt, DEFAULT_SQLSERVER_EXTRA_PARAMS.encrypt),
  trust_server_certificate: booleanParam(
    value?.trust_server_certificate,
    DEFAULT_SQLSERVER_EXTRA_PARAMS.trust_server_certificate,
  ),
  odbc_driver:
    typeof value?.odbc_driver === 'string' && value.odbc_driver.trim()
      ? value.odbc_driver.trim()
      : DEFAULT_SQLSERVER_EXTRA_PARAMS.odbc_driver,
})

const formData = ref<DataSourceForm>({
  source_name: '',
  source_type: 'clickhouse',
  host: '',
  port: 9000,
  database_name: '',
  username: '',
  password: '',
  extra_params: { ...DEFAULT_SQLSERVER_EXTRA_PARAMS },
  description: '',
  status: 1,
})
const editingId = ref<number | null>(null)
const copyFromName = ref('')
const submitting = ref(false)
const formError = ref('')

const testingConnection = ref(false)
const testResult = ref<{ success: boolean; message: string } | null>(null)
const reordering = ref(false)

const isAdmin = ref(false)
const userInfo = ref<Record<string, unknown> | null>(null)

const confirmDialog = ref({
  show: false,
  title: '',
  message: '',
  type: 'warning' as 'danger' | 'warning' | 'info',
  confirmText: '确认',
  onConfirm: () => {},
})

const openMore = ref<number | null>(null)
const moreMenuPos = ref<{ top: number; left: number; minWidth: number; openUp: boolean } | null>(null)
const MORE_MENU_WIDTH = 144
const MORE_MENU_EST_HEIGHT = 240

const openMoreItem = computed(() => {
  if (openMore.value === null) return null
  return datasources.value.find((ds) => ds.id === openMore.value) ?? null
})

const toggleMore = (id: number, e: MouseEvent) => {
  e.stopPropagation()
  if (openMore.value === id) {
    openMore.value = null
    moreMenuPos.value = null
    return
  }
  const btn = e.currentTarget as HTMLElement
  const rect = btn.getBoundingClientRect()
  const spaceBelow = window.innerHeight - rect.bottom
  const openUp = spaceBelow < MORE_MENU_EST_HEIGHT && rect.top > MORE_MENU_EST_HEIGHT
  moreMenuPos.value = {
    top: openUp ? rect.top - 4 : rect.bottom + 4,
    left: rect.right,
    minWidth: Math.max(rect.width, MORE_MENU_WIDTH),
    openUp,
  }
  openMore.value = id
}

const toast = ref({ show: false, message: '', type: 'info' as 'success' | 'error' | 'warning' | 'info', key: 0 })
const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
  toast.value = { show: true, message, type, key: toast.value.key + 1 }
}
const closeToast = () => { toast.value.show = false }

const checkRole = () => {
  try {
    const s = localStorage.getItem('user_info')
    if (s) {
      userInfo.value = JSON.parse(s)
      isAdmin.value = userInfo.value?.role === 'admin'
    }
  } catch { /* ignore */ }
}

const hasPerm = (code: string) => {
  if (isAdmin.value) return true
  const perms = userInfo.value?.permissions as { elements?: string[] } | undefined
  return perms?.elements?.includes(code) ?? false
}

const canEdit = computed(() => hasPerm('element:datasource:edit'))

const stats = computed(() => {
  const total = datasources.value.length
  const active = datasources.value.filter((d) => d.status === 1).length
  return { total, active, inactive: total - active }
})

const hasActiveFilters = computed(
  () => !!searchQuery.value.trim() || typeFilter.value !== 'ALL' || statusFilter.value !== 'ALL'
)

const filteredDatasources = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return datasources.value.filter((d) => {
    const matchesSearch =
      !q ||
      d.source_name.toLowerCase().includes(q) ||
      (d.description || '').toLowerCase().includes(q) ||
      d.host.toLowerCase().includes(q) ||
      (d.database_name || '').toLowerCase().includes(q)
    const matchesType = typeFilter.value === 'ALL' || d.source_type === typeFilter.value
    const matchesStatus = statusFilter.value === 'ALL' || String(d.status) === statusFilter.value
    return matchesSearch && matchesType && matchesStatus
  })
})

const formatDate = (value?: string) => {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return value
  }
}

const fetchDatasources = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/portal/datasource/datasources')
    datasources.value = res.data
    await loadTaskStatuses()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '获取数据源列表失败', 'error')
  } finally {
    loading.value = false
  }
}

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

const resetForm = () => {
  formData.value = {
    source_name: '',
    source_type: 'clickhouse',
    host: '',
    port: 9000,
    database_name: '',
    username: '',
    password: '',
    extra_params: { ...DEFAULT_SQLSERVER_EXTRA_PARAMS },
    description: '',
    status: 1,
  }
  formError.value = ''
  editingId.value = null
  copyFromName.value = ''
}

const generateCopyName = (baseName: string): string => {
  const existing = new Set(datasources.value.map((d) => d.source_name))
  let candidate = `${baseName}_copy`
  let n = 2
  while (existing.has(candidate)) {
    candidate = `${baseName}_copy${n}`
    n++
  }
  return candidate
}

const openCreateDialog = () => {
  resetForm()
  showCreateDialog.value = true
}

const openCopyDialog = (item: DataSource) => {
  resetForm()
  copyFromName.value = item.source_name
  formData.value = {
    source_name: generateCopyName(item.source_name),
    source_type: item.source_type,
    host: item.host,
    port: item.port,
    database_name: item.database_name || '',
    username: item.username || '',
    password: '',
    extra_params: normalizeSqlServerExtraParams(item.extra_params),
    description: item.description
      ? `${item.description}（复制自 ${item.source_name}）`
      : `复制自 ${item.source_name}`,
    status: 1,
  }
  showCreateDialog.value = true
}

const openEditDialog = (item: DataSource) => {
  formData.value = {
    source_name: item.source_name,
    source_type: item.source_type,
    host: item.host,
    port: item.port,
    database_name: item.database_name || '',
    username: item.username || '',
    password: '',
    extra_params: normalizeSqlServerExtraParams(item.extra_params),
    description: item.description || '',
    status: item.status,
  }
  formError.value = ''
  editingId.value = item.id
  showEditDialog.value = true
}

const closeDialogs = () => {
  showCreateDialog.value = false
  showEditDialog.value = false
  showTestDialog.value = false
  testResult.value = null
  testingItem.value = null
  formError.value = ''
}

const closeTestDialog = () => {
  showTestDialog.value = false
  testResult.value = null
  testingItem.value = null
}

const updatePort = () => {
  formData.value.port = defaultPortForType(formData.value.source_type)
  if (formData.value.source_type === 'sqlserver') {
    formData.value.extra_params = normalizeSqlServerExtraParams(formData.value.extra_params)
  }
}

const useSqlServerDriver = (driver: string) => {
  formData.value.extra_params.odbc_driver = driver
  formData.value.extra_params.compat_mode = driver === SQLSERVER_DRIVER_17 ? 'sqlserver_2014' : 'modern'
}

const applySqlServerCompatMode = () => {
  if (formData.value.extra_params.compat_mode === 'sqlserver_2014') {
    formData.value.extra_params.odbc_driver = SQLSERVER_DRIVER_17
    formData.value.extra_params.encrypt = false
    formData.value.extra_params.trust_server_certificate = true
  } else {
    formData.value.extra_params.odbc_driver = SQLSERVER_DRIVER_18
    formData.value.extra_params.encrypt = false
    formData.value.extra_params.trust_server_certificate = true
  }
}

const saveDataSource = async () => {
  if (!formData.value.source_name.trim()) {
    formError.value = '请输入数据源名称'
    return
  }
  if (!formData.value.host.trim()) {
    formError.value = '请输入主机地址'
    return
  }
  if (!formData.value.port) {
    formError.value = '请输入端口号'
    return
  }
  if (!editingId.value && copyFromName.value && !formData.value.password.trim()) {
    formError.value = '复制新建请重新填写密码（原密码无法复制）'
    return
  }

  submitting.value = true
  formError.value = ''

  try {
    const payload = buildFormPayload()

    if (editingId.value) {
      await axios.put(`/api/portal/datasource/datasources/${editingId.value}`, payload)
      showToast('数据源更新成功', 'success')
    } else {
      await axios.post('/api/portal/datasource/datasources', payload)
      showToast('数据源创建成功', 'success')
    }
    closeDialogs()
    fetchDatasources()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    formError.value = err.response?.data?.detail || '保存失败'
  } finally {
    submitting.value = false
  }
}

const buildFormPayload = () => {
  const payload: Record<string, unknown> = { ...formData.value }
  if (editingId.value && !payload.password) delete payload.password
  if (payload.source_type === 'sqlserver') {
    payload.extra_params = normalizeSqlServerExtraParams(formData.value.extra_params)
  } else {
    delete payload.extra_params
  }
  return payload
}

const applyStatusChange = async (item: DataSource, newStatus: number) => {
  const original = item.status
  item.status = newStatus
  try {
    await axios.put(`/api/portal/datasource/datasources/${item.id}`, { ...item, status: newStatus })
    showToast(newStatus === 1 ? '数据源已启用' : '数据源已停用', 'success')
  } catch {
    item.status = original
    showToast('状态更新失败', 'error')
  }
}

const toggleStatus = (item: DataSource) => {
  if (!canEdit.value) return
  const newStatus = item.status === 1 ? 0 : 1
  if (newStatus === 0) {
    openConfirm({
      title: '停用数据源',
      message: `停用后，依赖「${item.source_name}」的资源接口与 SQL 实验室将无法连接。确定停用吗？`,
      type: 'warning',
      confirmText: '停用',
      onConfirm: () => {
        confirmDialog.value.show = false
        applyStatusChange(item, 0)
      },
    })
    return
  }
  applyStatusChange(item, 1)
}

const confirmDelete = (item: DataSource) => {
  openConfirm({
    title: '删除数据源',
    message: `确定删除「${item.source_name}」吗？若仍有资源或权限引用该数据源，删除可能失败。`,
    type: 'danger',
    confirmText: '删除',
    onConfirm: () => {
      confirmDialog.value.show = false
      deleteDataSource(item)
    },
  })
}

const deleteDataSource = async (item: DataSource) => {
  try {
    await axios.delete(`/api/portal/datasource/datasources/${item.id}`)
    showToast('删除成功', 'success')
    fetchDatasources()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string; message?: string } } }
    showToast(err.response?.data?.detail || err.response?.data?.message || '删除失败', 'error')
  }
}

const testConnection = async (item: DataSource) => {
  testingItem.value = item
  testingConnection.value = true
  testResult.value = null
  showTestDialog.value = true

  try {
    const res = await axios.post(`/api/portal/datasource/datasources/${item.id}/test`)
    testResult.value = {
      success: res.data.status === 'success',
      message: res.data.message,
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    testResult.value = {
      success: false,
      message: err.response?.data?.detail || err.message || '请求失败',
    }
  } finally {
    testingConnection.value = false
  }
}

const testEditingConnection = async () => {
  if (!editingId.value || testingConnection.value) return
  if (!formData.value.source_name.trim()) {
    formError.value = '请输入数据源名称'
    return
  }
  if (!formData.value.host.trim()) {
    formError.value = '请输入主机地址'
    return
  }
  if (!formData.value.port) {
    formError.value = '请输入端口号'
    return
  }

  testingItem.value = {
    id: editingId.value,
    source_name: formData.value.source_name,
    source_type: formData.value.source_type,
    host: formData.value.host,
    port: formData.value.port,
    database_name: formData.value.database_name,
    username: formData.value.username,
    extra_params: formData.value.extra_params,
    description: formData.value.description,
    status: formData.value.status,
  }
  testingConnection.value = true
  testResult.value = null
  showTestDialog.value = true
  formError.value = ''

  try {
    const payload = {
      ...buildFormPayload(),
      source_id: editingId.value,
    }
    const res = await axios.post('/api/portal/datasource/datasources/test-connection', payload)
    testResult.value = {
      success: res.data.status === 'success',
      message: res.data.message,
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    testResult.value = {
      success: false,
      message: err.response?.data?.detail || err.message || '请求失败',
    }
  } finally {
    testingConnection.value = false
  }
}

const saveReorder = async () => {
  if (!canEdit.value) return
  reordering.value = true
  try {
    const ids = datasources.value.map((ds) => ds.id)
    await axios.put('/api/portal/datasource/reorder', { ids })
    showToast('排序已保存', 'success')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    showToast(err.response?.data?.detail || '排序保存失败', 'error')
    fetchDatasources()
  } finally {
    reordering.value = false
  }
}

const copyConnectionHint = async (item: DataSource) => {
  const text = `${item.source_type}://${item.username || 'user'}@${item.host}:${item.port}/${item.database_name || 'default'}`
  const success = await copyToClipboard(text)
  if (success) {
    showToast('连接信息已复制', 'success')
  } else {
    showToast('复制失败', 'error')
  }
}

// 智能摸排任务状态管理
type ProfileTaskStatus = {
  status: number
  total_tables: number
  processed_tables: number
  completed_profiles?: number
  last_profiled_at?: string | null
  updated_at?: string | null
  current_table?: string
  error_message?: string
}

const profilingTasks = ref<Record<number, ProfileTaskStatus>>({})

const profileModalTask = ref<ProfileTaskStatus | null>(null)

const formatProfileTaskTime = (task?: { last_profiled_at?: string | null; updated_at?: string | null } | null) => {
  const value = task?.last_profiled_at || task?.updated_at
  return value ? formatDate(value) : '暂无记录'
}

const profileModalTimeLabel = computed(() => {
  const task = profileModalTask.value
  if (!task) return ''
  const time = formatProfileTaskTime(task)
  if (task.status === 1) {
    return `摸排进行中 · 最近更新 ${time} · 已完成 ${task.completed_profiles || 0}/${task.total_tables || '?'} 张`
  }
  return `上次摸排 ${time} · 已完成 ${task.completed_profiles || 0} 张画像`
})

const hasViewableProfiles = (item: DataSource) => {
  return (profilingTasks.value[item.id]?.completed_profiles || 0) > 0
}
const pollingIntervals = reactive<Record<number, any>>({})

const isProfilingCancelled = (task?: { status?: number; error_message?: string }) => {
  return task?.status === 3 && (task?.error_message || '').startsWith('用户主动取消')
}

const profilingProgressPercent = (task?: { processed_tables?: number; total_tables?: number }) => {
  const total = task?.total_tables || 1
  const done = task?.processed_tables || 0
  return Math.min(100, Math.round((done / total) * 100))
}

const profilingStatusLabel = (task?: { status?: number; error_message?: string }) => {
  if (!task) return ''
  if (task.status === 2) return '摸排完成'
  if (isProfilingCancelled(task)) return '已取消'
  if (task.status === 3) return '摸排异常'
  return ''
}

const profilingFinishedToast = (task: { status: number; error_message?: string }) => {
  if (task.status === 2) return { message: '数据源摸排完成！', type: 'success' as const }
  if (isProfilingCancelled(task)) return { message: '摸排已取消，已完成表保留', type: 'warning' as const }
  return { message: '摸排异常结束', type: 'error' as const }
}

const loadTaskStatuses = async () => {
  for (const item of datasources.value) {
    try {
      const res = await axios.get(`/api/portal/datasource/datasources/${item.id}/profile-task`)
      if (res.data) {
        profilingTasks.value[item.id] = res.data
        if (res.data.status === 1) {
          startPolling(item.id)
        }
      }
    } catch {
      // 忽略
    }
  }
}

const startPolling = (configId: number) => {
  if (pollingIntervals[configId]) return
  pollingIntervals[configId] = setInterval(async () => {
    try {
      const res = await axios.get(`/api/portal/datasource/datasources/${configId}/profile-task`)
      if (res.data) {
        profilingTasks.value[configId] = res.data
        if (res.data.status !== 1) {
          clearInterval(pollingIntervals[configId])
          delete pollingIntervals[configId]
          const toast = profilingFinishedToast(res.data)
          showToast(toast.message, toast.type)
        }
      } else {
        clearInterval(pollingIntervals[configId])
        delete pollingIntervals[configId]
      }
    } catch {
      clearInterval(pollingIntervals[configId])
      delete pollingIntervals[configId]
    }
  }, 2000)
}

const requestProfiling = (item: DataSource) => {
  openConfirm({
    title: '确认启动智能摸排',
    message: `智能摸排功能将对数据源 “${item.source_name}” 下所有的表 and 视图进行结构分析与数据采样，并调用大模型生成中文业务备注名、表用途和分类标签以辅助元数据导入。注意：逐表处理可能需要一些时间，且每个表的分析都需要消耗大模型的 Token。您确认启动吗？`,
    type: 'warning',
    confirmText: '确认启动',
    onConfirm: () => {
      confirmDialog.value.show = false
      triggerProfiling(item)
    }
  })
}

const triggerProfiling = async (item: DataSource, force = false) => {
  try {
    const res = await axios.post(`/api/portal/datasource/datasources/${item.id}/profile`, null, {
      params: { force },
    })
    showToast(
      force ? '已提交全量重跑摸排任务，将全部表重新分析' : '已提交后台分析摸排任务，串行处理大模型分析中',
      'success'
    )
    profilingTasks.value[item.id] = res.data
    startPolling(item.id)
  } catch (e: any) {
    showToast(e.response?.data?.detail || (force ? '全量重跑失败' : '启动摸排失败'), 'error')
  }
}

const hasProfilingHistory = (item: DataSource) => {
  const task = profilingTasks.value[item.id]
  if (!task || task.status === 1) return false
  return task.status === 2 || task.status === 3 || (task.processed_tables || 0) > 0
}

const requestForceProfiling = (item: DataSource) => {
  const total = profilingTasks.value[item.id]?.total_tables
  const totalHint = total ? `${total} 张` : '所有'
  openConfirm({
    title: '确认全量重跑摸排',
    message: `将对数据源 “${item.source_name}” 下 ${totalHint} 表/视图重新摸排。已完成的画像将被覆盖，每张表都会重新调用大模型，将显著消耗 Token 和时间。此操作不可撤销，确认全量重跑吗？`,
    type: 'danger',
    confirmText: '确认全量重跑',
    onConfirm: () => {
      confirmDialog.value.show = false
      triggerProfiling(item, true)
    }
  })
}

const requestCancelProfiling = (item: DataSource) => {
  openConfirm({
    title: '确认停止摸排',
    message: `将停止数据源 “${item.source_name}” 的摸排任务。当前正在处理的表会完成后停止，已成功摸排的表会保留。确认停止吗？`,
    type: 'warning',
    confirmText: '确认停止',
    onConfirm: () => {
      confirmDialog.value.show = false
      cancelProfiling(item)
    }
  })
}

const cancelProfiling = async (item: DataSource) => {
  try {
    const res = await axios.post(`/api/portal/datasource/datasources/${item.id}/profile/cancel`)
    profilingTasks.value[item.id] = res.data
    showToast('已请求停止摸排，当前表处理完成后生效', 'warning')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '停止摸排失败', 'error')
  }
}

type TableScope = {
  all_tables: boolean
  tables: string[]
  configured: boolean
}

type DatasourcePermissionRole = {
  id: number
  role_code: string
  role_name: string
  member_count: number
  table_scope: TableScope
}

type DatasourcePermissionUser = {
  id: number
  user_name: string
  status: number
  table_scope: TableScope
}

type DatasourcePermissionsData = {
  source_id: number
  source_name: string
  roles: DatasourcePermissionRole[]
  users: DatasourcePermissionUser[]
  admin_count: number
}

const showPermissionsTarget = ref<DataSource | null>(null)
const permissionsData = ref<DatasourcePermissionsData | null>(null)
const loadingPermissions = ref(false)
const permissionsTab = ref<'roles' | 'users'>('roles')

const formatTableScope = (scope?: TableScope) => {
  if (!scope?.configured) return '未配置表权限'
  if (scope.all_tables) return '所有表'
  if (scope.tables.length === 0) return '未配置表权限'
  if (scope.tables.length <= 3) return scope.tables.join('、')
  return `${scope.tables.slice(0, 3).join('、')} 等 ${scope.tables.length} 张表`
}

const openPermissionsView = async (item: DataSource) => {
  showPermissionsTarget.value = item
  permissionsData.value = null
  loadingPermissions.value = true
  permissionsTab.value = 'roles'
  try {
    const res = await axios.get(`/api/portal/datasource/datasources/${item.id}/permissions`)
    permissionsData.value = res.data
  } catch (e: any) {
    showToast(e.response?.data?.detail || '获取授权信息失败', 'error')
    showPermissionsTarget.value = null
  } finally {
    loadingPermissions.value = false
  }
}

const closePermissionsView = () => {
  showPermissionsTarget.value = null
  permissionsData.value = null
}

// 查看摸排分析结果
const showProfilesTarget = ref<DataSource | null>(null)

const openTableProfiles = async (item: DataSource) => {
  showProfilesTarget.value = item
  profileModalTask.value = profilingTasks.value[item.id] || null
  try {
    const taskRes = await axios.get(`/api/portal/datasource/datasources/${item.id}/profile-task`)
    if (taskRes.data) {
      profileModalTask.value = taskRes.data
      profilingTasks.value[item.id] = taskRes.data
    }
  } catch {
    // 沿用缓存任务状态即可
  }
}

const closeTableProfiles = () => {
  showProfilesTarget.value = null
  profileModalTask.value = null
}

const closeMore = () => {
  openMore.value = null
  moreMenuPos.value = null
}

onMounted(() => {
  checkRole()
  fetchDatasources()
  document.addEventListener('click', closeMore)
  window.addEventListener('scroll', closeMore, true)
  window.addEventListener('resize', closeMore)
})

onUnmounted(() => {
  Object.values(pollingIntervals).forEach((interval) => clearInterval(interval))
  document.removeEventListener('click', closeMore)
  window.removeEventListener('scroll', closeMore, true)
  window.removeEventListener('resize', closeMore)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-wrap justify-between items-start gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">数据源管理</h1>
        <p class="text-sm text-gray-500 mt-1">配置 ClickHouse / MySQL / Oracle 连接，供资源接口与 SQL 实验室使用</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-2 px-3 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
          :disabled="loading"
          @click="fetchDatasources"
        >
          <ArrowPathIcon class="w-4 h-4" :class="loading ? 'animate-spin' : ''" />
          刷新
        </button>
        <button
          v-if="canEdit"
          type="button"
          class="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 shadow-sm"
          @click="openCreateDialog"
        >
          <PlusIcon class="w-4 h-4" />
          新建数据源
        </button>
      </div>
    </div>

    <!-- Stats -->
    <div v-if="!loading && datasources.length > 0" class="grid grid-cols-2 md:grid-cols-3 gap-3">
      <div class="bg-white border border-gray-200 rounded-lg px-4 py-3">
        <p class="text-xs text-gray-500">全部</p>
        <p class="text-2xl font-bold text-gray-900">{{ stats.total }}</p>
      </div>
      <div class="bg-white border border-green-200 rounded-lg px-4 py-3 bg-green-50/50">
        <p class="text-xs text-green-700">已启用</p>
        <p class="text-2xl font-bold text-green-700">{{ stats.active }}</p>
      </div>
      <div class="bg-white border border-gray-200 rounded-lg px-4 py-3 col-span-2 md:col-span-1">
        <p class="text-xs text-gray-500">已停用</p>
        <p class="text-2xl font-bold text-gray-600">{{ stats.inactive }}</p>
      </div>
    </div>

    <!-- Toolbar -->
    <div v-if="!loading && datasources.length > 0" class="bg-white border border-gray-200 rounded-lg p-3 flex flex-wrap gap-3 items-center">
      <ClearableInput
        v-model="searchQuery"
        show-search-icon
        wrapper-class="flex-1 min-w-[200px]"
        input-class="py-2 text-sm"
        placeholder="搜索名称、主机、库名、描述..."
      />
      <select
        v-model="typeFilter"
        class="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option value="ALL">全部类型</option>
        <option value="clickhouse">ClickHouse</option>
        <option value="mysql">MySQL</option>
        <option value="oracle">Oracle</option>
        <option value="sqlserver">SQL Server</option>
      </select>
      <select
        v-model="statusFilter"
        class="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option value="ALL">全部状态</option>
        <option value="1">已启用</option>
        <option value="0">已停用</option>
      </select>
      <p v-if="searchQuery || typeFilter !== 'ALL' || statusFilter !== 'ALL'" class="text-xs text-gray-400">
        显示 {{ filteredDatasources.length }} / {{ datasources.length }} 项
      </p>
    </div>

    <!-- List -->
    <div class="bg-white shadow rounded-lg overflow-hidden border border-gray-200">
      <!-- Loading skeleton -->
      <div v-if="loading" class="p-6 space-y-4 animate-pulse">
        <div v-for="i in 4" :key="i" class="flex gap-4">
          <div class="h-10 w-10 bg-gray-100 rounded" />
          <div class="flex-1 space-y-2">
            <div class="h-4 bg-gray-100 rounded w-1/4" />
            <div class="h-3 bg-gray-100 rounded w-1/2" />
          </div>
        </div>
      </div>

      <!-- Empty -->
      <div v-else-if="datasources.length === 0" class="py-16 px-6 text-center">
        <CircleStackIcon class="w-14 h-14 mx-auto text-gray-300 mb-4" />
        <h3 class="text-lg font-medium text-gray-900 mb-1">暂无数据源</h3>
        <p class="text-sm text-gray-500 mb-6">添加第一个数据源后，即可在资源管理与 SQL 实验室中使用</p>
        <button
          v-if="canEdit"
          type="button"
          class="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
          @click="openCreateDialog"
        >
          <PlusIcon class="w-4 h-4" />
          新建数据源
        </button>
      </div>

      <!-- No filter results -->
      <div v-else-if="filteredDatasources.length === 0" class="py-12 text-center text-sm text-gray-500">
        没有匹配的数据源，请调整搜索或筛选条件
      </div>

      <!-- Table -->
      <div v-else class="overflow-x-auto">
        <p v-if="canEdit && !hasActiveFilters" class="px-6 py-2 text-xs text-gray-400 border-b border-gray-100 bg-gray-50/80">
          拖拽左侧手柄可调整排序{{ reordering ? '（保存中...）' : '' }}
        </p>
        <p v-else-if="canEdit && hasActiveFilters" class="px-6 py-2 text-xs text-amber-600 border-b border-amber-50 bg-amber-50/50">
          筛选模式下暂不可拖拽排序，请清除筛选后再调整顺序
        </p>
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th v-if="canEdit" class="w-10 px-4 py-3" />
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">数据源信息</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">类型 / 连接信息</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">更新时间</th>
              <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
            </tr>
          </thead>
          <draggable
            v-if="!hasActiveFilters"
            v-model="datasources"
            tag="tbody"
            item-key="id"
            :handle="canEdit ? '.drag-handle' : undefined"
            :disabled="!canEdit"
            class="bg-white divide-y divide-gray-200"
            @change="saveReorder"
          >
            <template #item="{ element: item }">
              <tr class="hover:bg-gray-50/80 group">
                <td v-if="canEdit" class="px-4 py-4 whitespace-nowrap">
                  <div class="drag-handle cursor-grab active:cursor-grabbing text-gray-300 hover:text-gray-500 transition-colors" title="拖拽排序">
                    <Bars3Icon class="w-5 h-5" />
                  </div>
                </td>
                <td class="px-6 py-4">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <div class="text-sm font-semibold text-gray-900 font-mono">{{ item.source_name }}</div>
                    <span v-if="profilingTasks[item.id] && profilingTasks[item.id]?.status !== 1" class="inline-flex items-center text-[10px] px-1.5 py-0.2 rounded-full font-bold transition-all shrink-0"
                          :class="[
                            profilingTasks[item.id]?.status === 2 ? 'bg-green-50 text-green-600 border border-green-100' : '',
                            isProfilingCancelled(profilingTasks[item.id]) ? 'bg-amber-50 text-amber-600 border border-amber-100' : '',
                            profilingTasks[item.id]?.status === 3 && !isProfilingCancelled(profilingTasks[item.id]) ? 'bg-red-50 text-red-600 border border-red-100' : '',
                          ]">
                      <template v-if="profilingTasks[item.id]?.status === 2">
                        摸排完成
                      </template>
                      <template v-else-if="profilingTasks[item.id]?.status === 3" :title="profilingTasks[item.id]?.error_message">
                        {{ profilingStatusLabel(profilingTasks[item.id]) }}
                      </template>
                    </span>
                  </div>
                  <div class="text-xs text-gray-500 truncate max-w-xs mt-0.5">{{ item.description || '暂无描述' }}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex flex-col items-start gap-1">
                    <span
                      class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      :class="dataSourceTypeClass(item.source_type)"
                    >
                      {{ DATA_SOURCE_TYPE_LABELS[item.source_type] || item.source_type }}
                    </span>
                    <button
                      type="button"
                      class="text-left group/conn mt-0.5"
                      title="点击复制连接摘要"
                      @click="copyConnectionHint(item)"
                    >
                      <div class="font-mono text-xs text-gray-800 group-hover/conn:text-blue-600">{{ item.host }}:{{ item.port }}</div>
                      <div class="text-xs text-gray-400">{{ item.database_name || 'default' }} · {{ item.username || '无用户名' }}</div>
                    </button>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex items-center gap-2">
                    <Switch
                      :model-value="item.status === 1"
                      :disabled="!canEdit"
                      @update:model-value="toggleStatus(item)"
                    />
                    <span class="text-xs" :class="item.status === 1 ? 'text-green-600' : 'text-gray-400'">
                      {{ item.status === 1 ? '启用' : '停用' }}
                    </span>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-xs text-gray-500">{{ formatDate(item.updated_at) }}</td>
                <td class="px-6 py-4 text-right">
                  <div class="flex flex-col items-end gap-1.5">
                    <div class="flex justify-end items-center gap-1.5">
                      <button
                        v-if="canEdit"
                        type="button"
                        class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-200 hover:border-gray-300 rounded-md transition-all duration-150 active:scale-95 shrink-0"
                        title="测试连接"
                        @click="testConnection(item)"
                      >
                        <PlayIcon class="w-3.5 h-3.5" />
                        测试
                      </button>
                      <button
                        v-if="canEdit"
                        type="button"
                        class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-200 hover:border-gray-300 rounded-md transition-all duration-150 active:scale-95 shrink-0"
                        @click="openEditDialog(item)"
                      >
                        <PencilSquareIcon class="w-3.5 h-3.5" />
                        编辑
                      </button>
                      <!-- 更多下拉（click toggle） -->
                      <div v-if="canEdit" class="relative" @click.stop>
                        <button
                          type="button"
                          class="inline-flex items-center gap-0.5 px-2 py-1 text-xs font-medium bg-white hover:bg-gray-50 border border-gray-200 hover:border-gray-300 rounded-md transition-all duration-150 active:scale-95"
                          :class="openMore === item.id ? 'text-gray-700 border-gray-300 bg-gray-50' : 'text-gray-500'"
                          @click="toggleMore(item.id, $event)"
                        >
                          更多
                          <svg class="w-3 h-3 transition-transform duration-150" :class="openMore === item.id ? 'rotate-180' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                        </button>
                      </div>
                      <span v-if="!canEdit" class="text-xs text-gray-400">只读</span>
                    </div>
                    <!-- 摸排进行中进度 -->
                    <div v-if="profilingTasks[item.id]?.status === 1" class="flex items-center gap-2 mt-0.5 max-w-[320px]">
                      <div class="text-[10px] text-blue-500 font-mono font-medium animate-pulse truncate" :title="`正在分析表: ${profilingTasks[item.id]?.current_table}`">
                        摸排中 {{ profilingProgressPercent(profilingTasks[item.id]) }}% · {{ profilingTasks[item.id]?.current_table || '等待中...' }}
                      </div>
                      <button
                        type="button"
                        class="text-[10px] text-amber-600 hover:text-amber-700 font-bold shrink-0"
                        @click="requestCancelProfiling(item)"
                      >
                        停止
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </draggable>
          <tbody v-else class="bg-white divide-y divide-gray-200">
            <tr v-for="item in filteredDatasources" :key="item.id" class="hover:bg-gray-50/80">
              <td v-if="canEdit" class="px-4 py-4" />
              <td class="px-6 py-4">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <div class="text-sm font-semibold text-gray-900 font-mono">{{ item.source_name }}</div>
                  <span v-if="profilingTasks[item.id] && profilingTasks[item.id]?.status !== 1" class="inline-flex items-center text-[10px] px-1.5 py-0.2 rounded-full font-bold transition-all shrink-0"
                        :class="[
                          profilingTasks[item.id]?.status === 2 ? 'bg-green-50 text-green-600 border border-green-100' : '',
                          isProfilingCancelled(profilingTasks[item.id]) ? 'bg-amber-50 text-amber-600 border border-amber-100' : '',
                          profilingTasks[item.id]?.status === 3 && !isProfilingCancelled(profilingTasks[item.id]) ? 'bg-red-50 text-red-600 border border-red-100' : '',
                        ]">
                    <template v-if="profilingTasks[item.id]?.status === 2">
                      摸排完成
                    </template>
                    <template v-else-if="profilingTasks[item.id]?.status === 3" :title="profilingTasks[item.id]?.error_message">
                      {{ profilingStatusLabel(profilingTasks[item.id]) }}
                    </template>
                  </span>
                </div>
                <div class="text-xs text-gray-500 truncate max-w-xs mt-0.5">{{ item.description || '暂无描述' }}</div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex flex-col items-start gap-1">
                  <span
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold shrink-0"
                    :class="dataSourceTypeClass(item.source_type)"
                  >
                    {{ DATA_SOURCE_TYPE_LABELS[item.source_type] || item.source_type }}
                  </span>
                  <button
                    type="button"
                    class="text-left group/conn mt-0.5"
                    title="点击复制连接摘要"
                    @click="copyConnectionHint(item)"
                  >
                    <div class="font-mono text-xs text-gray-800 group-hover/conn:text-blue-600">{{ item.host }}:{{ item.port }}</div>
                    <div class="text-xs text-gray-400">{{ item.database_name || 'default' }} · {{ item.username || '无用户名' }}</div>
                  </button>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center gap-2">
                  <Switch :model-value="item.status === 1" :disabled="!canEdit" @update:model-value="toggleStatus(item)" />
                  <span class="text-xs" :class="item.status === 1 ? 'text-green-600' : 'text-gray-400'">{{ item.status === 1 ? '启用' : '停用' }}</span>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-xs text-gray-500">{{ formatDate(item.updated_at) }}</td>
              <td class="px-6 py-4 text-right">
                <div class="flex flex-col items-end gap-1.5">
                  <div class="flex justify-end items-center gap-1.5">
                    <button v-if="canEdit" type="button" class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-200 hover:border-gray-300 rounded-md transition-all duration-150 active:scale-95 shrink-0" @click="testConnection(item)">
                      <PlayIcon class="w-3.5 h-3.5" /> 测试
                    </button>
                    <button v-if="canEdit" type="button" class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-200 hover:border-gray-300 rounded-md transition-all duration-150 active:scale-95 shrink-0" @click="openEditDialog(item)">
                      <PencilSquareIcon class="w-3.5 h-3.5" /> 编辑
                    </button>
                    <!-- 更多下拉（click toggle） -->
                    <div v-if="canEdit" class="relative" @click.stop>
                      <button
                        type="button"
                        class="inline-flex items-center gap-0.5 px-2 py-1 text-xs font-medium bg-white hover:bg-gray-50 border border-gray-200 hover:border-gray-300 rounded-md transition-all duration-150 active:scale-95"
                        :class="openMore === item.id ? 'text-gray-700 border-gray-300 bg-gray-50' : 'text-gray-500'"
                        @click="toggleMore(item.id, $event)"
                      >
                        更多
                        <svg class="w-3 h-3 transition-transform duration-150" :class="openMore === item.id ? 'rotate-180' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                      </button>
                    </div>
                    <span v-if="!canEdit" class="text-xs text-gray-400">只读</span>
                  </div>
                  <!-- 摸排进行中进度 -->
                  <div v-if="profilingTasks[item.id]?.status === 1" class="flex items-center gap-2 mt-0.5 max-w-[320px]">
                    <div class="text-[10px] text-blue-500 font-mono font-medium animate-pulse truncate" :title="`正在分析表: ${profilingTasks[item.id]?.current_table}`">
                      摸排中 {{ profilingProgressPercent(profilingTasks[item.id]) }}% · {{ profilingTasks[item.id]?.current_table || '等待中...' }}
                    </div>
                    <button
                      type="button"
                      class="text-[10px] text-amber-600 hover:text-amber-700 font-bold shrink-0"
                      @click="requestCancelProfiling(item)"
                    >
                      停止
                    </button>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 更多操作菜单（Teleport 避免表格 overflow 裁切） -->
    <Teleport to="body">
      <div
        v-if="openMoreItem && moreMenuPos"
        class="fixed z-[9998] w-36 bg-white border border-gray-100 rounded-lg shadow-xl py-1 overflow-hidden"
        :style="{
          top: `${moreMenuPos.top}px`,
          left: `${moreMenuPos.left}px`,
          minWidth: `${moreMenuPos.minWidth}px`,
          transform: moreMenuPos.openUp ? 'translate(-100%, -100%)' : 'translateX(-100%)',
        }"
        @click.stop
      >
        <button
          v-if="profilingTasks[openMoreItem.id]?.status === 1"
          type="button"
          class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-amber-600 hover:bg-amber-50 transition-colors"
          @click="requestCancelProfiling(openMoreItem); closeMore()"
        >
          <CircleStackIcon class="w-3.5 h-3.5 shrink-0" />
          停止摸排
        </button>
        <button
          type="button"
          class="w-full flex items-center gap-2 px-3 py-1.5 text-xs transition-colors"
          :class="profilingTasks[openMoreItem.id]?.status === 1 || openMoreItem.status !== 1 ? 'text-gray-300 cursor-not-allowed' : 'text-indigo-600 hover:bg-indigo-50'"
          :disabled="profilingTasks[openMoreItem.id]?.status === 1 || openMoreItem.status !== 1"
          @click="requestProfiling(openMoreItem); closeMore()"
        >
          <CircleStackIcon class="w-3.5 h-3.5 shrink-0" :class="profilingTasks[openMoreItem.id]?.status === 1 ? 'animate-spin' : ''" />
          {{ profilingTasks[openMoreItem.id]?.status === 1 ? '摸排中...' : '启动摸排' }}
        </button>
        <button
          v-if="hasProfilingHistory(openMoreItem)"
          type="button"
          class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 transition-colors"
          @click="requestForceProfiling(openMoreItem); closeMore()"
        >
          <ArrowPathIcon class="w-3.5 h-3.5 shrink-0" />
          全量重跑
        </button>
        <button
          v-if="hasViewableProfiles(openMoreItem)"
          type="button"
          class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-purple-600 hover:bg-purple-50 transition-colors"
          @click="openTableProfiles(openMoreItem); closeMore()"
        >
          <CircleStackIcon class="w-3.5 h-3.5 shrink-0" />
          查看画像
          <span
            v-if="profilingTasks[openMoreItem.id]?.status === 1"
            class="ml-auto text-[9px] text-purple-400 font-mono"
          >{{ profilingTasks[openMoreItem.id]?.completed_profiles }}</span>
        </button>
        <button
          type="button"
          class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-blue-600 hover:bg-blue-50 transition-colors"
          @click="openPermissionsView(openMoreItem); closeMore()"
        >
          <ShieldCheckIcon class="w-3.5 h-3.5 shrink-0" />
          查看授权
        </button>
        <div class="h-px bg-gray-100 mx-2 my-1" />
        <button
          type="button"
          class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 transition-colors"
          @click="openCopyDialog(openMoreItem); closeMore()"
        >
          <DocumentDuplicateIcon class="w-3.5 h-3.5 shrink-0" />
          复制新建
        </button>
        <div class="h-px bg-gray-100 mx-2 my-1" />
        <button
          type="button"
          class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 transition-colors"
          @click="confirmDelete(openMoreItem); closeMore()"
        >
          <TrashIcon class="w-3.5 h-3.5 shrink-0" />
          删除
        </button>
      </div>
    </Teleport>

    <!-- Create / Edit Dialog -->
    <Teleport to="body">
      <div
        v-if="showCreateDialog || showEditDialog"
        class="fixed inset-0 z-[9990] flex items-center justify-center p-4 bg-black/50"
        @click.self="closeDialogs"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
          <div class="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex justify-between items-center">
            <div>
              <h2 class="text-lg font-bold text-gray-900">
                {{ showEditDialog ? '编辑数据源' : copyFromName ? '复制新建数据源' : '新建数据源' }}
              </h2>
              <p class="text-xs text-gray-500 mt-0.5">
                <template v-if="showEditDialog">数据源名称创建后不可修改</template>
                <template v-else-if="copyFromName">基于「{{ copyFromName }}」复制，请修改名称并重新填写密码</template>
                <template v-else>名称创建后不可修改，请使用有意义的英文标识</template>
              </p>
            </div>
            <button type="button" class="text-gray-400 hover:text-gray-600 p-1" @click="closeDialogs">✕</button>
          </div>

          <form class="p-6 space-y-5" @submit.prevent="saveDataSource">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">数据源名称 <span class="text-red-500">*</span></label>
                <input
                  v-model="formData.source_name"
                  type="text"
                  required
                  :disabled="showEditDialog"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                  placeholder="例如 prod_clickhouse"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">类型 <span class="text-red-500">*</span></label>
                <select
                  v-model="formData.source_type"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  @change="updatePort"
                >
                  <option value="clickhouse">ClickHouse</option>
                  <option value="mysql">MySQL</option>
                  <option value="oracle">Oracle</option>
        <option value="sqlserver">SQL Server</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">状态</label>
                <select v-model.number="formData.status" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option :value="1">启用</option>
                  <option :value="0">停用</option>
                </select>
              </div>

              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">主机地址 <span class="text-red-500">*</span></label>
                <input
                  v-model="formData.host"
                  type="text"
                  required
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="例如 10.0.0.1 或 db.example.com"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">端口 <span class="text-red-500">*</span></label>
                <input
                  v-model.number="formData.port"
                  type="number"
                  required
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">数据库 / Schema</label>
                <input
                  v-model="formData.database_name"
                  type="text"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="默认 default"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                <input v-model="formData.username" type="text" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">
                  密码
                  <span v-if="copyFromName" class="text-red-500">*</span>
                </label>
                <input
                  v-model="formData.password"
                  type="password"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  :placeholder="showEditDialog ? '留空则保持原密码' : copyFromName ? '复制新建需重新填写密码' : ''"
                />
              </div>

              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  v-model="formData.description"
                  rows="2"
                  class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="用途说明，便于团队识别"
                />
              </div>

              <div v-if="formData.source_type === 'sqlserver'" class="md:col-span-2 border border-gray-200 rounded-lg p-4 space-y-4 bg-gray-50/60">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <p class="text-sm font-medium text-gray-800">SQL Server 高级连接参数</p>
                    <p class="text-xs text-gray-500 mt-0.5">用于 ODBC Driver、TLS 与证书兼容配置</p>
                  </div>
                </div>

                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">兼容模式</label>
                  <select
                    v-model="formData.extra_params.compat_mode"
                    class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    @change="applySqlServerCompatMode"
                  >
                    <option value="modern">现代模式（SQL Server 2016+ / 默认）</option>
                    <option value="sqlserver_2014">SQL Server 2014 / 2012 兼容模式</option>
                  </select>
                  <p v-if="formData.extra_params.compat_mode === 'sqlserver_2014'" class="text-xs text-amber-600 mt-1">
                    将使用 ODBC Driver 17、关闭 Encrypt 并信任服务端证书；运行环境需安装 ODBC Driver 17。
                  </p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="flex items-center justify-between gap-3 bg-white border border-gray-200 rounded-lg px-3 py-2.5">
                    <div>
                      <p class="text-sm font-medium text-gray-700">Encrypt</p>
                      <p class="text-xs text-gray-500">加密连接</p>
                    </div>
                    <Switch v-model="formData.extra_params.encrypt" />
                  </div>

                  <div class="flex items-center justify-between gap-3 bg-white border border-gray-200 rounded-lg px-3 py-2.5">
                    <div>
                      <p class="text-sm font-medium text-gray-700">TrustServerCertificate</p>
                      <p class="text-xs text-gray-500">信任服务端证书</p>
                    </div>
                    <Switch v-model="formData.extra_params.trust_server_certificate" />
                  </div>
                </div>

                <div>
                  <div class="flex items-center justify-between gap-3 mb-1">
                    <label class="block text-sm font-medium text-gray-700">ODBC Driver</label>
                    <div class="flex items-center gap-1">
                      <button
                        type="button"
                        class="px-2 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                        @click="useSqlServerDriver(SQLSERVER_DRIVER_17)"
                      >
                        Driver 17
                      </button>
                      <button
                        type="button"
                        class="px-2 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                        @click="useSqlServerDriver(SQLSERVER_DRIVER_18)"
                      >
                        Driver 18
                      </button>
                    </div>
                  </div>
                  <input
                    v-model="formData.extra_params.odbc_driver"
                    type="text"
                    class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="ODBC Driver 18 for SQL Server"
                  />
                </div>
              </div>
            </div>

            <div v-if="formError" class="bg-red-50 text-red-700 p-3 rounded-lg text-sm border border-red-200">
              {{ formError }}
            </div>

            <div class="flex flex-col gap-3 pt-2 border-t border-gray-100 sm:flex-row sm:items-center sm:justify-between">
              <div class="min-h-9">
                <button
                  v-if="showEditDialog"
                  type="button"
                  :disabled="testingConnection || submitting"
                  class="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-green-700 bg-green-50 hover:bg-green-100 rounded-lg disabled:opacity-50"
                  @click="testEditingConnection"
                >
                  <PlayIcon class="w-4 h-4" />
                  {{ testingConnection ? '测试中...' : '测试当前配置' }}
                </button>
              </div>
              <div class="flex justify-end gap-3">
                <button type="button" class="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50" @click="closeDialogs">
                  取消
                </button>
                <button
                  type="submit"
                  :disabled="submitting"
                  class="px-5 py-2 text-sm bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {{ submitting ? '保存中...' : '保存' }}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <!-- Test Result Dialog -->
    <Teleport to="body">
      <div
        v-if="showPermissionsTarget"
        class="fixed inset-0 z-[9990] flex items-center justify-center p-4 bg-black/50"
        @click.self="closePermissionsView"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden">
          <div class="px-6 py-4 border-b border-gray-100 flex items-start justify-between gap-4">
            <div>
              <h3 class="text-lg font-bold text-gray-900">查看授权</h3>
              <p class="text-xs text-gray-500 mt-0.5 font-mono">{{ showPermissionsTarget.source_name }}</p>
            </div>
            <button type="button" class="text-gray-400 hover:text-gray-600 p-1" @click="closePermissionsView">✕</button>
          </div>

          <div v-if="loadingPermissions" class="flex-1 flex flex-col items-center justify-center py-16">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            <p class="mt-3 text-sm text-gray-500">正在加载授权信息...</p>
          </div>

          <template v-else-if="permissionsData">
            <div class="px-6 pt-4">
              <div class="flex items-center gap-2 p-3 rounded-lg bg-amber-50 border border-amber-100 text-xs text-amber-800">
                <ShieldCheckIcon class="w-4 h-4 shrink-0" />
                <span>
                  平台管理员（{{ permissionsData.admin_count }} 人）默认拥有全部数据源访问权限。
                  此处仅展示在角色/用户管理中<strong>直接配置</strong>的授权。
                </span>
              </div>

              <div class="mt-4 flex gap-1 p-1 bg-gray-100 rounded-lg w-fit">
                <button
                  type="button"
                  class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
                  :class="permissionsTab === 'roles' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
                  @click="permissionsTab = 'roles'"
                >
                  角色授权
                  <span class="ml-1 text-gray-400">({{ permissionsData.roles.length }})</span>
                </button>
                <button
                  type="button"
                  class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
                  :class="permissionsTab === 'users' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
                  @click="permissionsTab = 'users'"
                >
                  用户直授
                  <span class="ml-1 text-gray-400">({{ permissionsData.users.length }})</span>
                </button>
              </div>
            </div>

            <div class="flex-1 overflow-y-auto px-6 py-4">
              <div v-if="permissionsTab === 'roles'">
                <div v-if="permissionsData.roles.length === 0" class="py-10 text-center text-sm text-gray-400">
                  暂无角色被直接授权访问此数据源
                </div>
                <table v-else class="w-full text-sm">
                  <thead>
                    <tr class="text-left text-xs text-gray-500 border-b border-gray-100">
                      <th class="pb-2 font-medium">角色</th>
                      <th class="pb-2 font-medium">成员数</th>
                      <th class="pb-2 font-medium">表级范围</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-50">
                    <tr v-for="role in permissionsData.roles" :key="role.id" class="text-gray-700">
                      <td class="py-2.5 pr-3">
                        <div class="font-medium text-gray-900">{{ role.role_name }}</div>
                        <div class="text-[11px] text-gray-400 font-mono">{{ role.role_code }}</div>
                      </td>
                      <td class="py-2.5 pr-3 whitespace-nowrap">{{ role.member_count }}</td>
                      <td class="py-2.5">
                        <span
                          class="inline-flex px-2 py-0.5 rounded text-xs"
                          :class="role.table_scope.configured ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'"
                        >
                          {{ formatTableScope(role.table_scope) }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div v-else>
                <div v-if="permissionsData.users.length === 0" class="py-10 text-center text-sm text-gray-400">
                  暂无用户被直接授权访问此数据源
                </div>
                <table v-else class="w-full text-sm">
                  <thead>
                    <tr class="text-left text-xs text-gray-500 border-b border-gray-100">
                      <th class="pb-2 font-medium">用户</th>
                      <th class="pb-2 font-medium">状态</th>
                      <th class="pb-2 font-medium">表级范围</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-50">
                    <tr v-for="user in permissionsData.users" :key="user.id" class="text-gray-700">
                      <td class="py-2.5 pr-3 font-medium text-gray-900">{{ user.user_name }}</td>
                      <td class="py-2.5 pr-3">
                        <span
                          class="inline-flex px-2 py-0.5 rounded text-xs"
                          :class="user.status === 1 ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'"
                        >
                          {{ user.status === 1 ? '启用' : '禁用' }}
                        </span>
                      </td>
                      <td class="py-2.5">
                        <span
                          class="inline-flex px-2 py-0.5 rounded text-xs"
                          :class="user.table_scope.configured ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'"
                        >
                          {{ formatTableScope(user.table_scope) }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>

          <div class="px-6 py-4 border-t border-gray-100 flex justify-end">
            <button type="button" class="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg" @click="closePermissionsView">
              关闭
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Test Result Dialog -->
    <Teleport to="body">
      <div
        v-if="showTestDialog"
        class="fixed inset-0 z-[9990] flex items-center justify-center p-4 bg-black/50"
        @click.self="closeTestDialog"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6 text-center">
          <h3 class="text-lg font-bold text-gray-900 mb-1">连接测试</h3>
          <p v-if="testingItem" class="text-xs text-gray-500 font-mono mb-4">{{ testingItem.source_name }}</p>

          <div v-if="testingConnection" class="py-6">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            <p class="mt-3 text-sm text-gray-500">正在连接 {{ testingItem?.host }}:{{ testingItem?.port }}...</p>
          </div>

          <div v-else-if="testResult" class="py-4">
            <div v-if="testResult.success" class="text-green-600">
              <div class="w-12 h-12 mx-auto mb-2 rounded-full bg-green-100 flex items-center justify-center text-2xl">✓</div>
              <p class="font-bold">连接成功</p>
              <p class="text-sm text-gray-500 mt-1">{{ testResult.message }}</p>
            </div>
            <div v-else class="text-red-600">
              <div class="w-12 h-12 mx-auto mb-2 rounded-full bg-red-100 flex items-center justify-center text-2xl">✕</div>
              <p class="font-bold">连接失败</p>
              <p class="text-sm text-gray-600 mt-2 break-words text-left bg-red-50 p-3 rounded-lg">{{ testResult.message }}</p>
            </div>
          </div>

          <button type="button" class="mt-4 w-full px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg" @click="closeTestDialog">
            关闭
          </button>
        </div>
      </div>
    </Teleport>

    <!-- 摸排资产浏览（复用 SQL Lab 表探索器） -->
    <LabTableExplorer
      v-if="showProfilesTarget"
      mode="browse"
      :source-id="showProfilesTarget.id"
      :source-name="showProfilesTarget.source_name"
      :subtitle="profileModalTimeLabel"
      include-ignored
      :allow-ignore-toggle="canEdit"
      @close="closeTableProfiles"
    />

    <ConfirmDialog
      :show="confirmDialog.show"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :type="confirmDialog.type"
      :confirm-text="confirmDialog.confirmText"
      @confirm="confirmDialog.onConfirm()"
      @cancel="confirmDialog.show = false"
    />

    <Toast v-if="toast.show" :key="toast.key" :message="toast.message" :type="toast.type" @close="closeToast" />
  </div>
</template>
