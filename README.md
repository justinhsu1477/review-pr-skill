# review-pr

A Claude Code skill for reviewing GitHub pull requests and GitLab merge requests. Each review
starts from the repo's own review guide, `REVIEW.md`. It reports only findings it could back
with evidence, saves its comments as an unsubmitted review you can edit and submit, and writes
what it learned back to `REVIEW.md` so the next review starts further ahead.

It never submits, approves, requests changes, resolves, merges or pushes. Saving drafts and
editing `REVIEW.md` each wait for your yes.

## How a review runs

1. **Collect.** PR metadata through `gh` / `glab`. The head is read from a detached worktree,
   so your checkout is never touched. State goes to `.git/review-pr/<id>/`, which is never
   committed and is still there in the next session.
2. **Prefill.** `REVIEW.md`, nested `REVIEW.md` / `.cursor/BUGBOT.md`, and `AGENTS.md`,
   `CLAUDE.md`, `CONTRIBUTING.md`, all read from the **base** branch. A PR is never reviewed
   by rules it adds itself.
3. **Understand, then review** on five axes: correctness, security and boundaries, intent
   and spec, structure and reuse, repo rules. Diffs over 300 changed lines get one subagent
   per axis.
4. **Verify.** Each finding is checked at the cited line and needs evidence: a failing input,
   a broken caller, or a quoted rule. Existing PR threads (humans, Copilot, Bugbot) are read
   only after this independent pass, and points already raised there are dropped.
5. **Report.** A verdict (🟢 / 🟡 / 🔴), a walkthrough grouped by core logic, wiring and
   boilerplate, at most 7 findings each with a draft comment, what was dropped and why,
   `REVIEW.md` proposals, and what was not checked.
6. **Hand off.** You choose: save the drafts on the PR, write the proposals to `REVIEW.md`,
   both, or neither.

Re-reviews after new commits are incremental. They re-check every earlier commented
finding and mark it FIXED or still open.

## REVIEW.md

```markdown
## Learned

### Bare except in job workers is intentional

- Kind: false-positive
- Paths: `app/jobs/**`
- Confidence: recurring
- Skip when: a worker loop wraps one unit of work in `except Exception` and logs it.
- Do not skip when: the handler swallows the error without logging, or the code is outside `app/jobs/`.
- Source: PR #41, PR #57
```

There are three kinds of entry:

- `rule`: a class of bug worth checking every time.
- `false-positive`: a pattern that was flagged and turned out fine. A matching finding is
  dropped unless one of its `Do not skip when` conditions holds.
- `fact`: how the repo works. It goes into every reviewer's brief.

Confidence rises only when a person adds evidence: the author fixed it, or explained it and
the code proves it. An entry being applied is not evidence for it. No `false-positive` entry
covers security, auth, data-loss or money findings. See
[`skills/review-pr/review-guide.md`](skills/review-pr/review-guide.md).

## Drafts on the PR

`scripts/post_drafts.py` turns `comments.json` into a GitHub pending review or GitLab draft
notes, which nobody else sees until you submit them. It is a dry run unless you pass
`--post`. A comment whose line is outside the diff goes into the review body instead of
failing the whole request.

## Install

As a plugin:

```
/plugin marketplace add justinhsu1477/review-pr-skill
/plugin install review-pr@review-pr-skill
```

Or as a personal skill:

```bash
git clone https://github.com/justinhsu1477/review-pr-skill
ln -s "$PWD/review-pr-skill/skills/review-pr" ~/.claude/skills/review-pr
```

Requires `git`, Python 3.9+, and `gh` (GitHub) or `glab` (GitLab, with `GITLAB_HOST` set for
self-hosted instances).

Then ask for a review: "review this PR https://github.com/o/r/pull/123", or `/review-pr`.

## Prior art

- Cursor Bugbot: `.cursor/BUGBOT.md` found from the changed files upward, config read from the
  base branch, rules learned from merged PRs.
- Cursor's `pr-review-canvas`: grouping a diff by reviewer value, and an example trace for
  hard-to-predict changes.
- Cursor's thermos reviews: diff-scoped findings, no unfinished research, and other reviewers'
  threads read only after your own pass.

The skill was written test-first: a review with no skill, the same review with it, then a
re-review, each on a fixture repo with planted issues.

## Development

```bash
python3 -m unittest discover -s tests
```

## License

MIT
