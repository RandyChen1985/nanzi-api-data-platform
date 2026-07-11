<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex justify-between items-center">
      <h1 class="text-2xl font-bold text-gray-900">用户管理</h1>
      <button 
        @click="showCreateDialog = true" 
        class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition flex items-center gap-2"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        创建用户
      </button>
    </div>

    <!-- Filters -->
    <div class="bg-white shadow rounded-lg p-4">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <input 
          v-model="searchQuery" 
          @input="debouncedSearch"
          type="text" 
          placeholder="搜索用户名..." 
          class="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select 
          v-model="roleFilter" 
          @change="fetchUsers"
          class="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">所有角色</option>
          <option value="admin">管理员</option>
          <option value="user">普通用户</option>
        </select>
        <select 
          v-model="statusFilter" 
          @change="fetchUsers"
          class="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">所有状态</option>
          <option value="1">启用</option>
          <option value="0">禁用</option>
        </select>
        <button 
          @click="resetFilters" 
          class="border border-gray-300 rounded-lg px-4 py-2 hover:bg-gray-50 transition"
        >
          重置筛选
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="bg-white shadow rounded-lg p-12 text-center">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      <p class="mt-2 text-gray-500">加载中...</p>
    </div>

    <!-- User List -->
    <div v-else-if="users.length > 0" class="bg-white shadow rounded-lg overflow-hidden">
      <!-- Table Container with Horizontal Scroll -->
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">ID</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">用户名</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">角色</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">备注</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">状态</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">创建时间</th>
              <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">操作</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="user in users" :key="user.id" class="hover:bg-gray-50">
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{{ user.id }}</td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center">
                    <span class="text-sm font-medium text-gray-900">{{ user.user_name }}</span>
                    <span v-if="user.remark" class="custom-tooltip ml-2" :data-tooltip="user.remark">
                        <svg class="w-4 h-4 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    </span>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span :class="user.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'" class="px-2 py-1 text-xs font-semibold rounded-full">
                  {{ user.role === 'admin' ? '管理员' : '普通用户' }}
                </span>
              </td>
              <td class="px-6 py-4 text-sm text-gray-500 max-w-xs">
                <span :title="user.remark" class="truncate block">{{ user.remark || '-' }}</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center">
                  <Switch 
                    :model-value="user.status === 1" 
                    @update:model-value="toggleStatus(user)"
                  />
                  <span class="ml-2 text-xs" :class="user.status === 1 ? 'text-green-600' : 'text-gray-400'">
                    {{ user.status === 1 ? '已启用' : '已禁用' }}
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ formatDate(user.created_at) }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-right">
                <div class="flex justify-end items-center gap-1.5">
                  <button
                    @click="editUser(user)"
                    class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 border border-gray-200 hover:border-gray-300 rounded-md transition-all duration-150 active:scale-95"
                  >
                    <PencilSquareIcon class="w-3.5 h-3.5" /> 编辑
                  </button>
                  <!-- 更多下拉 -->
                  <div class="relative" @click.stop>
                    <button
                      type="button"
                      class="inline-flex items-center gap-0.5 px-2 py-1 text-xs font-medium bg-white hover:bg-gray-50 border border-gray-200 hover:border-gray-300 rounded-md transition-all duration-150 active:scale-95"
                      :class="openMore === user.id ? 'text-gray-700 bg-gray-50 border-gray-300' : 'text-gray-500'"
                      @click="toggleMore(user.id, $event)"
                    >
                      更多
                      <svg class="w-3 h-3 transition-transform duration-150" :class="openMore === user.id ? 'rotate-180' : ''" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                    </button>
                    <div
                      v-if="openMore === user.id"
                      class="absolute right-0 top-full mt-1 w-36 bg-white border border-gray-100 rounded-lg shadow-xl z-50 py-1 overflow-hidden"
                    >
                      <button
                        type="button"
                        class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 transition-colors"
                        @click="viewApiKey(user); openMore = null"
                      >
                        <KeyIcon class="w-3.5 h-3.5 shrink-0" />
                        查看 API Key
                      </button>
                      <button
                        type="button"
                        class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-amber-600 hover:bg-amber-50 transition-colors"
                        @click="regenerateApiKey(user); openMore = null"
                      >
                        <ArrowPathIcon class="w-3.5 h-3.5 shrink-0" />
                        重置 API Key
                      </button>
                      <div v-if="user.user_name !== 'admin'" class="h-px bg-gray-100 mx-2 my-1" />
                      <button
                        v-if="user.user_name !== 'admin'"
                        type="button"
                        class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 transition-colors"
                        @click="confirmDelete(user); openMore = null"
                      >
                        <TrashIcon class="w-3.5 h-3.5 shrink-0" />
                        删除用户
                      </button>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="bg-gray-50 px-4 py-3 flex items-center justify-between border-t border-gray-200">
        <div class="text-sm text-gray-700">
          共 {{ total }} 条记录，第 {{ page }} / {{ totalPages }} 页
        </div>
        <div class="flex gap-2">
          <button 
            @click="page > 1 && (page--, fetchUsers())" 
            :disabled="page <= 1"
            :class="page <= 1 ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-200'"
            class="px-3 py-1 border border-gray-300 rounded-lg"
          >
            上一页
          </button>
          <button 
            @click="page < totalPages && (page++, fetchUsers())" 
            :disabled="page >= totalPages"
            :class="page >= totalPages ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-200'"
            class="px-3 py-1 border border-gray-300 rounded-lg"
          >
            下一页
          </button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="bg-white shadow rounded-lg p-12 text-center">
      <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
      <h3 class="mt-2 text-sm font-medium text-gray-900">没有找到用户</h3>
      <p class="mt-1 text-sm text-gray-500">尝试调整筛选条件或创建新用户</p>
    </div>

    <!-- Create/Edit Dialog -->
    <div v-if="showCreateDialog || showEditDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9990]" @click.self="closeDialogs">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden transform transition-all">
        <div class="px-8 py-6 border-b bg-gray-50 flex justify-between items-center">
          <h2 class="text-xl font-bold text-gray-900">{{ showEditDialog ? '编辑用户权限' : '创建新用户' }}</h2>
          <button @click="closeDialogs" class="text-gray-400 hover:text-gray-600 transition-colors">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        
        <!-- Main Tabs -->
        <div class="flex border-b border-gray-200 bg-white px-8">
          <button @click="activeTab = 'basic'" class="px-6 py-4 text-sm font-bold border-b-2 transition-all" :class="activeTab === 'basic' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'">
            基础信息与角色
          </button>
          <button v-if="formData.role === 'user'" @click="activeTab = 'permissions'" class="px-6 py-4 text-sm font-bold border-b-2 transition-all" :class="activeTab === 'permissions' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'">
            精细化权限分配
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-8 custom-scrollbar bg-white">
          <!-- Basic Info Tab -->
          <div v-show="activeTab === 'basic'" class="space-y-6">
            <div class="grid grid-cols-2 gap-6">
              <div>
                <label class="block text-xs font-bold text-gray-500 uppercase mb-2">用户名</label>
                <input v-model="formData.user_name" type="text" :disabled="showEditDialog" class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none transition-all disabled:bg-gray-50 disabled:text-gray-400" placeholder="登录账号" />
              </div>
              <div>
                <label class="block text-xs font-bold text-gray-500 uppercase mb-2">系统角色</label>
                <select v-model="formData.role" class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none transition-all">
                  <option value="user">普通用户</option>
                  <option value="admin">管理员 (拥有全部权限)</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-bold text-gray-500 uppercase mb-2 flex items-center gap-2">
                  🚦 用户级限流 (User Limit)
                  <span class="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-normal normal-case border border-blue-100">优先级最高</span>
                </label>
                <div class="relative">
                  <input v-model.number="formData.rate_limit" type="number" class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none transition-all pr-12" placeholder="默认继承角色设置" />
                  <span class="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 text-xs font-bold">次/分</span>
                </div>
                <p class="mt-1 text-[10px] text-gray-400">覆盖角色和系统默认设置。留空则继承上级策略。</p>
              </div>
              <div>
                <label class="block text-xs font-bold text-gray-500 uppercase mb-2 flex items-center gap-2">
                  🛡️ 脱敏策略 (Masking)
                </label>
                <select v-model="formData.masking_strategy" class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none transition-all">
                  <option value="ROLE">跟随角色 (Follow Role)</option>
                  <option value="ENABLE">强制开启 (Force Enable)</option>
                  <option value="DISABLE">允许明文 (Allow Plaintext)</option>
                </select>
                <p class="mt-1 text-[10px] text-gray-400">用户个体的脱敏行为覆盖。仅对支持脱敏的接口生效。</p>
              </div>
            </div>

            <div v-if="formData.role === 'user' && availableRoles.length > 0">
              <label class="block text-xs font-bold text-gray-500 uppercase mb-3 flex items-center gap-2">
                所属业务角色 <span class="text-[10px] font-normal lowercase text-gray-400 font-mono">(Inherited Roles)</span>
              </label>
              <div class="grid grid-cols-3 gap-3">
                <label v-for="role in availableRoles" :key="role.id" 
                  class="flex items-center p-3 rounded-xl border cursor-pointer transition-all"
                  :class="selectedRoles.includes(role.id) ? 'bg-indigo-50 border-indigo-200 ring-1 ring-indigo-200' : 'bg-white border-gray-200 hover:bg-gray-50'">
                  <input type="checkbox" :value="role.id" v-model="selectedRoles" class="h-4 w-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500" />
                  <div class="ml-3">
                    <p class="text-sm font-bold text-gray-800">{{ role.role_name }}</p>
                    <p class="text-[10px] text-gray-400 truncate">{{ role.role_code }}</p>
                  </div>
                </label>
              </div>
            </div>

            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-2">备注信息</label>
              <textarea v-model="formData.remark" rows="3" class="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none transition-all" placeholder="输入用户的备注说明..."></textarea>
            </div>

            <div v-if="createdApiKey" class="bg-amber-50 border border-amber-200 rounded-2xl p-6 animate-in fade-in slide-in-from-top-4 duration-500">
              <div class="flex items-center gap-3 mb-4">
                <div class="p-2 bg-amber-100 rounded-lg text-amber-600"><KeyIcon class="w-6 h-6" /></div>
                <p class="text-sm font-bold text-amber-900">请立即复制该用户的 API Key：</p>
              </div>
              <div class="flex items-center gap-2">
                <code class="flex-1 bg-white px-4 py-3 rounded-xl border border-amber-200 text-xs break-all font-mono select-all text-amber-700 font-bold shadow-sm">{{ createdApiKey }}</code>
                <button @click="copyApiKey" class="px-6 py-3 bg-amber-600 text-white rounded-xl hover:bg-amber-700 font-bold transition-all shadow-md">复制</button>
              </div>
            </div>
          </div>

          <!-- Permissions Tab (User Only) -->
          <div v-show="activeTab === 'permissions' && formData.role === 'user'" class="flex flex-col h-full min-h-[500px]">
            <!-- Sub Tabs -->
            <div class="flex space-x-1 p-1 bg-gray-100 rounded-xl mb-6 w-fit">
              <button @click="activePermissionSubTab = 'resource'" 
                :class="activePermissionSubTab === 'resource' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
                class="px-6 py-2 text-xs font-bold rounded-lg transition-all uppercase tracking-wider flex items-center gap-2">
                接口资源
                <span class="bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-md text-[10px]">
                  {{ selectedResources.length + inheritedResources.length }}
                </span>
              </button>
              <button @click="activePermissionSubTab = 'ui'" 
                :class="activePermissionSubTab === 'ui' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
                class="px-6 py-2 text-xs font-bold rounded-lg transition-all uppercase tracking-wider flex items-center gap-2">
                功能与菜单
                <span class="bg-indigo-100 text-indigo-600 px-1.5 py-0.5 rounded-md text-[10px]">
                  {{ selectedMenus.length + selectedElements.length + inheritedMenus.length + inheritedElements.length }}
                </span>
              </button>
              <button @click="activePermissionSubTab = 'data'" 
                :class="activePermissionSubTab === 'data' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
                class="px-6 py-2 text-xs font-bold rounded-lg transition-all uppercase tracking-wider flex items-center gap-2">
                数据资产 (SQL)
                <span class="bg-orange-100 text-orange-600 px-1.5 py-0.5 rounded-md text-[10px]">
                  {{ selectedDataSources.length + selectedDataTables.length + inheritedDataSources.length + inheritedDataTables.length }}
                </span>
              </button>
            </div>

            <!-- Resource Sub-Tab -->
            <div v-show="activePermissionSubTab === 'resource'" class="space-y-6 flex-1">
              <div v-for="(resources, group) in groupedResources" :key="group" class="bg-gray-50 rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
                <div class="px-5 py-3 bg-white border-b border-gray-100 flex items-center justify-between">
                  <span class="text-xs font-black text-gray-400 uppercase tracking-widest">{{ group }}</span>
                  <button @click="toggleGroupSelection(resources)" type="button" class="text-[10px] font-bold text-blue-600 hover:underline">
                    {{ isGroupAllSelected(resources) ? '取消全选' : '选择全部' }}
                  </button>
                </div>
                <div class="p-4 grid grid-cols-2 gap-3">
                  <label v-for="resource in resources" :key="resource.id" 
                    class="flex items-start p-3 rounded-xl border cursor-pointer transition-all"
                    :class="[
                      selectedResources.includes(resource.id) ? 'bg-blue-50 border-blue-200' : 'bg-white border-transparent hover:border-gray-200',
                      isInherited(resource.id, 'resource') ? 'ring-1 ring-blue-300 bg-blue-50/50' : ''
                    ]">
                    <input type="checkbox" v-model="selectedResources" :value="resource.id" class="mt-1 h-4 w-4 rounded text-blue-600 border-gray-300 focus:ring-blue-500" />
                    <div class="ml-3 min-w-0">
                      <p class="text-sm font-bold text-gray-800 truncate flex items-center gap-2">
                        {{ resource.name }}
                        <span v-if="resource.id === 'system.sql.execute'" class="text-[9px] bg-red-100 text-red-600 px-1 py-0.5 rounded font-black border border-red-200 uppercase shrink-0">ROOT 权限</span>
                        <span v-if="isInherited(resource.id, 'resource')" class="text-[9px] bg-blue-100 text-blue-600 px-1 py-0.5 rounded uppercase">角色继承</span>
                      </p>
                      <p class="text-[10px] text-gray-400 font-mono truncate">{{ resource.id }}</p>
                    </div>
                  </label>
                </div>
              </div>
            </div>

            <!-- UI Sub-Tab -->
            <div v-show="activePermissionSubTab === 'ui'" class="grid grid-cols-1 gap-4">
              <div v-for="menu in MENU_TREE" :key="menu.id" class="bg-gray-50 rounded-2xl border border-gray-100 overflow-hidden shadow-sm hover:shadow-md transition-shadow">
                <div class="px-5 py-3 bg-white border-b border-gray-100 flex items-center gap-3">
                  <input type="checkbox" :value="menu.id" v-model="selectedMenus" class="h-5 w-5 text-indigo-600 rounded-lg border-gray-300 focus:ring-indigo-500" />
                  <span class="text-sm font-black text-gray-800 flex items-center gap-2">
                    <span class="bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded text-[10px] font-normal border border-gray-200">菜单</span>
                    {{ menu.label }}
                    <span v-if="isInherited(menu.id, 'menu')" class="text-[9px] bg-indigo-100 text-indigo-600 px-1 py-0.5 rounded uppercase">角色继承</span>
                  </span>
                </div>
                <div v-if="menu.children.length > 0" class="p-4 grid grid-cols-2 gap-2">
                  <label v-for="child in menu.children" :key="child.id" 
                    class="flex items-center p-2 rounded-lg border cursor-pointer transition-all"
                    :class="[
                      selectedElements.includes(child.id) ? 'bg-indigo-50 border-indigo-100' : 'bg-white/50 border-transparent hover:border-gray-200',
                      isInherited(child.id, 'element') ? 'ring-1 ring-indigo-200 bg-indigo-50/30' : ''
                    ]">
                    <input type="checkbox" :value="child.id" v-model="selectedElements" class="h-4 w-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500" />
                    <span class="ml-3 text-xs font-medium text-gray-600 flex items-center gap-2">
                      <span class="bg-purple-50 text-purple-600 px-1 py-0.5 rounded text-[9px] border border-purple-100">功能</span>
                      {{ child.label }}
                      <span v-if="isInherited(child.id, 'element')" class="text-[8px] bg-indigo-100 text-indigo-500 px-1 py-0.2 rounded">继承</span>
                    </span>
                  </label>
                </div>
              </div>
            </div>

            <!-- Data Asset Sub-Tab -->
            <div v-show="activePermissionSubTab === 'data'" class="space-y-4">
              <div class="bg-orange-50 border border-orange-100 rounded-xl p-4 mb-4">
                <div class="space-y-1">
                  <p class="text-[10px] text-orange-700 font-bold flex items-center gap-2 uppercase tracking-wider">
                    <span class="bg-orange-600 text-white px-1 py-0.5 rounded text-[8px]">重要提示</span>
                    表级权限遵循：空 = 无权限，ALL = 所有权限。请务必显式配置。
                  </p>
                  <p class="text-[10px] text-orange-600 flex items-center gap-2 pl-[54px]">
                    ※ 数据源权限直接影响 SQL 实验室页面功能及 SQL 动态查询接口的访问授权。
                  </p>
                </div>
              </div>

              <div v-for="ds in allDataSources" :key="ds.source_name" class="bg-gray-50 rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
                <div class="px-5 py-3 bg-white border-b border-gray-100 flex items-center justify-between">
                  <div class="flex items-center gap-3">
                    <input type="checkbox" :value="`ds:${ds.source_name}`" v-model="selectedDataSources" class="h-5 w-5 text-orange-600 rounded-lg border-gray-300 focus:ring-orange-500" />
                    <span class="text-sm font-black text-gray-800 uppercase flex items-center gap-2">
                      {{ ds.source_name }}
                      <span v-if="isInherited(`ds:${ds.source_name}`, 'datasource')" class="text-[9px] bg-orange-100 text-orange-600 px-1 py-0.5 rounded uppercase">角色继承</span>
                    </span>
                    <span class="bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded text-[9px] font-bold border border-gray-200">{{ ds.source_type }}</span>
                  </div>
                  <button 
                    v-if="selectedDataSources.includes(`ds:${ds.source_name}`) || isInherited(`ds:${ds.source_name}`, 'datasource')"
                    @click="toggleDSExpand(ds.source_name)" 
                    class="text-[10px] font-bold text-orange-600 hover:underline flex items-center gap-1">
                    {{ expandedDS === ds.source_name ? '收起配置' : '配置表权限' }}
                  </button>
                </div>

                <div v-if="expandedDS === ds.source_name" class="p-5 bg-white border-t border-gray-50 space-y-4 animate-in slide-in-from-top-2 duration-200">
                  <div class="flex items-center justify-between mb-2">
                    <div class="flex gap-2">
                      <button 
                        @click="setDSAllTables(ds.source_name)"
                        :class="isDSAllTables(ds.source_name) ? 'bg-orange-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
                        class="px-3 py-1 rounded text-[10px] font-bold transition-all">
                        所有表 (ALL)
                      </button>
                      <span v-if="isInherited(`ds:${ds.source_name}:table:*`, 'data_table')" class="text-[10px] bg-orange-100 text-orange-600 px-2 py-1 rounded font-bold">已从角色继承 ALL</span>
                    </div>
                    <div class="relative w-48">
                      <input v-model="tableSearch" placeholder="搜索表名..." class="w-full text-[10px] border border-gray-200 rounded-lg px-2 py-1 outline-none focus:ring-1 focus:ring-orange-500" />
                    </div>
                  </div>

                  <div v-if="loadingTables" class="py-12 text-center">
                    <div class="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-orange-600"></div>
                  </div>
                  
                  <div v-else class="grid grid-cols-3 gap-2 max-h-60 overflow-y-auto custom-scrollbar p-1">
                    <label v-for="table in filteredTables" :key="typeof table === 'string' ? table : table.name" 
                      class="flex items-center p-2 rounded-lg border cursor-pointer transition-all"
                      :class="[
                        selectedDataTables.includes(`ds:${ds.source_name}:table:${typeof table === 'string' ? table : table.name}`) ? 'bg-orange-50 border-orange-200' : 'bg-white border-transparent hover:border-gray-100',
                        isInherited(`ds:${ds.source_name}:table:${typeof table === 'string' ? table : table.name}`, 'data_table') ? 'ring-1 ring-orange-200 bg-orange-50/30' : ''
                      ]">
                      <input type="checkbox" :value="`ds:${ds.source_name}:table:${typeof table === 'string' ? table : table.name}`" v-model="selectedDataTables" class="h-3 w-3 text-orange-600 rounded border-gray-300 focus:ring-orange-500" />
                      <div class="ml-2 flex flex-col min-w-0">
                        <span class="text-[10px] font-medium text-gray-600 truncate flex items-center gap-1">
                          {{ typeof table === 'string' ? table : table.name }}
                          <span v-if="isInherited(`ds:${ds.source_name}:table:${typeof table === 'string' ? table : table.name}`, 'data_table')" class="text-[8px] bg-orange-100 text-orange-500 px-1 py-0.2 rounded">继承</span>
                        </span>
                        <span v-if="typeof table !== 'string'" :class="table.type === 'VIEW' ? 'text-amber-500' : 'text-blue-500'" class="text-[8px] font-black uppercase">{{ table.type }}</span>
                      </div>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="px-8 py-6 bg-gray-50 border-t flex justify-end gap-3">
            <button @click="closeDialogs" class="px-6 py-2.5 text-gray-500 font-bold hover:text-gray-700 transition-colors">
              {{ createdApiKey ? '关闭窗口' : '放弃修改' }}
            </button>
            <button v-if="!createdApiKey" @click="saveUser" :disabled="submitting" class="px-8 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-lg transition-all disabled:opacity-50 flex items-center gap-2">
              <span v-if="submitting" class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
              {{ submitting ? '提交中...' : (showEditDialog ? '保存配置' : '确认创建') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Dialog -->
    <div v-if="showDeleteDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9990]" @click.self="showDeleteDialog = false">
      <div class="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 class="text-xl font-bold mb-4 text-red-600">确认删除</h2>
        <p class="text-gray-700 mb-6">确定要删除用户 <strong>{{ userToDelete?.user_name }}</strong> 吗？此操作不可恢复。</p>
        <div class="flex justify-end gap-3">
          <button @click="showDeleteDialog = false" class="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
            取消
          </button>
          <button @click="deleteUser" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">
            确认删除
          </button>
        </div>
      </div>
    </div>

    <!-- Regenerate API Key Dialog -->
    <div v-if="showRegenerateDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9990]" @click.self="showRegenerateDialog = false">
      <div class="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 class="text-xl font-bold mb-4 text-yellow-600">重置 API Key</h2>
        
        <div v-if="!regeneratedApiKey">
          <p class="text-gray-700 mb-4">确定要为用户 <strong>{{ userToRegenerate?.user_name }}</strong> 重新生成 API Key 吗？</p>
          <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-6">
            <p class="text-sm text-yellow-800">⚠️ 旧的 API Key 将立即失效，无法恢复！</p>
          </div>
          <div class="flex justify-end gap-3">
            <button @click="showRegenerateDialog = false" class="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
              取消
            </button>
            <button @click="executeRegenerateApiKey" class="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700">
              确认重置
            </button>
          </div>
        </div>

        <div v-else>
          <div class="bg-green-50 border-2 border-green-400 rounded-lg p-4 mb-4">
            <div class="flex items-start gap-2 mb-3">
              <svg class="w-6 h-6 text-green-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
              <div class="flex-1">
                <p class="text-sm font-bold text-green-800 mb-1">✅ API Key 重置成功！</p>
                <p class="text-xs text-green-700 mb-2">请立即复制保存新的 API Key。</p>
              </div>
            </div>
            <div class="bg-white rounded border-2 border-green-300 p-3">
              <p class="text-xs text-gray-600 mb-1 font-medium">用户: {{ userToRegenerate?.user_name }}</p>
              <p class="text-xs text-gray-600 mb-1 font-medium">新的 API Key:</p>
              <div class="flex items-center gap-2">
                <code class="flex-1 bg-gray-50 px-3 py-2 rounded border text-xs break-all font-mono select-all">{{ regeneratedApiKey }}</code>
                <button @click="copyRegeneratedApiKey" class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 whitespace-nowrap font-medium">
                  📋 复制
                </button>
              </div>
            </div>
          </div>
          <div class="flex justify-end">
            <button @click="closeRegenerateDialog" class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700">
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- View API Key Dialog -->
    <div v-if="showViewKeyDialog" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9990]" @click.self="closeViewKeyDialog">
      <div class="bg-white rounded-lg p-6 w-full max-w-lg">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-xl font-bold text-indigo-600">🔑 查看 API Key</h2>
          <button
            @click="closeViewKeyDialog"
            class="text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary rounded-md p-1"
          >
            <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        <div class="mb-4">
          <p class="text-sm text-gray-700 mb-2">用户：<strong class="text-gray-900">{{ userToViewKey?.user_name }}</strong></p>
        </div>

        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <p class="text-sm text-blue-800 mb-3">📝 API Key 支持重复查看和复制</p>
          
          <div v-if="loadingViewKey" class="flex items-center justify-center py-8">
            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            <p class="ml-3 text-gray-600">加载中...</p>
          </div>

          <div v-else-if="viewedApiKey" class="space-y-3">
            <div class="flex items-center gap-2">
              <input
                type="text"
                :value="viewedApiKey"
                readonly
                class="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-white text-sm font-mono"
              />
              <button
                @click="copyViewedApiKey"
                class="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                title="复制 API Key"
              >
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
            </div>
          </div>

          <div v-else class="text-center py-8">
            <p class="text-red-600">加载失败</p>
          </div>
        </div>

        <div class="flex justify-end">
          <button
            @click="closeViewKeyDialog"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { useToast } from '../composables/useToast'
import Switch from '../components/Switch.vue'
import { 
  KeyIcon, 
  ArrowPathIcon, 
  PencilSquareIcon, 
  TrashIcon
} from '@heroicons/vue/24/outline'
import { PERMISSION_MENU_TREE as MENU_TREE } from '@/constants/permissionMenuTree'

const { showToast } = useToast()
const route = useRoute()


const activePermissionSubTab = ref<'resource' | 'ui' | 'data'>('resource')

const openMore = ref<number | null>(null)
const toggleMore = (id: number, e: MouseEvent) => { e.stopPropagation(); openMore.value = openMore.value === id ? null : id }
const closeMore = () => { openMore.value = null }

// Constants
const availableResources = ref<any[]>([])


const groupedResources = computed(() => {
  const groups: Record<string, any[]> = {}
  availableResources.value.forEach((res: any) => {
    if (!groups[res.group]) {
      groups[res.group] = []
    }
    groups[res.group]!.push(res)
  })
  return groups
})

const isGroupAllSelected = (resources: any[]) => {
  return resources.every(r => selectedResources.value.includes(r.id))
}

const toggleGroupSelection = (resources: any[]) => {
  if (isGroupAllSelected(resources)) {
    // Unselect all in this group
    const idsToRemove = resources.map(r => r.id)
    selectedResources.value = selectedResources.value.filter(id => !idsToRemove.includes(id))
  } else {
    // Select all in this group (avoid duplicates)
    resources.forEach(r => {
      if (!selectedResources.value.includes(r.id)) {
        selectedResources.value.push(r.id)
      }
    })
  }
}

const fetchAvailableResources = async () => {
  try {
    const apiKey = localStorage.getItem('api_key')
    const response = await axios.get('/api/portal/meta/resources', {
      headers: { 'X-API-Key': apiKey }
    })
    availableResources.value = response.data.map((r: any) => ({
      id: r.resource_key,
      name: r.resource_name,
      group: r.resource_group || '其他'
    }))
  } catch (e) {
    console.error('Failed to fetch resources:', e)
  }
}

const fetchAvailableUiPermissions = async () => {

  try {
    const apiKey = localStorage.getItem('api_key')
    // Get all registered UI permissions from the backend
    // Since admins get everything, we can pull the full set from a meta endpoint 
    // or reusing the permissions endpoint if user is admin.
    const response = await axios.get('/api/portal/auth/permissions', {
      headers: { 'X-API-Key': apiKey }
    })
    
    // We assume the logged-in user is admin and can see all possible perms
    // Filter by type
    const all = response.data.permissions
    availableMenus.value = (all.menus || []).map((m: string) => ({ id: m, name: m.replace('menu:', '').toUpperCase() }))
    availableElements.value = (all.elements || []).map((e: string) => ({ id: e, name: e.replace('element:', '').split(':').pop()?.toUpperCase() || e }))
  } catch (e) {
    console.error('Failed to fetch UI permissions:', e)
  }
}


// State
const users = ref<any[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const size = ref(15)
const totalPages = ref(0)

// Filters
const searchQuery = ref('')
const roleFilter = ref('')
const statusFilter = ref('')

// Dialogs
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
const showRegenerateDialog = ref(false)
const showViewKeyDialog = ref(false)
const userToDelete = ref<any>(null)
const userToRegenerate = ref<any>(null)
const userToViewKey = ref<any>(null)
const loadingViewKey = ref(false)
const viewedApiKey = ref('')
const activeTab = ref<'basic' | 'permissions'>('basic')

// Permission State
const availableMenus = ref<any[]>([])
const availableElements = ref<any[]>([])
const availableRoles = ref<any[]>([])
const selectedMenus = ref<string[]>([])
const selectedElements = ref<string[]>([])
const selectedRoles = ref<number[]>([])
const selectedDataSources = ref<string[]>([])
const selectedDataTables = ref<string[]>([])

// Data Asset State
const allDataSources = ref<any[]>([])
const expandedDS = ref<string | null>(null)
const currentTables = ref<any[]>([])
const loadingTables = ref(false)
const tableSearch = ref('')

const filteredTables = computed(() => {
  if (!tableSearch.value) return currentTables.value
  return currentTables.value.filter(t => (typeof t === 'string' ? t : t.name).toLowerCase().includes(tableSearch.value.toLowerCase()))
})

// Inherited State (ReadOnly)
const inheritedMenus = ref<string[]>([])
const inheritedElements = ref<string[]>([])
const inheritedResources = ref<string[]>([])
const inheritedDataSources = ref<string[]>([])
const inheritedDataTables = ref<string[]>([])

const isInherited = (id: string, type: 'menu' | 'element' | 'resource' | 'datasource' | 'data_table') => {
  if (type === 'menu') return inheritedMenus.value.includes(id)
  if (type === 'element') return inheritedElements.value.includes(id)
  if (type === 'resource') return inheritedResources.value.includes(id)
  if (type === 'datasource') return inheritedDataSources.value.includes(id)
  if (type === 'data_table') return inheritedDataTables.value.includes(id)
  return false
}

const toggleDSExpand = async (dsName: string) => {
  if (expandedDS.value === dsName) {
    expandedDS.value = null
    return
  }
  
  expandedDS.value = dsName
  loadingTables.value = true
  tableSearch.value = ''
  try {
    const res = await axios.post('/api/portal/meta/datasource/tables', { data_source: dsName })
    currentTables.value = res.data.tables || []
  } catch (e) {
    showToast('获取表列表失败', 'error')
    currentTables.value = []
  } finally {
    loadingTables.value = false
  }
}

const isDSAllTables = (dsName: string) => selectedDataTables.value.includes(`ds:${dsName}:table:*`)

const setDSAllTables = (dsName: string) => {
  const allKey = `ds:${dsName}:table:*`
  if (isDSAllTables(dsName)) {
    selectedDataTables.value = selectedDataTables.value.filter(k => k !== allKey)
  } else {
    selectedDataTables.value = selectedDataTables.value.filter(k => !k.startsWith(`ds:${dsName}:table:`))
    selectedDataTables.value.push(allKey)
  }
}

const fetchAllDataSources = async () => {
  try {
    const res = await axios.get('/api/portal/datasource/datasources')
    allDataSources.value = res.data
  } catch (e) { console.error(e) }
}

// Watch for data source deselection to auto-remove tables
watch(selectedDataSources, (newVal, oldVal) => {
  if (!oldVal) return
  const removedDS = oldVal.filter(ds => !newVal.includes(ds))
  if (removedDS.length > 0) {
    removedDS.forEach(dsCode => {
      // dsCode is "ds:name"
      // Remove all tables starting with "ds:name:table:"
      selectedDataTables.value = selectedDataTables.value.filter(t => !t.startsWith(`${dsCode}:table:`))
      
      // Close expanded panel if it was the removed one
      const dsName = dsCode.replace('ds:', '')
      if (expandedDS.value === dsName) expandedDS.value = null
    })
  }
})


// Watch for menu deselection to auto-remove children elements
watch(selectedMenus, (newVal, oldVal) => {
  // If oldVal is undefined (first run), skip
  if (!oldVal) return
  
  const removedMenus = oldVal.filter(m => !newVal.includes(m))
  if (removedMenus.length > 0) {
    removedMenus.forEach(menuId => {
      const menuNode = MENU_TREE.find(m => m.id === menuId)
      if (menuNode && menuNode.children) {
        const childIds = menuNode.children.map(c => c.id)
        // Remove these childIds from selectedElements
        selectedElements.value = selectedElements.value.filter(eid => !childIds.includes(eid))
      }
    })
  }
})

// Form
const formData = ref({
  user_name: '',
  role: 'user',
  remark: '',
  rate_limit: null as number | null,
  masking_strategy: 'ROLE'
})
const selectedResources = ref<string[]>([])
const editingUserId = ref<number | null>(null)
const submitting = ref(false)
const error = ref('')
const createdApiKey = ref('')
const regeneratedApiKey = ref('')

// Fetch users
const fetchUsers = async () => {
  loading.value = true
  try {
    const apiKey = localStorage.getItem('api_key')
    const params: any = {
      page: page.value,
      size: size.value
    }
    
    if (searchQuery.value) params.search = searchQuery.value
    if (roleFilter.value) params.role = roleFilter.value
    if (statusFilter.value) params.status = statusFilter.value
    
    const response = await axios.get('/api/portal/management/users', {
      headers: { 'X-API-Key': apiKey },
      params
    })
    
    users.value = response.data.items
    total.value = response.data.total
    totalPages.value = Math.ceil(total.value / size.value)
  } catch (e: any) {
    console.error('Failed to fetch users:', e)
    showToast('获取用户列表失败：' + (e.response?.data?.message || e.message), 'error')
  } finally {
    loading.value = false
  }
}

// Debounced search
let searchTimeout: any = null
const debouncedSearch = () => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    page.value = 1
    fetchUsers()
  }, 500)
}

