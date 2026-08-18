// One dashboard section per subject. Foundational skeleton (Phase 2):
// three empty slots this feature's user stories populate independently
// -- mastery (US1), weak-area (US2), and path (US3) -- each fetched and
// rendered on its own so a failure in one never blocks the others
// (FR-007, FR-008).

export interface DashboardSubjectSectionProps {
  subjectId: string;
  displayName: string;
}

export default function DashboardSubjectSection({
  subjectId,
  displayName,
}: DashboardSubjectSectionProps) {
  return (
    <section
      data-testid={`dashboard-subject-section-${subjectId}`}
      className="flex flex-col gap-4 rounded border border-black/10 p-6 dark:border-white/10"
    >
      <h2 className="text-xl font-semibold">{displayName}</h2>
      <div data-testid="dashboard-mastery-slot" />
      <div data-testid="dashboard-weak-area-slot" />
      <div data-testid="dashboard-path-slot" />
    </section>
  );
}
