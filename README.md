# Smart Living API

Django REST API backend for the [Smart Living System](../smart-living-system/) frontend.

## Stack

- **Django 5.2 LTS** + **Django REST Framework 3.17**
- PostgreSQL 17, Redis 7, Celery 5, S3/MinIO
- JWT auth (simplejwt), OpenAPI (drf-spectacular)

Architecture and endpoint map: `smart-living-system/docs/BACKEND_DESIGN.md`

## Quick start

```bash
cd smart-living-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env

# Optional: start Postgres, Redis, MinIO
docker compose up -d

python manage.py migrate
python manage.py seed_demo_admins   # demo admin phones for role selection
python manage.py createsuperuser
python manage.py runserver 8000
```

## Phase 1 auth endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/health/` | public | Health check |
| POST | `/api/v1/auth/otp/request/` | public | Send OTP (dev returns `devOtp`) |
| POST | `/api/v1/auth/otp/verify/` | public | Verify OTP → JWT + user |
| POST | `/api/v1/auth/role/select/` | JWT | Set renter / owner / admin |
| POST | `/api/v1/auth/token/refresh/` | public | Refresh access token |
| POST | `/api/v1/auth/logout/` | JWT | Blacklist refresh token |
| GET/PATCH | `/api/v1/accounts/me/` | JWT | Current user |
| GET/PATCH | `/api/v1/profile/renter/` | JWT | Profile CRUD |
| GET/POST | `/api/v1/account/verification/` | JWT | Verification status / submit |
| POST | `/api/v1/account/phone-change/request/` | JWT | OTP to new phone |
| POST | `/api/v1/account/phone-change/confirm/` | JWT | Confirm phone change |
| POST | `/api/v1/account/recover/` | public | Recover existing account |
| GET | `/api/v1/docs/` | — | Swagger UI |

All JSON responses use the frontend `ApiResult<T>` envelope: `{ "ok": true, "data": ... }`.

**Dev OTP:** with `DEBUG=true` and `OTP_DEV_FIXED_CODE=123456`, OTP is always `123456` and returned as `devOtp` for auto-fill.

**Demo admins** (after `seed_demo_admins`):

| Phone | Role |
|-------|------|
| +8801711111111 | super-admin |
| +8801722222222 | moderator |
| +8801733333333 | support |

## Settings

| Module | Use |
|--------|-----|
| `config.settings.dev` | Local development (default) |
| `config.settings.prod` | Production |

Set `DJANGO_SETTINGS_MODULE` in `.env`.

## Implementation phases

See **§19** in `BACKEND_DESIGN.md`. Phase 0–8 complete; Phase 9 is next.

## Phase 8 admin & monetization

```bash
python manage.py seed_admin_tools
```

Demo admin phones (OTP `123456` in DEBUG):

| Phone | Role |
|-------|------|
| +8801711111111 | super-admin |
| +8801722222222 | moderator |
| +8801733333333 | support |

Subscriptions remain from Phase 3 (`/subscriptions/*`) — not duplicated here.

| Area | Key paths |
|------|-----------|
| Dashboard | `/admin/dashboard/` |
| Admin users | `/admin/users/`, `/admin/users/managed/`, `/admin/users/managed/{id}/` |
| Verifications | `/admin/verifications/`, `/admin/verifications/{id}/` |
| Disputes | `/admin/disputes/`, `/admin/disputes/{id}/` |
| Property moderation | `/admin/properties/moderation/`, `/admin/properties/moderation/{id}/` |
| Complaints | `/admin/complaints/` |
| Fraud reports | `/admin/fraud-reports/`, `/admin/fraud-reports/{id}/` |
| Analytics | `/admin/analytics/` |
| Settings | `/admin/settings/` (GET/PUT singleton) |
| Activity logs | `/admin/activity-logs/` |
| Audit logs | `/audit/logs/` (POST append), `/admin/audit-logs/`, `/admin/audit-logs/{id}/rollback/` |
| Bookings (admin) | `/admin/bookings/` |

All `/admin/*` routes require JWT + active `AdminProfile` (`IsPlatformAdmin`).

## Phase 7 renter tools & documents

```bash
python manage.py seed_renter_tools
```

Demo phones: owner `+8801712345678`, renter `+8801710000001` (OTP `123456` in DEBUG).

| Area | Key paths |
|------|-----------|
| Complaints | `/complaints/`, `/complaints/{id}/status/` |
| Chats | `/chats/`, `/chats/{id}/`, `/chats/{id}/messages/`, `/chats/unread-count/` |
| Notifications | `/notifications/`, `/notifications/{id}/read/`, `/notifications/mark-all-read/` |
| Agreements | `/agreements/`, `/agreements/active/`, `/agreements/form-data/`, `/agreements/{id}/renewals/` |
| Checklists | `/checklists/`, `/checklists/categories/`, `/checklists/{id}/` |
| Expenses | `/expenses/categories/`, `/expenses/analytics/`, `/expenses/monthly/`, `/expenses/yearly/`, `/expenses/budgets/` |
| Budget patch | `/expenses/budgets/{id}/`, `/expenses/budgets/by-category/{categoryId}/` |
| Reports | `/reports/expense/`, `/reports/tax/` |
| Reminders | `/reminders/`, `/reminders/settings/`, `/reminders/history/` |

