<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import axios from "axios";
import { useToast } from "../composables/useToast";
import ClearableInput from "../components/common/ClearableInput.vue";

const { showToast: addToast } = useToast();

interface AuditLog {
  id: number;
  user_name: string;
  endpoint: string;
  method: string;
  status_code: number;
  process_time_ms: number;
  client_ip?: string;
  action_type?: string;
  created_at: string;
}

interface LogDetail {
  id: number;
  trace_id: string;
  user_name: string;
  endpoint: string;
  method: string;
  status_code: number;
  process_time_ms: number;
  client_ip?: string;
  request_params?: any;
  response_body?: any;
  error_message?: string;
  action_type?: string;
  source_sql?: string;
  created_at: string;
}

interface Statistics {
  total_requests: number;
  success_count: number;
  error_count: number;
  avg_response_time: number;
  success_rate: number;
}

interface Filters {
  start_time: string;
  end_time: string;
  method: string;
  min_status: number | null;
  max_status: number | null;
  user_name: string;
  endpoint: string;
  client_ip: string;
  action_type: string;
}

const ACTION_TYPES = [
  { value: '', label: '全部功能点' },
  { value: 'API_QUERY', label: '接口服务' },
  { value: 'SQL_EXECUTE', label: 'SQL 执行' },
  { value: 'LAB_QUERY', label: 'LAB 预览' },
  { value: 'LAB_EXPORT', label: '数据导出' },
  { value: 'LAB_PUBLISH', label: 'API 发布' },
  { value: 'LAB_ANALYSIS', label: 'AI 分析' },
  { value: 'LAB_METADATA', label: '建模文档' },
  { value: 'META_V2_SEARCH', label: '元数据检索' },
  { value: 'META_V2_DATASET_CREATE', label: '创建元数据集' },
  { value: 'META_V2_DATASET_UPDATE', label: '更新元数据集' },
  { value: 'META_V2_DATASET_DELETE', label: '删除元数据集' },
  { value: 'META_V2_TABLE_SAVE', label: '保存表元数据' },
  { value: 'META_V2_METRIC_CREATE', label: '创建业务指标' },
  { value: 'META_V2_RELATION_CREATE', label: '创建关联关系' },
  { value: 'META_V2_METRIC_RECOMMEND', label: 'AI推荐指标' },
  { value: 'META_V2_VECTOR_SYNC', label: '向量库同步' },
  { value: 'META_RESOURCE_CREATE', label: '创建API资源' },
  { value: 'META_RESOURCE_UPDATE', label: '更新API资源' },
  { value: 'META_RESOURCE_DELETE', label: '删除API资源' },
  { value: 'DS_EDIT', label: '数据源变更' },
  { value: 'RES_EDIT', label: '资源配置变更' },
  { value: 'USER_MANAGE', label: '用户管理' },
  { value: 'CONFIG_SAVE', label: '系统设置' },
  { value: 'CATALOG_PUBLISH', label: '目录发布' },
  { value: 'CATALOG_BATCH_PUBLISH', label: '目录批量上架' },
  { value: 'CATALOG_UNPUBLISH', label: '目录下架' },
  { value: 'CATALOG_PRODUCT_UPDATE', label: '目录产品编辑' },
  { value: 'CATALOG_ACCESS_REQUEST', label: '目录权限申请' },
  { value: 'CATALOG_ACCESS_APPROVE', label: '目录权限审批通过' },
  { value: 'CATALOG_ACCESS_REJECT', label: '目录权限审批拒绝' },
  { value: 'CATALOG_ACCESS_REVOKE', label: '目录权限收回' },
  { value: 'CATALOG_BATCH_ASSIGN_OWNER', label: '目录批量指定负责人' },
]

const getActionTypeLabel = (val?: string) => {
  const found = ACTION_TYPES.find(t => t.value === val)
  return found ? found.label : (val || '-')
}

const getActionTypeColor = (val?: string) => {
  if (!val) return 'bg-gray-100 text-gray-600'
  if (val.startsWith('CATALOG_')) return 'bg-teal-50 text-teal-700 border-teal-100'
  if (val.startsWith('LAB_')) return 'bg-blue-50 text-blue-700 border-blue-100'
  if (val.startsWith('META_')) return 'bg-indigo-50 text-indigo-700 border-indigo-100'
  if (val.includes('QUERY') || val.includes('EXECUTE')) return 'bg-green-50 text-green-700 border-green-100'
  if (val.includes('EDIT') || val.includes('MANAGE')) return 'bg-purple-50 text-purple-700 border-purple-100'
  return 'bg-gray-50 text-gray-600 border-gray-200'
}


