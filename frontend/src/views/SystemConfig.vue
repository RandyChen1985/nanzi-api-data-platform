<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from '@/utils/axios'
import { useToast } from '../composables/useToast'
import { copyToClipboard } from '@/utils/clipboard'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import Switch from '../components/Switch.vue'
import SystemMonitor from '../components/SystemMonitor.vue'
import Tooltip from '../components/common/Tooltip.vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  VisualMapComponent,
  MarkLineComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  VisualMapComponent,
  MarkLineComponent
])

import {
  CheckCircleIcon,
  ArrowPathIcon,
  CpuChipIcon,
  CircleStackIcon,
  ShieldCheckIcon
} from '@heroicons/vue/24/outline'
const activeTab = ref<'monitor' | 'ratelimit' | 'diagnostic' | 'pools' | 'logs' | 'ai' | 'masking' | 'platform'>('monitor')
const platformSection = ref<'catalog' | 'dingtalk' | 'wecom' | 'mcp' | 'branding'>('catalog')

const settingsTabs = [
  { id: 'monitor' as const, label: '系统监控' },
  { id: 'ratelimit' as const, label: '流控设置' },
  { id: 'diagnostic' as const, label: '系统诊断' },
  { id: 'pools' as const, label: '连接池监控' },
  { id: 'logs' as const, label: '日志管理' },
  { id: 'ai' as const, label: 'AI 模型' },
  { id: 'masking' as const, label: '数据脱敏' },
  { id: 'platform' as const, label: '系统配置' },
]

const platformSections = [
  { id: 'catalog' as const, label: '数据产品目录' },
  { id: 'dingtalk' as const, label: '钉钉通知' },
  { id: 'wecom' as const, label: '企微通知' },
  { id: 'mcp' as const, label: 'MCP 服务' },
  { id: 'branding' as const, label: '品牌个性化' },
]

type SettingsTabId = (typeof settingsTabs)[number]['id']

const onMobileTabChange = (e: Event) => {
  switchTab((e.target as HTMLSelectElement).value as SettingsTabId)
}
const logSubTab = ref<'tasks' | 'shards'>('tasks')
const logs = ref<string[]>([])
const maintenanceLogs = ref<any[]>([])
const shardLogs = ref<any[]>([])
const loading = ref<{ [key: string]: boolean }> ({
  redis: false,
  redis_scan: false,
  vector: false,
  pools_fetch: false,
  pools_health: false,
  log_purge: false,
  log_aggregate: false,
  m_logs: false,
  shard_logs: false,
  save_config: false,
  ai_load: false,
  ai_save: false,
  ai_test: false,
  rl_load: false,
  rl_save: false,
  rl_peak: false,
  masking_load: false,
  masking_save: false,
  platform_load: false,
  platform_save: false,
  dingtalk_save: false,
  dingtalk_test: false,
  wecom_save: false,
  wecom_test: false,
  mcp_save: false,
  mcp_test: false,
  branding_save: false,
  branding_icon: false,
})

// Data Masking State
interface MaskingRule {
  id?: number
  rule_name: string
  match_field: string
  mask_type: 'PARTIAL_3_4' | 'PARTIAL_4' | 'EMAIL' | 'FULL'
  is_active: number
  description?: string
}

const maskingRules = ref<MaskingRule[]>([])
const maskingGlobalEnabled = ref(true)

interface GroupOwnerRow {
  group: string
  user_id: number | null
}

const catalogConfig = ref({
  default_owner_strategy: 'publisher' as 'publisher' | 'group_owner' | 'none',
  group_owner_rows: [] as GroupOwnerRow[],
  notify_resource_change_enabled: true,
  notify_resource_change_webhook_url: '',
})
const dingtalkConfig = ref({
  enabled: false,
  webhook_url: '',
  secret: '',
  notify_on_request: true,
  notify_on_result: true,
})
const wecomConfig = ref({
  enabled: false,
  webhook_url: '',
  secret: '',
  notify_on_request: true,
  notify_on_result: true,
})
const mcpConfig = ref({
  enabled: false,
  instructions: '',
  sse_path: '/mcp/sse',
  sse_url: '',
  stdio_command: 'python -m yunshu_mcp',
})
const brandingConfig = ref({
  enabled: false,
  product_name: '云枢 · 数据服务平台',
  login_subtitle: 'Yunshu API Data Platform',
  icon_url: '/favicon.png',
  hide_login_sso: false,
  hide_version_link: false,
  contact_markdown: '',
  copyright_text: '',
})
const brandingIconInput = ref<HTMLInputElement | null>(null)
interface McpTestCheck {
  name: string
  ok: boolean
  detail: string
}
const mcpTestResult = ref<{
  success: boolean
  checks: McpTestCheck[]
  tools: string[]
  sse_url: string
} | null>(null)
const catalogUsers = ref<{ id: number; user_name: string; remark?: string }[]>([])

const applyPlatformSettings = (data: any) => {
  const catalog = data.catalog || {}
  catalogConfig.value.default_owner_strategy = catalog.default_owner_strategy || 'publisher'
  catalogConfig.value.notify_resource_change_enabled = catalog.notify_resource_change_enabled !== false
  catalogConfig.value.notify_resource_change_webhook_url = catalog.notify_resource_change_webhook_url || ''
  const map = catalog.group_owner_map || {}
  catalogConfig.value.group_owner_rows = Object.entries(map).map(([group, user_id]) => ({
    group,
    user_id: Number(user_id),
  }))

  const dingtalk = data.dingtalk || {}
  dingtalkConfig.value.enabled = !!dingtalk.enabled
  dingtalkConfig.value.webhook_url = dingtalk.webhook_url || ''
  dingtalkConfig.value.secret = dingtalk.secret || ''
  dingtalkConfig.value.notify_on_request = dingtalk.notify_on_request !== false
  dingtalkConfig.value.notify_on_result = dingtalk.notify_on_result !== false

  const wecom = data.wecom || {}
  wecomConfig.value.enabled = !!wecom.enabled
  wecomConfig.value.webhook_url = wecom.webhook_url || ''
  wecomConfig.value.secret = wecom.secret || ''
  wecomConfig.value.notify_on_request = wecom.notify_on_request !== false
  wecomConfig.value.notify_on_result = wecom.notify_on_result !== false

  const mcp = data.mcp || {}
  mcpConfig.value.enabled = !!mcp.enabled
  mcpConfig.value.instructions = mcp.instructions || ''
  mcpConfig.value.sse_path = mcp.sse_path || '/mcp/sse'
  mcpConfig.value.sse_url = mcp.sse_url || ''
  mcpConfig.value.stdio_command = mcp.stdio_command || 'python -m yunshu_mcp'

  const branding = data.branding || {}
  brandingConfig.value.enabled = !!branding.enabled
  brandingConfig.value.product_name = branding.product_name || '云枢 · 数据服务平台'
  brandingConfig.value.login_subtitle = branding.login_subtitle || 'Yunshu API Data Platform'
  brandingConfig.value.icon_url = branding.icon_url || '/favicon.png'
  brandingConfig.value.hide_login_sso = !!branding.hide_login_sso
  brandingConfig.value.hide_version_link = !!branding.hide_version_link
  brandingConfig.value.contact_markdown = branding.contact_markdown || ''
  brandingConfig.value.copyright_text = branding.copyright_text || ''
}

const fetchPlatformSettings = async () => {
  loading.value.platform_load = true
  try {
    const [settingsRes, usersRes] = await Promise.all([
      axios.get('/api/portal/system/platform-settings'),
      axios.get('/api/portal/catalog/assign-owner-users'),
    ])
    applyPlatformSettings(settingsRes.data)
    catalogUsers.value = usersRes.data
  } catch {
    showToast('系统配置加载失败', 'error')
  } finally {
    loading.value.platform_load = false
  }
}

const addGroupOwnerRow = () => {
  catalogConfig.value.group_owner_rows.push({ group: '', user_id: null })
}

const removeGroupOwnerRow = (index: number) => {
  catalogConfig.value.group_owner_rows.splice(index, 1)
}

const buildCatalogPayload = () => {
  const group_owner_map: Record<string, number> = {}
  for (const row of catalogConfig.value.group_owner_rows) {
    const g = row.group.trim()
    if (g && row.user_id) {
      group_owner_map[g] = row.user_id
    }
  }
  return {
    default_owner_strategy: catalogConfig.value.default_owner_strategy,
    group_owner_map,
    notify_resource_change_enabled: catalogConfig.value.notify_resource_change_enabled,
    notify_resource_change_webhook_url: catalogConfig.value.notify_resource_change_webhook_url,
  }
}

