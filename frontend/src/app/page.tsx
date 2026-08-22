import Link from "next/link";

export default function Home() {
  return (
    <div className="mx-auto flex max-w-2xl flex-1 flex-col items-start justify-center gap-6 p-8">
      <h1 className="text-3xl font-semibold">Cognivo</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        A domain-agnostic learning platform that personalizes sequencing based on a real mastery
        model, and generates assessments dynamically.
      </p>
      <div className="flex gap-4">
        <Link
          href="/placement?subject=algebra-1"
          className="rounded bg-foreground px-5 py-3 text-background"
        >
          Start Algebra I Placement
        </Link>
        <Link
          href="/placement?subject=biology"
          className="rounded bg-foreground px-5 py-3 text-background"
        >
          Start Biology Placement
        </Link>
      </div>
    </div>
  );
}