// Reset filters
const resetFilters = () => {
  searchQuery.value = ''
  roleFilter.value = ''
  statusFilter.value = ''
  page.value = 1
  fetchUsers()
}

// Edit user
const editUser = async (user: any) => {
  editingUserId.value = user.id
  formData.value = {
    user_name: user.user_name,
    role: user.role,
    remark: user.remark || '',
    rate_limit: user.rate_limit,
    masking_strategy: user.masking_strategy || 'ROLE'
  }
  
  // 1. Existing Resource Permissions
  selectedResources.value = user.allowed_resources || []
  selectedRoles.value = user.role_ids || []

    // 2. Fetch UI Permissions for this specific user

    try {

      const apiKey = localStorage.getItem('api_key')

      const res = await axios.get(`/api/portal/management/users/${user.id}/permissions`, {

          headers: { 'X-API-Key': apiKey }

      })

      

      // Direct perms (what we can save)
      selectedMenus.value = res.data.direct.menus || []
      selectedElements.value = res.data.direct.elements || []
      selectedDataSources.value = res.data.direct.datasources || []
      selectedDataTables.value = res.data.direct.data_tables || []
      
      // Aggregated perms (for visual indicators)
      inheritedMenus.value = (res.data.aggregated.menus || []).filter((m: string) => !selectedMenus.value.includes(m))
      inheritedElements.value = (res.data.aggregated.elements || []).filter((e: string) => !selectedElements.value.includes(e))
      inheritedResources.value = (res.data.aggregated.resources || []).filter((r: string) => !selectedResources.value.includes(r))
      inheritedDataSources.value = (res.data.aggregated.datasources || []).filter((d: string) => !selectedDataSources.value.includes(d))
      inheritedDataTables.value = (res.data.aggregated.data_tables || []).filter((t: string) => !selectedDataTables.value.includes(t))
  
    } catch (e) {
      console.error('Failed to fetch user UI perms:', e)
      selectedMenus.value = []
      selectedElements.value = []
      selectedDataSources.value = []
      selectedDataTables.value = []
    }

  showEditDialog.value = true
  createdApiKey.value = ''
  error.value = ''
}


