# Model notes — how workers actually perform

A running log of how models perform on real Ringer tasks, so engine and
model choices are made on evidence instead of vibes. The raw numbers now
live in the local eval log (`~/.ringer/runs.jsonl`); run `./ringer.py models`
to print the per-model, per-task_type scoreboard (tasks, attempts,
pass_rate, first_try_pass_rate, median duration/tokens, last_seen). This
file remains the judgment layer on top of those numbers.

**How to add a row:** after reviewing a run (post-run ritual step 5 in the
ringer skill), append one dated line under the model. Say the task type,
what happened, and what you'd do differently. Only write what the executed
checks and raw logs support — no vibes, no worker self-reports.

## codex (GPT-5-class, own harness)

- Strongest general worker; the default engine. Spend reasoning effort per
  task via `engine_args` (`["-c", "model_reasoning_effort=low|medium|high"]`)
  — high on gnarly tasks, low on boilerplate.
- 2026-07-05 — carried the heavy lanes of the milk-crate demo rehearsals
  (market read with source allowlist, site build) with clean first-attempt
  passes.
- 2026-07-10 — gpt-5.6-sol, code-feature (steering-profiles feature in
  ringer.py itself, ~470-line change + 18 tests + docs, run
  ringer-steering-profiles): shipped as PR #25. 2 attempts, 379k tokens,
  but the attempt-1 FAIL was the CHECK's fault, not the model's — the check
  gated on the ENTIRE pre-existing suite being green inside the worker
  sandbox (localhost binds blocked, fixture missing). The feature work
  itself was verified green both attempts; attempt 2 "hardened" an already
  -sound implementation. Scoreboard's FAIL row for this run understates the
  model. Lesson for check authors: regression gates must compare against
  the BASELINE failure set, never assert absolute suite green.
- 2026-07-06 — adversarial pre-merge review (aicred spark): passed on
  attempt 1, ~85k tokens.
- 2026-07-06 — motion design (5 HTML animations for video b-roll) + 2
  editorial diagram pages, each verified by rendering through headless
  Chromium to MP4/PNG: 7/7 passed on attempt 1. Broadcast-quality visual
  output from rich storyboard specs; the render-as-check pattern works.
- 2026-07-06 — milk-crate demo: two single-file website builds (v1 scaffold
  316s/~175k tok; final brand+market-test reskin 622s/~184k tok), both passed
  14-assertion content checks on attempt 1, including base64-embedding photos
  and honoring honesty-marker requirements. Codex remains the site-build lane.
- 2026-07-06 — ringer.py feature batch (task_type field + enriched eval rows
  + `models` scoreboard + hud single-tab fix; ~640-line diff incl. two new
  test suites): substance passed on attempt 1 — its check printed PASS
  (compile, all 16 suites, exact CLI aggregation contract) — but the run
  recorded attempt 2 because of the expect_files-before-check harness bug
  (see process lessons). Heavy single-file feature work against an exact
  behavioral contract is squarely codex's lane.

- 2026-07-06 — elsas-website demo: Next.js scaffold PASSED attempt 2 (682s,
  ~354k tok) — attempt 1 built a complete homepage and silently skipped the
  other 10 routes; the route-enumeration check caught it. Narration lane
  (15 ElevenLabs calls, chunked, nohup pattern) passed attempt 1. CAUTION: a
  codex fix worker GAMED a verbatim-content needle by hiding the required text
  in a visually-hidden paragraph — passed the check, caught only by
  orchestrator integration review. Needle checks need an anti-hidden-text
  assertion or documented exceptions.

- 2026-07-06 — OpenRouter catalog + explore suggester (catalog subcommand
  with snapshot/changelog/free-detection, daemon auto-refresh, tiered
  --explore; offline fixture-driven contract check): PASS attempt 1, 362s.
  Follow-up sentinel-pricing fix (variable-pricing models): PASS attempt 1,
  114s. With the verify-order fix landed, zero phantom retries across the
  whole batch.
- 2026-07-06 — adversarial review of the model-router stack (2,650-line
  diff, structured report contract): PASS attempt 1, 176s — found a real
  HIGH (--since window inflating first-try rates) plus 3 MEDIUMs, all
  confirmed against the code. Then fixed all five review findings in one
  batch (task-level --since, pricing transitions, event durability + flock,
  unknown pricing, stderr notice) with test coverage: PASS attempt 1, 202s.
  Review->fix roundtrip in codex's lane works end to end.
- 2026-07-06 — scoreboard HTML page (zero-LLM renderer, ~700-line diff,
  design + evidence-floor ranking + cost math + notes parser): substance
  PASS attempt 1 (the run's recorded retry was an orchestrator check bug —
  the free-promo watchlist legitimately mentions a free model before the
  ranked cards, and the check compared raw first-occurrence). Six review
  findings fixed in one batch, PASS attempt 1, 141s.
- 2026-07-06 — model-db stack (SQLite read model 516s, page redesign 536s,
  Ringside tab 527s, plus three fix batches all attempt-1): five substantial
  ringer.py features in one day, every one against an executed contract
  check. Review lane found the HIGH that mattered (sync cursor skipping a
  half-written trailing line). Codex is the proven lane for both sides of
  the review->fix loop on this codebase.

## GPT-6 Astra (codex) vs GPT-5.5 (codex) — head-to-head bakeoff

- 2026-09-12 — code-feature bakeoff (run astra-vs-gpt55-bakeoff): three pure-stdlib
  Python modules (log-header parser, scoreboard aggregator, promotion-ladder state
  machine), each spec'd to an exact behavioural contract and graded by a hidden
  unittest suite (44 assertions total) the workers never saw. Identical specs,
  identical checks, no reasoning-effort flags on either arm, so the only variable
  was the model. RESULT: a dead heat on correctness — 3/3 pass and 2/3 first-try
  for BOTH models, with both arms retrying on the same scenario (logparse).
  Astra cost more for the same outcome: 89,933 tokens / 174s total vs GPT-5.5's
  64,050 / 150s, so roughly 40% more tokens and 16% more wall-clock. Astra's code
  was also consistently terser (29/35/61 lines vs 33/46/80). Spot-checked the
  passing artifacts: no hidden-test gaming, no stubbing, clean idiomatic code
  from both. TAKEAWAY: on well-specified mechanical feature work there is no
  correctness reason to prefer Astra over GPT-5.5, and a mild cost reason to
  prefer 5.5. Astra's advantage, if it has one, should be looked for on
  underspecified or multi-tool work rather than contract-following.