const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const apiKey = ref(localStorage.getItem("api_key") || "");
const userInfo = ref<any>(null);

const logs = ref<AuditLog[]>([]);
const page = ref(1);
const size = ref(20);
const total = ref(0);
const loading = ref(false);

const statistics = ref<Statistics | null>(null);
const showFilters = ref(false);

const filters = ref<Filters>({
  start_time: "",
  end_time: "",
  method: "",
  min_status: null,
  max_status: null,
  user_name: "",
  endpoint: "",
  client_ip: "",
  action_type: "",
});

const showDetailDialog = ref(false);
const logDetail = ref<LogDetail | null>(null);

const showExportDialog = ref(false);
const exportFormat = ref<"csv" | "json">("csv");
const exporting = ref(false);

const onlyErrors = ref(false);

watch(onlyErrors, (val) => {
  if (val) {
    filters.value.min_status = 400;
    // filters.value.max_status = 599; // Optional
  } else {
    filters.value.min_status = null;
    filters.value.max_status = null;
  }
  page.value = 1;
  fetchLogs(true);
});

// Helper to format date for datetime-local input
const toLocalISOString = (date: Date) => {
  const tzOffset = date.getTimezoneOffset() * 60000; // offset in milliseconds
  const localISOTime = (new Date(date.getTime() - tzOffset)).toISOString().slice(0, 16);
  return localISOTime;
};

// Time range restriction logic (Max 3 days)
watch(() => filters.value.start_time, (newVal) => {
  if (!newVal || !filters.value.end_time) return;
  const start = new Date(newVal).getTime();
  const end = new Date(filters.value.end_time).getTime();
  const threeDaysMs = 3 * 24 * 60 * 60 * 1000;
  
  if (end < start) {
    const adjustedEnd = new Date(start + 3600000);
    filters.value.end_time = toLocalISOString(adjustedEnd);
  } else if (end - start > threeDaysMs) {
    const adjustedEnd = new Date(start + threeDaysMs);
    filters.value.end_time = toLocalISOString(adjustedEnd);
    addToast("查询跨度已自动调整为最大支持的 3 天", "info");
  }
});

watch(() => filters.value.end_time, (newVal) => {
  if (!newVal || !filters.value.start_time) return;
  const end = new Date(newVal).getTime();
  const start = new Date(filters.value.start_time).getTime();
  const threeDaysMs = 3 * 24 * 60 * 60 * 1000;
  
  if (start > end) {
    const adjustedStart = new Date(end - 3600000);
    filters.value.start_time = toLocalISOString(adjustedStart);
  } else if (end - start > threeDaysMs) {
    const adjustedStart = new Date(end - threeDaysMs);
    filters.value.start_time = toLocalISOString(adjustedStart);
    addToast("查询跨度已自动调整为最大支持的 3 天", "info");
  }
});

// Endpoint Autocomplete
const endpointSuggestions = ref<string[]>([]);
const showEndpointSuggestions = ref(false);
let endpointSearchTimer: any = null;

const fetchEndpointSuggestions = async (query: string) => {
  try {
    const response = await axios.get(
      `${API_BASE}/api/portal/audit/logs/endpoints`,
      {
        headers: { "X-API-Key": apiKey.value },
        params: { query, limit: 10 },
      }
    );
    endpointSuggestions.value = response.data;
  } catch (error) {
    console.error("Failed to fetch endpoint suggestions", error);
  }
};

const onEndpointInput = () => {
  showEndpointSuggestions.value = true;
  if (endpointSearchTimer) clearTimeout(endpointSearchTimer);
  endpointSearchTimer = setTimeout(() => {
    fetchEndpointSuggestions(filters.value.endpoint);
  }, 300);
};

const onEndpointFocus = () => {
  showEndpointSuggestions.value = true;
  fetchEndpointSuggestions(filters.value.endpoint);
};

const onEndpointBlur = () => {
  // Delay hiding to allow click event on suggestion to fire
  setTimeout(() => {
    showEndpointSuggestions.value = false;
  }, 200);
};

