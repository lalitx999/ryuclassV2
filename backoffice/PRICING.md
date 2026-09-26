# Prices managed in backoffice

Edit a course under /admin/courses/course/. Monthly price uses the existing price
column; price_180, price_365 and price_lifetime configure the other packages.
Blank optional prices disable those packages. Positive amounts only.

Deploy backend and frontend together. Back up the database, then run with the new
backend code before directing traffic to it:

    python manage.py migrate courses 0005_course_package_prices

Migration 0005 adds three nullable columns and copies the previous checkout's
6-month/year/lifetime prices for course IDs 1–5. It does not change monthly prices
or existing payment amounts. Other course IDs need optional package prices entered
by an administrator. Do not fake this migration.

The catalogue and checkout read the same database values. Reload the storefront
or reopen checkout after editing; this is not a live websocket update. Checkout
sends its displayed amount for comparison, but the server calculates the actual
amount independently and rejects outdated prices. Renewal remains 33 days at 10%
off the monthly price, subject to the existing server-side eligibility window.
Normal monthly duration remains 30 days, unchanged from the existing checkout.

Existing pending/approved payments retain their recorded amounts. No automatic
database migration or test-price edits were run as part of this implementation.
Verify with a non-production course before changing prices for active students.
