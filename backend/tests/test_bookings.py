from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_offline_booking():
    payload = {
        "vehicle": {
            "vehicle_id": "VH-1042",
            "vehicle_name": "Honda Activa 6G",
            "registration": "GJ 05 AB 4821",
            "price_per_day": 649,
            "vehicle_type": "Scooter",
        },
        "customer": {
            "name": "Ravi Kumar",
            "phone": "+91 98989 12345",
            "email": "ravi.kumar@example.com",
        },
        "rental": {
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",
            "pickup_time": "10:00",
            "return_time": "18:00",
            "pickup_location": "Vesu Hub, Surat",
            "add_ons": True,
            "discount": 100,
        },
        "payment": {
            "method": "Cash",
            "deposit": True,
            "paid_amount": 1000,
        },
        "notes": "Customer presented valid driving license.",
    }

    response = client.post("/api/v1/bookings/offline", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["type"] == "Offline"
    assert data["status"] == "Active"
    assert data["customer"] == "Ravi Kumar"
    assert data["vehicle"] == "Honda Activa 6G"
    assert data["rental_days"] == 2
    # Base: 649 * 2 = 1298
    assert data["base_amount"] == 1298.0
    # Add-on: 500 * 2 = 1000
    assert data["add_on_amount"] == 1000.0
    # Service fee: 5% of 1298 = 64.9
    assert data["service_fee"] == 64.9
    # Subtotal: 1298 + 1000 + 64.9 = 2362.9
    # Discount: 100
    # Deposit: 2000
    # Total: 2362.9 - 100 + 2000 = 4262.9
    assert round(data["total_amount"], 1) == 4262.9
    # Paid: 1000
    assert data["paid"] == 1000.0
    # Pending: 4262.9 - 1000 = 3262.9
    assert round(data["pending"], 1) == 3262.9


def test_list_and_get_offline_bookings():
    # List bookings
    list_res = client.get("/api/v1/bookings/offline")
    assert list_res.status_code == 200
    bookings = list_res.json()
    assert len(bookings) >= 1

    booking_id = bookings[0]["id"]
    # Get by ID
    get_res = client.get(f"/api/v1/bookings/offline/{booking_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == booking_id

    # Test search query
    query_res = client.get(f"/api/v1/bookings/offline?query=Ravi")
    assert query_res.status_code == 200
    assert len(query_res.json()) >= 1


def test_update_status_and_payment():
    # Create booking first
    payload = {
        "vehicle": {
            "vehicle_id": "VH-1038",
            "vehicle_name": "Royal Enfield Classic 350",
            "registration": "GJ 05 CD 7194",
            "price_per_day": 1899,
        },
        "customer": {
            "name": "Pooja Verma",
            "phone": "+91 91234 56789",
        },
        "rental": {
            "start_date": "2026-11-05",
            "end_date": "2026-11-06",
            "pickup_location": "Adajan Center",
            "add_ons": False,
            "discount": 0,
        },
        "payment": {
            "method": "UPI",
            "deposit": False,
            "paid_amount": 0,
        },
    }
    create_res = client.post("/api/v1/bookings/offline", json=payload)
    assert create_res.status_code == 201
    booking_id = create_res.json()["id"]
    total_amount = create_res.json()["total_amount"]

    # Record partial payment
    pay_res = client.post(
        f"/api/v1/bookings/offline/{booking_id}/payments",
        json={"amount": 500, "method": "UPI", "notes": "UPI reference 123456789"},
    )
    assert pay_res.status_code == 200
    pay_data = pay_res.json()
    assert pay_data["paid"] == 500.0
    assert pay_data["pending"] == round(total_amount - 500.0, 2)

    # Update status to Completed
    patch_res = client.patch(
        f"/api/v1/bookings/offline/{booking_id}",
        json={"status": "Completed"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "Completed"


def test_booking_not_found():
    res = client.get("/api/v1/bookings/offline/BK-999999")
    assert res.status_code == 404
