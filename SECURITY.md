# Security Policy

## Supported versions

Mirage is pre-1.0 and deployed as a single `main` branch. Security fixes land on `main`.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report them privately via
[GitHub Security Advisories](https://github.com/bhuwanb23/mirage/security/advisories/new).

Include as much of the following as you can:

- Description of the vulnerability and its impact
- Steps to reproduce (proof of concept, request/response samples)
- Affected component (`backend`, `frontend`, `bot`, `ml`)
- Any suggested fix, if you have one

You'll get an acknowledgement within a few days. We'll work with you on a fix and credit you in the advisory unless you prefer otherwise.

## Scope notes

- **No real user data.** Fire drills, honeypots, and test fixtures use synthetic identities. If you find a path where real personal data could leak between users, that's a high-severity report.
- **LLM prompt injection** in analyzer endpoints is in scope — the backend accepts untrusted text/URL/image/voice by design.
- **Secrets.** Never commit API keys. `.env` files are gitignored; if you find one tracked in history, report it so we can rotate and scrub.
- **Out of scope:** denial of service against the deployed demo, vulnerabilities in third-party dependencies already disclosed upstream (link the advisory instead).

## Responsible disclosure

We ask that you give us a reasonable window to fix an issue before public disclosure. We aim to ship a fix or mitigation within 14 days for high-severity issues, and will coordinate timing with you.