## Phase 6 mess

```bash
python manage.py seed_mess
```

Demo phones: owner `+8801712345678` (Abdul Karim), renter `+8801710000001` (Rahim, linked student if seeded).

| Area | Key paths |
|------|-----------|
| Mess discovery | `/mess/`, `/mess/{id}/`, `/mess/{id}/seats/` |
| Students & seats | `/mess/{id}/students/`, `/mess/{id}/seats/{seatId}/` |
| Notices | `/mess/{id}/notices/`, `/notices/`, `/notices/{id}/acknowledge/` |
| Bills | `/mess/{id}/bills/get-or-create/` |
| Meals | `/mess/{id}/meals/daily/`, `/weekly/`, `/timing/`, `/preferences/` |
| Attendance | `/mess/{id}/attendance/`, `/bulk/`, `/summary/`, `/report/` |
| SMS | `/mess/{id}/sms/templates/`, `/groups/`, `/send/`, `/history/` |
| Rules | `/mess/{id}/rules/`, `/rules/{id}/accept/`, `/rules/violations/` |
| Expenses | `/mess/{id}/expenses/`, `/summary/`, `/report/` |

## Phase 5 bookings & hotels

```bash
python manage.py seed_hotels
python manage.py seed_bookings   # optional — needs seed_listings first
```

Demo phones: owner `+8801712345678`, renter `+8801710000001` (OTP `123456` in DEBUG).

| Area | Key paths |
|------|-----------|
| Property bookings | `/bookings/`, `/bookings/mine/`, `/bookings/owner/`, `/bookings/{id}/status/` |
| Admin bookings | `/admin/bookings/` |
| Hotels | `/hotels/`, `/hotels/mine/`, `/hotels/{id}/`, `/hotels/{id}/rooms/` |
| Hotel bookings | `/hotels/{id}/bookings/`, `/hotels/bookings/mine/`, `/hotels/bookings/{id}/cancel/` |
| Pricing & reviews | `/hotels/{id}/pricing/`, `/hotels/{id}/rooms/pricing/`, `/hotels/{id}/reviews/` |

## Phase 4 payments

```bash
python manage.py seed_payments
```

Sandbox gateways auto-complete when credentials are empty (`PAYMENT_SANDBOX_AUTO_COMPLETE=true`). Replace `BKASH_*` / `NAGAD_*` / `ROCKET_*` in `.env` when you have real sandbox keys.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/payments/history/` | JWT | Payment history |
| GET/POST | `/api/v1/payments/scheduled/` | JWT | Scheduled payments |
| GET | `/api/v1/payments/schedules/` | JWT | Recurring schedules |
| POST | `/api/v1/payments/pay-bill/` | JWT | Pay a bill (wallet/cash) |
| POST | `/api/v1/payments/record-cash/` | owner | Complete cash collection |
| GET | `/api/v1/payments/owner/payouts/` | owner | Owner payout ledger |
| GET | `/api/v1/payments/owner/analytics/` | owner | Collection analytics |
| POST | `/api/v1/payments/owner/payouts/{id}/settle/` | owner | Mark payout settled |
| GET | `/api/v1/payments/transactions/{txn_id}/` | public | Lookup by gateway txn id |
| POST | `/api/v1/payments/webhooks/{bkash\|nagad\|rocket}/` | public | Gateway webhooks |
| POST | `/api/v1/payments/sandbox/complete/` | JWT (DEBUG) | Force-complete processing txn |

## Phase 3 portfolio & billing

```bash
python manage.py seed_portfolio
```

Owner demo phone: `+8801712345678` (OTP `123456` in DEBUG).

| Area | Key paths |
|------|-----------|
| Portfolio | `/buildings/`, `/flats/`, `/floors/`, `/portfolio/snapshot/` |
| Billing | `/bills/board/`, `/bills/generate/`, `/bills/bulk-generate/`, templates/rules/meters |
| Subscriptions | `/subscriptions/mine/`, `/subscriptions/flat-limit/`, `/subscriptions/upgrade/` |

## Phase 2 listings

```bash
python manage.py seed_listings
```

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/properties/` | public | List/filter published |
| POST | `/api/v1/properties/` | owner | Create listing |
| GET | `/api/v1/properties/{id}/` | public | Detail |
| PATCH | `/api/v1/properties/{id}/` | owner | Update |
| GET | `/api/v1/properties/featured/` | public | Featured |
| GET | `/api/v1/properties/meta/` | public | Cities/areas |
| GET | `/api/v1/properties/mine/` | JWT | Owner listings |
| POST | `/api/v1/properties/batch/` | public | By IDs |
| GET/POST | `/api/v1/properties/{id}/reviews/` | public/JWT | Reviews |
| GET | `/api/v1/favorites/` | JWT | Favorites |
| POST | `/api/v1/favorites/toggle/` | JWT | Toggle |
| * | `/api/v1/saved-searches/` | JWT | Saved searches |
| * | `/api/v1/search-history/` | JWT | Search history |
