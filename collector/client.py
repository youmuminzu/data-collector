"""礼貌的 HTTP 客户端：限速 + 重试 + 风控熔断

只负责「把一个请求安全地发出去」，不理解任何业务语义。
"""

from __future__ import annotations

import random
import time

import httpx

from .models import CircuitBroken, PageRequest

# 命中这些状态码视为风控拦截，立即停止且不再重试
DEFAULT_STOP_STATUS = frozenset({401, 403, 429})


class PoliteClient:
    """单线程串行请求，页间随机休眠，失败指数退避重试。"""

    def __init__(
        self,
        headers: dict[str, str] | None = None,
        timeout: float = 30,
        sleep_range: tuple[float, float] = (1.0, 2.0),
        max_retry: int = 3,
        retry_base: float = 2.0,
        stop_status: frozenset[int] = DEFAULT_STOP_STATUS,
        verify: bool = True,
    ) -> None:
        self.sleep_range = sleep_range
        self.max_retry = max_retry
        self.retry_base = retry_base
        self.stop_status = stop_status
        self._client = httpx.Client(
            headers=headers or {}, timeout=timeout, follow_redirects=True,
            verify=verify,
        )

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def wait(self) -> None:
        """页间限速，每次请求前调用。"""
        time.sleep(random.uniform(*self.sleep_range))

    def request(self, req: PageRequest) -> dict:
        """执行请求并返回 JSON 字典。

        抛出 CircuitBroken 表示必须立刻停止（调用方不应重试）；
        抛出 RuntimeError 表示本次失败（可重试）。
        """
        resp = self._client.request(
            req.method,
            req.url,
            json=req.json_body,
            params=req.params,
        )

        if resp.status_code in self.stop_status:
            raise CircuitBroken(
                f"HTTP {resp.status_code} —— 疑似触发风控，立即停止，不再重试"
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}")

        try:
            return resp.json()
        except ValueError as exc:
            raise RuntimeError(f"响应不是合法 JSON：{exc}") from exc
