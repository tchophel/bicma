import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ComplaintForm, type FormResult } from "../../components/ComplaintForm";
import { Icon } from "../../components/Icon";
import { SimilarNotice } from "../../components/SimilarNotice";
import "../../styles/Submit.css";

export function Submit() {
  const nav = useNavigate();
  return (
    <div className="container submit-page">
      <header className="submit-hero">
        <div className="submit-hero-copy">
          <span className="submit-eyebrow"><Icon name="complaint" size={16} />BICMA COMPLAINT PORTAL</span>
          <h1>Tell us what happened.</h1>
          <p>Submit a complaint and follow its progress, all in one place.</p>
          <div className="submit-hero-facts"><span><Icon name="clock" size={16} />Takes a few minutes</span><span><Icon name="lock" size={16} />Your details help us process your complaint</span></div>
        </div>
        <div className="submit-track-card"><span className="icon-tile"><Icon name="search" size={22} /></span><div><strong>Already submitted a complaint?</strong><p>Check the progress using your reference number.</p><Link to="/track">Track your complaint<Icon name="right" size={16} /></Link></div></div>
      </header>
      <div className="submit-layout">
        <ComplaintForm offline={false} onDone={(r) => nav("/submitted", { state: r, replace: true })} />
        <aside className="submit-guide" aria-label="Submission guidance">
          <section className="card submit-checklist">
            <div className="submit-checklist-heading"><span className="icon-tile"><Icon name="edit" size={20} /></span><div><span className="submit-small-label">GET READY</span><h2>Before you start</h2></div></div>
            <ul>
              <li><Icon name="user" size={18} /><div><strong>Your contact details</strong><p>Have your CID, phone number and email ready.</p></div></li>
              <li><Icon name="category" size={18} /><div><strong>The right category</strong><p>Choose the closest match so your complaint reaches the right division.</p></div></li>
              <li><Icon name="complaint" size={18} /><div><strong>What happened</strong><p>Include the place, key details and the outcome you’re looking for.</p></div></li>
              <li><Icon name="plus" size={18} /><div><strong>Supporting documents</strong><p>Have bills, screenshots or letters ready, if available.</p></div></li>
            </ul>
          </section>
        </aside>
      </div>
      <section className="submit-next" aria-label="After you submit"><div className="submit-next-heading"><span className="submit-small-label">A SIMPLE PROCESS</span><h2>What happens next?</h2></div><ol><li><span><Icon name="check" size={19} /></span><div><small>STEP 01</small><strong>Verify and submit</strong><p>Complete a short security check to send your complaint.</p></div></li><li><span><Icon name="mail" size={19} /></span><div><small>STEP 02</small><strong>Save your reference</strong><p>Your reference appears on screen and is sent to the email you provide.</p></div></li><li><span><Icon name="search" size={19} /></span><div><small>STEP 03</small><strong>Follow its progress</strong><p>Use your reference on the <Link to="/track">tracking page</Link> to check for updates.</p></div></li></ol></section>
    </div>
  );
}

export function Submitted() {
  const r = useLocation().state as FormResult | null;
  const [copied, setCopied] = useState(false);
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* the reference is also shown as text to select */ }
  }
  if (!r) return <div className="container"><p>Nothing to show. <Link to="/submit"><Icon name="plus" />Submit a complaint</Link>.</p></div>;
  return (
    <div className="container submitted-page">
      <div className="card success-hero" role="status">
        <div className="submission-celebration" aria-hidden="true">
          <img className="submission-watermark" src="/bicma-logo.png" alt="" />
          <span className="submission-spark spark-one" /><span className="submission-spark spark-two" /><span className="submission-spark spark-three" /><span className="submission-spark spark-four" />
          <svg viewBox="0 0 100 100" fill="none"><circle className="submission-ring" cx="50" cy="50" r="38" /><path className="submission-check" d="m30 50 14 14 27-30" /></svg>
        </div>
        <p className="submission-thanks">Thank you!</p>
        <h1 style={{ marginBottom: 6 }}>Complaint received</h1>
        <p className="muted" style={{ marginTop: 0 }}>Your complaint has been registered. Your reference number is:</p>
        <div className="ref-ticket">
          <span className="ref-ticket-label">YOUR COMPLAINT NUMBER</span>
          <strong className="ref-ticket-number" aria-label={`Complaint number ${r.reference.split("-").pop()}`}>{r.reference.split("-").pop()}</strong>
          <div className="ref-ticket-full">
            <span>Full reference for tracking: <b>{r.reference}</b></span>
            <button type="button" onClick={() => void copy(r.reference)}><Icon name={copied ? "check" : "expand"} size={15} />{copied ? "Copied" : "Copy"}</button>
          </div>
        </div>
        {!!r.similar && <SimilarNotice info={{ ...r, similar: r.similar }} submitted />}
        <p className="notice" style={{ textAlign: "left" }}><strong>Keep your reference number.</strong> Use it on the Track page to check progress at any time.</p>
        <Link className="btn" to="/track" state={{ reference: r.reference }}><Icon name="search" />Track this complaint</Link>
      </div>
    </div>
  );
}
