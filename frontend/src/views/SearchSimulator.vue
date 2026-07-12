<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { metadataV2Api, SEARCH_TYPES, type SearchType } from '../api/metadata_v2'
import axios from '../utils/axios'
import { useToast } from '../composables/useToast'
import VectorProcessDiagram from '../components/metadata/VectorProcessDiagram.vue'
import ClearableInput from '../components/common/ClearableInput.vue'

import { 
  CircleStackIcon, ChevronRightIcon, BeakerIcon, 
  BoltIcon, LanguageIcon, InformationCircleIcon,
  MagnifyingGlassIcon, ArrowPathIcon, SparklesIcon,
  DocumentTextIcon, ChevronDownIcon, ChevronUpIcon,
  CommandLineIcon, CodeBracketIcon, DocumentIcon,
  QuestionMarkCircleIcon
} from '@heroicons/vue/24/outline'

const query = ref('')

const selectedDataSource = ref('default')

const searchType = ref<SearchType>(SEARCH_TYPES.KEYWORD)
const enableRerank = ref(false)

const searching = ref(false)

const result = ref<any>(null)

const dataSources = ref<any[]>([])

const logsCollapsed = ref(false)
const activeResultTab = ref('yaml') // yaml | api
const isAiEnabled = ref(true)
const aiDisabledReason = ref('')
const isVectorSupported = ref(true)
const vectorDbWarning = ref('')
const showDiagram = ref(false)
const { showToast } = useToast()

const activeMainTab = ref('simulator') // simulator | browser

// Vector Browser State
const vectorList = ref<any[]>([])
const vectorTotal = ref(0)
const vectorPage = ref(1)
const vectorPageSize = ref(15)
const vectorLoading = ref(false)
const selectedDatasetId = ref<number | undefined>(undefined)
const datasets = ref<any[]>([])
const selectedVectorDetail = ref<any>(null)
const showDetailModal = ref(false)

const currentHost = computed(() => window.location.host)

const fetchVectorList = async () => {
  vectorLoading.value = true
  try {
    const res = await metadataV2Api.browseVectors({
      data_source: selectedDataSource.value,
      dataset_id: selectedDatasetId.value,
      page: vectorPage.value,
      page_size: vectorPageSize.value
    })
    vectorList.value = res.data.items
    vectorTotal.value = res.data.total
  } catch (e) {
    showToast('获取向量列表失败', 'error')
  } finally {
    vectorLoading.value = false
  }
}

const viewVectorDetail = async (key: string) => {
  try {
    const res = await metadataV2Api.getVectorDetails(key)
    selectedVectorDetail.value = res.data
    showDetailModal.value = true
  } catch (e) {
    showToast('获取向量详情失败', 'error')
  }
}

const fetchDatasets = async () => {
  try {
    const res = await metadataV2Api.getDatasets()
    datasets.value = res.data
  } catch (e) {
    console.error('Failed to fetch datasets')
  }
}

const checkVectorSupport = async () => {
  try {
    const res = await axios.post('/api/portal/system/test-connection/vector')
    isVectorSupported.value = res.data.status === 'success'
    
    // Check for DB 0 warning in logs
    if (res.data.logs) {
      const dbLog = res.data.logs.find((log: string) => log.includes('DB') && log.includes('0'))
      if (dbLog) {
        vectorDbWarning.value = dbLog
      }
    }

    if (!isVectorSupported.value) {
      if (searchType.value === SEARCH_TYPES.SEMANTIC) {
        searchType.value = SEARCH_TYPES.KEYWORD
      }
    }
  } catch (e) {
    isVectorSupported.value = false
  }
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    showToast('内容已成功复制到剪贴板', 'success')
  } catch (e) {
    showToast('复制失败，请手动选择复制', 'error')
  }
}

// 搜索原理说明

const searchPrinciples: Record<SearchType, string> = {

  [SEARCH_TYPES.KEYWORD]: '基于数据库的物理表名、字段名、业务术语、描述以及指标公式进行模糊匹配 (SQL LIKE)。适用于已知具体名称或术语的精确查找。',

  [SEARCH_TYPES.SEMANTIC]: '【实验性】利用 Embedding 向量化技术，对自然语言问题进行语义偏移计算，召回意图最接近的元数据上下文。即使名称不匹配，只要含义相近即可召回。'

}



const currentPrinciple = computed(() => searchPrinciples[searchType.value])



