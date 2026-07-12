<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { metadataV2Api } from '../../api/metadata_v2'
import request from '../../utils/axios'
import { 
  PlusIcon, PencilSquareIcon, TrashIcon, XMarkIcon, 
  BoltIcon, SparklesIcon, UserIcon, ClockIcon
} from '@heroicons/vue/24/outline'
import SmartMetricModal from './SmartMetricModal.vue'
import ClearableInput from '../common/ClearableInput.vue'
import { useToast } from '../../composables/useToast'

const props = defineProps<{
  datasetId: number
}>()

const emit = defineEmits(['show-smart-discovery', 'saved'])
const { showToast } = useToast()

// 权限检查辅助函数
const hasPerm = (code: string) => {
  const userInfoStr = localStorage.getItem('user_info')
  if (!userInfoStr) return false
  const user = JSON.parse(userInfoStr)
  if (user.role === 'admin') return true
  const perms = user.permissions?.elements || []
  return perms.includes(code)
}

const metrics = ref<any[]>([])
const loading = ref(false)
const showModal = ref(false)
const showSmartModal = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const searchQuery = ref('')
const isAiEnabled = ref(true)
const dismissAiWarning = ref(false)

const checkAiStatus = async () => {
  try {
    const res = await request.get('/api/portal/system/config/ai')
    isAiEnabled.value = String(res.data.enabled).toLowerCase() === 'true'
  } catch (e) {
    isAiEnabled.value = false
  }
}

const filteredMetrics = computed(() => {
  if (!searchQuery.value) return metrics.value
  const q = searchQuery.value.toLowerCase()
  return metrics.value.filter((m: any) =>
    m.display_name.toLowerCase().includes(q) ||
    m.name.toLowerCase().includes(q) ||
    (m.description && m.description.toLowerCase().includes(q))
  )
})
// Delete State
const showDeleteConfirm = ref(false)
const deletingMetricId = ref<number | null>(null)

// Form State
const form = ref({
  id: undefined as number | undefined,
  name: '',
  display_name: '',
  description: '',
  calculation_logic: '',
  unit: ''
})

