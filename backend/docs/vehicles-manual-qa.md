# Vehicle API manual QA checklist

Use a non-production MongoDB database and a disposable Cloudinary folder.

- [ ] Set `MONGODB_URI`, `MONGODB_DATABASE`, and all three Cloudinary variables.
- [ ] Start the API and confirm startup creates or reuses
  `uq_registration_number` on `vehicles.registrationNumber`.
- [ ] Create a vehicle with JPEG/PNG photos, a PDF document, and every document
  type. Confirm stored URLs and public IDs are returned, but no Cloudinary API
  secret or raw provider response is exposed.
- [ ] Attempt a duplicate registration number and confirm HTTP 409.
- [ ] Upload a disallowed MIME type and oversized photo/document; confirm HTTP
  422 and no orphaned Cloudinary asset.
- [ ] Simulate an interrupted upload and a Mongo write failure; confirm already
  uploaded assets are deleted.
- [ ] Patch rate and visibility. Confirm `price == dailyRate`, `status` matches
  `showOnWavygo`, and `fleetAvailability` is unchanged by the visibility toggle.
- [ ] Add and remove photos/documents. Confirm removed provider assets are
  deleted only after the database update succeeds; verify PDF deletion uses
  `raw` and image document deletion uses its stored resource type.
- [ ] Add a booking reference using both ObjectId and string `vehicleId`; confirm
  deletion returns HTTP 409 in both cases.
- [ ] Verify list search containing `+`, `[]`, `$`, and JSON-like text returns
  expected literal matches and does not alter query behavior.
- [ ] After real authentication is implemented, test an unauthenticated request,
  a non-owner/non-admin request, an owner request, and an admin request for each
  mutation route.
