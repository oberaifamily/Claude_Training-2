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
