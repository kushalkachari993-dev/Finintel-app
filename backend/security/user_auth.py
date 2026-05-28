import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from backend.config import settings
from backend.storage import connect_database


PASSWORD_ITERATIONS = 210_000


@dataclass(frozen=True)
class AuthUser:
    user_id: int
    email: str
    full_name: str
    role: str
    active: bool
    email_verified: bool = False


class UserStore:

    def __init__(
        self,
        database_path: str | None = None,
        database_url: str | None = None
    ):
        if database_path:
            self.database_path = database_path
            self.database_url = None
        elif database_url:
            self.database_path = None
            self.database_url = database_url
        else:
            self.database_path = settings.AUTH_DATABASE_PATH
            self.database_url = settings.AUTH_DATABASE_URL

        self.init_db()

    def connect(self):
        return connect_database(
            database_url=self.database_url,
            database_path=self.database_path
        )

    def init_db(self):
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL
                )
                """
            )
            self.ensure_auth_control_schema(
                connection
            )

    @staticmethod
    def ensure_auth_control_schema(
        connection
    ):
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        if "email_verified" not in columns:
            connection.execute(
                """
                ALTER TABLE users
                ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0
                """
            )

        if "updated_at" not in columns:
            connection.execute(
                """
                ALTER TABLE users
                ADD COLUMN updated_at INTEGER
                """
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                purpose TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at INTEGER,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_auth_tokens_lookup
            ON auth_tokens (token_hash, purpose, used_at, expires_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_auth_tokens_user
            ON auth_tokens (user_id, purpose, created_at DESC)
            """
        )

    @staticmethod
    def normalize_email(
        email: str
    ) -> str:
        return email.strip().lower()

    @staticmethod
    def hash_password(
        password: str,
        salt: str | None = None
    ) -> str:
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            PASSWORD_ITERATIONS
        ).hex()
        return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}"

    @staticmethod
    def verify_password(
        password: str,
        stored_hash: str
    ) -> bool:
        try:
            algorithm, iterations, salt, expected = stored_hash.split("$")
        except ValueError:
            return False

        if algorithm != "pbkdf2_sha256":
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations)
        ).hex()

        return hmac.compare_digest(
            digest,
            expected
        )

    def create_user(
        self,
        email: str,
        password: str,
        full_name: str = "",
        role: str = "user",
        email_verified: bool = False
    ) -> AuthUser:
        normalized_email = self.normalize_email(
            email
        )
        display_name = (
            full_name.strip()
            or normalized_email.split("@")[0]
        )

        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (
                    email,
                    full_name,
                    password_hash,
                    role,
                    active,
                    email_verified,
                    created_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    normalized_email,
                    display_name,
                    self.hash_password(password),
                    role,
                    1 if email_verified else 0,
                    int(time.time())
                )
            )

            return AuthUser(
                user_id=int(cursor.lastrowid),
                email=normalized_email,
                full_name=display_name,
                role=role,
                active=True,
                email_verified=email_verified
            )

    def row_to_user(
        self,
        row
    ) -> AuthUser | None:
        if not row:
            return None

        return AuthUser(
            user_id=row[0],
            email=row[1],
            full_name=row[2],
            role=row[4],
            active=bool(row[5]),
            email_verified=bool(row[6])
        )

    def get_user_by_email(
        self,
        email: str
    ) -> AuthUser | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, email, full_name, password_hash, role, active, email_verified
                FROM users
                WHERE email = ?
                """,
                (
                    self.normalize_email(email),
                )
            ).fetchone()

        return self.row_to_user(row)

    def get_user_by_id(
        self,
        user_id: int
    ) -> AuthUser | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, email, full_name, password_hash, role, active, email_verified
                FROM users
                WHERE id = ?
                """,
                (
                    user_id,
                )
            ).fetchone()

        return self.row_to_user(row)

    def authenticate(
        self,
        email: str,
        password: str
    ) -> AuthUser | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, email, full_name, password_hash, role, active, email_verified
                FROM users
                WHERE email = ?
                """,
                (
                    self.normalize_email(email),
                )
            ).fetchone()

        if not row:
            return None

        if not row[5]:
            return None

        if not self.verify_password(
            password,
            row[3]
        ):
            return None

        return self.row_to_user(row)

    @staticmethod
    def hash_token(
        token: str
    ) -> str:
        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

    def create_auth_token(
        self,
        user_id: int,
        purpose: str,
        expires_in_minutes: int
    ) -> str:
        token = secrets.token_urlsafe(
            32
        )
        now = int(
            time.time()
        )

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO auth_tokens (
                    user_id,
                    token_hash,
                    purpose,
                    expires_at,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    self.hash_token(token),
                    purpose,
                    now + expires_in_minutes * 60,
                    now
                )
            )

        return token

    def consume_auth_token(
        self,
        token: str,
        purpose: str
    ) -> AuthUser | None:
        token_hash = self.hash_token(
            token
        )
        now = int(
            time.time()
        )

        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT user_id
                FROM auth_tokens
                WHERE token_hash = ?
                  AND purpose = ?
                  AND used_at IS NULL
                  AND expires_at >= ?
                """,
                (
                    token_hash,
                    purpose,
                    now
                )
            ).fetchone()

            if not row:
                return None

            connection.execute(
                """
                UPDATE auth_tokens
                SET used_at = ?
                WHERE token_hash = ?
                """,
                (
                    now,
                    token_hash
                )
            )

        return self.get_user_by_id(
            int(row[0])
        )

    def create_email_verification_token(
        self,
        user_id: int
    ) -> str:
        return self.create_auth_token(
            user_id=user_id,
            purpose="email_verification",
            expires_in_minutes=settings.AUTH_EMAIL_VERIFICATION_TOKEN_MINUTES
        )

    def verify_email_token(
        self,
        token: str
    ) -> AuthUser | None:
        user = self.consume_auth_token(
            token,
            "email_verification"
        )

        if not user:
            return None

        self.update_user(
            user.user_id,
            email_verified=True
        )

        return self.get_user_by_id(
            user.user_id
        )

    def create_password_reset_token(
        self,
        email: str
    ) -> str | None:
        user = self.get_user_by_email(
            email
        )

        if not user:
            return None

        return self.create_auth_token(
            user_id=user.user_id,
            purpose="password_reset",
            expires_in_minutes=settings.AUTH_PASSWORD_RESET_TOKEN_MINUTES
        )

    def reset_password_with_token(
        self,
        token: str,
        new_password: str
    ) -> AuthUser | None:
        user = self.consume_auth_token(
            token,
            "password_reset"
        )

        if not user:
            return None

        with self.connect() as connection:
            connection.execute(
                """
                UPDATE users
                SET password_hash = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    self.hash_password(new_password),
                    int(time.time()),
                    user.user_id
                )
            )

        return self.get_user_by_id(
            user.user_id
        )

    def update_user(
        self,
        user_id: int,
        *,
        role: str | None = None,
        active: bool | None = None,
        email_verified: bool | None = None
    ) -> AuthUser | None:
        fields = []
        values = []

        if role is not None:
            fields.append(
                "role = ?"
            )
            values.append(
                role
            )

        if active is not None:
            fields.append(
                "active = ?"
            )
            values.append(
                1 if active else 0
            )

        if email_verified is not None:
            fields.append(
                "email_verified = ?"
            )
            values.append(
                1 if email_verified else 0
            )

        if not fields:
            return self.get_user_by_id(
                user_id
            )

        fields.append(
            "updated_at = ?"
        )
        values.append(
            int(time.time())
        )
        values.append(
            user_id
        )

        with self.connect() as connection:
            connection.execute(
                f"""
                UPDATE users
                SET {", ".join(fields)}
                WHERE id = ?
                """,
                tuple(values)
            )

        return self.get_user_by_id(
            user_id
        )

    def list_users(
        self,
        limit: int = 100
    ) -> list[AuthUser]:
        bounded_limit = max(
            1,
            min(
                int(limit),
                500
            )
        )

        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, email, full_name, password_hash, role, active, email_verified
                FROM users
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    bounded_limit,
                )
            ).fetchall()

        return [
            user
            for user in (
                self.row_to_user(row)
                for row in rows
            )
            if user is not None
        ]

    def apply_initial_admins(
        self,
        emails: list[str]
    ):
        for email in emails:
            user = self.get_user_by_email(
                email
            )

            if user:
                self.update_user(
                    user.user_id,
                    role="admin",
                    email_verified=True
                )


class TokenService:

    def __init__(
        self,
        secret: str = settings.AUTH_TOKEN_SECRET,
        expire_minutes: int = settings.AUTH_TOKEN_EXPIRE_MINUTES
    ):
        self.secret = secret.encode("utf-8")
        self.expire_minutes = expire_minutes

    @staticmethod
    def encode_part(
        payload: dict
    ) -> str:
        raw = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True
        ).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    @staticmethod
    def decode_part(
        value: str
    ) -> dict:
        padded = value + "=" * (-len(value) % 4)
        return json.loads(
            base64.urlsafe_b64decode(padded.encode("utf-8"))
        )

    def sign(
        self,
        value: str
    ) -> str:
        return base64.urlsafe_b64encode(
            hmac.new(
                self.secret,
                value.encode("utf-8"),
                hashlib.sha256
            ).digest()
        ).decode("utf-8").rstrip("=")

    def create_token(
        self,
        user: AuthUser
    ) -> str:
        header = {
            "alg": "HS256",
            "typ": "JWT"
        }
        now = int(time.time())
        payload = {
            "sub": str(user.user_id),
            "email": user.email,
            "role": user.role,
            "iat": now,
            "exp": now + self.expire_minutes * 60
        }
        unsigned = (
            f"{self.encode_part(header)}."
            f"{self.encode_part(payload)}"
        )
        return f"{unsigned}.{self.sign(unsigned)}"

    def verify_token(
        self,
        token: str
    ) -> dict | None:
        try:
            header, payload, signature = token.split(".")
        except ValueError:
            return None

        unsigned = f"{header}.{payload}"
        if not hmac.compare_digest(
            self.sign(unsigned),
            signature
        ):
            return None

        data = self.decode_part(
            payload
        )

        if int(data.get("exp", 0)) < int(time.time()):
            return None

        return data
