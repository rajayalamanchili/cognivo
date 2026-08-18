# Sequencing Evaluation Harness

Offline harness that simulates synthetic learner populations against
three ordering conditions (the real Sequencing Agent, a random
baseline, and a fixed canonical-order baseline) and measures
questions-to-mastery for each. See `specs/006-personalization-eval/`
for the full spec, plan, and research.

This harness is manual/on-demand -- it is never invoked by CI or at
request time (Clarifications). Publishing a new report is a deliberate,
reviewed act: run the harness, inspect the output, then commit it.

## Running the harness

From `backend/`:

```sh
python -m src.services.evaluation.run_harness
```

This runs the full profile x subject x condition matrix and writes
`backend/evaluation/reports/latest.json`.

See `--help` for flags to run a single subject/profile pair (`--subject`,
`--profile`), control the RNG seed (`--seed`), or cap the per-topic
question budget (`--max-questions-per-topic`).

## Publishing a report

After a run you're satisfied with, commit the updated report:

```sh
git add backend/evaluation/reports/latest.json
git commit -m "..."
```

`GET /api/evaluation/report` and the frontend report page both read
this committed file directly -- there is no separate publish step.
