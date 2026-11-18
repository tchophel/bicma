import { Fragment, useState } from "react";
import { api, ApiError } from "../../api";
import { Icon } from "../../components/Icon";
import { PageHeader } from "../../components/ui";
import { useList } from "../../useList";
import "./Permissions.css";

interface Data {
  roles: { value: string; label: string }[];
  permissions: { code: string; label: string; group: string }[];
  matrix: Record<string, string[]>;
}

/** Administrator screen: switch each permission on or off per role. Changes apply at once and are audited. */
export function Permissions() {
  const { data, err, reload } = useList<Data>("/admin/permissions/");
  const [matrix, setMatrix] = useState<Record<string, string[]> | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const m = matrix ?? data?.matrix ?? {};

  async function toggle(role: string, code: string, on: boolean) {
    setMsg(""); setBusy(`${role}:${code}`);
    try { setMatrix((await api<{ matrix: Record<string, string[]> }>("/admin/permissions/", { method: "PUT", json: { role, code, allowed: on } })).matrix); }
    catch (x) { setMsg((x as ApiError).message); }
    finally { setBusy(""); }
  }
  async function reset(role: string, label: string) {
    if (!confirm(`Reset ${label} to the recommended defaults?`)) return;
    setMsg("");
    try { setMatrix((await api<{ matrix: Record<string, string[]> }>(`/admin/permissions/?role=${role}`, { method: "DELETE" })).matrix); reload(); }
    catch (x) { setMsg((x as ApiError).message); }
  }
  const groups = [...new Set(data?.permissions.map((p) => p.group))];
  return (
    <div className="permissions-page">
      <PageHeader icon="lock" title="Roles & permissions" subtitle="Choose what each role may do. Changes apply immediately and are recorded in the audit log." />
      {err && <p className="error" role="alert">{err}</p>}
      {msg && <p className="error" role="alert">{msg}</p>}
      <p className="notice"><Icon name="help" size={18} /> A permission only applies where the case rules allow it. Division Heads and officers still act only in their own division, officers only on cases assigned to them, and only a Division Head's approval closes a case.</p>
      {data && (
        <div className="table-wrap card">
          <table className="perm-table">
            <thead>
              <tr><th>Permission</th>{data.roles.map((r) => <th key={r.value} className="perm-role">{r.label}<button type="button" className="linklike" onClick={() => reset(r.value, r.label)}>Reset</button></th>)}</tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <Fragment key={g}>
                  <tr className="perm-group"><td colSpan={data.roles.length + 1}>{g}</td></tr>
                  {data.permissions.filter((p) => p.group === g).map((p) => (
                    <tr key={p.code}>
                      <td>{p.label}</td>
                      {data.roles.map((r) => {
                        const on = (m[r.value] ?? []).includes(p.code);
                        return (
                          <td key={r.value} className="perm-cell">
                            <input type="checkbox" checked={on} disabled={busy === `${r.value}:${p.code}`} aria-label={`${r.label}: ${p.label}`} onChange={(e) => toggle(r.value, p.code, e.target.checked)} />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
