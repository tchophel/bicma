import { Icon, type IconName } from "./Icon";
import "../styles/IconBtn.css";

/** Small icon-only action button. The label is read by screen readers and shown as a tooltip. */
export function IconBtn({ icon, label, onClick, disabled, tone = "default" }: {
  icon: IconName; label: string; onClick: () => void; disabled?: boolean; tone?: "default" | "danger" | "ok";
}) {
  return (
    <button type="button" className={`icon-action icon-action-${tone}`} aria-label={label} title={label} disabled={disabled} onClick={onClick}>
      <Icon name={icon} size={16} />
    </button>
  );
}
