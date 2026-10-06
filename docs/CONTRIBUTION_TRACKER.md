# Contribution tracker: branch-based revision

No pull request is needed. Each configured branch has one persistent progress comment
under its work-area parent issue. Real GitHub subissues remain independently claimable.

## Update your CI/CD branch

Replace these files from this package:

- scripts/issue_tracker.py
- .github/workflows/contribution-tracker.yml
- tests/contribution_tracker/test_tracker.py
- docs/CONTRIBUTION_TRACKER.md

Add:

- .github/workflows/component-branch-changed.yml
- tests/contribution_tracker/test_branches.py

KEEP your reviewed .github/issue-plan.json and docs/project-overview.md. Copies are
included for a fresh install, but no configuration change is required by this revision.
The script accepts the existing plan unchanged. No Git operations were performed for you.
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

    python scripts/issue_tracker.py review --branch ML-Diego
    python scripts/issue_tracker.py review --branch "sandbox/telemetry---vinny-&-Joaquin"

For all configured branches:

    python scripts/issue_tracker.py review --all

To deliberately ignore the previous checkpoint and reassess from the common ancestor:

    python scripts/issue_tracker.py review --branch ML-Axel --force

API failures do not publish a result or advance its checkpoint. Dry runs also never
advance checkpoints. The --apply option remains restricted to default-branch Actions.

## What is compared

First published review: compare the component branch with its common ancestor with the
repository's default branch. It sees changes introduced on that branch, not all existing
files inherited from main. On later reviews, compare the last successfully published SHA
with the latest branch SHA and include the previous report as historical context.
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

Unchanged branch/task/check context skips Gemini. Task assignments, relevant CI results,
overview changes, or merge containment changes can refresh the report even without a
new component commit. Use --force if you need an explicit full reassessment.

## Automatic updates after you merge the setup

The plan's automatic_reviews setting stays false until you enable it. Manual reviews
are available regardless of that setting. Initialization is still a separate manual step.

1. Actions > Contribution tracker > Run workflow > main > seed, Apply unchecked.
2. Inspect the proposed issue hierarchy. Run seed with Apply checked to create it.
   Existing stable IDs are reused; repeated initialization does not duplicate tasks.
3. Run review, Branch ML-Axel, Apply unchecked to preview a real branch report.
4. Run review with Apply checked to publish the report and save its checkpoint.
5. When ready, set automatic_reviews: true in .github/issue-plan.json on main.

Immediate push route:
- Put ONLY .github/workflows/component-branch-changed.yml on each component branch
  you want to notify immediately (through your own merge/copy workflow).
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

You do NOT need to copy the Python script, task plan, tests, or overview onto component
branches. Only the small optional signal file is branch-local. Writers always run trusted
main/default-branch code and share a concurrency group. Never change the privileged job
to execute component branch code. Standard application CI remains separate.

## Workflow controls

Manual inputs: mode (seed/review), branch (blank reviews all), force, apply.
Use main in GitHub's workflow branch selector when applying writes. Before the workflow
exists on main, test locally as above; the newly added Run workflow button may not appear.
Validation still runs on pushes to CI/CD and PRs into main without keys or issue writes.
An explicit local --repo is optional for this project. GEMINI_MODEL can select another
available model; default gemini-2.5-flash. Retain your existing repository API-key secret.

## Current issue behavior

- Eight planned parents and 40 real subissues; seed creates 48 issues on a fresh repo.
- The proposal's owner names are coordination contacts, not assumed GitHub usernames.
- Actual mapped branches: ML-Axel, ML-Diego, backend-Dhrubo,
  sandbox/telemetry---vinny-&-Joaquin, and dev-branch (provisional integration mapping).
- Confirm the sandbox naming discrepancy: proposal says Vincent/Jarrel; branch says
  Vinny/Joaquin. No account assignments are inferred.
- Unmapped areas can still have seeded issues; add their branch names once confirmed.
- Subsequent seed runs repair missing links but preserve existing issue text and state.
- Status assessments are suggestions in the branch report, not automatic closures.
- This version never assigns, closes, reopens, deletes, or relabels issues automatically.
- Old PR-based summary comments remain historical; new branch comments are separate.

## Evidence and limits

Only changed-file patches and previous reports are supplied, not full source snapshots.
A missing change is not proof that a feature is missing. CI summaries are tied to the
head SHA and do not include test logs or certify all acceptance criteria. Previous AI
claims are historical context, not independently verified evidence.

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

20 local mocked tests pass: initialization idempotency, dry-run non-mutation, native
subissue links, report validation, first branch review, incremental comparison, comment
reuse, force refresh, rewritten history, stale SHA rejection, quota checkpoint protection,
comparison cap, and branch marker isolation. Workflow YAML is parsed locally.
Live Gemini/GitHub execution and Actions events still need verification in your repo.
