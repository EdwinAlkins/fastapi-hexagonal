import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { User } from '../api/types'

interface CurrentUserContextValue {
  currentUser: User | null
  setCurrentUser: (user: User | null) => void
}

const CurrentUserContext = createContext<CurrentUserContextValue | null>(null)

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUserState] = useState<User | null>(null)

  const setCurrentUser = useCallback((user: User | null) => {
    setCurrentUserState(user)
  }, [])

  const value = useMemo(
    () => ({ currentUser, setCurrentUser }),
    [currentUser, setCurrentUser],
  )

  return (
    <CurrentUserContext.Provider value={value}>
      {children}
    </CurrentUserContext.Provider>
  )
}

export function useCurrentUser() {
  const ctx = useContext(CurrentUserContext)
  if (!ctx) {
    throw new Error('useCurrentUser doit être utilisé dans CurrentUserProvider')
  }
  return ctx
}
