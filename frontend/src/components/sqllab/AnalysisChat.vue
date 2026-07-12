<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from "vue";
import {
  XMarkIcon,
  PaperAirplaneIcon,
  SparklesIcon,
  CommandLineIcon,
  DocumentDuplicateIcon,
  CheckIcon
} from "@heroicons/vue/24/outline";
import MarkdownIt from "markdown-it";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from "echarts/components";

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
]);

const props = defineProps<{
  isOpen: boolean;
  initialQuery?: string;
  data?: any[][];
  columns?: { name: string; type: string }[];
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "save-session", payload: { title: string; messages: Message[] }): void;
}>();

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
});

const copiedId = ref<number | null>(null);
const copyToClipboard = (text: string, idx: number) => {
  navigator.clipboard.writeText(text);
  copiedId.value = idx;
  setTimeout(() => {
    copiedId.value = null;
  }, 2000);
};


// 记录上一次分析的 SQL，用于判断是否需要重置
const lastAnalyzedQuery = ref("");

const resetChat = () => {
  messages.value = [];
  lastAnalyzedQuery.value = props.initialQuery || "";
};

interface Message {
  role: "user" | "assistant";
  content: string;
  charts?: any[]; // 支持多个图表
  suggestions?: string[]; // 引导追问建议
}

const messages = ref<Message[]>([]);
const inputText = ref("");
const loading = ref(false);
const chatScrollRef = ref<HTMLElement | null>(null);

const scrollToBottom = () => {
  nextTick(() => {
    if (chatScrollRef.value) {
      chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight;
    }
  });
};

const parseMessageContent = (content: string) => {
  let cleanContent = content;

  // 1. Extract all ECharts JSONs
  const chartRegex = /```chart\s*(\{[\s\S]*?\})\s*```/g;
  const charts: any[] = [];
  const chartMatches = [...content.matchAll(chartRegex)];
  for (const match of chartMatches) {
    if (match[1]) {
      try {
        charts.push(JSON.parse(match[1]));
      } catch (e) {
        console.error("Chart parse error", e);
      }
    }
  }
  cleanContent = cleanContent.replace(chartRegex, "").trim();

  // 2. Extract [Suggestions: ["...", "..."]]
  const suggestRegex = /\[Suggestions:\s*(\[[\s\S]*?\])\]/;
  let suggestions: string[] = [];
  const suggestMatch = cleanContent.match(suggestRegex);
  if (suggestMatch && suggestMatch[1]) {
    try {
      suggestions = JSON.parse(suggestMatch[1]);
    } catch (e) {
      console.error("Suggestions parse error", e);
    }
  }
  cleanContent = cleanContent.replace(suggestRegex, "").trim();

  return { content: cleanContent, charts, suggestions };
};

  const sendMessage = async (customPrompt?: string) => {
    const text = customPrompt || inputText.value.trim()
    if (!text || loading.value) return
  
    // 清除旧的引导建议，避免界面拥挤
    if (messages.value.length > 0) {
      const last = messages.value[messages.value.length - 1]
      if (last?.role === 'assistant') last.suggestions = []
    }
  
    if (!customPrompt) {
      messages.value.push({ role: 'user', content: text })
      inputText.value = ''
    } else {
      messages.value.push({ role: 'user', content: text })
    }
    
    loading.value = true
    scrollToBottom()
  
    const assistantMsgIndex = messages.value.length
    messages.value.push({ 
      role: 'assistant', 
      content: '', 
      charts: [],
      suggestions: []
    })
  
    try {
      // 限制发送给 AI 的数据量，防止 payload 过大导致 400 错误
      const contextObj = {
        sql: props.initialQuery,
        sample_data: props.data?.slice(0, 100), // 最多发送 100 行
        columns: props.columns
      }
      
      let contextStr = JSON.stringify(contextObj)
      // 如果上下文依然过长（超过 30KB 字符），进行物理截断
      if (contextStr.length > 30000) {
        contextStr = contextStr.substring(0, 30000) + "... [Data truncated due to size limit]"
      }
  
      const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
      const apiKey = localStorage.getItem("api_key") || "";
  
      const response = await fetch(`${API_BASE}/api/portal/lab/ai/chat-analysis`, {
        method: 'POST',
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey
        },
        body: JSON.stringify({
          prompt: text,
          context: contextStr
        })
      })
  
      if (!response.ok) {
         let errDetail = ""
         try {
           errDetail = await response.text()
         } catch (e) {
           errDetail = "Could not read error body"
         }
         throw new Error(`HTTP ${response.status}: ${errDetail}`)
      }

      if (!response.body) throw new Error('ReadableStream not yet supported by browser.')
  
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let rawAccumulatedContent = ''
  
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
            break
        }
        
        const chunk = decoder.decode(value, { stream: true })
        rawAccumulatedContent += chunk
        
        const parsed = parseMessageContent(rawAccumulatedContent)
        
        if (messages.value[assistantMsgIndex]) {
          messages.value[assistantMsgIndex].content = parsed.content
          messages.value[assistantMsgIndex].charts = parsed.charts
          messages.value[assistantMsgIndex].suggestions = parsed.suggestions
        }
        
        scrollToBottom()
      }
    } catch (e: any) {
      if (messages.value[assistantMsgIndex]) {
        messages.value[assistantMsgIndex].content += `\n\n❌ 分析失败: ${e.message}`
      }
    } finally {
      loading.value = false
      scrollToBottom()
    }
  }