const fetchMetrics = async () => {
  loading.value = true
  try {
    const res = await metadataV2Api.getDataset(props.datasetId)
    // Extract from res.data
    metrics.value = res.data.metrics || []
  } catch (e) {
    console.error('Failed to fetch metrics', e)
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingId.value = null
  form.value = { id: undefined, name: '', display_name: '', description: '', calculation_logic: '', unit: '' }
  showModal.value = true
}

const openEdit = (m: any) => {
  editingId.value = m.id || null
  form.value = { 
    id: m.id,
    name: m.name,
    display_name: m.display_name,
    description: m.description,
    calculation_logic: m.calculation_logic,
    unit: m.unit
  }
  showModal.value = true
}

const handleSave = async () => {
  if (!form.value.display_name) {
    showToast('请输入指标显示名称', 'error')
    return
  }
  if (!form.value.name) {
    showToast('请输入指标编码 (英文名)', 'error')
    return
  }
  if (!form.value.calculation_logic) {
    showToast('请输入 SQL 计算逻辑', 'error')
    return
  }
  
  saving.value = true
  try {
    await metadataV2Api.createMetric(props.datasetId, form.value)
    showModal.value = false
    fetchMetrics()
    emit('saved')
    showToast(editingId.value ? '指标已更新' : '指标已保存', 'success')
  } catch (e) {
    showToast('保存失败', 'error')
  } finally {
    saving.value = false
  }
}

const handleDelete = (metricId: number) => {
  deletingMetricId.value = metricId
  showDeleteConfirm.value = true
}

const confirmDelete = async () => {
  if (!deletingMetricId.value) return
  try {
    await metadataV2Api.deleteMetric(props.datasetId, deletingMetricId.value)
    showToast('指标已删除', 'success')
    showDeleteConfirm.value = false
    deletingMetricId.value = null
    fetchMetrics()
    emit('saved')
  } catch (e) {
    showToast('删除失败', 'error')
  }
}

watch(() => props.datasetId, fetchMetrics)
onMounted(() => {
  fetchMetrics()
  checkAiStatus()
})

const handleSmartMetricSaved = () => {
  fetchMetrics()
  emit('saved')
}

defineExpose({ fetchMetrics })
</script>

<template>
  <div class="space-y-6">
    <!-- Toolbar -->
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 px-2">
      <div>
        <h3 class="text-xl font-black text-gray-900 tracking-tight">业务指标库</h3>
        <p class="text-[10px] text-gray-400 font-bold uppercase tracking-widest mt-0.5">Defined analytical metrics & calculations</p>
      </div>
      
      <div class="flex flex-1 items-center gap-3 w-full md:w-auto">
        <ClearableInput
          v-model="searchQuery"
          show-search-icon
          wrapper-class="flex-1 md:w-64"
          input-class="py-2 text-sm font-medium bg-gray-50"
          placeholder="搜索指标名称、编码或描述..."
        />
        <button 
          v-if="hasPerm('element:metadata:manage')"
          @click="showSmartModal = true"
          :disabled="!isAiEnabled"
          class="bg-white hover:bg-gray-50 text-indigo-600 border border-indigo-200 px-4 py-2 rounded-lg transition-all flex items-center gap-2 text-sm font-bold shadow-sm whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <SparklesIcon class="w-4 h-4" /> 智能发现
        </button>
        <button 
          v-if="hasPerm('element:metadata:manage')"
          @click="openCreate"
          class="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg transition shadow-md flex items-center gap-2 text-sm font-bold active:scale-95 whitespace-nowrap"
        >
          <PlusIcon class="w-4 h-4" /> 新建指标
        </button>
      </div>
    </div>

    <!-- AI Warning if disabled -->
    <div v-if="!isAiEnabled && !dismissAiWarning" class="bg-amber-50 border border-amber-100 p-3 rounded-2xl flex items-center justify-between gap-2 text-amber-700 text-xs mx-2 animate-in fade-in slide-in-from-top-1">
       <div class="flex items-center gap-2">
          <SparklesIcon class="w-4 h-4" />
          <span>AI 功能未开启，无法使用“智能发现”功能。请先在系统设置中启用 AI。</span>
       </div>
       <button @click="dismissAiWarning = true" class="text-amber-400 hover:text-amber-600 transition-colors p-0.5">
          <XMarkIcon class="w-4 h-4" />
       </button>
    </div>

    <!-- List -->
    <div v-if="loading" class="flex justify-center py-20">
      <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-amber-500"></div>
    </div>
    
    <div v-else-if="metrics.length === 0" class="text-center py-32 bg-amber-50/30 rounded-[2.5rem] border-4 border-dashed border-amber-100">
      <div class="text-5xl mb-4 grayscale opacity-30">📉</div>
      <p class="text-amber-700 font-black">暂无定义的业务指标</p>
      <p class="text-xs text-amber-600/60 mt-2">添加指标可以帮助 AI 自动处理复杂的 SQL 聚合逻辑</p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
       <div v-for="m in filteredMetrics" :key="m.id" class="bg-white p-6 rounded-3xl border border-gray-100 shadow-sm hover:shadow-xl transition-all group relative">
          <div v-if="hasPerm('element:metadata:manage')" class="absolute top-6 right-6 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
             <button @click="openEdit(m)" class="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all"><PencilSquareIcon class="w-5 h-5" /></button>
             <button @click="handleDelete(m.id)" class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all"><TrashIcon class="w-5 h-5" /></button>
          </div>
          
          <div class="flex items-center gap-4 mb-4">
             <div class="w-12 h-12 rounded-2xl bg-amber-50 flex items-center justify-center text-amber-600 shadow-inner">
                <BoltIcon class="w-6 h-6" />
             </div>
             <div>
                <h4 class="font-black text-gray-900">{{ m.display_name }}</h4>
                <p class="text-[10px] font-mono text-gray-400 uppercase tracking-widest">#{{ m.name }}</p>
             </div>
          </div>
          
          <div class="space-y-4">
             <div class="bg-gray-900 rounded-2xl p-4 relative overflow-hidden">
                <div class="absolute top-0 right-0 p-2 text-[8px] font-black text-gray-700 uppercase tracking-widest">SQL Logic</div>
                <code class="text-[11px] text-amber-400 font-mono break-all leading-relaxed">{{ m.calculation_logic || '--' }}</code>
             </div>
             <p class="text-xs text-gray-500 line-clamp-2 leading-relaxed italic">"{{ m.description || '无详细口径描述' }}"</p>
             
             <div class="flex items-center justify-between pt-2 border-t border-gray-50">
                <div v-if="m.unit" class="flex items-center gap-2">
                   <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest">Unit</span>
                   <span class="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-[10px] font-bold border border-gray-200">{{ m.unit }}</span>
                </div>
                <div class="flex items-center gap-3 text-[9px] text-gray-400 font-medium ml-auto">
                   <div class="flex items-center gap-1">
                      <UserIcon class="w-3.5 h-3.5 text-indigo-400/60" />
                      <span>{{ m.creator_name || '系统' }}</span>
                   </div>
                   <div class="flex items-center gap-1 border-l border-gray-100 pl-3">
                      <ClockIcon class="w-3.5 h-3.5 text-gray-300" />
                      <span>{{ m.created_at ? new Date(m.created_at).toLocaleDateString() : '长期' }}</span>
                   </div>
                </div>
             </div>
          </div>
       </div>
    </div>

    <!-- Create/Edit Modal (Aligned Style) -->
    <div v-if="showModal" class="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
       <div class="bg-white rounded-3xl shadow-2xl w-full max-w-2xl overflow-hidden animate-in zoom-in duration-200 flex flex-col">
          <div class="px-8 py-6 border-b bg-gray-50 flex justify-between items-center">
             <div class="flex items-center gap-3">
                <div class="p-2.5 bg-indigo-600 rounded-xl text-white shadow-md"><PlusIcon class="w-5 h-5" /></div>
                <h3 class="text-xl font-bold text-gray-900">{{ editingId ? '编辑业务指标' : '定义业务指标' }}</h3>
             </div>
             <button @click="showModal = false" class="text-gray-400 hover:text-gray-600 transition-colors"><XMarkIcon class="w-6 h-6" /></button>
          </div>
          
          <div class="p-8 space-y-5 bg-white">
             <div class="grid grid-cols-2 gap-6">
                <div>
                   <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1.5 ml-1">指标显示名称</label>
                   <input v-model="form.display_name" class="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" placeholder="如：总收入" />
                </div>
                <div>
                   <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1.5 ml-1">指标编码 (英文名)</label>
                   <input v-model="form.name" class="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm font-mono focus:ring-2 focus:ring-indigo-500 outline-none transition-all" placeholder="total_revenue" />
                </div>
             </div>

             <div>
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1.5 ml-1">SQL 计算逻辑</label>
                <textarea v-model="form.calculation_logic" rows="3" class="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-xs font-mono bg-gray-50 focus:bg-white focus:ring-2 focus:ring-indigo-500 outline-none transition-all" placeholder="sum(amount * price)"></textarea>
             </div>

             <div class="grid grid-cols-2 gap-6">
                <div>
                   <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1.5 ml-1">单位 (Unit)</label>
                   <input v-model="form.unit" class="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all" placeholder="元 / % / 个" />
                </div>
             </div>

             <div>
                <label class="block text-[10px] font-bold text-gray-400 uppercase mb-1.5 ml-1">口径描述</label>
                <textarea v-model="form.description" rows="2" class="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-xs focus:ring-2 focus:ring-indigo-500 outline-none transition-all" placeholder="描述该指标的统计口径和业务意义..."></textarea>
             </div>
          </div>

          <div class="px-8 py-6 bg-gray-50 border-t flex justify-end gap-3">
             <button @click="showModal = false" class="px-6 py-2 text-gray-500 font-bold hover:text-gray-700 transition-colors text-sm">取消</button>
             <button @click="handleSave" :disabled="saving" class="px-10 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 text-sm">
                {{ saving ? '保存中...' : '确认并保存' }}
             </button>
          </div>
       </div>
    </div>

    <SmartMetricModal 
      :show="showSmartModal" 
      :dataset-id="props.datasetId" 
      @close="showSmartModal = false" 
      @saved="handleSmartMetricSaved" 
    />

    <!-- Delete Confirmation Modal -->
    <div v-if="showDeleteConfirm" class="fixed inset-0 z-[300] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden transform transition-all animate-in zoom-in duration-200">
        <div class="p-6 text-center">
          <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 mb-4">
            <TrashIcon class="h-6 w-6 text-red-600" />
          </div>
          <h3 class="text-lg leading-6 font-bold text-gray-900 mb-2">确认删除业务指标?</h3>
          <p class="text-sm text-gray-500 mb-6 leading-relaxed">
            此操作将永久移除该计算口径，<br/><span class="text-red-500 font-bold">不可撤销</span>。
          </p>
          <div class="flex gap-3">
            <button @click="showDeleteConfirm = false" class="flex-1 py-2.5 bg-gray-100 text-gray-700 font-bold rounded-lg hover:bg-gray-200 transition-all text-sm">取消</button>
            <button @click="confirmDelete" class="flex-1 py-2.5 bg-red-600 text-white font-bold rounded-lg hover:bg-red-700 shadow-lg transition-all text-sm">确认删除</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
