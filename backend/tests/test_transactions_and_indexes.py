from unittest.mock import MagicMock, patch
import pytest
from pymongo.errors import OperationFailure, PyMongoError

from app.db.mongodb import (
    ensure_all_indexes,
    ensure_booking_indexes,
    ensure_customer_indexes,
    ensure_vehicle_indexes,
    ensure_payment_indexes,
    ensure_auth_indexes,
    mongo_transaction,
)


def test_ensure_all_indexes_offline_graceful():
    """When DB is None (offline/unconfigured), ensure_all_indexes runs without crashing."""
    with patch("app.db.mongodb.get_database", return_value=None):
        results = ensure_all_indexes()
        assert isinstance(results, dict)
        assert results.get("bookings") is True
        assert results.get("vehicles") is True
        assert results.get("customers") is True
        assert results.get("payments") is True


def test_ensure_indexes_creates_collection_indexes():
    """Verify that index functions register the expected indexes on mock DB."""
    mock_db = {}
    
    class MockCollection:
        def __init__(self, name):
            self.name = name
            self.indexes = {}

        def create_index(self, keys, **kwargs):
            name = kwargs.get("name") or str(keys)
            self.indexes[name] = {"keys": keys, **kwargs}
            return name

        def list_indexes(self):
            return list(self.indexes.values())

        def drop_index(self, name):
            self.indexes.pop(name, None)

        def aggregate(self, pipeline):
            return []

    mock_db_instance = MagicMock()
    mock_db_instance.__getitem__.side_effect = lambda col_name: mock_db.setdefault(col_name, MockCollection(col_name))

    with patch("app.db.mongodb.get_database", return_value=mock_db_instance):
        ensure_booking_indexes()
        ensure_customer_indexes()
        ensure_vehicle_indexes()
        ensure_payment_indexes()
        ensure_auth_indexes()

    # Verify bookings indexes
    b_indexes = mock_db["bookings"].indexes
    assert "uq_bookings_id" in b_indexes
    assert "ix_bookings_tenant_status" in b_indexes
    assert "ix_bookings_overlap_lookup" in b_indexes

    # Verify customers indexes
    c_indexes = mock_db["customers"].indexes
    assert "uq_customers_tenant_phone" in c_indexes
    assert "ix_customers_phone_normalized" in c_indexes

    # Verify vehicles indexes
    v_indexes = mock_db["vehicles"].indexes
    assert "uq_tenant_registration" in v_indexes

    # Verify payments indexes
    p_indexes = mock_db["payments"].indexes
    assert "uq_payments_tenant_idempotency" in p_indexes


def test_mongo_transaction_none_client_graceful():
    """When client is None, mongo_transaction gracefully yields None."""
    with mongo_transaction(client=None) as session:
        assert session is None


def test_mongo_transaction_commits_on_success():
    """When in transaction, normal exit calls commit_transaction and ends session."""
    mock_session = MagicMock()
    mock_session.in_transaction = True
    mock_client = MagicMock()
    mock_client.start_session.return_value = mock_session

    with mongo_transaction(client=mock_client) as session:
        assert session is mock_session
        mock_session.start_transaction.assert_called_once()

    mock_session.commit_transaction.assert_called_once()
    mock_session.end_session.assert_called_once()


def test_mongo_transaction_aborts_on_exception():
    """When an exception occurs inside transaction, abort_transaction is called."""
    mock_session = MagicMock()
    mock_session.in_transaction = True
    mock_client = MagicMock()
    mock_client.start_session.return_value = mock_session

    with pytest.raises(ValueError, match="Database mutation failed"):
        with mongo_transaction(client=mock_client) as session:
            assert session is mock_session
            raise ValueError("Database mutation failed")

    mock_session.abort_transaction.assert_called_once()
    mock_session.commit_transaction.assert_not_called()
    mock_session.end_session.assert_called_once()


def test_mongo_transaction_standalone_fallback():
    """When MongoDB raises OperationFailure (standalone topology), gracefully fall back without transaction."""
    mock_session = MagicMock()
    mock_session.start_transaction.side_effect = OperationFailure("Transaction numbers are only allowed on a replica set member or mongos", code=20)
    mock_session.in_transaction = False
    mock_client = MagicMock()
    mock_client.start_session.return_value = mock_session

    # Should not raise exception on entry; runs in standard session mode
    with mongo_transaction(client=mock_client) as session:
        assert session is mock_session

    mock_session.commit_transaction.assert_not_called()
    mock_session.abort_transaction.assert_not_called()
    mock_session.end_session.assert_called_once()