watch(
  () => props.isOpen,
  (newVal) => {
    if (newVal) {
      // 如果 SQL 变化了，或者还没有任何消息，则重置并开始新分析
      if (
        props.initialQuery !== lastAnalyzedQuery.value ||
        messages.value.length === 0
      ) {
        resetChat();
        sendMessage(
          "请作为数据运营专家，根据这份最新的查询结果提供核心洞察和建议。如果适合可视化，请在回复中包含图表。",
        );
      }
    }
  },
);

onMounted(() => {
  if (props.isOpen) {
    resetChat();
    sendMessage("请作为数据运营专家，根据这份查询结果提供核心洞察和建议。");
  }
});
</script>

<template>
  <div
    v-if="isOpen"
    class="fixed inset-y-0 right-0 w-full md:w-[75%] bg-white shadow-2xl z-[10000] flex flex-col border-l border-gray-200 animate-in slide-in-from-right duration-300"
  >
    <!-- Header -->
    <div class="p-4 border-b bg-gray-50 flex justify-between items-center">
      <div class="flex items-center gap-2">
        <SparklesIcon class="w-5 h-5 text-indigo-600" />
        <h3 class="font-bold text-gray-900">AI 数据专家分析</h3>
      </div>
      <div class="flex items-center gap-2">
        <button
          v-if="messages.length > 0"
          @click="emit('save-session', { title: `分析 ${new Date().toLocaleString()}`, messages })"
          class="px-3 py-1 text-xs font-bold text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50"
        >保存会话</button>
        <button
          @click="emit('close')"
          class="p-1 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-200 transition-all"
        >
          <XMarkIcon class="w-6 h-6" />
        </button>
      </div>
    </div>

    <!-- Chat Area -->
    <div ref="chatScrollRef" class="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar bg-[#f8fafc] relative">
      <div class="absolute inset-0 opacity-[0.03] pointer-events-none bg-[url('https://www.transparenttextures.com/patterns/cubes.png')]"></div>
      
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        :class="msg.role === 'user' ? 'flex flex-row-reverse items-start gap-3' : 'flex flex-row items-start gap-3'"
      >
        <!-- Avatar -->
        <div 
          :class="[
            'w-9 h-9 rounded-xl flex items-center justify-center shrink-0 shadow-sm border',
            msg.role === 'user' ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-white border-gray-200 text-indigo-600'
          ]"
        >
          <CommandLineIcon v-if="msg.role === 'user'" class="w-5 h-5" />
          <SparklesIcon v-else class="w-5 h-5" />
        </div>

        <!-- Message Bubble Container -->
        <div :class="['flex flex-col max-w-[85%]', msg.role === 'user' ? 'items-end' : 'items-start']">
          <div 
            :class="[
              'rounded-2xl px-4 py-2.5 shadow-sm text-sm leading-relaxed group relative border transition-all',
              msg.role === 'user' 
                ? 'bg-indigo-600 border-indigo-500 text-white rounded-tr-none' 
                : 'bg-white border-gray-100 text-gray-800 rounded-tl-none assistant-bubble hover:border-indigo-100'
            ]"
          >
            <!-- Message-level Copy Button (Restored) -->
            <button
              v-if="msg.role === 'assistant' && msg.content"
              @click.stop="copyToClipboard(msg.content, idx)"
              class="absolute -top-3 -right-3 p-1.5 bg-white border border-gray-200 rounded-lg shadow-md text-gray-400 hover:text-indigo-600 opacity-0 group-hover:opacity-100 transition-all z-20"
              title="复制完整回复"
            >
              <component :is="copiedId === idx ? CheckIcon : DocumentDuplicateIcon" class="w-3.5 h-3.5" />
            </button>

            <div
              class="markdown-body prose prose-sm max-w-none break-words overflow-hidden"
              :class="msg.role === 'user' ? 'prose-invert' : 'prose-indigo'"
              v-html="md.render(msg.content)"
            ></div>

            <!-- Chart Components -->
            <div v-if="msg.charts && msg.charts.length > 0" class="space-y-4 mt-4">
              <div
                v-for="(chartConfig, cIdx) in msg.charts"
                :key="cIdx"
                class="bg-white rounded-xl border border-gray-100 p-2 h-72 w-full overflow-hidden shadow-inner"
              >
                <v-chart class="h-full w-full" :option="chartConfig" autoresize />
              </div>
            </div>
          </div>

          <!-- Guided Suggestions -->
          <div
            v-if="msg.suggestions && msg.suggestions.length > 0"
            class="mt-3 flex flex-wrap gap-2"
          >
            <button
              v-for="suggest in msg.suggestions"
              :key="suggest"
              @click="sendMessage(suggest)"
              class="px-3 py-1.5 bg-white text-indigo-600 hover:bg-indigo-50 rounded-full text-[11px] font-medium transition-all border border-indigo-100 shadow-sm"
            >
              {{ suggest }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="loading && !messages[messages.length-1]?.content" class="flex items-start gap-3">
        <div class="w-9 h-9 rounded-xl bg-white border border-gray-200 text-indigo-600 flex items-center justify-center shadow-sm">
          <SparklesIcon class="w-5 h-5 animate-pulse" />
        </div>
        <div class="bg-white border border-gray-100 rounded-2xl p-4 rounded-tl-none shadow-sm flex items-center gap-3">
          <div class="flex gap-1">
            <div class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"></div>
            <div class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
            <div class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.4s"></div>
          </div>
          <span class="text-xs text-gray-400 italic">正在思考并分析数据...</span>
        </div>
      </div>
    </div>

    <!-- Input Area -->
    <div class="p-4 border-t bg-white">
      <div class="relative flex items-center">
        <textarea
          v-model="inputText"
          @keydown.enter.prevent="sendMessage()"
          placeholder="深入挖掘数据，例如：分析异常值原因..."
          rows="2"
          class="w-full pl-4 pr-12 py-3 border border-gray-200 rounded-2xl focus:ring-2 focus:ring-indigo-500 outline-none text-sm resize-none transition-all"
        ></textarea>
        <button
          @click="sendMessage()"
          :disabled="!inputText.trim() || loading"
          class="absolute right-2 p-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-all shadow-md"
        >
          <PaperAirplaneIcon class="w-5 h-5" />
        </button>
      </div>
      <p
        class="mt-2 text-[10px] text-gray-400 text-center uppercase tracking-tighter font-black italic"
      >
        Powered by AI Data Insight Engine
      </p>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 10px;
}

/* Assistant Bubble Specific Styles */
.assistant-bubble {
  background-color: #ffffff;
  border-color: #f1f5f9;
}

/* Markdown Spacing & Table Styling */
:deep(.prose) {
  max-width: 100%;
}
:deep(.prose p) {
  margin-top: 0.75em;
  margin-bottom: 0.75em;
  line-height: 1.6;
}
:deep(.prose h2), :deep(.prose h3) {
  margin-top: 1.5em;
  margin-bottom: 0.8em;
  font-weight: 800;
  color: #1e293b;
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 0.3em;
}
:deep(.prose ul), :deep(.prose ol) {
  margin-top: 0.75em;
  margin-bottom: 0.75em;
  padding-left: 1.5em;
}
:deep(.prose li) {
  margin-top: 0.25em;
  margin-bottom: 0.25em;
}
:deep(.prose pre) {
  margin-top: 1em;
  margin-bottom: 1em;
  padding: 0;
  border-radius: 0.75rem;
}
</style>
