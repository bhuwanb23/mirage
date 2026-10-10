# Contributing to Mirage

Thanks for your interest in making people scam-proof. This document covers how to get a working environment, what we expect in a PR, and how we keep the codebase consistent.

## Ground rules

- Be kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Small, focused PRs beat large omnibus ones.
- Every PR must pass CI (lint + tests) before merge.
- No real user data in drills, honeypots, or test fixtures. Use synthetic identities only.

## Development setup

Requires [uv](https://docs.astral.sh/uv/) (Python 3.11+) and Node.js 20+.

```bash
# clone
git clone https://github.com/bhuwanb23/mirage.git
cd mirage

# backend
cd backend && uv sync && cp ../.env.example .env
uv run uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend && npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev

# bot (new terminal, optional — needs a Telegram token)
cd bot && uv sync && cp ../.env.example .env
uv run python main.py
```

Empty env values are fine in development — missing providers are skipped with a warning.

## Making a change

1. Fork and create a branch: `git checkout -b feat/short-description` or `fix/short-description`.
2. Follow the style of the code you're touching (see below).
3. Add or update tests when you change behavior.
4. Run the gates locally before pushing:

   ```bash
   # Python (backend or bot)
   uv run ruff check
   uv run pytest

   # Frontend
   npm run lint
   npm run build
   ```

5. Open a pull request using the PR template. Fill in every section.

## Style

### Python (backend, bot)

- Enforced by [ruff](https://docs.astral.sh/ruff/) (`line-length = 100`, target `py311`).
- ASCII-only source files.
- Type-annotate public functions.
- Prefer small service modules over god-objects; the backend already splits ~21 services — keep it that way.

### TypeScript (frontend)

- ESLint 9 flat config (`npm run lint`).
- Tailwind CSS 4 utilities; brand accents are `emerald-400` (`#34d399`), scam red is `destructive`.
- shadcn/ui components live in `src/components/ui/` — extend those rather than forking one-off primitives.
- Domain components go in `src/components/<feature>/`.

### Docs & diagrams

- Mermaid sources live in `docs/assets/diagrams/*.mmd`. If you change a diagram, re-render the PNG:

  ```bash
  npx @mermaid-js/mermaid-cli -i docs/assets/diagrams/<name>.mmd -o docs/assets/diagrams/<name>.png -b "#0a0a0a" --size 1400 -s 2
  ```

## Where to start

- `docs/plans/phase_0_checklist.md` — known gaps and verification log.
- Open [issues](https://github.com/bhuwanb23/mirage/issues) labeled `good first issue`.
- Frontend has zero test coverage — adding Vitest/Playwright is a welcome contribution.

## Reporting bugs

Use the [bug report template](https://github.com/bhuwanb23/mirage/issues/new?template=bug_report.yml). Security issues go to [SECURITY.md](SECURITY.md) instead — please don't file them publicly.
