import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/core'
import sqlLang from 'highlight.js/lib/languages/sql'
import jsonLang from 'highlight.js/lib/languages/json'
import pythonLang from 'highlight.js/lib/languages/python'
import javascriptLang from 'highlight.js/lib/languages/javascript'
import bashLang from 'highlight.js/lib/languages/bash'

hljs.registerLanguage('sql', sqlLang)
hljs.registerLanguage('json', jsonLang)
hljs.registerLanguage('python', pythonLang)
hljs.registerLanguage('javascript', javascriptLang)
hljs.registerLanguage('bash', bashLang)

const SQL_LANG_ALIASES = new Set(['sql', 'mysql', 'postgresql', 'clickhouse', 'mariadb', 'sqlite'])

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
  highlight(str, lang) {
    const normalized = (lang || '').toLowerCase()
    const useLang = normalized && hljs.getLanguage(normalized)
      ? normalized
      : (looksLikeSql(str) ? 'sql' : '')
    if (useLang && hljs.getLanguage(useLang)) {
      try {
        return hljs.highlight(str, { language: useLang, ignoreIllegals: true }).value
      } catch {
        /* fall through */
      }
    }
    try {
      return hljs.highlightAuto(str, ['sql', 'json', 'python', 'javascript', 'bash']).value
    } catch {
      return escapeHtml(str)
    }
  },
})

md.enable(['table'])

function looksLikeSql(text: string): boolean {
  const t = text.trim()
  return /^(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|ALTER|EXPLAIN|SHOW|DESC)\b/im.test(t)
    || (/\bSELECT\b/i.test(t) && /\bFROM\b/i.test(t))
}

/** 规范化 AI 输出中的代码块，便于高亮渲染 */
export function preprocessMarkdown(text: string): string {
  if (!text.trim()) return text

  let out = text.replace(/<br\s*\/?>/gi, '\n')

  out = out.replace(/```([^\n]*)\n/g, (_, rawLang: string) => {
    const lang = rawLang.trim().toLowerCase()
    if (!lang) return '```\n'
    if (SQL_LANG_ALIASES.has(lang)) return '```sql\n'
    return `\`\`\`${lang}\n`
  })

  const parts = out.split(/(```[\s\S]*?```)/g)
  out = parts.map((part, i) => (i % 2 === 1 ? part : wrapBareSqlBlocks(part))).join('')

  // 无语言标记的 fence，若内容为 SQL 则补上 sql
  out = out.replace(/```\n([\s\S]*?)```/g, (full, body: string) => {
    if (looksLikeSql(body)) return '```sql\n' + body.trim() + '\n```'
    return full
  })

  out = fixPipeTables(out)
  out = convertPlainTextTables(out)

  return out
}

/** 管道符表格缺少分隔行时自动补全 */
function fixPipeTables(text: string): string {
  const lines = text.split('\n')
  const out: string[] = []
  let inTable = false

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (line === undefined) continue
    const trimmed = line.trim()
    const isPipe = trimmed.includes('|')
    const isSep = /^\|?[\s:\-|]+\|?$/.test(trimmed)

    if (!isPipe) {
      inTable = false
      out.push(line)
      continue
    }

    if (isSep) {
      out.push(line)
      inTable = true
      continue
    }

    if (!inTable) {
      out.push(line)
      const next = lines[i + 1]?.trim() ?? ''
      const nextIsSep = /^\|?[\s:\-|]+\|?$/.test(next)
      if (next.includes('|') && !nextIsSep) {
        const colCount = trimmed.split('|').filter(c => c.trim()).length
        if (colCount >= 2) {
          out.push('|' + ' --- |'.repeat(colCount))
        }
      }
      inTable = true
    } else {
      out.push(line)
    }
  }
  return out.join('\n')
}

function splitTableRow(row: string, colCount: number): string[] | null {
  const t = row.trim()
  if (!t) return null
  if (colCount === 2) {
    const m = t.match(/^(\S+)\s+(.+)$/)
    if (m?.[1] != null && m[2] != null) return [m[1], m[2].trim()]
  }
  const byTab = t.split(/\t+/).map(c => c.trim()).filter(Boolean)
  if (byTab.length === colCount) return byTab
  const bySpaces = t.split(/\s{2,}/).map(c => c.trim()).filter(Boolean)
  if (bySpaces.length === colCount) return bySpaces
  return null
}

/** 将 AI 输出的「空格/制表符对齐」简易表转为 Markdown 表格 */
function convertPlainTextTables(text: string): string {
  const blocks = text.split(/\n\n+/)
  return blocks.map(block => {
    const lines = block.split('\n').map(l => l.trimEnd()).filter(l => l.trim())
    if (lines.length < 2) return block
    if (lines.some(l => l.includes('|'))) return block

    const firstLine = lines[0]
    if (!firstLine) return block
    const headerCells = splitTableRow(firstLine, 2) ?? splitTableRow(firstLine, 3)
    if (!headerCells) return block
    const colCount = headerCells.length
    if (colCount < 2 || colCount > 4) return block

    const dataRows: string[][] = []
    for (let i = 1; i < lines.length; i++) {
      const rowLine = lines[i]
      if (!rowLine) return block
      const cells = splitTableRow(rowLine, colCount)
      if (!cells) return block
      dataRows.push(cells)
    }
    if (dataRows.length === 0) return block
    // 多列且单元格过长，多半是正文而非表格
    if (colCount >= 3 && dataRows.some(r => r.some(c => c.length > 80))) return block

    const esc = (s: string) => s.replace(/\|/g, '\\|')
    const header = '| ' + headerCells.map(esc).join(' | ') + ' |'
    const sep = '| ' + headerCells.map(() => '---').join(' | ') + ' |'
    const body = dataRows.map(r => '| ' + r.map(esc).join(' | ') + ' |').join('\n')
    return [header, sep, body].join('\n')
  }).join('\n\n')
}

function wrapBareSqlBlocks(text: string): string {
  const lines = text.split('\n')
  const out: string[] = []
  let buf: string[] = []

  const isSqlLine = (line: string) => {
    const t = line.trim()
    if (!t) return buf.length > 0
    return /^(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|ALTER|EXPLAIN|FROM|WHERE|JOIN|GROUP|ORDER|HAVING|LIMIT|AND|OR|ON|LEFT|RIGHT|INNER|OUTER|UNION|SET|VALUES)\b/i.test(t)
      || (buf.length > 0 && /^[,)]/.test(t))
  }

  const flush = () => {
    if (!buf.length) return
    const block = buf.join('\n').trim()
    buf = []
    if (block && looksLikeSql(block)) {
      out.push('```sql\n' + block + '\n```')
    } else if (block) {
      out.push(block)
    }
  }

  for (const line of lines) {
    if (isSqlLine(line)) {
      buf.push(line)
    } else {
      flush()
      out.push(line)
    }
  }
  flush()
  return out.join('\n')
}

export function renderMarkdown(text: string): string {
  if (!text.trim()) return ''
  return md.render(preprocessMarkdown(text))
}