const checkAiStatus = async () => {

  try {

    const res = await axios.get('/api/portal/system/config/ai')

    const config = res.data

    const enabled = String(config.enabled).toLowerCase() === 'true'

    const hasModels = !!(config.embed_model && config.rerank_model)

    

    if (!enabled) {

      isAiEnabled.value = false

      aiDisabledReason.value = 'AI 未开启'

    } else if (!hasModels) {

      isAiEnabled.value = false

      aiDisabledReason.value = '模型配置不全'

    } else {

      isAiEnabled.value = true

      aiDisabledReason.value = ''

    }

  } catch (e) {

    isAiEnabled.value = false

    aiDisabledReason.value = '配置加载失败'

  }

}



const fetchDataSources = async () => {

  try {

    const res = await axios.get('/api/portal/datasource/datasources?status=active')

    dataSources.value = res.data

    if (dataSources.value.length > 0) {

      selectedDataSource.value = dataSources.value[0].source_name

    }

  } catch (e) {

    console.error('Failed to fetch data sources')

  }

}



onMounted(() => {

  checkAiStatus()
  checkVectorSupport()

  fetchDataSources()
  fetchDatasets()
})

// Watch for tab change to fetch data
import { watch } from 'vue'
watch(activeMainTab, (newTab) => {
  if (newTab === 'browser' && vectorList.value.length === 0) {
    fetchVectorList()
  }
})

watch([selectedDataSource, selectedDatasetId], () => {
  if (activeMainTab.value === 'browser') {
    vectorPage.value = 1
    fetchVectorList()
  }
})

