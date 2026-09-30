import { AlertCircle, ArrowRight, Check, ChevronLeft, ChevronRight, Download, FileSearch, Info, Radar, ShieldCheck, X } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import type { CheckResult, ReviewStatus, Submission } from '../lib/api'

function CheckCard({ check, openFinding }: { check: CheckResult; openFinding: (id: string) => void }) {
  const tone = check.status === 'signal' ? 'signal' : check.status === 'no_signal' ? 'clear' : 'unknown'
  return <div className={`result-card ${tone}`}>
    <div className="result-card-top"><span className="rule-code">{check.rule_id}</span><span className={`result-badge ${tone}`}>{check.status === 'signal' ? 'Needs review' : check.status === 'no_signal' ? 'No signal' : 'Not evaluable'}</span></div>
    <h3>{check.title}</h3>
    <div className="result-count"><strong>{check.status === 'not_evaluable' ? '—' : check.affected_count}</strong><span>{check.status === 'not_evaluable' ? 'Insufficient evidence' : `of ${check.evaluated_count} evaluated`}</span></div>
    <p>{check.reason ?? (check.status === 'no_signal' ? 'This check found no signal in the submitted records.' : 'This pattern merits a closer look at the source evidence.')}</p>
    {check.unknown_count > 0 && <div className="result-unknown">{check.unknown_count} unknown</div>}
    {check.finding_id && <button className="result-link" onClick={() => openFinding(check.finding_id!)}>View evidence <ArrowRight size={14} /></button>}
  </div>
}