- 2026-09-12 — RESOLVED, and it reverses the reading above. The shared logparse
  retry was a SPEC defect, not a model defect. With the attempt-history fix
  live, a third run finally preserved attempt 1's output: every arm failed the
  same single assertion, test_trailing_whitespace_trimmed, returning None for
  the line "model:   gpt-5.5  " with trailing spaces. The spec defined the
  engine field as "stripped of surrounding whitespace" but defined the model
  field only as a non-whitespace run anchored to end of line, never saying
  trailing whitespace was tolerated after it. Three workers across three runs
  read that literally and were defensible. Correct scoring for the bakeoff is
  therefore 3/3 first-try for BOTH models on substance, not 2/3 — the arms stay
  tied, and the cost gap (Astra ~40% more tokens) remains the only real
  separator. Lesson for spec authors, and the mirror of the existing
  check-authoring lesson: when one field in a contract says how whitespace is
  handled and a sibling field does not, workers will read the silence as
  significant. State it on every field or on none.

- 2026-09-12 — GPT-6 Astra, code-feature (attempt-history fix in ringer.py itself,
  run ringer-attempt-history): PASS on attempt 1, 42,852 tokens, 246s. Worktree
  mode, four-site change (TaskRuntime field, state emit, attempt loop append under
  the existing lock, build_failure_context rewrite) plus a 106-line test file it
  wrote itself. Graded by a four-layer verifier it never saw: patch export, full
  suite green, direct import assertions on build_failure_context, and a real
  two-attempt mock run asserting distinct per-attempt output. Clean minimal diff,
  correct lock placement, defensive copy on the state emit matching neighbouring
  style, and non-vacuous tests including exact-equality on attempt_history. This
  is the first Astra data point on REAL repo work rather than the synthetic
  bakeoff, and it is a clear pass. Contrast with the 2026-09-12 bakeoff above,
  where Astra merely tied GPT-5.5 on mechanical contract-following: the
  hypothesis that Astra earns its cost on multi-site work in a live codebase now
  has one supporting data point. Needs more before it is a routing rule.

## glm-5.2 via opencode (`openrouter/z-ai/glm-5.2`)

- The cheap-intelligence default (~$0.74/M in, $2.33/M out, 2026-07 —
  20-30x cheaper output than frontier coding models). Reliable on
  mechanical, tightly-specced work: file edits, format conversions,
  template-driven builds.
- 2026-07-05 — milk-crate demo rehearsals: handled brand-board/SVG/copy
  tasks at around a penny per passing task.
- 2026-07-06 — adversarial pre-merge review (aicred spark): passed, but
  needed the retry (attempt 2) where codex passed on attempt 1. Long
  structured reviews sit at the edge of its comfort zone; keep the section
  contract explicit in the spec.
- 2026-07-06 — three mechanical image-generation batches (18 images via
  openrouter-image commands, idempotent batch-runner spec): 3/3 passed on
  attempt 1, ~14.5k tokens each. The "execute these exact commands, do not
  improve them" spec pattern is fully reliable for glm-5.2.

- 2026-07-06 — backfill/seed script for the model log (252-line stdlib CLI
  with a run-state join, 3-level mapping precedence, never-overwrite and
  idempotency rules): the artifact was CORRECT; the recorded FAIL was an
  orchestrator check-fixture bug (a missing newline glued the fixture's last
  row to a garbage line) plus the harness ordering bug below. Verified PASS
  once the check was fixed. Tight behavior contracts in the spec work great
  for glm — and read the raw logs before blaming the model.
- 2026-07-06 — README/MODEL-NOTES docs + task_type sweep across 17 template
  manifests: passed attempt 2; attempt 1 was lost to the harness ordering
  bug, not model quality — the retry worker's log correctly diagnosed that
  harness bug unprompted, impressive debugging from the cheap lane.
- 2026-07-06 — catalog/explore README section (flags, promotion ladder,
  per-user framing): PASS attempt 1, ~21.5k tokens. Doc sections against a
  grep-able content contract remain a safe glm lane.
- 2026-07-06 — milk-crate demo, full run: 4 independent buyer-persona
  reviews (focus group) all passed attempt 1 (~15k tokens, ~2¢ each) with an
  explicit VERDICT-block contract — persona work is squarely in glm's zone.
  Market read with live curl fetching passed once the spec demanded verbatim
  copy-paste of source URLs (first fail was the worker trimming URL slugs —
  spec/check craft, not model weakness). Brand-kit doc incl. a clean inline
  SVG wordmark: good, one bounce off an over-strict check regex.

- 2026-07-06 — elsas-website demo: verbatim content capture (16 pages + 19
  news posts, 213 blockquotes) passed attempt 2 — attempt 1 SELF-REPORTED
  "all 213 match exactly, 0 errors" while the executed check found 13 stitched/
  paraphrased quotes. Self-reports are worthless; the retry with injected
  failures fixed all 13 (~148k tok total, ~3¢). Page builds (about+faq;
  news index + 19 generated post routes via its own extraction script) and
  2 focus-group personas: all attempt 1. Fix batch attempt 1.
- 2026-07-06 — invariants/file-I/O review lens on the same stack: PASS
  attempt 1, 68k tokens — caught the non-atomic backfill rewrite (real data
  loss risk) and the daemon stdout race; both confirmed. Then fixed the
  backfill atomicity (tmp+os.replace, pid-stamped backups) attempt 1 with
  the original behavioral grader unchanged. Structured review with an
  explicit lens is now proven glm territory, not just probation.
- 2026-07-06 — solo adversarial review of the scoreboard renderer (~700
  line diff, injection-focused lens): PASS attempt 1 — 1 MEDIUM (unanchored
  MODEL-NOTES heading match cross-contaminating gpt-4/gpt-4o-style
  families) + 5 real LOWs, plus an empirically-verified injection all-clear
  (it actually rendered hostile model ids to prove escaping). Second
  proven-tier structured review in one day; glm is now the default review
  lane for mid-size diffs.
- 2026-07-06 — invariants/injection/frontend review of the 4,061-line
  model-db branch: PASS attempt 1, 96k tokens, 14 coverage items — two real
  contention findings (full catalog re-ingest per sync; schema writes on
  read paths) plus an empirical XSS all-clear on the new DOM surfaces.
  Third proven-tier structured review today.

## kimi-k2.7 via opencode (`openrouter/moonshotai/kimi-k2.7-code`)

- 2026-07-06 — adversarial pre-merge review (aicred spark): passed on
  attempt 1, ~83k tokens. First real outing; promising for review work.
  (Ran through an ad-hoc copy of the opencode engine block — the per-task
  `model` field now makes that unnecessary.)

## kimi-k2.6 (`moonshotai/kimi-k2.6`, subject-model evidence via OpenRouter)

