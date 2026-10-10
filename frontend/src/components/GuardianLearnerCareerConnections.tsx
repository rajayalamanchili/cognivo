"use client";

import { useEffect, useState } from "react";
import {
  getMasteryState,
  listLearnerEnrollments,
  type CareerConnectionEntry,
} from "@/services/api";
import CareerConnectionsList from "@/components/CareerConnectionsList";

// Spec 039 FR-003 (sibling to GuardianLearnerStandards.tsx -- a
// different concern, same fetch shape). No existing guardian-facing
// page knew which subject(s) a learner is enrolled in before spec 038
// added this fetch; reused here rather than duplicated. Fails silently
// per subject rather than surfacing a loading/error UI of its own: this
// is a secondary enrichment of the learner card, not the guardian's
// primary task on this page (adding a learner, joining a roster).

export interface GuardianLearnerCareerConnectionsProps {
  learnerId: string;
  // spec 044 FR-002 (US1): scope to one subject (the selected card tab)
  // instead of every enrolled subject combined, once a learner has more
  // than one enrollment -- undefined keeps today's "every subject" sum.
  subjectId?: string;
}

export default function GuardianLearnerCareerConnections({
  learnerId,
  subjectId,
}: GuardianLearnerCareerConnectionsProps) {
  const [careerConnections, setCareerConnections] = useState<CareerConnectionEntry[]>([]);

  useEffect(() => {
    let cancelled = false;
    listLearnerEnrollments(learnerId)
      .then(async (result) => {
        const subjectIds = [...new Set(result.enrollments.map((e) => e.subject_id))].filter(
          (id) => subjectId === undefined || id === subjectId,
        );
        const results = await Promise.all(
          subjectIds.map((id) => getMasteryState(learnerId, id)),
        );
        if (!cancelled) {
          setCareerConnections(results.flatMap((state) => state.career_connections ?? []));
        }
      })
      .catch(() => {
        // Secondary enrichment -- see module comment above.
      });
    return () => {
      cancelled = true;
    };
  }, [learnerId, subjectId]);

  return <CareerConnectionsList careerConnections={careerConnections} />;
}
