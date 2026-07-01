<script setup lang="ts">
import { computed } from 'vue'
import {
  diffFieldList,
  diffLines,
  formatScalarValue,
  isListField,
  isTextField,
  lineDiffSummary,
  listDiffSummary,
  propLabel,
  type FieldItem,
} from '@/utils/resourceDiff'

export type DiffItem = {
  field: string
  label: string
  current_value: unknown
  version_value: unknown
}

const props = defineProps<{
  versionNo: number
  items: DiffItem[]
}>()

defineEmits<{ close: [] }>()

const kindMeta = {
  added: { label: '新增', class: 'bg-green-100 text-green-700' },
  removed: { label: '删除', class: 'bg-red-100 text-red-700' },
  modified: { label: '修改', class: 'bg-amber-100 text-amber-700' },
} as const

const enrichedItems = computed(() =>
  props.items.map((item) => {
    if (isListField(item.field)) {
      const rows = diffFieldList(
        item.current_value as FieldItem[] | undefined,
        item.version_value as FieldItem[] | undefined
      )
      return { ...item, mode: 'list' as const, listRows: rows, listSummary: listDiffSummary(rows) }
    }
    if (isTextField(item.field)) {
      const currentText = String(item.current_value ?? '')
      const versionText = String(item.version_value ?? '')
      const lineRows = diffLines(currentText, versionText)
      const changedOnly = lineRows.filter((r) => r.kind !== 'same')
      return {
        ...item,
        mode: 'text' as const,
        lineRows: changedOnly.length ? changedOnly : lineRows,
        lineSummary: lineDiffSummary(lineRows),
        showAllLines: changedOnly.length === 0,
      }
    }
    return { ...item, mode: 'scalar' as const }
  })
)
</script>

<template>
  <div class="border border-blue-100 bg-blue-50/40 rounded-xl p-4 space-y-4">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h4 class="text-sm font-semibold text-gray-900">与当前配置差异（v{{ versionNo }}）</h4>
        <p class="text-xs text-gray-500 mt-0.5">
          <span class="text-red-600">红/−</span> 表示当前有、回滚后将消失；
          <span class="text-green-600">绿/+</span> 表示回滚后将出现。
        </p>
      </div>
      <button type="button" class="text-xs text-gray-500 hover:text-gray-700 shrink-0" @click="$emit('close')">
        关闭
      </button>
    </div>

    <div v-if="!items.length" class="text-sm text-gray-500">与当前配置一致，无差异。</div>

    <div v-else class="space-y-4">
      <div
        v-for="item in enrichedItems"
        :key="item.field"
        class="bg-white border border-gray-100 rounded-lg overflow-hidden"
      >
        <div class="px-3 py-2 border-b border-gray-100 bg-gray-50/80 flex items-center justify-between gap-2">
          <span class="text-sm font-medium text-gray-800">{{ item.label }}</span>
          <span v-if="item.mode === 'list'" class="text-[11px] text-gray-500">
            <span v-if="item.listSummary.removed" class="text-red-600">删 {{ item.listSummary.removed }}</span>
            <span v-if="item.listSummary.modified" class="ml-2 text-amber-600">改 {{ item.listSummary.modified }}</span>
            <span v-if="item.listSummary.added" class="ml-2 text-green-600">增 {{ item.listSummary.added }}</span>
          </span>
          <span v-else-if="item.mode === 'text'" class="text-[11px] text-gray-500">
            <span v-if="item.lineSummary.removed" class="text-red-600">−{{ item.lineSummary.removed }} 行</span>
            <span v-if="item.lineSummary.added" class="ml-2 text-green-600">+{{ item.lineSummary.added }} 行</span>
          </span>
        </div>

        <!-- 标量：旧 → 新 -->
        <div v-if="item.mode === 'scalar'" class="p-3 flex flex-wrap items-center gap-2 text-sm">
          <span class="px-2.5 py-1 rounded-md bg-red-50 text-red-700 border border-red-100 line-through decoration-red-400">
            {{ formatScalarValue(item.current_value, item.field) }}
          </span>
          <svg class="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
          <span class="px-2.5 py-1 rounded-md bg-green-50 text-green-700 border border-green-100 font-medium">
            {{ formatScalarValue(item.version_value, item.field) }}
          </span>
        </div>

        <!-- 字段列表：按行标增删改 -->
        <div v-else-if="item.mode === 'list'" class="overflow-x-auto">
          <table class="min-w-full text-xs">
            <thead class="bg-gray-50 text-gray-500">
              <tr>
                <th class="px-3 py-2 text-left font-medium w-16">变更</th>
                <th class="px-3 py-2 text-left font-medium">字段名</th>
                <th class="px-3 py-2 text-left font-medium">当前配置</th>
                <th class="px-3 py-2 text-left font-medium">目标版本</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="row in item.listRows" :key="row.name" class="align-top">
                <td class="px-3 py-2">
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold" :class="kindMeta[row.kind].class">
                    {{ kindMeta[row.kind].label }}
                  </span>
                </td>
                <td class="px-3 py-2 font-mono text-gray-800">{{ row.name }}</td>
                <td class="px-3 py-2">
                  <template v-if="row.kind === 'added'">
                    <span class="text-gray-400">—</span>
                  </template>
                  <template v-else-if="row.kind === 'removed'">
                    <div class="text-red-700 bg-red-50 rounded px-2 py-1">
                      {{ row.current?.label || '—' }} · {{ row.current?.type || '—' }}
                    </div>
                  </template>
                  <template v-else>
                    <div class="space-y-1">
                      <div
                        v-for="prop in row.changedProps"
                        :key="prop"
                        class="text-red-700 bg-red-50 rounded px-2 py-0.5"
                      >
                        {{ propLabel(prop) }}: {{ row.current?.[prop as keyof FieldItem] || '—' }}
                      </div>
                    </div>
                  </template>
                </td>
                <td class="px-3 py-2">
                  <template v-if="row.kind === 'removed'">
                    <span class="text-gray-400">—</span>
                  </template>
                  <template v-else-if="row.kind === 'added'">
                    <div class="text-green-700 bg-green-50 rounded px-2 py-1">
                      {{ row.version?.label || '—' }} · {{ row.version?.type || '—' }}
                    </div>
                  </template>
                  <template v-else>
                    <div class="space-y-1">
                      <div
                        v-for="prop in row.changedProps"
                        :key="prop"
                        class="text-green-700 bg-green-50 rounded px-2 py-0.5"
                      >
                        {{ propLabel(prop) }}: {{ row.version?.[prop as keyof FieldItem] || '—' }}
                      </div>
                    </div>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- SQL / 备注：行级 diff -->
        <div v-else class="p-2 font-mono text-[12px] leading-5 max-h-64 overflow-auto bg-gray-900 rounded-b-lg">
          <div
            v-for="(line, idx) in item.lineRows"
            :key="idx"
            class="px-2 whitespace-pre-wrap break-all"
            :class="{
              'text-gray-500': line.kind === 'same',
              'bg-red-950/60 text-red-300': line.kind === 'remove',
              'bg-green-950/60 text-green-300': line.kind === 'add',
            }"
          >
            <span class="select-none opacity-60 w-4 inline-block">{{ line.kind === 'add' ? '+' : line.kind === 'remove' ? '−' : ' ' }}</span>{{ line.text || ' ' }}
          </div>
          <p v-if="item.showAllLines" class="px-2 py-1 text-gray-500 text-[11px]">内容相同，无行级差异。</p>
        </div>
      </div>
    </div>
  </div>
</template>
