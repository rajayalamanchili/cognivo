import Link from "next/link";

export default function SignInChooserPage() {
  return (
    <div className="mx-auto flex max-w-sm flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <p className="text-sm">Which kind of account are you signing in to?</p>
      <div className="flex flex-col gap-3">
        <Link
          href="/guardian/sign-in"
          className="rounded-lg bg-primary px-5 py-3 text-center text-primary-foreground"
        >
          Sign in as guardian
        </Link>
        <Link
          href="/instructor/sign-in"
          className="rounded-lg border border-border px-5 py-3 text-center"
        >
          Sign in as instructor
        </Link>
      </div>
    </div>
  );
}
