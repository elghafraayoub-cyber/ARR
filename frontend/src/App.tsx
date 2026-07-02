import { useState } from 'react'
import { RunProvider, useRunContext } from './RunContext'
import { Upload } from './pages/Upload'
import { RunMonitor } from './pages/RunMonitor'
import { GraphExplorer } from './pages/GraphExplorer'
import { RunHistory } from './pages/RunHistory'
import type { Run } from './api/client'

type Tab = 'upload' | 'monitor' | 'graph' | 'history'

function AppShell() {
  const [tab, setTab] = useState<Tab>('history')
  const { currentRunId, setCurrentRunId } = useRunContext()

  const goToRun = (run: Run) => {
    setCurrentRunId(run.id)
    setTab(run.status === 'done' ? 'graph' : 'monitor')
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'history', label: 'Run History' },
    { id: 'upload', label: 'Upload & Config' },
    { id: 'monitor', label: 'Run Monitor' },
    { id: 'graph', label: 'Graph Explorer' },
  ]

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '1.5rem', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ marginBottom: '0.25rem' }}>Soil KG Builder</h1>
      <p style={{ color: '#666', marginTop: 0 }}>Local knowledge-graph extraction — vLLM / Ollama only</p>

      <nav style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid #ddd' }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            disabled={(t.id === 'monitor' || t.id === 'graph') && !currentRunId}
            style={{
              padding: '0.5rem 1rem',
              border: 'none',
              borderBottom: tab === t.id ? '2px solid #4a9eff' : '2px solid transparent',
              background: 'transparent',
              fontWeight: tab === t.id ? 600 : 400,
              cursor: 'pointer',
            }}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === 'history' && <RunHistory onSelectRun={goToRun} />}
      {tab === 'upload' && <Upload onRunStarted={goToRun} />}
      {tab === 'monitor' && currentRunId && (
        <RunMonitor runId={currentRunId} onDone={() => setTab('graph')} />
      )}
      {tab === 'graph' && currentRunId && <GraphExplorer runId={currentRunId} />}
    </div>
  )
}

function App() {
  return (
    <RunProvider>
      <AppShell />
    </RunProvider>
  )
}

export default App
