# Phase 3: Vehicle API review, hardening, tests, and handoff

## What changed

- Added isolated vehicle route tests using an in-memory collection and mocked
  Cloudinary service calls. No test contacts MongoDB or Cloudinary.
- Added API contract and manual QA documentation.
- Capped FastAPI below `0.160`. The installed `0.160.0` resolves Starlette
  `1.9.0`, whose `TestClient` expects the separate `httpx2` package and hangs
  when it falls back to installed `httpx 0.28.1`. No new dependency was added.
- Changed the existing health test to call the health handler directly so the
  current suite remains runnable without the broken `TestClient` combination.

## Environment variables

Production media operations require:

- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

MongoDB configuration uses `MONGODB_URI` and `MONGODB_DATABASE`.

## Run tests

From `backend`:

```powershell
python -m pytest
```

## Known risks

- `get_current_tenant` is a development stub, not authentication or
  authorization. Vehicle records do not store ownership, so owner/admin checks
  cannot yet be enforced.
- Unit tests mock Cloudinary and MongoDB. Real provider credentials, upload
  behavior, index creation, and failure modes still require manual QA.
- Uploaded content is accepted based on the multipart MIME type; the current
  implementation does not inspect file magic bytes.
