# RyuClass Backoffice — AdminLTE 3.1.0

## Architecture

`/admin/` resolves to `backoffice.urls`, not `AdminSite.urls`.
All list/detail/create/edit/delete/login screens are standalone Django views and
templates under `templates/backoffice`. No Django admin template is inherited.
`SimpleAdminConfig` retains the existing `django_admin_log` model and migrations
but does not autodiscover the legacy ModelAdmin registrations.

- `registry.py`: module catalogue, sidebar, permissions and list columns.
- `views.py`: authentication, dashboard, record pages and payment review.
- `forms.py`: editable fields, password hashing and video URL encryption.
- `actions.py`: moderation, support, payout/migration status and renewal emails.
- `templates/backoffice/`: page markup and shared AdminLTE layout.
- `static/backoffice/`: locally bundled AdminLTE, Bootstrap, jQuery, Font Awesome.

The catalogue includes every existing business model except email OTP records,
which must not be exposed. Activity/history records are read-only. Account and
permission changes and secret settings require a superuser. Other pages respect
Django model permissions. Financial records/accounts cannot be deleted here.
Deleting a parent with cascading children is blocked, not silently cascaded.

## Deployment

Back up the current database and deployment before switching. This UI change adds
no models or migrations: do not reset migrations or use --fake for this change.
Use the directory containing the production Compose file:

```sh
docker compose build web
docker compose up -d web
docker compose exec web python manage.py check
docker compose logs --tail=100 web
```

The image bundles the vendor files and runs collectstatic. Static build failures
now fail the image build instead of being silently ignored. Docker excludes local
virtual environments, environment files, stale collected assets and UI archives.
Keep production secrets supplied through Compose environment/env_file as before.

Legacy UI templates/assets were moved to `legacy_ui_archive` outside Django's
template/static search paths for recovery, and excluded from the image. The old
Python admin registrations remain inactive; public/student API endpoints were
not replaced. Retain the root AdminLTE source package as the vendor source.

## Verification status and handoff

Django system checks and compilation of all seven templates passed locally.
No automated test suite, real database writes, email delivery, payment approval,
production deployment or browser/mobile visual acceptance was performed.

Before production acceptance, verify:

1. Login/logout, password change, staff versus superuser permissions and CSRF.
2. Every module list, filters, create/edit validation, related course/lesson links.
3. Slips: pending approval opens correct access once; rejection does not add spend.
4. Payout status actions and existing financial ledger reconciliation.
5. SMTP delivery for renewal reminders using a controlled recipient.
6. Phone/tablet layout, static assets, keyboard navigation and long Thai text.

Existing broadcast-email API is unchanged; this version does not provide a new
bulk email composer. Model forms use existing verbose labels, so some field labels
remain English. Large relation dropdowns should be replaced with permission-aware
search endpoints in a follow-up. Payment review locks records in this backoffice;
the existing separate administrative API has not been unified with it, so avoid
simultaneous approval through both paths until shared transactional review is added.
