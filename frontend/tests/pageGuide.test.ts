import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const readSource = (relativePath: string) =>
  readFile(new URL(relativePath, import.meta.url), 'utf8')

test('SQL Lab keeps a persistent question-mark help entry beside its title', async () => {
  const source = await readSource('../src/views/SQLLab.vue')

  assert.match(source, /<PageGuideModal/)
  assert.match(source, /showSqlLabGuideModal/)
  assert.match(source, /title="SQL 实验室使用指引"/)
  assert.match(source, /QuestionMarkCircleIcon/)
})

test('resource list keeps a persistent question-mark help entry beside its title', async () => {
  const source = await readSource('../src/views/resources/ResourceList.vue')

  assert.match(source, /<PageGuideModal/)
  assert.match(source, /showResourceGuideModal/)
  assert.match(source, /title="资源 API 使用指引"/)
  assert.match(source, /QuestionMarkCircleIcon/)
})

test('page guide modal has an accessible dismissible dialog shell', async () => {
  const source = await readSource('../src/components/common/PageGuideModal.vue')

  assert.match(source, /role="dialog"/)
  assert.match(source, /aria-modal="true"/)
  assert.match(source, /@click\.self="emit\('close'\)"/)
  assert.match(source, /@keydown\.esc="emit\('close'\)"/)
})

test('guide banner uses the spacious reference workflow treatment', async () => {
  const source = await readSource('../src/components/common/GuideBanner.vue')

  assert.match(source, /rounded-2xl/)
  assert.match(source, /shadow-sm/)
  assert.match(source, /展开流程/)
  assert.match(source, /不再提示/)
  assert.match(source, /v-show="!collapsed"/)
})

test('dismissed guide banners expose a restore action on both pages', async () => {
  const bannerSource = await readSource('../src/components/common/GuideBanner.vue')
  const sqlLabSource = await readSource('../src/views/SQLLab.vue')
  const resourceSource = await readSource('../src/views/resources/ResourceList.vue')

  assert.match(bannerSource, /emit\('dismiss'\)/)
  assert.match(bannerSource, /emit\('close'\)/)
  assert.match(sqlLabSource, /showSqlLabGuideBanner/)
  assert.match(sqlLabSource, /restoreSqlLabGuide/)
  assert.match(sqlLabSource, /localStorage\.removeItem\('sqllab-guide:dismissed'\)/)
  assert.match(sqlLabSource, /v-if="!showSqlLabGuideBanner"/)
  assert.match(resourceSource, /showResourceGuideBanner/)
  assert.match(resourceSource, /restoreResourceGuide/)
  assert.match(resourceSource, /localStorage\.removeItem\('resources-guide:dismissed'\)/)
  assert.match(resourceSource, /v-if="!showResourceGuideBanner"/)
})

test('dashboard keeps all route pages close to the global header', async () => {
  const source = await readSource('../src/views/Dashboard.vue')

  assert.match(source, /class="flex-1 overflow-y-auto bg-gray-100 px-4 py-3 sm:px-6 sm:py-4 lg:px-8 custom-scrollbar"/)
  assert.doesNotMatch(source, /class="flex-1 overflow-y-auto bg-gray-100 p-4 sm:p-6 lg:p-8 custom-scrollbar"/)
})

test('flow guides render after their page headers', async () => {
  const resourceSource = await readSource('../src/views/resources/ResourceList.vue')
  const sqlLabSource = await readSource('../src/views/SQLLab.vue')

  assert.ok(resourceSource.indexOf('<!-- Header -->') < resourceSource.indexOf('<GuideBanner'))
  assert.ok(sqlLabSource.indexOf('<h1 class="text-base font-bold text-gray-900 flex items-center">') < sqlLabSource.indexOf('<GuideBanner'))
})

test('workflow guides expose contextual actions for the real resource and SQL Lab flows', async () => {
  const bannerSource = await readSource('../src/components/common/GuideBanner.vue')
  const resourceSource = await readSource('../src/views/resources/ResourceList.vue')
  const sqlLabSource = await readSource('../src/views/SQLLab.vue')

  assert.match(bannerSource, /actionText\?: string/)
  assert.match(bannerSource, /actionType\?: string/)
  assert.match(bannerSource, /action: \[type: string\]/)
  assert.match(bannerSource, /step\.actionText && step\.actionType/)
  assert.match(resourceSource, /@action="handleResourceGuideAction"/)
  assert.match(resourceSource, /去数据源管理/)
  assert.match(resourceSource, /新建资源/)
  assert.match(resourceSource, /打开产品目录/)
  assert.match(sqlLabSource, /@action="handleSqlLabGuideAction"/)
  assert.match(sqlLabSource, /聚焦编辑器/)
  assert.match(sqlLabSource, /运行当前 SQL/)
})

test('workflow guide copy documents the actual resource and SQL Lab prerequisites', async () => {
  const resourceSource = await readSource('../src/views/resources/ResourceList.vue')
  const sqlLabSource = await readSource('../src/views/SQLLab.vue')

  assert.match(resourceSource, /TABLE\/SQL/)
  assert.match(resourceSource, /解析 SQL 获取字段/)
  assert.match(resourceSource, /保存后再用测试控制台或调试入口验证/)
  assert.match(resourceSource, /X-API-Key/)
  assert.match(sqlLabSource, /空参数测试/)
  assert.match(sqlLabSource, /发布前检查/)
  assert.match(sqlLabSource, /AI 分析与导出/)
})

test('guide step cards keep a tinted hover treatment instead of switching to opaque white', async () => {
  const source = await readSource('../src/components/common/GuideBanner.vue')

  assert.match(source, /hover:bg-indigo-50\/70/)
  assert.doesNotMatch(source, /min-h-32[^"\n]*hover:bg-white/)
})