// Save user (create or update)
const saveUser = async () => {
  if (!formData.value.user_name) {
    error.value = '请输入用户名'
    return
  }
  
  submitting.value = true
  error.value = ''
  
  // Construct permissions
  const allowed_resources = formData.value.role === 'user' ? selectedResources.value : []
  
  // 统一处理 UI 权限：根据 ID 前缀自动归类到菜单或功能，确保勾选状态真实持久化
  const allUiIds = [...selectedMenus.value, ...selectedElements.value]
  const finalMenus = Array.from(new Set(allUiIds.filter(id => id.startsWith('menu:'))))
  const finalElements = Array.from(new Set(allUiIds.filter(id => id.startsWith('element:'))))

  try {
    const apiKey = localStorage.getItem('api_key')
    
    if (showEditDialog.value && editingUserId.value) {
      await axios.put(
        `/api/portal/management/users/${editingUserId.value}`,
        { 
          role: formData.value.role,
          remark: formData.value.remark,
          allowed_resources: allowed_resources,
          role_ids: selectedRoles.value,
          menus: finalMenus,
          elements: finalElements, 
          datasources: selectedDataSources.value,
          data_tables: selectedDataTables.value,
          rate_limit: formData.value.rate_limit,
          masking_strategy: formData.value.masking_strategy
        },
        { headers: { 'X-API-Key': apiKey } }
      )


      showToast('用户更新成功', 'success')
      closeDialogs()
      fetchUsers()
    } else {
      const response = await axios.post(
        '/api/portal/management/users',
        {
          ...formData.value,
          allowed_resources: allowed_resources,
          datasources: selectedDataSources.value,
          data_tables: selectedDataTables.value
        },
        { headers: { 'X-API-Key': apiKey } }
      )
      createdApiKey.value = response.data.api_key
      fetchUsers()
    }
  } catch (e: any) {
    console.error('Failed to save user:', e)
    error.value = e.response?.data?.message || '操作失败'
  } finally {
    submitting.value = false
  }
}

