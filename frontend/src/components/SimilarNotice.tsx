import { Icon } from "./Icon";

export type SimilarInfo = {
  similar: number; days?: number; latest_days_ago?: number; resolved?: number; in_progress?: number;
  about?: string; provider?: string; dzongkhag?: string; topics?: { label: string; count: number }[];
};

const when = (d: number) => (d === 0 ? "today" : d === 1 ? "yesterday" : `${d} days ago`);

/** Tells a complainant that others reported the same issue, with a short summary: numbers, timing, status and places. Never any text from the complaints. */
export function SimilarNotice({ info, submitted = false, showEmpty = false }: { info: SimilarInfo; submitted?: boolean; showEmpty?: boolean }) {
  const n = info.similar;
  if (!n) return showEmpty ? (
    <div className="similar-notice no-matches" role="status" aria-live="polite">
      <span><Icon name="check" size={22} /></span>
      <div><strong>No similar complaints found</strong><p>No recent reports match the category and provider/platform details you selected in the last {info.days ?? 90} days. This check does not compare your description text. You can continue with your complaint.</p></div>
    </div>
  ) : null;
  const many = n >= 10;
  const where = info.dzongkhag ? ` in ${info.dzongkhag}` : "";
  const did = submitted ? "" : "already ";
  const title = many ? `Many people (${n})${where} have ${did}reported the same issue`
    : n === 1 ? `1 other person${where} has ${did}reported a similar issue` : `${n} other people${where} have ${did}reported a similar issue`;
  const about = [info.about, info.provider].filter(Boolean).join(" · ");
  const facts: string[] = [];
  if (info.latest_days_ago !== undefined) facts.push(`Latest report: ${when(info.latest_days_ago)}`);
  if (info.resolved !== undefined && info.in_progress !== undefined) {
    const parts = [info.in_progress ? `${info.in_progress} being handled` : "", info.resolved ? `${info.resolved} resolved` : ""].filter(Boolean);
    if (parts.length) facts.push(parts.join(", "));
  }
  return (
    <div className={`similar-notice ${many ? "many" : ""}`} role="status" aria-live="polite">
      <span><Icon name={many ? "alert" : "users"} size={22} /></span>
      <div>
        {showEmpty && <span className="similar-result-label">Possible similar complaints found</span>}
        <strong>{title}</strong>
        {showEmpty && <p>Based on your selected category and provider/platform details from the last {info.days ?? 90} days. This check does not compare your description text.</p>}
        <div className="similar-complaint-summary">
          <h4><Icon name="complaint" size={16} />{n === 1 ? "What the other complaint is about" : "What the other complaints are about"}</h4>
          {about && <p>{about}{info.dzongkhag ? ` · ${info.dzongkhag}` : ""}</p>}
          {!!info.topics?.length
            ? <ul aria-label="Reported issues">{info.topics.map((t) => <li key={t.label}>{t.label}{n > 1 ? ` (${t.count} ${t.count === 1 ? "report" : "reports"})` : ""}</li>)}</ul>
            : <p className="similar-summary-note">{about ? "No specific issue options were recorded for these reports." : "A detailed summary is not available for these reports."}</p>}
          <small>Summary from selected complaint options. Personal details and written descriptions are private.</small>
        </div>
        {facts.length > 0 && <ul className="similar-facts" aria-label={`Summary, last ${info.days ?? 90} days`}>{facts.map((f) => <li key={f}>{f}</li>)}</ul>}
        <p>{many ? "BICMA is aware this affects many people. " : ""}{submitted ? "You do not need to submit again. " : "You can still submit your own complaint. "}BICMA can see similar complaints together and may handle them as one.</p>
      </div>
    </div>
  );
}
