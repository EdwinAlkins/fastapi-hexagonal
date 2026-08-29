/** Types alignés sur le contrat OpenAPI de l'API (`/api/v1`). */

export type TaskStatus = 'todo' | 'in_progress' | 'done'

export interface User {
  id: string
  name: string
  email: string
  created_at: string
}

export interface Task {
  id: string
  owner_id: string
  title: string
  description: string | null
  status: TaskStatus
  created_at: string
  completed_at: string | null
}

export interface CreateUserPayload {
  name: string
  email: string
}

export interface UpdateUserPayload {
  name: string
}

export interface CreateTaskPayload {
  title: string
  description?: string | null
}

export interface UpdateTaskPayload {
  title: string
}

export interface PaginationParams {
  limit?: number
  offset?: number
}

export interface ShareTaskPayload {
  user_ids: string[]
  subject: string
  body: string
}
