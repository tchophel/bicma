import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../../auth";
import { Icon } from "../../components/Icon";
import "../../styles/NotFound.css";

export function NotFound() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const staff = pathname.startsWith("/staff");
  return (
    <main className="nf" aria-labelledby="nf-title">
      <div className="nf-card">
        <div className="nf-code" aria-hidden="true"><span>4</span><span className="nf-zero"><img src="/sad-face.png" alt="" width="173" height="200" /></span><span>4</span></div>
        <p className="nf-eyebrow">ERROR 404 · PAGE NOT FOUND</p>
        <h1 id="nf-title">We can’t find that page</h1>
        <p className="nf-text">The address <code>{pathname}</code> doesn’t exist, or the page has moved. Check the address, or use one of the links below.</p>
        <div className="nf-actions">
          {staff ? (user ? <>
            <Link to="/staff/dashboard" className="btn"><Icon name="home" />Back to the dashboard</Link>
            <Link to="/staff/complaints" className="btn secondary"><Icon name="search" />Complaints</Link>
          </> : <>
            <Link to="/staff" className="btn"><Icon name="lock" />Staff sign in</Link>
            <Link to="/" className="btn secondary"><Icon name="home" />Public home page</Link>
          </>) : <>
            <Link to="/" className="btn"><Icon name="home" />Go to the home page</Link>
            <Link to="/submit" className="btn secondary"><Icon name="plus" />Submit a complaint</Link>
            <Link to="/track" className="btn secondary"><Icon name="search" />Track a complaint</Link>
          </>}
        </div>
      </div>
    </main>
  );
}
