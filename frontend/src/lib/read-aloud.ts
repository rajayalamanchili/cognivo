// Browser-native text-to-speech (spec 019 FR-001/FR-002a, research.md
// Decision 1) -- shared between QuestionCard (practice/quiz/assignment
// flows) and placement-flow.tsx, which renders its own question UI
// independently of QuestionCard.

export function canUseReadAloud(): boolean {
  return typeof window !== "undefined" && Boolean(window.speechSynthesis);
}

export function speak(text: string): void {
  if (!canUseReadAloud()) return;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}
