export type Role = "supervisor" | "super_admin" | "focal" | "investigator";

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  employee_id: string | null;
  cid: string | null;
  designation: string;
  phone: string;
  role: Role;
  role_display: string;
  division: string | null;
  division_name: string | null;
  is_active: boolean;
  last_login: string | null;
  permissions?: string[];
}

export interface Division { id: string; name: string; code: string; is_active: boolean; focal?: { id: string; email: string; name: string } | null }
export interface Subcategory { id: string; name: string; is_active?: boolean; category?: string }
export interface Category {
  id: string; name: string; is_active: boolean; subcategories: Subcategory[];
  default_division: string | null; urban_division: string | null; rural_division: string | null; default_priority: string | null;
}
export interface Named { id: string; name: string }
export interface Meta {
  divisions: { id: string; name: string }[];
  dzongkhags: { id: string; name: string; gewogs: { id: string; name: string }[] }[];
  categories: Category[];
  channels: { value: string; label: string }[];
  provider_types: Named[];
  providers: { id: string; name: string; provider_type: string | null }[];
  priorities: { id: string; name: string; response_days: number; resolution_days: number }[];
  outcomes: Named[];
  closure_reasons: Named[];
}
export interface DzongkhagRow { id: string; name: string; is_active: boolean; gewog_count: number }
export interface GewogRow { id: string; dzongkhag: string; dzongkhag_name: string; name: string; is_active: boolean }
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }

export interface ComplaintRow {
  id: string;
  reference: string;
  subject: string;
  channel: string;
  category_name: string;
  division_name: string | null;
  assigned_to: string | null;
  assigned_to_name: string | null;
  internal_status: string;
  internal_status_display: string;
  public_status: string;
  complainant_name: string;
  dzongkhag: string | null;
  dzongkhag_name: string | null;
  provider_name: string;
  priority: string | null;
  priority_name: string | null;
  resolution_due_at: string | null;
  sla_state: "overdue" | "due_soon" | "ok" | "paused" | "done";
  confidential: boolean;
  created_at: string;
}

export interface CaseMessage {
  id: string; visibility: "public" | "internal"; kind: string; body: string; author_name: string; created_at: string;
  attachments: AttachmentInfo[];
}
export interface AttachmentInfo { id: string; original_name: string; size: number; visibility: string; created_at: string }

export interface ComplaintDetail extends ComplaintRow {
  cid: string; phone: string; email: string; gewog: string | null; gewog_name: string | null; locality: string; area_type: string;
  preferred_contact: string; on_behalf: boolean; affected_name: string; affected_relationship: string; affected_contact: string;
  subcategory: string | null; subcategory_name: string | null; description: string; incident_date: string | null; incident_time: string | null;
  platform: string; provider: string | null; provider_type: string | null; provider_type_name: string | null;
  already_complained: boolean; provider_reference: string; medium_of_publication: string; remedy_sought: string;
  website_or_social: string; additional_info: string; declaration_accepted: boolean; date_received: string | null;
  suggested_division: string | null; suggested_division_name: string | null; confidential_case: boolean;
  response_due_at: string | null; first_response_at: string | null; resolved_at: string | null; closed_at: string | null;
  investigation_findings: string; action_taken: string; recommendation: string; outcome: string | null; outcome_name: string | null;
  closure_reason: string; registered_by_name: string | null; updated_at: string; version: number; paused: boolean; division: string | null; category: string | null;
  status_history: { previous_status: string; new_status: string; actor: string | null; reason: string; created_at: string }[];
  messages: CaseMessage[];
  attachments: AttachmentInfo[];
  notifications: { id: string; event: string; recipient: string; subject: string; status: string; created_at: string }[];
  related: { id: string; reference: string; subject: string; status: string; created_at: string }[];
  permissions: Record<string, boolean>;
}

export interface AuditEntry {
  id: string; actor_email: string; action: string; entity_type: string; entity_id: string;
  detail: Record<string, unknown>; ip_address: string | null; created_at: string;
}

export interface StatItem { key?: string; label: string; count: number; query?: string }
export interface Dashboard {
  role: Role;
  cards: StatItem[];
  by_status: StatItem[];
  by_category: StatItem[];
  by_division: StatItem[];
  by_provider: StatItem[];
  by_location: StatItem[];
  time_to_acknowledge_hours: { average: number | null; median: number | null; count: number };
  time_to_resolve_hours: { average: number | null; median: number | null; count: number };
  overdue: ComplaintRow[];
  recurring: { category: string; provider: string; location: string; count: number }[];
  unassigned_overdue: number;
  monthly: StatItem[];
  recent: ComplaintRow[];
}

export interface AppNotification { id: string; message: string; link: string; read: boolean; created_at: string }