// Toggle user status
const toggleStatus = async (user: any) => {
  const newStatus = user.status === 1 ? 0 : 1
  const action = newStatus === 0 ? '禁用' : '启用'
  
  try {
    const apiKey = localStorage.getItem('api_key')
    await axios.patch(
      `/api/portal/management/users/${user.id}/status`,
      { status: newStatus },
      { headers: { 'X-API-Key': apiKey } }
    )
    showToast(`${user.user_name} 已${action}`, 'success')
    fetchUsers()
  } catch (e: any) {
    console.error('Failed to toggle status:', e)
    showToast(e.response?.data?.message || `${action}失败`, 'error')
  }
}

// Confirm delete
const confirmDelete = (user: any) => {
  userToDelete.value = user
  showDeleteDialog.value = true
}

// Delete user
const deleteUser = async () => {
  if (!userToDelete.value) return
  
  try {
    const apiKey = localStorage.getItem('api_key')
    await axios.delete(
      `/api/portal/management/users/${userToDelete.value.id}`,
      { headers: { 'X-API-Key': apiKey } }
    )
    showToast('删除成功', 'success')
    showDeleteDialog.value = false
    userToDelete.value = null
    fetchUsers()
  } catch (e: any) {
    console.error('Failed to delete user:', e)
    showToast(e.response?.data?.message || '删除失败', 'error')
  }
}