function EvidenceDrawer({ findingId, onClose }: { findingId: string; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const finding = useQuery({ queryKey: ['finding', findingId], queryFn: () => api.finding(findingId) })
  const evidence = useQuery({ queryKey: ['evidence', findingId, page], queryFn: () => api.evidence(findingId, page) })
  const [decision, setDecision] = useState<ReviewStatus>('needs_review')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<ApiError | null>(null)
  const [saved, setSaved] = useState(false)
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const dirty = Boolean(finding.data && (decision !== finding.data.review_status || note !== finding.data.review_note))

  useEffect(() => {
    if (finding.data) { setDecision(finding.data.review_status); setNote(finding.data.review_note); setSaved(false); setSaveError(null) }
  }, [finding.data?.revision, findingId])

  function requestClose() { if (dirty) setConfirmDiscard(true); else onClose() }
  async function save() {
    if (!finding.data) return
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      const updated = await api.saveReview(findingId, decision, note, finding.data.revision)
      queryClient.setQueryData(['finding', findingId], updated)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['findings'] }),
        queryClient.invalidateQueries({ queryKey: ['run'] }),
        queryClient.invalidateQueries({ queryKey: ['overview'] }),
      ])
      setSaved(true)
    } catch (issue) { setSaveError(issue instanceof ApiError ? issue : new ApiError('save_failed', 'Could not save the review. Try again.', 500)) }
    finally { setSaving(false) }
  }

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog && !dialog.open) dialog.showModal()
    return () => { if (dialog?.open) dialog.close() }
  }, [])
  useEffect(() => setPage(1), [findingId])

  return <dialog ref={dialogRef} className="evidence-dialog" aria-label="Observation and source evidence" onCancel={event => { event.preventDefault(); requestClose() }}>
    <div className="drawer-header"><div><span className="panel-overline">OBSERVATION / EVIDENCE</span><h2>{finding.data?.title ?? 'Loading observation…'}</h2></div><button className="icon-button drawer-close" aria-label="Close evidence" onClick={requestClose}><X size={19} /></button></div>
    <div className="drawer-content">
      {finding.isLoading && <div className="state-panel" role="status">Loading explanation…</div>}
      {finding.isError && <div className="state-panel error-text" role="alert">Could not load this observation. <button className="text-button" onClick={() => finding.refetch()}>Retry</button></div>}
      {finding.data && <>
        <div className="drawer-rule-strip"><span>{finding.data.rule_id} · VERSION {finding.data.rule_version}</span><span>{finding.data.affected_count} / {finding.data.evaluated_count} affected</span></div>
        <section className="drawer-section"><h3>Why this was flagged</h3><p>{finding.data.rationale}</p><div className="explanation-grid"><div><span>Evaluated</span><strong>{finding.data.evaluated_count}</strong></div><div><span>Affected</span><strong>{finding.data.affected_count}</strong></div><div><span>Unknown</span><strong>{finding.data.unknown_count}</strong></div><div><span>Excluded</span><strong>{finding.data.excluded_count}</strong></div></div>{Object.entries(finding.data.parameters).length > 0 && <p className="parameter-line">Rule parameters: {Object.entries(finding.data.parameters).map(([key, value]) => `${key.replaceAll('_', ' ')} ${value}`).join(' · ')}</p>}{finding.data.rule_id === 'MVP-NS-01' && <div className="evidence-caveat"><Info size={15} /> Alert coverage was declared {finding.data.alert_coverage}. No alert in this file does not establish a monitoring outage.</div>}</section>
        <section className="drawer-section review-editor"><div className="drawer-section-heading"><h3>Supervisor review</h3><span>Saved on this workbench</span></div><p>Record whether this observation warrants follow-up. A confirmation does not prove compromise.</p><div className="review-fields"><label htmlFor="review-decision">Decision<select id="review-decision" value={decision} onChange={event => { setDecision(event.target.value as ReviewStatus); setSaved(false) }} disabled={saving}><option value="needs_review">Needs review</option><option value="confirmed">Confirmed for follow-up</option><option value="dismissed">Dismissed</option><option value="needs_context">Needs context</option></select></label><label htmlFor="review-note">Review note <span className="optional">optional</span><textarea id="review-note" value={note} onChange={event => { setNote(event.target.value); setSaved(false) }} maxLength={2000} rows={3} placeholder="What should the next reviewer know?" disabled={saving} /></label></div>{saveError && <div className="review-error" role="alert">{saveError.message}{saveError.code === 'stale_review' && <button className="text-button" onClick={() => finding.refetch()}>Reload latest review</button>}</div>}{saved && <div className="review-saved" role="status"><Check size={15} /> Review saved</div>}<button className="button button-primary review-save" disabled={!dirty || saving} onClick={save}>{saving ? 'Saving…' : 'Save review'}</button></section>
        <section className="drawer-section"><div className="drawer-section-heading"><h3>Submitted source records</h3><span>{evidence.data?.total ?? '—'} rows</span></div>{evidence.isLoading && <p className="drawer-muted" role="status">Loading evidence…</p>}{evidence.isError && <p className="error-text" role="alert">Could not load evidence. <button className="text-button" onClick={() => evidence.refetch()}>Retry</button></p>}{evidence.data?.items.map(record => <article className="evidence-record" key={record.id}><div className="record-head"><div className="record-kind"><FileSearch size={16} /><strong>{record.source_id}</strong></div><span>{record.kind.toUpperCase()}</span></div>{record.duration_seconds != null && <div className="record-highlight">Closure duration: {Math.floor(record.duration_seconds / 60)}m {record.duration_seconds % 60}s</div>}<dl className="record-fields">{Object.entries(record.fields).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value || <em>blank</em>}</dd></div>)}</dl><div className="record-foot">{record.source_file} · data row {record.source_row} <span title={record.source_file_sha256}>SHA-256 {record.source_file_sha256.slice(0, 16)}…</span></div></article>)}{evidence.data && evidence.data.total > 25 && <div className="pagination"><button disabled={page === 1} onClick={() => setPage(page - 1)}><ChevronLeft size={15} /> Previous</button><span>Page {page} of {Math.ceil(evidence.data.total / 25)}</span><button disabled={page * 25 >= evidence.data.total} onClick={() => setPage(page + 1)}>Next <ChevronRight size={15} /></button></div>}</section>
        <section className="drawer-section provenance"><h3>Traceability</h3><p>Dataset SHA-256 <code>{finding.data.dataset_hash}</code></p><p>Rule configuration SHA-256 <code>{finding.data.config_hash}</code></p>{finding.data.history.length > 0 && <details><summary>Review history · {finding.data.history.length} change{finding.data.history.length === 1 ? '' : 's'}</summary>{finding.data.history.map(event => <div className="history-item" key={event.id}><strong>{event.new_status.replaceAll('_', ' ')}</strong><span>{event.operator_label} · {new Date(event.created_at).toLocaleString()}</span>{event.new_note && <p>{event.new_note}</p>}</div>)}</details>}</section>
      </>}
    </div>
    {confirmDiscard && <div className="discard-banner" role="alert"><strong>Unsaved review changes</strong><span>Save the review or discard your edits before closing.</span><div><button className="button button-secondary" onClick={() => setConfirmDiscard(false)}>Continue editing</button><button className="button button-primary" onClick={onClose}>Discard edits</button></div></div>}
  </dialog>
}

