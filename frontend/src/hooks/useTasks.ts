import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type {
  CreateTaskPayload,
  ShareTaskPayload,
  UpdateTaskPayload,
} from '../api/types'

export function tasksQueryKey(userId: string) {
  return ['tasks', userId] as const
}

export function useTasks(userId: string | undefined, limit = 10, offset = 0) {
  return useQuery({
    queryKey: [...tasksQueryKey(userId ?? ''), { limit, offset }],
    queryFn: () => api.listUserTasks(userId!, { limit, offset }),
    enabled: Boolean(userId),
  })
}

export function useCreateTask(userId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateTaskPayload) => api.createTask(userId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tasksQueryKey(userId) })
    },
  })
}

export function useRenameTask(userId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ taskId, title }: { taskId: string; title: string }) =>
      api.renameTask(taskId, { title } satisfies UpdateTaskPayload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tasksQueryKey(userId) })
    },
  })
}

export function useStartTask(userId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (taskId: string) => api.startTask(taskId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tasksQueryKey(userId) })
    },
  })
}

export function useCompleteTask(userId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (taskId: string) => api.completeTask(taskId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tasksQueryKey(userId) })
    },
  })
}

export function useDeleteTask(userId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (taskId: string) => api.deleteTask(taskId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tasksQueryKey(userId) })
    },
  })
}

export function useShareTask() {
  return useMutation({
    mutationFn: ({
      taskId,
      payload,
    }: {
      taskId: string
      payload: ShareTaskPayload
    }) => api.shareTask(taskId, payload),
  })
}
