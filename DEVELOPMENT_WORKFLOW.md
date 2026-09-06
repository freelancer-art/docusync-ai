# Development Workflow

This checklist is the definition of done for every DocuSync implementation, bug fix, and refactor.

## Before Coding

1. Read the owning module, adjacent tests, and the relevant section of `PROJECT_PLAN.MD`.
2. State the behavior being changed, the local hypothesis about the owning code path, and the cheapest test that can disprove it.
3. Identify tenant, authentication, storage, background-task, and external-provider boundaries affected by the change.
4. Decide which documentation needs updating: `README.md`, `USER_MANUAL.md`, `FILES_USAGE.md`, environment examples, or the roadmap.

## While Coding

1. Keep the change scoped to the owning abstraction and preserve existing public APIs unless a contract change is intentional.
2. Add or update focused tests for the behavior, authorization boundary, failure mode, and relevant integration seam.
3. Add a concise module docstring when introducing a module and a docstring for public functions/classes whose behavior is not obvious from their names.
4. Use the project dependency manager (`uv`) for dependency changes. Update `pyproject.toml` and `uv.lock` together.
5. Use structured logging for diagnostics. Do not use `print()` in application code.
6. Never log passwords, access tokens, service-account JSON, API keys, or raw financial document contents.
7. Preserve tenant isolation and validate file signatures before storing or processing uploaded/imported content.
8. Inject cloud clients, LLM clients, queues, and storage clients so tests do not require live credentials or services.
9. Keep mutations explicit, authorized, auditable, and confirmation-protected where they are exposed to MCP or automation.

## Before Handoff

Run the complete quality gate:

```bash
uv sync
uv run --extra dev pytest -q
uv run --extra dev ruff check app tests
uv run --extra dev ruff format --check app tests
git diff --check
```

Also verify:

- the changed behavior has a focused test;
- API and connector changes have authorization and failure-path tests;
- configuration changes are represented in `.env` comments or documentation without adding secrets;
- user-visible behavior is documented in `USER_MANUAL.md`;
- file/module responsibilities are reflected in `FILES_USAGE.md`;
- scope and deferred work are reflected in `PROJECT_PLAN.MD`;
- production-only assumptions are called out explicitly;
- `git status` contains no generated database, upload, credential, or cache artifacts.

## Review Questions

- Can a client access another tenant's record, file URL, export, connector, or query result?
- Can malformed, oversized, or disguised files bypass validation?
- Does a failed dependency produce a useful structured log and safe response?
- Is retry behavior idempotent for uploads, workers, connector imports, and payments?
- Are external calls bounded, injectable, and covered by mock tests?
- Are sensitive arguments redacted from logs and MCP audit records?
- Are warnings, deprecations, and known test gaps recorded rather than ignored?

## Release Readiness

Before production deployment, additionally verify:

- `DEBUG=false` and strong secrets are configured through the deployment secret manager;
- database migrations are applied and backups are available;
- Redis/Celery health and storage availability are monitored;
- central log collection, metrics, tracing, and alerting are configured;
- OAuth refresh tokens and connector credentials are stored outside the application database;
- a rollback path and operational runbook exist.
