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

/** Projection de lecture de l'export : plate, telle que la renvoie le query service. */
export interface TaskWithOwner {
  task_id: string
  title: string
  /** Transportée pour l'import, jamais affichée : voir le chapitre 10 du cours. */
  description: string | null
  status: TaskStatus
  created_at: string
  completed_at: string | null
  owner_id: string
  owner_name: string
  owner_email: string
}
