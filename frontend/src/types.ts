export type Role = "supervisor" | "super_admin" | "focal" | "investigator";

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  role: Role;
  role_display: string;
  division: string | null;
  division_name: string | null;
  is_active: boolean;
  last_login: string | null;
}

export interface Division { id: string; name: string; code: string; is_active: boolean; focal?: { id: string; email: string; name: string } | null }
export interface Subcategory { id: string; name: string; is_active?: boolean; category?: string }
export interface Category { id: string; name: string; is_active: boolean; subcategories: Subcategory[] }
export interface Meta {
  divisions: { id: string; name: string }[];
  dzongkhags: { id: string; name: string; gewogs: { id: string; name: string }[] }[];
  categories: Category[];
  channels: { value: string; label: string }[];
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
  created_at: string;
}

export interface ComplaintDetail extends ComplaintRow {
  phone: string; email: string; gewog: string | null; gewog_name: string | null; preferred_contact: string;
  on_behalf: boolean; affected_name: string; affected_relationship: string; affected_contact: string;
  subcategory_name: string | null; description: string; incident_date: string | null;
  platform: string; website_or_social: string; additional_info: string;
  registered_by_name: string | null; updated_at: string;
  status_history: { previous_status: string; new_status: string; actor: string | null; reason: string; created_at: string }[];
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
  by_division?: StatItem[];
  by_area?: StatItem[];
  by_officer?: StatItem[];
  monthly: StatItem[];
  recent: ComplaintRow[];
}

export interface AppNotification { id: string; message: string; link: string; read: boolean; created_at: string }
