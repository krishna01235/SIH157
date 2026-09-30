import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, Clock3, FileSpreadsheet, Info, ShieldCheck, UploadCloud } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import type { Coverage } from '../lib/api'

const kinds = ['assets', 'alerts', 'cases'] as const
const fileNames = { assets: 'Asset inventory', alerts: 'Security alerts', cases: 'Case records' }

export default function ImportPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const entities = useQuery({ queryKey: ['entities'], queryFn: api.entities })
  const [selectedEntity, setSelectedEntity] = useState('new')
  const [entityName, setEntityName] = useState('')
  const [sector, setSector] = useState('')
  const [label, setLabel] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [coverage, setCoverage] = useState<Coverage>('unknown')
  const [coverageAck, setCoverageAck] = useState(false)
  const [files, setFiles] = useState<Partial<Record<typeof kinds[number], File>>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!kinds.every(kind => files[kind])) { setError(new ApiError('missing_files', 'Select all three CSV files.', 422)); return }
    if (start && end && new Date(`${end}T00:00:00Z`) <= new Date(`${start}T00:00:00Z`)) { setError(new ApiError('invalid_period', 'The end date must follow the start date.', 422)); return }
    setBusy(true)
    try {
      let entityId = selectedEntity
      if (selectedEntity === 'new') {
        try { entityId = (await api.createEntity(entityName, sector)).id }
        catch (issue) {
          if (issue instanceof ApiError && issue.code === 'entity_exists' && issue.details[0]?.existing_id) entityId = issue.details[0].existing_id
          else throw issue
        }
        setSelectedEntity(entityId)
      }
      const data = new FormData()
      data.set('entity_id', entityId)
      data.set('period_start', `${start}T00:00:00Z`)
      data.set('period_end', `${end}T00:00:00Z`)
      data.set('alert_coverage', coverage)
      data.set('coverage_ack', String(coverageAck))
      if (label.trim()) data.set('label', label.trim())
      for (const kind of kinds) data.set(kind, files[kind]!)
      const saved = await api.importSubmission(data)
      await Promise.all([queryClient.invalidateQueries({ queryKey: ['overview'] }), queryClient.invalidateQueries({ queryKey: ['submissions'] }), queryClient.invalidateQueries({ queryKey: ['entities'] })])
      navigate(`/submissions/${saved.id}`, { state: { imported: true, reused: saved.reused } })
    } catch (issue) { setError(issue instanceof ApiError ? issue : new ApiError('unexpected', 'The submission could not be imported. Try again.', 500)) }
    finally { setBusy(false) }
  }

  return <div className="flow-page">
    <Link to="/" className="back-link"><ArrowLeft size={15} /> Back to overview</Link>
    <div className="flow-heading"><div><div className="eyebrow"><span className="eyebrow-rule" /> STEP 01 / SUBMIT EVIDENCE</div><h1>New submission</h1><p>Load operational records for one entity and reporting period. We validate every row before saving.</p></div><div className="heading-mark" aria-hidden="true"><UploadCloud size={32} /></div></div>
    <form onSubmit={submit} className="form-grid">
      <div className="form-main">
        <section className="form-panel"><div className="form-panel-head"><span className="form-section-number">01</span><div><h2>Entity & reporting window</h2><p>Define whose records these are and when they were collected.</p></div></div><div className="form-panel-body"><div className="field"><label htmlFor="entity">Critical sector entity</label><select id="entity" value={selectedEntity} onChange={event => setSelectedEntity(event.target.value)} disabled={busy}><option value="new">+ Add a new entity</option>{entities.data?.map(entity => <option key={entity.id} value={entity.id}>{entity.name}</option>)}</select>{entities.isError && <span className="field-help error-text">Could not load saved entities. You can still add a new one.</span>}</div>{selectedEntity === 'new' && <div className="field-row"><div className="field"><label htmlFor="entity-name">Entity name</label><input id="entity-name" required maxLength={120} value={entityName} onChange={event => setEntityName(event.target.value)} placeholder="e.g. North Grid Operations" disabled={busy} /></div><div className="field"><label htmlFor="sector">Sector <span className="optional">optional</span></label><input id="sector" maxLength={80} value={sector} onChange={event => setSector(event.target.value)} placeholder="e.g. Power" disabled={busy} /></div></div>}<div className="field"><label htmlFor="submission-label">Submission label <span className="optional">optional</span></label><input id="submission-label" maxLength={120} value={label} onChange={event => setLabel(event.target.value)} placeholder="e.g. January review batch" disabled={busy} /></div><div className="field-row"><div className="field"><label htmlFor="period-start">Start date · UTC</label><input id="period-start" type="date" required value={start} onChange={event => setStart(event.target.value)} disabled={busy} /></div><div className="field"><label htmlFor="period-end">End date · UTC <span className="optional">exclusive</span></label><input id="period-end" type="date" required value={end} onChange={event => setEnd(event.target.value)} disabled={busy} /></div></div><div className="inline-note"><Clock3 size={16} /><span>Use a window of 1–90 days. The end date is not included.</span></div></div></section>
        <section className="form-panel"><div className="form-panel-head"><span className="form-section-number">02</span><div><h2>CSV evidence</h2><p>Upload one file of each type. The files are stored together with their source hashes.</p></div></div><div className="form-panel-body"><div className="upload-grid">{kinds.map(kind => <div className="upload-card" key={kind}><div className="upload-card-top"><span className="upload-icon"><FileSpreadsheet size={19} /></span><span className="upload-step">{kind.toUpperCase()}</span></div><strong>{fileNames[kind]}</strong><span className="upload-filename">{files[kind]?.name ?? 'No file selected'}</span><label htmlFor={`file-${kind}`} className="file-picker">{files[kind] ? 'Change file' : 'Choose CSV'}<input id={`file-${kind}`} type="file" accept=".csv,text/csv" required={!files[kind]} onChange={event => setFiles(previous => ({ ...previous, [kind]: event.target.files?.[0] }))} disabled={busy} /></label><a href={`/templates/${kind}.csv`} download={`${kind}.csv`} className="template-link">Download template <ArrowRight size={12} /></a></div>)}</div><div className="inline-note"><Info size={16} /><span>UTF-8 CSV only, up to 10 MiB and 10,000 combined rows. Source files stay on this installation.</span></div></div></section>
        <section className="form-panel"><div className="form-panel-head"><span className="form-section-number">03</span><div><h2>Alert export coverage</h2><p>Tell us whether the submitted alert file covers the entire declared window.</p></div></div><div className="form-panel-body"><div className="coverage-options">{([['unknown', 'Unknown', 'Completeness has not been established.'], ['sample', 'Sample', 'Only a subset of alerts is included.'], ['complete', 'Complete', 'All alerts for in-scope assets and the full window.']] as const).map(([value, title, description]) => <label className={`coverage-option ${coverage === value ? 'selected' : ''}`} key={value}><input type="radio" name="coverage" value={value} checked={coverage === value} onChange={() => setCoverage(value)} disabled={busy} /><span><strong>{title}</strong><small>{description}</small></span></label>)}</div>{coverage === 'complete' && <label className="acknowledgement"><input type="checkbox" checked={coverageAck} onChange={event => setCoverageAck(event.target.checked)} required disabled={busy} /><span>I confirm this export includes all alerts for the declared assets and window.</span></label>}<div className="inline-note"><ShieldCheck size={16} /><span>The critical-asset absence check runs only for a complete export. Completeness cannot be inferred from the number of rows.</span></div></div></section>
        {error && <div className="error-banner" role="alert"><AlertCircle size={19} /><div><strong>{error.message}</strong>{error.details.length > 0 && <ul>{error.details.map((detail, index) => <li key={index}>{detail.file ? `${detail.file}${detail.row != null ? `, row ${detail.row}` : ''}: ` : ''}{detail.field ? `${detail.field} — ` : ''}{detail.message}</li>)}</ul>}</div></div>}
        <div className="form-actions"><Link to="/" className="button button-secondary">Cancel</Link><button type="submit" className="button button-primary" disabled={busy}>{busy ? 'Validating & importing…' : 'Import submission'} <ArrowRight size={16} /></button></div>
      </div>
      <aside className="form-aside"><div className="aside-card"><div className="aside-icon"><CheckCircle2 size={20} /></div><h3>Before you import</h3><ol><li>Use the exact CSV template headers.</li><li>Keep source IDs unique within each file.</li><li>Include timezone offsets in timestamps.</li><li>Leave unknown investigation counts blank.</li></ol><a href="/templates/assets.csv" download className="aside-link">Start with a template <ArrowRight size={14} /></a></div><div className="aside-small">This tool raises observations for a human reviewer. It does not certify SOC effectiveness or judge individual alerts.</div></aside>
    </form>
  </div>
}
