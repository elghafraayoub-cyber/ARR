import type { Run } from '../api/client'

const STATUS_COLOR: Record<Run['status'], string> = {
  queued: '#999',
  running: '#4a9eff',
  done: '#2ecc71',
  failed: '#e74c3c',
}

export function ProgressBar({ run }: { run: Run }) {
  const pct = Math.min(100, Math.round((run.round_no / Math.max(1, run.max_critic_rounds)) * 100))
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span
          style={{
            color: STATUS_COLOR[run.status],
            fontWeight: 600,
            textTransform: 'uppercase',
            fontSize: '0.85rem',
          }}
        >
          {run.status}
        </span>
        <span style={{ fontSize: '0.85rem', color: '#666' }}>
          round {run.round_no} / {run.max_critic_rounds}
        </span>
      </div>
      <div style={{ background: '#eee', borderRadius: 4, height: 8, overflow: 'hidden' }}>
        <div
          style={{
            width: `${run.status === 'done' ? 100 : pct}%`,
            background: STATUS_COLOR[run.status],
            height: '100%',
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      <div style={{ display: 'flex', gap: '1.5rem', marginTop: 8, fontSize: '0.9rem' }}>
        <span>Entities: {run.entity_count}</span>
        <span>Findings: {run.finding_count}</span>
        {run.orphan_count !== null && <span>Orphans: {run.orphan_count}</span>}
      </div>
      {run.error && <p style={{ color: STATUS_COLOR.failed, marginTop: 8 }}>Error: {run.error}</p>}
    </div>
  )
}