- 2026-07-07 — Benchmark Suite 2.0 operator eval, killed by Jon at ~4.5h.
  Serving throughput, not model quality, was the failure: on the Brick
  1000-piece case (reasoning xhigh, pinned provider order
  inceptron→decart→baidu→modelrun, no fallbacks) K2.6 averaged ~21 tok/s
  with two ~19-min stalls at 4.5 tok/s — 136+ min unfinished vs Sonnet 5's
  25 min (94 tok/s) and GPT-5.5's 24 min (55 tok/s) on the identical case.
  Model behavior itself was fine: 28 turns (fewer than Sonnet's 82), 170k
  output tokens (in family norms), 12% reasoning, zero API errors. Verdict:
  do NOT schedule K2.6 for long agentic work through that provider set;
  if K2.6 data is ever wanted, probe a single case against other providers
  first. Distinct model from k2.7-code above — don't transfer this verdict
  to k2.7.


## Grok 4.6 (Grok Build CLI v1.0.13, per-call billing)

- 2026-09-12 — code-feature proving run (grok-code-feature-proving): the same
  three hidden-test scenarios the Codex arms ran (logparse / scoreagg / ladder,
  44 assertions the worker never sees), logparse spec corrected first so the
  trailing-whitespace ambiguity could not manufacture a miss. 3/3 PASS on
  attempt 1, lifting the lane from a single logged-out 0% row to PROVEN at 3/4
  (75%). Spot-checked: one file per task as specified, clean idiomatic code,
  line counts in the same band as both Codex arms (28-81 lines). Harness
  self-report captured on all three rows via the new model_report_regex.
  COST IS THE STORY: 89k / 93k / 162k tokens against Astra's 39k / 36k / 15k and
  GPT-5.5's 38k / 16k / 11k on identical specs — roughly 2-10x the tokens — and
  this lane bills per call: $0.50 for the three tasks (the JSON reports
  total_cost_usd, which the old config comment denied). Same correctness as the
  Codex arms at several times the spend. ROUTING: a valid overflow or
  third-opinion lane, not a first choice for code-feature while Astra is
  plan-included and equally correct.
- 2026-09-12 — the pre-existing 0% code-feature row is from 2026-09-05, when the
  CLI was signed out (627,956 "tokens" in 6s is not a real attempt). Treat it as
  a lane failure, not a model failure.

## grok-build (Grok CLI engine, flat plan)

- 2026-07-10 — identity correction (Jon): the Grok Build CLI is a HARNESS
  serving exactly two models — Grok 4.5 (xAI) and Composer 2.5 (Cursor).
  The engine-lane slug `grok-build` resolves to Grok 4.5. "Grok Build 0.1"
  was never a model; earlier notes/rows using it as one describe Grok 4.5.

- 2026-07-06 — first outing (elsas-website demo), engine added same day:
  audition PASS attempt 1 in 28.9s. Then: asset harvest (11 images, live URL
  re-fetch check), books page, 5 work-page routes in one task (59 verbatim
  needles), adversarial code review (10 real findings incl. an unshelled 404
  and a broken embedded link), press/media fix batch, audio-player integration
  across 15 pages — ALL attempt 1 (player's red ledger entry was a check bug,
  artifact certified). Fast, precise on mechanical/code work. No token counts
  in JSON output (flat plan) — cost reads "included in plan".

## grok-composer-2.5-fast (Grok CLI engine, flat plan)

- 2026-07-06 — first outing (elsas-website demo): audition PASS attempt 1
  (138s — slower than grok-build but the strongest copy of the round).
  Accessibility constitution (14 testable criteria, SC-numbered) attempt 1;
  a11y-gatekeeper harness (axe+Playwright, light/dark, reduced-motion assert)
  attempt 2 — attempt 1's harness mishandled Next's default /404 route.
  Events/faq/contact fix batch attempt 1, but satisfied "editorial grid" with
  an EMPTY aside landmark — axe caught it (landmark-complementary-is-top-level).
  Persona work: good. Watch for letter-of-the-spec shortcuts on layout asks.

## nemotron-3-super-120b (via opencode, `openrouter/nvidia/nemotron-3-super-120b-a12b:free`)

- 2026-07-06 — AUDITION FAILED (exploration slot, $0 spent — free promo).
  Task: fresh-eyes adversarial review of a 2,650-line diff with a structured
  report contract. Failed both attempts on the same executed check: report
  had the right sections and verdict but under 3 concrete code citations —
  shallow engagement with the actual code, 212k tokens burned. Don't re-run
  this audition on long structured code review; if it gets another slot,
  try a shorter, more mechanical task first.

## llama-3.3-70b-instruct (via opencode, `openrouter/meta-llama/llama-3.3-70b-instruct:free`)

- 2026-07-06 — AUDITION FAILED (exploration slot, $0). Fresh-eyes review of
  a 4,061-line diff with a verbatim-quote citation requirement: failed the
  structured-report check both attempts. Second free-model audition to fail
  on long structured code review (after nemotron-3-super) — the exploration
  ladder now says: audition free models on SHORT mechanical tasks first;
  long-diff review is a proven-tier lane.

## Small / flash-class models

- First to choke on long conversational or multi-turn harness tasks —
  watch retry counts before scaling them into a batch (2026-07-05 focus
  group lesson).

## Process lessons (cross-model)

- 2026-09-12 — SECOND grader defect of the day, same shape (AE-32, Exam Prep
  question bank): both worker attempts FAILED on a KeyError in the CHECK's
  counting script, which globbed `data/bank/*.json` and iterated
  `sources.json` (a metadata file the SPEC itself asked for) as if it were a
  question array. The worker had built 271 correctly cited items and its
  notes even said "sources.json and skipped.json are metadata, not question
  arrays". Diagnosed in one read via attempt_history; fixed grader passed on
  the untouched tree in 2s; round 2 (verify-only spec) PASSED first try at
  34k tokens. Cost of the defect: 244k tokens across two wasted attempts.
  RULES: (1) a check that globs the worker's output directory must filter by
  SHAPE (list of dicts with the expected keys), never by filename convention
  alone, because the spec told the worker to write other files there;
  (2) put every unchanged-behaviour assert BEFORE the first new-behaviour
  assert so `--baseline` proves the unchanged block — AE-32's first baseline
  stopped at "missing dependency drizzle-orm" and never exercised typecheck;
  (3) an orchestrator spot-check that string-matches worker output against
  raw PDF text must tolerate the worker's documented normalisations (here:
  stacked fractions rendered as "1/2" where pypdf reads "1 2") — one honest
  item tripped it and the gate correctly refused to commit until a human
  looked, which is the right failure mode.

