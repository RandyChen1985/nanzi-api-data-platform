import {
  Document,
  HeadingLevel,
  ImageRun,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} from 'docx'

export const ANALYSIS_DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export interface AnalysisExportMessage {
  role: 'user' | 'assistant'
  content: string
  charts?: unknown[]
  chartImages?: readonly (AnalysisChartImage | undefined)[]
  suggestions?: string[]
}

export interface AnalysisChartImage {
  dataUrl: string
  width?: number
  height?: number
}

export interface AnalysisExportInput {
  title: string
  sql?: string
  messages: readonly AnalysisExportMessage[]
  exportedAt?: Date
}

export function normalizeAnalysisTitle(title: string): string {
  return String(title ?? '').trim().slice(0, 200)
}

export function buildAnalysisFilename(title: string, extension: 'md' | 'docx'): string {
  const normalized = normalizeAnalysisTitle(title)
    .replace(/[\\/:*?"<>|]/g, '_')
    .split('')
    .map((character) => character.charCodeAt(0) < 0x20 ? '_' : character)
    .join('')
    .replace(/[. ]+$/g, '')
  return `${normalized || 'AI分析'}.${extension}`
}

const formatExportTime = (date: Date) =>
  date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

const stringifyChart = (chart: unknown): string => {
  try {
    const serialized = JSON.stringify(chart, null, 2)
    return serialized === undefined ? '图表配置暂无法序列化' : serialized
  } catch {
    return '图表配置暂无法序列化'
  }
}

const nonEmptyLines = (values: readonly string[] | undefined): string[] =>
  (values || []).map((value) => String(value).trim()).filter(Boolean)

export function buildAnalysisMarkdown(input: AnalysisExportInput): string {
  const title = normalizeAnalysisTitle(input.title) || 'AI 数据专家分析'
  const exportedAt = input.exportedAt || new Date()
  const sections = [
    `# ${title}`,
    `导出时间：${formatExportTime(exportedAt)}`,
  ]

  if (input.sql?.trim()) {
    sections.push(`## 当前 SQL\n\n\`\`\`sql\n${input.sql.trim()}\n\`\`\``)
  }

  if (!input.messages.length) {
    sections.push('## 分析内容\n\n暂无分析内容')
  } else {
    input.messages.forEach((message, index) => {
      const role = message.role === 'user' ? '用户' : 'AI 分析'
      const content = String(message.content ?? '').trim()
      sections.push(`## ${role}${index + 1}\n\n${content || '（空消息）'}`)

      if (message.charts?.length) {
        message.charts.forEach((chart, chartIndex) => {
          sections.push(
            `### 图表 ${chartIndex + 1}\n\n\`\`\`json\n${stringifyChart(chart)}\n\`\`\``,
          )
        })
      }

      const suggestions = nonEmptyLines(message.suggestions)
      if (suggestions.length) {
        sections.push(`### 继续探索建议\n\n${suggestions.map((suggestion) => `- ${suggestion}`).join('\n')}`)
      }
    })
  }

  return `${sections.join('\n\n')}\n`
}

type DocxBlock = Paragraph | Table

const inlineRuns = (text: string, code = false): TextRun[] => {
  if (code) {
    return [new TextRun({ text, font: 'Courier New', size: 18 })]
  }

  const runs: TextRun[] = []
  const pattern = /(\*\*|__)(.+?)\1/g
  let cursor = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) runs.push(new TextRun({ text: text.slice(cursor, match.index) }))
    runs.push(new TextRun({ text: match[2], bold: true }))
    cursor = match.index + match[0].length
  }
  if (cursor < text.length) runs.push(new TextRun({ text: text.slice(cursor) }))
  return runs.length ? runs : [new TextRun({ text })]
}

const parseTableRow = (line: string): string[] => {
  const value = line.trim().replace(/^\|/, '').replace(/\|$/, '')
  return value.split('|').map((cell) => cell.trim())
}

const isTableSeparator = (line: string): boolean =>
  parseTableRow(line).every((cell) => /^:?-{3,}:?$/.test(cell))

