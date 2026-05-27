from backend.security.user_auth import TokenService
from backend.security.user_auth import UserStore


def test_user_store_registers_and_authenticates_user(tmp_path):
    store = UserStore(
        database_path=str(tmp_path / "users.sqlite3")
    )

    user = store.create_user(
        email="USER@example.com",
        password="strong-password",
        full_name="Test User"
    )

    assert user.email == "user@example.com"

    authenticated = store.authenticate(
        email="user@example.com",
        password="strong-password"
    )

    assert authenticated is not None
    assert authenticated.user_id == user.user_id

    assert store.authenticate(
        email="user@example.com",
        password="wrong-password"
    ) is None


def test_token_service_round_trips_user_token(tmp_path):
    store = UserStore(
        database_path=str(tmp_path / "users.sqlite3")
    )
    user = store.create_user(
        email="user@example.com",
        password="strong-password"
    )
    tokens = TokenService(
        secret="test-secret",
        expire_minutes=5
    )

    token = tokens.create_token(
        user
    )
    payload = tokens.verify_token(
        token
    )

    assert payload is not None
    assert payload["sub"] == str(user.user_id)


def test_token_service_rejects_tampered_token(tmp_path):
    store = UserStore(
        database_path=str(tmp_path / "users.sqlite3")
    )
    user = store.create_user(
        email="user@example.com",
        password="strong-password"
    )
    tokens = TokenService(
        secret="test-secret",
        expire_minutes=5
    )

    token = tokens.create_token(
        user
    )

    assert tokens.verify_token(
        token + "tampered"
    ) is None


def test_email_verification_token_marks_user_verified(tmp_path):
    store = UserStore(
        database_path=str(tmp_path / "users.sqlite3")
    )
    user = store.create_user(
        email="verify@example.com",
        password="strong-password"
    )

    token = store.create_email_verification_token(
        user.user_id
    )
    verified = store.verify_email_token(
        token
    )

    assert user.email_verified is False
    assert verified is not None
    assert verified.email_verified is True
    assert store.verify_email_token(
        token
    ) is None


def test_password_reset_token_updates_password_once(tmp_path):
    store = UserStore(
        database_path=str(tmp_path / "users.sqlite3")
    )
    store.create_user(
        email="reset@example.com",
        password="old-password"
    )

    token = store.create_password_reset_token(
        "reset@example.com"
    )
    reset_user = store.reset_password_with_token(
        token=token or "",
        new_password="new-password"
    )

    assert reset_user is not None
    assert store.authenticate(
        "reset@example.com",
        "old-password"
    ) is None
    assert store.authenticate(
        "reset@example.com",
        "new-password"
    ) is not None
    assert store.reset_password_with_token(
        token=token or "",
        new_password="another-password"
    ) is None


def test_admin_user_update_and_list(tmp_path):
    store = UserStore(
        database_path=str(tmp_path / "users.sqlite3")
    )
    user = store.create_user(
        email="admin-target@example.com",
        password="strong-password"
    )

    updated = store.update_user(
        user.user_id,
        role="admin",
        active=False,
        email_verified=True
    )
    users = store.list_users()

    assert updated is not None
    assert updated.role == "admin"
    assert updated.active is False
    assert updated.email_verified is True
    assert users[0].email == "admin-target@example.com"
