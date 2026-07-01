<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { computed, ref, onMounted, watch, provide } from 'vue'
import axios from '../utils/axios'
import Toast from '../components/Toast.vue'
import MyPermissionsModal from '../components/MyPermissionsModal.vue'
import { useMobileLayout } from '../composables/useMobileLayout'

const router = useRouter()
const route = useRoute()
const appVersion = import.meta.env.VITE_APP_VERSION || 'Dev Build'
const repoUrl = 'https://github.com/RandyChen1985/yunshu-api-data-platform'
const isCollapsed = ref(false)
const { isMobile, showMobileSidebar, toggleMobileSidebar, closeMobileSidebar } = useMobileLayout()
const showLogoutDialog = ref(false)
const showUserInfoDialog = ref(false)
const userApiKey = ref('')
const loadingApiKey = ref(false)
const onlineUserCount = ref(0)
const onlineUsers = ref<any[]>([])
const showOnlineUsersDialog = ref(false)
const showPermissionsModal = ref(false)
const myResources = ref<any[]>([])
const loadingMyResources = ref(false)
const userPermissions = ref<any>({})
const catalogBadge = ref({ count: 0, show_requests_menu: false, can_access_requests: false, owned_products: 0 })

const fetchCatalogBadge = async () => {
  try {
    const res = await axios.get('/api/portal/catalog/access-requests/pending-count')
    catalogBadge.value = res.data
    sessionStorage.setItem('catalog_can_access_requests', res.data.can_access_requests ? '1' : '0')
    sessionStorage.setItem('catalog_owned_products', String(res.data.owned_products || 0))
  } catch {
    catalogBadge.value = { count: 0, show_requests_menu: false, can_access_requests: false, owned_products: 0 }
    sessionStorage.setItem('catalog_can_access_requests', '0')
    sessionStorage.setItem('catalog_owned_products', '0')
  }
}

provide('refreshCatalogBadge', fetchCatalogBadge)

// Change Password State
const loadingPassword = ref(false)
const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const submitChangePassword = async () => {
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    showToast('两次输入的密码不一致', 'warning')
    return
  }
  
  loadingPassword.value = true
  try {
    await axios.post('/api/portal/auth/change-password', {
      old_password: passwordForm.value.oldPassword,
      new_password: passwordForm.value.newPassword
    })
    
    showToast('密码修改成功', 'success')
    // Reset form after success
    passwordForm.value.oldPassword = ''
    passwordForm.value.newPassword = ''
    passwordForm.value.confirmPassword = ''
  } catch (e: any) {
    console.error(e)
    const msg = e.response?.data?.detail || '密码修改失败'
    showToast(msg, 'error')
  } finally {
    loadingPassword.value = false
  }
}


const openPermissionsModal = () => {
    showPermissionsModal.value = true
}

const fetchMyResources = async () => {
    loadingMyResources.value = true
    try {
        const response = await axios.get('/api/portal/dashboard/my-resources')
        if (response.data) {
            myResources.value = response.data
        }
    } catch (e) {
        console.error("Failed to fetch my resources", e)
    } finally {
        loadingMyResources.value = false
    }
}

// Toast State
const toast = ref({
  show: false,
  message: '',
  type: 'info' as 'success' | 'error' | 'warning' | 'info',
  key: 0
})

const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
  toast.value = {
    show: true,
    message,
    type,
    key: toast.value.key + 1
  }
}

const closeToast = () => {
  toast.value.show = false
}

const userInfo = ref({
    id: 0,
    user_name: '',
    role: '',
    permissions: {
        menus: [] as string[],
        elements: [] as string[],
        resources: [] as string[]
    },
    created_at: '',
    remark: '',
    masking_strategy: '',
    user_rate_limit: null as number | null,
    role_rate_limit: null as number | null
})

const fetchUserInfo = async () => {

    try {

        const apiKey = localStorage.getItem('api_key')

        if (!apiKey) {

            router.push('/login')

            return

        }

        

        // 1. Get Basic Info

        const response = await axios.get('/api/portal/auth/me')

        if (response.data && response.data.status === 'success') {

            const basicInfo = response.data.data

            

            // 2. Get Permissions (Force Sync)

            const permRes = await axios.get('/api/portal/auth/permissions')

            const fullInfo = {

                ...basicInfo,

                permissions: permRes.data.permissions

            }

            

            // Log for debug

            console.log("DEBUG: Final Merged Permissions", fullInfo.permissions)

            

            // IMPORTANT: Set to localStorage BEFORE updating reactive ref

            localStorage.setItem('user_info', JSON.stringify(fullInfo))

            userInfo.value = fullInfo
            userPermissions.value = fullInfo.permissions

        }

    } catch (e) {


        console.error("Auth check failed", e)
        localStorage.removeItem('api_key')
        localStorage.removeItem('user_info')
        userInfo.value = { id: 0, user_name: '', role: '', permissions: { menus: [], elements: [], resources: [] }, created_at: '', remark: '', masking_strategy: '', user_rate_limit: null, role_rate_limit: null }
        router.push('/login')
    }
}


