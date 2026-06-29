/**
 * 认证相关 API
 */
import api from '@/utils/axios'

export interface LoginPayload {
  username: string
  password: string
}

export interface UserInfo {
  user_id: string
  user_name: string
  role: string
  api_key?: string
}

export async function loginWithApiKey(apiKey: string) {
  const { data } = await api.post<{ status: string; data: UserInfo }>(
    '/api/portal/auth/login',
    { api_key: apiKey }
  )
  return data
}

export async function login(payload: LoginPayload) {
  const { data } = await api.post<{ status: string; data: UserInfo }>(
    '/api/portal/auth/login',
    payload
  )
  return data
}

export async function ssoLogin(payload: LoginPayload) {
  const { data } = await api.post<{ status: string; data: UserInfo }>(
    '/api/portal/auth/sso/login',
    payload
  )
  return data
}

export async function logout() {
  return api.post('/api/portal/auth/logout')
}

export async function getCurrentUser() {
  const { data } = await api.get<{ status: string; data: UserInfo }>(
    '/api/portal/auth/me'
  )
  return data
}
