#!/usr/bin/env python3
"""Save review comments as an unsubmitted PR/MR review (GitHub pending review or
GitLab draft notes). Nothing becomes visible to anyone else until the reviewer
submits it in the web UI.

Dry run by default: prints the API calls it would make. Pass --post to send.

Usage:
  python3 post_drafts.py --comments comments.json --diff pr.diff [--post]

comments.json:
  {
    "forge": "github" | "gitlab",
    "repo": "owner/name"            # GitLab: full project path, e.g. group/sub/proj
    "number": 88,                   # PR number / MR iid
    "head_sha": "<sha>",
    "base_sha": "<sha>",            # GitLab only (diff_refs.base_sha)
    "start_sha": "<sha>",           # GitLab only (diff_refs.start_sha), defaults to base_sha
    "summary": "optional review body",
    "comments": [{"path": "src/a.py", "line": 42, "body": "..."}]
  }

`line` is a line number in the new (head) version of the file. A comment whose
line is not inside a diff hunk cannot be anchored; it is folded into the review
body (GitHub) or saved as a general draft note (GitLab) with its path:line.
GitLab: set GITLAB_HOST for self-hosted instances.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.parse

HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def parse_diff(text):
    """Map new_path -> {"old_path": str, "lines": {new_line: old_line_or_None}}.

    old_line is None for added lines and the old line number for context lines.
    """
    files, cur, old_path = {}, None, None
    old_no = new_no = 0
    in_hunk = False
    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            cur, old_path, in_hunk = None, None, False
            continue
        # File headers only appear before a file's first hunk; inside a hunk a
        # line like "--- x" is a removed "-- x" (an SQL comment, say).
        if not in_hunk:
            if raw.startswith("--- "):
                p = raw[4:].strip()
                old_path = None if p == "/dev/null" else p.removeprefix("a/")
                continue
            if raw.startswith("+++ "):
                p = raw[4:].strip()
                if p == "/dev/null":
                    cur = None
                else:
                    new_path = p.removeprefix("b/")
                    cur = files.setdefault(
                        new_path, {"old_path": old_path or new_path, "lines": {}}
                    )
                continue
        m = HUNK.match(raw)
        if m:
            old_no, new_no, in_hunk = int(m.group(1)), int(m.group(2)), True
            continue
        if not in_hunk or cur is None:
            continue
        if raw.startswith("+"):
            cur["lines"][new_no] = None
            new_no += 1
        elif raw.startswith("-"):
            old_no += 1
        elif raw.startswith("\\"):
            pass
        elif raw.startswith(" ") or raw == "":
            cur["lines"][new_no] = old_no
            new_no += 1
            old_no += 1
        else:
            in_hunk = False
    return files


def split_comments(comments, files):
    anchored, loose = [], []
    for c in comments:
        f = files.get(c["path"])
        if f is not None and c["line"] in f["lines"]:
            anchored.append(c)
        else:
            loose.append(c)
    return anchored, loose


def run(cmd, stdin=None):
    p = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout


def api_json(tool, method, path, payload, post):
    """Send one JSON request through `gh api` / `glab api`, or print it."""
    if not post:
        print(f"[dry-run] {tool} api --method {method} {path}")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh)
        body = fh.name
    out = run([tool, "api", "--method", method, path, "--input", body,
               "-H", "Content-Type: application/json"])
    return json.loads(out) if out.strip() else None


def github(spec, anchored, loose, post):
    repo, num = spec["repo"], spec["number"]
    if post:
        me = run(["gh", "api", "user", "--jq", ".login"]).strip()
        reviews = json.loads(run(["gh", "api", "--paginate", "--slurp",
                                  f"repos/{repo}/pulls/{num}/reviews"]))
        flat = [r for page in reviews for r in page]
        if any(r["state"] == "PENDING" and r["user"]["login"] == me for r in flat):
            sys.exit("You already have a pending review on this PR. Submit or "
                     "discard it in the web UI, then rerun.")
    body = spec.get("summary", "").strip()
    if loose:
        extra = "\n".join(f"- `{c['path']}:{c['line']}` {c['body']}" for c in loose)
        body = f"{body}\n\n{extra}".strip()
    payload = {
        "commit_id": spec["head_sha"],
        "body": body,
        "comments": [{"path": c["path"], "line": c["line"], "side": "RIGHT",
                      "body": c["body"]} for c in anchored],
    }
    # No "event" field: GitHub keeps the review PENDING until the reviewer submits it.
    res = api_json("gh", "POST", f"repos/{repo}/pulls/{num}/reviews", payload, post)
    if res:
        print(f"Pending review saved: {res.get('html_url')}")


def gitlab(spec, files, anchored, loose, post):
    proj = urllib.parse.quote(spec["repo"], safe="")
    path = f"projects/{proj}/merge_requests/{spec['number']}/draft_notes"
    base = spec["base_sha"]
    start = spec.get("start_sha") or base
    notes = []
    if spec.get("summary", "").strip():
        notes.append({"note": spec["summary"].strip()})
    for c in anchored:
        f = files[c["path"]]
        pos = {"position_type": "text", "base_sha": base, "start_sha": start,
               "head_sha": spec["head_sha"], "old_path": f["old_path"],
               "new_path": c["path"], "new_line": c["line"]}
        old_line = f["lines"][c["line"]]
        if old_line is not None:
            pos["old_line"] = old_line
        notes.append({"note": c["body"], "position": pos})
    for c in loose:
        notes.append({"note": f"`{c['path']}:{c['line']}` {c['body']}"})
    for n in notes:
        api_json("glab", "POST", path, n, post)
    if post:
        print(f"Saved {len(notes)} draft notes. Submit them from the MR's review panel.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--comments", required=True)
    ap.add_argument("--diff", required=True, help="unified diff of the PR (base...head)")
    ap.add_argument("--post", action="store_true", help="send; default is a dry run")
    a = ap.parse_args()
    spec = json.load(open(a.comments, encoding="utf-8"))
    files = parse_diff(open(a.diff, encoding="utf-8").read())
    anchored, loose = split_comments(spec.get("comments", []), files)
    print(f"{len(anchored)} anchored on diff lines, {len(loose)} not on a diff line")
    if spec["forge"] == "github":
        github(spec, anchored, loose, a.post)
    elif spec["forge"] == "gitlab":
        if "base_sha" not in spec:
            sys.exit("GitLab needs base_sha (and start_sha) from the MR's diff_refs.")
        gitlab(spec, files, anchored, loose, a.post)
    else:
        sys.exit("forge must be github or gitlab")


if __name__ == "__main__":
    main()
