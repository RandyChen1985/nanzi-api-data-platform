<template>
  <div class="space-y-6">
    <div class="flex flex-wrap justify-between items-center gap-3">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">业务角色管理</h1>
        <p class="text-sm text-gray-500 mt-1">配置业务角色的菜单、接口与数据权限，并分配成员</p>
      </div>
      <button
        @click="openCreateDialog"
        class="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition flex items-center gap-2 shadow-md"
      >
        <PlusIcon class="w-5 h-5" /> 创建角色
      </button>
    </div>

    <!-- Filters -->
    <div class="bg-white shadow-sm border border-gray-200 rounded-xl p-4">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
        <input
          v-model="roleSearch"
          type="text"
          placeholder="搜索角色名称或编码..."
          class="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 md:col-span-1"
        />
        <select
          v-model="sortBy"
          class="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="created_desc">创建时间（新→旧）</option>
          <option value="created_asc">创建时间（旧→新）</option>
          <option value="name_asc">名称 A→Z</option>
          <option value="members_desc">成员数（多→少）</option>
        </select>
        <button
          @click="roleSearch = ''; sortBy = 'created_desc'"
          class="border border-gray-300 rounded-lg px-4 py-2 hover:bg-gray-50 transition text-sm"
        >
          重置筛选
        </button>
        <div class="flex items-center justify-end gap-1 border border-gray-200 rounded-lg p-1 bg-gray-50 self-stretch">
          <button
            type="button"
            @click="viewMode = 'card'"
            class="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition"
            :class="viewMode === 'card' ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
            title="卡片视图"
          >
            <Squares2X2Icon class="w-4 h-4" />
            <span class="hidden sm:inline">卡片</span>
          </button>
          <button
            type="button"
            @click="viewMode = 'list'"
            class="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition"
            :class="viewMode === 'list' ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
            title="列表视图"
          >
            <ListBulletIcon class="w-4 h-4" />
            <span class="hidden sm:inline">列表</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="bg-white shadow rounded-lg p-12 text-center">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      <p class="mt-2 text-gray-500">加载角色列表中...</p>
    </div>

    <div
      v-else-if="filteredRoles.length === 0"
      class="bg-white border border-dashed border-gray-300 rounded-2xl p-12 text-center"
    >
      <UserGroupIcon class="w-12 h-12 text-gray-300 mx-auto mb-3" />
      <p class="text-gray-600 font-medium">{{ roleSearch ? '没有匹配的角色' : '尚未创建业务角色' }}</p>
      <p class="text-sm text-gray-400 mt-1 mb-4">
        {{ roleSearch ? '请调整搜索条件' : '创建角色后可批量配置权限并分配给用户' }}
      </p>
      <button
        v-if="!roleSearch"
        @click="openCreateDialog"
        class="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium"
      >
        <PlusIcon class="w-4 h-4" /> 创建第一个角色
      </button>
    </div>

    <div v-else-if="viewMode === 'card'" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="role in filteredRoles"
        :key="role.id"
        class="bg-white shadow-sm border border-gray-200 rounded-2xl p-6 hover:shadow-md hover:border-indigo-100 transition-all group cursor-pointer"
        @click="editRole(role)"
      >
        <div class="flex justify-between items-start mb-4">
          <div class="p-3 bg-indigo-50 rounded-xl text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition-all">
            <UserGroupIcon class="w-6 h-6" />
          </div>
          <div class="flex gap-2" @click.stop>
            <button
              @click="openMemberDialog(role)"
              class="p-1.5 text-gray-400 hover:text-indigo-600 transition-colors"
              title="成员管理"
            >
              <UserPlusIcon class="w-5 h-5" />
            </button>
            <button
              @click="editRole(role)"
              class="p-1.5 text-gray-400 hover:text-blue-600 transition-colors"
              title="编辑角色与权限"
            >
              <PencilSquareIcon class="w-5 h-5" />
            </button>
            <button
              @click="confirmDelete(role)"
              class="p-1.5 text-gray-400 hover:text-red-600 transition-colors"
              title="删除角色"
            >
              <TrashIcon class="w-5 h-5" />
            </button>
          </div>
        </div>
        <h3 class="text-lg font-bold text-gray-900">{{ role.role_name }}</h3>
        <p class="text-xs font-mono text-gray-400 mb-3">{{ role.role_code }}</p>
        <p class="text-sm text-gray-500 flex-1 line-clamp-2 mb-4">{{ role.description || '无详细描述' }}</p>

        <div class="flex flex-wrap gap-2 mb-4">
          <button
            type="button"
            class="flex items-center bg-indigo-50 text-indigo-700 px-2 py-1 rounded-lg text-[10px] font-bold border border-indigo-100 hover:bg-indigo-100 transition"
            title="已分配该角色的用户数，点击管理成员"
            @click.stop="openMemberDialog(role)"
          >
            <span class="mr-1">成员:</span> {{ role.stats?.user || 0 }}
          </button>
          <div
            class="flex items-center bg-blue-50 text-blue-700 px-2 py-1 rounded-lg text-[10px] font-bold border border-blue-100"
            title="已授权的侧边栏菜单数量"
          >
            <span class="mr-1">菜单:</span> {{ role.stats?.menu || 0 }}
          </div>
          <div
            class="flex items-center bg-purple-50 text-purple-700 px-2 py-1 rounded-lg text-[10px] font-bold border border-purple-100"
            title="已授权的功能点（按钮/操作）数量"
          >
            <span class="mr-1">功能:</span> {{ role.stats?.element || 0 }}
          </div>
          <div
            class="flex items-center bg-orange-50 text-orange-700 px-2 py-1 rounded-lg text-[10px] font-bold border border-orange-100"
            title="已授权的 Data API 接口数量"
          >
            <span class="mr-1">接口:</span> {{ role.stats?.resource || 0 }}
          </div>
        </div>

        <div class="space-y-2 mb-4">
          <div class="flex items-center text-xs text-gray-600">
            <span class="mr-2 text-base">🛡️</span>
            <span class="font-medium mr-2">脱敏策略:</span>
            <span v-if="role.masking_strategy === 'ENABLE'" class="text-red-600 font-bold bg-red-50 px-1.5 py-0.5 rounded">强制开启</span>
            <span v-else-if="role.masking_strategy === 'DISABLE'" class="text-green-600 font-bold bg-green-50 px-1.5 py-0.5 rounded">允许明文</span>
            <span v-else class="text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">跟随全局</span>
          </div>
          <div class="flex items-center text-xs text-gray-600">
            <span class="mr-2 text-base">⚡️</span>
            <span class="font-medium mr-2">流控限制:</span>
            <span v-if="role.rate_limit" class="text-amber-700 font-bold">
              {{ role.rate_limit }} <span class="font-normal text-[10px]">次/分</span>
            </span>
            <span v-else class="text-gray-400 italic font-normal">默认策略</span>
          </div>
        </div>

        <div class="mt-auto pt-4 border-t border-gray-50 flex justify-between items-center text-[10px] text-gray-400">
          <span class="flex items-center gap-1">
            <ClockIcon class="w-3 h-3" /> {{ formatDate(role.created_at) }}
          </span>
          <span class="bg-gray-100 px-2 py-0.5 rounded text-gray-500 font-bold">业务角色</span>
        </div>
      </div>
    </div>

    <!-- List View -->
    <div v-else class="bg-white shadow-sm border border-gray-200 rounded-xl overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase">角色名称</th>
              <th class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase">编码</th>
              <th class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase hidden lg:table-cell">描述</th>
              <th class="px-4 py-3 text-center text-xs font-bold text-gray-500 uppercase">成员</th>
              <th class="px-4 py-3 text-center text-xs font-bold text-gray-500 uppercase hidden md:table-cell">权限</th>
              <th class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase hidden sm:table-cell">脱敏/流控</th>
              <th class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase hidden xl:table-cell">创建时间</th>
              <th class="px-4 py-3 text-right text-xs font-bold text-gray-500 uppercase">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr
              v-for="role in filteredRoles"
              :key="role.id"
              class="hover:bg-indigo-50/40 cursor-pointer transition-colors"
              @click="editRole(role)"
            >
              <td class="px-4 py-3">
                <div class="font-semibold text-gray-900">{{ role.role_name }}</div>
              </td>
              <td class="px-4 py-3 text-xs font-mono text-gray-500">{{ role.role_code }}</td>
              <td class="px-4 py-3 text-sm text-gray-500 max-w-xs truncate hidden lg:table-cell">
                {{ role.description || '—' }}
              </td>
              <td class="px-4 py-3 text-center">
                <button
                  type="button"
                  class="inline-flex items-center justify-center min-w-[28px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-xs font-bold hover:bg-indigo-100"
                  @click.stop="openMemberDialog(role)"
                >
                  {{ role.stats?.user || 0 }}
                </button>
              </td>
              <td class="px-4 py-3 text-center text-xs text-gray-600 hidden md:table-cell">
                <span class="text-blue-600">{{ role.stats?.menu || 0 }}</span> /
                <span class="text-purple-600">{{ role.stats?.element || 0 }}</span> /
                <span class="text-orange-600">{{ role.stats?.resource || 0 }}</span>
                <div class="text-[10px] text-gray-400 mt-0.5">菜单/功能/接口</div>
              </td>
              <td class="px-4 py-3 text-xs text-gray-600 hidden sm:table-cell">
                <div>{{ maskingLabel(role.masking_strategy) }}</div>
                <div class="text-gray-400 mt-0.5">
                  {{ role.rate_limit ? `${role.rate_limit} 次/分` : '默认流控' }}
                </div>
              </td>
              <td class="px-4 py-3 text-xs text-gray-500 whitespace-nowrap hidden xl:table-cell">
                {{ formatDate(role.created_at) }}
              </td>
              <td class="px-4 py-3 text-right whitespace-nowrap" @click.stop>
                <div class="inline-flex items-center gap-1">
                  <button
                    @click="openMemberDialog(role)"
                    class="p-1.5 text-gray-400 hover:text-indigo-600 rounded-lg hover:bg-indigo-50"
                    title="成员管理"
                  >
                    <UserPlusIcon class="w-4 h-4" />
                  </button>
                  <button
                    @click="editRole(role)"
                    class="p-1.5 text-gray-400 hover:text-blue-600 rounded-lg hover:bg-blue-50"
                    title="编辑"
                  >
                    <PencilSquareIcon class="w-4 h-4" />
                  </button>
                  <button
                    @click="confirmDelete(role)"
                    class="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50"
                    title="删除"
                  >
                    <TrashIcon class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Create/Edit Modal -->
    <div
      v-if="showEditModal"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9990] p-2 sm:p-4"
      @click.self="tryCloseEditModal"
    >
      <div class="bg-white rounded-3xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden transform transition-all">
        <div class="px-4 sm:px-8 py-4 sm:py-6 border-b bg-gray-50 flex justify-between items-center shrink-0">
          <h2 class="text-lg sm:text-xl font-bold text-gray-900">{{ isEdit ? '编辑角色权限' : '创建新角色' }}</h2>
          <button @click="tryCloseEditModal" class="text-gray-400 hover:text-gray-600 transition-colors">
            <XMarkIcon class="w-6 h-6" />
          </button>
        </div>

        <div class="flex border-b border-gray-200 bg-white px-4 sm:px-8 overflow-x-auto shrink-0">
          <button
            @click="activeTab = 'info'"
            class="px-4 sm:px-6 py-3 sm:py-4 text-sm font-bold border-b-2 transition-all whitespace-nowrap"
            :class="activeTab === 'info' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
          >
            基础信息
          </button>
          <button
            @click="goToPermissionsTab"
            class="px-4 sm:px-6 py-3 sm:py-4 text-sm font-bold border-b-2 transition-all whitespace-nowrap"
            :class="activeTab === 'permissions' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
          >
            功能权限配置
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-4 sm:p-8 custom-scrollbar bg-white">
          <div v-show="activeTab === 'info'" class="space-y-6">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div>
                <label class="block text-xs font-bold text-gray-500 uppercase mb-2">角色名称 <span class="text-red-500">*</span></label>
                <input
                  v-model="formData.role_name"
                  class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
                  placeholder="如：数据分析师"
                />
              </div>
              <div>
                <label class="block text-xs font-bold text-gray-500 uppercase mb-2">角色编码 <span class="text-red-500">*</span></label>
                <input
                  v-model="formData.role_code"
                  :disabled="isEdit"
                  class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none transition-all disabled:bg-gray-50"
                  placeholder="如：data_analyst"
                />
                <p v-if="!isEdit" class="mt-1 text-[10px] text-gray-400">小写字母开头，仅含小写字母、数字和下划线</p>
              </div>
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-2">角色描述</label>
              <textarea
                v-model="formData.description"
                class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
                rows="4"
                placeholder="简述该角色的职责范围..."
              />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-2 flex items-center gap-2">
                ⚡️ API 限流阈值
                <span class="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded font-normal normal-case">每分钟最大请求数</span>
              </label>
              <div class="relative">
                <input
                  v-model.number="formData.rate_limit"
                  type="number"
                  min="0"
                  class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none transition-all pr-12"
                  placeholder="0"
                />
                <span class="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 text-xs font-bold">次/分</span>
              </div>
              <p class="mt-1 text-[10px] text-gray-400">设为 0 或留空表示使用系统默认策略。</p>
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-2">🛡️ 角色脱敏策略</label>
              <select
                v-model="formData.masking_strategy"
                class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
              >
                <option value="GLOBAL">跟随全局</option>
                <option value="ENABLE">强制开启</option>
                <option value="DISABLE">允许明文</option>
              </select>
            </div>
          </div>

          <div v-show="activeTab === 'permissions'" class="flex flex-col min-h-[400px]">
            <div class="mb-4">
              <input
                v-model="permissionSearch"
                type="text"
                placeholder="搜索权限项（名称、编码、分组）..."
                class="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>

            <div class="flex space-x-1 p-1 bg-gray-100 rounded-xl mb-6 w-full sm:w-fit overflow-x-auto">
              <button
                v-for="tab in permissionSubTabs"
                :key="tab.key"
                @click="activePermissionSubTab = tab.key"
                :class="activePermissionSubTab === tab.key ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
                class="px-4 sm:px-6 py-2 text-xs font-bold rounded-lg transition-all whitespace-nowrap flex items-center gap-2 shrink-0"
              >
                {{ tab.label }}
                <span :class="tab.badgeClass" class="px-1.5 py-0.5 rounded-md text-[10px]">{{ tab.count }}</span>
              </button>
            </div>

            <!-- Resource Sub-Tab -->
            <div v-show="activePermissionSubTab === 'resource'" class="space-y-4 flex-1">
              <p v-if="Object.keys(filteredGroupedResources).length === 0" class="text-center text-gray-400 py-8 text-sm">无匹配的接口资源</p>
              <div
                v-for="(resources, group) in filteredGroupedResources"
                :key="group"
                class="bg-gray-50 rounded-2xl border border-gray-100 overflow-hidden shadow-sm"
              >
                <div class="px-5 py-3 bg-white border-b border-gray-100 flex items-center justify-between gap-2">
                  <button
                    type="button"
                    class="flex items-center gap-2 text-xs font-black text-gray-600 uppercase tracking-widest hover:text-indigo-600"
                    @click="toggleGroupCollapse(String(group))"
                  >
                    <ChevronDownIcon
                      class="w-4 h-4 transition-transform"
                      :class="collapsedGroups.has(String(group)) ? '-rotate-90' : ''"
                    />
                    {{ group }}
                    <span class="text-gray-400 font-normal normal-case">({{ resources.length }})</span>
                  </button>
                  <button
                    @click="toggleGroupSelection(resources)"
                    type="button"
                    class="text-[10px] font-bold text-indigo-600 hover:underline shrink-0"
                  >
                    {{ isGroupAllSelected(resources) ? '取消全选' : '选择全部' }}
                  </button>
                </div>
                <div v-show="!collapsedGroups.has(String(group))" class="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <label
                    v-for="resource in resources"
                    :key="resource.id"
                    class="flex items-start p-3 rounded-xl border cursor-pointer transition-all"
                    :class="selectedResources.includes(resource.id) ? 'bg-indigo-50 border-indigo-200' : 'bg-white border-transparent hover:border-gray-200'"
                  >
                    <input
                      type="checkbox"
                      v-model="selectedResources"
                      :value="resource.id"
                      class="mt-1 h-4 w-4 rounded text-indigo-600 border-gray-300 focus:ring-indigo-500"
                    />
                    <div class="ml-3 min-w-0">
                      <p class="text-sm font-bold text-gray-800 truncate flex items-center gap-2">
                        {{ resource.name }}
                        <span
                          v-if="resource.id === 'system.sql.execute'"
                          class="text-[9px] bg-red-100 text-red-600 px-1 py-0.5 rounded font-black border border-red-200 uppercase shrink-0"
                        >
                          ROOT 权限
                        </span>
                      </p>
                      <p class="text-[10px] text-gray-400 font-mono truncate">{{ resource.id }}</p>
                    </div>
                  </label>
                </div>
              </div>
            </div>

            <!-- UI Sub-Tab -->
            <div v-show="activePermissionSubTab === 'ui'" class="grid grid-cols-1 gap-4">
              <p v-if="filteredMenuTree.length === 0" class="text-center text-gray-400 py-8 text-sm">无匹配的菜单或功能</p>
              <div
                v-for="menu in filteredMenuTree"
                :key="menu.id"
                class="bg-gray-50 rounded-2xl border border-gray-100 overflow-hidden shadow-sm"
              >
                <div class="px-5 py-3 bg-white border-b border-gray-100 flex items-center gap-3">
                  <input
                    type="checkbox"
                    :value="menu.id"
                    v-model="selectedMenus"
                    @change="onMenuToggle(menu, $event)"
                    class="h-5 w-5 text-indigo-600 rounded-lg border-gray-300 focus:ring-indigo-500"
                  />
                  <span class="text-sm font-black text-gray-800 flex items-center gap-2">
                    <span class="bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded text-[10px] font-normal border border-gray-200">菜单</span>
                    {{ menu.label }}
                  </span>
                </div>
                <div v-if="menu.children.length > 0" class="p-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <label
                    v-for="child in menu.children"
                    :key="child.id"
                    class="flex items-center p-2 rounded-lg border cursor-pointer transition-all"
                    :class="selectedElements.includes(child.id) ? 'bg-indigo-50 border-indigo-100' : 'bg-white/50 border-transparent hover:border-gray-200'"
                  >
                    <input
                      type="checkbox"
                      :value="child.id"
                      v-model="selectedElements"
                      class="h-4 w-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                    />
                    <span class="ml-3 text-xs font-medium text-gray-600 flex items-center gap-2">
                      <span class="bg-purple-50 text-purple-600 px-1 py-0.5 rounded text-[9px] border border-purple-100">功能</span>
                      {{ child.label }}
                    </span>
                  </label>
                </div>
              </div>
            </div>

            <!-- Data Asset Sub-Tab -->
            <div v-show="activePermissionSubTab === 'data'" class="space-y-4">
              <div class="bg-orange-50 border border-orange-100 rounded-xl p-4">
                <p class="text-[10px] text-orange-700 font-bold">
                  表级权限：空 = 无权限，ALL = 所有表。数据源权限影响 SQL 实验室与动态查询接口。
                </p>
              </div>

              <p v-if="filteredDataSources.length === 0" class="text-center text-gray-400 py-8 text-sm">无匹配的数据源</p>

              <div
                v-for="ds in filteredDataSources"
                :key="ds.source_name"
                class="bg-gray-50 rounded-2xl border border-gray-100 overflow-hidden shadow-sm"
              >
                <div class="px-5 py-3 bg-white border-b border-gray-100 flex items-center justify-between gap-2">
                  <div class="flex items-center gap-3 min-w-0">
                    <input
                      type="checkbox"
                      :value="`ds:${ds.source_name}`"
                      v-model="selectedDataSources"
                      class="h-5 w-5 text-orange-600 rounded-lg border-gray-300 focus:ring-orange-500 shrink-0"
                    />
                    <span class="text-sm font-black text-gray-800 truncate">{{ ds.source_name }}</span>
                    <span class="bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded text-[9px] font-bold border border-gray-200 shrink-0">
                      {{ ds.source_type }}
                    </span>
                  </div>
                  <button
                    v-if="selectedDataSources.includes(`ds:${ds.source_name}`)"
                    @click="toggleDSExpand(ds.source_name)"
                    class="text-[10px] font-bold text-orange-600 hover:underline shrink-0"
                  >
                    {{ expandedDSSet.has(ds.source_name) ? '收起表权限' : '配置表权限' }}
                  </button>
                </div>

                <div
                  v-if="expandedDSSet.has(ds.source_name) && selectedDataSources.includes(`ds:${ds.source_name}`)"
                  class="p-5 bg-white border-t border-gray-50 space-y-4"
                >
                  <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <button
                      @click="setDSAllTables(ds.source_name)"
                      :class="isDSAllTables(ds.source_name) ? 'bg-orange-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
                      class="px-3 py-1 rounded text-[10px] font-bold transition-all"
                    >
                      所有表 (ALL)
                    </button>
                    <div class="relative w-full sm:w-48">
                      <input
                        :value="tableSearchByDS[ds.source_name] || ''"
                        @input="setTableSearch(ds.source_name, ($event.target as HTMLInputElement).value)"
                        placeholder="搜索表名..."
                        class="w-full text-xs border border-gray-200 rounded-lg px-2 py-1.5 outline-none focus:ring-1 focus:ring-orange-500"
                      />
                    </div>
                  </div>

                  <div v-if="loadingTablesByDS[ds.source_name]" class="py-8 text-center">
                    <div class="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-orange-600"></div>
                  </div>

                  <div v-else class="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-60 overflow-y-auto custom-scrollbar p-1">
                    <label
                      v-for="table in filteredTablesForDS(ds.source_name)"
                      :key="typeof table === 'string' ? table : table.name"
                      class="flex items-center p-2 rounded-lg border cursor-pointer transition-all"
                      :class="
                        selectedDataTables.includes(`ds:${ds.source_name}:table:${typeof table === 'string' ? table : table.name}`)
                          ? 'bg-orange-50 border-orange-200'
                          : 'bg-white border-transparent hover:border-gray-100'
                      "
                    >
                      <input
                        type="checkbox"
                        :value="`ds:${ds.source_name}:table:${typeof table === 'string' ? table : table.name}`"
                        v-model="selectedDataTables"
                        class="h-3 w-3 text-orange-600 rounded border-gray-300 focus:ring-orange-500"
                      />
                      <div class="ml-2 flex flex-col min-w-0">
                        <span class="text-[10px] font-medium text-gray-600 truncate">
                          {{ typeof table === 'string' ? table : table.name }}
                        </span>
                        <span
                          v-if="typeof table !== 'string'"
                          :class="table.type === 'VIEW' ? 'text-amber-500' : 'text-blue-500'"
                          class="text-[8px] font-black uppercase"
                        >
                          {{ table.type }}
                        </span>
                      </div>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="px-4 sm:px-8 py-4 sm:py-6 bg-gray-50 border-t flex justify-end gap-3 shrink-0">
          <button @click="tryCloseEditModal" class="px-6 py-2.5 text-gray-500 font-bold hover:text-gray-700 transition-colors">
            取消
          </button>
          <button
            @click="saveRole"
            :disabled="submitting"
            class="px-8 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-lg transition-all disabled:opacity-50 flex items-center gap-2"
          >
            <span v-if="submitting" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
            确认保存
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="showDeleteModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-gray-900/60 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        <div class="p-6 text-center">
          <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 mb-4">
            <TrashIcon class="h-6 w-6 text-red-600" />
          </div>
          <h3 class="text-lg font-bold text-gray-900 mb-2">确认删除角色?</h3>
          <p class="text-sm text-gray-500 mb-4">
            您即将删除角色 <span class="font-bold text-gray-800">{{ roleToDelete?.role_name }}</span>。
          </p>
          <div
            v-if="(roleToDelete?.stats?.user || 0) > 0"
            class="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-left text-sm text-amber-800"
          >
            <p class="font-bold">该角色仍有 {{ roleToDelete.stats.user }} 名成员</p>
            <p class="mt-1 text-xs">删除后这些用户将失去该角色继承的全部权限，且不可撤销。</p>
          </div>
          <p v-else class="text-sm text-red-500 font-bold mb-4">此操作不可撤销。</p>
          <div class="flex gap-3">
            <button @click="showDeleteModal = false" class="flex-1 py-2.5 bg-gray-100 text-gray-700 font-bold rounded-lg hover:bg-gray-200">
              取消
            </button>
            <button @click="executeDeleteRole" class="flex-1 py-2.5 bg-red-600 text-white font-bold rounded-lg hover:bg-red-700 shadow-lg">
              {{ (roleToDelete?.stats?.user || 0) > 0 ? '仍要删除' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Role Members Dialog -->
    <div
      v-if="showMemberModal"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9990] p-2 sm:p-4"
      @click.self="showMemberModal = false"
    >
      <div class="bg-white rounded-3xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        <div class="px-6 sm:px-8 py-5 border-b bg-gray-50 flex justify-between items-center shrink-0">
          <div>
            <h2 class="text-xl font-bold text-gray-900">成员管理</h2>
            <p class="text-xs text-gray-500 mt-1">
              当前角色：<span class="font-bold text-indigo-600">{{ currentRole?.role_name }}</span>
            </p>
          </div>
          <button @click="showMemberModal = false" class="text-gray-400 hover:text-gray-600">
            <XMarkIcon class="w-6 h-6" />
          </button>
        </div>

        <div class="p-4 sm:p-6 flex-1 min-h-0 overflow-hidden flex flex-col">
          <div v-if="loadingMembers" class="py-12 text-center">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            <p class="mt-2 text-gray-500">获取成员数据中...</p>
          </div>
          <template v-else>
            <div class="flex flex-col sm:flex-row gap-3 flex-1 min-h-0 h-[min(420px,calc(90vh-220px))]">
              <!-- Available -->
              <div class="flex-1 min-w-0 min-h-0 flex flex-col border border-gray-200 rounded-2xl overflow-hidden">
                <div class="px-4 py-2 bg-gray-50 border-b space-y-2 shrink-0">
                  <span class="text-xs font-bold text-gray-600">备选用户 ({{ filteredAvailableUsers.length }})</span>
                  <input
                    v-model="userSearchAvailable"
                    placeholder="搜索用户名..."
                    class="w-full text-xs border border-gray-300 rounded-lg px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
                  />
                </div>
                <div class="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-2 space-y-1">
                  <div
                    v-for="user in filteredAvailableUsers"
                    :key="user.id"
                    @click="toggleMemberSelection(user.id)"
                    @dblclick="addMember(user)"
                    class="p-2 rounded-lg text-sm cursor-pointer transition-all flex items-center justify-between gap-2"
                    :class="selectedMemberIds.includes(user.id) ? 'bg-indigo-600 text-white shadow-sm' : 'hover:bg-gray-100 text-gray-700'"
                  >
                    <div class="min-w-0">
                      <div class="font-medium truncate">{{ user.user_name }}</div>
                      <div class="text-[10px] opacity-80 mt-0.5 truncate">{{ formatUserMeta(user) }}</div>
                    </div>
                    <button
                      type="button"
                      class="shrink-0 p-1 rounded-md border transition-colors"
                      :class="selectedMemberIds.includes(user.id) ? 'border-white/40 hover:bg-white/20' : 'border-gray-200 hover:bg-indigo-50 hover:border-indigo-200 hover:text-indigo-600'"
                      title="添加此用户"
                      @click.stop="addMember(user)"
                    >
                      <ChevronRightIcon class="w-4 h-4" />
                    </button>
                  </div>
                  <p v-if="filteredAvailableUsers.length === 0" class="text-center text-gray-400 text-xs py-6">无匹配用户</p>
                </div>
              </div>

              <!-- Transfer Buttons -->
              <div class="flex sm:flex-col justify-center items-center gap-3 shrink-0 py-1 sm:py-0 sm:px-1">
                <button
                  @click="moveToSelected"
                  :disabled="!selectedMemberIds.length"
                  class="w-full sm:w-12 h-10 sm:h-12 flex items-center justify-center gap-1 rounded-xl border-2 border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-600 hover:text-white hover:border-indigo-600 transition-all disabled:opacity-30 disabled:hover:bg-indigo-50 disabled:hover:text-indigo-700 disabled:hover:border-indigo-200 text-xs sm:text-sm font-bold"
                  title="将左侧选中用户添加到角色"
                >
                  <span class="sm:hidden">添加选中</span>
                  <ChevronRightIcon class="w-5 h-5" />
                </button>
                <button
                  @click="moveToAvailable"
                  :disabled="!selectedInSelectedIds.length"
                  class="w-full sm:w-12 h-10 sm:h-12 flex items-center justify-center gap-1 rounded-xl border-2 border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-600 hover:text-white hover:border-indigo-600 transition-all disabled:opacity-30 disabled:hover:bg-indigo-50 disabled:hover:text-indigo-700 disabled:hover:border-indigo-200 text-xs sm:text-sm font-bold"
                  title="将右侧选中用户移出角色"
                >
                  <ChevronLeftIcon class="w-5 h-5" />
                  <span class="sm:hidden">移除选中</span>
                </button>
              </div>

              <!-- Selected -->
              <div class="flex-1 min-w-0 min-h-0 flex flex-col border border-indigo-200 rounded-2xl overflow-hidden bg-indigo-50/10">
                <div class="px-4 py-2 bg-indigo-50 border-b border-indigo-100 space-y-2 shrink-0">
                  <span class="text-xs font-bold text-indigo-600">已分配成员 ({{ filteredRoleMembers.length }})</span>
                  <input
                    v-model="userSearchSelected"
                    placeholder="搜索已分配用户..."
                    class="w-full text-xs border border-indigo-200 rounded-lg px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none bg-white"
                  />
                </div>
                <div class="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-2 space-y-1">
                  <div
                    v-for="user in filteredRoleMembers"
                    :key="user.id"
                    @click="toggleInSelectedSelection(user.id)"
                    @dblclick="removeMember(user)"
                    class="p-2 rounded-lg text-sm cursor-pointer transition-all flex items-center justify-between gap-2"
                    :class="selectedInSelectedIds.includes(user.id) ? 'bg-indigo-600 text-white shadow-sm' : 'hover:bg-indigo-100/50 text-gray-700'"
                  >
                    <button
                      type="button"
                      class="shrink-0 p-1 rounded-md border transition-colors"
                      :class="selectedInSelectedIds.includes(user.id) ? 'border-white/40 hover:bg-white/20' : 'border-indigo-200 hover:bg-white hover:text-indigo-600'"
                      title="移除此用户"
                      @click.stop="removeMember(user)"
                    >
                      <ChevronLeftIcon class="w-4 h-4" />
                    </button>
                    <div class="min-w-0 flex-1 text-right sm:text-left">
                      <div class="font-medium truncate">{{ user.user_name }}</div>
                      <div class="text-[10px] opacity-80 mt-0.5 truncate">{{ formatUserMeta(user) }}</div>
                    </div>
                  </div>
                  <p v-if="filteredRoleMembers.length === 0" class="text-center text-gray-400 text-xs py-6">暂无成员</p>
                </div>
              </div>
            </div>
            <p class="text-xs text-gray-500 mt-3 text-center shrink-0">
              单击选中后点中间 <strong class="text-indigo-600">→ ←</strong> 批量操作；双击行可快速添加/移除；也可点行内箭头单独操作
            </p>
          </template>
        </div>

        <div class="px-6 sm:px-8 py-4 bg-gray-50 border-t flex justify-end gap-3 shrink-0">
          <button @click="showMemberModal = false" class="px-6 py-2.5 text-gray-500 font-bold hover:text-gray-700">取消</button>
          <button
            @click="saveMembers"
            :disabled="submittingMembers"
            class="px-8 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-lg disabled:opacity-50 flex items-center gap-2"
          >
            <span v-if="submittingMembers" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
            保存更改
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :show="showDiscardConfirm"
      title="放弃未保存的更改？"
      message="当前编辑内容尚未保存，关闭后将丢失这些修改。"
      type="warning"
      confirm-text="仍要关闭"
      :z-index="10001"
      @confirm="confirmDiscardEdit"
      @cancel="showDiscardConfirm = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch, reactive } from 'vue'
import axios from '../utils/axios'
import { useToast } from '../composables/useToast'
import {
  PERMISSION_MENU_TREE,
  getMenuChildIds,
  type PermissionMenuNode,
} from '@/constants/permissionMenuTree'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import {
  PlusIcon,
  UserGroupIcon,
  PencilSquareIcon,
  TrashIcon,
  XMarkIcon,
  ClockIcon,
  UserPlusIcon,
  ChevronRightIcon,
  ChevronLeftIcon,
  ChevronDownIcon,
  Squares2X2Icon,
  ListBulletIcon,
} from '@heroicons/vue/24/outline'

const { showToast } = useToast()
const ROLE_CODE_PATTERN = /^[a-z][a-z0-9_]*$/
const ROLES_VIEW_MODE_KEY = 'roles_view_mode'

const roles = ref<any[]>([])
const loading = ref(false)
const roleSearch = ref('')
const sortBy = ref<'created_desc' | 'created_asc' | 'name_asc' | 'members_desc'>('created_desc')
const viewMode = ref<'card' | 'list'>(
  (localStorage.getItem(ROLES_VIEW_MODE_KEY) as 'card' | 'list') || 'card',
)

const showEditModal = ref(false)
const showDiscardConfirm = ref(false)
const showDeleteModal = ref(false)
const roleToDelete = ref<any>(null)
const isEdit = ref(false)
const submitting = ref(false)
const activeTab = ref<'info' | 'permissions'>('info')
const activePermissionSubTab = ref<'resource' | 'ui' | 'data'>('resource')
const permissionSearch = ref('')
const collapsedGroups = ref<Set<string>>(new Set())
const formSnapshot = ref('')

const formData = ref({
  id: null as number | null,
  role_name: '',
  role_code: '',
  description: '',
  rate_limit: null as number | null,
  masking_strategy: 'GLOBAL',
})

const showMemberModal = ref(false)
const loadingMembers = ref(false)
const submittingMembers = ref(false)
const currentRole = ref<any>(null)
const allUsers = ref<any[]>([])
const roleMembers = ref<any[]>([])
const userSearchAvailable = ref('')
const userSearchSelected = ref('')
const selectedMemberIds = ref<number[]>([])
const selectedInSelectedIds = ref<number[]>([])

const selectedMenus = ref<string[]>([])
const selectedElements = ref<string[]>([])
const selectedResources = ref<string[]>([])
const selectedDataSources = ref<string[]>([])
const selectedDataTables = ref<string[]>([])

const allDataSources = ref<any[]>([])
const expandedDSSet = ref<Set<string>>(new Set())
const dsTablesCache = reactive<Record<string, any[]>>({})
const loadingTablesByDS = reactive<Record<string, boolean>>({})
const tableSearchByDS = reactive<Record<string, string>>({})

const availableResources = ref<any[]>([])

const roleNameById = computed(() => {
  const map: Record<number, string> = {}
  roles.value.forEach((r) => {
    map[r.id] = r.role_name
  })
  return map
})

const permissionSubTabs = computed(() => [
  {
    key: 'resource' as const,
    label: '接口资源',
    count: selectedResources.value.length,
    badgeClass: 'bg-indigo-100 text-indigo-600',
  },
  {
    key: 'ui' as const,
    label: '功能与菜单',
    count: selectedMenus.value.length + selectedElements.value.length,
    badgeClass: 'bg-purple-100 text-purple-600',
  },
  {
    key: 'data' as const,
    label: '数据资产',
    count: selectedDataSources.value.length + selectedDataTables.value.length,
    badgeClass: 'bg-orange-100 text-orange-600',
  },
])

const filteredRoles = computed(() => {
  let list = [...roles.value]
  const q = roleSearch.value.trim().toLowerCase()
  if (q) {
    list = list.filter(
      (r) =>
        r.role_name?.toLowerCase().includes(q) ||
        r.role_code?.toLowerCase().includes(q) ||
        r.description?.toLowerCase().includes(q),
    )
  }
  switch (sortBy.value) {
    case 'created_asc':
      list.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      break
    case 'name_asc':
      list.sort((a, b) => (a.role_name || '').localeCompare(b.role_name || '', 'zh-CN'))
      break
    case 'members_desc':
      list.sort((a, b) => (b.stats?.user || 0) - (a.stats?.user || 0))
      break
    default:
      list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  }
  return list
})

const groupedResources = computed(() => {
  const groups: Record<string, any[]> = {}
  availableResources.value.forEach((res: any) => {
    const g = res.group || '其他'
    if (!groups[g]) groups[g] = []
    groups[g].push(res)
  })
  return groups
})

const filteredGroupedResources = computed(() => {
  const q = permissionSearch.value.trim().toLowerCase()
  const result: Record<string, any[]> = {}
  Object.entries(groupedResources.value).forEach(([group, resources]) => {
    let filtered = resources
    if (q) {
      filtered = resources.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          r.id.toLowerCase().includes(q) ||
          group.toLowerCase().includes(q),
      )
    }
    if (filtered.length) result[group] = filtered
  })
  return result
})

