import { ref, computed, type Ref } from 'vue'

export type MoreMenuPos = {
  top: number
  left: number
  minWidth: number
  openUp: boolean
}

type UseActionMoreMenuOptions = {
  menuWidth?: number
  estHeight?: number
}

export function useActionMoreMenu<T extends { id: number }>(
  items: Ref<T[]>,
  options: UseActionMoreMenuOptions = {},
) {
  const menuWidth = options.menuWidth ?? 144
  const estHeight = options.estHeight ?? 200

  const openMore = ref<number | null>(null)
  const moreMenuPos = ref<MoreMenuPos | null>(null)

  const openMoreItem = computed(() => {
    if (openMore.value === null) return null
    return items.value.find((item) => item.id === openMore.value) ?? null
  })

  const moreMenuStyle = computed(() => {
    if (!moreMenuPos.value) return undefined
    const pos = moreMenuPos.value
    return {
      top: `${pos.top}px`,
      left: `${pos.left}px`,
      minWidth: `${pos.minWidth}px`,
      transform: pos.openUp ? 'translate(-100%, -100%)' : 'translateX(-100%)',
    }
  })

  const toggleMore = (id: number, e: MouseEvent) => {
    e.stopPropagation()
    if (openMore.value === id) {
      closeMore()
      return
    }
    const btn = e.currentTarget as HTMLElement
    const rect = btn.getBoundingClientRect()
    const spaceBelow = window.innerHeight - rect.bottom
    const openUp = spaceBelow < estHeight && rect.top > estHeight
    moreMenuPos.value = {
      top: openUp ? rect.top - 4 : rect.bottom + 4,
      left: rect.right,
      minWidth: Math.max(rect.width, menuWidth),
      openUp,
    }
    openMore.value = id
  }

  const closeMore = () => {
    openMore.value = null
    moreMenuPos.value = null
  }

  const bindGlobalClose = () => {
    document.addEventListener('click', closeMore)
    window.addEventListener('scroll', closeMore, true)
    window.addEventListener('resize', closeMore)
  }

  const unbindGlobalClose = () => {
    document.removeEventListener('click', closeMore)
    window.removeEventListener('scroll', closeMore, true)
    window.removeEventListener('resize', closeMore)
  }

  return {
    openMore,
    moreMenuPos,
    openMoreItem,
    moreMenuStyle,
    toggleMore,
    closeMore,
    bindGlobalClose,
    unbindGlobalClose,
  }
}