const selectEndpoint = (suggestion: string) => {
  filters.value.endpoint = suggestion;
  showEndpointSuggestions.value = false;
};

// Modified to accept an optional argument which could be an Event or boolean
const fetchLogs = async (arg?: boolean | Event) => {
  // Determine if we should refresh stats. Default to true.
  // If called from button click (Event), treat as true.
  // If called explicitly with false (pagination), treat as false.
  const refreshStats = typeof arg === 'boolean' ? arg : true;

  loading.value = true;
  try {
    const params: any = {
      page: page.value,
      size: size.value,
      include_stats: refreshStats,
    };

    // Add filters
    if (filters.value.start_time) params.start_time = filters.value.start_time;
    if (filters.value.end_time) params.end_time = filters.value.end_time;
    if (filters.value.method) params.method = filters.value.method;
    if (filters.value.min_status) params.min_status = filters.value.min_status;
    if (filters.value.max_status) params.max_status = filters.value.max_status;
    if (filters.value.user_name) params.user_name = filters.value.user_name;
    if (filters.value.endpoint) params.endpoint = filters.value.endpoint;
    if (filters.value.client_ip) params.client_ip = filters.value.client_ip;
    if (filters.value.action_type) params.action_type = filters.value.action_type;

    const response = await axios.get(`${API_BASE}/api/portal/audit/logs`, {
      headers: { "X-API-Key": apiKey.value },
      params,
    });

    logs.value = response.data.items || [];
    total.value = response.data.total || 0;
    
    // Only update statistics if backend returned them
    if (response.data.statistics) {
      statistics.value = response.data.statistics;
    }
  } catch (error: any) {
    addToast(error.response?.data?.detail || "加载日志失败", "error");
    console.error("Failed to fetch logs:", error);
  } finally {
    loading.value = false;
  }
};

const applyFilters = () => {
  page.value = 1;
  fetchLogs(true);
};

const resetFilters = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const todayStr = `${year}-${month}-${day}`;
  
  // Default to today 00:00:00 - 23:59:59 to avoid multi-day joins by default
  const defaultStart = `${todayStr}T00:00`;
  const defaultEnd = `${todayStr}T23:59`;

  filters.value = {
    start_time: defaultStart,
    end_time: defaultEnd,
    method: "",
    min_status: null,
    max_status: null,
    user_name: "",
    endpoint: "",
    client_ip: "",
    action_type: "",
  };
  page.value = 1;
  fetchLogs(true);
};

const viewLogDetail = async (logId: number) => {
  showDetailDialog.value = true;
  logDetail.value = null;

  try {
    const response = await axios.get(
      `${API_BASE}/api/portal/audit/logs/${logId}`,
      {
        headers: { "X-API-Key": apiKey.value },
      }
    );
    logDetail.value = response.data;
  } catch (error: any) {
    addToast(error.response?.data?.detail || "加载日志详情失败", "error");
    console.error("Failed to fetch log detail:", error);
    showDetailDialog.value = false;
  }
};

const exportLogs = async () => {
  exporting.value = true;
  try {
    const params: any = {
      format: exportFormat.value,
    };

    // Add filters
    if (filters.value.start_time) params.start_time = filters.value.start_time;
    if (filters.value.end_time) params.end_time = filters.value.end_time;
    if (filters.value.method) params.method = filters.value.method;
    if (filters.value.min_status) params.min_status = filters.value.min_status;
    if (filters.value.max_status) params.max_status = filters.value.max_status;
    if (filters.value.user_name) params.user_name = filters.value.user_name;
    if (filters.value.endpoint) params.endpoint = filters.value.endpoint;
    if (filters.value.client_ip) params.client_ip = filters.value.client_ip;
    if (filters.value.action_type) params.action_type = filters.value.action_type;

    const response = await axios.get(
      `${API_BASE}/api/portal/audit/logs/export`,
      {
        headers: { "X-API-Key": apiKey.value },
        params,
        responseType: "blob",
      }
    );

    // Download file
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;

    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, "-");
    link.setAttribute(
      "download",
      `audit_logs_${timestamp}.${exportFormat.value}`
    );
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);

    addToast("导出成功", "success");
    showExportDialog.value = false;
  } catch (error: any) {
    addToast(error.response?.data?.detail || "导出失败", "error");
    console.error("Failed to export logs:", error);
  } finally {
    exporting.value = false;
  }
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return "-";
  let dateInput =
    typeof dateStr === "string" ? dateStr.replace(" ", "T") : dateStr;

  return new Date(dateInput).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