// Regenerate API Key
const regenerateApiKey = (user: any) => {
  userToRegenerate.value = user
  regeneratedApiKey.value = ''
  showRegenerateDialog.value = true
}

// Execute regenerate API Key
const executeRegenerateApiKey = async () => {
  if (!userToRegenerate.value) return
  
  try {
    const apiKey = localStorage.getItem('api_key')
    const response = await axios.post(
      `/api/portal/management/users/${userToRegenerate.value.id}/reset-key`,
      {},
      { headers: { 'X-API-Key': apiKey } }
    )
    
    regeneratedApiKey.value = response.data.api_key
    fetchUsers()
  } catch (e: any) {
    console.error('Failed to regenerate API key:', e)
    showToast(e.response?.data?.message || '重置 API Key 失败', 'error')
  }
}

// Copy API key to clipboard
const copyApiKey = async () => {
  try {
    await navigator.clipboard.writeText(createdApiKey.value)
    showToast('API Key 已复制到剪贴板！', 'success')
  } catch (e) {
    const textArea = document.createElement('textarea')
    textArea.value = createdApiKey.value
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    showToast('API Key 已复制到剪贴板！', 'success')
  }
}

// Copy regenerated API key
const copyRegeneratedApiKey = async () => {
  try {
    await navigator.clipboard.writeText(regeneratedApiKey.value)
    showToast('新的 API Key 已复制到剪贴板！', 'success')
  } catch (e) {
    const textArea = document.createElement('textarea')
    textArea.value = regeneratedApiKey.value
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    showToast('新的 API Key 已复制到剪贴板！', 'success')
  }
}

