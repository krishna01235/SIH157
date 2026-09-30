import { ArrowDownRight, ArrowRight, BarChart3, CheckCheck, ChevronRight, ClipboardCheck, DatabaseZap, FileSearch, Layers3, LockKeyhole, Menu, Radar, ShieldCheck, X } from 'lucide-react'
import { useState } from 'react'
import { Link, Route, Routes } from 'react-router-dom'

function Brand() {
  return <div className="brand"><div className="brand-symbol" aria-hidden="true"><span /><span /><span /></div><div><strong>NIGRANI<span>·</span>SA</strong><small>SOC ASSESSMENT WORKBENCH</small></div></div>
}

function AppFrame({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false)
  return <div className="app-frame">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`} aria-label="Primary navigation">
      <div className="sidebar-head"><Brand /><button className="icon-button mobile-close" aria-label="Close menu" onClick={() => setMenuOpen(false)}><X size={19} /></button></div>
      <div className="sidebar-section-label">WORKSPACE</div>
      <nav className="side-nav"><Link className="side-link active" to="/" onClick={() => setMenuOpen(false)}><BarChart3 size={18} /> Overview <span className="nav-active-dot" /></Link><a className="side-link" href="/#method" onClick={() => setMenuOpen(false)}><Layers3 size={18} /> How it works <ChevronRight size={15} className="nav-chevron" /></a></nav>
      <div className="sidebar-bottom"><div className="sidebar-info"><ShieldCheck size={18} /><div><strong>Human-led review</strong><span>Signals support judgment.</span></div></div><div className="sidebar-footer">NIGRANI-SA <span>·</span> MVP 1.0</div></div>
    </aside>
    {menuOpen && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setMenuOpen(false)} />}
    <div className="content-frame">
      <header className="topbar"><div className="topbar-left"><button className="icon-button mobile-menu" aria-label="Open menu" onClick={() => setMenuOpen(true)}><Menu size={20} /></button><span className="breadcrumb-root">Workspace</span><ChevronRight size={14} className="muted-icon" /><span className="breadcrumb-current">Overview</span></div><div className="local-badge"><span className="status-dot" /> Local workbench</div></header>
      <main id="main-content" className="page-container">{children}</main>
    </div>
  </div>
}

function Dashboard() {
  return <div className="dashboard">
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-rule" /> EVIDENCE-LED SUPERVISION</div><h1>Understand the SOC behind<br className="desktop-only" /> the numbers.</h1><p>Turn periodic alert and case records into clear, traceable observations for supervisory review.</p></div><div className="heading-mark" aria-hidden="true"><Radar size={37} strokeWidth={1.3} /></div></div>

    <section className="hero-card" aria-label="Product overview"><div className="hero-copy"><div className="hero-kicker"><span className="hero-kicker-line" /> THE PURPOSE</div><h2>From submitted evidence<br /> to better questions.</h2><p>Spot process gaps and missing signals in SOC records. Follow every observation back to its source. Keep the final decision with the reviewer.</p><div className="hero-pills"><span><DatabaseZap size={14} /> Validated evidence</span><span><FileSearch size={14} /> Explainable checks</span><span><ClipboardCheck size={14} /> Recorded review</span></div></div><div className="hero-visual" aria-hidden="true"><div className="orbit orbit-outer" /><div className="orbit orbit-middle" /><div className="orbit orbit-inner" /><div className="orbit-axis axis-h" /><div className="orbit-axis axis-v" /><div className="orbit-point point-one" /><div className="orbit-point point-two" /><div className="orbit-point point-three" /><div className="orbit-core"><ShieldCheck size={31} /></div><div className="orbit-label label-top">ALERTS</div><div className="orbit-label label-bottom">EVIDENCE</div></div></section>

    <div className="content-grid"><section className="panel submissions-panel" aria-labelledby="submissions-heading"><div className="panel-head"><div><div className="panel-overline">YOUR WORKSPACE</div><h2 id="submissions-heading">Recent submissions</h2></div><span className="panel-count">0 submissions</span></div><div className="empty-workspace"><div className="empty-icon"><DatabaseZap size={27} strokeWidth={1.5} /></div><h3>No evidence submitted yet</h3><p>Import an entity’s asset, alert, and case records to begin a review. Your submissions will appear here.</p></div></section>
    <section className="panel checks-panel" aria-labelledby="checks-heading"><div className="panel-head"><div><div className="panel-overline">INCLUDED IN THIS MVP</div><h2 id="checks-heading">What the checks look for</h2></div><ArrowDownRight size={21} className="muted-icon" /></div><div className="check-preview"><div className="check-preview-row"><div className="check-icon amber"><CheckCheck size={18} /></div><div><strong>Very fast case closure</strong><span>High-severity cases closed in under five minutes.</span></div></div><div className="check-preview-row"><div className="check-icon blue"><FileSearch size={18} /></div><div><strong>No recorded investigation</strong><span>Closed cases with a submitted count of zero.</span></div></div><div className="check-preview-row"><div className="check-icon teal"><Radar size={18} /></div><div><strong>Critical assets with no alerts</strong><span>Evaluated only for complete alert exports.</span></div></div></div><div className="checks-footnote"><LockKeyhole size={14} /> Observations are prompts for review, not findings of compromise.</div></section></div>

    <section id="method" className="method-section" aria-labelledby="method-heading"><div className="method-heading"><div><div className="eyebrow"><span className="eyebrow-rule" /> A SIMPLE WORKFLOW</div><h2 id="method-heading">How an assessment works</h2></div><span>01 / 03</span></div><div className="step-grid"><div className="step-card"><span className="step-number">01</span><div className="step-icon"><DatabaseZap size={22} /></div><h3>Submit the evidence</h3><p>Load the three CSV exports for one entity and reporting period. Errors are shown before data is saved.</p><ArrowRight size={18} className="step-arrow" /></div><div className="step-card"><span className="step-number">02</span><div className="step-icon"><FileSearch size={22} /></div><h3>Review the signals</h3><p>Run transparent checks and see who or what contributed to each observation.</p><ArrowRight size={18} className="step-arrow" /></div><div className="step-card"><span className="step-number">03</span><div className="step-icon"><ClipboardCheck size={22} /></div><h3>Record your judgment</h3><p>Open source records, save a decision, and export a traceable review.</p><ArrowRight size={18} className="step-arrow" /></div></div></section>
    <footer className="page-footer"><span>NIGRANI-SA</span><span>Evidence first. Judgment stays human.</span></footer>
  </div>
}

export default function App() { return <AppFrame><Routes><Route path="*" element={<Dashboard />} /></Routes></AppFrame> }
