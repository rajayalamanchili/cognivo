# Phase 1 Data Model: Learner-Facing UI Redesign

No new entities, fields, tables, or migrations. This feature restyles the
display of data the platform already models and persists (mastery state,
assessment events, tutor exchanges, recommendation/weak-area output) without
changing its shape, source, or lifecycle. FR-002 and FR-008 require this
explicitly: no new backend/API field, response shape, or database change.

The only artifact this feature changes that could be called a "model" is the
design-token values in `frontend/src/app/globals.css` (a CSS custom-property
set, not an application data model) -- see `research.md` §1.