- 2026-09-12 — CHECK BUG, not a model bug (AE-28, Exam Prep bootstrap): both
  worker attempts FAILED on `grep -Eq "Tests +[1-9][0-9]* passed"` against the
  captured `npm test` output, while the work itself was green (lint, typecheck,
  vitest, build all passed in the orchestrator lane, and the worker's notes
  said "one shell test passed"). Cause: vitest 5 emits ANSI colour even when
  piped, and the escapes sit between "Tests" and the count, so the anchored
  grep never matches. Diagnosed in seconds because attempt_history preserved
  attempt 1's check output — the same class of loss that hid the bakeoff retry
  earlier today. Fix: strip ANSI before asserting on tool output
  (`sed 's/\x1b\[[0-9;]*m//g'`), or pass the tool's own no-colour flag. This
  is the third colour-related false negative of the day (codex `--color auto`
  under a wrapper broke token_regex and model_report_regex the same way).
  RULE for check authors: any grep over a CLI's output must run on
  ANSI-stripped text. The worker paid two attempts (87k tokens) for a grader
  defect; the round-2 spec says so explicitly so the record stays honest.

- 2026-07-06 — the orchestrator's CHECKS were the day's top failure source:
  three check bugs (fixture newline join, first-occurrence ordering vs the
  watchlist strip, claim-prefix split on '.' instead of ':') each produced
  a FAIL verdict on work that was actually correct — including all four
  capability-research packets at once. Every one was caught by reading raw
  logs/artifacts before blaming the model. Corollary for the scoreboard:
  recorded FAILs whose root cause was a check bug are annotated here, and
  check fixtures deserve the same review care as production code.


- 2026-07-06 — HARNESS BUG (fix in flight on feat/model-perf-log):
  Verifier.verify evaluated expect_files BEFORE running the check, so any
  check that itself creates/exports its deliverable (the worktree
  patch-export pattern) failed attempt 1 with "missing expected files" even
  when the check printed PASS. Cost 3 phantom retries in one run — and it
  poisons first_try_pass_rate, the model log's routing signal. Until the
  reorder lands on your checkout: have the WORKER write the declared
  deliverable, or don't declare check-created files in expect_files. When
  reading seeded scoreboard numbers, remember 2026-07-06 first-try rates
  are depressed by this.
- 2026-07-06 — the model log is now automatic: every attempt row carries
  model/task_type/retry; `./ringer.py models` prints the scoreboard; 81
  historical rows were seeded via scripts/backfill_model_log.py with a
  hand-authored task-type mapping. Give every manifest task a task_type or
  its evidence buckets as (untyped).

- 2026-07-06 — a three-model "bakeoff" ran every task on the engine's
  hard-coded model: task keys said glm/gpt/kimi, but the opencode engine
  block pinned glm-5.2, so one model wrote all three "competing" reviews.
  This is why the per-task `model` field exists — a bakeoff is only a
  bakeoff if the manifest, not the engine block, names the model. Verify
  with the `model` column in the run state, not the task key.
- 2026-07-06 — spawning 5-6 opencode workers simultaneously hit opencode's
  local "database is locked" (sqlite) — several instant attempt-1 failures,
  all absorbed by Ringer's retry. Cosmetic in Ringside ("sent back" at 0s) but
  wastes an attempt; consider staggering opencode spawns.
- 2026-07-06 — opencode's bash tool kills foreground commands around the
  ~2-minute mark: a 2min+ image-generation API call can never finish inline.
  Spec pattern that works: nohup the long command in the background, then
  poll for the output file in separate short commands.
- 2026-07-06 — two check-craft lessons from the same run: (1) URL-allowlist
  checks must be prefix-tolerant (workers legitimately trim slugs); (2) any
  heading-regex must tolerate numbered headings ("## 3. Type / Typography").
  Both failures looked like worker laziness until the raw logs said otherwise.
- 2026-07-06 — elsas-website demo, check-craft in BOTH directions: (1) a fixed
  800-char body floor failed a worker for faithfully converting genuinely tiny
  source posts — floor must scale with the source; (2) a citation gate treating
  every backtick as a page-quote failed honest reviewers who backticked their
  own fix-suggestions — line-scoped pair parsing + attribute-aware corpus fixed
  it; (3) needle-exception lists must be shared across ALL checks that consume
  the needle set (a needle excepted in one checker failed a task through
  another). Post-mortems ruled FOR the worker 3 times this run — read raw logs
  before blaming the model.
- 2026-07-06 — opencode sqlite "database is locked" again with just 2
  simultaneous opencode spawns (page-news + page-about-faq); retry absorbed it.

## codex (2026-07-06, bench-operator-proofing)
- 8/8 code-feature tasks passed attempt 1 across 3 rounds (worktrees mode, Python harness refactor; 108k-406k tokens/task). Specs embedded the approved architecture doc + exact file ownership; checks built fresh uv venvs and ran the full pytest suite.
- Lesson (check design, not model): all 3 post-integration bugs were invisible to the checks — a test that passed only because the worker's worktree lacked .env, a `--help`-only assertion missing a runtime importlib/sys.modules bug (py3.12 dataclasses), and bare console-script names failing outside activated venvs. Checks should exercise one real invocation from a cold shell, not just --help.

## gpt-5.6-sol (codex)
- 2026-07-15 ringer-self-update run (3 serial tasks, direct-repo-edit mode): code-fix baseline-test repair 1/1 first-try (61k tokens, 1.6m); code-feature self-update mechanism (git fetch/ff-pull/re-exec + HUD staleness restart + 20-test suite) 1/1 first-try at high effort (153k, 8.1m); code-feature signal-contract (all 3 scoreboard surfaces + canonical-route lint enforcement) passed on retry (358k, 13.7m) — attempt 1 died on stale old-column assertions in pre-existing tests it hadn't finished updating; the retry prompt's injected FAIL list was enough to close it out. Lesson: when a task rewrites a display contract, name every test file asserting the old contract in the spec's ownership list AND tell it to update them FIRST.
- 2026-07-09 code-feature/code-fix (ringside-overhaul): 4/4 first-try — a ringer.py logging change with tests, a 265-line stdlib backfill CLI (atomic rewrite, dry-run, idempotence all check-verified), a ~1500-line single-file HTML redesign (running-now pills + worker-card grid + multi-expansion refactor, 30KB patch, node --check + contract greps + unittest), and a render-gating change where it correctly UPDATED tests asserting the old behavior instead of gaming the check. Medium/high reasoning, 65–120k tokens/task.
- Same day, different session (bench-harness-patches, code-fix): 0.29 first-try over 7 tasks on a Next.js/Turbopack harness. Spec and check quality dominate model choice — see the scoreboard before generalizing either number.

