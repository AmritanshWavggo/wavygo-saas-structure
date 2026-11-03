"""
End-to-end check of the Add Vehicle backend (Phase 1, 2 and 3).

Run from the backend folder, with (.venv) active and the server running
in ANOTHER terminal (uvicorn app.main:app --reload):

    python scripts/test_all_phases.py

Needs backend/.env with MONGODB_URI and the CLOUDINARY_* values.
Use a DEV database only. Test vehicles and Cloudinary files are deleted at the end.
"""
from __future__ import annotations

import base64
import os
import random
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

import httpx  # noqa: E402

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
API = f"{BASE_URL}/api/v1/vehicles"

# 1x1 transparent PNG and a minimal valid PDF
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
PDF = (
    b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF"
)

results: list[tuple[str, bool, str]] = []
created_ids: list[str] = []
cloud_assets: list[tuple[str, str]] = []  # (public_id, resource_type) to clean up


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail and not ok else ""))
    return bool(ok)


def vid(body: dict) -> str:
    return str(body.get("id") or body.get("_id") or "")


def new_rc() -> str:
    return f"GJ05TS{random.randint(1000, 9999)}"


def camel(key: str) -> str:
    """snake_case -> camelCase (the API reads camelCase form fields)."""
    head, *tail = key.split("_")
    return head + "".join(t.title() for t in tail)


def form(rc: str, **over) -> dict:
    data = {
        "make_model": "Test Honda Activa",
        "registration": "GJ 05 TS 0001",
        "year": "2024",
        "type": "Scooter",
        "fuel": "Petrol",
        "transmission": "Automatic",
        "registration_number": rc,
        "color": "Blue",
        "engine_capacity": "125",
        "seats": "2",
        "rc_status": "Pending review",
        "daily_rate": "500",
        "minimum_days": "1",
        "security_deposit": "1000",
        "pickup_address": "Surat",
        "pickup_lat": "21.17",
        "pickup_lng": "72.83",
        "show_on_wavygo": "false",
        "fleet_availability": "Available",
        "document_types": ["RC"],
    }
    data.update(over)
    return {camel(k): v for k, v in data.items()}


def files():
    # Field names must match the File(...) params in the create route.
    return [
        ("photos", ("photo.png", PNG, "image/png")),
        ("documents", ("rc.pdf", PDF, "application/pdf")),
    ]


def safe_get(c: httpx.Client, url: str, **kwargs):
    """GET that never raises, so one dropped connection does not kill the run."""
    try:
        return c.get(url, **kwargs)
    except httpx.HTTPError as exc:
        print(f"      request failed: {url} -> {exc!r}")
        return None


def cloud_exists(public_id: str, resource_type: str) -> bool:
    import cloudinary.api
    from cloudinary.exceptions import NotFound

    try:
        cloudinary.api.resource(public_id, resource_type=resource_type)
        return True
    except NotFound:
        return False


