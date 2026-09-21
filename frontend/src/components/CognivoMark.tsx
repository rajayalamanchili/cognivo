// "Friendly Aperture" mark -- Cognivo Logo Concepts (Claude Design), turn 3.
// An open "c" arc in the brand lilac with a warm amber center.
export default function CognivoMark({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 104 104" fill="none" className={className} aria-hidden="true">
      <circle
        cx="52"
        cy="52"
        r="41"
        stroke="var(--color-primary)"
        strokeWidth="19"
        strokeLinecap="round"
        strokeDasharray="180 78"
        transform="rotate(48 52 52)"
      />
      <circle cx="52" cy="52" r="14" fill="var(--color-accent)" />
    </svg>
  );
}
