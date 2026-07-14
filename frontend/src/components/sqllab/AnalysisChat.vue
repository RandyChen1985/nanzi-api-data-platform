<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import {
  XMarkIcon,
  PaperAirplaneIcon,
  SparklesIcon,
  CommandLineIcon,
  DocumentDuplicateIcon,
  CheckIcon,
  ClockIcon,
  TrashIcon,
  StopIcon,
  ArrowPathIcon,
} from "@heroicons/vue/24/outline";
import { renderMarkdown } from "../../utils/markdown";
import axios from "@/utils/axios";
import { useToast } from "@/composables/useToast";
import { copyToClipboard as safeCopyToClipboard } from '@/utils/clipboard'
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

const { showToast } = useToast();
const showSessionPanel = ref(false);
const sessions = ref<{ id: number; title: string; sql_text?: string; created_at: string }[]>([]);
const sessionsLoading = ref(false);
const suppressAutoStart = ref(false);

const copiedId = ref<number | null>(null);
const copiedCodeId = ref<string | null>(null);
const copyToClipboard = async (text: string, idx: number) => {
  const success = await safeCopyToClipboard(text);
  if (success) {
    copiedId.value = idx;
    setTimeout(() => {
      copiedId.value = null;
    }, 2000);
  }
};

const copyCodeBlock = async (code: string, id: string) => {
  const success = await safeCopyToClipboard(code);
  if (success) {
    copiedCodeId.value = id;
    setTimeout(() => { copiedCodeId.value = null; }, 2000);
  }
};

const handleMarkdownClick = (e: MouseEvent) => {
  const btn = (e.target as HTMLElement).closest('.code-copy-btn') as HTMLElement | null;
  if (!btn) return;
  const wrap = btn.closest('.code-block-wrap');
  const codeEl = wrap?.querySelector('code');
  const id = btn.getAttribute('data-id') || '';
  if (codeEl) copyCodeBlock(codeEl.textContent || '', id);
};

const renderMessageHtml = (content: string) => {
  let html = renderMarkdown(content);
  let codeIdx = 0;
  html = html.replace(/<pre(?:[^>]*)><code class="([^"]*)">([\s\S]*?)<\/code><\/pre>/g, (_, classes, inner) => {
    const id = `code-${codeIdx++}`;
    const langMatch = classes.match(/language-([\w-]+)/);
    const lang = langMatch?.[1] || 'code';
    return `<div class="code-block-wrap"><div class="code-block-header"><span class="code-lang-tag">${lang.toUpperCase()}</span><button type="button" class="code-copy-btn" data-id="${id}">复制</button></div><pre class="hljs-code-block"><code class="${classes}">${inner}</code></pre></div>`;
  });
  return html;
};


// 记录上一次分析的 SQL，用于判断是否需要重置
const lastAnalyzedQuery = ref("");

const resetChat = () => {
  messages.value = [];
  lastAnalyzedQuery.value = props.initialQuery || "";
  suppressAutoStart.value = false;
};

const fetchSessions = async () => {
  sessionsLoading.value = true;
  try {
    const res = await axios.get("/api/portal/lab/analysis-sessions");
    sessions.value = res.data;
  } catch {
    showToast("加载历史会话失败", "error");
  } finally {
    sessionsLoading.value = false;
  }
};

const openSessionPanel = async () => {
  showSessionPanel.value = true;
  await fetchSessions();
};

const loadSession = async (sessionId: number) => {
  try {
    const res = await axios.get(`/api/portal/lab/analysis-sessions/${sessionId}`);
    const data = res.data;
    const msgs = normalizeLoadedMessages((data.messages_json || []) as Message[]);
    messages.value = msgs;
    lastAnalyzedQuery.value = data.sql_text || props.initialQuery || "";
    suppressAutoStart.value = true;
    showSessionPanel.value = false;
    showToast(`已加载「${data.title}」`, "success");
    scrollToBottom();
  } catch {
    showToast("加载会话失败", "error");
  }
};

const deleteSession = async (sessionId: number) => {
  try {
    await axios.delete(`/api/portal/lab/analysis-sessions/${sessionId}`);
    sessions.value = sessions.value.filter(s => s.id !== sessionId);
    showToast("已删除", "info");
  } catch {
    showToast("删除失败", "error");
  }
};

