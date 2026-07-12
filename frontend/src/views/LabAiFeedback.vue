<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from '../utils/axios'
import { useToast } from '../composables/useToast'
import ClearableInput from '../components/common/ClearableInput.vue'
import {
  HandThumbUpIcon, HandThumbDownIcon, EyeIcon, XMarkIcon,
} from '@heroicons/vue/24/outline'

const { showToast } = useToast()

interface FeedbackItem {
  id: number
  user_id: number
  user_name?: string
  source_id?: number
  source_name?: string
  prompt?: string
  generated_sql?: string
  rating: number
  execution_success: number
  created_at: string
}

interface FeedbackStats {
  total: number
  up_count: number
  down_count: number
  exec_success_count: number
  satisfaction_rate: number
}

const userInfo = ref<any>(null)
const items = ref<FeedbackItem[]>([])
const stats = ref<FeedbackStats | null>(null)
const loading = ref(false)
const page = ref(1)
const size = ref(20)
const total = ref(0)

const ratingFilter = ref('')
const userNameFilter = ref('')
const startTime = ref('')
const endTime = ref('')

const detailItem = ref<FeedbackItem | null>(null)

const canManageAll = computed(() => {
  if (userInfo.value?.role === 'admin') return true
  return userInfo.value?.permissions?.elements?.includes('element:lab:feedback:manage')
})

const fetchList = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/portal/lab/ai/feedback', {
      params: {
        page: page.value,
        size: size.value,
        include_stats: true,
        rating: ratingFilter.value ? Number(ratingFilter.value) : undefined,
        user_name: canManageAll.value && userNameFilter.value ? userNameFilter.value : undefined,
        start_time: startTime.value || undefined,
        end_time: endTime.value || undefined,
      },
    })
    items.value = res.data.items || []
    total.value = res.data.total || 0
    stats.value = res.data.statistics || null
  } catch (e: any) {
    showToast(e.response?.data?.detail || '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  ratingFilter.value = ''
  userNameFilter.value = ''
  startTime.value = ''
  endTime.value = ''
  page.value = 1
  fetchList()
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))

const goPage = (p: number) => {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  fetchList()
}

const truncate = (s: string, n: number) => (s.length > n ? s.slice(0, n) + '…' : s)

onMounted(() => {
  try {
    userInfo.value = JSON.parse(localStorage.getItem('user_info') || '{}')
  } catch {
    userInfo.value = {}
  }
  fetchList()
})
</script>