const filteredMenuTree = computed(() => {
  const q = permissionSearch.value.trim().toLowerCase()
  if (!q) return PERMISSION_MENU_TREE
  return PERMISSION_MENU_TREE.filter((menu) => {
    if (menu.label.toLowerCase().includes(q) || menu.id.toLowerCase().includes(q)) return true
    return menu.children.some(
      (c) => c.label.toLowerCase().includes(q) || c.id.toLowerCase().includes(q),
    )
  }).map((menu) => {
    if (menu.label.toLowerCase().includes(q) || menu.id.toLowerCase().includes(q)) return menu
    return {
      ...menu,
      children: menu.children.filter(
        (c) => c.label.toLowerCase().includes(q) || c.id.toLowerCase().includes(q),
      ),
    }
  })
})

const filteredDataSources = computed(() => {
  const q = permissionSearch.value.trim().toLowerCase()
  if (!q) return allDataSources.value
  return allDataSources.value.filter(
    (ds) =>
      ds.source_name.toLowerCase().includes(q) ||
      (ds.source_type || '').toLowerCase().includes(q),
  )
})

const availableUsers = computed(() => {
  const memberIds = roleMembers.value.map((m) => m.id)
  return allUsers.value.filter((u) => !memberIds.includes(u.id))
})

const filteredAvailableUsers = computed(() => {
  const q = userSearchAvailable.value.trim().toLowerCase()
  if (!q) return availableUsers.value
  return availableUsers.value.filter((u) => u.user_name.toLowerCase().includes(q))
})