interface Message {
  role: "user" | "assistant";
  content: string;
  charts?: any[];
  suggestions?: string[];
  createdAt?: number;
}

const formatMessageTime = (ts?: number) => {
  if (!ts) return "";
  return new Date(ts).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const copyMessage = (msg: Message, idx: number) => {
  if (!msg.content?.trim()) return;
  copyToClipboard(msg.content, idx);
  showToast("已复制", "success");
};

const retryMessage = (idx: number) => {
  if (loading.value) return;

  let userIdx = idx;
  if (messages.value[idx]?.role === "assistant") {
    userIdx = idx - 1;
    while (userIdx >= 0 && messages.value[userIdx]?.role !== "user") userIdx--;
  }
  const userMsg = messages.value[userIdx];
  if (!userMsg || userMsg.role !== "user") return;

  const prompt = userMsg.content;
  messages.value = messages.value.slice(0, userIdx);
  sendMessage(prompt);
};

const isMessageStreaming = (idx: number) =>
  loading.value && idx === messages.value.length - 1 && messages.value[idx]?.role === "assistant";

const messages = ref<Message[]>([]);
const inputText = ref("");
const loading = ref(false);
const chatScrollRef = ref<HTMLElement | null>(null);
const chatAbortController = ref<AbortController | null>(null);

const stopGeneration = () => {
  if (!loading.value) return;
  chatAbortController.value?.abort();
};

const scrollToBottom = () => {
  nextTick(() => {
    if (chatScrollRef.value) {
      chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight;
    }
  });
};

const findJsonArrayEnd = (text: string, start: number): number => {
  if (text[start] !== '[') return -1
  let depth = 0
  let inString = false
  let escape = false
  for (let i = start; i < text.length; i++) {
    const ch = text[i]
    if (escape) {
      escape = false
      continue
    }
    if (ch === '\\' && inString) {
      escape = true
      continue
    }
    if (ch === '"') {
      inString = !inString
      continue
    }
    if (!inString) {
      if (ch === '[') depth++
      else if (ch === ']') {
        depth--
        if (depth === 0) return i
      }
    }
  }
  return -1
}

const parseSuggestionArray = (arrayStr: string): string[] => {
  const attempts = [
    arrayStr,
    arrayStr.replace(/'/g, '"'),
    arrayStr.replace(/,\s*]/g, ']'),
  ]
  for (const candidate of attempts) {
    try {
      const parsed = JSON.parse(candidate)
      if (Array.isArray(parsed)) {
        return parsed.map((s) => String(s).trim()).filter(Boolean)
      }
    } catch {
      // try next
    }
  }
  return []
}

const extractGuidedSuggestions = (content: string): { cleanContent: string; suggestions: string[] } => {
  const markerRegex = /\[Suggestions?:\s*/i
  const match = markerRegex.exec(content)
  if (!match) return { cleanContent: content, suggestions: [] }

  const arrayStart = match.index + match[0].length
  const arrayEnd = findJsonArrayEnd(content, arrayStart)
  if (arrayEnd === -1) return { cleanContent: content, suggestions: [] }

  const suggestions = parseSuggestionArray(content.slice(arrayStart, arrayEnd + 1))
  if (!suggestions.length) return { cleanContent: content, suggestions: [] }

  let removeEnd = arrayEnd + 1
  while (removeEnd < content.length && /\s/.test(content.charAt(removeEnd))) removeEnd++
  if (content.charAt(removeEnd) === ']') removeEnd++

  const cleanContent = (content.slice(0, match.index) + content.slice(removeEnd)).trim()
  return { cleanContent, suggestions }
}

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

  // 2. Extract guided suggestions — tolerate Suggestion/Suggestions and nested brackets
  const { cleanContent: withoutSuggestions, suggestions } = extractGuidedSuggestions(cleanContent);
  cleanContent = withoutSuggestions;

  return { content: cleanContent, charts, suggestions };
};

const normalizeLoadedMessages = (msgs: Message[]): Message[] =>
  msgs.map((msg) => {
    if (msg.role !== 'assistant' || !msg.content) return msg
    const parsed = parseMessageContent(msg.content)
    return {
      ...msg,
      content: parsed.content,
      charts: parsed.charts.length ? parsed.charts : msg.charts,
      suggestions: parsed.suggestions.length ? parsed.suggestions : msg.suggestions,
    }
  })

  const sendMessage = async (customPrompt?: string) => {
    const text = customPrompt || inputText.value.trim()
    if (!text || loading.value) return
  
    // 清除旧的引导建议，避免界面拥挤
    if (messages.value.length > 0) {
      const last = messages.value[messages.value.length - 1]
      if (last?.role === 'assistant') last.suggestions = []
    }
  
    if (!customPrompt) {
      messages.value.push({ role: 'user', content: text, createdAt: Date.now() })
      inputText.value = ''
    } else {
      messages.value.push({ role: 'user', content: text, createdAt: Date.now() })
    }
    
    loading.value = true
    scrollToBottom()
  
    const assistantMsgIndex = messages.value.length
    messages.value.push({ 
      role: 'assistant', 
      content: '', 
      charts: [],
      suggestions: [],
      createdAt: Date.now(),
    })

    chatAbortController.value?.abort()
    chatAbortController.value = new AbortController()
    const { signal } = chatAbortController.value
  
    try {
      // 限制发送给 AI 的数据量，防止 payload 过大导致 400 错误
      const contextObj = {
        sql: props.initialQuery,
        sample_data: props.data?.slice(0, 200), // 最多发送 200 行
        columns: props.columns
      }
      
      let contextStr = JSON.stringify(contextObj)
      // 如果上下文依然过长（超过 50KB 字符），进行物理截断
      if (contextStr.length > 50000) {
        contextStr = contextStr.substring(0, 50000) + "... [Data truncated due to size limit]"
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
        }),
        signal,
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
        if (signal.aborted) {
          await reader.cancel().catch(() => {})
          break
        }

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
      if (e?.name === 'AbortError' || signal.aborted) {
        const msg = messages.value[assistantMsgIndex]
        if (msg) {
          msg.content = msg.content
            ? `${msg.content}\n\n_[已中断生成]_`
            : '_[已中断生成]_'
        }
        showToast('已中断 AI 分析', 'info')
      } else if (messages.value[assistantMsgIndex]) {
        messages.value[assistantMsgIndex].content += `\n\n❌ 分析失败: ${e.message}`
      }
    } finally {
      chatAbortController.value = null
      loading.value = false
      scrollToBottom()
    }
  }

