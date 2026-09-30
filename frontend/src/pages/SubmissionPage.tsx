import { AlertCircle, ArrowLeft, CheckCircle2, FileSpreadsheet, Layers3 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api, formatWindow } from '../lib/api'

export default function SubmissionPage() {
  const { id = '' } = useParams()
  const location = useLocation()
  const query = useQuery({ queryKey: ['submission', id], queryFn: () => api.submission(id), enabled: Boolean(id) })
  if (query.isLoading) return <div className="state-panel" role="status">Loading submission…</div>
  if (query.isError || !query.data) return <div className="state-panel error-text" role="alert">Could not load this submission. <button className="text-button" onClick={() => query.refetch()}>Retry</button></div>
  const submission = query.data
  const imported = Boolean((location.state as { imported?: boolean } | null)?.imported)
  const reused = Boolean((location.state as { reused?: boolean } | null)?.reused)
  return <div className="flow-page">
    <Link to="/" className="back-link"><ArrowLeft size={15} /> Back to overview</Link>
    <div className="flow-heading"><div><div className="eyebrow"><span className="eyebrow-rule" /> SUBMISSION / EVIDENCE</div><h1>{submission.entity_name}</h1><p>{submission.label || 'SOC evidence submission'} · {formatWindow(submission.period_start, submission.period_end)}</p></div><div className="heading-mark" aria-hidden="true"><Layers3 size={32} /></div></div>
    {imported && <div className="success-banner" role="status"><CheckCircle2 size={19} /> {reused ? 'Identical evidence was already saved. Opened the existing submission.' : 'Evidence validated and stored successfully.'}</div>}
    {submission.synthetic && <div className="synthetic-banner">Synthetic example · No real operational data</div>}
    <div className="stat-grid"><div className="stat-card"><span>Assets</span><strong>{submission.validation_summary.row_counts.assets}</strong><small>Inventory rows</small></div><div className="stat-card"><span>Alerts</span><strong>{submission.validation_summary.row_counts.alerts}</strong><small>Submitted events</small></div><div className="stat-card"><span>Cases</span><strong>{submission.validation_summary.row_counts.cases}</strong><small>Case records</small></div><div className="stat-card"><span>Alert coverage</span><strong className="stat-word">{submission.alert_coverage}</strong><small>User declaration</small></div></div>
    <div className="detail-grid"><section className="panel"><div className="panel-head"><div><div className="panel-overline">VALIDATED INPUTS</div><h2>Source files</h2></div></div><div className="file-list">{submission.source_files.map(source => <div className="file-row" key={source.kind}><div className="file-row-icon"><FileSpreadsheet size={19} /></div><div><strong>{source.display_name}</strong><span>{source.kind} · {source.row_count} rows · SHA-256 {source.sha256.slice(0, 14)}…</span></div></div>)}</div></section><section className="panel"><div className="panel-head"><div><div className="panel-overline">ASSESSMENT READINESS</div><h2>Validation summary</h2></div></div><div className="detail-copy"><p>The three files passed schema, timestamp, and reference checks. The assessment will use this exact submitted dataset.</p>{submission.validation_summary.warnings.length ? <div className="warning-list"><AlertCircle size={17} /><div>{submission.validation_summary.warnings.map(warning => <p key={warning}>{warning}</p>)}</div></div> : <div className="inline-note"><CheckCircle2 size={16} /> No informational warnings.</div>}<div className="coverage-note"><strong>Coverage: {submission.alert_coverage}</strong><span>{submission.alert_coverage === 'complete' ? 'The absence check may evaluate in-scope critical assets.' : 'The absence check cannot evaluate sampled or unknown coverage.'}</span></div></div></section></div>
    <div className="next-step-note"><Layers3 size={20} /><div><strong>Evidence ready for assessment</strong><p>This submission is saved. Assessment checks will appear here when that milestone is connected.</p></div></div>
  </div>
}
