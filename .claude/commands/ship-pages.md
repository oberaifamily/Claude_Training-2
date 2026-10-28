---
description: Scan for secrets, push to a GitHub repo, update README and About, deploy GitHub Pages, set up CI/CD.
argument-hint: <owner/repo or GitHub URL> [branch=main] [--dry-run]
allowed-tools: Bash(git:*), Bash(gh:*), Bash(curl:*), Bash(python3:*), Bash(mkdir:*), Bash(sleep:*), Read, Write, Edit, Glob, Grep
---

# /ship-pages

Publish this project to GitHub safely: secret scan, push, README, About section, GitHub Pages and a CI/CD workflow.

Input: `$ARGUMENTS`

Work through the steps in order. Stop at the first step that fails and say what to do. Report each step as done, skipped (already up to date) or needs a human.

## Rules that always apply

- Nothing leaves the machine until step 3 passes.
- Never print the value of a secret. Print the rule, file and line only.
- Never force-push, delete remote content, change repo visibility or change org settings.
- Never rewrite git history yourself. If a secret is in history, explain how to purge it and tell the user to rotate it.
- On any permission error (403, 404 on a repo that should exist, "Resource not accessible"), stop and report the fix. Do not retry in a loop and do not look for a workaround.
- Every file you create or update must be idempotent: if the content would not change, leave it alone and say "no changes".

## 1. Parse the input

- First word: `owner/repo` or a URL like `https://github.com/owner/repo(.git)`. Strip a trailing `.git` and `/`. Keep the exact capitalisation, because the Pages URL is case-sensitive.
- Optional `branch=NAME` (default `main`).
- Optional `--dry-run`: do steps 1, 2 and 3 for real (they only read), then print what steps 4 to 10 would do and stop. Change nothing.
- If no repo is given, ask the user for it and stop.

Call them OWNER, REPO and BRANCH below.

## 2. Preflight

- Confirm the working directory is inside a git repo (`git rev-parse --show-toplevel`). If it is not, run `git init -b BRANCH`.
- Confirm there is an `index.html` at the top level. If not, ask which folder is the site and use it as the publish folder.
- Show `git status --short`.
- Read the project (index.html, any existing README) so you can write an accurate README and About description later.

## 3. Sensitive-data gate

1. Write `scripts/secret-scan.py` from the "Secret scan script" section below (only if missing or different).
2. Make sure `.gitignore` contains at least these lines (append any that are missing, never remove lines):
   `.env`, `.env.*`, `!.env.example`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`, `*.tfstate`, `node_modules/`, `.DS_Store`.
3. Run `python3 scripts/secret-scan.py --history` from the repo root.
   - Exit 0: clean. Continue.
   - Exit 1: secrets found. Stop. List each finding (rule, file, line, masked). Tell the user to remove the value, rotate the credential and, if it is in history, purge it (for example with `git filter-repo`) before running this command again. Do not continue.
   - Exit 2: personal data needs a decision (emails, phone numbers, private IPs, internal hostnames). Show each finding and ask the user, for each, whether it is meant to be public. For each one they confirm, append a line `rule:path` to `.secret-scan-allow` (create it with a header comment if missing). Then run the scan again. Anything not confirmed means stop.
4. Check visibility: `gh repo view OWNER/REPO --json visibility,isPrivate`. If the repo is public (or does not exist yet), say plainly: everything pushed is world-readable and stays in history forever.
5. Report "No sensitive data found" only when the scan exited 0.

## 4. Remote

- If `origin` exists, set its URL to `https://github.com/OWNER/REPO.git`; otherwise add it.
- Run `git ls-remote origin`. If it fails with an access error, stop and give the fix from step 6.

## 5. README, workflow and ignore files

Create or update these files from the templates below. Use the project's real content, never placeholders left in.

- `README.md`: see "README template". Only rewrite the text between `<!-- ship-pages:start -->` and `<!-- ship-pages:end -->`. If the file exists without those markers, keep all existing text and add the managed block at the top after the first heading. The live-demo link in the block is `https://OWNER.github.io/REPO/`.
- `.github/workflows/pages.yml`: see "Workflow template". Replace `BRANCH` with the publish branch.
- Commit in separate commits, using the commit attribution the project or session requires: the secret-scan script and `.gitignore`/allow-list, then the README, then the workflow, and any uncommitted project changes first.

## 6. Push

- Run `git push -u origin BRANCH`. Retry only on network errors, up to 4 times, waiting 2, 4, 8 and 16 seconds.
- On a 403 or any access message, stop and print this fix: an owner of the OWNER account or org must install the Claude GitHub App for the repo at https://github.com/apps/claude/installations/select_target, or reconnect GitHub at https://claude.ai/customize/connectors?auth_start=github&auth_start_force=1. Then run the command again.
- If the remote branch has commits you do not have, fetch and rebase; never force-push.

