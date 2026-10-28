# Vehicles API

Base path: `/api/v1/vehicles`

All routes depend on `get_current_tenant`. At present this is a development stub
that always returns `{"tenant_id": "dev_tenant", "role": "owner"}`. It does not
authenticate a request, validate a token, scope records by tenant, or authorize
the caller against a vehicle owner.

| Method | Path | Request | Success | Errors |
| --- | --- | --- | --- | --- |
| GET | `/` | Query: `search`, `type`, `fuel`, `fleetAvailability`, `listing` (`all`, `online`, `offline`), `page` (minimum 1), `limit` (1–100) | `200` `{items, total, page, limit}` | `422` invalid filter/pagination; `503` database unavailable |
| POST | `/` | `multipart/form-data`: `makeModel`, `registration`, `year`, `type`, `fuel`, `transmission`, `dailyRate`, `pickupAddress`; optional vehicle fields; repeated `photos`; repeated `documents` with parallel `documentTypes` | `201` created vehicle | `409` duplicate registration number; `422` validation/file error; `502` upload failure; `500` database failure; `503` database unavailable |
| GET | `/{vehicle_id}` | Path ID | `200` full vehicle, including `photos` and `documents` | `404` invalid or absent ID; `503` database unavailable |
| PATCH | `/{vehicle_id}` | `multipart/form-data` partial vehicle fields; `new_photos`, `new_documents`, `newDocumentTypes`, `removePhotoIds`, `removeDocumentIds` | `200` updated vehicle | `404` invalid/absent ID; `409` duplicate registration number; `422` validation/file error; `502` upload failure; `500` database failure; `503` database unavailable |
| PATCH | `/{vehicle_id}/show-on-wavygo` | JSON `{"showOnWavygo": true}` | `200` updated vehicle | `404` invalid/absent ID; `422` invalid body; `503` database unavailable |
| DELETE | `/{vehicle_id}` | Path ID | `200` `{message, id}` | `404` invalid/absent ID; `409` booking references vehicle; `503` database unavailable |

## Multipart details

- Photo MIME types: JPEG, PNG, WebP, HEIC, HEIF; maximum 5 MB each.
- Document MIME types: JPEG, PNG, WebP, PDF; maximum 10 MB each.
- At most 20 photos and 10 documents are retained per vehicle.
- `documentTypes` and `newDocumentTypes` must have exactly one entry per corresponding document. Allowed values are `RC`, `Insurance`, `PUC`, and `Other`.
- `dailyRate` is written to both `dailyRate` and legacy `price`.
- Setting `showOnWavygo` also sets `status` to `Online` or `Offline`. It never changes `fleetAvailability`.

## Authentication integration contract

Replace the implementation of `app.modules.auth.deps.get_current_tenant` without
changing route signatures. Its result must contain a stable user identity, tenant
identity, and role/permission information. Before production, vehicle queries and
mutations also need owner-or-admin authorization using a stored ownership field;
the current vehicle document has no such field.