export default function AssessmentPanel({ runId, submission }: { runId: string; submission: Submission }) {
  const run = useQuery({ queryKey: ['run', runId], queryFn: () => api.run(runId) })
  const [ruleFilter, setRuleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const findings = useQuery({ queryKey: ['findings', runId, page, ruleFilter, statusFilter], queryFn: () => api.findings(runId, page, ruleFilter, statusFilter), enabled: run.data?.status === 'completed' })
  const [params, setParams] = useSearchParams()
  const findingId = params.get('finding')
  const lastFocus = useRef<HTMLElement | null>(null)
  function openFinding(id: string) { lastFocus.current = document.activeElement as HTMLElement; setParams({ finding: id }) }
  function closeFinding() { setParams({}) }
  useEffect(() => {
    if (!findingId && lastFocus.current) {
      const target = lastFocus.current
      requestAnimationFrame(() => { if (target.isConnected) target.focus(); lastFocus.current = null })
    }
  }, [findingId])
  async function downloadExport() {
    setExporting(true)
    setExportError('')
    try {
      const blob = await api.exportReview(runId, ruleFilter, statusFilter)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `sat-sa-review-${runId}.csv`
      document.body.append(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (issue) { setExportError(issue instanceof ApiError ? issue.message : 'Could not export the review.') }
    finally { setExporting(false) }
  }

  if (run.isLoading) return <div className="state-panel" role="status">Loading assessment…</div>
  if (run.isError || !run.data) return <div className="state-panel error-text" role="alert">Assessment could not be loaded. <button className="text-button" onClick={() => run.refetch()}>Retry</button></div>
  if (run.data.status === 'running') return <div className="state-panel" role="status">Assessment is running. <button className="text-button" onClick={() => run.refetch()}>Refresh status</button></div>
  if (run.data.status === 'failed') return <div className="state-panel error-text" role="alert"><AlertCircle size={18} /> This assessment failed. Retry from the submission header.</div>

  return <section className="assessment-section" aria-labelledby="assessment-heading">
    <div className="assessment-heading"><div><div className="eyebrow"><span className="eyebrow-rule" /> STEP 02 / EXPLAINABLE CHECKS</div><h2 id="assessment-heading">Assessment results</h2><p>Three checks evaluated the submitted records for {submission.entity_name}. Each observation links back to source evidence.</p></div><span className="assessment-version">RULESET {run.data.engine_version}</span></div>
    <div className="result-grid">{run.data.checks.map(check => <CheckCard key={check.rule_id} check={check} openFinding={openFinding} />)}</div>
    <div className="result-footnote"><Info size={15} /> Within this submission. No score or compliance grade is inferred from these checks.</div>
    <div className="finding-panel panel"><div className="panel-head"><div><div className="panel-overline">REVIEW QUEUE</div><h2>Observations</h2></div><div className="finding-actions"><span className="panel-count">{run.data.finding_count} observations</span><button className="button button-secondary export-button" onClick={downloadExport} disabled={exporting}><Download size={15} /> {exporting ? 'Exporting…' : 'Export CSV'}</button></div></div>{exportError && <div className="overview-error export-error" role="alert">{exportError}</div>}<div className="finding-toolbar"><label>Check <select value={ruleFilter} onChange={event => { setRuleFilter(event.target.value); setPage(1) }}><option value="">All checks</option>{run.data.checks.map(check => <option key={check.rule_id} value={check.rule_id}>{check.title}</option>)}</select></label><label>Review state <select value={statusFilter} onChange={event => { setStatusFilter(event.target.value); setPage(1) }}><option value="">All states</option><option value="needs_review">Needs review</option><option value="confirmed">Confirmed</option><option value="dismissed">Dismissed</option><option value="needs_context">Needs context</option></select></label></div>
      {findings.isLoading && <div className="finding-empty" role="status">Loading observations…</div>}
      {findings.isError && <div className="finding-empty error-text" role="alert">Could not load observations. <button className="text-button" onClick={() => findings.refetch()}>Retry</button></div>}
      {findings.data?.items.length === 0 && <div className="finding-empty"><div className="empty-icon">{run.data.finding_count === 0 ? <Check size={24} /> : <Radar size={24} />}</div><strong>{run.data.finding_count === 0 ? 'No signals in these checks' : 'No observations match these filters'}</strong><p>{run.data.finding_count === 0 ? 'This does not establish that the entity is secure; review the data scope and the three check definitions.' : 'Change a filter to see other observations.'}</p></div>}
      {findings.data?.items.map(item => <button key={item.id} className="finding-row" onClick={() => openFinding(item.id)}><span className="finding-indicator"><ShieldCheck size={17} /></span><span className="finding-main"><strong>{item.title}</strong><small>{item.rule_id} · {item.affected_count} of {item.evaluated_count} affected</small></span><span className="finding-status">{item.review_status.replaceAll('_', ' ')}</span><ChevronRight size={17} className="muted-icon" /></button>)}
      {findings.data && findings.data.total > 25 && <div className="pagination"><button disabled={page === 1} onClick={() => setPage(page - 1)}><ChevronLeft size={15} /> Previous</button><span>Page {page} of {Math.ceil(findings.data.total / 25)}</span><button disabled={page * 25 >= findings.data.total} onClick={() => setPage(page + 1)}>Next <ChevronRight size={15} /></button></div>}
    </div>
    {findingId && <EvidenceDrawer key={findingId} findingId={findingId} onClose={closeFinding} />}
  </section>
}
