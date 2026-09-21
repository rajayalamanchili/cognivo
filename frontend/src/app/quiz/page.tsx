import { Suspense } from "react";
import QuizFlow from "./quiz-flow";
import LoadingIndicator from "@/components/LoadingIndicator";

export default function QuizPage() {
  return (
    <Suspense fallback={<LoadingIndicator message="Getting ready…" />}>
      <QuizFlow />
    </Suspense>
  );
}
