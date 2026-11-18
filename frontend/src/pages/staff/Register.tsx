import { useNavigate } from "react-router-dom";
import { useAuth } from "../../auth";
import { ComplaintForm } from "../../components/ComplaintForm";
import { PageHeader } from "../../components/ui";

export function Register() {
  const { user } = useAuth();
  const nav = useNavigate();
  if (user && !["focal", "investigator", "super_admin"].includes(user.role)) return <p className="error">Your role cannot register complaints.</p>;
  return (<div className="register-page"><PageHeader icon="plus" title="Register an offline complaint" subtitle="Record a complaint received by phone, email, letter, social media or in person." /><ComplaintForm offline onDone={() => nav("/staff/complaints")} /></div>);
}