// Close regenerate dialog
const closeRegenerateDialog = () => {
  showRegenerateDialog.value = false
  userToRegenerate.value = null
  regeneratedApiKey.value = ''
}

// View API Key
const viewApiKey = async (user: any) => {
  userToViewKey.value = user
  viewedApiKey.value = ''
  showViewKeyDialog.value = true
  
  // Load API Key immediately
  loadingViewKey.value = true
  try {
    const apiKey = localStorage.getItem('api_key')
    const response = await axios.get(
      `/api/portal/management/api-key/${user.id}`,
      { headers: { 'X-API-Key': apiKey } }
    )
    viewedApiKey.value = response.data.api_key
  } catch (e: any) {
    console.error('Failed to fetch API key:', e)
    showToast(e.response?.data?.detail || '获取 API Key 失败', 'error')
    viewedApiKey.value = ''
  } finally {
    loadingViewKey.value = false
  }
}

// Copy viewed API key
const copyViewedApiKey = async () => {
  try {
    await navigator.clipboard.writeText(viewedApiKey.value)
    showToast('API Key 已复制到剪贴板！', 'success')
  } catch (e) {
    const textArea = document.createElement('textarea')
    textArea.value = viewedApiKey.value
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    showToast('API Key 已复制到剪贴板！', 'success')
  }
}