const handleSearch = async () => {

  if (!query.value.trim() || !selectedDataSource.value) return

  searching.value = true

  result.value = null

  

  try {

    const res = await metadataV2Api.searchMetadata({

      query: query.value,

      data_source: selectedDataSource.value,

      search_type: searchType.value,
      
      enable_rerank: enableRerank.value

    })
    
    if (res && res.data) {
        result.value = {
          found: res.data.count > 0,
          count: res.data.count,
          yaml: res.data.data,
          debug_logs: res.data.debug_logs
        }
    } else {
        showToast('检索响应异常', 'error')
    }
  } catch (e) {
    console.error(e)
  } finally {
    searching.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Breadcrumbs -->
    <nav class="flex mb-4 text-xs" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-2 text-gray-400">
        <li>
          <router-link to="/dashboard/metadata" class="hover:text-indigo-600 transition-colors flex items-center gap-1">
            <CircleStackIcon class="w-3.5 h-3.5" />
            元数据中心
          </router-link>
        </li>
        <li class="flex items-center gap-2">
          <ChevronRightIcon class="w-3 h-3 text-gray-300" />
          <span class="text-gray-900 font-bold">检索模拟器</span>
        </li>
      </ol>
    </nav>

    <!-- Page Header -->
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-3">
        <div class="p-2 bg-indigo-600 rounded-lg text-white">
          <BeakerIcon class="w-6 h-6" />
        </div>
        <div>
          <h1 class="text-xl font-bold text-gray-900">检索模拟器</h1>
          <p class="text-xs text-gray-500">验证 AI Agent 如何从元数据库中召回语义上下文 (RAG)</p>
        </div>
      </div>
      
      <!-- Selection Controls -->
      <div class="flex items-center gap-4">
        <!-- Main Tab Switcher -->
        <div class="flex bg-gray-100 p-1 rounded-lg">
          <button 
            @click="activeMainTab = 'simulator'"
            :class="activeMainTab === 'simulator' ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'"
            class="px-4 py-1.5 text-xs font-bold rounded-md transition-all flex items-center gap-2"
          >
            <MagnifyingGlassIcon class="w-3.5 h-3.5" /> 检索测试
          </button>
          <button 
            @click="activeMainTab = 'browser'"
            :class="activeMainTab === 'browser' ? 'bg-white shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'"
            class="px-4 py-1.5 text-xs font-bold rounded-md transition-all flex items-center gap-2"
          >
            <CircleStackIcon class="w-3.5 h-3.5" /> Redis 向量浏览器
          </button>
        </div>

        <div class="flex items-center bg-white border border-gray-200 rounded-lg px-3 py-1.5 gap-2">
          <CircleStackIcon class="w-4 h-4 text-gray-400" />
          <select 
            v-model="selectedDataSource"
            class="bg-transparent border-none text-xs font-bold text-gray-700 focus:ring-0 p-0 pr-6"
          >
            <option v-for="ds in dataSources" :key="ds.id" :value="ds.source_name">
              数据源: {{ ds.source_name }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <!-- Vector DB Warning -->
    <div v-if="isAiEnabled && isVectorSupported && vectorDbWarning" class="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-r-lg flex items-start gap-3 animate-in fade-in slide-in-from-top-2 duration-300">
      <div class="flex-shrink-0">
        <InformationCircleIcon class="h-5 w-5 text-blue-400" aria-hidden="true" />
      </div>
      <div>
        <p class="text-sm text-blue-700 font-bold">Redis DB 配置风险提示</p>
        <p class="text-xs text-blue-600 mt-1">
          {{ vectorDbWarning }}
          <br>当前环境仅建议将 <code class="bg-blue-100 px-1 py-0.5 rounded font-mono">REDIS_DB</code> 设置为 0 以保证向量索引功能正常。
        </p>
      </div>
    </div>

    <!-- Simulator View -->
    <div v-if="activeMainTab === 'simulator'" class="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <!-- Left Controls (4 cols) -->
      <div class="lg:col-span-4 space-y-6">
        <!-- Search Mode Card -->
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div class="px-4 py-3 border-b bg-gray-50 flex items-center gap-2">
            <DocumentTextIcon class="w-4 h-4 text-gray-400" />
            <span class="text-xs font-bold text-gray-700">检索策略配置</span>
          </div>
          <div class="p-4 space-y-3">
            <button 
              @click="searchType = SEARCH_TYPES.KEYWORD"
              :class="searchType === SEARCH_TYPES.KEYWORD ? 'border-indigo-600 bg-indigo-50 text-indigo-700' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'"
              class="w-full flex items-center justify-between p-3 border rounded-lg transition-all text-left"
            >
              <div class="flex items-center gap-3">
                <BoltIcon class="w-4 h-4" />
                <span class="font-bold text-sm">关键词搜索</span>
              </div>
              <div v-if="searchType === SEARCH_TYPES.KEYWORD" class="w-1.5 h-1.5 bg-indigo-600 rounded-full"></div>
            </button>
            <button 
              @click="(isAiEnabled && isVectorSupported) ? (searchType = SEARCH_TYPES.SEMANTIC) : null"
              :disabled="!isAiEnabled || !isVectorSupported"
              :class="[
                searchType === SEARCH_TYPES.SEMANTIC ? 'border-indigo-600 bg-indigo-50 text-indigo-700' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50',
                (!isAiEnabled || !isVectorSupported) ? 'opacity-50 cursor-not-allowed grayscale' : ''
              ]"
              class="w-full flex items-center justify-between p-3 border rounded-lg transition-all text-left relative group/sem"
            >
              <div class="flex items-center gap-3">
                <LanguageIcon class="w-4 h-4" />
                <span class="font-bold text-sm">语义搜索</span>
              </div>
              <div class="flex items-center gap-1.5">
                <span v-if="!isAiEnabled" class="text-[8px] px-1 py-0.5 bg-gray-100 text-gray-400 rounded border border-gray-200 font-bold">{{ aiDisabledReason }}</span>
                <span v-else-if="!isVectorSupported" class="text-[8px] px-1 py-0.5 bg-amber-50 text-amber-600 rounded border border-amber-200 font-bold">Redis 不支持</span>
                <span class="text-[9px] px-1.5 py-0.5 rounded font-black border" :class="searchType === SEARCH_TYPES.SEMANTIC ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-gray-100 text-gray-400 border-gray-200'">ALPHA</span>
                
                <!-- Diagram Help Button -->
                <div @click.stop="showDiagram = true" class="p-1 hover:bg-indigo-200 rounded-full transition-colors cursor-pointer" title="查看向量检索原理">
                  <QuestionMarkCircleIcon class="w-4 h-4" :class="searchType === SEARCH_TYPES.SEMANTIC ? 'text-indigo-600' : 'text-gray-400'" />
                </div>
              </div>
            </button>
            
            <!-- Rerank Toggle (Nested under Semantic) -->
            <div v-if="searchType === SEARCH_TYPES.SEMANTIC && isAiEnabled && isVectorSupported" class="ml-4 pl-4 border-l-2 border-indigo-100 py-1 transition-all animate-in slide-in-from-top-2">
               <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                     <span class="text-xs font-bold text-indigo-900">启用 Rerank 精排</span>
                     <span class="bg-amber-100 text-amber-700 text-[8px] px-1 rounded font-bold">SLOW</span>
                  </div>
                  <button 
                    @click="enableRerank = !enableRerank"
                    class="relative inline-flex h-4 w-7 items-center rounded-full transition-colors duration-200 ease-in-out focus:outline-none"
                    :class="enableRerank ? 'bg-indigo-600' : 'bg-gray-300'"
                  >
                    <span 
                      class="inline-block h-3 w-3 transform rounded-full bg-white transition-transform duration-200 ease-in-out shadow-sm"
                      :class="enableRerank ? 'translate-x-3.5' : 'translate-x-0.5'"
                    />
                  </button>
               </div>
               <p class="text-[10px] text-gray-400 mt-1 leading-relaxed">
                  先召回 Top-15 向量，再使用 Cross-Encoder 模型进行二次打分，显著提升准确率。
               </p>
            </div>
          </div>
        </div>

        <!-- Principle Explanation -->
        <div class="bg-indigo-50/50 border border-indigo-100 rounded-xl p-4">
          <div class="flex items-center gap-2 text-indigo-600 mb-2">
            <InformationCircleIcon class="w-4 h-4" />
            <span class="text-[10px] font-bold uppercase tracking-wider">原理说明</span>
          </div>
          <p class="text-xs text-indigo-700/70 leading-relaxed font-medium">
            {{ currentPrinciple }}
          </p>
        </div>
      </div>

      <!-- Right Content (8 cols) -->
      <div class="lg:col-span-8 space-y-6">
        <!-- Search Input Card -->
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-2 flex items-center gap-2">
          <ClearableInput
            v-model="query"
            show-search-icon
            wrapper-class="flex-1 border-0 shadow-none focus-within:ring-0"
            input-class="py-3 text-sm font-medium placeholder:text-gray-400"
            placeholder="请输入您的业务问题、表名或指标关键字..."
            @keyup.enter="handleSearch"
          />
          <button 
            @click="handleSearch" :disabled="searching || !query"
            class="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-bold shadow-sm transition-all active:scale-95 disabled:opacity-50 flex items-center gap-2 text-sm"
          >
            <ArrowPathIcon v-if="searching" class="w-4 h-4 animate-spin" />
            <SparklesIcon v-else class="w-4 h-4" />
            <span>{{ searching ? '正在检索...' : '执行模拟检索' }}</span>
          </button>
        </div>

        <!-- Results Display -->
        <div v-if="result" class="space-y-6">
          
          <!-- Debug Logs / Retrieval Path (Always Show if logs exist) -->
          <div v-if="result.debug_logs && result.debug_logs.length > 0" class="bg-slate-900 rounded-xl border border-slate-800 shadow-inner transition-all duration-300">
              <div 
                @click="logsCollapsed = !logsCollapsed"
                class="px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-slate-800/50 transition-colors rounded-t-xl"
              >
                <div class="flex items-center gap-3">
                  <div class="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse"></div>
                  <h4 class="text-[10px] font-black text-gray-400 uppercase tracking-widest">检索路径分析 (Retrieval Path Analysis)</h4>
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-[9px] text-slate-500 font-bold uppercase">{{ logsCollapsed ? '展开日志' : '折叠' }}</span>
                  <ChevronDownIcon v-if="logsCollapsed" class="w-4 h-4 text-slate-500" />
                  <ChevronUpIcon v-else class="w-4 h-4 text-slate-500" />
                </div>
              </div>
              
              <div v-show="!logsCollapsed" class="px-8 pb-6 space-y-2.5 font-mono text-[11px] border-t border-slate-800/50 pt-4">
                <div v-for="(log, lIdx) in result.debug_logs" :key="lIdx" class="flex gap-4 group">
                  <span class="text-slate-600 opacity-60 tabular-nums w-4 text-right">{{ Number(lIdx) + 1 }}</span>
                  <p class="text-slate-300 leading-normal">{{ log }}</p>
                </div>
              </div>
          </div>

          <div v-if="result.found" class="space-y-6">
            <!-- Summary Bar -->
            <div class="flex items-center justify-between px-4 py-3 bg-emerald-50 border border-emerald-100 rounded-lg">
              <div class="flex items-center gap-3">
                <div class="p-1.5 bg-emerald-500 text-white rounded-md">
                  <SparklesIcon class="w-4 h-4" />
                </div>
                <span class="text-sm font-bold text-emerald-900">成功召回 {{ result.count }} 个语义对象</span>
              </div>
              <span class="text-[10px] font-bold text-emerald-600 uppercase">Recall Status: OK</span>
            </div>

            <!-- Tab Header -->
            <div class="flex items-center gap-1 border-b border-gray-200">
               <button 
                  @click="activeResultTab = 'yaml'"
                  :class="activeResultTab === 'yaml' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-400 hover:text-gray-600'"
                  class="px-6 py-3 border-b-2 font-bold text-xs transition-all flex items-center gap-2"
               >
                  <CommandLineIcon class="w-4 h-4" /> 语义上下文 (YAML)
               </button>
               <button 
                  @click="activeResultTab = 'api'"
                  :class="activeResultTab === 'api' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-400 hover:text-gray-600'"
                  class="px-6 py-3 border-b-2 font-bold text-xs transition-all flex items-center gap-2"
               >
                  <CodeBracketIcon class="w-4 h-4" /> API 集成指南
               </button>
            </div>

            <div class="bg-white rounded-b-xl border border-gray-200 border-t-0 shadow-sm overflow-hidden flex flex-col">
              <!-- YAML Tab Content -->
              <div v-if="activeResultTab === 'yaml'">
                <div class="px-4 py-3 border-b bg-gray-50/50 flex items-center justify-between">
                  <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Metadata Context for LLM</span>
                  <button @click="copyToClipboard(result.yaml)" class="text-[10px] font-bold text-indigo-600 hover:text-indigo-800 transition-colors uppercase">复制 YAML</button>
                </div>
                <div class="bg-white p-4">
                  <textarea 
                    readonly
                    class="w-full h-[400px] bg-slate-50 border border-gray-100 rounded-lg p-4 font-mono text-xs text-slate-700 leading-relaxed outline-none resize-none custom-scrollbar shadow-inner"
                    :value="result.yaml"
                  ></textarea>
                </div>
              </div>

              <!-- API Guide Tab Content -->
              <div v-else class="p-8 space-y-6">
                 <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div class="space-y-4">
                       <h5 class="text-sm font-bold text-gray-900 flex items-center gap-2">
                          <DocumentIcon class="w-4 h-4 text-indigo-600" /> 接口详情
                       </h5>
                       <div class="bg-gray-50 rounded-lg p-4 space-y-3">
                          <div class="flex items-center justify-between">
                             <span class="text-xs text-gray-500">请求方法</span>
                             <span class="text-xs font-black text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">POST</span>
                          </div>
                          <div class="flex items-center justify-between">
                             <span class="text-xs text-gray-500">端点 (V1)</span>
                             <span class="text-xs font-mono font-bold text-gray-700">/api/v1/meta/search</span>
                          </div>
                          <div class="flex items-center justify-between">
                             <span class="text-xs text-gray-500">认证方式</span>
                             <span class="text-xs font-bold text-amber-600">X-API-Key (Header)</span>
                          </div>
                       </div>
                       
                       <div class="space-y-2">
                          <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">参数说明</p>
                          <table class="w-full text-xs">
                             <tr class="border-b"><td class="py-2 text-gray-500">query</td><td class="py-2 font-bold text-gray-700">检索关键词/自然语言问题</td></tr>
                             <tr class="border-b"><td class="py-2 text-gray-500">data_source</td><td class="py-2 font-bold text-gray-700">指定数据源编码 (默认: default)</td></tr>
                             <tr><td class="py-2 text-gray-500">search_type</td><td class="py-2 font-bold text-gray-700">keyword (关键词) | semantic (语义)</td></tr>
                          </table>
                       </div>
                    </div>

                    <div class="space-y-4">
                       <h5 class="text-sm font-bold text-gray-900 flex items-center gap-2">
                          <CodeBracketIcon class="w-4 h-4 text-indigo-600" /> 代码示例 (cURL)
                       </h5>
                       <div class="bg-slate-900 rounded-xl p-4 relative group">
                          <pre class="text-[11px] text-cyan-400 font-mono leading-relaxed overflow-x-auto whitespace-pre-wrap">curl -X POST "http://{{ currentHost }}/api/v1/meta/search" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{{ query || '销售额' }}",
    "data_source": "{{ selectedDataSource }}",
    "search_type": "{{ searchType }}"
  }'</pre>
                       </div>
                       <p class="text-[10px] text-gray-400 leading-normal italic">
                          * 将该接口返回的 `data` (YAML) 拼接到您的 LLM Prompt 中，即可让 AI 获得实时的业务语义背景。
                       </p>
                    </div>
                 </div>
              </div>
            </div>
          </div>

          <!-- Empty State -->
          <div v-else class="text-center py-16 bg-white rounded-xl border border-dashed border-gray-300">
            <div class="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4 text-gray-300 border border-gray-100">
              <MagnifyingGlassIcon class="w-8 h-8" />
            </div>
            <p class="text-sm font-bold text-gray-500 italic">未能在数据源 [{{ selectedDataSource }}] 中找到匹配的语义资产</p>
            <p class="text-[10px] text-gray-400 mt-2 uppercase tracking-widest">请尝试不同的关键词或完善元数据定义</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Vector Browser View -->
    <div v-else class="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div class="px-6 py-4 border-b bg-gray-50 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <CommandLineIcon class="w-5 h-5 text-indigo-600" />
            <div>
              <h3 class="text-sm font-bold text-gray-900">Redis 向量库浏览器</h3>
              <p class="text-[10px] text-gray-500">直接查看存储在 Redis 中的元数据向量与片段</p>
            </div>
          </div>
          
          <div class="flex items-center gap-3">
             <div class="flex items-center bg-white border border-gray-200 rounded-lg px-3 py-1.5 gap-2">
                <span class="text-[10px] font-bold text-gray-400 uppercase">数据集过滤:</span>
                <select 
                  v-model="selectedDatasetId"
                  class="bg-transparent border-none text-xs font-bold text-gray-700 focus:ring-0 p-0 pr-6"
                >
                  <option :value="undefined">全部数据集</option>
                  <option v-for="ds in datasets" :key="ds.id" :value="ds.id">
                    {{ ds.display_name || ds.name }} (ID: {{ ds.id }})
                  </option>
                </select>
              </div>
              <button 
                @click="fetchVectorList"
                class="p-2 text-gray-400 hover:text-indigo-600 transition-colors"
                title="刷新"
              >
                <ArrowPathIcon class="w-5 h-5" :class="{ 'animate-spin': vectorLoading }" />
              </button>
          </div>
        </div>

        <!-- Vector Table -->
        <div class="overflow-x-auto">
          <table class="w-full text-left">
            <thead class="bg-gray-50 text-[10px] font-black text-gray-400 uppercase tracking-widest">
              <tr>
                <th class="px-6 py-3 border-b border-gray-100">类型/名称</th>
                <th class="px-6 py-3 border-b border-gray-100">数据集 ID</th>
                <th class="px-6 py-3 border-b border-gray-100">业务术语 (Term)</th>
                <th class="px-6 py-3 border-b border-gray-100">数据源</th>
                <th class="px-6 py-3 border-b border-gray-100">最后同步</th>
                <th class="px-6 py-3 border-b border-gray-100 text-right">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-if="vectorLoading && vectorList.length === 0">
                <td colspan="6" class="px-6 py-12 text-center text-gray-400 italic text-sm">正在加载向量库数据...</td>
              </tr>
              <tr v-else-if="vectorList.length === 0">
                <td colspan="6" class="px-6 py-12 text-center text-gray-400 italic text-sm">Redis 中暂无匹配的向量数据</td>
              </tr>
              <tr 
                v-for="item in vectorList" 
                :key="item.key"
                class="hover:bg-indigo-50/30 transition-colors group"
              >
                <td class="px-6 py-4">
                  <div class="flex items-center gap-3">
                    <div :class="item.type === 'table' ? 'bg-blue-100 text-blue-600' : 'bg-purple-100 text-purple-600'" class="p-1.5 rounded">
                      <CircleStackIcon v-if="item.type === 'table'" class="w-4 h-4" />
                      <BoltIcon v-else class="w-4 h-4" />
                    </div>
                    <div>
                      <div class="text-xs font-bold text-gray-900">{{ item.name }}</div>
                      <div class="text-[9px] text-gray-400 font-mono">{{ item.key }}</div>
                    </div>
                  </div>
                </td>
                <td class="px-6 py-4">
                  <span class="text-xs font-mono font-bold text-gray-500">#{{ item.dataset_id }}</span>
                </td>
                <td class="px-6 py-4">
                  <span class="text-xs text-gray-600">{{ item.term || '-' }}</span>
                </td>
                <td class="px-6 py-4">
                  <span class="text-[10px] font-bold text-gray-400 uppercase">{{ item.data_source }}</span>
                </td>
                <td class="px-6 py-4">
                  <span class="text-[10px] text-gray-400 font-mono">{{ item.updated_at || '-' }}</span>
                </td>
                <td class="px-6 py-4 text-right">
                  <button 
                    @click="viewVectorDetail(item.key)"
                    class="text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
                  >
                    详情
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div class="px-6 py-4 bg-gray-50 flex items-center justify-between border-t border-gray-100">
           <span class="text-[10px] font-bold text-gray-400">共 {{ vectorTotal }} 条向量记录</span>
           <div class="flex items-center gap-2">
              <button 
                :disabled="vectorPage <= 1"
                @click="vectorPage--; fetchVectorList()"
                class="p-1 rounded hover:bg-white border border-transparent hover:border-gray-200 disabled:opacity-30"
              >
                <ChevronRightIcon class="w-4 h-4 rotate-180" />
              </button>
              <span class="text-xs font-bold text-gray-700">{{ vectorPage }}</span>
              <button 
                :disabled="vectorPage * vectorPageSize >= vectorTotal"
                @click="vectorPage++; fetchVectorList()"
                class="p-1 rounded hover:bg-white border border-transparent hover:border-gray-200 disabled:opacity-30"
              >
                <ChevronRightIcon class="w-4 h-4" />
              </button>
           </div>
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <div v-if="showDetailModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
       <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" @click="showDetailModal = false"></div>
       <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
          <div class="px-6 py-4 border-b flex items-center justify-between bg-gray-50/50">
             <div class="flex items-center gap-3">
                <div class="p-2 bg-indigo-600 rounded-lg text-white">
                  <DocumentIcon class="w-5 h-5" />
                </div>
                <div>
                   <h3 class="text-sm font-bold text-gray-900">Redis 向量元数据详情</h3>
                   <p class="text-[10px] text-gray-500 font-mono">{{ selectedVectorDetail?.dataset_id }} / {{ selectedVectorDetail?.name }}</p>
                </div>
             </div>
             <button @click="showDetailModal = false" class="text-gray-400 hover:text-gray-600 transition-colors">
                <ArrowPathIcon class="w-6 h-6 rotate-45" />
             </button>
          </div>
          
          <div class="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
             <div class="grid grid-cols-2 gap-4">
                <div v-for="(val, key) in selectedVectorDetail" :key="key" v-show="key !== 'content' && key !== 'vector'">
                   <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block mb-1">{{ key }}</label>
                   <div class="text-sm font-bold text-gray-700 bg-gray-50 px-3 py-2 rounded-lg border border-gray-100">{{ val }}</div>
                </div>
             </div>
             
             <div class="space-y-2">
                <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">向量化内容 (YAML Fragment)</label>
                <div class="bg-slate-900 rounded-xl p-4 relative group">
                   <button 
                     @click="copyToClipboard(selectedVectorDetail?.content)"
                     class="absolute top-3 right-3 text-[10px] font-bold text-slate-500 hover:text-cyan-400 opacity-0 group-hover:opacity-100 transition-all uppercase"
                   >
                     Copy
                   </button>
                   <pre class="text-[11px] text-cyan-400 font-mono leading-relaxed overflow-x-auto whitespace-pre-wrap">{{ selectedVectorDetail?.content }}</pre>
                </div>
             </div>

             <div class="bg-amber-50 border border-amber-100 rounded-lg p-4 flex gap-3">
                <InformationCircleIcon class="w-5 h-5 text-amber-500 shrink-0" />
                <p class="text-[10px] text-amber-700 leading-relaxed">
                   <strong>提示：</strong> 以上内容是 Redis 中存储的原始片段。语义搜索时，系统会计算输入 Query 与此内容对应向量的距离。如果召回不符合预期，通常需要优化这里的业务描述或 YAML 结构。
                </p>
             </div>
          </div>
          
          <div class="px-6 py-4 border-t bg-gray-50/50 flex justify-end">
             <button @click="showDetailModal = false" class="px-6 py-2 bg-white border border-gray-200 rounded-lg text-xs font-bold text-gray-600 hover:bg-gray-50 transition-all">关闭</button>
          </div>
       </div>
    </div>

    <VectorProcessDiagram :show="showDiagram" @close="showDiagram = false" />
  </div>
</template>

<style scoped>
/* 移除了一些不必要的复杂样式 */
</style>