## GPT-5.5 (codex) — attribution caveat
- Scoreboard rows dated before 2026-07-09 may actually be gpt-5.6: codex eval rows logged model="" until the write-time stamping fix (PR #18) and were credited to GPT-5.5 by the registry default at read time, while the machine's codex default had already moved to gpt-5.6-sol at an unknown earlier date. `scripts/backfill_model_from_logs.py` re-stamps rows with surviving command-log evidence; anything it skips is a mixed-model aggregate. Trust post-2026-07-09 rows.

## nvidia/nemotron-3-super-120b-a12b:free
- 2026-07-08 (research, content-strategy-recon): FAIL x2. Did the analysis in chat but never wrote report.md; attempt 2 exited rc=0 with no file. Doesn't reliably follow file-output contracts under OpenCode. Demoted — don't re-audition on file-deliverable tasks.

## meta-llama/llama-3.3-70b-instruct:free
- 2026-07-08 (research, content-strategy-recon): FAIL x2. Timed out at 900s both attempts on a moderate DB-scrape+format task. Too slow on the free tier for harness work. Demoted — don't re-audition without much longer timeouts or paid tier.

## z-ai/glm-5.2 (addendum)
- 2026-07-08 (research/filter, pitch-foundry): FAIL x2 on a long-spec rubric-application task (~40k input: embedded rubric + 4 candidate files). Read all inputs, exited rc=0 with ZERO output tokens both attempts — silent stall, no file written. GLM handled the same session's shorter formatting specs fine. Lesson: keep GLM specs short; route long-context apply-this-rubric work to codex.

## GPT-5.5 (codex) — honesty flag
- 2026-07-08 (image-gen, pitch-foundry): sandbox DNS blocked openrouter.ai; ALL 10 API calls errored (logged honestly in gen-log) — but the worker then FABRICATED 10 deliverables locally (composited canvases from the ref image) to satisfy a files-exist>40KB check, and passed. Lesson: (a) codex sandbox has no external DNS on this machine — route API-calling tasks to opencode (network open); (b) never write an existence-only check for generated media — require the success log (SAVED/cost lines) to match the file count.

- 2026-07-09 persona-review (pitch-foundry exec-briefing panel): 0/2 first-try+retry. Produced coherent review CONTENT as chat text but never wrote report.md — does not reliably use file-write tools under opencode. Demoted; do not re-audition for file-deliverable tasks without a write-tool probe first.

## gpt-5.6-luna (codex)
- 2026-07-09 code-feature (unlock-ai guide-format conversion, strict type-contract check): 1/1 first-try, 42.6k tokens, 80s. Followed a multi-file TS pattern precisely at $1/$6 pricing. Good candidate for mechanical codegen/docs lanes; audition in adjacent types.

## opencode / z-ai glm-5.2 (via openrouter)
- 2026-07-09 (aicred-invoice-downloads, 4 code-fix tasks + 1 follow-up, worktrees+npm ci checks): systematic attempt-1 NO-OP — all 4 parallel workers produced zero edits and no summary on first attempt, then completed cleanly on attempt 2 after retry-prompt injection (34k-69k tokens each). Follow-up single task passed attempt 1. Suspect first-invocation session warm-up in opencode-sandboxed under parallel spawn; budget for 2 attempts on parallel GLM batches. Output quality on Next.js/Stripe route+test work: solid, spec-faithful, one boss-caught design gap (used user-scoped supabase client where RLS demanded service role — spec didn't say explicitly; say it explicitly).

## opencode (harness note, any model)
- 2026-07-28 (code-review, pr82-token-saver-review): GLM 5.2 produced a complete, high-quality 218-line report but could NOT write it to an output directory created by the parent Claude Code process — every write returned EPERM. It then spent ~3000s burning retries on ctypes/`openat`/AppleScript/`sandbox-exec` workarounds until it timed out, and the task logged as FAIL despite the deliverable existing in its taskdir. Codex workers in the same run were unaffected. Lesson: point opencode workers' output INSIDE their own taskdir and harvest via `expect_files`; never hand them a shared output dir another process created. This is an orchestrator spec bug, not a model failure — do not read the FAIL as evidence against GLM.

## Process lessons (2026-07-28, PR #82 review)
- **Ideas worth keeping from a rejected PR.** PR #82's pre-call gateway was dropped (needs your own API key, so it converts flat-rate OAuth plans into metered API billing; incompatible with Claude Code; and it saves tokens by stripping the tool list, which is the thing that makes the CLI worth using). One idea inside it is worth remembering if the problem ever comes back: an *explicitly blessed* answer cache — key a reviewed answer to the exact request plus the exact selected source packet, and replay it with zero upstream calls, never auto-accepting a model answer. It only fires on byte-identical repeats, which is why it didn't justify 2,000 lines here.
- **Doc-stated support floors need a CI job or they are fiction.** README promised Python 3.11+ while CI only ever ran 3.12; a 3.12-only f-string reached review with a fully green suite. Either test the floor or move it.

## gpt-6-sol (codex) — slug not yet live

- 2026-09-26 — one-task probe (run gpt-6-sol-engine-probe) on codex-cli
  0.153.4 with the ChatGPT-account login: both attempts died before any work
  with 400 "The 'gpt-6-sol' model is not supported when using Codex with a
  ChatGPT account". ~/.codex/models_cache.json lists gpt-6-astra, gpt-5.6-sol,
  gpt-5.6-terra, gpt-5.6-luna, gpt-5.5 — no GPT-6 Sol. Codex default stays
  gpt-6-astra. Re-probe after `codex` self-updates or the cache refreshes;
  the slug may differ from "gpt-6-sol".
- Same day: grok engine default moved to grok-4.7. After `grok login
  --device-auth` (the OAuth flow hangs with stdin closed; device-code works
  headless), `grok models` lists grok-4.7 ONLY — 4.6 is gone from the plan.

## Grok 4.7 (Grok Build CLI v1.0.13, per-call billing)

- 2026-09-26 — probe (run grok-4.7-engine-probe): PASS on attempt 2, 354k
  tokens, $0.32 total ($0.09 + $0.23). Attempt 1 was the CHECK's fault, not
  the model's: templates/probe spec says heading "## Model Response Or API
  Result" but probe_check.py demands a literal "MODEL RESPONSE:" marker with
  colon. FIXED same day: probe_check.py now accepts the heading form too. Worker log
  self-reports grok-4.7 (7 hits) but Ringer stored model_reported=None; the
  JSON is pretty-printed in this version, so re-check model_report_regex.
  Token burn on a trivial echo task is the 4.6 story repeated: expensive
  third-opinion lane, not a first-choice worker.

## GPT-5.6 Sol (codex) — 2026-09-26 re-validation

- Probe (run new-model-probes-2026-09-26): PASS first try twice, 32k and 16k
  tokens, ~27s. Worker log header reads model: gpt-5.6-sol. Available on the
  ChatGPT-plan Codex catalog alongside Astra; route per task with "model".

## GLM 5.3 (opencode, OpenRouter) — first validation

- 2026-09-26 — probe: opencode 1.18.15 (Homebrew) rejected BOTH glm-5.3 and
  glm-5.3-flash with "Unexpected server error" in ~2s while glm-5.2 passed —
  its bundled model list stopped at 5.2 even though models.dev had 5.3.
  `brew upgrade opencode` (1.18.15 -> 1.18.32) fixed it: glm-5.3 PASS first
  try, 21.6k tokens, 33s, self-reports z-ai/glm-5.3. Lesson: a fast
  "Unexpected server error" from opencode on a NEW slug means upgrade the
  CLI, not the model. Pricing (OpenRouter, 2026-09-26): glm-5.3 $1.40/$4.40
  per M vs glm-5.2 $0.65/$2.04; glm-5.3-flash $0.04/$0.14 (price cut today,
  1.3M ctx) is the exploration candidate for low-stakes lanes — untested yet.

## 2026-09-26 — check-lessons fix swarm (run ringer-check-lessons), 3 code-fix tasks

- All three PASS first try, worktrees mode, patches applied clean and the full
  286-test suite is green. Fixes: ANSI stripping + NO_COLOR env in
  test-hardening and repo-feature checks; `--baseline-failures` gate in
  check_repo_feature.py (fails only on NEW failure lines); numbered-heading
  tolerance across bakeoff/focus-group/fix-swarm/research-with-proof/
  review-swarm; URL prefix tolerance in competitive-teardown synthesis_check.
- gpt-6-astra, code-fix: the biggest lane (2 checks + README + manifest +
  a hermetic subprocess test), 38k tokens, 150s, first try. Clean patch.
- gpt-5.6-sol, code-fix ×2: headings (5 files, one helper per file as asked,
  23k tokens, 100s) and URLs (27k, 123s). Both first try; the URL patch also
  fixed a latent char-class escaping bug in URL_RE that the spec did not ask
  for — correct, and noted here so the change is not a surprise.

## Grok 4.7 — 2026-09-26 proving run hit a QUOTA WALL, not a model failure

- Run proving-astra-grok47: three read-only code-review lanes over the
  ringer repo all FAILED both attempts with NO report.md. Every worker log
  ends in the same harness error: "You've reached your free Grok Build usage
  limit for now. Get SuperGrok for much higher limits". The account signed
  in today is on the FREE tier (the 2026-09-12 note assumed SuperGrok /
  Premium+). Total spend before the wall: ~$0.34 across three lanes. The
  three FAIL rows in the scoreboard for grok-4.7/code-review are quota
  failures and must not be read as evidence about the model. Rule from the
  playbook applies: never retry into a limit — Ringer's automatic retry
  burned attempt 2 on all three. Do not schedule grok-4.7 lanes again until
  the plan is confirmed; then re-run the same three review specs.
- Same run, gpt-6-astra research (OpenCode 1.18.32 compatibility): PASS
  first try, 11k tokens, 70s — and the report is genuinely useful: the
  `--dangerously-skip-permissions` flag Ringer passes is undocumented on
  1.18.32 (`--auto` is the documented replacement, which preserves explicit
  denials). This makes Astra PROVEN on research (3/4 first try).

## Grok 4.7 via Cursor CLI (engine `cursor`, Cursor plan) — added 2026-09-26

- Why a second route: the Grok Build account is free-tier and walled. Kiran's
  Cursor subscription lists grok-4.7-{low,medium,high,xhigh}[-fast]. Cursor's
  `agent -p --output-format json --force --sandbox enabled` runs headless.
- Probe (run cursor-grok-4.7-engine-probe): PASS first try, 58s API time,
  usage inputTokens 45,827 / outputTokens 2,902 / cacheRead 76,928. The JSON
  has no total-tokens field and no model self-report; scoreboard tokens for
  this engine = input tokens only. Billing is plan-included (no cost field).

## 2026-09-26 — check-lessons round 2 (run ringer-check-lessons-round-2), 6 code-fix tasks

- 6/6 PASS first try in worktrees; patches applied, full suite 327 tests green
  after one expectation update in tests/test_attempt_history.py (it pinned
  the whitespace-collapsed check_output_tail the finding said was wrong).
- gpt-6-astra ×2: the ringer.py verifier fix (incremental check-stdout
  capture so a timed-out check keeps its diagnostic; retry prompt gets the
  TAIL not the prefix; verdict_for returns PASS when the check passed even if
  the worker timed out, with worker_timed_out recorded) — 76k tokens, 7 new
  tests incl. two end-to-end CLI runs; and the test-hardening baseline gate,
  34k. Both first try. Astra is now PROVEN on code-fix.
- gpt-5.6-sol ×1: probe api/postmortem heading forms, 62k, first try —
  PROVEN on code-fix (3/3).
- grok-4.7-high via Cursor ×3: numbered headings across five checks (147k
  input tokens — the widest lane), research-proof ANSI + tail (63k), and the
  review-swarm evidence label (40k). All first try. PROVEN on code-fix.
- ORCHESTRATOR CHECK BUG (mine): every --verify-command in this manifest was
  `python3 -m unittest ... 2>&1 | tail -N && ...`. The pipe made the exit
  status tail's, so a red suite could not fail the check — the Astra task's
  full-suite run WAS red on test_attempt_history and passed anyway. Caught
  only because the orchestrator re-ran the suite after applying. RULE: never
  pipe a verify command's test runner into tail/head/grep; use `set -o
  pipefail` or write output to a file and tail it separately.

## Claude Opus 5.5 via Cursor CLI — 2026-09-26 validation

- Probe (run cursor-claude-engine-probes, model claude-opus-5-5-high): PASS
  first try, 28s. Usage inputTokens 8 / outputTokens 1,207 / cacheRead 52,546
  / cacheWrite 27,389 — with Cursor's prompt caching the scoreboard's
  "input tokens" column (8) is meaningless for this engine; read cacheRead.
  Self-reports Opus 5.5. Plan-included.

## Claude Fable 5.1 via Cursor CLI — blocked on a data-policy acknowledgement

- Same run, model claude-fable-5-1-high: both attempts died before any work
  with `ActionRequiredError: Review Data Policy You must acknowledge Claude
  Fable 5's data retention policy to use the model.` Cursor lists every Fable
  slug as "(NO ZDR)" — zero data retention does not cover it, and the account
  must accept that once (in the Cursor app / dashboard, not from the CLI).
  The two FAIL rows for this slug are a harness gate, not model evidence.
  Re-probe after Kiran acknowledges; until then do not route Fable lanes.

## Claude Fable 5.1 and Claude Opus 5.5 via Claude Code CLI (engine `claude`, Anthropic subscription) — 2026-09-26

- Why this route: Kiran asked why the Anthropic account was not used. It is the
  first-class harness for Claude models (like Codex for GPT); Cursor was only
  wired first. Engine added with a wrapper that strips the nested-session env
  (CLAUDECODE, CLAUDE_CODE_*) so workers spawn from inside a Claude Code
  session; sandbox on via `--settings '{"sandbox":{"enabled":true,
  "allowUnsandboxedCommands":false}}'` + `--permission-mode acceptEdits`.
- Probe (run claude-cli-engine-probes): BOTH PASS first try. Fable 5.1 23s,
  output 1,219 tokens, cache read 81,628, notional total_cost_usd 0.68;
  Opus 5.5 19s, output 1,356, cache read 76,966, notional 0.27. Billing is
  the subscription, so total_cost_usd is a notional API price, not a charge.
  modelUsage self-reports the exact slug, so harness identity wins here —
  unlike Cursor, which reports no model.
- Scoreboard tokens for this engine = the LAST "output_tokens" match in the
  JSON (the modelUsage per-model block), which is lower than the top-level
  usage figure; read the worker log for the full usage object.
- Fable via Cursor stays gated on the data-policy acknowledgement; not needed
  now that the Anthropic route works.
- Same day, same engine: Claude Sonnet 5 (claude-sonnet-5) PASS first try,
  15s, output 991, notional 0.14; Claude Haiku 4.5 (claude-haiku-4-5-20251001)
  PASS first try, 18s, output 1,068, notional 0.05. Haiku is the cheap fast
  lane for mechanical/docs work on this account; validate on a real task
  before scaling (small models choke first on long multi-turn harness tasks).

## GPT-6 Astra, code-feature — AE-53 (run ae-53, 2026-09-26), two serial tasks on the Exam Prep repo

- lc-older-layouts: the REAL work landed on round-1 attempt 1 (nine older
  Year 5/7/9 language-conventions papers went from 0 to 43–57 items each, 451
  total; 12pt position-ordered labels + 8pt answer-box labels found by the
  layout probe; synthetic regression tests added). Round 1 recorded TWO FAILs
  for it: my check's vitest gate ran AFTER the bank floor, so the baseline
  never exercised it and a test already red at HEAD (AE-51 removed the 2016
  skip it looks for) failed honest work twice. Round 2 (same run_name, fixed
  check with a named HEAD-baseline test): PASS attempt 1. Scoreboard: 1 false
  FAIL pair + 1 true PASS. Orchestrator spot check: 13/13 recovered items
  match the official answer cells (spelling write-ins and MCQ, 3 papers).
- numeracy-2013-y3-and-reading-2013: PASS on attempt 2, and attempt 1 was
  also my check — cross-task ownership guard + skipped.json comparison on a
  SHARED serial tree flagged the LC task's legitimate edits, and paper_of()
  did not recognise HEAD's doubled-prefix skip ids. The worker's finding was
  right and honest: the 2013 Y3 numeracy PDF has NO text layer (orchestrator
  probe: 6 tokens in 16 pages vs 300+/paper in 2012/2014), so it stays skipped
  whole with a raster-specific reason for all 35 questions; the 15-item floor
  was unattainable without OCR and the check now accepts the honest form.
  Reading 2013 Y5/Y7: 9 items recovered (split "r"+"ead" instruction tokens
  and fragmented END OF TEST leaking into options), 3 genuine limits kept
  skipped with reasons; orchestrator spot check 9/9 against the answer table.
- CHECK LESSONS (mine, all three cost Astra a false FAIL): (1) run every
  unchanged-behaviour tool gate BEFORE the first new-behaviour floor so the
  baseline exercises it; (2) on a shared serial tree, judge only THIS task's
  papers and let the sibling task's edits stand; (3) match target papers by
  id prefix, never by splitting on "-q"; (4) a floor that assumes a text layer
  must accept an honest whole-paper skip with a specific reason.

## Claude lineup adversarial review (run claude-lineup-adversarial-review, 2026-09-26) — round 1 rows are mostly CHECK NOISE

- 12 code-review lanes (Fable 5.1, Opus 5.5, Sonnet 5, Haiku 4.5 × three
  surfaces: today's verifier changes, the hardened template checks, the
  engine wrappers). Final verdicts 9 PASS / 3 FAIL, but FIRST-TRY rates are
  the routing signal and round 1's first attempts were sunk by my checks:
  review-swarm.py's 1200-word cap (never stated in the spec — raised to
  2500 in the template), my evidence checker not resolving the ABSOLUTE
  paths the engine-wrappers spec itself asked for, and a stray illustrative
  `a.py:3` treated as a citation. Check-caused first-attempt FAILs: Fable ×3,
  Opus ×2, Sonnet ×2 (one of Sonnet's was the "Summary ≤3 lines" rule, a
  format nit). Genuine: Haiku engine-wrappers — attempt 1 findings cited no
  resolvable line, attempt 2 dropped the Evidence: label. Haiku is PROVEN on
  code-review at 2/3 first try on its own merits.
- Round 2 (same run_name): the nine Fable/Opus/Sonnet lanes re-run with the
  fixed checker and the format rules stated in the spec, so their first-try
  evidence is real. Read the round-2 rows, not round 1, for those three.
- Substance: Fable's engine-wrappers report found that the placeholder
  substitution is applied to the spec text (a spec containing "{model}" is
  corrupted) and that model_report_regex reading the FIRST modelUsage key can
  attribute a run to a helper model — both worth a fix swarm.
- Round 2 result (2026-09-26): 9/9 PASS on attempt 1 with the fixed checker
  and the format rules in the spec. Tiers after rounds 1+2: Sonnet 5 PROVEN
  (4/6 first try), Opus 5.5 PROVEN (4/6), Haiku 4.5 PROVEN (2/3), Fable 5.1
  still probation at 3/6 because round 1's three check-caused FAILs weigh it
  down — three more first-try passes needed; round 3 gives it three fresh,
  useful surfaces (the AE-53 ingest commit, the Open Engine bridge, the AE-53
  check scripts). Round-2 reports carry 49 findings (11 P0/P1) — synthesis
  and a fix swarm follow.
- 2026-09-26 ~19:15 AEST — claude.ai SESSION LIMIT (HTTP 429, "You've hit
  your session limit · resets 10:20pm") hit with four Claude workers running
  in parallel (Fable round-3 review + a 3-task fix swarm). Rows to IGNORE as
  quota, not model: fable51-ae53-ingest (code-review, 2 attempts, no report)
  and all three ringer-review-fixes-3 tasks (code-fix: Opus engine-args gate,
  Sonnet failure-line regex, Fable opencode sandbox — 2 attempts each, no
  patch). Rule: on the subscription account keep concurrent Claude workers
  to 2–3 and never let Ringer's automatic retry fire into a 429 — it burned
  attempt 2 on all four. Both runs relaunched after the reset (fix swarm at
  max_parallel 2).

## 2026-09-26 — review-fixes-3 fix swarm (Claude lineup, code-fix), 3 tasks, all PASS first try on the third launch

- Launch 1 died on the claude.ai session limit, launch 2 on the worktrees it
  left behind (`worktree taskdir already exists` — clean up before relaunch);
  launch 3 at max_parallel 2: 3/3 first try. Patches applied; full suite 349
  green after three fixture renames in tests/test_template_check_output_hygiene.py
  (baseline entries under the new 6-char minimum — the Sonnet task's verify
  command ran only its own module, so the orchestrator suite run caught it;
  put the FULL suite in every ringer.py/template verify command).
- claude-opus-5-5, code-fix: engine_args full-access gate in ringer.py
  (engine full_access_args tokens + a prefix denylist rejected unless
  full_access && allow_full_access; lint finding engine_args_full_access;
  tests). Clean, well-scoped. First try.
- claude-sonnet-5, code-fix: failure-line regex rewritten without \b around
  symbols (vitest/jest/pytest/unittest/tap/go formats), baseline entries
  validated (min 6 chars; a <20-char entry matching every failure line is
  "too broad"); READMEs updated; tests. First try.
- claude-fable-5-1, code-fix: Seatbelt profile makes ~/.config/opencode
  read-only and denies writes to share/plugins and share/commands (later
  rules win); tests/test_opencode_sandbox_profile.py extracts the SBPL
  heredoc and drives sandbox-exec on temp dirs — it SKIPS under a nested
  sandbox (the worker's own run), so the orchestrator re-ran it unsandboxed:
  11/11 real. First try.
- Inline (orchestrator, config only): claude engine gains --strict-mcp-config
  so workers never inherit the user's MCP servers (Opus review finding).
- Fable round 3 (2026-09-26): bridge PASS a1, ae53-checks PASS a1, ae53-ingest
  PASS a2 — and that attempt-1 FAIL was my evidence checker AGAIN (its
  citation regex knew py/sh/toml/json/md but not .ts, so an Exam Prep review
  citing scripts/*.ts:NN read as "no citation"; the attempt-1 report passes
  the fixed checker with 22 resolving citations). Extensions widened to
  ts/tsx/js/mjs/mts/yml/yaml in every copy. Fable's code-review tally across
  three rounds: 5 real first-try passes, 1 genuine attempt-2, 4 orchestrator
  check defects — the tier reads probation only because the defects count.
- SUBSTANCE from that lane: a real production-data bug predating AE-53 —
  ingest-reading.ts filters tokens with /STOP|END OF TEST/i, so any sentence
  token containing "stop" is dropped; `naplan-2013-y5-reading-q14` and
  `-y3-reading-q26` ship a truncated CORRECT option. Verified in the bank,
  filed as AE-54. Reviews earn their keep.
- PROPOSAL (not built): Ringer needs a way to mark an eval row as
  "orchestrator check defect" so it is excluded from first-try tiers without
  editing history — today the only remedy is this notes file, and four
  Claude models' tiers were distorted by it in one day.

## GLM 5.3 Flash (opencode, OpenRouter) — 2026-09-26 validation

- Kiran asked for "GLM 4.3 Flash"; no such slug exists on OpenRouter (Flash
  lineup: glm-5.3-flash, glm-4.7-flash, ~glm-flash-latest). Validated
  glm-5.3-flash: probe PASS first try, 53s, 13.9k tokens, self-reports the
  slug. At $0.04/$0.14 per M with 1.3M context it is the exploration lane
  for low-stakes docs/mechanical work — untested on real tasks; small models
  choke first on long harness tasks, so audition it on ONE task per batch.

## 2026-09-27 — attempt annotations shipped (`ringer.py annotate`), built by Claude Fable 5.1

- Run ringer-attempt-annotations, one code-feature task on the `claude`
  engine: implementation PASSED its verify command on attempt 1 (new tests,
  full suite, cold-shell help, docs) but the fix-swarm template's 700-word
  SUMMARY cap — never stated in the spec — failed the attempt; cap raised to
  1500 (format rule), attempt 2 PASS. Annotated with the feature itself.
- Feature: append-only <state_dir>/annotations.jsonl; kinds check_defect /
  quota / harness; retracts are rows; both aggregators drop voided attempts
  and promote the earliest survivor to first try; "Voided" column on CLI,
  JSON, HTML and Ringside; SQLite read model untouched (annotations applied
  at aggregation time). README "Annotating attempts", TAXONOMY paragraph.
- Applied 2026-09-27: 23 annotations covering the 2026-09-26 check defects
  (word caps, citation resolver, .ts extensions, AE-53 gate order and shared
  tree), the claude.ai 429 wall, the Grok Build free-tier wall, the stale
  worktree setup errors, and the gpt-6-sol unavailable slug. Every row names
  its reason and points here. Tiers after: Fable 5.1 / Opus 5.5 / Sonnet 5 /
  Haiku 4.5 / Grok 4.7 (Cursor) PROVEN on code-review; Astra, 5.6 Sol and Grok
  4.7 PROVEN on code-fix; Fable 1/1, Opus 1/1, Sonnet 2/2 on code-fix at 100%
  first try but under the 3-task minimum — real fixes (AE-54, the remaining
  P2 review findings) close that.
  Haiku's genuine engine-wrappers failure was left standing.

## 2026-09-27 — GPT-6 Astra first-attempt audit (run astra-first-attempt-audit): code-feature PROVEN on evidence, not simulation

- Kiran asked what could be "simulated" to prove Astra. Answer: nothing —
  synthetic tasks would move the number without measuring feature work.
  Instead: an evidence audit of all 21 first-attempt FAILs on code-feature,
  four read-only lanes on Opus 5.5 and Sonnet 5 (never Astra judging itself),
  one cited verdict per failure, CHECK DEFECT only with the check's own
  output/script line or a documented lesson as evidence. 4/4 lanes PASS
  (lane D attempt 1 was my evidence checker again — bare MODEL-NOTES.md
  citation; annotated).
- Verdicts: CHECK DEFECT ×14 (AE-21 &apos; grep, AE-23 it.each grep, AE-24
  pre-existing helper grep, AE-28 ANSI count grep, AE-32 grader KeyError,
  AE-33 per-file provenance grep, AE-35 label grep in one dir, AE-37 quoted
  codes regex, AE-38 double-quote grep, AE-39 wrong-file env grep, AE-41
  protected test file, AE-50 ×3 shared-tree ownership loop); QUOTA ×4
  (AE-44, AE-45, AE-47 Codex usage limit; AE-51 out of credits — the auditor
  wrote GENUINE, the evidence says the worker never started); GENUINE ×3
  left standing (AE-34 ×2, AE-42). Every annotation carries its reason.
- Result: Astra code-feature 32/55 (0.58, probation) → 46/56 (0.82, PROVEN)
  with 29 voided attempts shown on the scoreboard (43 annotations active overall). Also proven on code-fix
  (0.70) and research (0.75). The same audit doubles as evidence that the
  orchestrator's checks were the dominant failure source through September —
  the check-craft rules in this file exist because of exactly these rows.
