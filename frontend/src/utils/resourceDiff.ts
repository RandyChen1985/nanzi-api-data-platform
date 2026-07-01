export type FieldItem = { name: string; label?: string; type?: string }

export type ListDiffRow = {
  kind: 'added' | 'removed' | 'modified'
  name: string
  current?: FieldItem
  version?: FieldItem
  changedProps: string[]
}

export type LineDiffRow = {
  kind: 'same' | 'add' | 'remove'
  text: string
}

const FIELD_PROP_LABELS: Record<string, string> = {
  label: '中文名',
  type: '类型',
}

export function diffFieldList(current: FieldItem[] | null | undefined, version: FieldItem[] | null | undefined): ListDiffRow[] {
  const curMap = new Map((current || []).map((f) => [f.name, f]))
  const verMap = new Map((version || []).map((f) => [f.name, f]))
  const names = new Set([...curMap.keys(), ...verMap.keys()])
  const rows: ListDiffRow[] = []

  for (const name of names) {
    const cur = curMap.get(name)
    const ver = verMap.get(name)
    if (cur && !ver) {
      rows.push({ kind: 'removed', name, current: cur, changedProps: [] })
    } else if (!cur && ver) {
      rows.push({ kind: 'added', name, version: ver, changedProps: [] })
    } else if (cur && ver) {
      const changedProps: string[] = []
      if ((cur.label || '') !== (ver.label || '')) changedProps.push('label')
      if ((cur.type || '') !== (ver.type || '')) changedProps.push('type')
      if (changedProps.length) {
        rows.push({ kind: 'modified', name, current: cur, version: ver, changedProps })
      }
    }
  }

  const order = { removed: 0, modified: 1, added: 2 }
  return rows.sort((a, b) => order[a.kind] - order[b.kind] || a.name.localeCompare(b.name))
}

export function listDiffSummary(rows: ListDiffRow[]) {
  return {
    added: rows.filter((r) => r.kind === 'added').length,
    removed: rows.filter((r) => r.kind === 'removed').length,
    modified: rows.filter((r) => r.kind === 'modified').length,
  }
}

export function formatScalarValue(value: unknown, field?: string): string {
  if (value === null || value === undefined || value === '') return '（空）'
  if (field === 'status') return value === 1 ? '启用' : '禁用'
  if (field === 'cache_ttl') return value === 0 ? '不缓存' : `${value} 秒`
  return String(value)
}

export function isListField(field: string) {
  return field === 'fields_config' || field === 'allowed_filters'
}

export function isTextField(field: string) {
  return field === 'custom_sql' || field === 'remarks'
}

/** 简易行级 diff（LCS），用于 SQL / 长文本 */
export function diffLines(oldText: string, newText: string): LineDiffRow[] {
  const a = (oldText || '').split('\n')
  const b = (newText || '').split('\n')
  const n = a.length
  const m = b.length
  const dp: number[][] = Array.from({ length: n + 1 }, () => Array<number>(m + 1).fill(0))

  const cell = (row: number, col: number): number => dp[row]?.[col] ?? 0
  const lineAt = (lines: string[], index: number): string => lines[index] ?? ''

  for (let i = n - 1; i >= 0; i--) {
    const row = dp[i]
    if (!row) continue
    for (let j = m - 1; j >= 0; j--) {
      row[j] =
        lineAt(a, i) === lineAt(b, j)
          ? cell(i + 1, j + 1) + 1
          : Math.max(cell(i + 1, j), cell(i, j + 1))
    }
  }

  const rows: LineDiffRow[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    const aLine = lineAt(a, i)
    const bLine = lineAt(b, j)
    if (aLine === bLine) {
      rows.push({ kind: 'same', text: aLine })
      i++
      j++
    } else if (cell(i + 1, j) >= cell(i, j + 1)) {
      rows.push({ kind: 'remove', text: aLine })
      i++
    } else {
      rows.push({ kind: 'add', text: bLine })
      j++
    }
  }
  while (i < n) {
    rows.push({ kind: 'remove', text: lineAt(a, i) })
    i++
  }
  while (j < m) {
    rows.push({ kind: 'add', text: lineAt(b, j) })
    j++
  }
  return rows
}

export function lineDiffSummary(rows: LineDiffRow[]) {
  return {
    added: rows.filter((r) => r.kind === 'add').length,
    removed: rows.filter((r) => r.kind === 'remove').length,
  }
}

export function propLabel(prop: string) {
  return FIELD_PROP_LABELS[prop] || prop
}
