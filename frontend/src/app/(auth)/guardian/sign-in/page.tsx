import { redirect } from "next/navigation";

// spec 041 FR-004: the separate per-role sign-in page is now a thin
// redirect into the unified `/sign-in` page's correct tab, rather than
// duplicating the form -- `register`'s own "Sign in instead" link still
// points here unchanged, so this one extra hop is the only user-visible
// difference from before.
export default function GuardianSignInPage() {
  redirect("/sign-in?tab=guardian");
}
