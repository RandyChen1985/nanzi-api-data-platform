<script setup lang="ts">
defineProps<{ open: boolean }>()
defineEmits<{ (e: 'close'): void }>()

const shortcuts = [
  { keys: 'Ctrl / Cmd + Enter', desc: '运行 SQL（有选中则运行选中，否则光标处语句）' },
  { keys: 'Tab', desc: '编辑器内缩进' },
  { keys: 'Esc', desc: '关闭弹窗 / 退出全屏' },
  { keys: '工具栏 · 运行', desc: '执行当前 SQL' },
  { keys: '工具栏 · 取消', desc: '中断进行中的查询' },
  { keys: '工具栏 · ⚡', desc: '查看 EXPLAIN 执行计划' },
  { keys: '工具栏 · 格式化', desc: '美化 SQL（保留 Jinja 标签）' },
  { keys: '工具栏 · 书签', desc: '打开「我的查询」云端保存' },
  { keys: '工具栏 · 片段', desc: '插入 SQL 片段库模板' },
  { keys: '工具栏 · 预设', desc: '切换参数预设组合' },
  { keys: '表头右键', desc: '复制整列数据' },
  { keys: '?', desc: '打开本快捷键面板' },
]
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-[130] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm" @click.self="$emit('close')">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
      <div class="px-6 py-4 border-b flex justify-between items-center">
        <h3 class="font-bold text-gray-800">快捷键与操作</h3>
        <button class="text-gray-400 hover:text-gray-600" @click="$emit('close')">✕</button>
      </div>
      <ul class="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
        <li v-for="(s, i) in shortcuts" :key="i" class="flex justify-between gap-4 text-sm py-2 border-b border-gray-50 last:border-0">
          <kbd class="px-2 py-1 bg-gray-100 rounded text-xs font-mono text-gray-700 shrink-0">{{ s.keys }}</kbd>
          <span class="text-gray-600 text-right">{{ s.desc }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>
