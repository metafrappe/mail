# Metafrappe v16 deployment

This branch keeps the standalone `mail` app available in the same bench catalog
as Frappe Suite. Install **either Mail or Suite on a site**, never both: their
DocType names overlap. Both installation orders are rejected explicitly.

## Compatibility changes

- The standalone settings module is `Standalone Mail` (`mail.standalone_mail`).
  Suite continues to own its separate `Mail` module. An ownership-checked
  pre-model-sync patch migrates older standalone Mail metadata without changing
  Suite's code or module ownership.
- Bun 1.4.2 is a local build dependency. The root Yarn and frontend Bun lockfiles
  are committed; installation does not install Bun globally.
- Production assets use the Git-pinned Frappe UI package and its dependencies.
  Source builds outside a bench use port 9000 for development realtime; builds
  inside a bench read only the public socket port from its common config.
- A site with no configured Stalwart server can install and migrate its schema
  without downloading Stalwart CLI. Configured installations still refresh the
  CLI and surface failures.

## Validation

The compatibility workflow runs on Python 3.14.6, Node 24.20.0 and MariaDB 10.6.25,
using the deployed Frappe 16.33.1, ERPNext 16.34.2 and HRMS 16.18.1 commits.
Mail and Suite coexist in the test bench with separate disposable sites.
The workflow checks dependency resolution with the existing 54-app requirements,
site installation, repeated migrations, production assets, controller loading,
bootstrap data, legacy module migration, namespace isolation and same-site
installation guards. See `mail/tests/v16_smoke.py` for focused regression checks.

## Mail service configuration

Installing this app does not provision a working mail service. Connect a
JMAP-compatible backend, or configure Stalwart and its domain/DNS settings as
described in the upstream README. Actual inbound/outbound delivery, credentials
and DNS must be verified separately. Automated compatibility tests do not send
real email.
