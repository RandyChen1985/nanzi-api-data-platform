import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import Overview from '../views/Overview.vue'
import AuditLogs from '../views/AuditLogs.vue'
import Playground from '../views/Playground.vue'
import Users from '../views/Users.vue'
import { MOBILE_LAYOUT_BREAKPOINT } from '../composables/useMobileLayout'

const isMobileViewport = () =>
  typeof window !== 'undefined' && window.innerWidth < MOBILE_LAYOUT_BREAKPOINT

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: Login
    },
    {
      path: '/dashboard',
      component: Dashboard,
      children: [
        {
          path: '',
          redirect: { name: 'Catalog' },
        },
        {
          path: 'overview',
          name: 'Overview',
          component: Overview,
          meta: { menuCode: 'menu:overview' }
        },
        {
          path: 'users',
          name: 'Users',
          component: Users,
          meta: { menuCode: 'menu:users' }
        },
        {
          path: 'roles',
          name: 'Roles',
          component: () => import('../views/Roles.vue'),
          meta: { menuCode: 'menu:system:roles' }
        },
        {
          path: 'audit',
          name: 'Audit',
          component: AuditLogs,
          meta: { menuCode: 'menu:audit', desktopOnly: true }
        },
        {
          path: 'playground',
          name: 'Playground',
          component: Playground,
          meta: { menuCode: 'menu:playground', desktopOnly: true }
        },
        {
          path: 'lab',
          name: 'SQLLab',
          component: () => import('../views/SQLLab.vue'),
          meta: { menuCode: 'menu:lab', desktopOnly: true }
        },
        {
          path: 'developer',
          name: 'DeveloperPortal',
          component: () => import('../views/developer/DeveloperPortal.vue'),
          meta: { desktopOnly: true },
        },
        {
          path: 'datasources',
          name: 'DataSourceList',
          component: () => import('../views/datasource/DataSourceList.vue'),
          meta: { menuCode: 'menu:datasource', desktopOnly: true }
        },
        {
          path: 'resources',
          name: 'Resources',
          component: () => import('../views/resources/ResourceList.vue'),
          meta: { menuCode: 'menu:resources', desktopOnly: true }
        },
        {
          path: 'resources/:key',
          name: 'ResourceEdit',
          component: () => import('../views/resources/ResourceEdit.vue'),
          meta: { menuCode: 'menu:resources', desktopOnly: true }
        },
        {
          path: 'metadata',
          name: 'MetadataCenter',
          component: () => import('../views/MetadataCenter.vue'),
          meta: { menuCode: 'menu:metadata', desktopOnly: true }
        },
        {
          path: 'metadata/:id',
          name: 'MetadataDetail',
          component: () => import('../views/MetadataDetail.vue'),
          meta: { menuCode: 'menu:metadata', desktopOnly: true }
        },
        {
          path: 'metadata/simulator',
          name: 'SearchSimulator',
          component: () => import('../views/SearchSimulator.vue'),
          meta: { menuCode: 'menu:metadata', desktopOnly: true }
        },
        {
          path: 'catalog',
          name: 'Catalog',
          component: () => import('../views/Catalog.vue')
        },
        {
          path: 'catalog/:key/edit',
          name: 'CatalogProductEdit',
          component: () => import('../views/CatalogProductEdit.vue')
        },
        {
          path: 'catalog/:key',
          name: 'CatalogDetail',
          component: () => import('../views/CatalogDetail.vue')
        },
        {
          path: 'catalog-my-applications',
          name: 'CatalogMyApplications',
          component: () => import('../views/CatalogMyApplications.vue'),
        },
        {
          path: 'catalog-change-notifications',
          name: 'CatalogChangeNotifications',
          component: () => import('../views/CatalogChangeNotifications.vue'),
        },
        {
          path: 'catalog-redundant',
          name: 'CatalogRedundant',
          component: () => import('../views/CatalogRedundant.vue'),
          meta: { desktopOnly: true },
        },
        {
          path: 'catalog-requests',
          name: 'CatalogAccessRequests',
          component: () => import('../views/CatalogAccessRequests.vue'),
          meta: { menuCode: 'menu:catalog:requests' }
        },
        {
          path: 'asset-panorama',
          name: 'AssetPanorama',
          component: () => import('../views/AssetPanorama.vue'),
          meta: { menuCode: 'menu:asset-panorama' }
        },
        {
          path: 'settings',
          name: 'SystemSettings',
          component: () => import('../views/SystemConfig.vue'),
          meta: { menuCode: 'menu:config' }
        },
        {
          path: 'personal',
          name: 'PersonalCenter',
          component: () => import('../views/PersonalCenter.vue'),
        },
        {
          path: '403',
          name: 'Forbidden',
          component: () => import('../views/Forbidden.vue')
        }
      ]
    },
    {
      path: '/',
      redirect: '/dashboard/catalog'
    }
  ]
})

router.beforeEach(async (to: any, _from: any, next: any) => {
  const isAuthenticated = !!localStorage.getItem('api_key')
  
  if (to.name !== 'Login' && !isAuthenticated) {
    next({ name: 'Login' })
    return
  }

  if (isAuthenticated && isMobileViewport()) {
    if (to.meta?.desktopOnly) {
      next({ name: 'Catalog' })
      return
    }
  }

  // Permission Check
  const userInfoStr = localStorage.getItem('user_info')
  if (userInfoStr) {
    const userInfo = JSON.parse(userInfoStr)
    const userRole = userInfo.role
    
    // 1. Admin bypass everything
    if (userRole === 'admin') {
      next()
      return
    }

    // 2. Check Menu Permissions (Controlled by ABAC)
    const targetMenu = to.meta.menuCode
    if (targetMenu) {
      const userMenus = userInfo.permissions?.menus || []
      
      // If user is logged in but has NO menus at all, and isn't admin
      if (userMenus.length === 0 && userRole !== 'admin' && to.name !== 'Forbidden') {
          next({ name: 'Forbidden' })
          return
      }

      // 目录权限申请：以服务端 pending-count 为准，避免 localStorage 残留 menu 权限
      if (targetMenu === 'menu:catalog:requests') {
        const userElements = userInfo.permissions?.elements || []
        const canBySession = sessionStorage.getItem('catalog_can_access_requests') === '1'
        const ownedProducts = Number(sessionStorage.getItem('catalog_owned_products') || 0)
        if (
          userElements.includes('element:catalog:review') ||
          canBySession ||
          ownedProducts > 0
        ) {
          next()
          return
        }
        if (to.name !== 'Forbidden') {
          next({ name: 'Forbidden' })
          return
        }
      }

      if (!userMenus.includes(targetMenu)) {
        // Optimization: If accessing Overview (default page) but denied,
        // try to redirect to the first accessible page instead of Forbidden.
        if (to.name === 'Overview' && userRole !== 'admin') {
          const allRoutes = router.getRoutes()
          const firstAllowed = allRoutes.find(r => 
            r.meta?.menuCode && 
            userMenus.includes(r.meta.menuCode as string) &&
            r.name !== 'Overview' &&
            !r.meta?.desktopOnly
          )
          
          if (firstAllowed) {
            next({ name: firstAllowed.name })
            return
          }
        }

        if (to.name !== 'Forbidden') {
          next({ name: 'Forbidden' })
          return
        }
      }
    }
  }

  next()
})

export default router