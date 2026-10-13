# Contribution tracker

No pull request is needed. Each configured branch has one persistent progress comment
under its work-area parent issue. Real GitHub subissues remain independently claimable.

## Update your CI/CD branch

Replace these files from this package:

- .github/issue-plan.json
- scripts/issue_tracker.py
- .github/workflows/contribution-tracker.yml
- tests/contribution_tracker/test_tracker.py
- docs/CONTRIBUTION_TRACKER.md

Add:

- .github/workflows/component-branch-changed.yml
- .github/workflows/component-ci.yml
- .github/workflows/static-analysis-tests.yml (if the target branch does not already contain it)
- tests/contribution_tracker/test_branches.py

Keep `docs/project-overview.md`. The issue plan is active configuration: each area
declares evidence paths and exact CI check names, and multiple areas may share a branch.
The tracker performs no Git operations.
Do not retain a duplicate older contribution-tracker workflow under another filename.

## Test now, before merging

From the repository root, after setting GH_TOKEN and GEMINI_API_KEY in your terminal:

    python scripts/issue_tracker.py validate
    python -m unittest discover -s tests/contribution_tracker -v
    python scripts/issue_tracker.py review --branch ML-Axel

The repository defaults to VinnyBitties/CS-4398-Project. Override with --repo owner/repo.
The review is a DRY RUN: it calls GitHub and Gemini but writes no issues or comments.
Existing issues are used if seeded; otherwise the local plan supplies the tasks.
No PR number is needed. The old --pr option has been removed.

For another branch:

    python scripts/issue_tracker.py review --branch llm-threat-intelligence
    python scripts/issue_tracker.py review --branch feature/dynamic-sandbox-engine

For all configured branches:

    python scripts/issue_tracker.py review --all

To deliberately ignore the previous checkpoint and reassess from the common ancestor:

    python scripts/issue_tracker.py review --branch ML-Axel --force

API failures do not publish a result or advance its checkpoint. Dry runs also never
advance checkpoints. The --apply option remains restricted to default-branch Actions.
Dry-run output lists completion candidates, but no issue closes unless `--apply` and
`automatic_closures` are enabled and every configured CI check has succeeded.

## What is compared

First published review: compare the component branch with its common ancestor with the
repository's default branch, or with the area's configured historical `baseline`. A
baseline lets an area assess work already merged into `main`. Optional area `paths`
restrict model evidence to that component. On later reviews, compare the last published SHA
with the latest branch SHA and include the previous report as historical context. If task
or CI state changes at the same SHA, evidence is recollected from the original baseline so
a newly successful CI run can close a previously blocked task autonomously.
If history was rewritten so the old SHA is no longer an ancestor, rebase the assessment
on the current common ancestor. --force explicitly requests that same full refresh.

The report includes the inspected commit, comparison base, whether the branch tip is
contained in the default branch, task evidence, next steps, and unassigned tasks.
Code implemented on a component branch is distinct from code integrated into main.
Ancestry does not prove review approval; squash/rebase merges may not retain ancestry.

A small hidden checkpoint in the BOT COMMENT stores the last SHA, input fingerprint,
and previous report. This is not a second issue backlog. Do not edit or remove the
bot's checkpoint. Human issue descriptions and other comments are never overwritten.
Multiple branches sharing a parent get separate progress comments and checkpoints.
Multiple areas may track `main`; each report remains isolated under its own parent.

Unchanged branch/task/check context skips Gemini. Task assignments, relevant CI results,
overview changes, or merge containment changes can refresh the report even without a
new component commit. Use --force if you need an explicit full reassessment.

## Automatic updates after you merge the setup

Manual reviews are available regardless of `automatic_reviews`. Initialization remains
a separate manual step.

1. Actions > Contribution tracker > Run workflow > main > seed, Apply unchecked.
2. Inspect the proposed issue hierarchy. Run seed with Apply checked to create it.
   Existing stable IDs are reused; repeated initialization does not duplicate tasks.
3. Run review, Branch ML-Axel, Apply unchecked to preview a real branch report.
4. Run review with Apply checked to publish the report and save its checkpoint.
5. Confirm `automatic_reviews: true` and `automatic_closures: true` on main.
6. Configure every area's `required_checks`. Autonomous closure remains blocked until
   every named check is completed successfully; no human approval step is involved.
7. Put `.github/workflows/component-ci.yml` on each active component branch so its exact
   required check runs on that branch's commits. It has read-only contents permission and
   receives no tracker or Gemini secrets.

Immediate push route:
- Put .github/workflows/component-branch-changed.yml on each component branch you want
  to notify immediately (through your own merge/copy workflow).
- A push runs that tiny signal job; it has no checkout, secrets, or write permissions.
- Its completion triggers Contribution tracker on the default branch using workflow_run.
- The trusted analyzer fetches the current branch head via the API, not untrusted
  artifacts or scripts from the signal job. It only accepts configured branch names.
- The signal can run before the main-side setup is merged, but no analysis starts
  until the receiver workflow exists on main and automatic_reviews is enabled.

