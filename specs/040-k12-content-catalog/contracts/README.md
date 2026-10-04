# Contracts: Full K-12 Content Catalog

No contract file in this directory — this feature changes zero API
endpoints and zero response shapes. See `research.md` Decision 4: every
route this feature touches (subject listing, placement start, practice
start, quiz-assignment creation, instructor dashboard) already resolves
`subject_id` against whatever `Subject` rows exist in the database, with
no enumerated allow-list anywhere in route or service code. Algebra II and
Physics become reachable through every existing endpoint the moment their
content artifact is loaded via `scripts/load_content_artifact.py` — no
request/response contract changes on either side.
