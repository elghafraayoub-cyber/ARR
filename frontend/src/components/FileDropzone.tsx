import { useRef, useState } from 'react'

export function FileDropzone({ onUpload }: { onUpload: (file: File) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) onUpload(file)
      }}
      onClick={() => inputRef.current?.click()}
      style={{
        border: `2px dashed ${dragging ? '#4a9eff' : '#888'}`,
        borderRadius: 8,
        padding: '2rem',
        textAlign: 'center',
        cursor: 'pointer',
        background: dragging ? '#f0f7ff' : 'transparent',
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.md"
        style={{ display: 'none' }}
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onUpload(file)
          e.target.value = ''
        }}
      />
      <p>Drag &amp; drop a paper here (.pdf / .txt / .md), or click to browse.</p>
    </div>
  )
}
