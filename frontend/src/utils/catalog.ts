/** Normalize API featured flag (bool | 0/1 | "0"/"1") to boolean */
export function toFeaturedBool(value: unknown): boolean {
  return value === true || value === 1 || value === '1'
}

/** 目录产品上下架状态（0 草稿 / 1 已上架 / 2 已下线） */
export function catalogShelfStatus(status: number | undefined | null) {
  if (status === 1) return { text: '已上架', class: 'bg-green-100 text-green-700' }
  if (status === 0) return { text: '草稿', class: 'bg-gray-100 text-gray-600' }
  if (status === 2) return { text: '已下线', class: 'bg-amber-100 text-amber-700' }
  return { text: '', class: '' }
}

/** Playground 跳转所需的最小产品字段 */
export type CatalogPlaygroundProduct = {
  product_key: string
  primary_resource_key?: string
  resource_group?: string
}
