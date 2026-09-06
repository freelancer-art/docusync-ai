## Summary

<!-- What behavior changed and why? -->

## Validation

- [ ] `uv run --extra dev pytest -q`
- [ ] `uv run --extra dev ruff check app tests`
- [ ] `uv run --extra dev ruff format --check app tests`
- [ ] `git diff --check`

## Change Checklist

- [ ] Focused tests cover the changed behavior and failure paths.
- [ ] Authentication, authorization, and tenant isolation were reviewed.
- [ ] File signature, input size, and path safety were reviewed where relevant.
- [ ] External clients and storage are injectable; tests do not require live credentials.
- [ ] Application diagnostics use structured logging and redact secrets.
- [ ] Public modules/functions have concise purpose documentation where needed.
- [ ] `README.md` or `USER_MANUAL.md` was updated for user-visible behavior.
- [ ] `FILES_USAGE.md` was updated for new or moved modules.
- [ ] `PROJECT_PLAN.MD` was updated for scope, completion, or deferred work.
- [ ] No secrets, generated databases, uploads, or cache artifacts are included.

## Known Gaps

<!-- List warnings, deferred work, migrations, or follow-up tasks. Use "None" when there are none. -->
