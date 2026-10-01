# Contribution tracker: first implementation

## Purpose

Help floating contributors find relevant unassigned work and see evidence of progress.
One parent issue per work area; real GitHub subissues are independently claimable tasks.
The owner list comes from the capstone proposal. Display names are not GitHub usernames,
so the initializer does not assign accounts automatically.

## Included files

- .github/workflows/contribution-tracker.yml: validation, manual operations, and gated automatic reviews.
- .github/issue-plan.json: eight parents, 40 general tasks, stable IDs, and actual known branch mappings.
- scripts/issue_tracker.py: standard-library-only GitHub and Gemini integration.
- docs/project-overview.md: product context extracted from the proposal.
- tests/contribution_tracker/test_tracker.py: mocked tests; no keys, network, or real issue writes.

This is a fresh replacement design. Do not run an older gemini-tracker workflow alongside
this one after rollout; disable the old workflow yourself if it still exists. Existing
issues from older trackers are not changed or adopted by title matching.

## On your CI/CD branch

Copy the included files into your repository root without replacing unrelated files.
Run locally from the root:

    python scripts/issue_tracker.py validate
    python -m unittest discover -s tests/contribution_tracker -v

Pushing to CI/CD runs these checks automatically. Opening a PR to main also runs them.
No API keys are required for these validation runs and they never create issues.
The workflow's push filter uses the exact branch name CI/CD; change it if you choose
another name. You control all commits, branches, pushes, and merges.

For a live seed preview before merging, set GH_TOKEN to a GitHub credential with issue
read access in your terminal, then run:

    python scripts/issue_tracker.py seed --repo VinnyBitties/CS-4398-Project

A live Gemini preview additionally needs GEMINI_API_KEY, an existing component PR number,
and a GitHub token able to read PRs, checks, and statuses:

    python scripts/issue_tracker.py review --repo VinnyBitties/CS-4398-Project --pr 123

Replace 123 with a real mapped PR number. Do not paste keys into source files or commits.
Seed previews use no Gemini calls. Review previews use Gemini quota but make no GitHub writes.
The --apply flag is deliberately restricted to default-branch GitHub Actions runs.

## After YOU merge the reviewed setup into main

GitHub normally needs workflow_dispatch present on the default branch before showing
the Run workflow button for a newly introduced workflow.

1. Confirm GEMINI_API_KEY is a repository Actions secret. GEMINI_MODEL is an optional
   repository variable; the default is gemini-2.5-flash. Keep a free-tier project and
   no paid fallback; availability and quotas depend on your Google project.
2. Actions > Contribution tracker > Run workflow. Use main, mode seed, apply unchecked.
   Read the run's Summary to review the proposed parents, children, and relationships.
3. Review the task plan. Run seed again with apply checked to create the issues and
   link actual subissues. This creates 48 issues on first successful application.
   Later runs reuse stable markers and repair missing links without overwriting human
   descriptions. If task scope changes, edit existing issues as well: seeding does not
   synchronize previously created issue text or delete removed tasks.
4. Use mode review, enter a mapped component PR number, and leave apply unchecked.
   Check the AI report in the Summary, including omitted diff files and CI evidence.
5. Run that review with apply checked to post/update one bot comment on the parent
   issue. This does not change subissue status, assignees, labels, or descriptions.
6. Once satisfied, set automatic_reviews to true in .github/issue-plan.json on main.
   Creation and updates of mapped same-repository PRs into main then refresh reports,
   including draft PRs. Closed PRs also receive a final assessment; no task auto-closes.

Writes use the workflow's GITHUB_TOKEN with issues: write. Reading check results needs
checks: read and statuses: read, both declared in the workflow. Organization policy
can still prevent these operations. The Gemini key is never supplied to GitHub comments.

## Branch mappings

Known branches mapped during preparation:

- ML-Axel and ML-Diego -> Machine learning (shared parent; no invented division of work).
- backend-Dhrubo -> Backend services and orchestration.
- sandbox/telemetry---vinny-&-Joaquin -> Dynamic analysis and sandbox.
- dev-branch -> Integration and contribution visibility (provisional; confirm this role).

The proposal names Vincent/Jarrel for dynamic analysis, while the observed branch names
Vinny/Joaquin. Verify those display names with the team; no GitHub identities are assigned.
Frontend, LLM, static analysis, and documentation have empty branch lists until confirmed.
Their backlog issues can still be created. Add exact branch names when ready. Each branch
maps to one parent, but a parent can have several branches. CI/CD is intentionally unmapped:
its changes are validated rather than analyzed as application progress.

## What the AI sees and does

Each review sends the trusted project overview, task criteria/current issue text,
PR description, bounded cumulative PR diff, and CI check results at the PR head SHA.
Subissue assignees/state are current GitHub data. This first version does not read the
whole codebase, issue comment discussions, optional branch plans, or CI log files.
It reports suggested no_evidence, in_progress, or review_needed assessments and next steps.
Closed tasks remain closed. Unassigned tasks are highlighted but not guaranteed unblocked.

A report is one persistent comment per PR under the work-area parent. Multiple owner PRs
produce separate comments rather than overwriting each other's progress. No hidden task
state database is maintained. Stable HTML markers identify seeded issues and bot comments.
Do not remove those markers; titles can change without losing identity.

The model cannot choose arbitrary issue operations. Python validates known task IDs,
complete coverage, statuses, and evidence paths before writing a comment. New suggestions
stay in the report rather than becoming issues automatically. The writer rechecks PR head
SHA/state before publishing. Manual and automatic writer jobs share a concurrency group.

## Current limits

- PRs must be from this repository and use a configured head branch. Direct pushes with
  no PR do not trigger review. Open draft PRs early for visibility.
- Only diffs are supplied, not surrounding source. Missing evidence does not imply a
  feature is absent. A future iteration can fetch selected surrounding files if needed.
- About 80,000 patch characters and 150,000 total context characters maximum. Omitted
  binary/large/excluded files are counted. GitHub patches can themselves be truncated.
- Common secret-related filenames and lockfiles are excluded; this is not a secret scanner.
- Tests added and passing CI checks do not prove all acceptance criteria were met.
- No automated closing, reopening, assignment, or labels yet. Keep explicit completion
  decisions with the team. This is intentionally the first small, reviewable implementation.
- The initializer creates all planned areas, including those without mapped branches.
- Closed issues with matching markers are reused, not recreated or reopened.
- Quota failures stop that run without a paid fallback or automatic retries.
- Initializers may stop partially if an API call fails; rerun to reuse existing issues and
  repair missing links. Concurrent manual CLI writers are not supported.

## Security boundary

Validation runs branch code with read-only access and no Gemini secret. The privileged
pull_request_target job explicitly checks out main and treats PR content as data; never
change that checkout to the PR head or execute malware/sandbox jobs in this writer.
Normal tests and sandbox execution belong in separate appropriately isolated workflows.

## Verification performed

Local tests cover plan validation, dry-run non-mutation, idempotent issue creation,
partial-seed repair, duplicate marker rejection, evidence validation, and report rendering.
No live Gemini requests or GitHub issue writes were performed while preparing this package.
