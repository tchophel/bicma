import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api";
import { Icon, type IconName } from "../../components/Icon";
import css from "../../styles/Home.module.css";

const STEPS: { icon: IconName; title: string; text: string; ok?: boolean }[] = [
  { icon: "edit", title: "Submit", text: "Lodge your complaint online or through BICMA officials." },
  { icon: "search", title: "Track", text: "Use your reference number to check the status." },
  { icon: "gear", title: "Process", text: "BICMA reviews, investigates and takes necessary action." },
  { icon: "check", title: "Resolution", text: "Receive the final decision and communication.", ok: true },
];
const READY: { icon: IconName; title: string; text: string }[] = [
  { icon: "user", title: "Your contact details", text: "Have your CID, phone number and email ready." },
  { icon: "category", title: "The right category", text: "Choose the closest match so your complaint reaches the right division." },
  { icon: "complaint", title: "What happened", text: "Include the place, key details and the outcome you’re looking for." },
  { icon: "plus", title: "Supporting documents", text: "Have bills, screenshots or letters ready, if available." },
];
const SERVICES = ["Telecommunications", "Internet", "Cable television", "Broadcasting", "Online media"];

type Stats = { total: number; resolved: number; pending: number; not_within_mandate: number };

/** Counts up from 0 to the value, unless the visitor prefers reduced motion. */
function useCount(target: number) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || target === 0) { setN(target); return; }
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / 900);
      setN(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return n;
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  const n = useCount(value);
  return (
    <div className={`${css.stat} ${css[tone]}`}>
      <strong aria-label={`${value} ${label}`}>{n.toLocaleString()}</strong><span>{label}</span>
    </div>
  );
}

export function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => { api<Stats>("/public/stats/").then(setStats).catch(() => setStats(null)); }, []);
  const rate = stats && stats.total ? Math.round((stats.resolved / stats.total) * 100) : 0;
  const nav = useNavigate();
  const [ref, setRef] = useState("");
  function quickTrack(e: FormEvent) {
    e.preventDefault();
    nav(ref.trim() ? `/track?ref=${encodeURIComponent(ref.trim())}&send=1` : "/track");  // send=1: the Track page emails the code at once
  }
  return (
    <>
      <section className={css.hero}>
        <div className={css.art} aria-hidden="true" />
        <div className={css.inner}>
          <div className={css.copy}>
            <span className={css.eyebrow}><i />Bhutan InfoComm and Media Authority</span>
            <h1 className={css.title}>BICMA <span>Complaint Portal</span></h1>
            <p className={css.lead}>Register and track complaints on telecommunications, internet, cable television, broadcasting and online media services in Bhutan.</p>
            <div className={css.actions}>
              <Link to="/submit" className={css.btnYellow}><Icon name="plus" size={20} />Submit a Complaint</Link>
              <Link to="/track" className={css.btnGlass}><Icon name="search" size={20} />Track a Complaint</Link>
            </div>
          </div>
          <form className={css.quick} onSubmit={quickTrack} aria-labelledby="quick-title">
            <span className={css.quickIcon}><Icon name="search" size={22} /></span>
            <h2 id="quick-title">Track your complaint</h2>
            <p>Use your reference number or CID to check the status. We will email you a code.</p>
            <label className="sr-only" htmlFor="quick-ref">Reference number or CID</label>
            <div className={css.quickRow}>
              <input id="quick-ref" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="Reference number or CID" autoComplete="off" />
              <button type="submit" aria-label="Track and send me a code"><Icon name="right" size={20} /></button>
            </div>
            {stats && (
              <div className={css.glance} aria-labelledby="glance">
                <div className={css.glanceHead}>
                  <div><span className={css.kicker}>Complaints at a glance</span><h3 id="glance">What BICMA has received</h3></div>
                  <span className={css.rate}><b>{rate}%</b> resolved</span>
                </div>
                <div className={css.stats}>
                  <Stat label="Total" value={stats.total} tone="tTotal" />
                  <Stat label="Resolved" value={stats.resolved} tone="tDone" />
                  <Stat label="Pending" value={stats.pending} tone="tWait" />
                </div>
                <div className={css.bar} role="img" aria-label={`${rate} percent resolved`}><i style={{ width: `${rate}%` }} /></div>
                {stats.not_within_mandate > 0 && <p className={css.note}>{stats.not_within_mandate} outside BICMA&apos;s jurisdiction, not counted above.</p>}
              </div>
            )}
          </form>
        </div>
        <svg className={css.wave} viewBox="0 0 1440 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0 90V48C180 8 360 8 540 40s360 40 540 12 260-34 360-14V90Z" fill="#fcf6f1" /></svg>
      </section>

      <div className={css.wrap}>
        <section className={css.steps4} aria-label="Process overview">
          {STEPS.map((f, i) => (
            <div className={css.step} key={f.title} style={{ animationDelay: `${i * 90}ms` }}>
              <span className={`${css.stepIcon} ${f.ok ? css.ok : ""}`}><Icon name={f.icon} size={30} /></span>
              <span className={css.stepNo}>0{i + 1}</span>
              <h3>{f.title}</h3>
              <p>{f.text}</p>
            </div>
          ))}
        </section>

        <section className={css.services} aria-label="Services covered">
          <span>We handle complaints about</span>
          <ul>{SERVICES.map((s) => <li key={s}>{s}</li>)}</ul>
        </section>

        <section className={css.ready} aria-labelledby="ready">
          <div className={css.readyHead}>
            <div><span className={css.kicker}>Get ready</span><h2 id="ready">Before you start</h2></div>
            <Link to="/submit" className={css.readyBtn}><Icon name="plus" size={18} />Start complaint<Icon name="right" size={16} /></Link>
          </div>
          <ul className={css.readyGrid}>
            {READY.map((r, i) => (
              <li key={r.title} className={css[`r${i}`]}>
                <span><Icon name={r.icon} size={22} /></span>
                <div><strong>{r.title}</strong><p>{r.text}</p></div>
              </li>
            ))}
          </ul>
        </section>

        <div className={css.lower}>
          <section className={css.panel} aria-labelledby="how">
            <span className={css.kicker}>Simple and transparent</span>
            <h2 id="how">How It Works</h2>
            <ol className={css.timeline}>
              <li><span className={css.num}>1</span><p>Submit your complaint and receive a reference number.</p></li>
              <li><span className={css.num}>2</span><p>BICMA screens it and assigns it to the responsible division.</p></li>
              <li><span className={css.num}>3</span><p>Use your reference number to check its status at any time.</p></li>
            </ol>
          </section>
          <aside className={`${css.panel} ${css.help}`} aria-labelledby="help">
            <span className={css.helpIcon}><Icon name="help" size={28} /></span>
            <h2 id="help">Need Help?</h2>
            <Link to="/track" className={css.link}><Icon name="search" /><span>Track your complaint</span><Icon name="chev" /></Link>
            <Link to="/submit" className={css.link}><Icon name="edit" /><span>Submit a complaint</span><Icon name="chev" /></Link>
          </aside>
        </div>
      </div>
    </>
  );
}
