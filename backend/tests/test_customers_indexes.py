"""
Tests for Customer MongoDB index creation and startup refusal on failure.
"""

from __future__ import annotations

import mongomock
import pytest

from app.db import mongodb


def test_customer_indexes_are_created(monkeypatch):
    database = mongomock.MongoClient().wavygo_test
    monkeypatch.setattr(mongodb, "get_database", lambda: database)

    mongodb.ensure_indexes()

    indexes = database.customers.index_information()
    assert "ix_customers_tenant_deleted_created" in indexes
    assert indexes["ix_customers_tenant_deleted_created"]["key"] == [
        ("tenantId", 1),
        ("deletedAt", 1),
        ("createdAt", 1),
    ]

    assert "uq_customer_tenant_phone_active" in indexes
    phone_idx = indexes["uq_customer_tenant_phone_active"]
    assert phone_idx["unique"] is True
    assert phone_idx["key"] == [("tenantId", 1), ("phone", 1)]
    assert phone_idx["partialFilterExpression"] == {
        "deletedAt": {"$type": "null"},
        "phone": {"$type": "string"},
    }


def test_customer_index_failure_raises_runtime_error_and_stops_startup(monkeypatch):
    database = mongomock.MongoClient().wavygo_test
    monkeypatch.setattr(mongodb, "get_database", lambda: database)

    def fake_create_index(*args, **kwargs):
        raise mongodb.DuplicateKeyError("E11000 duplicate key error on customers.phone")

    monkeypatch.setattr(database["customers"], "create_index", fake_create_index)

    with pytest.raises(RuntimeError, match="Database indexes could not be created; refusing to start.") as exc_info:
        mongodb.ensure_indexes()

    assert exc_info.value.__cause__ is not None

