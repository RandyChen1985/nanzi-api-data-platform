/**
 * 复制文本到剪贴板
 * 优先使用 navigator.clipboard 接口，在非安全上下文（如 HTTP 部署）等不可用情况下，
 * 优雅回退到使用隐藏的 textarea + document.execCommand('copy') 方法
 * 
 * @param text 需要复制的文本
 * @returns 复制是否成功
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // 1. 优先使用 modern 浏览器的 navigator.clipboard
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (err) {
      console.warn('navigator.clipboard.writeText failed, trying fallback method', err)
    }
  }

  // 2. 兼容性回退方案：使用隐藏 textarea 配合 execCommand
  try {
    const textArea = document.createElement('textarea')
    textArea.value = text

    // 严密隐藏该 textarea，防止其在移动端或大页面上引发抖动或强制滚动
    textArea.style.position = 'fixed'
    textArea.style.top = '0'
    textArea.style.left = '0'
    textArea.style.width = '2em'
    textArea.style.height = '2em'
    textArea.style.padding = '0'
    textArea.style.border = 'none'
    textArea.style.outline = 'none'
    textArea.style.boxShadow = 'none'
    textArea.style.background = 'transparent'
    
    // 关键：防止屏幕阅读器干扰并避免任何指针事件
    textArea.setAttribute('readonly', '')
    textArea.style.pointerEvents = 'none'

    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()

    const successful = document.execCommand('copy')
    document.body.removeChild(textArea)

    if (successful) {
      return true
    }
    throw new Error('document.execCommand copy execution returned false')
  } catch (err) {
    console.error('Fallback copyToClipboard execution failed:', err)
    return false
  }
}