# --------------------------------------------------------------------------
# PHASE 1: foundation (model, Cloudinary service, env)
# --------------------------------------------------------------------------
def phase1() -> None:
    print("\nPHASE 1: foundation")
    missing = [k for k in ("MONGODB_URI", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET") if not os.environ.get(k)]
    check("All required .env values are set", not missing, f"missing: {missing}")

    try:
        from app.modules.vehicles.models import VehicleModel

        m = VehicleModel(registration_number="  gj05ab4821 ")
        check("Model normalizes RC (trim + uppercase)", m.registration_number == "GJ05AB4821", str(m.registration_number))
        legacy = VehicleModel()
        check("Legacy record with no new fields stays valid", legacy.show_on_wavygo is False and legacy.photos == [])
        check("availability is the only fleet field (alias fleetAvailability)",
              VehicleModel(fleetAvailability="Rented").availability.value == "Rented"
              and not hasattr(legacy, "fleet_availability"))
    except Exception as exc:  # noqa: BLE001
        check("Vehicle model loads", False, repr(exc))

    try:
        from app.services import cloudinary_service as cs

        up = cs.upload_file(PNG, "wavygo/test", resource_type="image")
        pid = up["public_id"]
        cloud_assets.append((pid, "image"))
        check("Cloudinary upload works", up["url"].startswith("https://"), str(up.get("url")))
        check("Upload result has only url + public_id", set(up.keys()) == {"url", "public_id"}, str(up.keys()))
        cs.delete_file(pid, resource_type="image")
        check("Cloudinary delete works", not cloud_exists(pid, "image"))
        cloud_assets.remove((pid, "image"))

        up_pdf = cs.upload_file(PDF, "wavygo/test", resource_type="raw")
        pdf_id = up_pdf["public_id"]
        cloud_assets.append((pdf_id, "raw"))
        cs.delete_file(pdf_id, resource_type="raw")
        check("Raw (PDF) upload and delete work with the same resource_type", not cloud_exists(pdf_id, "raw"))
        cloud_assets.remove((pdf_id, "raw"))
    except Exception as exc:  # noqa: BLE001
        check("Cloudinary service works with your keys", False, repr(exc))


# --------------------------------------------------------------------------
# PHASE 2: the six APIs
# --------------------------------------------------------------------------
def phase2(c: httpx.Client) -> None:
    print("\nPHASE 2: APIs")
    rc = new_rc()

    r = c.post(API, data=form(rc, registration_number=f" {rc.lower()} "), files=files())
    ok = r.status_code in (200, 201)
    check("POST create vehicle (photo + PDF)", ok, f"{r.status_code} {r.text[:300]}")
    if not ok:
        return
    created = r.json()
    vehicle_id = vid(created)
    created_ids.append(vehicle_id)
    check("Create returns an id", bool(vehicle_id), str(created.keys()))
    check("RC stored normalized", str(created.get("registrationNumber", "")) == rc, str(created.get("registrationNumber")))
    check("price equals dailyRate", created.get("price") == created.get("dailyRate") == 500.0, f"{created.get('price')} / {created.get('dailyRate')}")
    check("Photo stored with url + publicId", bool(created.get("photos")) and created["photos"][0].get("publicId", "") != "")
    docs = created.get("documents", [])
    check("PDF stored as resourceType raw", bool(docs) and docs[0].get("resourceType") == "raw", str(docs[:1]))

    photo_id = created["photos"][0]["publicId"]
    doc_id = docs[0]["publicId"] if docs else ""
    cloud_assets.extend([(photo_id, "image"), (doc_id, docs[0].get("resourceType", "raw") if docs else "raw")])
    check("Photo exists in Cloudinary", cloud_exists(photo_id, "image"))
    check("PDF exists in Cloudinary", cloud_exists(doc_id, "raw"))
    check("Photo URL opens", httpx.get(created["photos"][0]["url"], timeout=30).status_code == 200)

    r = c.post(API, data=form(rc), files=files())
    check("Duplicate RC returns 409", r.status_code == 409, str(r.status_code))
    r = c.post(API, data=form(new_rc()), files=[("photos", ("bad.txt", b"hello", "text/plain"))])
    check("Invalid photo type returns 422", r.status_code == 422, str(r.status_code))
    r = c.post(API, data=form(new_rc(), daily_rate="-5"))
    check("Negative daily rate returns 422", r.status_code == 422, str(r.status_code))
    r = c.post(API, data=form(new_rc(), pickup_lat="200"))
    check("Latitude out of range returns 422", r.status_code == 422, str(r.status_code))

    r = c.get(f"{API}/{vehicle_id}")
    check("GET details", r.status_code == 200 and r.json().get("name") == "Test Honda Activa", f"{r.status_code}")
    check("GET invalid id returns 404, not 500", c.get(f"{API}/not-a-real-id").status_code == 404)
    check("GET unknown id returns 404", c.get(f"{API}/64b000000000000000000000").status_code == 404)

    r = c.patch(f"{API}/{vehicle_id}/show-on-wavygo", json={"showOnWavygo": True})
    body = r.json() if r.status_code == 200 else {}
    check("Toggle ON sets showOnWavygo and status Online",
          r.status_code == 200 and body.get("showOnWavygo") is True and body.get("status") == "Online", f"{r.status_code} {r.text[:200]}")
    check("Toggle does not change fleetAvailability", body.get("fleetAvailability") == "Available", str(body.get("fleetAvailability")))

    r = c.get(API, params={"listing": "online", "search": "Test Honda", "limit": 50})
    items = r.json().get("items", []) if r.status_code == 200 else []
    check("List listing=online contains the vehicle", any(vid(i) == vehicle_id for i in items), f"{r.status_code}")
    r = c.get(API, params={"listing": "offline", "limit": 50})
    check("List listing=offline excludes the vehicle", all(vid(i) != vehicle_id for i in r.json().get("items", [])))
    r = c.get(API, params={"listing": "all", "page": 1, "limit": 5})
    j = r.json() if r.status_code == 200 else {}
    check("List returns items/total/page/limit", all(k in j for k in ("items", "total", "page", "limit")), str(j.keys()))

    r = c.patch(f"{API}/{vehicle_id}/show-on-wavygo", json={"showOnWavygo": False})
    check("Toggle OFF sets status Offline", r.status_code == 200 and r.json().get("status") == "Offline")

    r = c.patch(
        f"{API}/{vehicle_id}",
        data={"dailyRate": "650", "removePhotoIds": [photo_id], "removeDocumentIds": []},
        files=[("newPhotos", ("new.png", PNG, "image/png"))],
    )
    ok = r.status_code == 200
    check("PATCH update (rate + replace photo)", ok, f"{r.status_code} {r.text[:300]}")
    if ok:
        up = r.json()
        check("Update keeps price == dailyRate", up.get("price") == up.get("dailyRate") == 650.0)
        check("Removed photo deleted from Cloudinary", not cloud_exists(photo_id, "image"))
        new_ids = [p["publicId"] for p in up.get("photos", [])]
        cloud_assets.extend((p, "image") for p in new_ids)

    other_rc = new_rc()
    r = c.post(API, data=form(other_rc))
    if r.status_code in (200, 201):
        other_id = vid(r.json())
        created_ids.append(other_id)
        r = c.patch(f"{API}/{other_id}", data={"registrationNumber": rc})
        check("Update to an existing RC returns 409", r.status_code == 409, str(r.status_code))

    r = c.delete(f"{API}/{vehicle_id}")
    check("DELETE vehicle", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    created_ids.remove(vehicle_id)
    check("Deleted vehicle files are gone from Cloudinary", not cloud_exists(doc_id, "raw"))
    check("Deleted vehicle returns 404 afterwards", c.get(f"{API}/{vehicle_id}").status_code == 404)


# --------------------------------------------------------------------------
# PHASE 3: security, tests, docs
# --------------------------------------------------------------------------
def phase3(c: httpx.Client) -> None:
    print("\nPHASE 3: security, tests, docs")

    r = safe_get(c, API, params={"search": '{"$ne": ""}'})
    check(
        "Mongo operator in search does not break or match everything",
        r is not None and r.status_code == 200 and r.json().get("total", 1) == 0,
        "no response (connection dropped)" if r is None else f"{r.status_code} {r.text[:200]}",
    )

    r = safe_get(c, API, params={"search": "(.*+["})
    check(
        "Regex characters in search return 200, not 500",
        r is not None and r.status_code == 200,
        "no response (connection dropped)" if r is None else f"{r.status_code} {r.text[:200]}",
    )

    r = safe_get(c, API, params={"limit": 100000})
    check(
        "Huge limit is rejected or capped",
        r is not None and (r.status_code == 422 or (r.status_code == 200 and len(r.json().get("items", [])) <= 500)),
        "no response (connection dropped)" if r is None else f"{r.status_code}",
    )

    secret = os.environ.get("CLOUDINARY_API_SECRET", "")
    probes = [safe_get(c, API), safe_get(c, f"{API}/not-a-real-id")]
    leaked = bool(secret) and any(p is not None and secret in p.text for p in probes)
    check("Cloudinary API secret never appears in responses", not leaked)

    r = safe_get(c, f"{BASE_URL}/openapi.json")
    paths = r.json().get("paths", {}) if r is not None and r.status_code == 200 else {}
    check("All 6 vehicle routes registered",
          {"get", "post"} <= set(paths.get("/api/v1/vehicles", {}))
          and {"get", "patch", "delete"} <= set(paths.get("/api/v1/vehicles/{vehicle_id}", {}))
          and "patch" in paths.get("/api/v1/vehicles/{vehicle_id}/show-on-wavygo", {}))

    h1 = safe_get(c, f"{BASE_URL}/health")
    h2 = safe_get(c, f"{BASE_URL}/api/v1/health")
    check("Existing health routes still work",
          h1 is not None and h1.status_code == 200 and h2 is not None and h2.status_code == 200)

    docs_ok = all((BACKEND_DIR / "docs" / f).exists() for f in ("vehicles-api.md", "vehicles-manual-qa.md", "phase-3-pr-description.md"))
    check("Handoff docs exist", docs_ok)

    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], capture_output=True, text=True, timeout=180)
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[-200:]
    check("pytest suite passes (xfails = tenant isolation gap)", proc.returncode == 0, tail)
    print(f"      pytest: {tail}")


def cleanup(c: httpx.Client) -> None:
    print("\nCleanup")
    for v in list(created_ids):
        try:
            c.delete(f"{API}/{v}")
        except Exception:  # noqa: BLE001
            pass
    try:
        import cloudinary.uploader

        for pid, rtype in cloud_assets:
            if pid:
                cloudinary.uploader.destroy(pid, resource_type=rtype)
    except Exception:  # noqa: BLE001
        pass
    print("  Test vehicles and Cloudinary files removed (check the Media Library once).")


def main() -> int:
    try:
        httpx.get(f"{BASE_URL}/health", timeout=5)
    except Exception:  # noqa: BLE001
        print(f"Server not reachable at {BASE_URL}. Start it first: uvicorn app.main:app --reload")
        return 2

    phase1()
    with httpx.Client(timeout=60) as c:
        try:
            phase2(c)
            phase3(c)
        finally:
            cleanup(c)

    failed = [r for r in results if not r[1]]
    print(f"\nRESULT: {len(results) - len(failed)}/{len(results)} checks passed")
    for name, _, detail in failed:
        print(f"  FAILED: {name}  {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())