const markdownBlocks = (content: string): DocxBlock[] => {
  const lines = String(content ?? '').replace(/\r\n/g, '\n').split('\n')
  const blocks: DocxBlock[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index] ?? ''
    if (!line.trim()) {
      index += 1
      continue
    }

    if (line.trim().startsWith('```')) {
      index += 1
      const codeLines: string[] = []
      while (index < lines.length && !(lines[index] ?? '').trim().startsWith('```')) {
        codeLines.push(lines[index] ?? '')
        index += 1
      }
      index += 1
      codeLines.forEach((codeLine) => {
        blocks.push(new Paragraph({ children: inlineRuns(codeLine || ' ', true) }))
      })
      continue
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/)
    if (heading) {
      const headingMarks = heading[1] ?? ''
      const headingText = heading[2] ?? ''
      const level = Math.min(headingMarks.length, 3)
      const headingLevel = level === 1
        ? HeadingLevel.HEADING_1
        : level === 2
          ? HeadingLevel.HEADING_2
          : HeadingLevel.HEADING_3
      blocks.push(new Paragraph({
        heading: headingLevel,
        children: inlineRuns(headingText.trim()),
      }))
      index += 1
      continue
    }

    const listItem = line.match(/^\s*(?:[-*]|\d+[.)])\s+(.+)$/)
    if (listItem) {
      blocks.push(new Paragraph({
        bullet: { level: 0 },
        children: inlineRuns(listItem[1] ?? ''),
      }))
      index += 1
      continue
    }

    if (line.trim().startsWith('>')) {
      blocks.push(new Paragraph({
        children: [new TextRun({ text: line.replace(/^\s*>\s?/, ''), italics: true })],
        indent: { left: 480 },
      }))
      index += 1
      continue
    }

    const nextLine = lines[index + 1] ?? ''
    if (line.includes('|') && index + 1 < lines.length && isTableSeparator(nextLine)) {
      const rows: TableRow[] = []
      const header = parseTableRow(line)
      rows.push(new TableRow({
        tableHeader: true,
        children: header.map((cell) => new TableCell({
          children: [new Paragraph({ children: [new TextRun({ text: cell, bold: true })] })],
        })),
      }))
      index += 2
      while (index < lines.length && (lines[index] ?? '').includes('|') && (lines[index] ?? '').trim()) {
        const rowLine = lines[index] ?? ''
        rows.push(new TableRow({
          children: parseTableRow(rowLine).map((cell) => new TableCell({
            children: [new Paragraph({ children: inlineRuns(cell) })],
          })),
        }))
        index += 1
      }
      blocks.push(new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        rows,
      }))
      continue
    }

    blocks.push(new Paragraph({ children: inlineRuns(line.trim()) }))
    index += 1
  }

  return blocks
}

const chartImageSize = (image: AnalysisChartImage) => {
  const sourceWidth = image.width && image.width > 0 ? image.width : 640
  const sourceHeight = image.height && image.height > 0 ? image.height : 360
  const maxWidth = 640
  const scale = Math.min(1, maxWidth / sourceWidth)
  return {
    width: Math.round(sourceWidth * scale),
    height: Math.round(sourceHeight * scale),
  }
}

export async function buildAnalysisDocx(input: AnalysisExportInput): Promise<Blob> {
  const title = normalizeAnalysisTitle(input.title) || 'AI 数据专家分析'
  const exportedAt = input.exportedAt || new Date()
  const children: DocxBlock[] = [
    new Paragraph({ heading: HeadingLevel.TITLE, children: inlineRuns(title) }),
    new Paragraph({ children: [new TextRun({ text: `导出时间：${formatExportTime(exportedAt)}`, color: '666666' })] }),
  ]

  if (input.sql?.trim()) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: inlineRuns('当前 SQL') }))
    markdownBlocks(`\`\`\`sql\n${input.sql.trim()}\n\`\`\``).forEach((block) => children.push(block))
  }

  if (!input.messages.length) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: inlineRuns('分析内容') }))
    children.push(new Paragraph({ children: inlineRuns('暂无分析内容') }))
  } else {
    input.messages.forEach((message, index) => {
      const role = message.role === 'user' ? '用户' : 'AI 分析'
      children.push(new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: inlineRuns(`${role}${index + 1}`),
      }))
      markdownBlocks(message.content || '（空消息）').forEach((block) => children.push(block))

      if (message.charts?.length) {
        children.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: inlineRuns('图表') }))
        message.charts.forEach((chart, chartIndex) => {
          children.push(new Paragraph({
            heading: HeadingLevel.HEADING_3,
            children: inlineRuns(`图表 ${chartIndex + 1}`),
          }))
          const chartImage = message.chartImages?.[chartIndex]
          if (chartImage?.dataUrl?.startsWith('data:image/png')) {
            children.push(new Paragraph({
              children: [new ImageRun({
                type: 'png',
                data: chartImage.dataUrl,
                transformation: chartImageSize(chartImage),
              })],
            }))
          } else {
            markdownBlocks(`\`\`\`json\n${stringifyChart(chart)}\n\`\`\``).forEach((block) => children.push(block))
          }
        })
      }

      const suggestions = nonEmptyLines(message.suggestions)
      if (suggestions.length) {
        children.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: inlineRuns('继续探索建议') }))
        suggestions.forEach((suggestion) => children.push(new Paragraph({
          bullet: { level: 0 },
          children: inlineRuns(suggestion),
        })))
      }
    })
  }

  const document = new Document({ sections: [{ children }] })
  const blob = await Packer.toBlob(document)
  return blob.type === ANALYSIS_DOCX_MIME
    ? blob
    : new Blob([blob], { type: ANALYSIS_DOCX_MIME })
}
