import type { Finding } from '../api/client'

export function FindingTable({ findings }: { findings: Finding[] }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
      <thead>
        <tr style={{ textAlign: 'left', borderBottom: '2px solid #ddd' }}>
          <th style={{ padding: '6px 8px' }}>Source</th>
          <th style={{ padding: '6px 8px' }}>Relation</th>
          <th style={{ padding: '6px 8px' }}>Target</th>
          <th style={{ padding: '6px 8px' }}>Confidence</th>
          <th style={{ padding: '6px 8px' }}>Flags</th>
        </tr>
      </thead>
      <tbody>
        {findings.map((f) => (
          <tr key={f.finding_id} style={{ borderBottom: '1px solid #eee' }}>
            <td style={{ padding: '6px 8px' }}>{f.source_id}</td>
            <td style={{ padding: '6px 8px' }}>{f.relation_type}</td>
            <td style={{ padding: '6px 8px' }}>{f.target_id}</td>
            <td style={{ padding: '6px 8px' }}>{f.confidence.toFixed(2)}</td>
            <td style={{ padding: '6px 8px' }}>
              {f.has_flags && <span style={{ color: '#e74c3c', fontWeight: 600 }}>flagged</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