const filteredRoleMembers = computed(() => {
  const q = userSearchSelected.value.trim().toLowerCase()
  if (!q) return roleMembers.value
  return roleMembers.value.filter((u) => u.user_name.toLowerCase().includes(q))
})

const captureFormSnapshot = () =>
  JSON.stringify({
    form: formData.value,
    menus: selectedMenus.value,
    elements: selectedElements.value,
    resources: selectedResources.value,
    datasources: selectedDataSources.value,
    data_tables: selectedDataTables.value,
  })

const hasUnsavedChanges = computed(
  () => showEditModal.value && formSnapshot.value !== captureFormSnapshot(),
)

const formatUserMeta = (user: any) => {
  const sysRole = user.role === 'admin' ? '系统管理员' : '普通用户'
  const biz = (user.role_ids || [])
    .map((id: number) => roleNameById.value[id])
    .filter(Boolean)
  const bizText = biz.length ? biz.join('、') : '无业务角色'
  return `${sysRole} · ${bizText}`
}

const resetPermissionState = () => {
  selectedMenus.value = []
  selectedElements.value = []
  selectedResources.value = []
  selectedDataSources.value = []
  selectedDataTables.value = []
  expandedDSSet.value = new Set()
  permissionSearch.value = ''
  collapsedGroups.value = new Set()
  Object.keys(dsTablesCache).forEach((k) => delete dsTablesCache[k])
  Object.keys(loadingTablesByDS).forEach((k) => delete loadingTablesByDS[k])
  Object.keys(tableSearchByDS).forEach((k) => delete tableSearchByDS[k])
}

