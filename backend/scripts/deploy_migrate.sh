#!/usr/bin/env bash
# Explicit per-environment migration step (tech-stack.md's "Migrations per
# environment" row): `alembic upgrade head` against exactly the target
# branch's own DATABASE_URL, never a shared run assumed to cover more
# than one Neon branch. Intended as a Vercel Deploy Hook target for the
# `production` and `staging` Vercel environments (each with its own
# DATABASE_URL env var set in that Vercel project environment) -- run
# manually against an ephemeral preview/dev branch's DATABASE_URL
# instead, since those aren't persistent Vercel environments.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -z "${DATABASE_URL:-}" ]; then
  echo "deploy_migrate.sh: DATABASE_URL is not set" >&2
  exit 1
fi

alembic upgrade head
