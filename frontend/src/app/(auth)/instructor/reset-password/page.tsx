import ResetPasswordForm from "@/components/ResetPasswordForm";

export default function InstructorResetPasswordPage() {
  return (
    <div className="p-8">
      <ResetPasswordForm accountType="instructor" />
    </div>
  );
}