onMounted(() => {
    fetchUserInfo()
    fetchOnlineUsers()
    fetchMyResources()
    fetchCatalogBadge()
})

watch(() => route.path, () => {
  fetchCatalogBadge()
  if (isMobile.value) {
    closeMobileSidebar()
  }
})

const openOnlineUsers = () => {
    if (userInfo.value.role === 'admin') {
        fetchOnlineUsers() // Refresh data when opening
        showOnlineUsersDialog.value = true
    }
}

const fetchOnlineUsers = async () => {
    try {
        const response = await axios.get('/api/portal/dashboard/online-users')
        if (response.data) {
            onlineUserCount.value = response.data.count
            onlineUsers.value = response.data.users || []
        }
    } catch (e) {
        console.error("Failed to fetch online users", e)
    }
}

const logout = () => {
  showLogoutDialog.value = true
}

const confirmLogout = async () => {
  try {
    await axios.post('/api/portal/auth/logout')
  } catch (e) {
    console.error('Logout API failed', e)
  } finally {
    // 彻底清理
    localStorage.removeItem('api_key')
    localStorage.removeItem('user_info')
    localStorage.removeItem('sql_lab_tabs') // 也清理一下实验室标签
    showLogoutDialog.value = false
    router.push('/login')
  }
}


const cancelLogout = () => {
  showLogoutDialog.value = false
}

const openUserInfo = async () => {
  if (isMobile.value) {
    closeMobileSidebar()
    router.push('/dashboard/personal')
    return
  }
  showUserInfoDialog.value = true
  if (!userApiKey.value && userInfo.value.id) {
    await fetchApiKey()
  }
}

const closeUserInfo = () => {
  showUserInfoDialog.value = false
}

const fetchApiKey = async () => {
  if (!userInfo.value.id) return
  
  loadingApiKey.value = true
  try {
    const response = await axios.get(`/api/portal/management/api-key/${userInfo.value.id}`)
    userApiKey.value = response.data.api_key
  } catch (error: any) {
    console.error('Failed to fetch API key:', error)
    showToast(error.response?.data?.detail || '获取 API Key 失败', 'error')
  } finally {
    loadingApiKey.value = false
  }
}

const copyApiKey = async () => {
  if (!userApiKey.value) {
    showToast('API Key 未加载', 'warning')
    return
  }
  
  try {
    await navigator.clipboard.writeText(userApiKey.value)
    showToast('API Key 已复制到剪贴板', 'success')
  } catch (err) {
    console.error('Failed to copy:', err)
    showToast('复制失败，请手动复制', 'error')
  }
}

const handleEscape = (e: KeyboardEvent) => {
  if (e.key === 'Escape') {
    if (showUserInfoDialog.value) {
      closeUserInfo()
    } else if (showLogoutDialog.value) {
      cancelLogout()
    }
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleEscape)
})

// Cleanup on unmount
import { onUnmounted } from 'vue'
onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
})

const breadcrumbs = computed(() => {
  const matched = route.matched;
  return matched.map(m => m.name).filter(Boolean);
})

const toggleSidebar = () => {
  if (isMobile.value) {
    toggleMobileSidebar()
    return
  }
  isCollapsed.value = !isCollapsed.value
}

// --- 菜单重构逻辑开始 ---

// 权限辅助函数 (复用原有的 hasMenu)
const hasMenuPerm = (perm: string) => {
  if (!perm) return true; // 如果没有定义权限，默认显示
  if (userInfo.value.role === 'admin') return true;
  return userInfo.value.permissions?.menus?.includes(perm);
};

interface MenuItem {
  name: string;
  to: string;
  icon: string;
  perm: string;
  activeNames?: string[];
  badge?: number;
  desktopOnly?: boolean;
  mobileOnly?: boolean;
  mobileVisible?: boolean;
}

interface MenuGroup {
  title: string;
  items: MenuItem[];
}

