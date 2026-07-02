import type { Entity } from '../api/client'

export function EntityTable({ entities }: { entities: Entity[] }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
      <thead>
        <tr style={{ textAlign: 'left', borderBottom: '2px solid #ddd' }}>
          <th style={{ padding: '6px 8px' }}>Name</th>
          <th style={{ padding: '6px 8px' }}>Type</th>
          <th style={{ padding: '6px 8px' }}>Confidence</th>
          <th style={{ padding: '6px 8px' }}>Orphan</th>
        </tr>
      </thead>
      <tbody>
        {entities.map((e) => (
          <tr key={e.entity_id} style={{ borderBottom: '1px solid #eee' }}>
            <td style={{ padding: '6px 8px' }}>{e.name}</td>
            <td style={{ padding: '6px 8px' }}>{e.entity_type}</td>
            <td style={{ padding: '6px 8px' }}>{e.confidence.toFixed(2)}</td>
            <td style={{ padding: '6px 8px' }}>
              {e.is_orphan && (
                <span style={{ color: '#e74c3c', fontWeight: 600 }}>orphan</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