## 7. GitHub Pages

- Try `gh api -X POST repos/OWNER/REPO/pages -f build_type=workflow`.
- If it returns 409 (already exists), update it: `gh api -X PUT repos/OWNER/REPO/pages -f build_type=workflow`.
- If the call is refused (permission error or "not permitted through this proxy"), do not retry. The workflow's `configure-pages` step with `enablement: true` will try to enable Pages itself. If that also fails, tell the user: Settings > Pages > Build and deployment > Source = GitHub Actions.
- The site URL is `https://OWNER.github.io/REPO/`.

## 8. About section

Set the repo description, homepage (the Pages URL from step 7) and topics, and update them in place if they already exist:

`gh repo edit OWNER/REPO --description "DESCRIPTION" --homepage "https://OWNER.github.io/REPO/" --add-topic TOPIC`

- DESCRIPTION: one sentence, under 120 characters, taken from the README title and summary.
- Topics: 3 to 6 lowercase topics that fit the project (for a single-page static app: `html`, `css`, `javascript`, `github-pages`, plus subject topics like `kanban`).
- If the call is refused, print the exact description, website and topics to paste under the gear icon next to "About" on the repo page. Say it needs a human.

## 9. Verify

- If `gh` can read runs: `gh run list --repo OWNER/REPO --workflow pages.yml --limit 1`, then `gh run watch` on it. Report the result and, if it failed, the failing job and the reason.
- Otherwise poll `curl -sI https://OWNER.github.io/REPO/` every 20 seconds for up to 3 minutes and report the status code.
- Confirm the About homepage equals the live URL: `gh repo view OWNER/REPO --json homepageUrl`.

## 10. Report

Give: the live URL, the repo URL, the secret-scan result, each step as done, skipped or needs a human, and any manual action left (for example enabling Pages or pasting About values). If the repo is private, note that GitHub Pages may need a paid plan.

---

## Secret scan script

Write this to `scripts/secret-scan.py`. The CI job runs the same file, so local and CI results match.

