import type { Config } from '../api/client'

export function ConfigForm({
  config,
  onChange,
}: {
  config: Config
  onChange: (update: Partial<Config>) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxWidth: 420 }}>
      <label>
        Provider
        <select
          value={config.provider}
          onChange={(e) => onChange({ provider: e.target.value })}
          style={{ width: '100%' }}
        >
          <option value="vllm">vllm</option>
          <option value="ollama">ollama</option>
        </select>
      </label>
      <label>
        Model
        <input
          type="text"
          value={config.model}
          onChange={(e) => onChange({ model: e.target.value })}
          placeholder="/models/Qwen3-32B or llama3.1"
          style={{ width: '100%' }}
        />
      </label>
      <label>
        {config.provider === 'vllm' ? 'vLLM base URL' : 'Ollama base URL'}
        <input
          type="text"
          value={config.provider === 'vllm' ? config.vllm_base_url : config.ollama_base_url}
          onChange={(e) =>
            onChange(
              config.provider === 'vllm'
                ? { vllm_base_url: e.target.value }
                : { ollama_base_url: e.target.value },
            )
          }
          style={{ width: '100%' }}
        />
      </label>
      <label>
        Max critic rounds
        <input
          type="number"
          min={1}
          max={10}
          value={config.max_critic_rounds}
          onChange={(e) => onChange({ max_critic_rounds: Number(e.target.value) })}
          style={{ width: '100%' }}
        />
      </label>
    </div>
  )
}