// 菜单组定义
const menuGroups: MenuGroup[] = [
  {
    title: '',
    items: [
      { name: '概览', to: '/dashboard/overview', icon: 'dashboard', perm: 'menu:overview', activeNames: ['Overview'] }
    ]
  },
  {
    title: '数据服务',
    items: [
      { name: '产品目录', to: '/dashboard/catalog', icon: 'catalog', perm: '', mobileVisible: true, activeNames: ['Catalog', 'CatalogDetail', 'CatalogProductEdit'] },
      { name: '我的申请', to: '/dashboard/catalog-my-applications', icon: 'catalog', perm: '', mobileVisible: true, activeNames: ['CatalogMyApplications'] },
      { name: '资产全景', to: '/dashboard/asset-panorama', icon: 'panorama', perm: 'menu:asset-panorama', desktopOnly: true, activeNames: ['AssetPanorama'] },
      { name: '权限审批', to: '/dashboard/catalog-requests', icon: 'catalog', perm: 'menu:catalog:requests', mobileVisible: true, activeNames: ['CatalogAccessRequests'] }
    ]
  },
  {
    title: '数据开发',
    items: [
      { name: '接口管理', to: '/dashboard/resources', icon: 'resources', perm: 'menu:resources', desktopOnly: true },
      { name: 'SQL 实验室', to: '/dashboard/lab', icon: 'lab', perm: 'menu:lab', activeNames: ['SQLLab'], desktopOnly: true },
      { name: '元数据中心', to: '/dashboard/metadata', icon: 'metadata', perm: 'menu:metadata', desktopOnly: true },
      { name: '数据源管理', to: '/dashboard/datasources', icon: 'datasource', perm: 'menu:datasource', activeNames: ['DataSourceList', 'DataSourceEdit', 'DataSourceNew'], desktopOnly: true },
      { name: '审计日志', to: '/dashboard/audit', icon: 'audit', perm: 'menu:audit', activeNames: ['Audit'], desktopOnly: true }
    ]
  },
  {
    title: '调试中心',
    items: [
      { name: 'API 调试', to: '/dashboard/playground', icon: 'playground', perm: 'menu:playground', activeNames: ['Playground'], desktopOnly: true },
      { name: '开发者中心', to: '/dashboard/developer', icon: 'developer', perm: '', activeNames: ['DeveloperPortal'], desktopOnly: true }
    ]
  },
  {
    title: '系统管理',
    items: [
      { name: '用户管理', to: '/dashboard/users', icon: 'users', perm: 'menu:users', activeNames: ['Users'] },
      { name: '角色管理', to: '/dashboard/roles', icon: 'roles', perm: 'menu:system:roles', activeNames: ['Roles'] },
      { name: '系统设置', to: '/dashboard/settings', icon: 'config', perm: 'menu:config', activeNames: ['SystemSettings'] }
    ]
  },
  {
    title: '',
    items: [
      { name: '个人中心', to: '/dashboard/personal', icon: 'personal', perm: '', activeNames: ['PersonalCenter'], mobileOnly: true }
    ]
  }
];

const isItemActive = (item: MenuItem) => {
  if (route.path === item.to) return true;
  if (item.activeNames && item.activeNames.includes(route.name as string)) return true;
  // 特殊处理元数据中心这种前缀匹配的
  if (item.to === '/dashboard/metadata' && route.path.startsWith('/dashboard/metadata')) return true;
  if (item.to === '/dashboard/resources' && route.path.startsWith('/dashboard/resources')) return true;
  if (item.to === '/dashboard/catalog') {
    return route.path === '/dashboard/catalog' || /^\/dashboard\/catalog\/[^/]+/.test(route.path)
  }
  return false;
};

const currentPageTitle = computed(() => {
  for (const group of menuGroups) {
    for (const item of group.items) {
      if (isItemActive(item)) return item.name
    }
  }
  if (route.name === 'PersonalCenter') return '个人中心'
  return '云枢数据'
})

const collapsedMenuGroups = ref<Record<string, boolean>>({});

const isGroupActive = (group: MenuGroup) => {
  return group.items.some(item => isItemActive(item));
};

const isGroupCollapsed = (group: MenuGroup) => {
  if (!group.title) return false;
  if (isGroupActive(group)) return false;
  return Boolean(collapsedMenuGroups.value[group.title]);
};

const toggleMenuGroup = (group: MenuGroup) => {
  if (!group.title || isCollapsed.value) return;
  collapsedMenuGroups.value[group.title] = !collapsedMenuGroups.value[group.title];
};

const filteredMenuGroups = computed(() => {
  return menuGroups.map(group => ({
    ...group,
    items: group.items
      .filter(item => {
        if (item.to === '/dashboard/catalog-requests') {
          return catalogBadge.value.can_access_requests
        }
        if (isMobile.value && item.mobileVisible) {
          return true
        }
        if (!hasMenuPerm(item.perm)) return false
        if (item.desktopOnly && isMobile.value) return false
        if (item.mobileOnly && !isMobile.value) return false
        return true
      })
      .map(item => ({
        ...item,
        badge: item.to === '/dashboard/catalog-requests' ? catalogBadge.value.count : undefined,
      }))
  })).filter(group => group.items.length > 0);
});

