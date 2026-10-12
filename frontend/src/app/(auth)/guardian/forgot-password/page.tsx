import ForgotPasswordForm from "@/components/ForgotPasswordForm";

export default function GuardianForgotPasswordPage() {
  return (
    <div className="p-8">
      <ForgotPasswordForm accountType="guardian" />
    </div>
  );
}
