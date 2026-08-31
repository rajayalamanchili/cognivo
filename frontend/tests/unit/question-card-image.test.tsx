// Unit test: QuestionCard renders an image when the question carries one,
// and renders nothing extra when it doesn't (T014, spec 003 FR-004/US1).

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import QuestionCard from "@/components/QuestionCard";
import type { NextQuestion } from "@/services/api";

const baseQuestion: NextQuestion = {
  question_id: "q1",
  topic_id: "systems-of-equations",
  difficulty: "easy",
  question_type: "multiple_choice",
  stem: "Where do the two lines intersect?",
  options: ["(2, 3)", "(0, 1)", "(5, 0)", "(-1, 2)"],
  image_url: null,
  image_alt_text: null,
};

function renderCard(question: NextQuestion) {
  render(
    <QuestionCard
      question={question}
      response=""
      onResponseChange={vi.fn()}
      onFlag={vi.fn()}
      flagged={false}
    />,
  );
}

describe("QuestionCard image rendering", () => {
  it("renders an img with the given alt text when image_url is set", () => {
    renderCard({
      ...baseQuestion,
      image_url: "/content-images/algebra-1/systems-of-equations-graph.svg",
      image_alt_text: "A coordinate plane showing two intersecting lines.",
    });

    const img = screen.getByRole("img", {
      name: "A coordinate plane showing two intersecting lines.",
    });
    expect(img).toHaveAttribute(
      "src",
      "/content-images/algebra-1/systems-of-equations-graph.svg",
    );
  });

  it("renders no image when image_url is null", () => {
    renderCard(baseQuestion);

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
