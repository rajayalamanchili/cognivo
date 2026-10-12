import type { Metadata } from "next";
import ResetPasswordForm from "@/components/ResetPasswordForm";

// PR #115 review (minor): the reset token travels in the URL query
// string -- don't leak it to a third party in a Referer header if this
// page ever links out.
export const metadata: Metadata = { referrer: "no-referrer" };

export default function InstructorResetPasswordPage() {
  return (
    <div className="p-8">
      <ResetPasswordForm accountType="instructor" />
    </div>
  );
}