// --- 菜单重构逻辑结束 ---
</script>

<template>
  <div class="h-screen bg-gray-50 flex overflow-hidden relative">
    <!-- Mobile Overlay -->
    <div
      v-if="isMobile && showMobileSidebar"
      class="fixed inset-0 bg-black/50 z-20 transition-opacity backdrop-blur-sm"
      @click="closeMobileSidebar"
    />

    <!-- Sidebar -->
    <aside 
       class="bg-sidebar text-white shadow-xl flex flex-col z-30 transition-all duration-300 ease-in-out flex-shrink-0"
       :class="[
         isMobile ? 'fixed inset-y-0 left-0 h-full' : 'relative',
         isMobile
           ? (showMobileSidebar ? 'translate-x-0 w-[220px]' : '-translate-x-full w-[220px]')
           : (isCollapsed ? 'w-20' : 'w-[220px]'),
       ]"
    >
      <!-- Brand Header -->
      <div 
         class="h-16 flex items-center bg-sidebar border-b border-gray-700 overflow-hidden whitespace-nowrap"
         :class="isCollapsed && !isMobile ? 'justify-center px-0' : 'px-4'"
      >
        <router-link
          to="/dashboard/catalog"
          class="flex-shrink-0 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
          title="产品目录"
          @click="isMobile ? closeMobileSidebar() : null"
        >
          <img src="/favicon.png?v=20260629-2" class="w-8 h-8 rounded-lg" alt="Logo" />
        </router-link>
        <transition name="fade">
          <div v-if="!isCollapsed || isMobile" class="ml-2.5 flex flex-col justify-center -translate-y-0.5">
            <router-link
              to="/dashboard/catalog"
              class="text-[15px] font-bold tracking-wide leading-tight hover:text-white/90 transition-colors focus:outline-none focus-visible:underline"
              title="产品目录"
              @click="isMobile ? closeMobileSidebar() : null"
            >
              云枢 · 数据服务平台
            </router-link>
            <component
              :is="repoUrl ? 'a' : 'span'"
              :href="repoUrl || undefined"
              :target="repoUrl ? '_blank' : undefined"
              :rel="repoUrl ? 'noopener noreferrer' : undefined"
              class="group flex items-center text-[10px] text-gray-500 font-medium tracking-wider leading-none mt-0.5 transition-colors"
              :class="repoUrl ? 'hover:text-white' : ''"
              :title="repoUrl ? 'View on GitHub' : undefined"
            >
              <svg class="w-3 h-3 mr-1 opacity-80 group-hover:opacity-100 transition-opacity" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path fill-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clip-rule="evenodd" />
              </svg>
              <span>v{{ appVersion }}</span>
            </component>
          </div>
        </transition>
      </div>

      <!-- Navigation (Scrollable internally) -->
      <nav
        class="flex-1 py-4 space-y-4 overflow-y-auto overflow-x-hidden custom-scrollbar"
        @click="isMobile ? closeMobileSidebar() : null"
      >
        <div v-for="group in filteredMenuGroups" :key="group.title" class="space-y-1">
          <!-- Group Title (Hierarchy Name) -->
          <button 
            v-if="(!isCollapsed || isMobile) && group.title" 
            type="button"
            class="py-2 flex items-center justify-between gap-2 text-left text-[10px] font-black text-gray-500 uppercase tracking-[0.15em] select-none hover:text-gray-300 transition-colors"
            :class="isCollapsed ? 'w-full justify-center px-0 mx-0' : 'w-[calc(100%-1.5rem)] mx-3 px-3'"
            :aria-expanded="!isGroupCollapsed(group)"
            @click.stop="toggleMenuGroup(group)"
          >
            <span class="truncate">{{ group.title }}</span>
            <svg 
              class="w-3 h-3 flex-shrink-0 transition-transform duration-200"
              :class="isGroupCollapsed(group) ? '-rotate-90' : 'rotate-0'"
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <div v-else-if="isCollapsed && group.title" class="h-px bg-gray-700/50 mx-4 my-2"></div>

          <!-- Group Items -->
          <transition name="menu-group">
            <div v-show="!isGroupCollapsed(group)" class="space-y-1">
              <router-link
                v-for="item in group.items"
                :key="item.to"
                :to="item.to"
                class="group flex items-center py-2 text-sm font-medium transition-all duration-200 whitespace-nowrap"
                :class="[
                  isItemActive(item)
                    ? 'bg-primary text-white shadow-md'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white',
                  isCollapsed && !isMobile ? 'justify-center px-0 mx-0 rounded-none' : 'px-4 mx-3 rounded-xl',
                ]"
                @click="isMobile ? closeMobileSidebar() : null"
              >
            <!-- Icons (保持原有 SVG) -->
            <svg v-if="item.icon === 'dashboard'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
            <svg v-else-if="item.icon === 'audit'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
            <svg v-else-if="item.icon === 'playground'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
            <svg v-else-if="item.icon === 'developer'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
            <svg v-else-if="item.icon === 'resources'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
            <svg v-else-if="item.icon === 'lab'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
            <svg v-else-if="item.icon === 'metadata' || item.icon === 'datasource'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>
            <svg v-else-if="item.icon === 'users'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
            <svg v-else-if="item.icon === 'roles'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
            <svg v-else-if="item.icon === 'catalog'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
            <svg v-else-if="item.icon === 'panorama'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" /></svg>
            <svg v-else-if="item.icon === 'config'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
            <svg v-else-if="item.icon === 'personal'" class="flex-shrink-0 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>

                <transition name="fade">
                  <span v-if="!isCollapsed || isMobile" class="ml-3 flex-1 flex items-center justify-between gap-2 min-w-0">
                    <span class="truncate">{{ item.name }}</span>
                    <span
                      v-if="item.badge && item.badge > 0"
                      class="flex-shrink-0 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center"
                    >
                      {{ item.badge > 99 ? '99+' : item.badge }}
                    </span>
                  </span>
                </transition>
              </router-link>
            </div>
          </transition>
        </div>
      </nav>

      <!-- User Profile (Clickable) -->
      <button 
         @click="openUserInfo"
         class="py-4 bg-sidebar border-t border-gray-700 flex items-center overflow-hidden whitespace-nowrap hover:bg-gray-800 transition-colors w-full text-left focus:outline-none focus:ring-2 focus:ring-primary"
         :class="isCollapsed && !isMobile ? 'justify-center px-0' : 'px-4'"
         title="查看个人信息"
      >
         <div class="h-8 w-8 rounded-full bg-gray-500 flex flex-shrink-0 items-center justify-center text-xs font-bold text-white uppercase">
            {{ userInfo.user_name ? userInfo.user_name.substring(0, 2) : 'USER' }}
         </div>
         <transition name="fade">
             <div v-if="!isCollapsed || isMobile" class="ml-3 flex-1">
                <p class="text-sm font-medium text-white">{{ userInfo.user_name || 'Loading...' }}</p>
                <p class="text-xs text-gray-400">{{ userInfo.role === 'admin' ? '管理员' : '普通用户' }}</p>
             </div>
         </transition>
         <transition name="fade">
            <svg v-if="!isCollapsed && !isMobile" class="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
         </transition>
      </button>
    </aside>

    <!-- Main Content Area -->
    <div class="flex-1 flex flex-col overflow-hidden min-w-0">
      <!-- Top Header -->
      <header class="bg-white shadow-sm h-16 flex justify-between items-center px-4 sm:px-6 lg:px-8 z-10 border-b border-gray-200 flex-shrink-0">
         <div class="flex items-center min-w-0 flex-1">
            <!-- Sidebar Toggle Button -->
            <button 
               @click="toggleSidebar"
               class="mr-3 text-gray-500 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-primary rounded-md p-1 shrink-0"
               title="Toggle Sidebar"
            >
               <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                   <path v-if="!isMobile && !isCollapsed" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" />
                   <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
               </svg>
            </button>

            <!-- Mobile Title -->
            <div v-if="isMobile" class="min-w-0 flex-1">
              <h1 class="text-sm font-bold text-gray-900 truncate">{{ currentPageTitle }}</h1>
            </div>

            <!-- Breadcrumbs -->
            <nav v-else class="hidden md:flex" aria-label="Breadcrumb">
              <ol class="flex items-center space-x-2">
                <li>
                   <router-link
                     to="/dashboard/overview"
                     class="text-gray-400 hover:text-indigo-600 transition-colors"
                     title="概览"
                   >
                      <svg class="flex-shrink-0 h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                         <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
                      </svg>
                   </router-link>
                </li>
                <li v-for="(crumb, index) in breadcrumbs" :key="index" class="flex items-center">
                   <svg class="flex-shrink-0 h-5 w-5 text-gray-300" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
                   </svg>
                   <span class="ml-2 text-sm font-medium text-gray-500 hover:text-gray-700 capitalize">{{ crumb }}</span>
                </li>
              </ol>
            </nav>
         </div>

         <div class="flex items-center space-x-2 sm:space-x-4 flex-shrink-0">
           <!-- Refined Status Capsule -->
           <div class="flex items-center bg-white/80 backdrop-blur-sm border border-gray-100 rounded-full px-0.5 sm:px-1 py-0.5 sm:py-1 shadow-sm hover:shadow-md transition-all duration-300">
             <!-- My Permissions -->
             <button 
                @click="openPermissionsModal"
                class="flex items-center px-1 sm:px-3 py-1 sm:py-1.5 rounded-full hover:bg-indigo-50 transition-all group focus:outline-none"
                title="查看我的资源权限"
              >
                <div class="p-0.5 sm:p-1 bg-indigo-100 rounded-md sm:rounded-lg sm:mr-2 group-hover:rotate-12 transition-transform duration-300">
                  <svg class="h-3 w-3 sm:h-4 sm:w-4 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 14l-1 1-1 1H3m9-9a6 6 0 019 9h9v1.8c0 .249-.088.485-.246.663l-4 4.062C8.6 20.2 8.3 20.3 8 20.5l-5-5-5-5L15 7z" />
                  </svg>
                </div>
                <span class="hidden sm:inline text-xs font-bold text-gray-600 group-hover:text-indigo-700">我的权限</span>
                <span class="ml-0.5 sm:ml-1.5 px-1 sm:px-1.5 py-px sm:py-0.5 bg-indigo-600 text-[9px] sm:text-[10px] font-black text-white rounded-full leading-none min-w-[16px] text-center">{{ myResources.length }}</span>
              </button>

             <div class="hidden sm:block w-px h-4 bg-gray-200 mx-1"></div>

             <!-- Online Users -->
             <div 
                @click="openOnlineUsers"
                :class="[
                  'flex items-center px-1 sm:px-3 py-1 sm:py-1.5 group custom-tooltip transition-colors',
                  userInfo.role === 'admin' ? 'cursor-pointer hover:bg-green-50 rounded-lg' : 'cursor-default'
                ]"
                :data-tooltip="userInfo.role === 'admin' ? '点击查看在线用户详情' : '当前在线用户 (Web 登录用户 + API 调用用户)'"
             >
                <div class="relative flex h-1.5 w-1.5 sm:h-2 sm:w-2 sm:mr-2.5">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-full w-full bg-green-500"></span>
                </div>
                <span class="text-xs sm:text-sm font-bold sm:font-black text-gray-700 tabular-nums">{{ onlineUserCount }}</span>
                <span class="hidden sm:inline text-[11px] font-bold text-gray-400 ml-1.5 group-hover:text-green-600 transition-colors">在线</span>
             </div>
           </div>

          <div class="hidden sm:block h-6 w-px bg-gray-200 mx-2" aria-hidden="true"></div>
          <button 
             @click="logout" 
             class="flex items-center px-2 sm:px-3 py-1.5 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 group"
          >
             <svg class="h-4 w-4 sm:mr-1.5 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
             </svg>
             <span class="hidden sm:inline">退出</span>
          </button>
        </div>
      </header>

      <!-- Main Scrollable Content -->
      <main class="flex-1 overflow-y-auto bg-gray-100 p-4 sm:p-6 lg:p-8 custom-scrollbar">
        <router-link
          v-if="catalogBadge.count > 0 && catalogBadge.can_access_requests"
          to="/dashboard/catalog-requests"
          class="mb-4 flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 hover:bg-amber-100/80 transition-colors"
        >
          <span>您有 <strong>{{ catalogBadge.count }}</strong> 条目录权限申请待审批</span>
          <span class="font-medium text-amber-800 whitespace-nowrap">立即处理 →</span>
        </router-link>
        <router-view v-slot="{ Component }">
           <transition name="page" mode="out-in">
              <component :is="Component" :key="$route.fullPath" />
           </transition>
        </router-view>
      </main>
    </div>

    <!-- Online Users Dialog -->
    <teleport to="body">
      <transition name="dialog">
        <div 
          v-if="showOnlineUsersDialog" 
          class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4"
          @click.self="showOnlineUsersDialog = false"
        >
          <div class="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
            <div class="flex items-center justify-between mb-6">
              <div class="flex items-center">
                <div class="p-2 bg-green-100 rounded-lg mr-3">
                  <div class="relative flex h-3 w-3">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                  </div>
                </div>
                <div>
                  <h3 class="text-xl font-black text-gray-900">在线用户详情</h3>
                  <p class="text-sm text-gray-500">当前共有 <span class="font-bold text-green-600">{{ onlineUserCount }}</span> 位活跃用户</p>
                </div>
              </div>
              <button 
                @click="showOnlineUsersDialog = false"
                class="text-gray-400 hover:text-gray-500 transition-colors p-2 hover:bg-gray-100 rounded-full"
              >
                <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div class="max-h-[60vh] overflow-y-auto custom-scrollbar pr-2">
              <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                  <tr>
                    <th scope="col" class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">用户名</th>
                    <th scope="col" class="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">角色</th>
                    <th scope="col" class="px-4 py-3 text-right text-xs font-bold text-gray-500 uppercase tracking-wider">最后活跃时间</th>
                  </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                  <tr v-for="user in onlineUsers" :key="user.username" class="hover:bg-gray-50 transition-colors">
                    <td class="px-4 py-4 whitespace-nowrap">
                      <div class="flex items-center">
                        <div class="h-8 w-8 rounded-full bg-indigo-100 flex items-center justify-center mr-3">
                          <span class="text-xs font-bold text-indigo-700">{{ user.username.charAt(0).toUpperCase() }}</span>
                        </div>
                        <span class="text-sm font-bold text-gray-900">{{ user.username }}</span>
                      </div>
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap">
                      <span 
                        :class="[
                          'px-2 py-0.5 text-[10px] font-black rounded-full uppercase',
                          user.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                        ]"
                      >
                        {{ user.role }}
                      </span>
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap text-right text-sm text-gray-500 font-medium">
                      {{ user.last_active }}
                    </td>
                  </tr>
                  <tr v-if="onlineUsers.length === 0">
                    <td colspan="3" class="px-4 py-8 text-center text-gray-500">
                      暂无在线用户信息
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="mt-8 flex justify-end">
              <button
                @click="showOnlineUsersDialog = false"
                class="px-6 py-2.5 bg-gray-900 text-white text-sm font-bold rounded-xl hover:bg-gray-800 transition-all active:scale-95 shadow-lg shadow-gray-200"
              >
                确定
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>

    <!-- Global Toast Notification -->
    <teleport to="body">
      <Toast 
        v-if="toast.show" 
        :key="toast.key"
        :message="toast.message" 
        :type="toast.type" 
        @close="closeToast" 
      />
    </teleport>

    <!-- Logout Confirmation Dialog -->
    <teleport to="body">
      <transition name="dialog">
        <div 
          v-if="showLogoutDialog" 
          class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
          @click.self="cancelLogout"
        >
          <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <div class="flex items-start">
              <div class="flex-shrink-0">
                <svg class="h-6 w-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div class="ml-3 flex-1">
                <h3 class="text-lg font-medium text-gray-900">确认退出</h3>
                <p class="mt-2 text-sm text-gray-500">您确定要退出登录吗？</p>
              </div>
            </div>
            <div class="mt-6 flex justify-end space-x-3">
              <button
                @click="cancelLogout"
                class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
              >
                取消
              </button>
              <button
                @click="confirmLogout"
                class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
              >
                退出登录
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>

    <!-- User Info Dialog -->
    <teleport to="body">
      <transition name="dialog">
        <div 
          v-if="showUserInfoDialog" 
          class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4"
          @click.self="closeUserInfo"
        >
          <div class="bg-white rounded-lg shadow-xl max-w-4xl w-full p-6"> <!-- 1. Widened Modal -->
            <!-- Header -->
            <div class="flex items-center justify-between mb-6">
              <h3 class="text-xl font-semibold text-gray-900">个人信息</h3>
              <button
                @click="closeUserInfo"
                class="text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary rounded-md p-1"
              >
                <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div class="flex flex-col md:flex-row gap-8"> <!-- 2. Two-column Flex Container -->
            
              <!-- Left Column: User Details & API Key -->
              <div class="flex-1 space-y-6">
                 <!-- User Avatar -->
                <div class="flex items-center">
                  <div class="h-16 w-16 rounded-full bg-primary flex items-center justify-center text-2xl font-bold text-white uppercase">
                    {{ userInfo.user_name ? userInfo.user_name.substring(0, 2) : 'U' }}
                  </div>
                  <div class="ml-4">
                    <h4 class="text-lg font-medium text-gray-900">{{ userInfo.user_name }}</h4>
                    <p class="text-sm text-gray-500">
                      <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium" 
                        :class="userInfo.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'"
                      >
                        {{ userInfo.role === 'admin' ? '管理员' : '普通用户' }}
                      </span>
                    </p>
                  </div>
                </div>

                <!-- User Details -->
                <div class="space-y-4">
                  <div>
                    <label class="block text-sm font-medium text-gray-700">用户名</label>
                    <p class="mt-1 text-sm text-gray-900">{{ userInfo.user_name }}</p>
                  </div>

                  <div v-if="userInfo.remark">
                    <label class="block text-sm font-medium text-gray-700">备注</label>
                    <p class="mt-1 text-sm text-gray-900">{{ userInfo.remark }}</p>
                  </div>

                  <div>
                    <label class="block text-sm font-medium text-gray-700">创建时间</label>
                    <p class="mt-1 text-sm text-gray-900">{{ userInfo.created_at || '-' }}</p>
                  </div>

                  <!-- API Key Section (Always Visible) -->
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">API Key</label>
                    <div class="flex items-center space-x-2">
                      <input
                        type="text"
                        :value="userApiKey || '点击“查看”加载 API Key'"
                        readonly
                        class="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-sm font-mono"
                      />
                      <button
                        v-if="!userApiKey"
                        @click="fetchApiKey"
                        :disabled="loadingApiKey"
                        class="px-4 py-2 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50"
                      >
                        {{ loadingApiKey ? '加载中...' : '查看' }}
                      </button>
                      <button
                        v-else
                        @click="copyApiKey"
                        class="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                        title="复制 API Key"
                      >
                        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      </button>
                    </div>
                    <p class="mt-1 text-xs text-gray-500">⚠️ API Key 支持重复查看和复制</p>
                  </div>
                </div>
              </div>

              <!-- Vertical Divider -->
              <div class="hidden md:block w-px bg-gray-200"></div>

              <!-- Right Column: Change Password -->
              <div class="flex-1">
                 <h4 class="text-lg font-medium text-gray-900 mb-4">修改密码</h4>
                 <form @submit.prevent="submitChangePassword" class="space-y-4">
                  <div>
                    <label class="block text-sm font-medium text-gray-700">旧密码</label>
                    <input 
                      v-model="passwordForm.oldPassword"
                      type="password" 
                      class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary sm:text-sm"
                      placeholder="首次设置请留空"
                    />
                  </div>

                  <div>
                    <label class="block text-sm font-medium text-gray-700">新密码</label>
                    <input 
                      v-model="passwordForm.newPassword"
                      type="password" 
                      required
                      minlength="6"
                      class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary sm:text-sm"
                      placeholder="请输入新密码 (至少6位)"
                    />
                  </div>
                  
                  <div>
                    <label class="block text-sm font-medium text-gray-700">确认新密码</label>
                    <input 
                      v-model="passwordForm.confirmPassword"
                      type="password" 
                      required
                      class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary sm:text-sm"
                      placeholder="请再次输入新密码"
                    />
                  </div>

                  <div class="flex justify-end pt-4">
                    <button
                      type="submit"
                      :disabled="loadingPassword"
                      class="w-full md:w-auto px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary-hover rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50"
                    >
                      {{ loadingPassword ? '提交中...' : '确认修改' }}
                    </button>
                  </div>
                </form>
              </div>

            </div>

            <!-- Footer (Simplified) -->
            <div class="mt-8 flex justify-end items-center border-t border-gray-200 pt-4">
              <button
                @click="closeUserInfo"
                class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>



    <!-- Permissions Modal -->
    <MyPermissionsModal 
      :isOpen="showPermissionsModal"
      :resources="myResources"
      :datasources="userPermissions?.datasources"
      :dataTables="userPermissions?.data_tables"
      :maskingStrategy="userInfo.masking_strategy"
      :rateLimit="userInfo.user_rate_limit || userInfo.role_rate_limit"
      @close="showPermissionsModal = false"
      @show-toast="showToast"
    />
  </div>
