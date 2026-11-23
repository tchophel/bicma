import { useState } from "react";
import { Modal } from "./Modal";
import { Icon } from "./Icon";

const IMAGES = ["jpg", "jpeg", "png", "gif", "webp"];
// Shown in a frame: PDFs by the browser, Word files as a converted page, text as plain text
const FRAMED = ["pdf", "docx", "txt", "csv"];
const ext = (name: string) => (name.includes(".") ? name.split(".").pop()!.toLowerCase() : "");

/** A file on the case page. Images and PDFs open in a preview window on the page (view only); other types download. */
export function FileLink({ href, name, icon = false }: { href: string; name: string; icon?: boolean }) {
  const [open, setOpen] = useState(false);
  const e = ext(name);
  const label = <>{icon && <Icon name="complaint" size={14} />} {name}</>;
  if (!IMAGES.includes(e) && !FRAMED.includes(e)) return <a href={href} title={name}>{label}</a>;
  const src = `${href}?view=1`;
  const show = (ev: { preventDefault: () => void }) => { ev.preventDefault(); setOpen(true); };
  return (
    <>
      <span className="file-link" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <a href={src} title={name} onClick={show}>{label}</a>
        <button type="button" className="icon-btn" title="View" aria-label={`View ${name}`} onClick={show}
          style={{ width: 28, height: 28, minWidth: 28, padding: 0, display: "inline-grid", placeItems: "center" }}><Icon name="eye" size={16} /></button>
      </span>
      <Modal open={open} onClose={() => setOpen(false)} title={name} icon="complaint" wide>
        {FRAMED.includes(e)
          ? <iframe src={src} title={name} sandbox={e === "pdf" ? undefined : ""} style={{ width: "100%", height: "70vh", border: 0, background: "#fff" }} />
          : <img src={src} alt={name} style={{ display: "block", maxWidth: "100%", maxHeight: "70vh", margin: "0 auto" }} />}
      </Modal>
    </>
  );
}