// Close view key dialog
const closeViewKeyDialog = () => {
  showViewKeyDialog.value = false
  userToViewKey.value = null
  viewedApiKey.value = ''
  loadingViewKey.value = false
}

const fetchAvailableRoles = async () => {
  try {
    const apiKey = localStorage.getItem('api_key')
    const response = await axios.get('/api/portal/management/roles', {
      headers: { 'X-API-Key': apiKey }
    })
    availableRoles.value = response.data
  } catch (e) {
    console.error('Failed to fetch roles:', e)
  }
}

// Close dialogs
const closeDialogs = () => {
    showCreateDialog.value = false
    showEditDialog.value = false
    activeTab.value = 'basic'
    activePermissionSubTab.value = 'resource'
    formData.value = {
        user_name: '',
        role: 'user',
        remark: '',
        rate_limit: null,
        masking_strategy: 'ROLE'
    }
    selectedResources.value = []
    selectedMenus.value = []
    selectedElements.value = []
    selectedRoles.value = []
    selectedDataSources.value = []
    selectedDataTables.value = []
    createdApiKey.value = ''
    error.value = ''
    editingUserId.value = null
}


// Format date
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  // Fix Safari compatibility & Timezone
  let dateInput = typeof dateStr === 'string' ? dateStr.replace(' ', 'T') : dateStr;
  
  return new Date(dateInput).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// Load users on mount