const tryCloseEditModal = () => {
  if (hasUnsavedChanges.value) {
    showDiscardConfirm.value = true
    return
  }
  showEditModal.value = false
}

const confirmDiscardEdit = () => {
  showDiscardConfirm.value = false
  showEditModal.value = false
}

const goToPermissionsTab = () => {
  if (!formData.value.role_name?.trim()) {
    showToast('请先填写角色名称', 'warning')
    activeTab.value = 'info'
    return
  }
  if (!isEdit.value && !formData.value.role_code?.trim()) {
    showToast('请先填写角色编码', 'warning')
    activeTab.value = 'info'
    return
  }
  activeTab.value = 'permissions'
}

const toggleGroupCollapse = (group: string) => {
  const next = new Set(collapsedGroups.value)
  if (next.has(group)) next.delete(group)
  else next.add(group)
  collapsedGroups.value = next
}

const onMenuToggle = (menu: PermissionMenuNode, event: Event) => {
  const checked = (event.target as HTMLInputElement).checked
  if (checked && menu.children.length) {
    menu.children.forEach((c) => {
      if (!selectedElements.value.includes(c.id)) selectedElements.value.push(c.id)
    })
  }
}

const fetchAvailableResources = async () => {
  try {
    const apiKey = localStorage.getItem('api_key')
    const response = await axios.get('/api/portal/meta/resources', {
      headers: { 'X-API-Key': apiKey },
    })
    availableResources.value = response.data.map((r: any) => ({
      id: r.resource_key,
      name: r.resource_name,
      group: r.resource_group || '其他',
    }))
  } catch {
    /* ignore */
  }
}

