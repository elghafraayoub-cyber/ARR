import { useEffect, useRef, useState } from 'react'
import { api, type Run } from '../api/client'
import { ProgressBar } from '../components/ProgressBar'

const POLL_MS = 1500

export function RunMonitor({ runId, onDone }: { runId: string; onDone: (run: Run) => void }) {
  const [run, setRun] = useState<Run | null>(null)
  const [logLines, setLogLines] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let cancelled = false

    const poll = async () => {
      try {
        const r = await api.getRunStatus(runId)
        if (cancelled) return
        setRun(r)
        setLogLines(r.log_lines)
        if (r.status === 'done' || r.status === 'failed') {
          if (intervalRef.current) clearInterval(intervalRef.current)
          if (r.status === 'done') onDone(r)
        }
      } catch (e) {
        if (!cancelled) setError(String(e))
      }
    }

    poll()
    intervalRef.current = setInterval(poll, POLL_MS)
    return () => {
      cancelled = true
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])

  if (error) return <p style={{ color: '#e74c3c' }}>Failed to poll run: {error}</p>
  if (!run) return <p>Loading run status…</p>

  return (
    <div>
      <h2>Run Monitor — {run.paper_source}</h2>
      <ProgressBar run={run} />

      <h3 style={{ marginTop: '1.5rem' }}>Live agent log</h3>
      <div
        style={{
          background: '#111',
          color: '#0f0',
          fontFamily: 'monospace',
          fontSize: '0.8rem',
          padding: '0.75rem',
          borderRadius: 6,
          height: 260,
          overflowY: 'auto',
        }}
      >
        {logLines.length === 0 ? (
          <div style={{ color: '#888' }}>Waiting for agent activity…</div>
        ) : (
          logLines.map((line, i) => <div key={i}>{line}</div>)
        )}
      </div>

      {run.status === 'done' && (
        <button style={{ marginTop: '1rem' }} onClick={() => onDone(run)}>
          View graph
        </button>
      )}
    </div>
  )
}
