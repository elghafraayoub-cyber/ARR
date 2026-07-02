import { createContext, useContext, useState, type ReactNode } from 'react'

interface RunContextValue {
  currentRunId: string | null
  setCurrentRunId: (id: string | null) => void
}

const RunContext = createContext<RunContextValue | undefined>(undefined)

export function RunProvider({ children }: { children: ReactNode }) {
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  return (
    <RunContext.Provider value={{ currentRunId, setCurrentRunId }}>
      {children}
    </RunContext.Provider>
  )
}

export function useRunContext(): RunContextValue {
  const ctx = useContext(RunContext)
  if (!ctx) throw new Error('useRunContext must be used within a RunProvider')
  return ctx
}