watch(
  () => props.initialQuery,
  (q, oldQ) => {
    if (q !== oldQ) suppressAutoStart.value = false
  },
);

watch(
  () => props.isOpen,
  (newVal) => {
    if (!newVal) {
      stopGeneration();
      return;
    }
    if (suppressAutoStart.value) return;
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
  },
);

onBeforeUnmount(() => {
  stopGeneration();
});

onMounted(() => {
  if (props.isOpen) {
    resetChat();
    sendMessage("请作为数据运营专家，根据这份查询结果提供核心洞察和建议。");
  }
});
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="fixed inset-0 z-[10000] flex justify-end">
      <!-- 遮罩：点击关闭，并突出右侧抽屉 -->
      <div
        class="absolute inset-0 bg-gray-900/45 backdrop-blur-[2px]"
        aria-hidden="true"
        @click="emit('close')"
      />

      <div
        class="relative h-full w-full md:w-[75%] max-w-5xl bg-white shadow-2xl flex flex-col border-l border-gray-200 animate-in slide-in-from-right duration-300"
      >
    <!-- Header -->
    <div class="p-4 border-b bg-gray-50 flex justify-between items-center">
      <div class="flex items-center gap-2">
        <SparklesIcon class="w-5 h-5 text-indigo-600" />
        <h3 class="font-bold text-gray-900">AI 数据专家分析</h3>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="openSessionPanel"
          class="px-3 py-1 text-xs font-bold text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-100 flex items-center gap-1"
        >
          <ClockIcon class="w-3.5 h-3.5" /> 历史会话
        </button>
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
            <div
              v-if="isMessageStreaming(idx) && !msg.content?.trim()"
              class="flex items-center gap-3 py-1"
            >
              <div class="flex gap-1">
                <div class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"></div>
                <div class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                <div class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.4s"></div>
              </div>
              <span class="text-xs text-gray-400 italic">正在思考并分析数据...</span>
            </div>
            <div
              v-else
              class="markdown-body prose prose-sm max-w-none break-words overflow-hidden"
              :class="msg.role === 'user' ? 'prose-invert' : 'prose-indigo'"
              @click="handleMarkdownClick"
              v-html="renderMessageHtml(msg.content)"
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

          <!-- 时间 / 复制 / 重试 -->
          <div
            v-if="(msg.content || msg.role === 'user') && !isMessageStreaming(idx)"
            class="mt-1.5 flex items-center gap-3 text-[10px] text-gray-400"
            :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
          >
            <span class="tabular-nums">{{ formatMessageTime(msg.createdAt) }}</span>
            <button
              v-if="msg.content?.trim()"
              type="button"
              class="inline-flex items-center gap-1 hover:text-indigo-600 transition-colors"
              @click="copyMessage(msg, idx)"
            >
              <component :is="copiedId === idx ? CheckIcon : DocumentDuplicateIcon" class="w-3 h-3" />
              {{ copiedId === idx ? '已复制' : '复制' }}
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1 hover:text-indigo-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="loading"
              @click="retryMessage(idx)"
            >
              <ArrowPathIcon class="w-3 h-3" />
              重试
            </button>
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
              :disabled="loading"
              class="px-3 py-1.5 bg-white text-indigo-600 hover:bg-indigo-50 rounded-full text-[11px] font-medium transition-all border border-indigo-100 shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {{ suggest }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Session History Panel -->
    <div
      v-if="showSessionPanel"
      class="absolute inset-0 z-10 bg-white/95 backdrop-blur-sm flex flex-col"
    >
      <div class="p-4 border-b flex justify-between items-center">
        <h4 class="font-bold text-gray-800 text-sm">历史分析会话</h4>
        <button class="text-gray-400 hover:text-gray-600" @click="showSessionPanel = false">
          <XMarkIcon class="w-5 h-5" />
        </button>
      </div>
      <div class="flex-1 overflow-y-auto p-3 custom-scrollbar">
        <div v-if="sessionsLoading" class="text-center py-8 text-gray-400 text-sm">加载中...</div>
        <div v-else-if="!sessions.length" class="text-center py-8 text-gray-400 text-sm">暂无保存的会话</div>
        <div
          v-for="s in sessions"
          :key="s.id"
          class="p-3 mb-2 rounded-xl border hover:border-indigo-200 hover:bg-indigo-50/30 flex justify-between items-center gap-2 group cursor-pointer"
          @click="loadSession(s.id)"
        >
          <div class="min-w-0 flex-1">
            <div class="font-bold text-sm text-gray-800 truncate">{{ s.title }}</div>
            <div class="text-[10px] text-gray-400 mt-0.5">{{ s.created_at }}</div>
          </div>
          <button
            class="p-1 text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 shrink-0"
            @click.stop="deleteSession(s.id)"
          >
            <TrashIcon class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>

    <!-- Input Area -->
    <div class="p-4 border-t bg-white">
      <div class="relative flex items-center">
        <textarea
          v-model="inputText"
          @keydown.enter.prevent="loading ? stopGeneration() : sendMessage()"
          placeholder="深入挖掘数据，例如：分析异常值原因..."
          rows="2"
          class="w-full pl-4 pr-12 py-3 border border-gray-200 rounded-2xl focus:ring-2 focus:ring-indigo-500 outline-none text-sm resize-none transition-all"
        ></textarea>
        <button
          v-if="loading"
          type="button"
          @click="stopGeneration"
          class="absolute right-2 p-2 bg-red-500 text-white rounded-xl hover:bg-red-600 transition-all shadow-md ring-2 ring-red-200"
          title="中断生成"
        >
          <StopIcon class="w-5 h-5" />
        </button>
        <button
          v-else
          type="button"
          @click="sendMessage()"
          :disabled="!inputText.trim()"
          class="absolute right-2 p-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-all shadow-md"
          title="发送"
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
    </div>
  </Teleport>
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
:deep(.prose h2), :deep(.prose h3), :deep(.prose h4) {
  margin-top: 1.5em;
  margin-bottom: 0.8em;
  font-weight: 800;
  color: #1e293b;
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 0.3em;
}
:deep(.prose blockquote) {
  margin: 0.75em 0;
  padding: 0.5em 0.75em;
  border-left: 3px solid #c7d2fe;
  background: #f8fafc;
  color: #64748b;
  font-size: 0.9em;
  border-radius: 0 0.375rem 0.375rem 0;
}
:deep(.prose blockquote p) {
  margin: 0;
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
:deep(.prose pre:not(.hljs-code-block)) {
  margin-top: 1em;
  margin-bottom: 1em;
  padding: 0;
  border-radius: 0.75rem;
}
:deep(.code-block-wrap) {
  margin: 0.85em 0;
  border-radius: 0.75rem;
  overflow: hidden;
  border: 1px solid #475569;
  background: #0f172a;
}
:deep(.code-block-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.35rem 0.75rem;
  background: #0f172a;
  border-bottom: 1px solid #334155;
}
:deep(.code-lang-tag) {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #94a3b8;
}
:deep(.code-copy-btn) {
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  padding: 0.15rem 0.5rem;
  border-radius: 0.375rem;
  border: 1px solid #475569;
  background: transparent;
  cursor: pointer;
}
:deep(.code-copy-btn:hover) {
  color: #e2e8f0;
  border-color: #64748b;
}
:deep(.hljs-code-block) {
  margin: 0 !important;
  padding: 0.85rem 1rem !important;
  overflow-x: auto;
  background: #0f172a !important;
  border-radius: 0 !important;
  font-size: 13px;
  line-height: 1.6;
}
:deep(.hljs-code-block code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  white-space: pre;
  color: #e2e8f0 !important;
  background: transparent !important;
}
/* 高对比度 SQL 语法色（覆盖 highlight.js 默认主题） */
:deep(.code-block-wrap .hljs) {
  color: #e2e8f0 !important;
  background: transparent !important;
}
:deep(.code-block-wrap .hljs-keyword) { color: #7dd3fc !important; font-weight: 600; }
:deep(.code-block-wrap .hljs-built_in) { color: #a5b4fc !important; }
:deep(.code-block-wrap .hljs-type) { color: #a5b4fc !important; }
:deep(.code-block-wrap .hljs-string) { color: #86efac !important; }
:deep(.code-block-wrap .hljs-number) { color: #fde047 !important; }
:deep(.code-block-wrap .hljs-literal) { color: #fde047 !important; }
:deep(.code-block-wrap .hljs-comment) { color: #94a3b8 !important; font-style: italic; }
:deep(.code-block-wrap .hljs-operator) { color: #f9a8d4 !important; }
:deep(.code-block-wrap .hljs-punctuation) { color: #cbd5e1 !important; }
:deep(.code-block-wrap .hljs-title) { color: #c4b5fd !important; }
:deep(.code-block-wrap .hljs-attr) { color: #fdba74 !important; }
:deep(.code-block-wrap .hljs-name) { color: #e2e8f0 !important; }
:deep(.code-block-wrap .hljs-symbol) { color: #fda4af !important; }
:deep(.prose table) {
  width: 100%;
  margin: 0.85em 0;
  font-size: 12px;
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
}
:deep(.prose thead) {
  background: #f8fafc;
}
:deep(.prose th) {
  padding: 0.5rem 0.75rem;
  text-align: left;
  font-weight: 700;
  color: #334155;
  border-bottom: 2px solid #e2e8f0;
  white-space: nowrap;
}
:deep(.prose td) {
  padding: 0.5rem 0.75rem;
  color: #475569;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: top;
  line-height: 1.5;
}
:deep(.prose tbody tr:hover) {
  background: #f8fafc;
}
:deep(.prose tbody tr:last-child td) {
  border-bottom: none;
}
</style>
