export interface Run {
  id: string
  paper_source: string
  status: 'queued' | 'running' | 'done' | 'failed'
  provider: string
  model: string
  max_critic_rounds: number
  round_no: number
  entity_count: number
  finding_count: number
  orphan_count: number | null
  duplicate_count: number | null
  vacuous_condition_count: number | null
  condition_coverage: number | null
  kg_path: string
  trace_path: string | null
  error: string | null
  created_at: string
  updated_at: string
}

export interface Entity {
  pk: number
  run_id: string
  entity_id: string
  name: string
  entity_type: string
  description: string
  evidence_quote: string
  confidence: number
  paper_source: string
  is_orphan: boolean
}

export interface Condition {
  condition_text: string
  parameter?: string | null
  threshold?: string | null
  operator?: string | null
  temporal?: string | null
  spatial?: string | null
  soil_type?: string | null
  statistical_evidence?: string | null
}

export interface Finding {
  pk: number
  run_id: string
  finding_id: string
  source_id: string
  target_id: string
  relation_type: string
  effect_magnitude: string | null
  p_value: string | null
  evidence_quote: string
  confidence: number
  has_flags: boolean
  conditions_json: string
}

export interface Config {
  provider: string
  model: string
  vllm_base_url: string
  ollama_base_url: string
  max_critic_rounds: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: init?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  listPapers: () => request<string[]>('/api/papers'),

  uploadPaper: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ paper_source?: string; error?: string }>('/api/papers/upload', {
      method: 'POST',
      body: form,
    })
  },

  getConfig: () => request<Config>('/api/config'),

  updateConfig: (update: Partial<Config>) =>
    request<Config>('/api/config', { method: 'PUT', body: JSON.stringify(update) }),

  listRuns: () => request<Run[]>('/api/runs'),

  getRun: (id: string) => request<Run>(`/api/runs/${id}`),

  getRunStatus: (id: string) => request<Run & { log_lines: string[] }>(`/api/runs/${id}/status`),

  startRun: (params: {
    paper_source: string
    provider?: string
    model?: string
    max_critic_rounds?: number
  }) => request<Run>('/api/runs', { method: 'POST', body: JSON.stringify(params) }),

  getEntities: (
    runId: string,
    params: { entity_type?: string; q?: string; page?: number; page_size?: number } = {},
  ) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][],
    )
    return request<Entity[]>(`/api/runs/${runId}/entities?${qs.toString()}`)
  },

  getFindings: (
    runId: string,
    params: { relation_type?: string; flagged?: boolean; page?: number; page_size?: number } = {},
  ) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][],
    )
    return request<Finding[]>(`/api/runs/${runId}/findings?${qs.toString()}`)
  },
}
