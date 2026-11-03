from __future__ import annotations

from datetime import timedelta

import jwt
import pytest
from bson import ObjectId
from fastapi import HTTPException
from fastapi import Request, Response
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.modules.auth import deps
from app.modules.auth import router as auth_router
from app.modules.auth.models import UserRole
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import create_access_token, create_refresh_document, decode_access_token, utc_now


class UsersCollection:
    def __init__(self, user: dict) -> None:
        self.user = user

    def find_one(self, query: dict):
        if all(self.user.get(key) == value for key, value in query.items()):
            return self.user
        return None


class Database:
    def __init__(self, user: dict) -> None:
        self.users = UsersCollection(user)

    def __getitem__(self, name: str):
        assert name == "users"
        return self.users


@pytest.fixture
def auth_user(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "a" * 32)
    user = {"_id": ObjectId(), "tenantId": ObjectId(), "email": "owner@example.com", "role": "owner", "isActive": True}
    monkeypatch.setattr(deps, "get_database", lambda: Database(user))
    return user


def credential(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_valid_token_loads_active_user(auth_user):
    assert deps.get_current_user(credential(create_access_token(auth_user))) == auth_user


@pytest.mark.parametrize("claims", [
    {"exp": utc_now() - timedelta(seconds=1)},
    {"tenant_id": str(ObjectId())},
])
def test_expired_or_tenant_tampered_tokens_are_rejected(auth_user, claims):
    token_claims = jwt.decode(create_access_token(auth_user), settings.jwt_secret, algorithms=["HS256"], options={"verify_signature": False})
    token_claims.update(claims)
    token = jwt.encode(token_claims, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        deps.get_current_user(credential(token))
    assert error.value.status_code == 401


def test_wrong_algorithm_and_deactivated_user_are_rejected(auth_user):
    token = create_access_token(auth_user)
    claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"verify_signature": False})
    wrong_algorithm = jwt.encode(claims, "different-secret", algorithm="HS384")
    with pytest.raises(HTTPException) as error:
        deps.get_current_user(credential(wrong_algorithm))
    assert error.value.status_code == 401

    auth_user["isActive"] = False
    with pytest.raises(HTTPException) as error:
        deps.get_current_user(credential(token))
    assert error.value.status_code == 401


def test_role_dependency_rejects_staff_for_vehicle_mutations(auth_user):
    auth_user["role"] = "staff"
    dependency = deps.require_role(UserRole.owner, UserRole.manager)
    with pytest.raises(HTTPException) as error:
        dependency(auth_user)
    assert error.value.status_code == 403


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        ("owner", {"read", "create", "update", "toggle", "delete"}),
        ("manager", {"read", "create", "update", "toggle"}),
        ("staff", {"read"}),
    ],
)
def test_vehicle_role_matrix(role, allowed):
    operations = {
        "read": (UserRole.owner, UserRole.manager, UserRole.staff),
        "create": (UserRole.owner, UserRole.manager),
        "update": (UserRole.owner, UserRole.manager),
        "toggle": (UserRole.owner, UserRole.manager),
        "delete": (UserRole.owner,),
    }
    user = {"role": role}
    for operation, roles in operations.items():
        dependency = deps.require_role(*roles)
        if operation in allowed:
            assert dependency(user) == user
        else:
            with pytest.raises(HTTPException) as error:
                dependency(user)
            assert error.value.status_code == 403


def test_refresh_rotation_uses_one_family(auth_user):
    first_token, first = create_refresh_document(auth_user)
    second_token, second = create_refresh_document(auth_user, first["familyId"])
    assert first_token != second_token
    assert first["familyId"] == second["familyId"]
    assert first["tokenHash"] != second["tokenHash"]


class _RefreshCollection:
    def __init__(self, documents): self.documents = documents
    def find_one(self, query):
        return next((document for document in self.documents if all(
            (document.get(key) == value if not isinstance(value, dict) else self._match_op(document.get(key), value))
            for key, value in query.items()
        )), None)
    @staticmethod
    def _match_op(value, op_dict):
        if "$gt" in op_dict:
            return value is not None and value > op_dict["$gt"]
        return value == op_dict
    def insert_one(self, document, session=None):
        document = dict(document, _id=ObjectId())
        self.documents.append(document)
        return type("Result", (), {"inserted_id": document["_id"]})()
    def find_one_and_update(self, query, update):
        document = self.find_one(query)
        if document is None:
            return None
        document.update(update["$set"])
        return document
    def update_one(self, query, update, session=None):
        document = self.find_one(query)
        if document is None: return type("Result", (), {"modified_count": 0})()
        document.update(update["$set"])
        return type("Result", (), {"modified_count": 1})()
    def update_many(self, query, update):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()): document.update(update["$set"])


def test_reusing_rotated_refresh_token_revokes_entire_family(auth_user, monkeypatch):
    raw_token, token_doc = create_refresh_document(auth_user)
    token_doc["_id"] = ObjectId()
    refresh_tokens = _RefreshCollection([token_doc])
    database = type("Database", (), {"__getitem__": lambda self, key: refresh_tokens if key == "refresh_tokens" else UsersCollection(auth_user)})()
    monkeypatch.setattr(auth_router, "get_database", lambda: database)
    origin = settings.frontend_origins[0]
    request = Request({"type": "http", "headers": [(b"origin", origin.encode())], "client": ("127.0.0.1", 5000)})
    auth_router.refresh(request, Response(), raw_token)
    with pytest.raises(HTTPException) as error:
        auth_router.refresh(request, Response(), raw_token)
    assert error.value.status_code == 401
    assert all(document["revokedAt"] is not None for document in refresh_tokens.documents)



def test_token_requires_expected_issuer_and_audience(auth_user):
    claims = jwt.decode(create_access_token(auth_user), settings.jwt_secret, algorithms=["HS256"], options={"verify_signature": False})
    claims["aud"] = "wrong-audience"
    token = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


@pytest.mark.parametrize("secret", ["", "change-me", "short-secret"])
def test_startup_security_rejects_missing_short_or_default_jwt_secret(monkeypatch, secret):
    monkeypatch.setattr(settings, "jwt_secret", secret)
    with pytest.raises(RuntimeError):
        settings.validate_security_settings()


def test_refresh_and_logout_require_exact_origin_and_cookie_scope():
    request = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 5000)})
    with pytest.raises(HTTPException) as error:
        auth_router._same_origin(request)
    assert error.value.status_code == 403
    response = Response()
    auth_router._set_cookie(response, "refresh-token")
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie and "SameSite=lax" in cookie


def test_unknown_login_runs_dummy_password_compare_and_returns_generic_error(monkeypatch):
    called = []
    database = type("Database", (), {"__getitem__": lambda self, _: type("Users", (), {"find_one": lambda self, _: None})()})()
    monkeypatch.setattr(auth_router, "get_database", lambda: database)
    monkeypatch.setattr(auth_router, "verify_password", lambda password, password_hash: called.append((password, password_hash)) or False)
    auth_router._attempts.clear()
    request = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 5000)})
    with pytest.raises(HTTPException) as error:
        auth_router.login(LoginRequest(email="unknown@example.com", password="valid-password"), request, Response())
    assert error.value.status_code == 401
    assert error.value.detail == "Invalid email or password."
    assert called == [("valid-password", None)]


def test_password_rejects_more_than_72_utf8_bytes():
    with pytest.raises(Exception):
        LoginRequest(email="owner@example.com", password="€" * 25)