const toggleGroupSelection = (resources: any[]) => {
  if (isGroupAllSelected(resources)) {
    const idsToRemove = resources.map((r) => r.id)
    selectedResources.value = selectedResources.value.filter((id) => !idsToRemove.includes(id))
  } else {
    resources.forEach((r) => {
      if (!selectedResources.value.includes(r.id)) selectedResources.value.push(r.id)
    })
  }
}

const isGroupAllSelected = (resources: any[]) =>
  resources.length > 0 && resources.every((r) => selectedResources.value.includes(r.id))

const loadDSTables = async (dsName: string) => {
  if (dsTablesCache[dsName]) return
  loadingTablesByDS[dsName] = true
  try {
    const res = await axios.post('/api/portal/meta/datasource/tables', { data_source: dsName })
    dsTablesCache[dsName] = res.data.tables || []
  } catch {
    showToast('获取表列表失败', 'error')
    dsTablesCache[dsName] = []
  } finally {
    loadingTablesByDS[dsName] = false
  }
}

const toggleDSExpand = async (dsName: string) => {
  const next = new Set(expandedDSSet.value)
  if (next.has(dsName)) {
    next.delete(dsName)
  } else {
    next.add(dsName)
    await loadDSTables(dsName)
  }
  expandedDSSet.value = next
}

