import { format as formatSqlLib } from 'sql-formatter'

/** SQL Lab 统一格式化（保留 Jinja 占位符） */
export function formatLabSql(sql: string, sourceType = 'mysql'): string {
  const trimmed = sql.trim()
  if (!trimmed) return sql

  const dialect = sourceType === 'clickhouse' ? 'mariadb' : 'mysql'
  let formatted = sql
  const tags: string[] = []
  const tagRegex = /(\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\})/gs

  formatted = formatted.replace(tagRegex, (match) => {
    tags.push(match)
    return `__JINJA_TAG_${tags.length - 1}__`
  })

  formatted = formatSqlLib(formatted, {
    language: dialect as 'mysql' | 'mariadb',
    keywordCase: 'upper',
    linesBetweenQueries: 2,
  })

  tags.forEach((tag, i) => {
    formatted = formatted.replace(`__JINJA_TAG_${i}__`, tag)
  })

  return formatted
}

/** 格式化失败时返回原 SQL */
export function formatLabSqlSafe(sql: string, sourceType = 'mysql'): string {
  try {
    return formatLabSql(sql, sourceType)
  } catch {
    return sql
  }
}
