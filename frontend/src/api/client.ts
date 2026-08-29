import type {
  CreateTaskPayload,
  CreateUserPayload,
  PaginationParams,
  Task,
  UpdateTaskPayload,
  UpdateUserPayload,
  User,
  ShareTaskPayload,
} from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly body?: unknown

  constructor(message: string, status: number, body?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
    ...init,
  })

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  const data = text ? (JSON.parse(text) as unknown) : undefined

  if (!response.ok) {
    const detail =
      typeof data === 'object' &&
      data !== null &&
      'detail' in data &&
      typeof (data as { detail: unknown }).detail === 'string'
        ? (data as { detail: string }).detail
        : `Erreur HTTP ${response.status}`
    throw new ApiError(detail, response.status, data)
  }

  return data as T
}

function toQuery(params?: PaginationParams): string {
  if (!params) return ''
  const search = new URLSearchParams()
  if (params.limit !== undefined) search.set('limit', String(params.limit))
  if (params.offset !== undefined) search.set('offset', String(params.offset))
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export const api = {
  listUsers(params?: PaginationParams) {
    return request<User[]>(`/api/v1/users${toQuery(params)}`)
  },

  getUser(userId: string) {
    return request<User>(`/api/v1/users/${userId}`)
  },

  createUser(payload: CreateUserPayload) {
    return request<User>('/api/v1/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  renameUser(userId: string, payload: UpdateUserPayload) {
    return request<User>(`/api/v1/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  listUserTasks(userId: string, params?: PaginationParams) {
    return request<Task[]>(`/api/v1/users/${userId}/tasks${toQuery(params)}`)
  },

  createTask(userId: string, payload: CreateTaskPayload) {
    return request<Task>(`/api/v1/users/${userId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  renameTask(taskId: string, payload: UpdateTaskPayload) {
    return request<Task>(`/api/v1/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  startTask(taskId: string) {
    return request<Task>(`/api/v1/tasks/${taskId}/start`, { method: 'POST' })
  },

  completeTask(taskId: string) {
    return request<Task>(`/api/v1/tasks/${taskId}/complete`, { method: 'POST' })
  },

  deleteTask(taskId: string) {
    return request<void>(`/api/v1/tasks/${taskId}`, { method: 'DELETE' })
  },

  shareTask(taskId: string, payload: ShareTaskPayload) {
    return request<void>(`/api/v1/tasks/${taskId}/share`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}