onMounted(async () => {
  await fetchUsers()
  fetchAvailableResources()
  fetchAvailableUiPermissions()
  fetchAvailableRoles()
  fetchAllDataSources()

  const uid = route.query.user_id
  if (uid) {
    try {
      const apiKey = localStorage.getItem('api_key')
      const response = await axios.get('/api/portal/management/users', {
        headers: { 'X-API-Key': apiKey },
        params: { page: 1, size: 1000 },
      })
      const target = response.data.items?.find((u: any) => String(u.id) === String(uid))
      if (target) await editUser(target)
    } catch {
      /* ignore */
    }
  }
  document.addEventListener('click', closeMore)
})

onUnmounted(() => {
  document.removeEventListener('click', closeMore)
})


</script>

<style scoped>
.custom-tooltip {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.custom-tooltip::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: 150%;
  left: 50%;
  transform: translateX(-50%);
  background-color: rgba(31, 41, 55, 0.95);
  color: white;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  width: max-content;
  max-width: 300px;
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 9999;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  pointer-events: none;
  font-weight: normal;
}

.custom-tooltip::before {
  content: '';
  position: absolute;
  bottom: 120%;
  left: 50%;
  transform: translateX(-50%);
  border-width: 6px;
  border-style: solid;
  border-color: rgba(31, 41, 55, 0.95) transparent transparent transparent;
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 9999;
}

.custom-tooltip:hover::after {
  opacity: 1;
  visibility: visible;
  bottom: 160%;
}

.custom-tooltip:hover::before {
  opacity: 1;
  visibility: visible;
  bottom: 130%;
}
</style>