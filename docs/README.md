# Documentation index

Read `../README.md` first (what the app is, quick start, recent work log),
`../AGENTS.md` for the short rules an AI agent must follow, then come back
here. Each file below is self-contained and cross-links the others.

| # | File | Covers |
| --- | --- | --- |
| 01 | [01-architecture.md](01-architecture.md) | Stack, `settings.py`, middleware, request flow |
| 02 | [02-data-model.md](02-data-model.md) | Every model and field, relationships, Access quirks |
| 03 | [03-urls-and-views.md](03-urls-and-views.md) | Every URL, view, parameter and POST endpoint |
| 04 | [04-ui-and-templates.md](04-ui-and-templates.md) | Templates, partials, the Win95 CSS system, JS |
| 05 | [05-access-data-pipeline.md](05-access-data-pipeline.md) | Access import, field map, contact cleaning |
| 06 | [06-dashboard.md](06-dashboard.md) | How the statistics screen is computed and rendered |
| 07 | [07-business-workflow.md](07-business-workflow.md) | RFQ → tender → vendor list, statuses, roles |
| 08 | [08-auth-and-access-control.md](08-auth-and-access-control.md) | LDAP/AD, `EmployeeAccess`, local admin |
| 09 | [09-internationalization.md](09-internationalization.md) | EN/AR, translation workflow |
| 10 | [10-testing.md](10-testing.md) | The test scripts and manual verification |
| 11 | [11-operations.md](11-operations.md) | Run, back up, restore, troubleshoot, gotchas |
| 12 | [12-deployment.md](12-deployment.md) | nginx + systemd + gunicorn serving `cb.alma.local`, incident log, rollback |

## If you are troubleshooting, start here

| Symptom | Go to |
| --- | --- |
| `504 Gateway Time-out` / login hangs | [12-deployment.md](12-deployment.md) §4.2 and §8 |
| App not reachable at `cb.alma.local` | [12-deployment.md](12-deployment.md) §1, §8 |
| Static assets 403/404 or stale CSS | [11-operations.md](11-operations.md) *Static files*, [12](12-deployment.md) §8 |
| Restore a database / take a backup | [11-operations.md](11-operations.md) *Database* |
| Re-import from the `.accdb` files | [05-access-data-pipeline.md](05-access-data-pipeline.md) |
| LDAP/AD login rejected | [08-auth-and-access-control.md](08-auth-and-access-control.md), [12](12-deployment.md) §4.2 |
| New Arabic string not showing | [09-internationalization.md](09-internationalization.md) |
