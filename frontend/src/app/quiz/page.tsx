import { Suspense } from "react";
import QuizFlow from "./quiz-flow";

export default function QuizPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading&hellip;</p>}>
      <QuizFlow />
    </Suspense>
  );
}
