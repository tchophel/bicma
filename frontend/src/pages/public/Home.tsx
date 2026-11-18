import { Link } from "react-router-dom";
import { Icon, type IconName } from "../../components/Icon";
import css from "../../styles/Home.module.css";

export function Home() {
  const features: { icon: IconName; title: string; text: string; ok?: boolean }[] = [
    { icon: "edit", title: "Submit", text: "Lodge your complaint online or through BICMA officials." },
    { icon: "search", title: "Track", text: "Use your reference number to check the status." },
    { icon: "gear", title: "Process", text: "BICMA reviews, investigates and takes necessary action." },
    { icon: "check", title: "Resolution", text: "Receive the final decision and communication.", ok: true },
  ];
  return (
    <>
      <section className={css.hero}>
        <div className={css.art} aria-hidden="true" />
        <div className={css.inner}>
          <h1 className={css.title}>BICMA <span>Complaint Portal</span></h1>
          <p className={css.lead}>Register and track complaints on telecommunications, internet, cable television, broadcasting and online media services in Bhutan.</p>
          <div className={css.rule} />
          <div className={css.actions}>
            <Link to="/submit" className={css.btnYellow}><Icon name="plus" size={20} />Submit a Complaint</Link>
            <Link to="/track" className={css.btnOutline}><Icon name="search" size={20} />Track a Complaint</Link>
          </div>
        </div>
      </section>
      <div className={css.wrap}>
        <section className={css.features} aria-label="Process overview">
          {features.map((f) => (
            <div className={css.feature} key={f.title}>
              <span className={`${css.fIcon} ${f.ok ? css.ok : ""}`}><Icon name={f.icon} size={48} /></span>
              <div><h3>{f.title}</h3><p>{f.text}</p></div>
            </div>
          ))}
        </section>
        <div className={css.lower}>
          <section className={css.panel} aria-labelledby="how">
            <h2 id="how">How It Works</h2>
            <ol className={css.steps}>
              <li><span className={css.num}>1</span>Submit your complaint and receive a reference number.</li>
              <li><span className={css.num}>2</span>BICMA screens it and assigns it to the responsible division.</li>
              <li><span className={css.num}>3</span>Use your reference number to check its status at any time.</li>
            </ol>
            <svg className={css.hills} viewBox="0 0 400 120" aria-hidden="true"><path d="M0 120 0 85 70 55 140 80 220 40 300 75 400 50V120Z" fill="#9db9d8" /><path d="M0 120 0 100 90 80 180 100 270 70 400 95V120Z" fill="#7d9fc6" /></svg>
          </section>
          <aside className={css.panel} aria-labelledby="help">
            <div className={css.helpHead} id="help"><Icon name="help" size={28} />Need Help?</div>
            <Link to="/track" className={css.link}><Icon name="search" /><span>Track your complaint</span><Icon name="chev" /></Link>
            <Link to="/submit" className={css.link}><Icon name="edit" /><span>Submit a complaint</span><Icon name="chev" /></Link>
          </aside>
        </div>
      </div>
    </>
  );
}