const setTableSearch = (dsName: string, value: string) => {
  tableSearchByDS[dsName] = value
}

const filteredTablesForDS = (dsName: string) => {
  const tables = dsTablesCache[dsName] || []
  const q = (tableSearchByDS[dsName] || '').trim().toLowerCase()
  if (!q) return tables
  return tables.filter((t) => (typeof t === 'string' ? t : t.name).toLowerCase().includes(q))
}

const isDSAllTables = (dsName: string) => selectedDataTables.value.includes(`ds:${dsName}:table:*`)

const setDSAllTables = (dsName: string) => {
  const allKey = `ds:${dsName}:table:*`
  if (isDSAllTables(dsName)) {
    selectedDataTables.value = selectedDataTables.value.filter((k) => k !== allKey)
  } else {
    selectedDataTables.value = selectedDataTables.value.filter((k) => !k.startsWith(`ds:${dsName}:table:`))
    selectedDataTables.value.push(allKey)
  }
}

const autoExpandConfiguredDataSources = async () => {
  const dsNames = new Set<string>()
  selectedDataSources.value.forEach((code) => dsNames.add(code.replace('ds:', '')))
  selectedDataTables.value.forEach((key) => {
    const m = key.match(/^ds:([^:]+):table:/)
    if (m?.[1]) dsNames.add(m[1])
  })
  const next = new Set(expandedDSSet.value)
  for (const name of dsNames) {
    next.add(name)
    await loadDSTables(name)
  }
  expandedDSSet.value = next
}

