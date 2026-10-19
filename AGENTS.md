# LilCusin development workflow

## Start and finish

- State the task scope and acceptance criteria before editing. Read
  `docs/STATE.md`, then only the relevant item in `docs/TASKS.md` and linked files.
- Use scoped searches and diffs. Do not audit the full repository unless asked.
  Avoid loading historical evidence, generated assets or all tests by default.
- Preserve dirty files and attribute pre-existing changes separately. Work from
  this nested repository; the outer workspace and other checkouts are not mirrors.
- Finish with changes, checks/results, remaining issues and documentation updated.
  Distinguish implementation, local tests, deployment and real-user verification.

## Navigation and conventions

- `README.md`: setup and usage; `docs/ARCHITECTURE.md`: code map and dependencies.
- `docs/STATE.md`: current handoff; `docs/TASKS.md`: next priorities and acceptance.
- `docs/social-product-vision.md`: product vision and canonical T00–T21 criteria.
- `docs/decisions.md`: decision history (reuse its existing lowercase filename).
- Python uses existing async services/handlers and unittest conventions; match
  nearby code. Keep business logic reusable between chat and Mini App.
- UI sources are `music_bot/web/`; edit these and Worker modules, then regenerate
  `worker/worker.mjs` with `python worker/build.py` only when inputs change.
- Preserve natural English/Persian copy, RTL/mobile behavior and the current art
  direction. Do not present proposed features or demo data as working capabilities.

## Verification (from this repository)

Use the existing environment (`.venv/Scripts/python.exe` on Windows, or activated
`python`); do not install/upgrade dependencies merely for a documentation task.

- Python change: `python -m unittest tests.test_<affected_module> -v` using actual
  module names. For example, taste-card work: `python -m unittest tests.test_taste_cards -v`.
- Worker/API or UI: select affected scripts, e.g.
  `node worker/test-worker.mjs`, `node worker/test-bridge.mjs`,
  `node worker/test-taste-card.mjs`, `node worker/test-ui-delivery.mjs`.
- UI syntax: `node --check music_bot/web/app.js`; UI behavior also requires real
  browser checks in English/Persian at desktop/phone sizes, including overflow.
- Docs only: inspect scoped diff, local links and `git diff --check -- <paths>`;
  include new files in manual checks because Git diff omits untracked files.
- Broaden testing only for cross-cutting changes or unresolved failures. Report
  failures/checks not run. Tests and HTTP status alone do not prove live journeys.

## Safety

Never commit, push, deploy or modify production infrastructure without explicit
user approval. Never run a second Telegram poller against a live bot token.
Do not run deployment/probe scripts, live provider tests or preflight implicitly:
read `DEPLOYMENT.md` and establish scope first. Use isolated fixtures, not real
databases. Never expose `.env`, credentials, Telegram initData or user records.
Retain owner/authentication checks, explicit rating/consent and bounded media jobs.

## Documentation ownership

Keep these instructions concise; task details belong in STATE/TASKS. Update docs
only on material changes, linking to existing evidence instead of copying it.
STATE owns current status, TASKS owns priority, ARCHITECTURE owns navigation,
decisions owns rationale, and the vision owns detailed product acceptance criteria.

## Project case-study documentation

Maintain these repository files:
- `docs/decisions.md` — problems, decisions, alternatives, and tradeoffs.
- `docs/evidence.md` — relevant commits, checks, screenshots, and user confirmations.
- `docs/case-study.md` — a concise narrative grounded in those records.

After resolving a meaningful problem or agreeing on an important decision:
1. Update the relevant documentation without waiting for a separate request.
2. Record the date in Asia/Tehran, user impact, evidence, chosen approach,
   rationale, tradeoffs, outcome, and remaining limitations.
3. Distinguish planned, implemented, locally tested, deployed, and
   user-confirmed work. Never infer deployment from a commit or passing test.
   Keep agreed plans and decisions separate from verified accomplishments.
4. Attribute the user's decisions and confirmations accurately. If the rationale
   is unknown, say so rather than inventing it.
5. Update existing entries instead of duplicating them. Preserve earlier
   decisions and explain when a later decision supersedes them.
6. Exclude credentials, private user data, and sensitive infrastructure details.
7. Keep entries concise. Skip routine edits and activity with no useful outcome.

Before finishing, briefly mention any documentation updated.
Repository documentation is authorized; publishing externally requires separate
authorization. These instructions supplement the existing Work Journal workflow;
they do not authorize Notion publication or replace its approval requirements.
