import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildAnalysisMarkdown,
  buildAnalysisDocx,
  normalizeAnalysisTitle,
  buildAnalysisFilename,
  type AnalysisExportMessage,
} from '../src/utils/analysisExport.ts'

const messages: AnalysisExportMessage[] = [
  { role: 'user', content: '请分析订单趋势' },
  {
    role: 'assistant',
    content: '## 核心洞察\n订单量在周末上升。',
    charts: [{ title: { text: '订单趋势' }, series: [{ data: [1, 2] }] }],
    suggestions: ['按渠道拆分', '查看异常日期'],
  },
]

test('buildAnalysisMarkdown preserves the complete analysis session', () => {
  const markdown = buildAnalysisMarkdown({
    title: '订单趋势分析',
    sql: 'SELECT day, count(*) FROM orders GROUP BY day',
    messages,
  })

  assert.match(markdown, /^# 订单趋势分析/m)
  assert.match(markdown, /当前 SQL/)
  assert.ok(markdown.indexOf('请分析订单趋势') < markdown.indexOf('核心洞察'))
  assert.match(markdown, /图表 1/)
  assert.match(markdown, /订单趋势/)
  assert.match(markdown, /继续探索建议/)
  assert.match(markdown, /按渠道拆分/)
})

test('normalizeAnalysisTitle rejects empty titles and trims long names', () => {
  assert.equal(normalizeAnalysisTitle('   '), '')
  assert.equal(normalizeAnalysisTitle(' ' + 'a'.repeat(210) + ' ').length, 200)
})

test('buildAnalysisFilename removes unsafe filename characters', () => {
  assert.equal(buildAnalysisFilename('订单/趋势:*?', 'md'), '订单_趋势___.md')
})

test('buildAnalysisDocx returns a downloadable OOXML blob', async () => {
  const blob = await buildAnalysisDocx({ title: '订单趋势分析', messages })
  assert.equal(blob.type, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
  assert.ok(blob.size > 0)
  const bytes = new Uint8Array(await blob.arrayBuffer())
  assert.deepEqual(Array.from(bytes.slice(0, 2)), [80, 75])
})

test('buildAnalysisDocx embeds chart snapshots as image parts', async () => {
  const chartImage =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
  const blob = await buildAnalysisDocx({
    title: '图表分析',
    messages: [{
      role: 'assistant',
      content: '图表结论',
      charts: [{ title: { text: '用户分布' } }],
      chartImages: [{ dataUrl: chartImage }],
    }],
  })

  const zipText = new TextDecoder().decode(new Uint8Array(await blob.arrayBuffer()))
  assert.match(zipText, /word\/media\/[a-f0-9]+\.png/)
})
