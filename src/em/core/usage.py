"""代理首次使用预占：持久化账户预算与进程预算，不推断供应商实际扣费。"""

import hashlib
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit

import requests

from em.core import budget
from em.core.errors import ConfigError, ProxyQuotaExceededError, ProxyUnavailableError

UsagePhase = Literal["prefilter", "business"]


@dataclass(frozen=True)
class UsageLease:
    token: str
    source: str
    expires_at: float


@dataclass
class UsageOutcome:
    sent: bool = False
    status_code: int | None = None
    error_type: str | None = None
    accepted: bool | None = None


_outcome: ContextVar[UsageOutcome | None] = ContextVar("proxy_usage_outcome", default=None)


def usage_http_started() -> None:
    outcome = _outcome.get()
    if outcome is not None:
        outcome.sent = True


def usage_http_result(status_code: int | None = None, error: BaseException | None = None) -> None:
    outcome = _outcome.get()
    if outcome is not None:
        outcome.status_code = status_code
        if error is not None:
            outcome.error_type = type(error).__name__


def proxy_identity(proxy: str) -> str:
    parsed = urlsplit(proxy if "://" in proxy else f"http://{proxy}")
    return hashlib.sha256(f"{parsed.hostname}:{parsed.port}".encode()).hexdigest()


def _count_balance(payload: Any) -> tuple[int, int]:
    if not isinstance(payload, dict) or payload.get("success") not in (True, "true"):
        raise ValueError("余额查询未成功")
    packages = payload.get("data")
    if not isinstance(packages, list):
        raise ValueError("余额查询套餐格式无效")
    counts = [
        entry for entry in packages if isinstance(entry, dict) and entry.get("type") == "次数套餐"
    ]
    if len(counts) != 1 or counts[0].get("valid") not in (True, "true"):
        raise ValueError("次数套餐缺失、失效或不唯一")
    numbers = []
    for name in ("num", "use"):
        value = counts[0].get(name)
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError("次数字段必须为非负整数")
        text = str(value).strip()
        if not text.isascii() or not text.isdigit():
            raise ValueError("次数字段必须为非负整数")
        numbers.append(int(text))
    total, used = numbers
    if used > total:
        raise ValueError("已用次数超过总额")
    return total, used