Hourly fallback:
- At minute 23 each hour, the main workflow checks all configured branches.
- No workflow/script is needed on component branches for this route.
- Scheduled runs can be delayed by GitHub. It is a fallback, not an exact-time promise.
- This also catches pushes skipped during concurrency coalescing and later CI results.
- Remove schedule or change it to '23 */3 * * *' for less frequent polling.

You do NOT need to copy the tracker Python script, task plan, tracker tests, or overview
onto component branches. The optional signal workflow and read-only component CI workflow
are branch-local. Writers always run trusted main/default-branch code and share a
concurrency group. Never change the privileged job to execute component branch code.

## Workflow controls

Manual inputs: mode (seed/review), branch (blank reviews all), force, apply.
Use main in GitHub's workflow branch selector when applying writes. Before the workflow
exists on main, test locally as above; the newly added Run workflow button may not appear.
The manual writer skips dispatches selected from a non-default ref and explicitly checks
out default-branch code before receiving issue-write permission and the Gemini key.
Validation runs on pushes to CI/CD and main and on PRs into main without keys or issue writes.
After successful main validation, the trusted workflow assesses areas mapped to main.
Scheduled runs continue to refresh other mapped branches and later CI results.
An explicit local --repo is optional for this project. The Actions repository variable
GEMINI_MODEL can select another available model without a code change; the fallback is
gemini-3.8-flash. Gemini uses low thinking for this latency-sensitive classification and
has a 180-second response timeout. Retain your existing repository API-key secret.

## Current issue behavior

- Eight planned parents and 40 real subissues; seed creates 48 issues on a fresh repo.
- The proposal's owner names are coordination contacts, not assumed GitHub usernames.
- Active component branches are ML-Axel, backend-Dhrubo,
  feature/dynamic-sandbox-engine, and llm-threat-intelligence.
- Frontend, static analysis, documentation, and integration assess filtered evidence on
  main from a configured historical baseline.
- Subsequent seed runs repair missing links and synchronize only the generated target-branch
  line; human notes and issue state are preserved.
- Assessments are no_evidence, in_progress, review_needed, or complete. Complete requires
  concrete code or documentation evidence and at least one path in the current comparison.
- With automatic_closures false, completion candidates are reported but not changed.
- With automatic_closures true and Apply checked, the tracker posts an evidence comment
  and closes an eligible open subissue only after every exact `required_checks` entry for
  that area has a completed, successful check run on the reviewed commit. A notification,
  unrelated lint job, pending run, skipped run, or failed run cannot authorize closure.
  Conflicting runs with the same required name also block closure; app, suite, and run
  identities remain in the review fingerprint.
- Only mapped tracker subissues can close automatically. Parent and unrelated issues never
  close automatically, and the tracker never assigns, reopens, deletes, or relabels issues.
- Old PR-based summary comments remain historical; new branch comments are separate.

## Evidence and limits

Only changed-file patches and previous reports are supplied, not full source snapshots.
A missing change is not proof that a feature is missing. CI summaries are tied to the
head SHA and do not include test logs or certify all acceptance criteria. Exact required
check names make CI a deterministic closure gate, while Gemini still evaluates whether
changed evidence satisfies each task. Previous AI claims are historical context, not
independently verified evidence.

Automatic completion is deliberately stricter than progress reporting: inherited report
paths alone cannot support complete. At least one cited path must be present in the current
comparison, which is why the first closure-enabled assessment of an existing branch should
use Force. The tracker rechecks the branch head, required CI results, and the child's stable
task marker immediately before writing. Completion comments are reused, closure is
idempotent, and closed issues are not automatically reopened. Seed synchronization also
aborts rather than overwriting an issue body changed after enumeration.

Maximum about 80,000 patch characters and 150,000 total context characters. Binary,
large, and excluded patches are counted as omitted; GitHub may truncate patches too.
At 300 changed files the compare API may be capped, so the script refuses to publish or
advance the checkpoint. Split the work or extend collection before attempting that case.
Other omissions are disclosed but do not prevent publishing; use --force after adjusting
collection limits if you need to reassess previously omitted evidence.

Basic secret-related filename filtering is not a secret scanner. Avoid committing keys
or confidential data. Gemini receives no GitHub credentials or write tools. Validate
structured output before publishing; a model cannot select unrelated issues to edit.
Quota errors do not trigger paid fallback or retries. All-branch runs stop on quota
errors; completed earlier reports remain valid, and a later run skips unchanged work.
Missing GitHub resources in an all-branch run are reported rather than closing issues.
Hourly Actions jobs still consume private-repository minutes even when Gemini is skipped.

## Verification

Local mocked tests cover initialization idempotency, dry-run non-mutation, native subissue
links, report and plan validation, current-evidence completion, closure rollout controls,
completion comments and idempotency, oversized-report protection, first branch review,
incremental comparison, comment reuse, force refresh, rewritten history, stale SHA
rejection, quota checkpoint protection, comparison caps, branch marker isolation,
required-CI closure gating, shared-branch dispatch, historical baselines, and path filtering.
The suite also covers delayed same-SHA CI success, conflicting duplicate checks, CI changes
during analysis, concurrent issue edits, workflow check producers, and trusted manual dispatch.
Live autonomous closure and automatic Actions events still need verification in your repo.
