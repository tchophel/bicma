import { useNavigate } from "react-router-dom";
import { useAuth } from "../../auth";
import { ComplaintForm } from "../../components/ComplaintForm";
import { PageHeader } from "../../components/ui";

export function Register() {
  const { user } = useAuth();
  const nav = useNavigate();
  if (user && !user.permissions?.includes("register_complaint")) return <p className="error">Your role is not permitted to register complaints.</p>;
  return (
    <div className="register-page">
      <PageHeader icon="plus" title="Register a complaint" subtitle="Record a complaint received by phone, letter, walk-in or email. Save a draft to finish later." />
      <ComplaintForm offline onDone={(r) => nav(r.draft ? "/staff/complaints?scope=drafts" : r.id ? `/staff/complaints/${r.id}` : "/staff/complaints")} />
    </div>
  );
}