<template>
  <div class="space-y-6 max-w-[1400px] mx-auto">
    <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">AI 反馈管理</h1>
        <p class="text-sm text-gray-500 mt-1">SQL 实验室 AI 生成 SQL 的点赞/点踩记录，用于质量复盘与优化。</p>
      </div>
      <router-link
        to="/dashboard/lab"
        class="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
      >前往 SQL 实验室 →</router-link>
    </div>

    <div v-if="stats" class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
        <div class="text-xs font-bold text-gray-400 uppercase tracking-wider">反馈总数</div>
        <div class="text-2xl font-black text-gray-900 mt-1">{{ stats.total }}</div>
      </div>
      <div class="bg-white rounded-xl border border-emerald-100 p-4 shadow-sm">
        <div class="text-xs font-bold text-emerald-600 uppercase tracking-wider flex items-center gap-1">
          <HandThumbUpIcon class="w-3.5 h-3.5" /> 满意
        </div>
        <div class="text-2xl font-black text-emerald-700 mt-1">{{ stats.up_count }}</div>
      </div>
      <div class="bg-white rounded-xl border border-amber-100 p-4 shadow-sm">
        <div class="text-xs font-bold text-amber-600 uppercase tracking-wider flex items-center gap-1">
          <HandThumbDownIcon class="w-3.5 h-3.5" /> 待改进
        </div>
        <div class="text-2xl font-black text-amber-700 mt-1">{{ stats.down_count }}</div>
      </div>
      <div class="bg-white rounded-xl border border-indigo-100 p-4 shadow-sm">
        <div class="text-xs font-bold text-indigo-600 uppercase tracking-wider">满意度</div>
        <div class="text-2xl font-black text-indigo-700 mt-1">{{ stats.satisfaction_rate }}%</div>
      </div>
    </div>

    <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
        <select
          v-model="ratingFilter"
          class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
          @change="page = 1; fetchList()"
        >
          <option value="">全部评价</option>
          <option value="2">满意 👍</option>
          <option value="1">待改进 👎</option>
        </select>
        <ClearableInput
          v-if="canManageAll"
          v-model="userNameFilter"
          placeholder="用户名..."
          input-class="px-3 py-2 text-sm"
          @keyup.enter="page = 1; fetchList()"
        />
        <input
          v-model="startTime"
          type="datetime-local"
          class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
          @change="page = 1; fetchList()"
        />
        <input
          v-model="endTime"
          type="datetime-local"
          class="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
          @change="page = 1; fetchList()"
        />
        <div class="flex gap-2">
          <button
            type="button"
            class="flex-1 px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-bold hover:bg-indigo-700"
            @click="page = 1; fetchList()"
          >查询</button>
          <button
            type="button"
            class="px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
            @click="resetFilters"
          >重置</button>
        </div>
      </div>
      <p v-if="!canManageAll" class="text-xs text-gray-400 mt-2">当前仅显示您本人的反馈记录。</p>
    </div>

    <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div v-if="loading" class="p-12 text-center text-gray-500">加载中...</div>
      <div v-else-if="items.length === 0" class="p-12 text-center text-gray-400">暂无反馈数据</div>
      <div v-else class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200 text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase">时间</th>
              <th v-if="canManageAll" class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase">用户</th>
              <th class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase">评价</th>
              <th class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase">执行</th>
              <th class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase">数据源</th>
              <th class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase min-w-[200px]">Prompt</th>
              <th class="px-4 py-3 text-right text-xs font-bold text-gray-500 uppercase">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="row in items" :key="row.id" class="hover:bg-gray-50/80">
              <td class="px-4 py-3 whitespace-nowrap text-gray-600 font-mono text-xs">{{ row.created_at }}</td>
              <td v-if="canManageAll" class="px-4 py-3 whitespace-nowrap font-medium text-gray-800">{{ row.user_name || row.user_id }}</td>
              <td class="px-4 py-3 whitespace-nowrap">
                <span
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold"
                  :class="row.rating === 2 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'"
                >
                  <HandThumbUpIcon v-if="row.rating === 2" class="w-3.5 h-3.5" />
                  <HandThumbDownIcon v-else class="w-3.5 h-3.5" />
                  {{ row.rating === 2 ? '满意' : '待改进' }}
                </span>
              </td>
              <td class="px-4 py-3 whitespace-nowrap">
                <span
                  class="text-xs font-semibold"
                  :class="row.execution_success ? 'text-emerald-600' : 'text-gray-400'"
                >{{ row.execution_success ? '成功' : '未成功/未试跑' }}</span>
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-gray-600">{{ row.source_name || '—' }}</td>
              <td class="px-4 py-3 text-gray-600 max-w-xs truncate" :title="row.prompt">{{ truncate(row.prompt || '—', 60) }}</td>
              <td class="px-4 py-3 text-right">
                <button
                  type="button"
                  class="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 text-xs font-bold"
                  @click="detailItem = row"
                >
                  <EyeIcon class="w-4 h-4" /> 详情
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="total > size" class="px-4 py-3 border-t bg-gray-50 flex items-center justify-between text-sm">
        <span class="text-gray-500">共 {{ total }} 条</span>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="px-3 py-1 border rounded-lg disabled:opacity-40"
            :disabled="page <= 1"
            @click="goPage(page - 1)"
          >上一页</button>
          <span class="text-gray-600">{{ page }} / {{ totalPages }}</span>
          <button
            type="button"
            class="px-3 py-1 border rounded-lg disabled:opacity-40"
            :disabled="page >= totalPages"
            @click="goPage(page + 1)"
          >下一页</button>
        </div>
      </div>
    </div>

    <div
      v-if="detailItem"
      class="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm"
      @click.self="detailItem = null"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[88vh] overflow-hidden flex flex-col">
        <div class="px-5 py-4 border-b flex justify-between items-center">
          <div>
            <h3 class="font-bold text-gray-900">反馈详情 #{{ detailItem.id }}</h3>
            <p class="text-xs text-gray-500 mt-0.5">{{ detailItem.created_at }} · {{ detailItem.user_name || detailItem.user_id }}</p>
          </div>
          <button class="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100" @click="detailItem = null">
            <XMarkIcon class="w-5 h-5" />
          </button>
        </div>
        <div class="flex-1 overflow-y-auto p-5 space-y-4 custom-scrollbar">
          <div>
            <div class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">用户 Prompt</div>
            <p class="text-sm text-gray-800 bg-gray-50 rounded-xl p-3 border whitespace-pre-wrap">{{ detailItem.prompt || '—' }}</p>
          </div>
          <div>
            <div class="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">生成的 SQL</div>
            <pre class="text-xs font-mono bg-[#1e1e1e] text-emerald-400 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap max-h-[360px]">{{ detailItem.generated_sql || '—' }}</pre>
          </div>
          <div class="flex flex-wrap gap-3 text-xs">
            <span class="px-2 py-1 rounded-lg bg-gray-100 text-gray-700">数据源：{{ detailItem.source_name || '—' }}</span>
            <span
              class="px-2 py-1 rounded-lg font-bold"
              :class="detailItem.rating === 2 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'"
            >{{ detailItem.rating === 2 ? '满意' : '待改进' }}</span>
            <span class="px-2 py-1 rounded-lg bg-gray-100 text-gray-700">
              试跑：{{ detailItem.execution_success ? '成功' : '未成功/未试跑' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