const fetchAllDataSources = async () => {
  try {
    const res = await axios.get('/api/portal/datasource/datasources')
    allDataSources.value = res.data
  } catch {
    /* ignore */
  }
}

watch(selectedDataSources, (newVal, oldVal) => {
  if (!oldVal) return
  const removedDS = oldVal.filter((ds) => !newVal.includes(ds))
  removedDS.forEach((dsCode) => {
    selectedDataTables.value = selectedDataTables.value.filter((t) => !t.startsWith(`${dsCode}:table:`))
    const dsName = dsCode.replace('ds:', '')
    const next = new Set(expandedDSSet.value)
    next.delete(dsName)
    expandedDSSet.value = next
  })
})

watch(selectedMenus, (newVal, oldVal) => {
  if (!oldVal) return
  const removedMenus = oldVal.filter((m) => !newVal.includes(m))
  removedMenus.forEach((menuId) => {
    const childIds = getMenuChildIds(menuId)
    selectedElements.value = selectedElements.value.filter((eid) => !childIds.includes(eid))
  })
})

const fetchRoles = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/portal/management/roles')
    roles.value = res.data
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  isEdit.value = false
  activeTab.value = 'info'
  formData.value = {
    id: null,
    role_name: '',
    role_code: '',
    description: '',
    rate_limit: null,
    masking_strategy: 'GLOBAL',
  }
  resetPermissionState()
  showEditModal.value = true
  formSnapshot.value = captureFormSnapshot()
}

