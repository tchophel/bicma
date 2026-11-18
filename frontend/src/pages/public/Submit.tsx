import { Link, useLocation, useNavigate } from "react-router-dom";
import { ComplaintForm, type FormResult } from "../../components/ComplaintForm";
import { Icon } from "../../components/Icon";
import "./Submit.css";

export function Submit() {
  const nav = useNavigate();
  return (
    <div className="container submit-page">
      <header className="submit-hero">
        <span className="submit-eyebrow"><Icon name="complaint" size={16} />BICMA COMPLAINT PORTAL</span>
        <h1>Submit a complaint</h1>
        <p>Tell us what happened. It takes a few minutes.</p>
      </header>
      <div className="submit-layout">
        <ComplaintForm offline={false} onDone={(r) => nav("/submitted", { state: r, replace: true })} />
        <aside className="submit-guide" aria-label="Submission guidance">
          <section className="card"><span className="icon-tile"><Icon name="edit" size={20} /></span><h2>Before you submit</h2><ul><li>Have your CID, phone number and email ready.</li><li>Choose the category that fits best; it decides which BICMA division handles it.</li><li>Include the date, time and place, and what outcome you want.</li><li>Attach bills, screenshots or letters if you have them.</li></ul></section>
          <section className="submit-next"><h2>What happens next?</h2><ol><li><span>1</span><div><strong>Verify and submit</strong><p>Complete a short security check.</p></div></li><li><span>2</span><div><strong>Save your reference</strong><p>You’ll receive a reference number on screen and by email.</p></div></li><li><span>3</span><div><strong>Follow its progress</strong><p>Use your reference on the tracking page.</p></div></li></ol></section>
        </aside>
      </div>
    </div>
  );
}

export function Submitted() {
  const r = useLocation().state as FormResult | null;
  if (!r) return <div className="container"><p>Nothing to show. <Link to="/submit"><Icon name="plus" />Submit a complaint</Link>.</p></div>;
  return (
    <div className="container">
      <div className="card success-hero" style={{ padding: 32 }}>
        <span className="icon-tile lg" aria-hidden="true"><Icon name="check" size={32} /></span>
        <h1 style={{ marginBottom: 6 }}>Complaint received</h1>
        <p className="muted" style={{ marginTop: 0 }}>Thank you. Your complaint has been registered. Your reference number is:</p>
        <div className="ref-big">{r.reference}</div>
        <p className="notice" style={{ textAlign: "left" }}><strong>Keep your reference number.</strong> Use it on the Track page to check progress at any time.</p>
        <Link className="btn" to="/track" state={{ reference: r.reference }}><Icon name="search" />Track this complaint</Link>
      </div>
    </div>
  );
}
