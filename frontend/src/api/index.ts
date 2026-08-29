/** Client HTTP typé (contrat `/api/v1`). Régénérable depuis `/openapi.json` plus tard. */
export { api, ApiError } from './client'
export type {
  CreateTaskPayload,
  CreateUserPayload,
  PaginationParams,
  ShareTaskPayload,
  Task,
  TaskStatus,
  UpdateTaskPayload,
  UpdateUserPayload,
  User,
} from './types'
