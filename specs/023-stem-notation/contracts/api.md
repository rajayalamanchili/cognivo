# API Contracts: Math and Science Notation for Free-Text Answers

## No contract changes

Per `research.md` §5, this feature makes no backend or API changes.

The existing `POST /api/questions/{id}/answer` endpoint (and its
practice-session/quiz-session equivalents) already accepts `response`
as a `str` for `free_text` questions and `response_steps` as a
`list[str]` for `multi_step` questions. Notation is carried as ordinary
UTF-8 text within those same, already-documented fields -- no new
field, no new endpoint, no changed response shape, no changed error
shape (`answer_too_long`/`rate_limited`/`moderation_rejected`/
`grading_unavailable` all behave identically regardless of whether the
text contains notation characters).

This feature is frontend-only: a notation-insertion toolbar layered on
`FreeTextAnswerInput`/`MultiStepAnswerInput`, producing the same string
type those components already send.
