import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  linkify: true,
  typographer: true,
  breaks: true,
})

export function renderMarkdown(text: string): string {
  if (!text.trim()) return ''
  return md.render(text)
}
