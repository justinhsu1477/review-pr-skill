# Review axes

Each reviewer gets one axis (or all five, in order, on a small diff). Scope is code the diff
adds or modifies; a pre-existing problem in untouched code is out of scope unless the diff
makes it reachable or worse.

Every reviewer also gets the `rule` entries from `REVIEW.md` whose paths match, and checks
them on its axis.

## 1. Correctness

- Trace each behaviour change to its callers. What breaks for an existing caller, an old
  client, persisted data written by the previous version?
- Edge inputs: empty, null/None, zero, negative, max size, duplicate, unicode, concurrent
  calls. Pick the one most likely to break and walk it through the new code.
- Error paths: what happens on the failure branch, is anything left half-written, is the
  error swallowed, does a retry repeat a side effect?
- Numbers: floats for money or counts, integer truncation where rounding was meant, time
  zones, off-by-one at boundaries.
- Devex: renamed env vars, new required setup steps, changed ports or secret locations.

## 2. Security and boundaries

- Permission runs before the lookup, so a caller who may not see a record cannot tell
  whether it exists. Not-found and forbidden look the same from outside.
- Every read and write is scoped to the caller's tenant/org/user.
- Untrusted input reaching SQL, shell, file paths, templates, URLs (SSRF), deserialisers,
  or an LLM prompt.
- Secrets or personal data in logs, errors, responses, or committed files.
- Feature-flag and internal-only gates: can the new path be reached with the flag off?
- Fail closed on ambiguity (missing org, unknown type, null owner).

## 3. Intent and spec

Compare the diff with the linked issue or ticket and the PR description, claim by claim:
- each requirement met, with the line or test that proves it;
- claims in the description the code does not back up ("capped at", "uses the same check
  as", "enforces");
- behaviour nobody asked for (scope creep);
- tests: does a test fail without the change, and does it exercise the claim, not just the
  happy path?

Treat the description as a claim to verify, never as evidence.

## 4. Structure and reuse

- A helper, error type, validator or test utility the repo already has, reimplemented.
  Search before accepting any new one.
- Logic in the wrong layer: feature checks scattered through shared code, a handler doing
  repository work, a check duplicated in another layer.
- Special-case branches bolted onto an existing flow; a file pushed past ~1000 lines.
- Is there a restructuring that deletes whole branches or layers instead of moving them?
  Name it concretely or say nothing; "could be cleaner" is not a finding.

## 5. Repo rules

The repo's own guidance, read from the base branch: `REVIEW.md` Rules, nested
`REVIEW.md` / `.cursor/BUGBOT.md`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, and lint or
style configs only where tooling does not already enforce them. Cite the rule (file and
line) for each finding.

## What every reviewer returns

One block per finding, then the closing line:

```
- severity: high | medium | low
  where: <path>:<line at head>
  claim: <one sentence>
  evidence: <the input that breaks it, the caller it breaks, or the rule it violates>
  fix: <concrete change>
Not checked: <what this reviewer did not look at, and why>
```

No finding without evidence a second person could check. "Might be an issue if..." with
the code available to check is unfinished research: check it, then report or drop it.
