from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_payments():
    response = client.get("/api/v1/payments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Check structure
    tx = data[0]
    assert "id" in tx
    assert "booking" in tx
    assert "amount" in tx
    assert "method" in tx


def test_payment_stats():
    response = client.get("/api/v1/payments/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_collected" in data
    assert "online_collected" in data
    assert "offline_collected" in data
    assert "pending_balance" in data
    assert "total_transactions" in data
    assert data["total_transactions"] >= 1


def test_get_payment_by_id():
    list_res = client.get("/api/v1/payments")
    tx_id = list_res.json()[0]["id"]

    res = client.get(f"/api/v1/payments/{tx_id}")
    assert res.status_code == 200
    assert res.json()["id"] == tx_id


def test_record_new_payment():
    payload = {
        "booking_id": "BK-3983",
        "customer_name": "Isha Patel",
        "amount": 500.0,
        "method": "Cash",
        "status": "Paid",
        "notes": "Counter cash payment",
        "transaction_reference": "CASH/RECEIPT-01",
    }
    response = client.post("/api/v1/payments", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["booking"] == "BK-3983"
    assert data["customer"] == "Isha Patel"
    assert data["amount"] == 500.0
    assert data["method"] == "Cash"
    assert data["id"].startswith("TX-")


def test_update_and_refund_payment():
    # Record payment first
    payload = {
        "booking_id": "BK-9999",
        "customer_name": "Test Customer",
        "amount": 1000.0,
        "method": "UPI",
    }
    res = client.post("/api/v1/payments", json=payload)
    tx_id = res.json()["id"]

    # Refund
    refund_res = client.post(f"/api/v1/payments/{tx_id}/refund?reason=CustomerCancellation")
    assert refund_res.status_code == 200
    assert refund_res.json()["status"] == "Refunded"
    assert "CustomerCancellation" in refund_res.json()["notes"]


def test_payment_not_found():
    res = client.get("/api/v1/payments/TX-NONEXISTENT")
    assert res.status_code == 404