const formatJSON = (data: any) => {
  if (!data) return "-";
  if (typeof data === "string") {
    try {
      return JSON.stringify(JSON.parse(data), null, 2);
    } catch {
      return data;
    }
  }
  return JSON.stringify(data, null, 2);
};

const loadUserInfo = () => {
  const stored = localStorage.getItem("user_info");
  if (stored) {
    userInfo.value = JSON.parse(stored);
  }
};

const hasPerm = (code: string) => {
  if (userInfo.value?.role === 'admin') return true
  return userInfo.value?.permissions?.elements?.includes(code)
}

onMounted(() => {
  loadUserInfo();
  
  // Initialize with today's range by default
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const todayStr = `${year}-${month}-${day}`;
  filters.value.start_time = `${todayStr}T00:00`;
  filters.value.end_time = `${todayStr}T23:59`;
  
  fetchLogs(true);
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-semibold text-gray-900">审计日志</h1>
      <div class="flex items-center space-x-3">
        <label class="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 cursor-pointer select-none">
          <input type="checkbox" v-model="onlyErrors" class="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300 rounded mr-2" />
          仅看错误
        </label>
        <button
          @click="fetchLogs(true)"
          class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
        >
          <svg
            class="-ml-1 mr-2 h-5 w-5 text-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          刷新
        </button>
        <button
          v-if="hasPerm('element:audit:export')"
          @click="showExportDialog = true"

          class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md shadow-sm text-sm font-medium hover:bg-blue-700"
        >
          <svg
            class="-ml-1 mr-2 h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          导出
        </button>
      </div>
    </div>

    <!-- Statistics Cards -->
    <div
      v-if="statistics"
      class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
    >
      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0 bg-blue-100 rounded-md p-3">
            <svg
              class="h-6 w-6 text-blue-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
          </div>
          <div class="ml-5 w-0 flex-1">
            <dl>
              <dt class="text-sm font-medium text-gray-500 truncate">
                总请求数
              </dt>
              <dd class="text-lg font-semibold text-gray-900">
                {{ statistics.total_requests }}
              </dd>
            </dl>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div
            class="flex-shrink-0 rounded-md p-3"
            :class="
              statistics.success_rate >= 90 ? 'bg-green-100' : 'bg-red-100'
            "
          >
            <svg
              class="h-6 w-6"
              :class="
                statistics.success_rate >= 90
                  ? 'text-green-600'
                  : 'text-red-600'
              "
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <div class="ml-5 w-0 flex-1">
            <dl>
              <dt class="text-sm font-medium text-gray-500 truncate">成功率</dt>
              <dd
                class="text-lg font-semibold"
                :class="
                  statistics.success_rate >= 90
                    ? 'text-green-600'
                    : 'text-red-600'
                "
              >
                {{ statistics.success_rate }}%
              </dd>
            </dl>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0 bg-yellow-100 rounded-md p-3">
            <svg
              class="h-6 w-6 text-yellow-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <div class="ml-5 w-0 flex-1">
            <dl>
              <dt class="text-sm font-medium text-gray-500 truncate">
                平均响应时间
              </dt>
              <dd class="text-lg font-semibold text-gray-900">
                {{ statistics.avg_response_time }} ms
              </dd>
            </dl>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center">
          <div class="flex-shrink-0 bg-red-100 rounded-md p-3">
            <svg
              class="h-6 w-6 text-red-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <div class="ml-5 w-0 flex-1">
            <dl>
              <dt class="text-sm font-medium text-gray-500 truncate">错误数</dt>
              <dd class="text-lg font-semibold text-red-600">
                {{ statistics.error_count }}
              </dd>
            </dl>
          </div>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="bg-white shadow-sm rounded-lg border border-gray-200">
      <!-- Filter Header -->
      <div
        @click="showFilters = !showFilters"
        class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50 border-b border-gray-200"
      >
        <div class="flex items-center space-x-2">
          <svg
            class="h-5 w-5 text-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
            />
          </svg>
          <h3 class="text-sm font-medium text-gray-900">筛选条件</h3>
        </div>
        <svg
          class="h-5 w-5 text-gray-400 transition-transform duration-200"
          :class="{ 'rotate-180': showFilters }"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </div>

      <!-- Filter Content -->
      <div v-show="showFilters" class="p-4 bg-gray-50/50">
        <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-x-4 gap-y-3">
          <!-- Time Range -->
          <div>
            <label class="block text-xs font-semibold text-gray-500 mb-1">开始时间</label>
            <input
              v-model="filters.start_time"
              type="datetime-local"
              class="w-full px-2 py-1.5 border border-gray-300 rounded shadow-sm text-xs focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label class="block text-xs font-semibold text-gray-500 mb-1">结束时间</label>
            <input
              v-model="filters.end_time"
              type="datetime-local"
              class="w-full px-2 py-1.5 border border-gray-300 rounded shadow-sm text-xs focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <!-- Action Type -->
          <div>
            <label class="block text-xs font-semibold text-gray-500 mb-1">功能点</label>
            <select
              v-model="filters.action_type"
              class="w-full px-2 py-1.5 border border-gray-300 rounded shadow-sm text-xs focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            >
              <option v-for="type in ACTION_TYPES" :key="type.value" :value="type.value">
                {{ type.label }}
              </option>
            </select>
          </div>

          <!-- Endpoint -->
          <div class="relative lg:col-span-2">
            <label class="block text-xs font-semibold text-gray-500 mb-1">接口路径</label>
            <ClearableInput
              v-model="filters.endpoint"
              placeholder="搜索路径"
              autocomplete="off"
              input-class="px-2 py-1.5 text-xs"
              @input="onEndpointInput"
              @focus="onEndpointFocus"
              @blur="onEndpointBlur"
            />
            <!-- Autocomplete Dropdown -->
            <ul
              v-if="showEndpointSuggestions && endpointSuggestions.length > 0"
              class="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded shadow-lg max-h-40 overflow-y-auto"
            >
              <li
                v-for="suggestion in endpointSuggestions"
                :key="suggestion"
                @mousedown.prevent="selectEndpoint(suggestion)"
                class="px-2 py-1.5 text-xs text-gray-700 hover:bg-gray-100 cursor-pointer"
              >
                {{ suggestion }}
              </li>
            </ul>
          </div>

          <!-- Method -->
          <div>
            <label class="block text-xs font-semibold text-gray-500 mb-1">HTTP 方法</label>
            <select
              v-model="filters.method"
              class="w-full px-2 py-1.5 border border-gray-300 rounded shadow-sm text-xs focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">全部</option>
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="DELETE">DELETE</option>
              <option value="PATCH">PATCH</option>
            </select>
          </div>

          <!-- Status Code -->
          <div>
            <label class="block text-xs font-semibold text-gray-500 mb-1">状态码范围</label>
            <div class="flex space-x-1">
              <input
                v-model.number="filters.min_status"
                type="number"
                placeholder="最小"
                class="w-full px-2 py-1.5 border border-gray-300 rounded shadow-sm text-xs focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              />
              <span class="text-gray-400 self-center">-</span>
              <input
                v-model.number="filters.max_status"
                type="number"
                placeholder="最大"
                class="w-full px-2 py-1.5 border border-gray-300 rounded shadow-sm text-xs focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          <!-- User Name -->
          <div v-if="hasPerm('element:audit:manage')">
            <label class="block text-xs font-semibold text-gray-500 mb-1">用户名</label>
            <ClearableInput
              v-model="filters.user_name"
              placeholder="搜索用户"
              input-class="px-2 py-1.5 text-xs"
            />
          </div>

          <!-- Client IP -->
          <div>
            <label class="block text-xs font-semibold text-gray-500 mb-1">客户端 IP</label>
            <ClearableInput
              v-model="filters.client_ip"
              placeholder="搜索 IP"
              input-class="px-2 py-1.5 text-xs"
            />
          </div>

          <!-- Page Size -->
          <div>
            <label class="block text-xs font-semibold text-gray-500 mb-1">每页条数</label>
            <select
              v-model.number="size"
              @change="page = 1; fetchLogs(true);"
              class="w-full px-2 py-1.5 border border-gray-300 rounded shadow-sm text-xs focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            >
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
            </select>
          </div>
        </div>

        <!-- Filter Actions -->
        <div class="flex items-center justify-end space-x-2 mt-3 pt-3 border-t border-gray-100">
          <button
            @click="resetFilters"
            class="inline-flex items-center px-3 py-1.5 border border-gray-300 text-gray-700 rounded text-xs font-medium hover:bg-gray-50 transition-colors"
          >
            <svg class="mr-1.5 h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            重置
          </button>
          <button
            @click="applyFilters"
            class="inline-flex items-center px-3 py-1.5 bg-blue-600 text-white rounded text-xs font-medium hover:bg-blue-700 transition-colors shadow-sm"
          >
            <svg class="mr-1.5 h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
            查询
          </button>
        </div>
      </div>
    </div>

    <!-- Table Card -->
    <div
      class="bg-white shadow-sm rounded-lg border border-gray-200 overflow-hidden"
    >
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
              >
                用户
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
              >
                功能点
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
              >
                方法
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
              >
                接口路径
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
              >
                状态码
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
              >
                客户端IP
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
              >
                耗时
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
              >
                时间
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider"
              >
                操作
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <!-- Loading State: Shown during page transitions -->
            <tr v-if="loading">
              <td colspan="8" class="px-6 py-24 text-center">
                <svg
                  class="animate-spin h-8 w-8 mx-auto text-blue-500"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    class="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    stroke-width="4"
                  ></circle>
                  <path
                    class="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                <p class="mt-2 text-sm text-gray-500 font-medium">正在加载数据...</p>
              </td>
            </tr>

            <!-- Data Rows: Only rendered when not loading -->
            <template v-else>
              <tr
                v-for="log in logs"
                :key="log.id"
                class="transition-colors"
                :class="log.status_code >= 400 ? 'bg-red-50 hover:bg-red-100' : 'hover:bg-gray-50'"
              >
                <td
                  class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900"
                >
                  <div class="flex items-center">
                    <div
                      class="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold mr-3 text-xs"
                    >
                      {{ (log.user_name || "?").charAt(0).toUpperCase() }}
                    </div>
                    {{ log.user_name || "未知用户" }}
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-xs">
                  <span
                    class="inline-flex items-center px-2 py-0.5 rounded border font-bold uppercase tracking-tighter"
                    :class="getActionTypeColor(log.action_type)"
                  >
                    {{ getActionTypeLabel(log.action_type) }}
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  <span
                    class="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium font-mono"
                    :class="{
                      'bg-blue-100 text-blue-800': log.method === 'GET',
                      'bg-green-100 text-green-800': log.method === 'POST',
                      'bg-yellow-100 text-yellow-800':
                        log.method === 'PUT' || log.method === 'PATCH',
                      'bg-red-100 text-red-800': log.method === 'DELETE',
                      'bg-gray-100 text-gray-800': ![
                        'GET',
                        'POST',
                        'PUT',
                        'PATCH',
                        'DELETE',
                      ].includes(log.method),
                    }"
                  >
                    {{ log.method }}
                  </span>
                </td>
                <td
                  class="px-6 py-4 text-sm text-gray-600 font-mono max-w-xs truncate"
                  :title="log.endpoint"
                >
                  {{ log.endpoint }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                  <span
                    class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                    :class="{
                      'bg-green-100 text-green-800':
                        log.status_code >= 200 && log.status_code < 300,
                      'bg-yellow-100 text-yellow-800':
                        log.status_code >= 300 && log.status_code < 400,
                      'bg-red-100 text-red-800': log.status_code >= 400,
                    }"
                  >
                    {{ log.status_code }}
                  </span>
                </td>
                <td
                  class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono"
                >
                  {{ log.client_ip || "-" }}
                </td>
                <td
                  class="px-6 py-4 whitespace-nowrap text-sm"
                  :class="{
                    'text-green-600': log.process_time_ms < 100,
                    'text-yellow-600':
                      log.process_time_ms >= 100 && log.process_time_ms < 500,
                    'text-red-600': log.process_time_ms >= 500,
                  }"
                >
                  {{ log.process_time_ms.toFixed(2) }} ms
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {{ formatDate(log.created_at) }}
                </td>
                <td
                  class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
                >
                  <button
                    @click="viewLogDetail(log.id)"
                    class="text-blue-600 hover:text-blue-900"
                  >
                    详情
                  </button>
                </td>
              </tr>
              <!-- Empty State -->
              <tr v-if="logs.length === 0">
                <td colspan="8" class="px-6 py-12 text-center text-gray-500">
                  <svg
                    class="mx-auto h-12 w-12 text-gray-300"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <p class="mt-2 text-sm font-medium text-gray-900">暂无日志</p>
                  <p class="mt-1 text-sm text-gray-500">
                    请先发起一些 API 请求或调整筛选条件。
                  </p>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Footer/Pagination -->
      <div
        class="bg-gray-50 px-4 py-3 border-t border-gray-200 flex items-center justify-between sm:px-6"
      >
        <div
          class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between"
        >
          <div>
            <p class="text-sm text-gray-700">
              第 <span class="font-medium">{{ page }}</span> 页，共
              <span class="font-medium">{{ total }}</span> 条结果
            </p>
          </div>
          <div>
            <nav
              class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px"
              aria-label="Pagination"
            >
              <button
                :disabled="page <= 1"
                @click="
                  page--;
                  fetchLogs(false);
                "
                class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span class="sr-only">上一页</span>
                <svg
                  class="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M15 19l-7-7 7-7"
                  />
                </svg>
              </button>
              <button
                :disabled="logs.length < size"
                @click="
                  page++;
                  fetchLogs(false);
                "
                class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span class="sr-only">下一页</span>
                <svg
                  class="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </button>
            </nav>
          </div>
        </div>
      </div>
    </div>

    <!-- Log Detail Dialog -->
    <div
      v-if="showDetailDialog"
      class="fixed z-10 inset-0 overflow-y-auto"
      @click.self="showDetailDialog = false"
    >
      <div
        class="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0"
      >
        <div
          class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
        ></div>

        <div
          class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full"
        >
          <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <div class="flex items-start justify-between mb-4">
              <h3 class="text-lg leading-6 font-medium text-gray-900">
                日志详情
              </h3>
              <button
                @click="showDetailDialog = false"
                class="text-gray-400 hover:text-gray-500"
              >
                <svg
                  class="h-6 w-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <div v-if="logDetail" class="space-y-4">
              <!-- Basic Info -->
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700"
                    >Trace ID</label
                  >
                  <p class="mt-1 text-sm text-gray-900 font-mono">
                    {{ logDetail.trace_id }}
                  </p>
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700"
                    >用户名</label
                  >
                  <p class="mt-1 text-sm text-gray-900">
                    {{ logDetail.user_name }}
                  </p>
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700"
                    >请求方法</label
                  >
                  <p class="mt-1 text-sm text-gray-900 font-mono">
                    {{ logDetail.method }}
                  </p>
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700"
                    >状态码</label
                  >
                  <p class="mt-1 text-sm">
                    <span
                      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                      :class="{
                        'bg-green-100 text-green-800':
                          logDetail.status_code >= 200 &&
                          logDetail.status_code < 300,
                        'bg-yellow-100 text-yellow-800':
                          logDetail.status_code >= 300 &&
                          logDetail.status_code < 400,
                        'bg-red-100 text-red-800': logDetail.status_code >= 400,
                      }"
                    >
                      {{ logDetail.status_code }}
                    </span>
                  </p>
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700"
                    >客户端IP</label
                  >
                  <p class="mt-1 text-sm text-gray-900 font-mono">
                    {{ logDetail.client_ip || "-" }}
                  </p>
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700"
                    >处理时间</label
                  >
                  <p class="mt-1 text-sm text-gray-900">
                    {{ logDetail.process_time_ms?.toFixed(2) }} ms
                  </p>
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700"
                    >功能点</label
                  >
                  <p class="mt-1 text-sm">
                    <span
                      class="inline-flex items-center px-2.5 py-0.5 rounded border font-bold text-xs uppercase"
                      :class="getActionTypeColor(logDetail.action_type)"
                    >
                      {{ getActionTypeLabel(logDetail.action_type) }}
                    </span>
                  </p>
                </div>
                <div class="col-span-2">
                  <label class="block text-sm font-medium text-gray-700"
                    >接口路径</label
                  >
                  <p class="mt-1 text-sm text-gray-900 font-mono break-all">
                    {{ logDetail.endpoint }}
                  </p>
                </div>
                <div v-if="logDetail.source_sql" class="col-span-2">
                  <label class="block text-sm font-medium text-gray-700 mb-2">关联 SQL (溯源)</label>
                  <div class="bg-gray-900 rounded-md p-4 max-h-40 overflow-auto border border-gray-700">
                    <pre class="text-xs text-green-400 whitespace-pre-wrap font-mono">{{ logDetail.source_sql }}</pre>
                  </div>
                </div>
                <div class="col-span-2">
                  <label class="block text-sm font-medium text-gray-700"
                    >时间</label
                  >
                  <p class="mt-1 text-sm text-gray-900">
                    {{ formatDate(logDetail.created_at) }}
                  </p>
                </div>
              </div>

              <!-- Request Params -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >请求参数</label
                >
                <div class="bg-gray-50 rounded-md p-4 max-h-60 overflow-auto">
                  <pre
                    class="text-xs text-gray-800 whitespace-pre-wrap font-mono"
                    >{{ formatJSON(logDetail.request_params) }}</pre
                  >
                </div>
              </div>

              <!-- Response Body -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >响应内容</label
                >
                <div class="bg-gray-50 rounded-md p-4 max-h-60 overflow-auto">
                  <pre
                    class="text-xs text-gray-800 whitespace-pre-wrap font-mono"
                    >{{ formatJSON(logDetail.response_body) }}</pre
                  >
                </div>
              </div>

              <!-- Error Message -->
              <div v-if="logDetail.error_message">
                <label class="block text-sm font-medium text-red-700 mb-2"
                  >错误信息</label
                >
                <div
                  class="bg-red-50 border border-red-200 rounded-md p-4 max-h-40 overflow-auto"
                >
                  <pre
                    class="text-xs text-red-800 whitespace-pre-wrap font-mono"
                    >{{ logDetail.error_message }}</pre
                  >
                </div>
              </div>
            </div>

            <div v-else class="text-center py-8">
              <svg
                class="animate-spin h-8 w-8 mx-auto text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  class="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  stroke-width="4"
                ></circle>
                <path
                  class="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              <p class="mt-2 text-sm text-gray-500">加载中...</p>
            </div>
          </div>

          <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
            <button
              @click="showDetailDialog = false"
              class="w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 sm:ml-3 sm:w-auto sm:text-sm"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Export Dialog -->
    <div
      v-if="showExportDialog"
      class="fixed z-10 inset-0 overflow-y-auto"
      @click.self="showExportDialog = false"
    >
      <div
        class="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0"
      >
        <div
          class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
        ></div>

        <div
          class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full"
        >
          <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <div class="flex items-start justify-between mb-4">
              <h3 class="text-lg leading-6 font-medium text-gray-900">
                导出日志
              </h3>
              <button
                @click="showExportDialog = false"
                class="text-gray-400 hover:text-gray-500"
              >
                <svg
                  class="h-6 w-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2"
                  >导出格式</label
                >
                <div class="grid grid-cols-2 gap-3">
                  <button
                    @click="exportFormat = 'csv'"
                    class="flex items-center justify-center px-4 py-3 border rounded-md text-sm font-medium"
                    :class="
                      exportFormat === 'csv'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                    "
                  >
                    <svg
                      class="h-5 w-5 mr-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    CSV 格式
                  </button>
                  <button
                    @click="exportFormat = 'json'"
                    class="flex items-center justify-center px-4 py-3 border rounded-md text-sm font-medium"
                    :class="
                      exportFormat === 'json'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-300 text-gray-700 hover:bg-gray-50'
                    "
                  >
                    <svg
                      class="h-5 w-5 mr-2"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
                      />
                    </svg>
                    JSON 格式
                  </button>
                </div>
              </div>

              <div class="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                <div class="flex">
                  <svg
                    class="h-5 w-5 text-yellow-400"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                      clip-rule="evenodd"
                    />
                  </svg>
                  <div class="ml-3">
                    <p class="text-sm text-yellow-700">
                      导出将应用当前筛选条件，最多导出 10000 条记录。
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
            <button
              @click="exportLogs"
              :disabled="exporting"
              class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg
                v-if="exporting"
                class="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  class="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  stroke-width="4"
                ></circle>
                <path
                  class="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              {{ exporting ? "导出中..." : "开始导出" }}
            </button>
            <button
              @click="showExportDialog = false"
              class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none sm:mt-0 sm:w-auto sm:text-sm"
            >
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>