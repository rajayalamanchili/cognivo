import ResetPasswordForm from "@/components/ResetPasswordForm";

export default function GuardianResetPasswordPage() {
  return (
    <div className="p-8">
      <ResetPasswordForm accountType="guardian" />
    </div>
  );
}