</template>

<style scoped>
/* Page Transition - Smoother than fade */
.page-enter-active {
  transition: opacity 0.15s ease-out, transform 0.15s ease-out;
}

.page-leave-active {
  transition: opacity 0.1s ease-in, transform 0.1s ease-in;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* Sidebar Text Fade */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  width: 0; /* Helps collapse/expand smoothness for text */
}

.menu-group-enter-active,
.menu-group-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.menu-group-enter-from,
.menu-group-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Dialog Animation */
.dialog-enter-active,
.dialog-leave-active {
  transition: opacity 0.3s ease;
}

.dialog-enter-from,
.dialog-leave-to {
  opacity: 0;
}

.dialog-enter-active > div,
.dialog-leave-active > div {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.dialog-enter-from > div,
.dialog-leave-to > div {
  transform: scale(0.9);
  opacity: 0;
}

/* Custom Tooltip Styles */
.custom-tooltip {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.custom-tooltip::after {
  content: attr(data-tooltip);
  position: absolute;
  top: 150%;
  right: 0;
  transform: none;
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
  top: 120%;
  right: 20px;
  border-width: 6px;
  border-style: solid;
  border-color: transparent transparent rgba(31, 41, 55, 0.95) transparent;
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 9999;
}

.custom-tooltip:hover::after {
  opacity: 1;
  visibility: visible;
  top: 160%;
}

.custom-tooltip:hover::before {
  opacity: 1;
  visibility: visible;
  top: 130%;
}
</style>
