import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import type { User } from "../types";
import { Loader } from "./Loader";
import "../styles/NdiLogin.css";

interface Start { threadId: string; deepLinkURL: string; qr: string; expiresIn: number }
interface Poll { status: "pending" | "verified" | "failed" | "expired" | "no_account"; detail?: string; user?: User }

// Official Bhutan NDI links. The video guide and store pages are the NDI defaults: replace with the exact tutorial / app URLs if GovTech gives them.
const VIDEO_GUIDE = "https://www.youtube.com/results?search_query=Bhutan+NDI+wallet";
const PLAY_STORE = "https://play.google.com/store/search?q=Bhutan%20NDI&c=apps";
const APP_STORE = "https://apps.apple.com/us/search?term=Bhutan%20NDI";
const isMobile = () => typeof window !== "undefined" && window.matchMedia("(max-width: 700px), (pointer: coarse)").matches;

const Title = ({ children }: { children: ReactNode }) => <h2 className="ndi-title">{children}</h2>;

/** Bhutan NDI sign-in (follows "Bhutan NDI UI Specifications v3"): shows a QR code (and a wallet deep link), then polls until the wallet result arrives. */
export function NdiLogin({ onError }: { onError: (message: string) => void }) {
  const { acceptUser } = useAuth();
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState<Start | null>(null);
  const [message, setMessage] = useState("");
  const [starting, setStarting] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const stop = useCallback(() => { window.clearTimeout(timer.current); timer.current = undefined; }, []);

  const begin = useCallback(async () => {
    stop(); setMessage(""); setStart(null); setStarting(true); setOpen(true);
    try { setStart(await api<Start>("/auth/ndi/start/", { json: {} })); }
    catch (x) { setOpen(false); onError((x as ApiError).message); }
    finally { setStarting(false); }
  }, [onError, stop]);

  useEffect(() => {
    if (!open || !start) return;
    const until = Date.now() + start.expiresIn * 1000;
    const poll = async () => {
      try {
        const r = await api<Poll>(`/auth/ndi/status/?threadId=${encodeURIComponent(start.threadId)}`);
        if (r.status === "verified" && r.user) { stop(); setOpen(false); await acceptUser(r.user); return; }
        if (r.status !== "pending") { setMessage(r.detail ?? "Sign-in did not complete."); return; }
      } catch (x) { setMessage((x as ApiError).message); return; }
      if (Date.now() > until) { setMessage("This sign-in request has expired."); return; }
      timer.current = window.setTimeout(poll, 2000);
    };
    timer.current = window.setTimeout(poll, 2000);
    return stop;
  }, [open, start, acceptUser, stop]);

  const close = () => { stop(); setOpen(false); };
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  const mobile = open && isMobile();
  return (
    <>
      <button type="button" className="ndi-btn" onClick={begin} disabled={starting}>
        <img src="/ndi-logo.png" alt="" width={34} height={34} />
        <span>Login with Bhutan NDI</span>
      </button>
      <dialog ref={dialog} className="ndi-popup" aria-label="Login with Bhutan NDI"
        onCancel={(e) => { e.preventDefault(); close(); }} onClick={(e) => { if (e.target === dialog.current) close(); }}>
        {open && (
          <div className="ndi-card">
            <button type="button" className="ndi-close" aria-label="Close" onClick={close}>×</button>
            {mobile
              ? <Title>Login with <span>Bhutan NDI</span> Wallet</Title>
              : <Title>Scan with <span>Bhutan NDI</span> Wallet</Title>}
            {!start && !message && <Loader label="Preparing your sign-in" />}
            {mobile && start && !message && (
              <>
                <a className="ndi-open" href={start.deepLinkURL}>Open Bhutan NDI wallet</a>
                <div className="ndi-or" aria-hidden="true"><span>OR</span></div>
              </>
            )}
            {start && !message && (start.qr
              ? <div className="ndi-qr-frame"><img src={start.qr} alt="QR code to scan with the Bhutan NDI wallet" width={190} height={190} /></div>
              : <p className="error" role="alert">The QR code could not be drawn.{start.deepLinkURL ? " Use Open Bhutan NDI wallet." : ""}</p>)}
            {message && (
              <div className="ndi-message">
                <p className="error" role="alert">{message}</p>
                <button type="button" className="ndi-open" onClick={begin}>Try again</button>
              </div>
            )}
            {start && !message && <p className="ndi-status" role="status" aria-live="polite">Waiting for you to approve in the wallet…</p>}
            <ol className="ndi-steps">
              <li>Open Bhutan NDI Wallet on your phone</li>
              <li>Tap the Scan button <img src="/ndi-scan.png" alt="" width={27} height={27} /> located on the menu bar and scan the QR code</li>
            </ol>
            <a className="ndi-video" href={VIDEO_GUIDE} target="_blank" rel="noreferrer">Watch video guide
              <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="10" fill="currentColor" /><path d="M8 6.2v7.6l6-3.8z" fill="#f8f8f8" /></svg>
            </a>
            <p className="ndi-download">Don’t have the Bhutan NDI Wallet? <strong>Download Now!</strong></p>
            <div className="ndi-stores">
              <a className="ndi-store" href={PLAY_STORE} target="_blank" rel="noreferrer" aria-label="Get it on Google Play">
                <svg width="26" height="28" viewBox="0 0 26 28" aria-hidden="true"><path d="M1 1.5v25L14 14z" fill="#00d7fe" /><path d="M1 1.5 18.5 11 14 14z" fill="#00f076" /><path d="M1 26.5 18.5 17 14 14z" fill="#ff3a44" /><path d="M18.5 11l5 3-5 3L14 14z" fill="#ffd500" /></svg>
                <span><small>GET IT ON</small>Google Play</span>
              </a>
              <a className="ndi-store" href={APP_STORE} target="_blank" rel="noreferrer" aria-label="Download on the App Store">
                <svg width="22" height="26" viewBox="0 0 24 24.5" aria-hidden="true"><path fill="#fff" d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701" /></svg>
                <span><small>Download on the</small>App Store</span>
              </a>
            </div>
            <p className="ndi-support-title">Get Support</p>
            <p className="ndi-support">
              <a href="mailto:ndifeedback@dhi.bt"><svg width="20" height="14" viewBox="0 0 20 14" aria-hidden="true"><rect width="20" height="14" rx="2" fill="#5AC994" /><path d="M1.5 2.5 10 8l8.5-5.5" stroke="#fff" strokeWidth="1.6" fill="none" /></svg>ndifeedback@dhi.bt</a>
              <a href="tel:1199"><svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="#5AC994" d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z" /></svg>1199</a>
            </p>
          </div>
        )}
      </dialog>
    </>
  );
}
