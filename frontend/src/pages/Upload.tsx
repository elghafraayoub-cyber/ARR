import { useEffect, useState } from 'react'
import { api, type Config, type Run } from '../api/client'
import { FileDropzone } from '../components/FileDropzone'
import { ConfigForm } from '../components/ConfigForm'

export function Upload({ onRunStarted }: { onRunStarted: (run: Run) => void }) {
  const [papers, setPapers] = useState<string[]>([])
  const [selectedPaper, setSelectedPaper] = useState<string>('')
  const [config, setConfig] = useState<Config | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)

  const refreshPapers = () => {
    api.listPapers().then((list) => {
      setPapers(list)
      if (!selectedPaper && list.length > 0) setSelectedPaper(list[0])
    })
  }

  useEffect(() => {
    refreshPapers()
    api.getConfig().then(setConfig)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleUpload = async (file: File) => {
    setStatus(`Uploading ${file.name}…`)
    try {
      const res = await api.uploadPaper(file)
      if (res.error) {
        setStatus(`Upload failed: ${res.error}`)
        return
      }
      setStatus(`Uploaded ${res.paper_source}`)
      refreshPapers()
      if (res.paper_source) setSelectedPaper(res.paper_source)
    } catch (e) {
      setStatus(`Upload failed: ${e}`)
    }
  }

  const handleConfigChange = (update: Partial<Config>) => {
    if (!config) return
    const next = { ...config, ...update }
    setConfig(next)
    api.updateConfig(update).catch((e) => setStatus(`Config update failed: ${e}`))
  }

  const handleStart = async () => {
    if (!selectedPaper || !config) return
    setStarting(true)
    setStatus(null)
    try {
      const run = await api.startRun({
        paper_source: selectedPaper,
        provider: config.provider,
        model: config.model,
        max_critic_rounds: config.max_critic_rounds,
      })
      onRunStarted(run)
    } catch (e) {
      setStatus(`Failed to start run: ${e}`)
    } finally {
      setStarting(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: 500 }}>
      <div>
        <h2>Upload a paper</h2>
        <FileDropzone onUpload={handleUpload} />
        {status && <p style={{ marginTop: '0.5rem' }}>{status}</p>}
      </div>

      <div>
        <h2>Select paper</h2>
        {papers.length === 0 ? (
          <p>No papers yet — upload one above.</p>
        ) : (
          <select value={selectedPaper} onChange={(e) => setSelectedPaper(e.target.value)}>
            {papers.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        )}
      </div>

      <div>
        <h2>Configuration</h2>
        {config && <ConfigForm config={config} onChange={handleConfigChange} />}
      </div>

      <button
        onClick={handleStart}
        disabled={!selectedPaper || !config?.model || starting}
        style={{ padding: '0.6rem 1.2rem', fontWeight: 600, alignSelf: 'flex-start' }}
      >
        {starting ? 'Starting…' : 'Start Run'}
      </button>
      {!config?.model && <p style={{ color: '#e74c3c' }}>Set a model name before starting.</p>}
    </div>
  )
}
