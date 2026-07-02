import { useEffect, useMemo, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { api, type Condition, type Entity, type Finding } from '../api/client'

const TYPE_COLORS: Record<string, string> = {
  SOIL_PHYSICAL_PROPERTY: '#3498db',
  SOIL_CHEMICAL_PROPERTY: '#9b59b6',
  BIOLOGICAL_AGENT: '#27ae60',
  SOIL_PROCESS: '#16a085',
  MANAGEMENT_PRACTICE: '#e67e22',
  CROP_SPECIES: '#2ecc71',
  PLANT_RESPONSE: '#f1c40f',
  ENVIRONMENTAL_FACTOR: '#1abc9c',
  ECOSYSTEM_SERVICE: '#3498db',
  QUANTITATIVE_OUTCOME: '#e74c3c',
  EXPERIMENTAL_CONTEXT: '#7f8c8d',
  OTHER: '#95a5a6',
}

interface GraphNode {
  id: string
  name: string
  entity_type: string
  color: string
  entity: Entity
}

interface GraphLink {
  source: string
  target: string
  relation_type: string
  finding: Finding
}

type Selected = { kind: 'entity'; data: Entity } | { kind: 'finding'; data: Finding } | null

export function GraphExplorer({ runId }: { runId: string }) {
  const [entities, setEntities] = useState<Entity[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [selected, setSelected] = useState<Selected>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      api.getEntities(runId, { page_size: 500 }),
      api.getFindings(runId, { page_size: 500 }),
    ])
      .then(([e, f]) => {
        setEntities(e)
        setFindings(f)
      })
      .catch((e) => setError(String(e)))
  }, [runId])

  const graphData = useMemo(() => {
    const nodes: GraphNode[] = entities.map((e) => ({
      id: e.entity_id,
      name: e.name,
      entity_type: e.entity_type,
      color: TYPE_COLORS[e.entity_type] ?? TYPE_COLORS.OTHER,
      entity: e,
    }))
    const nodeIds = new Set(nodes.map((n) => n.id))
    const links: GraphLink[] = findings
      .filter((f) => nodeIds.has(f.source_id) && nodeIds.has(f.target_id))
      .map((f) => ({
        source: f.source_id,
        target: f.target_id,
        relation_type: f.relation_type,
        finding: f,
      }))
    return { nodes, links }
  }, [entities, findings])

  if (error) return <p style={{ color: '#e74c3c' }}>Failed to load graph: {error}</p>

  return (
    <div style={{ display: 'flex', gap: '1rem' }}>
      <div style={{ flex: 1, border: '1px solid #ddd', borderRadius: 8, overflow: 'hidden' }}>
        <ForceGraph2D
          graphData={graphData}
          width={800}
          height={600}
          nodeId="id"
          nodeLabel={(n) => `${(n as GraphNode).name} (${(n as GraphNode).entity_type})`}
          nodeColor={(n) => (n as GraphNode).color}
          nodeVal={(n) => ((n as GraphNode).entity.is_orphan ? 2 : 4)}
          linkLabel={(l) => (l as unknown as GraphLink).relation_type}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          onNodeClick={(n) => setSelected({ kind: 'entity', data: (n as GraphNode).entity })}
          onLinkClick={(l) => setSelected({ kind: 'finding', data: (l as unknown as GraphLink).finding })}
        />
      </div>

      <div style={{ width: 320, flexShrink: 0 }}>
        <h3>Details</h3>
        {!selected && <p>Click a node or edge to inspect it.</p>}
        {selected?.kind === 'entity' && <EntityDetail entity={selected.data} />}
        {selected?.kind === 'finding' && <FindingDetail finding={selected.data} />}

        <h3 style={{ marginTop: '1.5rem' }}>Legend</h3>
        <div style={{ fontSize: '0.8rem' }}>
          {Object.entries(TYPE_COLORS).map(([type, color]) => (
            <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
              <span style={{ width: 10, height: 10, background: color, borderRadius: '50%', display: 'inline-block' }} />
              {type}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function EntityDetail({ entity }: { entity: Entity }) {
  return (
    <div style={{ fontSize: '0.9rem' }}>
      <p>
        <strong>{entity.name}</strong> {entity.is_orphan && <span style={{ color: '#e74c3c' }}>(orphan)</span>}
      </p>
      <p>Type: {entity.entity_type}</p>
      <p>Confidence: {entity.confidence.toFixed(2)}</p>
      <p>{entity.description}</p>
      {entity.evidence_quote && (
        <blockquote style={{ borderLeft: '3px solid #ccc', paddingLeft: 8, color: '#555' }}>
          "{entity.evidence_quote}"
        </blockquote>
      )}
    </div>
  )
}

function FindingDetail({ finding }: { finding: Finding }) {
  let conditions: Condition[] = []
  try {
    conditions = JSON.parse(finding.conditions_json)
  } catch {
    conditions = []
  }
  return (
    <div style={{ fontSize: '0.9rem' }}>
      <p>
        <strong>{finding.source_id}</strong> —{finding.relation_type}→ <strong>{finding.target_id}</strong>
      </p>
      <p>Confidence: {finding.confidence.toFixed(2)}</p>
      {finding.effect_magnitude && <p>Effect magnitude: {finding.effect_magnitude}</p>}
      {finding.p_value && <p>p-value: {finding.p_value}</p>}
      {finding.has_flags && <p style={{ color: '#e74c3c' }}>Flagged by critic</p>}
      {finding.evidence_quote && (
        <blockquote style={{ borderLeft: '3px solid #ccc', paddingLeft: 8, color: '#555' }}>
          "{finding.evidence_quote}"
        </blockquote>
      )}
      {conditions.length > 0 && (
        <>
          <p style={{ marginBottom: 2 }}>Conditions:</p>
          <ul style={{ marginTop: 0, paddingLeft: 18 }}>
            {conditions.map((c, i) => (
              <li key={i}>{c.condition_text}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
