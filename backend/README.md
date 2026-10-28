# WavyGo Vendor API

FastAPI backend for the WavyGo vendor workspace. Install the dependencies and run
the API from `backend/`:

```powershell
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Copy `.env.example` to `.env` and set `MONGODB_URI` and a securely generated
`JWT_SECRET_KEY` of at least 32 bytes directly in the untracked `.env` file or
a deployment secret manager. Do not print or log the signing secret. The API
can start without MongoDB or a signing key, but authentication/customer
requests will return `503 Service Unavailable` until both are configured.

Vendors are provisioned outside the public API. From `backend/`, run
`python -m app.modules.auth.provision`; it securely prompts for the vendor's
email and password and stores an Argon2id password hash in the `vendors`
collection. Vendor records use their MongoDB `_id` as the tenant identity.
Inactive vendor accounts (`is_active: false`) cannot log in or use existing
tokens.

To reset the password for an existing vendor without creating or changing any
other vendor fields, run `python -m app.modules.auth.reset_password` from
`backend/`. It prompts for the normalized vendor email, then prompts twice for
a hidden 12-128 character password.

Log in with `POST /api/v1/auth/login` and a JSON body containing `email` and
`password`. Send the returned access token as
`Authorization: Bearer <access_token>` on every customer request. Tokens use
HS256, include issuer/audience and expiry claims, and expire after 30 minutes
by default (configurable with `JWT_ACCESS_TOKEN_MINUTES`).

Customer endpoints are available at `/api/v1/customers/`. Listing supports
`skip` and `limit` (maximum 100) and an optional `status=Review` or
`status=Verified` filter. Results are ordered by creation time and ID; `total`
is the count after tenant and status filtering. Invalid pagination, status,
or update data returns `422`; malformed IDs return `400`; missing or
cross-tenant records return the same `404`; duplicate phone/email values
return `409`; and database failures return `503`.

Customer records include profile fields and zero-initialized booking/payment
summary fields for the current frontend contract; those summaries are not yet
linked to booking or payment data. `PUT` accepts a non-empty subset of editable
profile fields, leaving omitted fields unchanged. Phone numbers are compared
after formatting is removed, and non-empty emails are normalized to lowercase.
Uniqueness is intended per vendor/tenant. It is enforced by MongoDB unique
indexes on `(tenant_id, phone_normalized)` and `(tenant_id, email)`; duplicate
key errors are returned as `409`. The application does not create or alter
customer indexes automatically.

New customer records are assigned to the authenticated vendor; clients cannot
set or override that tenant ID. All list, count, read, update, and delete
queries are tenant-scoped. Records without `tenant_id` remain unassigned and
are excluded from all vendor endpoints. They are never automatically
attributed to a vendor.

**Production index and legacy-data migration requires operator approval and
has not been run by the application.** Before enabling per-tenant duplicates
on a database that still has global phone/email unique indexes, use this
review-first plan:

1. Take a restorable backup and produce a read-only inventory of customer
   counts, missing/invalid tenant IDs, and duplicate normalized phone/email
   values within each verified tenant. Do not copy customer PII into logs.
2. Keep unassigned legacy records isolated. Reconcile ownership against a
   trusted source and obtain explicit approval for each assignment; do not
   infer a tenant from email, phone, or other customer fields. Separately
   review duplicate contacts within each tenant and agree on corrections.
3. After approval, create and validate unique compound indexes for
   `(tenant_id, phone_normalized)` and `(tenant_id, email)`, with partial
   filters that include only records with an ObjectId `tenant_id` and a string
   contact value. This excludes unassigned legacy records until individually
   reconciled. If duplicate data prevents index creation, stop and resolve
   only approved records; do not delete data to force index creation.
4. Only after both compound indexes are verified, and with approval, remove
   the old global unique indexes. Keep a rollback plan and confirm same-tenant
   duplicate rejection and cross-tenant duplicate acceptance in an isolated
   staging database before deployment.

Until that approved index migration is complete, existing global indexes may
still reject a phone or email shared by different vendors. The application
does not change those indexes or customer data.

Run the backend tests from `backend/`:

```powershell
python -m pytest
```

Authentication and tenant-scoping tests run with isolated in-memory fakes and
do not read or modify Atlas data. The application still needs production
controls such as login rate limiting, password reset/account recovery, secret
rotation, and a controlled migration plan for legacy unassigned customer
records. Configure the secret and migrate any records before production use.
