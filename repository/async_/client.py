"""
repository.async._client
~~~~~~~~~~~~~~~~~

This module implements the asynchronous HTTP client interface
and concrete implementation.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Any, Mapping, Optional, Type, Union

import aiohttp

log = logging.getLogger(__name__)


class NetworkTimeOutError(Exception):
    """Raised when a network connection times out."""

    def __init__(self, url: str, seconds: int) -> None:
        """
        Initialize the NetworkTimeOutError with the URL and timeout duration.

        Args:
            url (str): The URL that timed out
            seconds (int): The timeout duration in seconds
        """
        self.url = url
        self.seconds = seconds
        log.error(
            f"Network connection timed out after {seconds} seconds for url: {url}"
        )
        super().__init__(
            f"Network connection timed out after {seconds} seconds for url: {url}"
        )


class BaseAsyncClient(ABC):
    """Base interface for asynchronous HTTP clients."""

    @abstractmethod
    async def make_request(self, method: str, url: str, **kwargs: Any) -> Any:
        """
        Make an asynchronous HTTP request.

        Args:
            method (str): The HTTP method (GET, POST, PUT, DELETE, etc.)
            url (str): The URL to make the request to
            **kwargs: Additional keyword arguments to pass to the request

        Returns:
            Any: The response from the HTTP request

        Raises:
            NotImplementedError: If the subclass does not implement this method
        """
        raise NotImplementedError("Subclasses must implement make_request method")


class _AsyncClient(BaseAsyncClient):
    """
    Implementation of the asynchronous HTTP client interface.

    This class uses aiohttp to make asynchronous HTTP requests and
    implements the context manager protocol for proper resource management.

    Attributes:
        _session (Optional[aiohttp.ClientSession]): The aiohttp session for making requests
    """

    def __init__(self) -> None:
        """Initialize the asynchronous client without creating a session."""
        log.debug("Initializing _AsyncClient")
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "_AsyncClient":
        """
        Enter the asynchronous context manager.

        Creates a new aiohttp ClientSession that will be used for making requests.

        Returns:
            _AsyncClient: The client instance
        """
        log.debug("Creating new aiohttp ClientSession")
        self._session = aiohttp.ClientSession()
        log.debug("aiohttp ClientSession created successfully")
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Exit the asynchronous context manager.

        Closes the aiohttp ClientSession to clean up resources.

        Args:
            exc_type: The exception type if an exception was raised in the context
            exc_val: The exception value if an exception was raised in the context
            exc_tb: The traceback if an exception was raised in the context
        """
        log.debug("Exiting context manager, closing aiohttp ClientSession")
        if self._session and not self._session.closed:
            await self._session.close()
            log.debug("aiohttp ClientSession closed successfully")
        else:
            log.debug("No active aiohttp ClientSession to close")

    async def make_request(
        self, method: str, url: str, **kwargs: Union[Any, Mapping[str, Any]]
    ) -> aiohttp.ClientResponse:
        """
        Make an asynchronous HTTP request using aiohttp.

        Args:
            method (str): The HTTP method (GET, POST, PUT, DELETE, etc.)
            url (str): The URL to make the request to
            **kwargs: Additional keyword arguments to pass to the aiohttp request

        Returns:
            aiohttp.ClientResponse: The response from the HTTP request

        Raises:
            NetworkTimeOutError: If the request times out
        """
        log.info(f"Making {method} request to {url}")

        if self._session is None:
            log.error("Session not initialized. Use async with context manager.")
            raise ValueError("Session not initialized. Use async with context manager.")

        # Add timeout to prevent hanging
        timeout_seconds = 10

        try:
            kwargs.setdefault("timeout", aiohttp.ClientTimeout(total=timeout_seconds))

            async with self._session.request(method, url, **kwargs) as response:  # type: ignore
                try:
                    return await response.json()
                except (aiohttp.ContentTypeError, json.decoder.JSONDecodeError) as e:
                    raise e

        except asyncio.TimeoutError as e:
            raise NetworkTimeOutError(url, timeout_seconds) from e
