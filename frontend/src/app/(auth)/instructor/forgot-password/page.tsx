import ForgotPasswordForm from "@/components/ForgotPasswordForm";

export default function InstructorForgotPasswordPage() {
  return (
    <div className="p-8">
      <ForgotPasswordForm accountType="instructor" />
    </div>
  );
}