const editRole = async (role: any) => {
  isEdit.value = true
  activeTab.value = 'info'
  formData.value = {
    id: role.id,
    role_name: role.role_name,
    role_code: role.role_code,
    description: role.description,
    rate_limit: role.rate_limit ?? null,
    masking_strategy: role.masking_strategy || 'GLOBAL',
  }
  resetPermissionState()

  try {
    const res = await axios.get(`/api/portal/management/roles/${role.id}/permissions`)
    selectedMenus.value = res.data.menus || []
    selectedElements.value = res.data.elements || []
    selectedResources.value = res.data.resources || []
    selectedDataSources.value = res.data.datasources || []
    selectedDataTables.value = res.data.data_tables || []
    if (res.data.rate_limit != null) formData.value.rate_limit = res.data.rate_limit
    await autoExpandConfiguredDataSources()
  } catch {
    selectedMenus.value = []
    selectedElements.value = []
    selectedResources.value = []
    selectedDataSources.value = []
    selectedDataTables.value = []
  }

  showEditModal.value = true
  formSnapshot.value = captureFormSnapshot()
}

const saveRole = async () => {
  if (!formData.value.role_name?.trim() || !formData.value.role_code?.trim()) {
    showToast('请填写角色名称和编码', 'warning')
    return
  }
  if (!isEdit.value && !ROLE_CODE_PATTERN.test(formData.value.role_code)) {
    showToast('角色编码须以小写字母开头，仅含小写字母、数字和下划线', 'warning')
    return
  }

  submitting.value = true
  try {
    let roleId = formData.value.id
    const payload = {
      role_name: formData.value.role_name,
      role_code: formData.value.role_code,
      description: formData.value.description,
      masking_strategy: formData.value.masking_strategy,
    }

    if (isEdit.value) {
      await axios.put(`/api/portal/management/roles/${roleId}`, payload)
    } else {
      await axios.post('/api/portal/management/roles', payload)
      await fetchRoles()
      const newRole = roles.value.find((r) => r.role_code === formData.value.role_code)
      if (newRole) roleId = newRole.id
    }

    if (roleId) {
      const allUiIds = [...selectedMenus.value, ...selectedElements.value]
      const finalMenus = allUiIds.filter((id) => id.startsWith('menu:'))
      const finalElements = allUiIds.filter((id) => id.startsWith('element:'))
      const rateLimit =
        formData.value.rate_limit == null ? 0 : Number(formData.value.rate_limit)

      await axios.put(`/api/portal/management/roles/${roleId}/permissions`, {
        menus: Array.from(new Set(finalMenus)),
        elements: Array.from(new Set(finalElements)),
        resources: selectedResources.value,
        datasources: selectedDataSources.value,
        data_tables: selectedDataTables.value,
        rate_limit: rateLimit,
      })
    }

    showToast('角色保存成功', 'success')
    showEditModal.value = false
    formSnapshot.value = captureFormSnapshot()
    fetchRoles()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '操作失败', 'error')
  } finally {
    submitting.value = false
  }
}

const confirmDelete = (role: any) => {
  roleToDelete.value = role
  showDeleteModal.value = true
}

const executeDeleteRole = async () => {
  if (!roleToDelete.value) return
  try {
    await axios.delete(`/api/portal/management/roles/${roleToDelete.value.id}`)
    showToast('删除成功', 'success')
    showDeleteModal.value = false
    fetchRoles()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

const openMemberDialog = async (role: any) => {
  currentRole.value = role
  showMemberModal.value = true
  loadingMembers.value = true
  selectedMemberIds.value = []
  selectedInSelectedIds.value = []
  userSearchAvailable.value = ''
  userSearchSelected.value = ''

  try {
    const [usersRes, membersRes] = await Promise.all([
      axios.get('/api/portal/management/users?size=1000'),
      axios.get(`/api/portal/management/roles/${role.id}/users`),
    ])
    allUsers.value = usersRes.data.items || []
    const memberIds = membersRes.data || []
    roleMembers.value = allUsers.value.filter((u) => memberIds.includes(u.id))
  } catch {
    showToast('获取成员数据失败', 'error')
  } finally {
    loadingMembers.value = false
  }
}

const toggleMemberSelection = (id: number) => {
  const idx = selectedMemberIds.value.indexOf(id)
  if (idx > -1) selectedMemberIds.value.splice(idx, 1)
  else selectedMemberIds.value.push(id)
}

const toggleInSelectedSelection = (id: number) => {
  const idx = selectedInSelectedIds.value.indexOf(id)
  if (idx > -1) selectedInSelectedIds.value.splice(idx, 1)
  else selectedInSelectedIds.value.push(id)
}

const addMember = (user: any) => {
  if (!roleMembers.value.find((m) => m.id === user.id)) {
    roleMembers.value = [...roleMembers.value, user]
  }
  selectedMemberIds.value = selectedMemberIds.value.filter((id) => id !== user.id)
}

const removeMember = (user: any) => {
  roleMembers.value = roleMembers.value.filter((m) => m.id !== user.id)
  selectedInSelectedIds.value = selectedInSelectedIds.value.filter((id) => id !== user.id)
}

const moveToSelected = () => {
  const usersToMove = allUsers.value.filter((u) => selectedMemberIds.value.includes(u.id))
  const existingIds = new Set(roleMembers.value.map((m) => m.id))
  roleMembers.value = [...roleMembers.value, ...usersToMove.filter((u) => !existingIds.has(u.id))]
  selectedMemberIds.value = []
}

const moveToAvailable = () => {
  roleMembers.value = roleMembers.value.filter((m) => !selectedInSelectedIds.value.includes(m.id))
  selectedInSelectedIds.value = []
}

const saveMembers = async () => {
  submittingMembers.value = true
  try {
    const userIds = roleMembers.value.map((m) => m.id)
    await axios.put(`/api/portal/management/roles/${currentRole.value.id}/users`, { user_ids: userIds })
    showToast('成员分配更新成功', 'success')
    showMemberModal.value = false
    fetchRoles()
  } catch (e: any) {
    showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    submittingMembers.value = false
  }
}

const formatDate = (d: string) =>
  d
    ? new Date(d).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '-'

const maskingLabel = (strategy?: string) => {
  if (strategy === 'ENABLE') return '强制脱敏'
  if (strategy === 'DISABLE') return '允许明文'
  return '跟随全局'
}

watch(viewMode, (mode) => {
  localStorage.setItem(ROLES_VIEW_MODE_KEY, mode)
})

onMounted(() => {
  fetchRoles()
  fetchAvailableResources()
  fetchAllDataSources()
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #f1f1f1;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 10px;
}
</style>
