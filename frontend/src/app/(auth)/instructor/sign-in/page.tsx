import { redirect } from "next/navigation";

// spec 041 FR-004: see guardian/sign-in/page.tsx's identical comment.
export default function InstructorSignInPage() {
  redirect("/sign-in?tab=instructor");
}
