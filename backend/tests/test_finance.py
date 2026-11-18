from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_finance_overview():
    response = client.get("/api/v1/finance/overview")
    assert response.status_code == 200
    data = response.json()
    assert "total_revenue" in data
    assert "total_expenses" in data
    assert "estimated_net" in data
    assert "profit_margin_pct" in data
    assert "comparison_chart" in data
    assert isinstance(data["comparison_chart"], list)
    assert len(data["comparison_chart"]) >= 6
    assert "expense_breakdown" in data
    assert isinstance(data["expense_breakdown"], list)


def test_finance_cashflow():
    response = client.get("/api/v1/finance/cashflow")
    assert response.status_code == 200
    data = response.json()
    assert "total_inflow" in data
    assert "total_outflow" in data
    assert "net_cashflow" in data
    assert "by_method" in data
    assert "UPI" in data["by_method"]


def test_finance_pnl():
    response = client.get("/api/v1/finance/pnl")
    assert response.status_code == 200
    data = response.json()
    assert "period" in data
    assert "total_revenue" in data
    assert "total_operating_expenses" in data
    assert "net_operating_income" in data
    assert "operating_margin_pct" in data


def test_expenses_crud():
    # 1. Create Expense
    payload = {
        "category": "Maintenance",
        "title": "Brake shoe replacement for Activa",
        "amount": 750.0,
        "payment_method": "UPI",
        "payee": "Speedway Garage",
        "reference": "UPI/9876543210",
        "notes": "Emergency brake shoe replacement",
    }
    create_res = client.post("/api/v1/finance/expenses", json=payload)
    assert create_res.status_code == 201
    created_expense = create_res.json()
    exp_id = created_expense["id"]
    assert exp_id.startswith("EXP-")
    assert created_expense["title"] == "Brake shoe replacement for Activa"
    assert created_expense["amount"] == 750.0
    assert created_expense["category"] == "Maintenance"

    # 2. Get Expense by ID
    get_res = client.get(f"/api/v1/finance/expenses/{exp_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == exp_id

    # 3. List Expenses
    list_res = client.get("/api/v1/finance/expenses")
    assert list_res.status_code == 200
    expenses = list_res.json()
    assert isinstance(expenses, list)
    assert any(e["id"] == exp_id for e in expenses)

    # 4. Update Expense
    update_res = client.patch(
        f"/api/v1/finance/expenses/{exp_id}",
        json={"amount": 800.0, "status": "Paid", "notes": "Updated price with tax"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["amount"] == 800.0
    assert update_res.json()["notes"] == "Updated price with tax"

    # 5. Delete Expense
    del_res = client.delete(f"/api/v1/finance/expenses/{exp_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 6. Verify Deleted
    get_after_del = client.get(f"/api/v1/finance/expenses/{exp_id}")
    assert get_after_del.status_code == 404

