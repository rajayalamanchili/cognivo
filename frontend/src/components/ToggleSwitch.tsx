// Shared pill toggle-switch control (visually-hidden checkbox + styled
// track/knob) -- the same markup CareerConnectionsToggle introduced,
// extracted so Settings' accessibility/notification toggles reuse it
// instead of a third hand-rolled copy. Render inside a <label> so the
// `peer` input precedes the track span as a sibling.

export interface ToggleSwitchProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}

export default function ToggleSwitch({ checked, onChange, disabled }: ToggleSwitchProps) {
  return (
    <>
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden="true"
        className="flex h-[30px] w-[52px] shrink-0 items-center rounded-full bg-border p-[3px] transition-colors peer-checked:bg-primary peer-checked:justify-end peer-disabled:opacity-40"
      >
        <span className="h-6 w-6 rounded-full bg-white shadow" />
      </span>
    </>
  );
}