```python
#!/usr/bin/env python3
"""Scan a git repo for secrets and personal data before publishing.

Exit codes: 0 clean, 1 secrets found, 2 personal data needs confirmation.
Confirm personal data by adding "rule:path" lines to .secret-scan-allow.
Values are never printed in full.
"""
import fnmatch, os, re, subprocess, sys

ALLOW_FILE = ".secret-scan-allow"
SELF = "scripts/secret-scan.py"
MAX_BYTES = 2_000_000

SECRET_RULES = {
    "private-key": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "slack-token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "stripe-key": re.compile(r"\b[sr]k_live_[A-Za-z0-9]{16,}\b"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "url-credentials": re.compile(r"""\b[a-z][a-z0-9+.-]*://[^/\s:@"']+:[^/\s:@"']+@"""),
    "credential-assignment": re.compile(
        r"""(?i)\b(?:api[_-]?key|secret|passwd|password|access[_-]?token|auth[_-]?token)\b["']?\s*[:=]\s*["'][^"'\s]{8,}["']"""
    ),
}
REVIEW_RULES = {
    "email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?!example\.(?:com|org|net)\b|users\.noreply\.github\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
    "phone": re.compile(
        r"""(?i)(?:wa\.me/\+?\d{8,15}|tel:\+?\d[\d\s-]{7,}|\b(?:phone|mobile|whatsapp|tel)\w*["']?\s*[:=]\s*["']\+?[\d\s-]{8,}["'])"""
    ),
    "private-ip": re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
    "internal-host": re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:internal|corp|intranet)\b"),
}
BAD_NAMES = [
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*",
    "*.keystore", ".npmrc", ".netrc", "credentials.json", "service-account*.json", "*.tfstate",
]
OK_NAMES = [".env.example", ".env.sample", ".env.template"]


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def mask(value):
    return value[:4] + "..." + "(" + str(len(value)) + " chars)"


def bad_name(path):
    name = os.path.basename(path)
    if name in OK_NAMES:
        return False
    return any(fnmatch.fnmatch(name, pattern) for pattern in BAD_NAMES)


def load_allow():
    allowed = set()
    if os.path.exists(ALLOW_FILE):
        with open(ALLOW_FILE, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#"):
                    allowed.add(line)
    return allowed


def scan_line(line, path, where, lineno, found):
    for rule, pattern in SECRET_RULES.items():
        match = pattern.search(line)
        if match:
            found.append(("secret", rule, path, where, lineno, mask(match.group(0))))
    for rule, pattern in REVIEW_RULES.items():
        match = pattern.search(line)
        if match:
            found.append(("review", rule, path, where, lineno, mask(match.group(0))))


def scan_files(found):
    listing = git("ls-files", "-co", "--exclude-standard", "-z")
    if listing.returncode != 0:
        sys.exit("not a git repository")
    for path in filter(None, listing.stdout.split("\0")):
        if path == SELF or path == ALLOW_FILE or not os.path.isfile(path):
            continue
        if bad_name(path):
            found.append(("secret", "sensitive-filename", path, "files", 0, os.path.basename(path)))
            continue
        if os.path.getsize(path) > MAX_BYTES:
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        if b"\0" in data[:4096]:
            continue
        for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            scan_line(line, path, "files", number, found)


def scan_history(found):
    log = git("log", "--all", "-p", "-U0", "--no-color", "--format=commit:%h")
    if log.returncode != 0:
        return
    commit, path = "", ""
    for line in log.stdout.splitlines():
        if line.startswith("commit:"):
            commit = line[7:]
        elif line.startswith("+++ b/"):
            path = line[6:]
            if path != SELF and path != ALLOW_FILE and bad_name(path):
                found.append(("secret", "sensitive-filename", path, "history " + commit, 0, os.path.basename(path)))
        elif line.startswith("+") and not line.startswith("+++") and path not in (SELF, ALLOW_FILE):
            scan_line(line[1:], path, "history " + commit, 0, found)


def main():
    found = []
    scan_files(found)
    if "--history" in sys.argv:
        scan_history(found)
    allowed = load_allow()
    seen, secrets, reviews = set(), [], []
    for level, rule, path, where, lineno, shown in found:
        key = (rule, path, where, lineno)
        if key in seen:
            continue
        seen.add(key)
        if level == "review" and (rule + ":" + path) in allowed:
            continue
        (secrets if level == "secret" else reviews).append((rule, path, where, lineno, shown))
    for title, items in (("SECRET", secrets), ("REVIEW", reviews)):
        for rule, path, where, lineno, shown in items:
            place = path + (":" + str(lineno) if lineno else "")
            print("[" + title + "] " + rule + "  " + place + "  (" + where + ")  " + shown)
    if secrets:
        print("\n" + str(len(secrets)) + " secret finding(s). Remove, rotate and purge before publishing.")
        return 1
    if reviews:
        print("\n" + str(len(reviews)) + " item(s) of personal data. If meant to be public, add 'rule:path' to " + ALLOW_FILE + ".")
        return 2
    print("secret-scan: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## Workflow template

Write this to `.github/workflows/pages.yml`, replacing `BRANCH`. It scans for secrets and validates on every push and pull request, and deploys to GitHub Pages from BRANCH only. It stages a `_site` folder that leaves out dot-files, scripts and the README, so only site files are published.

```yaml
name: CI/CD

on:
  push:
    branches: [BRANCH]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Scan files and history for secrets and personal data
        run: python3 scripts/secret-scan.py --history

  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check the site entry point
        run: |
          test -s index.html
          grep -qi "<title>" index.html

  deploy:
    needs: [secret-scan, validate]
    if: github.event_name != 'pull_request' && github.ref == 'refs/heads/BRANCH'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    concurrency:
      group: pages
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
        with:
          enablement: true
      - name: Stage site files only
        run: |
          mkdir _site
          rsync -a --exclude='.*' --exclude='_site' --exclude='scripts' --exclude='README.md' ./ _site/
      - uses: actions/upload-pages-artifact@v3
        with:
          path: _site
      - id: deployment
        uses: actions/deploy-pages@v4
```

## README template

Fill every field from the real project. Keep everything outside the markers untouched.

```markdown
# PROJECT TITLE

<!-- ship-pages:start -->
ONE-SENTENCE DESCRIPTION.

[![CI/CD](https://github.com/OWNER/REPO/actions/workflows/pages.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/pages.yml)

**Live demo:** https://OWNER.github.io/REPO/

## Features

- 3 to 6 bullets taken from the project.

## Run locally

Open `index.html` in a browser. No build step or server is needed.

## Configuration

List each setting a user may change, with the constant name and where it is (for example the email in `FORMSUBMIT_ENDPOINT`). Never include real secrets.

## Deployment

Pushes to `BRANCH` run `.github/workflows/pages.yml`: secret scan, validation, then deploy to GitHub Pages. Run `python3 scripts/secret-scan.py --history` locally before pushing.
<!-- ship-pages:end -->
```