class ProxyUsage:
    """同一SQLite文件跨客户端、跨进程共享账户预占，失败不自动退款。"""

    def __init__(
        self,
        path: str,
        apis: list[str],
        free_limit: int,
        paid_limit: int,
        max_new: int | None = None,
        balance_url: str = "",
        balance_refresh_sec: int = 30,
    ) -> None:
        if min(free_limit, paid_limit) < 0 or (max_new is not None and max_new < 0):
            raise ConfigError("代理使用额度不能为负")
        self.path = Path(path).expanduser().resolve()
        self.balance_url = balance_url.strip()
        self.balance_refresh_sec = max(balance_refresh_sec, 1)
        self._balance_lock = threading.Lock()
        self._balance_checked_at = -float("inf")
        self._remote_payload: dict[str, Any] | None = None
        self.sources: dict[str, str] = {}
        kinds: dict[str, str] = {}
        accounts = set()
        for api in apis:
            parsed = urlsplit(api)
            query = parse_qs(parsed.query)
            kind = {"0": "free", "2": "paid"}.get(query.get("type", [""])[0])
            if (
                parsed.hostname != "api.xiequ.cn"
                or kind is None
                or len(query.get("type", [])) != 1
                or len(query.get("uid", [])) != 1
            ):
                raise ConfigError("启用使用额度时须配置可识别的携趣 type=0/2 与 uid")
            account = hashlib.sha256(f"{parsed.hostname}:{query['uid'][0]}".encode()).hexdigest()
            accounts.add(account)
            source = f"{account}:{kind}"
            self.sources[api] = source
            kinds[source] = kind
        if len(accounts) != 1:
            raise ConfigError("一个使用额度账本必须对应同一供应商账号")
        self.account_id = next(iter(accounts))
        if self.balance_url:
            parsed_balance = urlsplit(self.balance_url)
            balance_query = parse_qs(parsed_balance.query)
            balance_uid = balance_query.get("uid", [])
            if (
                parsed_balance.scheme != "https"
                or parsed_balance.hostname != "op.xiequ.cn"
                or parsed_balance.path != "/ApiUser.aspx"
                or parsed_balance.username is not None
                or parsed_balance.password is not None
                or parsed_balance.port not in (None, 443)
                or parsed_balance.fragment
                or balance_query.get("act") != ["suitdt"]
                or len(balance_uid) != 1
                or len(balance_query.get("ukey", [])) != 1
                or hashlib.sha256(f"api.xiequ.cn:{balance_uid[0]}".encode()).hexdigest()
                != self.account_id
            ):
                raise ConfigError("余额查询须为同账号的 HTTPS suitdt 接口")
        self.run_id = uuid.uuid4().hex
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS accounts (
                source TEXT PRIMARY KEY, kind TEXT NOT NULL, quota INTEGER NOT NULL,
                reserved INTEGER NOT NULL DEFAULT 0,
                prefilter_used INTEGER NOT NULL DEFAULT 0,
                business_used INTEGER NOT NULL DEFAULT 0,
                prefilter_attempts INTEGER NOT NULL DEFAULT 0,
                business_attempts INTEGER NOT NULL DEFAULT 0)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, quota INTEGER, reserved INTEGER NOT NULL DEFAULT 0)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS leases (
                token TEXT PRIMARY KEY, source TEXT NOT NULL, identity TEXT NOT NULL,
                expires REAL NOT NULL, reserved INTEGER NOT NULL DEFAULT 0,
                prefilter INTEGER NOT NULL DEFAULT 0, business INTEGER NOT NULL DEFAULT 0)""")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS lease_identity ON leases(source,identity)"
            )
            connection.execute("""CREATE TABLE IF NOT EXISTS usage_batches (
                id TEXT PRIMARY KEY, run_id TEXT NOT NULL, client_id TEXT NOT NULL,
                source TEXT NOT NULL, created REAL NOT NULL, returned INTEGER NOT NULL)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS usage_deliveries (
                batch_id TEXT NOT NULL, lease_token TEXT NOT NULL, identity TEXT NOT NULL,
                expires REAL NOT NULL, PRIMARY KEY(batch_id,lease_token))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS usage_attempts (
                id TEXT PRIMARY KEY, run_id TEXT NOT NULL, client_id TEXT NOT NULL,
                batch_id TEXT, lease_token TEXT NOT NULL, source TEXT NOT NULL,
                identity TEXT NOT NULL, phase TEXT NOT NULL, first_use INTEGER NOT NULL,
                started REAL NOT NULL, finished REAL, elapsed REAL,
                state TEXT NOT NULL DEFAULT 'pending', sent INTEGER NOT NULL DEFAULT 0,
                status_code INTEGER, error_type TEXT, accepted INTEGER)""")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS usage_attempt_client ON usage_attempts(client_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS usage_batch_client ON usage_batches(client_id)"
            )
            connection.execute("""CREATE TABLE IF NOT EXISTS remote_limits (
                account_id TEXT PRIMARY KEY, ceiling INTEGER NOT NULL, total INTEGER NOT NULL,
                used INTEGER NOT NULL, queried REAL NOT NULL, checked REAL NOT NULL)""")
            for source, kind in kinds.items():
                quota = free_limit if kind == "free" else paid_limit
                connection.execute(
                    "INSERT OR IGNORE INTO accounts(source,kind,quota) VALUES (?,?,?)",
                    (source, kind, quota),
                )
                existing = connection.execute(
                    "SELECT quota FROM accounts WHERE source=?", (source,)
                ).fetchone()
                if existing[0] != quota:
                    raise ConfigError("额度账本已有不同初始余额；请先核对账本，不能自动重置")
            connection.execute("INSERT INTO runs(id,quota) VALUES (?,?)", (self.run_id, max_new))
            saved = connection.execute(
                "SELECT total,used,checked FROM remote_limits WHERE account_id=?",
                (self.account_id,),
            ).fetchone()
            if saved is not None:
                self._remote_payload = {
                    "total": saved[0],
                    "used": saved[1],
                    "available": saved[0] - saved[1],
                    "checked_at": saved[2],
                }

    @contextmanager
    def _transaction(self, enforce_budget: bool = True) -> Iterator[sqlite3.Connection]:
        remaining = budget.remaining() if enforce_budget else None
        connection = sqlite3.connect(
            self.path,
            timeout=min(10, remaining) if remaining is not None else 10,
            isolation_level=None,
        )
        try:
            connection.execute("BEGIN IMMEDIATE")
            if enforce_budget:
                budget.remaining()
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _capacity(self, connection: sqlite3.Connection, source: str) -> bool:
        account = connection.execute(
            "SELECT quota,reserved FROM accounts WHERE source=?", (source,)
        ).fetchone()
        run = connection.execute(
            "SELECT quota,reserved FROM runs WHERE id=?", (self.run_id,)
        ).fetchone()
        available = account[0] - account[1] if account is not None else 0
        remote = self._remote_capacity(connection)
        if remote is not None:
            available = min(available, remote)
        return available > 0 and (run[0] is None or run[1] < run[0])

    def _reserved_total(self, connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT COALESCE(SUM(reserved),0) FROM accounts WHERE source IN (?,?)",
            (f"{self.account_id}:free", f"{self.account_id}:paid"),
        ).fetchone()
        return int(row[0])

    def _remote_capacity(self, connection: sqlite3.Connection) -> int | None:
        row = connection.execute(
            "SELECT ceiling FROM remote_limits WHERE account_id=?", (self.account_id,)
        ).fetchone()
        return max(0, row[0] - self._reserved_total(connection)) if row is not None else None

    def refresh_balance(self, force: bool = False) -> dict[str, Any] | None:
        """查询账号级次数套餐；失败保留本地保守额度，不抛网络异常。"""
        if not self.balance_url:
            return None
        with budget.acquire_lock(self._balance_lock):
            now = time.monotonic()
            if not force and now - self._balance_checked_at < self.balance_refresh_sec:
                return dict(self._remote_payload) if self._remote_payload is not None else None
            with self._transaction() as connection:
                reserved_before = self._reserved_total(connection)
            query_started = time.time()
            try:
                with requests.Session() as session:
                    session.trust_env = False
                    response = session.get(
                        self.balance_url, timeout=budget.timeouts(3.0, 8.0), allow_redirects=False
                    )
                if response.status_code != 200:
                    raise ValueError("余额接口未返回HTTP200")
                total, used = _count_balance(response.json())
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                requests.RequestException,
            ):
                self._balance_checked_at = time.monotonic()
                return dict(self._remote_payload) if self._remote_payload is not None else None
            checked_at = time.time()
            ceiling = reserved_before + total - used
            with self._transaction() as connection:
                connection.execute(
                    """INSERT INTO remote_limits VALUES (?,?,?,?,?,?)
                    ON CONFLICT(account_id) DO UPDATE SET
                    ceiling=MIN(remote_limits.ceiling,excluded.ceiling),
                    total=CASE WHEN excluded.queried>=remote_limits.queried THEN excluded.total ELSE remote_limits.total END,
                    used=CASE WHEN excluded.queried>=remote_limits.queried THEN excluded.used ELSE remote_limits.used END,
                    checked=CASE WHEN excluded.queried>=remote_limits.queried THEN excluded.checked ELSE remote_limits.checked END,
                    queried=MAX(remote_limits.queried,excluded.queried)""",
                    (self.account_id, ceiling, total, used, query_started, checked_at),
                )
                saved = connection.execute(
                    "SELECT total,used,checked FROM remote_limits WHERE account_id=?",
                    (self.account_id,),
                ).fetchone()
            self._remote_payload = {
                "available": saved[0] - saved[1],
                "total": saved[0],
                "used": saved[1],
                "checked_at": saved[2],
            }
            self._balance_checked_at = time.monotonic()
            return dict(self._remote_payload)

    def can_start(self, api: str) -> bool:
        self.refresh_balance()
        with self._transaction() as connection:
            return self._capacity(connection, self.sources[api])

    def record_delivery(self, api: str, client_id: str, returned: int) -> str:
        identifier = uuid.uuid4().hex
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO usage_batches VALUES (?,?,?,?,?,?)",
                (identifier, self.run_id, client_id, self.sources[api], time.time(), returned),
            )
        return identifier

    def register(
        self,
        api: str,
        proxy: str,
        expires_at: float,
        batch_id: str | None = None,
    ) -> UsageLease:
        source = self.sources[api]
        identity = proxy_identity(proxy)
        now = time.time()
        with self._transaction() as connection:
            connection.execute("DELETE FROM leases WHERE expires<=?", (now,))
            existing = connection.execute(
                "SELECT token,expires FROM leases WHERE source=? AND identity=? AND expires>?",
                (source, identity, now),
            ).fetchone()
            if existing is not None:
                lease = UsageLease(existing[0], source, existing[1])
            else:
                token = uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO leases(token,source,identity,expires) VALUES (?,?,?,?)",
                    (token, source, identity, expires_at),
                )
                lease = UsageLease(token, source, expires_at)
            if batch_id is not None:
                batch = connection.execute(
                    "SELECT source FROM usage_batches WHERE id=?", (batch_id,)
                ).fetchone()
                if batch is None or batch[0] != source:
                    raise ConfigError("代理交付批次与来源不匹配")
                connection.execute(
                    "INSERT OR IGNORE INTO usage_deliveries VALUES (?,?,?,?)",
                    (batch_id, lease.token, identity, lease.expires_at),
                )
        return lease

    def can_use(self, lease: UsageLease) -> bool:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT reserved,expires FROM leases WHERE token=? AND source=?",
                (lease.token, lease.source),
            ).fetchone()
            return (
                row is not None
                and row[1] > time.time()
                and (bool(row[0]) or self._capacity(connection, lease.source))
            )

    def reserve(self, lease: UsageLease, phase: UsagePhase, client_id: str = "") -> str:
        if phase not in ("prefilter", "business"):
            raise ValueError("unknown proxy usage phase")
        self.refresh_balance()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT reserved,expires,prefilter,business,identity FROM leases WHERE token=? AND source=?",
                (lease.token, lease.source),
            ).fetchone()
            if row is None or row[1] <= time.time():
                raise ProxyUnavailableError("代理使用租期已过期")
            delivery = connection.execute(
                """SELECT batch.id FROM usage_batches AS batch
                JOIN usage_deliveries AS delivery ON delivery.batch_id=batch.id
                WHERE batch.client_id=? AND delivery.lease_token=? AND batch.source=?
                ORDER BY batch.created DESC LIMIT 1""",
                (client_id, lease.token, lease.source),
            ).fetchone()
            if client_id and delivery is None:
                raise ProxyQuotaExceededError("当前客户端缺少代理交付记录，拒绝使用")
            if not row[0]:
                if not self._capacity(connection, lease.source):
                    raise ProxyQuotaExceededError("代理首次使用预算已耗尽")
                connection.execute(
                    "UPDATE accounts SET reserved=reserved+1 WHERE source=?", (lease.source,)
                )
                connection.execute("UPDATE runs SET reserved=reserved+1 WHERE id=?", (self.run_id,))
                connection.execute("UPDATE leases SET reserved=1 WHERE token=?", (lease.token,))
            first_phase_use = not row[2 if phase == "prefilter" else 3]
            if phase == "prefilter":
                connection.execute(
                    """UPDATE accounts SET prefilter_used=prefilter_used+?,
                    prefilter_attempts=prefilter_attempts+1 WHERE source=?""",
                    (int(first_phase_use), lease.source),
                )
                connection.execute("UPDATE leases SET prefilter=1 WHERE token=?", (lease.token,))
            else:
                connection.execute(
                    """UPDATE accounts SET business_used=business_used+?,
                    business_attempts=business_attempts+1 WHERE source=?""",
                    (int(first_phase_use), lease.source),
                )
                connection.execute("UPDATE leases SET business=1 WHERE token=?", (lease.token,))
            attempt_id = uuid.uuid4().hex
            connection.execute(
                """INSERT INTO usage_attempts
                (id,run_id,client_id,batch_id,lease_token,source,identity,phase,first_use,started)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    attempt_id,
                    self.run_id,
                    client_id,
                    delivery[0] if delivery else None,
                    lease.token,
                    lease.source,
                    row[4],
                    phase,
                    int(not row[0]),
                    time.time(),
                ),
            )
        return attempt_id

    @contextmanager
    def attempt(
        self, lease: UsageLease, phase: UsagePhase, client_id: str
    ) -> Iterator[UsageOutcome]:
        attempt_id = self.reserve(lease, phase, client_id)
        outcome = UsageOutcome()
        context_token = _outcome.set(outcome)
        began = time.monotonic()
        try:
            yield outcome
        except BaseException as error:
            if outcome.error_type is None:
                outcome.error_type = type(error).__name__
            outcome.accepted = False
            raise
        finally:
            _outcome.reset(context_token)
            with self._transaction(enforce_budget=False) as connection:
                connection.execute(
                    """UPDATE usage_attempts SET finished=?,elapsed=?,state='finished',
                    sent=?,status_code=?,error_type=?,accepted=? WHERE id=?""",
                    (
                        time.time(),
                        time.monotonic() - began,
                        int(outcome.sent),
                        outcome.status_code,
                        outcome.error_type,
                        outcome.accepted,
                        attempt_id,
                    ),
                )

    def client_audit(self, client_id: str) -> dict[str, Any]:
        """当前客户端交付与使用明细；只返回匿名身份，不返回密钥或出口地址。"""
        with self._transaction(enforce_budget=False) as connection:
            connection.row_factory = sqlite3.Row
            batches = [
                dict(row)
                for row in connection.execute(
                    """SELECT id,run_id,client_id,
                substr(source,instr(source,':')+1) AS source,created,returned
                FROM usage_batches WHERE client_id=? ORDER BY created,id""",
                    (client_id,),
                )
            ]
            attempts = [
                dict(row)
                for row in connection.execute(
                    """SELECT id,run_id,client_id,batch_id,
                lease_token,substr(source,instr(source,':')+1) AS source,identity,phase,first_use,
                started,finished,elapsed,state,sent,status_code,error_type,accepted
                FROM usage_attempts WHERE client_id=? ORDER BY started,id""",
                    (client_id,),
                )
            ]
        return {
            "client_id": client_id,
            "batches": batches,
            "attempts": attempts,
            "summary": {
                "fetch_calls": len(batches),
                "returned": sum(row["returned"] for row in batches),
                "attempts": len(attempts),
                "first_uses": sum(row["first_use"] for row in attempts),
                "pending": sum(row["state"] == "pending" for row in attempts),
                "successful_http": sum(row["status_code"] == 200 for row in attempts),
                "accepted": sum(row["accepted"] == 1 for row in attempts),
            },
        }

    def snapshot(self) -> dict[str, Any]:
        with self._transaction() as connection:
            rows = connection.execute("""SELECT source,kind,quota,reserved,prefilter_used,
                business_used,prefilter_attempts,business_attempts FROM accounts""").fetchall()
            run = connection.execute(
                "SELECT quota,reserved FROM runs WHERE id=?", (self.run_id,)
            ).fetchone()
            remote_capacity = self._remote_capacity(connection)
            remote_row = connection.execute(
                "SELECT total,used,checked FROM remote_limits WHERE account_id=?",
                (self.account_id,),
            ).fetchone()
        active = set(self.sources.values())
        return {
            "basis": "local_first_use_reservations_not_provider_billing",
            "account": {
                row[1]: {
                    "initial": row[2],
                    "reserved": row[3],
                    "remaining": row[2] - row[3],
                    "prefilter_used": row[4],
                    "business_used": row[5],
                    "prefilter_attempts": row[6],
                    "business_attempts": row[7],
                }
                for row in rows
                if row[0] in active
            },
            "run": {"limit": run[0], "reserved": run[1]},
            "remote_balance": {
                "total": remote_row[0],
                "used": remote_row[1],
                "available": remote_row[0] - remote_row[1],
                "checked_at": remote_row[2],
            }
            if remote_row is not None
            else None,
            "remote_guard_remaining": remote_capacity,
        }
