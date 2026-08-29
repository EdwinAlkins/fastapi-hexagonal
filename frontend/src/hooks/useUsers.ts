import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { CreateUserPayload } from '../api/types'

export const usersQueryKey = ['users'] as const

export function useUsers(limit = 100, offset = 0) {
  return useQuery({
    queryKey: [...usersQueryKey, { limit, offset }],
    queryFn: () => api.listUsers({ limit, offset }),
  })
}

export function useUser(userId: string | undefined) {
  return useQuery({
    queryKey: [...usersQueryKey, userId],
    queryFn: () => api.getUser(userId!),
    enabled: Boolean(userId),
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateUserPayload) => api.createUser(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: usersQueryKey })
    },
  })
}

export function useRenameUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ userId, name }: { userId: string; name: string }) =>
      api.renameUser(userId, { name }),
    onSuccess: (user) => {
      // Le back invalide son cache Redis (cf. RenameUser) ; côté client on fait
      // pareil sur le cache React Query : écriture immédiate du détail (pas de
      // flash), puis invalidation de la clé `['users']` — qui couvre par préfixe
      // la fiche `['users', id]` et la liste `['users', {limit, offset}]`.
      queryClient.setQueryData([...usersQueryKey, user.id], user)
      void queryClient.invalidateQueries({ queryKey: usersQueryKey })
    },
  })
}
