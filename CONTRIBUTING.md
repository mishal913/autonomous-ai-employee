# Contributing

Thanks for taking an interest in the Autonomous AI Employee project.

## Development setup

### Prerequisites

- Python 3.11
- Node.js 24
- Docker Desktop / Docker Engine with Compose
- Git

### Environment files

Copy the safe templates:

```text
.env.example        -> .env
.env.docker.example -> .env.docker
```

Replace `CHANGE_ME` values locally. Never commit real credentials.

### Start the stack

```bash
docker compose --env-file .env.docker up -d --build
```

### Backend tests

```bash
python -m pytest -q
```

### Frontend build

```bash
cd frontend
npm ci
npm run build
```

## Branch workflow

Use a focused branch for non-trivial changes:

```bash
git checkout -b feature/short-description
```

Keep commits small and descriptive.

Examples:

```text
Add RAG evidence gate
Improve workflow observability
Fix Knowledge Base document IDs
```

## Pull requests

A good pull request should explain:

- what changed
- why the change is needed
- how it was tested
- whether security, persistence, or external actions are affected
- screenshots for meaningful UI changes

GitHub Actions should pass before merge.

## Code-quality expectations

- preserve server-side validation for consequential actions
- do not bypass the private RAG evidence gate
- keep external web evidence explicitly untrusted
- avoid hard-coded credentials or personal data
- add/update tests for backend behavior changes
- run the frontend production build for UI changes
- keep user-facing failure messages actionable

## Secrets and private data

Do not commit:

- `.env` files
- API keys
- passwords
- JWT secrets
- Gmail OAuth credentials/tokens
- private Knowledge Base documents
- personal email addresses in portfolio screenshots

## Documentation

Update the README or architecture/security documentation when a change affects system behavior, setup, trust boundaries, or deployment.
