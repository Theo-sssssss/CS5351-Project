# 认证与授权：密码使用带盐 PBKDF2 摘要，登录后签发带租户和角色的限时令牌。

"""Authentication, signed sessions and tenant-aware role checks."""
import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Iterable, Optional


ROLE_PERMISSIONS = {
    "admin": {"read", "review", "fix", "manage", "audit"},
    "maintainer": {"read", "review", "fix"},
    "auditor": {"read", "audit"},
}


# 生成随机盐并执行 PBKDF2，保存算法、迭代次数、盐和摘要以便后续校验。
def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    if len(password) < 10:
        raise ValueError("password must contain at least 10 characters")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return "pbkdf2_sha256$310000$%s$%s" % (
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    )


# 读取已存储的盐和迭代次数重算密码摘要，并用恒定时间比较校验。
def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# 使用 URL 安全的 Base64 编码，并去掉令牌中可省略的填充符。
def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


# 补齐 Base64 填充符后解码，兼容令牌中的无填充表示。
def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


# 已经认证的身份快照，包含用户、租户与角色。
@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    tenant_id: str
    role: str

    # 查询当前角色是否包含指定权限；未知角色没有默认权限。
    def can(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())


# 管理密码登录、令牌签发和权限检查。
class AuthManager:
    # 保存令牌签名配置；提供初始账号密码时创建管理员及其租户成员关系。
    def __init__(
        self, store, secret: str, ttl_seconds: int = 3600,
        bootstrap_username: str = "", bootstrap_password: str = "",
        default_tenant_id: str = "default",
    ):
        self.store = store
        self.secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds
        self.default_tenant_id = default_tenant_id
        if bootstrap_username and bootstrap_password:
            self.store.create_user(
                str(uuid.uuid5(uuid.NAMESPACE_URL, "evoagent:" + bootstrap_username)),
                bootstrap_username, hash_password(bootstrap_password),
                default_tenant_id, "admin",
            )

    # 验证账号密码与租户成员关系，签发包含租户、角色和到期时间的令牌。
    def login(self, username: str, password: str, tenant_id: str = "") -> Dict[str, object]:
        user = self.store.get_user(username)
        if not user or not user["active"] or not verify_password(password, user["password_hash"]):
            raise PermissionError("invalid username or password")
        memberships = {item["tenant_id"]: item["role"] for item in user["memberships"]}
        selected = tenant_id or (next(iter(memberships)) if len(memberships) == 1 else "")
        if not selected or selected not in memberships:
            raise PermissionError("user is not a member of the requested tenant")
        now = int(time.time())
        payload = {
            "sub": user["id"], "username": user["username"], "tenant": selected,
            "role": memberships[selected], "iat": now, "exp": now + self.ttl_seconds,
        }
        token = self._encode(payload)
        return {"access_token": token, "token_type": "Bearer", "expires_in": self.ttl_seconds,
                "tenant_id": selected, "role": memberships[selected]}

    # 解析 Bearer 令牌并验证签名，构造后续权限校验使用的身份对象。
    def authenticate(self, authorization: str) -> Principal:
        if not authorization.startswith("Bearer "):
            raise PermissionError("Bearer token is required")
        payload = self._decode(authorization[7:].strip())
        return Principal(
            str(payload["sub"]), str(payload["username"]),
            str(payload["tenant"]), str(payload["role"]),
        )

    # 要求身份同时具备给定权限，缺少任意一项即拒绝访问。
    @staticmethod
    def require(principal: Principal, permissions: Iterable[str]) -> None:
        missing = [permission for permission in permissions if not principal.can(permission)]
        if missing:
            raise PermissionError("permission denied")

    # 对稳定序列化的头部和载荷计算 HMAC-SHA256，生成签名令牌。
    def _encode(self, payload: Dict[str, object]) -> str:
        header = _b64(b'{"alg":"HS256","typ":"JWT"}')
        body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signing_input = (header + "." + body).encode("ascii")
        signature = _b64(hmac.new(self.secret, signing_input, hashlib.sha256).digest())
        return header + "." + body + "." + signature

    # 校验令牌签名、有效期及角色，并将格式错误统一转为认证失败。
    def _decode(self, token: str) -> Dict[str, object]:
        try:
            header, body, supplied = token.split(".", 2)
            signing_input = (header + "." + body).encode("ascii")
            expected = _b64(hmac.new(self.secret, signing_input, hashlib.sha256).digest())
            if not hmac.compare_digest(expected, supplied):
                raise PermissionError("invalid token")
            payload = json.loads(_unb64(body).decode("utf-8"))
            if int(payload["exp"]) < int(time.time()):
                raise PermissionError("token has expired")
            if payload.get("role") not in ROLE_PERMISSIONS:
                raise PermissionError("invalid role")
            return payload
        except PermissionError:
            raise
        except Exception as exc:
            raise PermissionError("invalid token") from exc