const saveCatalogPlatformConfig = async () => {
  loading.value.platform_save = true
  try {
    const res = await axios.put('/api/portal/system/platform-settings', {
      catalog: buildCatalogPayload(),
    })
    applyPlatformSettings(res.data)
    showToast('目录配置已保存', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    loading.value.platform_save = false
  }
}

const saveDingtalkPlatformConfig = async () => {
  loading.value.dingtalk_save = true
  try {
    const res = await axios.put('/api/portal/system/platform-settings', {
      dingtalk: { ...dingtalkConfig.value },
    })
    applyPlatformSettings(res.data)
    showToast('钉钉通知配置已保存', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    loading.value.dingtalk_save = false
  }
}

const saveWecomPlatformConfig = async () => {
  loading.value.wecom_save = true
  try {
    const res = await axios.put('/api/portal/system/platform-settings', {
      wecom: { ...wecomConfig.value },
    })
    applyPlatformSettings(res.data)
    showToast('企微通知配置已保存', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    loading.value.wecom_save = false
  }
}

const saveMcpPlatformConfig = async () => {
  loading.value.mcp_save = true
  try {
    const res = await axios.put('/api/portal/system/platform-settings', {
      mcp: {
        enabled: mcpConfig.value.enabled,
        instructions: mcpConfig.value.instructions,
      },
    })
    applyPlatformSettings(res.data)
    showToast('MCP 配置已保存', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    loading.value.mcp_save = false
  }
}

const testMcpServer = async () => {
  loading.value.mcp_test = true
  mcpTestResult.value = null
  try {
    const res = await axios.post('/api/portal/system/platform-settings/mcp/test', {
      enabled: mcpConfig.value.enabled,
      instructions: mcpConfig.value.instructions,
    })
    mcpTestResult.value = res.data
    if (res.data.success) {
      showToast('MCP 连通性测试通过', 'success')
    } else {
      showToast('MCP 测试未全部通过，请查看下方明细', 'error')
    }
  } catch (e: any) {
    showToast(e.response?.data?.detail || '测试请求失败', 'error')
  } finally {
    loading.value.mcp_test = false
  }
}

const copyMcpSseUrl = async () => {
  const url = mcpConfig.value.sse_url
  if (!url) {
    showToast('暂无 SSE 地址', 'error')
    return
  }
  const success = await copyToClipboard(url)
  if (success) {
    showToast('已复制 SSE 地址', 'success')
  } else {
    showToast('复制失败，请手动选择复制', 'error')
  }
}

const mcpSseCursorExample = computed(() =>
  JSON.stringify(
    {
      mcpServers: {
        yunshu: {
          url: mcpConfig.value.sse_url || 'https://data.example.com/mcp/sse',
          headers: {
            'X-API-Key': '你的个人 API Key',
          },
        },
      },
    },
    null,
    2,
  ),
)

const copyMcpSseCursorConfig = async () => {
  const success = await copyToClipboard(mcpSseCursorExample.value)
  if (success) {
    showToast('已复制 Cursor SSE 配置示例', 'success')
  } else {
    showToast('复制失败，请手动选择复制', 'error')
  }
}

const saveBrandingPlatformConfig = async () => {
  loading.value.branding_save = true
  try {
    const res = await axios.put('/api/portal/system/platform-settings', {
      branding: { ...brandingConfig.value },
    })
    applyPlatformSettings(res.data)
    const { loadBranding } = await import('@/composables/useBranding')
    await loadBranding(true)
    showToast('品牌配置已保存', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    loading.value.branding_save = false
  }
}

const triggerBrandingIconUpload = () => {
  brandingIconInput.value?.click()
}

const onBrandingIconSelected = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  loading.value.branding_icon = true
  try {
    const form = new FormData()
    form.append('file', file)
    const res = await axios.post('/api/portal/system/branding/icon', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    brandingConfig.value.icon_url = res.data.icon_url
    showToast('图标已上传，请保存配置后生效', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '图标上传失败', 'error')
  } finally {
    loading.value.branding_icon = false
  }
}

const testDingtalkNotification = async () => {
  loading.value.dingtalk_test = true
  try {
    await axios.post('/api/portal/system/platform-settings/dingtalk/test', {
      ...dingtalkConfig.value,
    })
    showToast('测试消息已发送，请在钉钉群查看', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '测试发送失败', 'error')
  } finally {
    loading.value.dingtalk_test = false
  }
}

const testWecomNotification = async () => {
  loading.value.wecom_test = true
  try {
    await axios.post('/api/portal/system/platform-settings/wecom/test', {
      ...wecomConfig.value,
    })
    showToast('测试消息已发送，请在企业微信群查看', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '测试发送失败', 'error')
  } finally {
    loading.value.wecom_test = false
  }
}

const showMaskingModal = ref(false)
const editingRule = ref<MaskingRule>({
  rule_name: '',
  match_field: '',
  mask_type: 'PARTIAL_3_4',
  is_active: 1
})

const fetchMaskingConfig = async () => {
  loading.value.masking_load = true
  try {
    const [rulesRes, configRes] = await Promise.all([
      axios.get('/api/portal/system/masking/rules'),
      axios.get('/api/portal/system/masking/config')
    ])
    maskingRules.value = rulesRes.data
    maskingGlobalEnabled.value = configRes.data.enabled
  } catch (e: any) {
    showToast('脱敏配置加载失败', 'error')
  } finally {
    loading.value.masking_load = false
  }
}

const toggleGlobalMasking = async () => {
  try {
    await axios.post('/api/portal/system/masking/config', { enabled: maskingGlobalEnabled.value })
    showToast('全局脱敏开关已更新', 'success')
  } catch (e) {
    maskingGlobalEnabled.value = !maskingGlobalEnabled.value
    showToast('更新失败', 'error')
  }
}

const openMaskingModal = (rule?: MaskingRule) => {
  if (rule) {
    editingRule.value = { ...rule }
  } else {
    editingRule.value = {
      rule_name: '',
      match_field: '',
      mask_type: 'PARTIAL_3_4',
      is_active: 1,
      description: ''
    }
  }
  showMaskingModal.value = true
}

const saveMaskingRule = async () => {
  loading.value.masking_save = true
  try {
    if (editingRule.value.id) {
      await axios.put(`/api/portal/system/masking/rules/${editingRule.value.id}`, editingRule.value)
    } else {
      await axios.post('/api/portal/system/masking/rules', editingRule.value)
    }
    showToast('规则已保存', 'success')
    showMaskingModal.value = false
    await fetchMaskingConfig()
  } catch (e: any) {
    showToast('保存失败: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    loading.value.masking_save = false
  }
}

const toggleRuleStatus = async (rule: MaskingRule) => {
  if (!rule.id) return
  const newStatus = rule.is_active === 1 ? 0 : 1
  try {
    await axios.put(`/api/portal/system/masking/rules/${rule.id}`, { is_active: newStatus })
    rule.is_active = newStatus // Optimistic update
    showToast(`规则已${newStatus ? '启用' : '禁用'}`, 'success')
  } catch (e: any) {
    showToast('状态更新失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

const deleteMaskingRule = (id: number) => {
  dialog.value = {
    show: true,
    title: '确认删除',
    message: '您确定要删除这条脱敏规则吗？删除后相关字段将明文显示。',
    type: 'danger',
    onConfirm: async () => {
      dialog.value.show = false
      try {
        await axios.delete(`/api/portal/system/masking/rules/${id}`)
        showToast('规则已删除', 'success')
        await fetchMaskingConfig()
      } catch (e) {
        showToast('删除失败', 'error')
      }
    }
  }
}

const getMaskPreview = (type: string) => {
  const mockValues: any = {
    'PARTIAL_3_4': '138****8000',
    'PARTIAL_4': '*******1234',
    'EMAIL': 'a***@example.com',
    'FULL': '******'
  }
  return mockValues[type] || '******'
}

// AI Config State
const aiConfig = ref({
  enabled: 'false',
  provider: 'openai',
  base_url: '',
  api_key: '',
  model: '',
  embed_model: '',
  embed_base_url: '',
  embed_api_key: '',
  rerank_model: '',
  rerank_base_url: '',
  rerank_api_key: ''
})

// Rate Limit Config State
const rlConfig = ref({
  enabled: 'true',
  admin_limit: 1000,
  user_limit: 100
})

const peakData = ref<any[]>([])
const chartOptions = ref<any>(null)

// Retention State
const retentionConfig = ref({
  raw_logs: 7,
  stats: 90
})

// Dialog State
const dialog = ref({
  show: false,
  title: '',
  message: '',
  type: 'info' as 'danger' | 'warning' | 'info',
  onConfirm: () => {}
})

const { showToast } = useToast()

const fetchAiConfig = async () => {
  loading.value.ai_load = true
  try {
    const res = await axios.get('/api/portal/system/config/ai')
    aiConfig.value = res.data
  } catch (e: any) {
    showToast('AI 配置加载失败: ' + e.message, 'error')
  } finally {
    loading.value.ai_load = false
  }
}

const saveAiConfig = async () => {
  loading.value.ai_save = true
  try {
    await axios.post('/api/portal/system/config/ai', { configs: aiConfig.value })
    showToast('AI 配置已保存', 'success')
    await fetchAiConfig() // Re-fetch to show masked key
  } catch (e: any) {
    showToast('保存失败: ' + e.message, 'error')
  } finally {
    loading.value.ai_save = false
  }
}

const testAiConnection = async () => {
  loading.value.ai_test = true
  try {
    const res = await axios.post('/api/portal/system/config/ai/test', { configs: aiConfig.value })
    if (res.data.success) {
      showToast('连接测试成功！', 'success')
    }
  } catch (e: any) {
    const detail = e.response?.data?.detail || e.message
    showToast('测试失败: ' + detail, 'error')
  } finally {
    loading.value.ai_test = false
  }
}

const fetchRateLimitConfig = async () => {
  loading.value.rl_load = true
  try {
    const res = await axios.get('/api/portal/system/config')
    rlConfig.value.enabled = res.data['ratelimit.enabled'] || 'true'
    rlConfig.value.admin_limit = parseInt(res.data['ratelimit.admin.limit'] || '1000')
    rlConfig.value.user_limit = parseInt(res.data['ratelimit.user.limit'] || '100')
  } catch (e: any) {
    showToast('流控配置加载失败: ' + e.message, 'error')
  } finally {
    loading.value.rl_load = false
  }
}

const saveRateLimitConfig = async () => {
  loading.value.rl_save = true
  try {
    await axios.post('/api/portal/system/config', {
      'ratelimit.enabled': rlConfig.value.enabled,
      'ratelimit.admin.limit': rlConfig.value.admin_limit.toString(),
      'ratelimit.user.limit': rlConfig.value.user_limit.toString()
    })
    showToast('流控配置已更新', 'success')
    renderChart()
  } catch (e: any) {
    showToast('流控配置保存失败', 'error')
  } finally {
    loading.value.rl_save = false
  }
}

const fetchPeakData = async () => {
  loading.value.rl_peak = true
  try {
    const res = await axios.get('/api/portal/dashboard/api-peak-24h')
    peakData.value = res.data
    renderChart()
  } catch (e: any) {
    console.error("Failed to fetch peak data", e)
  } finally {
    loading.value.rl_peak = false
  }
}

const renderChart = () => {
  const hours = peakData.value.map(d => d.hour)
  const peaks = peakData.value.map(d => d.peak)
  
  chartOptions.value = {
    title: {
      text: '最近 24 小时每分钟请求峰值',
      left: 'center',
      textStyle: { fontSize: 14, color: '#374151' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const p = params[0]
        return `${p.name}<br/>分钟峰值: <span style="font-weight:bold;color:#ef4444">${p.value}</span> 次/分`
      }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: hours,
      axisLabel: { color: '#9ca3af', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      name: '请求数/分',
      splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } }
    },
    series: [
      {
        name: '峰值',
        type: 'bar',
        data: peaks,
        itemStyle: {
          color: (params: any) => {
            const val = params.value
            if (val > rlConfig.value.user_limit) return '#ef4444'
            return '#6366f1'
          },
          borderRadius: [4, 4, 0, 0]
        },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { position: 'end', fontSize: 10 },
          data: [
            { yAxis: rlConfig.value.user_limit, name: '用户限流', lineStyle: { color: '#f59e0b', type: 'dashed' } },
            { yAxis: rlConfig.value.admin_limit, name: '管理员限流', lineStyle: { color: '#dc2626' } }
          ]
        }
      }
    ]
  }
}

const fetchConfig = async () => {
  try {
    const res = await axios.get('/api/portal/system/config')
    retentionConfig.value.raw_logs = parseInt(res.data['log.retention.raw_days'] || '7')
    retentionConfig.value.stats = parseInt(res.data['log.retention.stats_days'] || '90')
  } catch (e) {
    console.error("Failed to fetch config", e)
  }
}

const saveConfig = async () => {
  loading.value.save_config = true
  try {
    await axios.post('/api/portal/system/config', {
      'log.retention.raw_days': retentionConfig.value.raw_logs.toString(),
      'log.retention.stats_days': retentionConfig.value.stats.toString()
    })
    showToast('系统配置已保存', 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    loading.value.save_config = false
  }
}

const fetchMaintenanceLogs = async () => {
  loading.value.m_logs = true
  try {
    const res = await axios.get('/api/portal/system/logs/maintenance')
    maintenanceLogs.value = res.data
  } catch (e) {
    console.error("Failed to fetch maintenance logs", e)
  } finally {
    loading.value.m_logs = false
  }
}

const fetchShardLogs = async () => {
  loading.value.shard_logs = true
  try {
    const res = await axios.get('/api/portal/system/logs/shards')
    shardLogs.value = res.data
  } catch (e) {
    console.error("Failed to fetch shard logs", e)
  } finally {
    loading.value.shard_logs = false
  }
}

const triggerPurge = () => {
  dialog.value = {
    show: true,
    title: '确认清理',
    message: `您确定要手动清理 ${retentionConfig.value.raw_logs} 天前的原始日志吗？此操作不可撤销。`,
    type: 'danger',
    onConfirm: async () => {
      dialog.value.show = false
      loading.value.log_purge = true
      try {
        await axios.post('/api/portal/system/logs/purge', { days: retentionConfig.value.raw_logs })
        showToast('清理任务已在后台启动', 'success')
        fetchMaintenanceLogs() // 立即刷新
        setTimeout(fetchMaintenanceLogs, 2000) // 延迟刷新日志
      } catch (e: any) {
        showToast(e.response?.data?.detail || '触发失败', 'error')
      } finally {
        loading.value.log_purge = false
      }
    }
  }
}

const triggerAggregation = () => {
  dialog.value = {
    show: true,
    title: '确认聚合',
    message: '您确定要重新聚合过去 7 天的数据吗？这将覆盖统计表中的现有记录。',
    type: 'warning',
    onConfirm: async () => {
      dialog.value.show = false
      loading.value.log_aggregate = true
      try {
        await axios.post('/api/portal/system/logs/aggregate', { days: 7 })
        showToast('聚合任务已在后台启动', 'success')
        fetchMaintenanceLogs() // 立即刷新
        setTimeout(fetchMaintenanceLogs, 2000)
      } catch (e: any) {
        showToast(e.response?.data?.detail || '触发失败', 'error')
      } finally {
        loading.value.log_aggregate = false
      }
    }
  }
}

const results = ref<{ [key: string]: 'success' | 'failed' | null }> ({ redis: null, vector: null })
interface PoolStatus { source_id: number; source_name: string; source_type: string; status: string; active: number; free: number; max: number; health: 'healthy' | 'unhealthy' | 'unknown'; health_msg?: string }
const pools = ref<PoolStatus[]>([])
const appendLog = (msg: string) => { const timestamp = new Date().toLocaleTimeString(); logs.value.push(`[${timestamp}] ${msg}`) }
const clearLogs = () => { logs.value = [] }

const testConnection = async (component: string) => {
  loading.value[component] = true; results.value[component] = null; appendLog(`>>> 开始测试 ${component} 连接...`)
  try {
    const res = await axios.post(`/api/portal/system/test-connection/${component}`)
    if (res.data.logs) res.data.logs.forEach((l: string) => appendLog(l))
    results.value[component] = res.data.status === 'success' ? 'success' : 'failed'
    showToast(res.data.message, results.value[component] as any)
  } catch (e: any) { results.value[component] = 'failed'; appendLog(`>>> ❌ 异常: ${e.message}`) } finally { loading.value[component] = false }
}

const scanRedisKeys = async () => {
  loading.value['redis_scan'] = true; appendLog('>>> 开始扫描 Redis Keys...')
  try {
     const res = await axios.post('/api/portal/system/redis/keys')
     appendLog(`>>> 📊 总数: ${res.data.count}`)
     res.data.keys.forEach((k: string, i: number) => appendLog(`${i+1}. ${k}`))
     showToast('扫描成功', 'success')
  } catch (e: any) { showToast('扫描失败', 'error') } finally { loading.value['redis_scan'] = false }
}

const fetchPools = async () => {
  loading.value['pools_fetch'] = true
  try {
    const dsRes = await axios.get('/api/portal/datasource/datasources')
    const poolList: PoolStatus[] = []
    await Promise.all(dsRes.data.map(async (ds: any) => {
      try {
        const pRes = await axios.get(`/api/portal/pool/status?source_id=${ds.id}`)
        let health: 'healthy' | 'unhealthy' | 'unknown' = 'unknown'
        if (pRes.data.status === 'not_initialized') {
          health = 'unknown'
        }
        poolList.push({ 
          source_id: ds.id, 
          source_name: ds.source_name, 
          source_type: ds.source_type, 
          status: pRes.data.status, 
          active: pRes.data.active, 
          free: pRes.data.free, 
          max: pRes.data.max, 
          health 
        })
      } catch (e) { 
        poolList.push({ 
          source_id: ds.id, 
          source_name: ds.source_name, 
          source_type: ds.source_type, 
          status: 'error', 
          active: 0, 
          free: 0, 
          max: 0, 
          health: 'unhealthy' 
        }) 
      }
    }))
    pools.value = poolList.sort((a, b) => a.source_id - b.source_id)
  } finally { loading.value['pools_fetch'] = false }
}

const checkAllHealth = async () => {
  loading.value['pools_health'] = true
  try {
    const res = await axios.post('/api/portal/pool/health/check')
    const healthResults = res.data || {}
    
    pools.value.forEach(p => {
      const status = healthResults[p.source_id.toString()] || healthResults[p.source_id]
      if (status === 'healthy') {
        p.health = 'healthy'
      } else if (status && status.startsWith('unhealthy')) {
        p.health = 'unhealthy'
      } else {
        p.health = 'unknown'
      }
    })
    showToast('体检完成', 'success')
  } catch (e) {
    showToast('体检执行失败', 'error')
  } finally {
    loading.value['pools_health'] = false
  }
}

const userInfo = ref<any>(null)
const loadUserInfo = () => {
  const info = localStorage.getItem('user_info')
  if (info) userInfo.value = JSON.parse(info)
}
const hasPerm = (code: string) => {
  if (userInfo.value?.role === 'admin') return true
  return userInfo.value?.permissions?.elements?.includes(code)
}

onMounted(() => {
  loadUserInfo()
  fetchConfig()
  fetchAiConfig()
  fetchRateLimitConfig()
  fetchPeakData()
  fetchMaintenanceLogs()
  fetchMaskingConfig()
})


const switchTab = (tab: 'monitor' | 'ratelimit' | 'diagnostic' | 'pools' | 'logs' | 'ai' | 'masking' | 'platform') => {
  activeTab.value = tab
  if (tab === 'pools' && pools.value.length === 0) fetchPools()
  if (tab === 'logs') fetchMaintenanceLogs()
  if (tab === 'ai') fetchAiConfig()
  if (tab === 'masking') fetchMaskingConfig()
  if (tab === 'platform') fetchPlatformSettings()
  if (tab === 'ratelimit') {
    fetchRateLimitConfig()
    fetchPeakData()
  }
}

const formatDateTime = (val: string) => {
  if (!val) return '-'
  return new Date(val).toLocaleString()
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <h1 class="text-lg sm:text-2xl font-semibold text-gray-900">系统配置与诊断</h1>
    </div>

    <!-- Mobile: tab selector -->
    <div class="lg:hidden">
      <label for="settings-tab-select" class="sr-only">设置分区</label>
      <select
        id="settings-tab-select"
        :value="activeTab"
        class="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm font-medium text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
        @change="onMobileTabChange"
      >
        <option v-for="tab in settingsTabs" :key="tab.id" :value="tab.id">
          {{ tab.label }}
        </option>
      </select>
    </div>

    <!-- Desktop: tabs -->
    <div class="hidden lg:block border-b border-gray-200">
      <nav class="-mb-px flex space-x-6 overflow-x-auto custom-scrollbar" aria-label="Tabs">
        <button @click="switchTab('monitor')" :class="[activeTab === 'monitor' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center shrink-0']">
          <BoltIcon class="h-5 w-5 mr-2" /> 系统监控
        </button>
        <button @click="switchTab('ratelimit')" :class="[activeTab === 'ratelimit' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center shrink-0']">
          <AdjustmentsHorizontalIcon class="h-5 w-5 mr-2" /> 流控设置
        </button>
        <button @click="switchTab('diagnostic')" :class="[activeTab === 'diagnostic' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center shrink-0']">
          <CommandLineIcon class="h-5 w-5 mr-2" /> 系统诊断
        </button>
        <button @click="switchTab('pools')" :class="[activeTab === 'pools' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center shrink-0']">
          <ServerIcon class="h-5 w-5 mr-2" /> 连接池监控
        </button>
        <button @click="switchTab('logs')" :class="[activeTab === 'logs' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center shrink-0']">
          <ClockIcon class="h-5 w-5 mr-2" /> 日志管理
        </button>
        <button @click="switchTab('ai')" :class="[activeTab === 'ai' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center shrink-0']">
          <SparklesIcon class="h-5 w-5 mr-2" /> AI 模型
        </button>
        <button @click="switchTab('masking')" :class="[activeTab === 'masking' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center shrink-0']">
          <ShieldCheckIcon class="h-5 w-5 mr-2" /> 数据脱敏
        </button>
        <button @click="switchTab('platform')" :class="[activeTab === 'platform' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center shrink-0']">
          <CircleStackIcon class="h-5 w-5 mr-2" /> 系统配置
        </button>
      </nav>
    </div>

    <!-- Tab Content: Monitor -->
    <div v-if="activeTab === 'monitor'" class="min-h-[500px]">
      <SystemMonitor />
    </div>

    <!-- Tab Content: Rate Limit -->
    <div v-show="activeTab === 'ratelimit'" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Configuration Card -->
        <div class="lg:col-span-1 bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
          <div class="p-6 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
            <div class="flex items-center">
              <div class="p-2 bg-indigo-100 rounded-lg mr-4">
                <AdjustmentsHorizontalIcon class="w-6 h-6 text-indigo-600" />
              </div>
              <h3 class="text-lg font-bold text-gray-900">全局流控策略</h3>
            </div>
            <label class="inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="rlConfig.enabled" true-value="true" false-value="false" class="sr-only peer">
              <div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
            </label>
          </div>
          
          <div class="p-6 space-y-6">
            <div>
              <label class="block text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                👑 管理员默认限流 (次/分)
              </label>
              <input v-model.number="rlConfig.admin_limit" type="number" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
              <p class="mt-1 text-xs text-gray-400">针对角色为 admin 的用户，除非用户单独设置。</p>
            </div>
            
            <div>
              <label class="block text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                👤 普通用户默认限流 (次/分)
              </label>
              <input v-model.number="rlConfig.user_limit" type="number" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
              <p class="mt-1 text-xs text-gray-400">针对角色为 user 的用户。</p>
            </div>

            <div class="pt-4">
              <button 
                @click="saveRateLimitConfig"
                :disabled="loading.rl_save"
                class="w-full inline-flex justify-center items-center px-6 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 shadow-sm disabled:opacity-50 transition-colors"
              >
                <ArrowPathIcon v-if="loading.rl_save" class="animate-spin -ml-1 mr-2 h-4 w-4" />
                保存配置
              </button>
            </div>
          </div>
        </div>

        <!-- Peak Analysis Chart -->
        <div class="lg:col-span-2 bg-white rounded-lg shadow border border-gray-200 p-6">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-lg font-bold text-gray-900 flex items-center">
              <ChartBarIcon class="w-6 h-6 text-indigo-500 mr-2" />
              历史峰值分析
            </h3>
            <button @click="fetchPeakData" class="text-gray-400 hover:text-indigo-600">
              <ArrowPathIcon class="h-5 w-5" :class="{'animate-spin': loading.rl_peak}" />
            </button>
          </div>
          
          <div class="h-[350px]">
            <v-chart v-if="chartOptions" class="w-full h-full" :option="chartOptions" autoresize />
            <div v-else-if="loading.rl_peak" class="w-full h-full flex items-center justify-center">
               <span class="text-gray-400 animate-pulse">正在加载统计数据...</span>
            </div>
            <div v-else class="w-full h-full flex items-center justify-center text-gray-400">
               暂无统计数据
            </div>
          </div>
          
          <div class="mt-4 p-4 bg-blue-50 rounded-lg">
            <p class="text-xs text-blue-700 leading-relaxed">
              <strong>💡 设置建议：</strong> 参考上方柱状图。
              蓝色表示请求量在正常范围内，<span class="text-red-600 font-bold">红色</span> 表示超过了当前的“普通用户”限流阈值。
              建议将限流值设为日常最高峰值的 1.5 - 2 倍，以应对正常的业务波动。
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab Content: AI Config -->
    <div v-show="activeTab === 'ai'" class="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
      <div class="p-6 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
        <div class="flex items-center">
          <div class="p-2 bg-blue-100 rounded-lg mr-4">
            <CpuChipIcon class="w-6 h-6 text-blue-600" />
          </div>
          <div>
            <h3 class="text-lg font-bold text-gray-900">AI 模型集成</h3>
            <p class="text-xs text-gray-500">配置 OpenAI 兼容的大模型服务，为 SQL 实验室提供智能辅助。</p>
          </div>
        </div>
        <div class="flex items-center">
          <label class="inline-flex items-center cursor-pointer">
            <input type="checkbox" v-model="aiConfig.enabled" true-value="true" false-value="false" class="sr-only peer">
            <div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            <span class="ms-3 text-sm font-medium text-gray-700">{{ aiConfig.enabled === 'true' ? '已启用' : '已禁用' }}</span>
          </label>
        </div>
      </div>

      <div class="p-6 space-y-10">
        <div v-if="loading.ai_load" class="py-10 flex justify-center">
          <svg class="animate-spin h-8 w-8 text-blue-500" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </div>

        <div v-else class="space-y-12">
          <!-- 1. Chat Model Section -->
          <section class="space-y-6">
            <div class="flex items-center gap-3 border-b border-gray-100 pb-2">
              <span class="text-xl">💬</span>
              <h4 class="text-sm font-bold text-gray-900 uppercase tracking-wider">对话模型 (Chat Model)</h4>
              <Tooltip text="核心对话与逻辑推理模型，负责 SQL 生成与多轮对话分析。" position="top">
                <QuestionMarkCircleIcon class="w-4 h-4 text-gray-400 cursor-help" />
              </Tooltip>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">模型名称</label>
                <input v-model="aiConfig.model" type="text" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm" placeholder="gpt-4o">
              </div>
              <div class="md:col-span-2">
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">API 基础地址 (Base URL)</label>
                <input v-model="aiConfig.base_url" type="text" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono" placeholder="https://api.openai.com/v1">
              </div>
              <div class="md:col-span-3">
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">API 密钥 (API Key)</label>
                <input v-model="aiConfig.api_key" type="password" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono" placeholder="sk-...">
              </div>
            </div>
          </section>

          <!-- 2. Embedding Model Section -->
          <section class="space-y-6">
            <div class="flex items-center gap-3 border-b border-gray-100 pb-2">
              <span class="text-xl">🔤</span>
              <h4 class="text-sm font-bold text-gray-900 uppercase tracking-wider">嵌入模型 (Embedding Model)</h4>
              <Tooltip text="用于将业务描述转化为向量，是语义检索（RAG）召回的基础。" position="top">
                <QuestionMarkCircleIcon class="w-4 h-4 text-gray-400 cursor-help" />
              </Tooltip>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">模型名称</label>
                <input v-model="aiConfig.embed_model" type="text" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm" placeholder="text-embedding-3-small">
              </div>
              <div class="md:col-span-2">
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">API 基础地址 (Base URL)</label>
                <input v-model="aiConfig.embed_base_url" type="text" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono" placeholder="https://api.openai.com/v1">
              </div>
              <div class="md:col-span-3">
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">API 密钥 (API Key)</label>
                <input v-model="aiConfig.embed_api_key" type="password" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono" placeholder="sk-...">
              </div>
            </div>
          </section>

          <!-- 3. Rerank Model Section -->
          <section class="space-y-6">
            <div class="flex items-center gap-3 border-b border-gray-100 pb-2">
              <span class="text-xl">🎯</span>
              <h4 class="text-sm font-bold text-gray-900 uppercase tracking-wider">重排模型 (Rerank Model)</h4>
              <Tooltip text="对检索初步召回的结果进行深度精排，显著提升 RAG 的问答准确率。" position="top">
                <QuestionMarkCircleIcon class="w-4 h-4 text-gray-400 cursor-help" />
              </Tooltip>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">模型名称</label>
                <input v-model="aiConfig.rerank_model" type="text" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm" placeholder="bge-reranker-v2-m3">
              </div>
              <div class="md:col-span-2">
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">API 基础地址 (Base URL)</label>
                <input v-model="aiConfig.rerank_base_url" type="text" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono" placeholder="https://api.siliconflow.cn/v1">
              </div>
              <div class="md:col-span-3">
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-2">API 密钥 (API Key)</label>
                <input v-model="aiConfig.rerank_api_key" type="password" class="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono" placeholder="sk-...">
              </div>
            </div>
          </section>
        </div>
      </div>

      <div class="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
        <button 
          @click="testAiConnection"
          :disabled="loading.ai_test || loading.ai_save"
          class="inline-flex items-center px-4 py-2 border border-blue-200 text-sm font-medium rounded-md text-blue-700 bg-white hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
          <svg v-if="loading.ai_test" class="animate-spin -ml-1 mr-2 h-4 w-4 text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ loading.ai_test ? '正在连接...' : '连通性测试' }}
        </button>

        <button 
          @click="saveAiConfig"
          :disabled="loading.ai_save || loading.ai_test"
          class="inline-flex items-center px-6 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 shadow-sm disabled:opacity-50 transition-colors"
        >
          <span v-if="loading.ai_save">保存中...</span>
          <span v-else>保存配置</span>
        </button>
      </div>
    </div>

    <!-- Tab Content: Platform Settings -->
    <div v-show="activeTab === 'platform'" class="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
      <div class="p-6 border-b border-gray-100">
        <h3 class="text-lg font-bold text-gray-900">系统配置</h3>
        <p class="text-sm text-gray-500 mt-1">管理平台业务相关配置，可按模块分别保存。</p>
      </div>

      <div v-if="loading.platform_load" class="p-12 text-center text-gray-400">加载中...</div>

      <div v-else class="flex flex-col lg:flex-row">
        <nav class="lg:w-52 shrink-0 border-b lg:border-b-0 lg:border-r border-gray-100 p-4 space-y-1">
          <button
            v-for="section in platformSections"
            :key="section.id"
            type="button"
            class="w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="platformSection === section.id ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-50'"
            @click="platformSection = section.id"
          >
            {{ section.label }}
          </button>
        </nav>

        <div class="flex-1 p-6 space-y-6">
          <!-- 数据产品目录 -->
          <div v-show="platformSection === 'catalog'" class="space-y-6">
            <div>
              <h4 class="text-base font-semibold text-gray-900">数据产品目录</h4>
              <p class="text-sm text-gray-500 mt-1">配置从资源发布到目录时的默认负责人策略与 API 变更提醒。</p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">默认负责人策略</label>
              <select
                v-model="catalogConfig.default_owner_strategy"
                class="w-full max-w-md border border-gray-200 rounded-lg px-3 py-2 text-sm"
              >
                <option value="publisher">发布人（当前操作者）</option>
                <option value="group_owner">按业务域映射（见下表）</option>
                <option value="none">不自动指定</option>
              </select>
              <p class="text-xs text-gray-400 mt-2">
                从「接口管理」发布资源到目录时，自动写入产品负责人。选「按业务域映射」时需配置下表。
              </p>
            </div>

            <div v-if="catalogConfig.default_owner_strategy === 'group_owner'" class="space-y-3">
              <div class="flex items-center justify-between">
                <label class="text-sm font-medium text-gray-700">业务域 → 负责人</label>
                <button type="button" class="text-sm text-indigo-600 hover:text-indigo-800" @click="addGroupOwnerRow">
                  + 添加映射
                </button>
              </div>
              <div v-if="!catalogConfig.group_owner_rows.length" class="text-sm text-gray-400 bg-gray-50 rounded-lg p-4">
                暂无映射，请点击「添加映射」
              </div>
              <div
                v-for="(row, idx) in catalogConfig.group_owner_rows"
                :key="idx"
                class="flex flex-wrap gap-2 items-center"
              >
                <input
                  v-model="row.group"
                  placeholder="业务域名称（与 resource_group 一致）"
                  class="flex-1 min-w-[180px] border border-gray-200 rounded-lg px-3 py-2 text-sm"
                />
                <select v-model="row.user_id" class="flex-1 min-w-[180px] border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option :value="null">选择负责人</option>
                  <option v-for="u in catalogUsers" :key="u.id" :value="u.id">
                    {{ u.user_name }}{{ u.remark ? ` (${u.remark})` : '' }}
                  </option>
                </select>
                <button type="button" class="text-sm text-red-600 hover:text-red-800 px-2" @click="removeGroupOwnerRow(idx)">
                  删除
                </button>
              </div>
            </div>

            <div class="border-t border-gray-100 pt-6 space-y-4">
              <div>
                <h5 class="text-sm font-semibold text-gray-900">API 变更通知</h5>
                <p class="text-xs text-gray-400 mt-1">
                  关联 API 被他人更新或回滚时，向产品负责人写入站内提醒；可选 Webhook 推送 JSON 事件。
                </p>
              </div>
              <label class="inline-flex items-center gap-3 cursor-pointer">
                <input
                  v-model="catalogConfig.notify_resource_change_enabled"
                  type="checkbox"
                  class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span class="text-sm text-gray-700">启用站内变更提醒</span>
              </label>
              <fieldset
                :disabled="!catalogConfig.notify_resource_change_enabled"
                class="border-0 p-0 m-0 min-w-0 disabled:opacity-50"
              >
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">变更 Webhook URL（可选）</label>
                  <input
                    v-model="catalogConfig.notify_resource_change_webhook_url"
                    type="url"
                    placeholder="https://..."
                    class="w-full max-w-xl border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono disabled:bg-gray-50 disabled:cursor-not-allowed"
                  />
                  <p class="text-xs text-gray-400 mt-1">留空则仅站内提醒，不推送 Webhook。</p>
                </div>
              </fieldset>
            </div>

            <div>
              <button
                :disabled="loading.platform_save"
                class="inline-flex items-center px-6 py-2 text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                @click="saveCatalogPlatformConfig"
              >
                {{ loading.platform_save ? '保存中...' : '保存目录配置' }}
              </button>
            </div>
          </div>

          <!-- 钉钉通知 -->
          <div v-show="platformSection === 'dingtalk'" class="space-y-6">
            <div>
              <h4 class="text-base font-semibold text-gray-900">钉钉通知</h4>
              <p class="text-sm text-gray-500 mt-1">
                目录权限申请与审批结果推送至钉钉群机器人，便于负责人及时处理。
              </p>
            </div>

            <label class="inline-flex items-center gap-3 cursor-pointer">
              <input
                v-model="dingtalkConfig.enabled"
                type="checkbox"
                class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span class="text-sm text-gray-700">启用钉钉审批通知</span>
            </label>

            <fieldset
              :disabled="!dingtalkConfig.enabled"
              class="space-y-6 border-0 p-0 m-0 min-w-0 disabled:opacity-50"
            >
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Webhook 地址</label>
                <input
                  v-model="dingtalkConfig.webhook_url"
                  type="url"
                  placeholder="https://oapi.dingtalk.com/robot/send?access_token=..."
                  class="w-full max-w-xl border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono disabled:bg-gray-50 disabled:cursor-not-allowed"
                />
                <p class="text-xs text-gray-400 mt-1">钉钉群 → 智能群助手 → 添加机器人 → 自定义 → 复制 Webhook 地址。</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">加签密钥（可选）</label>
                <input
                  v-model="dingtalkConfig.secret"
                  type="password"
                  placeholder="SEC..."
                  class="w-full max-w-xl border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono disabled:bg-gray-50 disabled:cursor-not-allowed"
                />
                <p class="text-xs text-gray-400 mt-1">若机器人启用了「加签」安全设置，请填写 SEC 开头的密钥。</p>
              </div>

              <div class="space-y-3 rounded-lg border border-gray-100 bg-gray-50 p-4 disabled:bg-gray-50">
                <p class="text-sm font-medium text-gray-700">推送场景</p>
                <label
                  class="flex items-center gap-3"
                  :class="dingtalkConfig.enabled ? 'cursor-pointer' : 'cursor-not-allowed'"
                >
                  <input
                    v-model="dingtalkConfig.notify_on_request"
                    type="checkbox"
                    class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed"
                  />
                  <span class="text-sm text-gray-700">用户提交目录权限申请时</span>
                </label>
                <label
                  class="flex items-center gap-3"
                  :class="dingtalkConfig.enabled ? 'cursor-pointer' : 'cursor-not-allowed'"
                >
                  <input
                    v-model="dingtalkConfig.notify_on_result"
                    type="checkbox"
                    class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed"
                  />
                  <span class="text-sm text-gray-700">审批通过或拒绝时</span>
                </label>
              </div>

              <div class="flex flex-wrap gap-3">
                <button
                  type="button"
                  :disabled="loading.dingtalk_test || loading.dingtalk_save || !dingtalkConfig.enabled"
                  class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md border border-indigo-200 text-indigo-700 bg-white hover:bg-indigo-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  @click="testDingtalkNotification"
                >
                  {{ loading.dingtalk_test ? '发送中...' : '发送测试消息' }}
                </button>
              </div>
            </fieldset>

            <div>
              <button
                type="button"
                :disabled="loading.dingtalk_save"
                class="inline-flex items-center px-6 py-2 text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                @click="saveDingtalkPlatformConfig"
              >
                {{ loading.dingtalk_save ? '保存中...' : '保存钉钉配置' }}
              </button>
            </div>
          </div>

          <!-- 企微通知 -->
          <div v-show="platformSection === 'wecom'" class="space-y-6">
            <div>
              <h4 class="text-base font-semibold text-gray-900">企业微信通知</h4>
              <p class="text-sm text-gray-500 mt-1">
                目录权限申请与审批结果推送至企业微信群机器人，可与钉钉并行启用。
              </p>
            </div>

            <label class="inline-flex items-center gap-3 cursor-pointer">
              <input
                v-model="wecomConfig.enabled"
                type="checkbox"
                class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span class="text-sm text-gray-700">启用企微审批通知</span>
            </label>

            <fieldset
              :disabled="!wecomConfig.enabled"
              class="space-y-6 border-0 p-0 m-0 min-w-0 disabled:opacity-50"
            >
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Webhook 地址</label>
                <input
                  v-model="wecomConfig.webhook_url"
                  type="url"
                  placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
                  class="w-full max-w-xl border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono disabled:bg-gray-50 disabled:cursor-not-allowed"
                />
                <p class="text-xs text-gray-400 mt-1">企微群 → 群机器人 → 添加 → 复制 Webhook 地址。</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">加签密钥（可选）</label>
                <input
                  v-model="wecomConfig.secret"
                  type="password"
                  placeholder="机器人安全设置中的密钥"
                  class="w-full max-w-xl border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono disabled:bg-gray-50 disabled:cursor-not-allowed"
                />
                <p class="text-xs text-gray-400 mt-1">若机器人启用了「加签」安全设置，请填写密钥。</p>
              </div>

              <div class="space-y-3 rounded-lg border border-gray-100 bg-gray-50 p-4 disabled:bg-gray-50">
                <p class="text-sm font-medium text-gray-700">推送场景</p>
                <label
                  class="flex items-center gap-3"
                  :class="wecomConfig.enabled ? 'cursor-pointer' : 'cursor-not-allowed'"
                >
                  <input
                    v-model="wecomConfig.notify_on_request"
                    type="checkbox"
                    class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed"
                  />
                  <span class="text-sm text-gray-700">用户提交目录权限申请时</span>
                </label>
                <label
                  class="flex items-center gap-3"
                  :class="wecomConfig.enabled ? 'cursor-pointer' : 'cursor-not-allowed'"
                >
                  <input
                    v-model="wecomConfig.notify_on_result"
                    type="checkbox"
                    class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:cursor-not-allowed"
                  />
                  <span class="text-sm text-gray-700">审批通过或拒绝时</span>
                </label>
              </div>

              <div class="flex flex-wrap gap-3">
                <button
                  type="button"
                  :disabled="loading.wecom_test || loading.wecom_save || !wecomConfig.enabled"
                  class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md border border-indigo-200 text-indigo-700 bg-white hover:bg-indigo-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  @click="testWecomNotification"
                >
                  {{ loading.wecom_test ? '发送中...' : '发送测试消息' }}
                </button>
              </div>
            </fieldset>

            <div>
              <button
                type="button"
                :disabled="loading.wecom_save"
                class="inline-flex items-center px-6 py-2 text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                @click="saveWecomPlatformConfig"
              >
                {{ loading.wecom_save ? '保存中...' : '保存企微配置' }}
              </button>
            </div>
          </div>

          <!-- MCP 服务 -->
          <div v-show="platformSection === 'mcp'" class="space-y-6">
            <div>
              <h4 class="text-base font-semibold text-gray-900">MCP Server</h4>
              <p class="text-sm text-gray-500 mt-1">
                开关与 Agent 提示在下方维护；SSE 地址自动生成。客户端使用个人 API Key，与调用 Data API 相同（SSE 用 headers，stdio 用 env）。
              </p>
            </div>

            <label class="inline-flex items-center gap-3 cursor-pointer">
              <input
                v-model="mcpConfig.enabled"
                type="checkbox"
                class="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span class="text-sm font-medium text-gray-800">启用 MCP Server</span>
            </label>

            <fieldset :disabled="!mcpConfig.enabled" class="space-y-4 border border-gray-100 rounded-xl p-4 disabled:opacity-60">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Agent 提示文案 (instructions)</label>
                <textarea
                  v-model="mcpConfig.instructions"
                  rows="4"
                  class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                  placeholder="描述 MCP 工具使用顺序与注意事项..."
                />
              </div>

              <div class="bg-gray-50 rounded-lg p-4 text-xs text-gray-600 space-y-2">
                <div v-if="mcpConfig.sse_url" class="flex items-start gap-2">
                  <span class="text-gray-400 shrink-0">SSE 完整地址：</span>
                  <code class="font-mono text-indigo-700 break-all flex-1">{{ mcpConfig.sse_url }}</code>
                  <button
                    type="button"
                    class="shrink-0 px-2 py-1 text-xs rounded border border-indigo-200 text-indigo-700 bg-white hover:bg-indigo-50"
                    title="复制 SSE 地址"
                    @click="copyMcpSseUrl"
                  >
                    复制
                  </button>
                </div>
                <p v-else class="text-gray-400">SSE 地址将在加载配置后根据当前访问地址生成</p>
                <div class="pt-2 border-t border-gray-200">
                  <div class="flex items-center justify-between gap-2 mb-1">
                    <span class="text-gray-400">Cursor SSE 配置示例</span>
                    <button
                      type="button"
                      class="shrink-0 px-2 py-1 text-xs rounded border border-indigo-200 text-indigo-700 bg-white hover:bg-indigo-50"
                      @click="copyMcpSseCursorConfig"
                    >
                      复制配置
                    </button>
                  </div>
                  <pre class="bg-white rounded p-2 overflow-x-auto text-[11px] leading-relaxed font-mono text-gray-700">{{ mcpSseCursorExample }}</pre>
                </div>
                <p><span class="text-gray-400">stdio 启动：</span><code class="font-mono">{{ mcpConfig.stdio_command }}</code></p>
                <p class="text-gray-500 pt-2 leading-relaxed">
                  远程客户端推荐 SSE：复制上方配置，将 <code class="bg-white px-1 rounded">X-API-Key</code> 换成个人 Key（与门户「我的 API Key」相同）。
                  本机开发可用 stdio，在 <code class="bg-white px-1 rounded">env</code> 中配置 <code class="bg-white px-1 rounded">YUNSHU_API_KEY</code> 与 <code class="bg-white px-1 rounded">YUNSHU_BASE_URL</code>。
                </p>
              </div>
            </fieldset>

            <div
              v-if="mcpTestResult"
              class="rounded-xl border p-4 space-y-2"
              :class="mcpTestResult.success ? 'border-green-200 bg-green-50' : 'border-amber-200 bg-amber-50'"
            >
              <p class="text-sm font-medium" :class="mcpTestResult.success ? 'text-green-800' : 'text-amber-800'">
                {{ mcpTestResult.success ? '测试通过' : '部分检查未通过' }}
                <span v-if="mcpTestResult.tools.length" class="font-normal text-gray-600">
                  — 工具：{{ mcpTestResult.tools.join('、') }}
                </span>
              </p>
              <ul class="space-y-1">
                <li
                  v-for="(item, idx) in mcpTestResult.checks"
                  :key="idx"
                  class="text-xs flex items-start gap-2"
                >
                  <span :class="item.ok ? 'text-green-600' : 'text-red-600'">{{ item.ok ? '✓' : '✗' }}</span>
                  <span class="text-gray-700">
                    <span class="font-medium">{{ item.name }}：</span>{{ item.detail }}
                  </span>
                </li>
              </ul>
            </div>

            <div class="flex flex-wrap gap-3">
              <button
                type="button"
                :disabled="loading.mcp_test || loading.mcp_save || !mcpConfig.enabled"
                class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md border border-indigo-200 text-indigo-700 bg-white hover:bg-indigo-50 disabled:opacity-50 disabled:cursor-not-allowed"
                @click="testMcpServer"
              >
                {{ loading.mcp_test ? '测试中...' : '连通性测试' }}
              </button>
              <button
                type="button"
                :disabled="loading.mcp_save || loading.mcp_test"
                class="inline-flex items-center px-6 py-2 text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                @click="saveMcpPlatformConfig"
              >
                {{ loading.mcp_save ? '保存中...' : '保存 MCP 配置' }}
              </button>
            </div>
          </div>

          <div v-show="platformSection === 'branding'" class="space-y-6">
            <div class="flex items-center justify-between">
              <div>
                <h3 class="text-lg font-bold text-gray-900">品牌个性化</h3>
                <p class="text-sm text-gray-500 mt-1">开启后可自定义产品名称、登录页、图标与联系信息</p>
              </div>
              <Switch v-model="brandingConfig.enabled" />
            </div>

            <fieldset :disabled="!brandingConfig.enabled" class="space-y-4 border border-gray-100 rounded-xl p-4 disabled:opacity-60">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">产品名称</label>
                <input
                  v-model="brandingConfig.product_name"
                  type="text"
                  class="block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                  placeholder="云枢 · 数据服务平台"
                />
                <p class="text-xs text-gray-400 mt-1">影响浏览器标题、左侧菜单栏名称、登录页</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">登录页副标题</label>
                <input
                  v-model="brandingConfig.login_subtitle"
                  type="text"
                  class="block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                  placeholder="Yunshu API Data Platform"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Logo / Favicon</label>
                <div class="flex items-center gap-4">
                  <img
                    :src="brandingConfig.icon_url || '/favicon.png'"
                    alt="Logo 预览"
                    class="w-12 h-12 rounded-lg border border-gray-200 object-cover bg-white"
                  />
                  <div class="flex-1 space-y-2">
                    <input
                      v-model="brandingConfig.icon_url"
                      type="text"
                      class="block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm font-mono"
                      placeholder="/favicon.png 或 /branding/icon.png"
                    />
                    <button
                      type="button"
                      class="text-sm text-indigo-600 hover:text-indigo-800 disabled:opacity-50"
                      :disabled="loading.branding_icon || !brandingConfig.enabled"
                      @click="triggerBrandingIconUpload"
                    >
                      {{ loading.branding_icon ? '上传中...' : '上传图片' }}
                    </button>
                    <input
                      ref="brandingIconInput"
                      type="file"
                      accept="image/png,image/jpeg,image/webp,image/svg+xml"
                      class="hidden"
                      @change="onBrandingIconSelected"
                    />
                  </div>
                </div>
                <p class="text-xs text-gray-400 mt-1">用于登录页、侧栏左上角与浏览器标签图标（PNG/JPEG/WebP/SVG，最大 512KB）</p>
              </div>

              <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 py-2 border-t border-gray-100">
                <div>
                  <p class="text-sm font-medium text-gray-700">隐藏登录页 SSO</p>
                  <p class="text-xs text-gray-400">开启后登录页不再显示 SSO 登录 Tab</p>
                </div>
                <Switch v-model="brandingConfig.hide_login_sso" />
              </div>

              <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 py-2 border-t border-gray-100">
                <div>
                  <p class="text-sm font-medium text-gray-700">隐藏版本号外链</p>
                  <p class="text-xs text-gray-400">开启后侧栏版本号不再链接到 GitHub，并隐藏 GitHub 图标</p>
                </div>
                <Switch v-model="brandingConfig.hide_version_link" />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">联系信息（Markdown）</label>
                <textarea
                  v-model="brandingConfig.contact_markdown"
                  rows="8"
                  class="block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm font-mono"
                  placeholder="支持 Markdown，将在「我的权限资产库 → 联系我们」中展示"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">版权信息</label>
                <input
                  v-model="brandingConfig.copyright_text"
                  type="text"
                  class="block w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                  placeholder="© 2026 公司名称 · All Rights Reserved"
                />
                <p class="text-xs text-gray-400 mt-1">启用品牌个性化后，显示在登录页底部（小字展示，支持换行）</p>
              </div>
            </fieldset>

            <div class="flex justify-end">
              <button
                type="button"
                :disabled="loading.branding_save"
                class="inline-flex items-center px-6 py-2 text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                @click="saveBrandingPlatformConfig"
              >
                {{ loading.branding_save ? '保存中...' : '保存品牌配置' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab Content: Data Masking -->
    <div v-show="activeTab === 'masking'" class="space-y-6">
      <!-- Global Toggle -->
      <div class="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
        <div class="p-6 flex items-center justify-between">
          <div class="flex items-center">
            <div class="p-2 bg-indigo-100 rounded-lg mr-4">
              <ShieldCheckIcon class="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <h3 class="text-lg font-bold text-gray-900">数据脱敏总开关</h3>
              <p class="text-xs text-gray-500">一键开启或关闭全系统的敏感字段自动脱敏逻辑。</p>
            </div>
          </div>
          <label class="inline-flex items-center cursor-pointer">
            <input type="checkbox" v-model="maskingGlobalEnabled" @change="toggleGlobalMasking" class="sr-only peer">
            <div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
            <span class="ms-3 text-sm font-medium text-gray-700">{{ maskingGlobalEnabled ? '已全局启用' : '已全局禁用' }}</span>
          </label>
        </div>
      </div>

      <!-- Rules Management -->
      <div class="bg-white shadow rounded-lg overflow-hidden border border-gray-200">
        <div class="p-4 border-b bg-gray-50 flex justify-between items-center">
          <div>
            <h3 class="font-bold text-gray-900">脱敏规则配置</h3>
            <p class="text-xs text-gray-500 mt-1">系统将根据字段名自动匹配并应用脱敏算法。</p>
          </div>
          <button @click="openMaskingModal()" class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 shadow-sm transition-colors">
            <BoltIcon class="h-4 w-4 mr-2" /> 添加规则
          </button>
        </div>

        <div v-if="loading.masking_load" class="py-20 flex justify-center">
          <ArrowPathIcon class="h-8 w-8 text-indigo-500 animate-spin" />
        </div>

        <table v-else class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">规则名称</th>
              <th class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">匹配字段 (Pattern)</th>
              <th class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">脱敏类型</th>
              <th class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">预览效果</th>
              <th class="px-6 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">状态</th>
              <th class="px-6 py-3 text-right text-xs font-bold text-gray-500 uppercase tracking-wider">操作</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="rule in maskingRules" :key="rule.id" class="hover:bg-gray-50 transition-colors">
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ rule.rule_name }}</td>
              <td class="px-6 py-4 whitespace-nowrap">
                <code class="px-2 py-1 bg-gray-100 text-indigo-600 rounded text-xs font-mono">{{ rule.match_field }}</code>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-xs text-gray-600">
                <span v-if="rule.mask_type === 'PARTIAL_3_4'" class="bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">前3后4遮掩</span>
                <span v-else-if="rule.mask_type === 'PARTIAL_4'" class="bg-green-50 text-green-700 px-2 py-0.5 rounded-full">保留后4位</span>
                <span v-else-if="rule.mask_type === 'EMAIL'" class="bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full">邮箱脱敏</span>
                <span v-else-if="rule.mask_type === 'FULL'" class="bg-red-50 text-red-700 px-2 py-0.5 rounded-full">完全遮盖</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-xs font-mono text-gray-400">
                {{ getMaskPreview(rule.mask_type) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center gap-2">
                  <Switch 
                    :model-value="rule.is_active === 1" 
                    @update:model-value="toggleRuleStatus(rule)"
                  />
                  <span :class="rule.is_active ? 'text-green-600' : 'text-gray-400'" class="text-xs font-bold">
                    {{ rule.is_active ? '已启用' : '已禁用' }}
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <button @click="openMaskingModal(rule)" class="text-indigo-600 hover:text-indigo-900 mr-4">编辑</button>
                <button @click="deleteMaskingRule(rule.id!)" class="text-red-600 hover:text-red-900">删除</button>
              </td>
            </tr>
            <tr v-if="maskingRules.length === 0">
              <td colspan="6" class="px-6 py-10 text-center text-gray-400 italic">暂无脱敏规则</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Config Guide Card -->
      <div class="bg-indigo-50 rounded-lg p-6 border border-indigo-100">
        <h4 class="text-indigo-900 font-bold mb-2 flex items-center">
          <AdjustmentsHorizontalIcon class="w-5 h-5 mr-2" /> 配置指南与示例
        </h4>
        <ul class="text-sm text-indigo-700 space-y-2 list-disc pl-5">
          <li><strong>匹配规则</strong>：支持通配符 <code>*</code>。例如 <code>*phone*</code> 将匹配 <code>user_phone</code>、<code>mobile_phone</code> 等。</li>
          <li><strong>优先级</strong>：采用“首次匹配原则”。如果一个字段被多个规则命中，将应用 ID 较大的最新规则。</li>
          <li><strong>豁免机制</strong>：Admin 用户默认脱敏，如需查看明文，请在请求时携带参数 <code>?unmask=true</code>。</li>
          <li><strong>层级覆盖</strong>：用户级设置 > 角色级设置 > 全局设置。</li>
        </ul>
      </div>
    </div>

    <!-- Masking Modal -->
    <teleport to="body">
      <transition name="dialog">
        <div v-if="showMaskingModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4" @click.self="showMaskingModal = false">
          <div class="bg-white rounded-xl shadow-2xl max-w-lg w-full overflow-hidden animate-scale-in">
            <div class="px-6 py-4 border-b flex justify-between items-center bg-gray-50">
              <h3 class="text-lg font-bold text-gray-900">{{ editingRule.id ? '编辑脱敏规则' : '添加脱敏规则' }}</h3>
              <button @click="showMaskingModal = false" class="text-gray-400 hover:text-gray-600 transition-colors"><XCircleIcon class="w-6 h-6" /></button>
            </div>
            
            <div class="p-6 space-y-5">
              <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">规则名称</label>
                <input v-model="editingRule.rule_name" type="text" class="w-full rounded-lg border-gray-300 shadow-sm focus:ring-indigo-500 focus:border-indigo-500" placeholder="e.g. 手机号保护">
              </div>

              <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">
                  匹配字段 (Field Pattern)
                  <span class="ml-1 text-[10px] text-indigo-500 bg-indigo-50 px-1 rounded">支持通配符 *</span>
                </label>
                <input v-model="editingRule.match_field" type="text" class="w-full rounded-lg border-gray-300 shadow-sm focus:ring-indigo-500 focus:border-indigo-500 font-mono" placeholder="e.g. *phone*">
              </div>

              <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">脱敏算法</label>
                <select v-model="editingRule.mask_type" class="w-full rounded-lg border-gray-300 shadow-sm focus:ring-indigo-500 focus:border-indigo-500">
                  <option value="PARTIAL_3_4">前3后4遮掩 (138****8000)</option>
                  <option value="PARTIAL_4">保留后4位 (*******1234)</option>
                  <option value="EMAIL">邮箱打码 (a***@b.com)</option>
                  <option value="FULL">完全遮蔽 (******)</option>
                </select>
              </div>

              <div class="flex items-center">
                <label class="inline-flex items-center cursor-pointer">
                  <input type="checkbox" v-model="editingRule.is_active" :true-value="1" :false-value="0" class="sr-only peer">
                  <div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                  <span class="ms-3 text-sm font-medium text-gray-700">启用该规则</span>
                </label>
              </div>

              <div>
                <label class="block text-sm font-semibold text-gray-700 mb-1">备注</label>
                <textarea v-model="editingRule.description" rows="2" class="w-full rounded-lg border-gray-300 shadow-sm focus:ring-indigo-500 focus:border-indigo-500" placeholder="规则详细说明..."></textarea>
              </div>
            </div>

            <div class="px-6 py-4 bg-gray-50 border-t flex justify-end space-x-3">
              <button @click="showMaskingModal = false" class="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors">取消</button>
              <button @click="saveMaskingRule" :disabled="loading.masking_save" class="px-6 py-2 bg-indigo-600 text-white rounded-lg text-sm font-bold hover:bg-indigo-700 shadow-lg shadow-indigo-100 disabled:opacity-50 flex items-center">
                <ArrowPathIcon v-if="loading.masking_save" class="animate-spin -ml-1 mr-2 h-4 w-4" />
                确认保存
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>

    <!-- Tab Content: Diagnostic -->
    <div v-show="activeTab === 'diagnostic'" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="space-y-6">
        <div class="bg-white shadow rounded-lg p-6">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center space-x-3">
              <div class="p-2 bg-red-100 rounded-lg"><CircleStackIcon class="h-6 w-6 text-red-600" /></div>
              <div><h3 class="text-lg font-medium text-gray-900">Redis</h3><p class="text-sm text-gray-500">缓存与会话管理</p></div>
            </div>
            <div v-if="results.redis"><CheckCircleIcon v-if="results.redis === 'success'" class="h-6 w-6 text-green-500" /><XCircleIcon v-else class="h-6 w-6 text-red-500" /></div>
          </div>
          <div class="border-t border-gray-100 pt-4 mt-2 grid grid-cols-2 gap-3">
            <button @click="testConnection('redis')" :disabled="loading.redis" class="flex justify-center items-center py-2 px-4 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"><PlayIcon class="h-4 w-4 mr-2" /> {{ loading.redis ? '测试中...' : '测试连接' }}</button>
                            <button @click="scanRedisKeys" :disabled="loading.redis_scan" class="flex justify-center items-center py-2 px-4 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"><MagnifyingGlassIcon class="h-4 w-4 mr-2" /> {{ loading.redis_scan ? '扫描中...' : '扫描 Keys' }}</button>
                          </div>
                        </div>
            
                        <!-- Vector Search Capability -->
                        <div class="p-6 bg-gray-50 flex items-center justify-between">
                          <div class="flex items-center gap-4">
                            <div class="p-3 bg-indigo-100 rounded-xl text-indigo-600">
                              <BoltIcon class="h-6 w-6" />
                            </div>
                            <div>
                              <h3 class="text-lg font-medium text-gray-900">向量搜索能力 (Vector Search)</h3>
                              <p class="text-sm text-gray-500">检测 Redis Stack 是否已加载 RediSearch 模块</p>
                            </div>
                          </div>
                          <div class="flex items-center gap-4">
                            <div v-if="results.vector">
                              <CheckCircleIcon v-if="results.vector === 'success'" class="h-6 w-6 text-green-500" />
                              <XCircleIcon v-else class="h-6 w-6 text-red-500" />
                            </div>
                            <button 
                              @click="testConnection('vector')" 
                              :disabled="loading.vector" 
                              class="flex-shrink-0 whitespace-nowrap flex justify-center items-center py-2 px-4 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
                            >
                              <PlayIcon class="h-4 w-4 mr-2" /> 
                              {{ loading.vector ? '检测中...' : '开始检测' }}
                            </button>
                          </div>
                        </div>      </div>
      <div class="bg-gray-900 rounded-lg shadow h-[500px] flex flex-col overflow-hidden text-green-400 font-mono text-sm p-4">
        <div class="flex justify-between border-b border-gray-700 pb-2 mb-2 text-gray-400"><span class="text-xs">诊断控制台</span><button @click="clearLogs" class="text-xs hover:text-white">清空</button></div>
        <div class="flex-1 overflow-y-auto space-y-1"><div v-for="(log, i) in logs" :key="i">> {{ log }}</div></div>
      </div>
    </div>

    <!-- Tab Content: Pools -->
    <div v-show="activeTab === 'pools'" class="bg-white shadow rounded-lg overflow-hidden">
      <div class="p-4 border-b bg-gray-50 flex justify-between items-center">
        <h3 class="font-medium text-gray-900">活跃连接池</h3>
        <div class="space-x-3">
          <button @click="fetchPools" :disabled="loading.pools_fetch" class="inline-flex items-center px-3 py-2 border rounded-md bg-white text-sm hover:bg-gray-50"><ArrowPathIcon class="h-4 w-4 mr-2" :class="{'animate-spin': loading.pools_fetch}" /> 刷新</button>
          <button @click="checkAllHealth" :disabled="loading.pools_health" class="inline-flex items-center px-3 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"><HeartIcon class="h-4 w-4 mr-2" /> 体检</button>
        </div>
      </div>
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50"><tr><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">数据源</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">活跃/已分配</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th></tr></thead>
        <tbody class="divide-y divide-gray-200"><tr v-for="p in pools" :key="p.source_id">
          <td class="px-6 py-4 text-sm text-gray-500">#{{ p.source_id }}</td>
          <td class="px-6 py-4 font-medium text-gray-900">{{ p.source_name }} <span class="ml-2 text-xs text-gray-400 bg-gray-100 px-1 rounded">{{ p.source_type }}</span></td>
          <td class="px-6 py-4 text-sm text-gray-900"><span class="text-green-600 font-bold">{{ p.active }}</span> / {{ p.active + p.free }}</td>
          <td class="px-6 py-4">
            <span v-if="p.status === 'not_initialized'" class="text-gray-400 flex items-center text-xs font-medium">
              <ClockIcon class="w-4 h-4 mr-1"/>待初始化
            </span>
            <span v-else-if="p.health === 'healthy'" class="text-green-600 flex items-center text-xs font-medium">
              <CheckCircleIcon class="w-4 h-4 mr-1"/>正常
            </span>
            <span v-else-if="p.health === 'unhealthy' || p.status === 'error'" class="text-red-600 flex items-center text-xs font-medium">
              <XCircleIcon class="w-4 h-4 mr-1"/>异常
            </span>
            <span v-else class="text-amber-500 flex items-center text-xs font-medium">
              <MagnifyingGlassIcon class="h-4 w-4 mr-1" /> 待体检
            </span>
          </td>
        </tr></tbody>
      </table>
    </div>

    <!-- Tab Content: Logs -->
    <div v-show="activeTab === 'logs'" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Config Card -->
        <div class="lg:col-span-1 space-y-6">
          <div class="bg-white shadow rounded-lg p-6">
            <h3 class="text-lg font-medium text-gray-900 mb-4 flex items-center"><TrashIcon class="h-5 w-5 mr-2 text-gray-400" /> 日志策略</h3>
            <div class="space-y-4">
              <div><label class="block text-xs font-medium text-gray-500 uppercase mb-1">原始日志保留 (天)</label><input type="number" v-model="retentionConfig.raw_logs" class="w-full rounded-md border-gray-300 text-sm shadow-sm" /></div>
              <div><label class="block text-xs font-medium text-gray-500 uppercase mb-1">聚合数据保留 (天)</label><input type="number" v-model="retentionConfig.stats" class="w-full rounded-md border-gray-300 text-sm shadow-sm" /></div>
              <button v-if="hasPerm('element:config:save')" @click="saveConfig" :disabled="loading.save_config" class="w-full py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">保存配置</button>
            </div>
          </div>
          <div class="bg-white shadow rounded-lg p-6">
            <h3 class="text-lg font-medium text-gray-900 mb-4 flex items-center"><ArrowPathIcon class="h-5 w-5 mr-2 text-gray-400" /> 手动运维</h3>
            <div class="space-y-3">
              <button v-if="hasPerm('element:config:save')" @click="triggerPurge" :disabled="loading.log_purge" class="w-full flex items-center justify-center px-4 py-2 border border-red-300 text-red-700 rounded-md text-sm hover:bg-red-50 disabled:opacity-50"><TrashIcon class="h-4 w-4 mr-2" /> 立即清理过期日志</button>
              <button v-if="hasPerm('element:config:save')" @click="triggerAggregation" :disabled="loading.log_aggregate" class="w-full flex items-center justify-center px-4 py-2 border border-indigo-300 text-indigo-700 rounded-md text-sm hover:bg-indigo-50 disabled:opacity-50"><TableCellsIcon class="h-4 w-4 mr-2" /> 重新数据聚合 (7天)</button>
            </div>
          </div>

        </div>

        <!-- Maintenance Logs & Shard Info -->
        <div class="lg:col-span-2 bg-white shadow rounded-lg overflow-hidden flex flex-col">
          <div class="p-4 border-b bg-gray-50 flex justify-between items-center">
            <div class="flex space-x-4">
              <button 
                @click="logSubTab = 'tasks'" 
                :class="[logSubTab === 'tasks' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500 hover:text-gray-700']"
                class="pb-1 text-sm font-medium transition-colors"
              >
                运维任务
              </button>
              <button 
                @click="() => { logSubTab = 'shards'; fetchShardLogs(); }" 
                :class="[logSubTab === 'shards' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500 hover:text-gray-700']"
                class="pb-1 text-sm font-medium transition-colors"
              >
                数据分表
              </button>
            </div>
            <button v-if="logSubTab === 'tasks'" @click="fetchMaintenanceLogs" class="text-gray-400 hover:text-indigo-600">
              <ArrowPathIcon class="h-4 w-4" :class="{'animate-spin': loading.m_logs}" />
            </button>
            <button v-else @click="fetchShardLogs" class="text-gray-400 hover:text-indigo-600">
              <ArrowPathIcon class="h-4 w-4" :class="{'animate-spin': loading.shard_logs}" />
            </button>
          </div>

          <div class="flex-1 overflow-y-auto max-h-[600px]">
            <!-- Tasks View -->
            <table v-if="logSubTab === 'tasks'" class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-4 py-2 text-left text-xs text-gray-500 font-medium">任务/执行人</th>
                  <th class="px-4 py-2 text-left text-xs text-gray-500 font-medium">状态/影响</th>
                  <th class="px-4 py-2 text-left text-xs text-gray-500 font-medium">时间</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="ml in maintenanceLogs" :key="ml.id" class="text-sm hover:bg-gray-50 transition-colors">
                  <td class="px-4 py-3">
                    <div class="font-medium text-gray-900">
                      {{ 
                        ml.task_name === 'log_purge' || ml.task_name === 'log_purge_sharded' ? '日志清理' : 
                        ml.task_name === 'backfill_sharded' ? '数据回填' : ml.task_name 
                      }}
                    </div>
                    <div class="text-xs text-gray-400">{{ ml.operator }}</div>
                  </td>
                  <td class="px-4 py-3">
                    <span :class="{'text-green-600': ml.status === 'SUCCESS', 'text-red-600': ml.status === 'FAILED', 'text-blue-600 animate-pulse': ml.status === 'RUNNING'}" class="font-medium">{{ ml.status }}</span>
                    <div class="text-xs text-gray-500" v-if="ml.status === 'SUCCESS'">影响: {{ ml.affected_rows }} 行</div>
                    <div class="text-xs text-red-400 truncate max-w-[150px]" v-if="ml.error_message" :title="ml.error_message">{{ ml.error_message }}</div>
                  </td>
                  <td class="px-4 py-3 text-xs text-gray-500">
                    <div>始: {{ formatDateTime(ml.start_time) }}</div>
                    <div v-if="ml.end_time">终: {{ formatDateTime(ml.end_time) }}</div>
                  </td>
                </tr>
                <tr v-if="maintenanceLogs.length === 0">
                  <td colspan="3" class="px-4 py-10 text-center text-gray-400 italic">暂无维护记录</td>
                </tr>
              </tbody>
            </table>

            <!-- Shards View -->
            <table v-else class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-4 py-2 text-left text-xs text-gray-500 font-medium">表名</th>
                  <th class="px-4 py-2 text-right text-xs text-gray-500 font-medium">记录数</th>
                  <th class="px-4 py-2 text-right text-xs text-gray-500 font-medium">数据占用</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200">
                <tr v-for="shard in shardLogs" :key="shard.table_name" class="text-sm hover:bg-gray-50 transition-colors">
                  <td class="px-4 py-3 font-mono text-xs text-gray-900">{{ shard.table_name }}</td>
                  <td class="px-4 py-3 text-right text-gray-600">{{ shard.row_count.toLocaleString() }}</td>
                  <td class="px-4 py-3 text-right font-medium text-gray-900">{{ shard.size_mb }} MB</td>
                </tr>
                <tr v-if="shardLogs.length === 0">
                  <td colspan="3" class="px-4 py-10 text-center text-gray-400 italic">未发现日志分表</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Custom Confirm Dialog -->
    <ConfirmDialog 
      :show="dialog.show"
      :title="dialog.title"
      :message="dialog.message"
      :type="dialog.type"
      @confirm="dialog.onConfirm"
      @cancel="dialog.show = false"
    />
  </div>
</template>
