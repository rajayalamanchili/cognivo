import Link from "next/link";

// Matches Home.dc.html's three feature cards -- icon badge, heading,
// body -- the one piece of the mockup's hero section this restyle had
// previously dropped (no icon, no decorative hero visual, no audience
// section, no footer).
const FEATURES: { title: string; body: string; icon: React.ReactNode }[] = [
  {
    title: "Bayesian mastery",
    body: "Explainable per-topic tracking, not chat inference.",
    icon: (
      <>
        <path d="M3 20h18" />
        <path d="M6 16v-5" />
        <path d="M11 16V8" />
        <path d="M16 16V7" />
      </>
    ),
  },
  {
    title: "Rubric-first questions",
    body: "Every item authored with its own answer key.",
    icon: (
      <>
        <path d="M9 11l3 3 8-8" />
        <path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" />
      </>
    ),
  },
  {
    title: "Tutor on demand",
    body: "Grounded answers from the subject's own content.",
    icon: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
  },
];

const AUDIENCES = [
  {
    label: "For learners",
    body: "Practice that knows what you've mastered, what's fading, and what's next -- with the reason shown every time.",
  },
  {
    label: "For guardians",
    body: "You create your child's login, join their class, and start their quizzes. Their data is deleted when you ask.",
    cta: { href: "/guardian/register", label: "Create a guardian account" },
  },
  {
    label: "For instructors",
    body: "Rosters, assigned quizzes, a class-wide weak-area view, and a review queue for flagged questions.",
    cta: { href: "/instructor/register", label: "Create an instructor account" },
  },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <div className="mx-auto grid w-full max-w-[1180px] items-center gap-14 px-8 py-16 md:grid-cols-2">
        <div className="flex flex-col gap-5">
          <h1 className="font-heading text-4xl font-bold leading-tight tracking-tight text-heading md:text-[60px]">
            A learning platform that adapts to <span className="text-primary">how you learn</span>.
          </h1>
          <p className="max-w-[44ch] text-lg leading-relaxed text-muted">
            Cognivo sequences what you see next from a real mastery model -- not a guess -- and
            generates every assessment on the spot, rubric first.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/demo"
              className="inline-flex min-h-[54px] items-center gap-2.5 rounded-full bg-primary px-7 font-extrabold text-primary-foreground"
            >
              Try the demo
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M5 12h14" />
                <path d="m13 6 6 6-6 6" />
              </svg>
            </Link>
            <Link
              href="/sign-in"
              className="inline-flex min-h-[54px] items-center rounded-full border-2 border-primary/25 bg-surface px-6 font-extrabold text-heading"
            >
              Sign in
            </Link>
          </div>
          <p className="text-sm text-muted">
            No sign-up needed for the demo. It uses made-up learners only.
          </p>
        </div>

        <div className="relative hidden flex-col gap-4 md:flex" aria-hidden="true">
          <div className="flex flex-col gap-3.5 rounded-card border border-border bg-surface p-6 shadow-[0_20px_40px_-24px_rgba(63,36,112,0.35)]">
            <span className="w-fit rounded-full bg-primary-subtle px-3.5 py-1 text-sm font-bold text-heading">
              Next step after One-Step Equations
            </span>
            <div className="font-heading text-[28px] font-bold text-heading">
              Solve 4(x − 2) = 2x + 6
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2.5 text-[15px]">
                <span className="rounded-full bg-success/15 px-2.5 py-0.5 text-xs font-extrabold text-success">
                  Met
                </span>
                Moves the x terms to one side
              </div>
              <div className="flex items-center gap-2.5 text-[15px]">
                <span className="rounded-full bg-warning/15 px-2.5 py-0.5 text-xs font-extrabold text-warning">
                  Missed
                </span>
                Distributes 4 to both terms
              </div>
            </div>
          </div>

          <div className="ml-auto flex w-[78%] flex-col gap-2.5 rounded-card border border-border bg-surface p-5 shadow-[0_20px_40px_-24px_rgba(63,36,112,0.35)]">
            <div className="flex items-center justify-between text-[15px] font-extrabold">
              <span>Integers and Operations</span>
              <span className="text-warning">Refresh due</span>
            </div>
            <div className="relative h-3 rounded-full bg-surface-subtle">
              <div className="absolute inset-y-0 left-0 w-[92%] rounded-full border-2 border-dashed border-primary/40 box-border" />
              <div className="absolute inset-y-0 left-0 w-[68%] rounded-full bg-warning" />
            </div>
            <span className="text-sm font-bold text-muted">
              Retained 68% · best 92% · last practiced 4 months ago
            </span>
          </div>
        </div>
      </div>

      <div className="mx-auto grid w-full max-w-[1180px] gap-5 px-8 pb-14 md:grid-cols-3">
        {FEATURES.map((feature) => (
          <div
            key={feature.title}
            className="flex flex-col gap-2.5 rounded-card border border-border bg-surface p-7"
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-subtle text-primary">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                {feature.icon}
              </svg>
            </span>
            <div className="font-heading text-xl font-bold text-heading">{feature.title}</div>
            <div className="text-muted">{feature.body}</div>
          </div>
        ))}
      </div>

      <div className="border-y border-border bg-surface">
        <div className="mx-auto grid w-full max-w-[1180px] gap-8 px-8 py-12 md:grid-cols-3">
          {AUDIENCES.map((audience) => (
            <div key={audience.label} className="flex flex-col gap-2">
              <span className="text-[13px] font-extrabold tracking-[0.08em] text-primary">
                {audience.label.toUpperCase()}
              </span>
              <p className="text-[17px] text-heading">{audience.body}</p>
              {audience.cta && (
                <Link href={audience.cta.href} className="font-extrabold text-primary">
                  {audience.cta.label}
                </Link>
              )}
            </div>
          ))}
        </div>
      </div>

      <footer className="mx-auto flex w-full max-w-[1180px] flex-wrap items-center justify-between gap-4 px-8 py-7 text-sm text-muted">
        <span>Cognivo · Algebra I and Biology today, more subjects on the same engine</span>
        <span className="flex gap-5">
          <a href="#">Privacy</a>
          <a href="#">How grading works</a>
        </span>
      </footer>
    </div>
  );
}
