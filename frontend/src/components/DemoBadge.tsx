// Persistent, unmissable demo-account marker (Constitution Principle VIII,
// tech-stack.md's Demo account strategy). Milestone 1 has no real auth --
// every learner is the seeded DemoLearnerProfile -- so this is shown
// unconditionally rather than gated on a fetched `is_demo` value.

export default function DemoBadge() {
  return (
    <div
      role="status"
      data-testid="demo-badge"
      className="sticky top-0 z-50 flex items-center justify-center gap-2 bg-amber-400 px-4 py-1.5 text-sm font-semibold text-amber-950"
    >
      DEMO ACCOUNT -- synthetic data, not a real learner
    </div>
  );
}
