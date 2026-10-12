"use client";

import { useEffect, useState } from "react";
import {
  getMasteryState,
  listLearnerEnrollments,
  type StandardCoverageEntry,
} from "@/services/api";
import StandardsCoverage from "@/components/StandardsCoverage";

// Spec 038 FR-004 (Clarifications: guardian-facing parity with the
// instructor dashboard). No existing guardian-facing page knew which
// subject(s) a learner is enrolled in (research.md Decision 4 / T014
// correction) -- this fetches that list first, then that subject's
// mastery-state (which already carries `standards`, FR-004), one
// section per enrolled subject. Fails silently per subject rather than
// surfacing a loading/error UI of its own: this is a secondary
// enrichment of the learner card, not the guardian's primary task on
// this page (adding a learner, joining a roster).

interface SubjectStandards {
  subjectId: string;
  standards: StandardCoverageEntry[];
}

export interface GuardianLearnerStandardsProps {
  learnerId: string;
  // spec 044 FR-002 (US1): scope to one subject (the selected card tab)
  // instead of every enrolled subject combined, once a learner has more
  // than one enrollment -- undefined keeps today's "every subject" sum.
  subjectId?: string;
}

export default function GuardianLearnerStandards({
  learnerId,
  subjectId,
}: GuardianLearnerStandardsProps) {
  const [bySubject, setBySubject] = useState<SubjectStandards[]>([]);

  useEffect(() => {
    let cancelled = false;
    listLearnerEnrollments(learnerId)
      .then(async (result) => {
        const subjectIds = [...new Set(result.enrollments.map((e) => e.subject_id))].filter(
          (id) => subjectId === undefined || id === subjectId,
        );
        const results = await Promise.all(
          subjectIds.map(async (id) => {
            const state = await getMasteryState(learnerId, id);
            return { subjectId: id, standards: state.standards ?? [] };
          }),
        );
        if (!cancelled) setBySubject(results);
      })
      .catch(() => {
        // Secondary enrichment -- see module comment above.
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId]);

  return (
    <>
      {bySubject.map(({ subjectId, standards }) => (
        <StandardsCoverage key={subjectId} standards={standards} />
      ))}
    </>
  );
}
