import { useEffect, useState } from 'react'
import { api, type Run } from '../api/client'

export function RunHistory({ onSelectRun }: { onSelectRun: (run: Run) => void }) {
  const [runs, setRuns] = useState<Run[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listRuns().then(setRuns).catch((e) => setError(String(e)))
  }, [])

  if (error) return <p style={{ color: '#e74c3c' }}>Failed to load runs: {error}</p>

  return (
    <div>
      <h2>Run History</h2>
      {runs.length === 0 ? (
        <p>No runs yet — start one from the Upload &amp; Config tab.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '2px solid #ddd' }}>
              <th style={{ padding: '6px 8px' }}>Paper</th>
              <th style={{ padding: '6px 8px' }}>Status</th>
              <th style={{ padding: '6px 8px' }}>Entities</th>
              <th style={{ padding: '6px 8px' }}>Findings</th>
              <th style={{ padding: '6px 8px' }}>Orphan rate</th>
              <th style={{ padding: '6px 8px' }}>Condition coverage</th>
              <th style={{ padding: '6px 8px' }}>Created</th>
              <th style={{ padding: '6px 8px' }} />
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '6px 8px' }}>{run.paper_source}</td>
                <td style={{ padding: '6px 8px' }}>{run.status}</td>
                <td style={{ padding: '6px 8px' }}>{run.entity_count}</td>
                <td style={{ padding: '6px 8px' }}>{run.finding_count}</td>
                <td style={{ padding: '6px 8px' }}>
                  {run.orphan_count !== null && run.entity_count > 0
                    ? `${((run.orphan_count / run.entity_count) * 100).toFixed(1)}%`
                    : '—'}
                </td>
                <td style={{ padding: '6px 8px' }}>
                  {run.condition_coverage !== null ? run.condition_coverage.toFixed(2) : '—'}
                </td>
                <td style={{ padding: '6px 8px' }}>{new Date(run.created_at).toLocaleString()}</td>
                <td style={{ padding: '6px 8px' }}>
                  <button onClick={() => onSelectRun(run)}>
                    {run.status === 'done' ? 'View graph' : 'Monitor'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
