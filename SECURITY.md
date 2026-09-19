# Security

## Security philosophy

This project treats agentic systems as software that crosses trust boundaries, not as a single prompt.

The design separates:

- untrusted public evidence
- trusted/private seller knowledge
- model-generated suggestions
- deterministic application rules
- consequential external actions

## Threat model

Primary risks considered by the application include:

- prompt injection in public web pages
- malicious or misleading retrieved text
- hallucinated seller capabilities
- unauthorized Knowledge Base mutation
- unsafe or duplicate outbound email actions
- accidental credential exposure
- model output escaping expected score ranges

## Implemented controls

### Untrusted evidence handling

Public web text is treated as reference data rather than executable instructions.

The security layer can detect suspicious instruction patterns, classify risk, neutralize high-risk content, and emit structured security events.

### Private-evidence requirement

The workflow does not calculate seller-prospect fit when no relevant private Knowledge Base evidence is available.

This reduces the chance that the model invents capabilities based only on prospect research.

### Deterministic business rules

The model proposes constrained scoring components, while Python performs range validation and the final score calculation.

Action decisions are validated server-side.

### Human-in-the-loop approval

Email delivery is a consequential side effect.

The workflow pauses before sending and requires stored human approval before the send path can proceed.

### Authentication and authorization

Protected application routes require authentication. Knowledge Base mutation routes are role-aware.

Authentication tokens are stored using an HttpOnly cookie.

### Send-path safeguards

The outbound email path includes approval validation and idempotency protections designed to reduce unintended duplicate actions.

### Secret handling

Real secrets must remain in local environment files or deployment secret stores.

The repository ignores:

- `.env`
- `.env.*` except explicit example templates
- Gmail OAuth `credentials.json`
- Gmail OAuth `token.json`
- uploaded private Knowledge Base files
- local logs

Example environment files must contain placeholders only.

## Security checks before committing

Before pushing code:

```bash
git status
git diff --cached
```

Verify that no API key, password, OAuth file, JWT secret, private document, or personal test data is staged.

## Reporting a vulnerability

Do not post credentials, tokens, or exploit details in a public issue.

Use GitHub's private security reporting/advisory mechanism when available, or contact the repository owner privately through their GitHub profile.

## Scope

This is a portfolio/engineering project and should not be interpreted as a formally audited production security system.

Production deployment would require additional controls such as managed secret storage, hardened identity/access management, network policy, rate limiting, backups, centralized audit retention, dependency scanning, and infrastructure monitoring.
