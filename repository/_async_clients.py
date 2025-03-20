import logging
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Any, Dict, Optional, Type

import aiohttp

log = logging.getLogger(__name__)


class BaseAsyncClient(ABC):
    @abstractmethod
    async def make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        pass


class _AsyncClient(BaseAsyncClient):
    def __init__(self):
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        # Add timeout to prevent hanging
        kwargs.setdefault("timeout", aiohttp.ClientTimeout(total=10))
        async with self._session.request(method, url, **kwargs) as response:
            return await response.json()
