Backends
========

zipwire uses pluggable HTTP backends to fetch byte ranges from remote
servers.  Each backend is a thin wrapper around a popular HTTP library that
implements the :class:`~zipwire.SyncReader` or :class:`~zipwire.AsyncReader`
protocol.

Available backends
------------------

.. list-table::
   :header-rows: 1
   :widths: 15 25 10 20

   * - Library
     - Class
     - Mode
     - Install extra
   * - urllib3
     - :class:`~zipwire.backends.Urllib3Reader`
     - sync
     - *(included)*
   * - httpx2
     - :class:`~zipwire.backends.Httpx2SyncReader`
     - sync
     - ``httpx2``
   * - httpx2
     - :class:`~zipwire.backends.Httpx2AsyncReader`
     - async
     - ``httpx2``
   * - requests
     - :class:`~zipwire.backends.RequestsReader`
     - sync
     - ``requests``
   * - aiohttp
     - :class:`~zipwire.backends.AiohttpReader`
     - async
     - ``aiohttp``

Choosing a backend
------------------

- **Default / no extra dependency** - use :class:`~zipwire.backends.Urllib3Reader`.
  urllib3 is already a dependency of zipwire.
- **Async with aiohttp** - use :class:`~zipwire.backends.AiohttpReader`.
  Best choice if your project already depends on aiohttp.
- **Sync + async from one library** - install ``httpx2`` and use
  :class:`~zipwire.backends.Httpx2SyncReader` or
  :class:`~zipwire.backends.Httpx2AsyncReader`.
- **Requests integration** - use :class:`~zipwire.backends.RequestsReader`
  if your project already uses ``requests`` and you want to share sessions,
  authentication, or retry configuration.

Passing an existing client
--------------------------

Every backend constructor accepts an optional pre-configured client or
session.  When you pass one, zipwire will **not** close it - you remain
responsible for its lifecycle.

.. code-block:: python

   import aiohttp

   from zipwire import AsyncRemoteZip
   from zipwire.backends import AiohttpReader

   async with aiohttp.ClientSession() as session:
       reader = AiohttpReader(
           "https://archive.example/data.zip", session=session
       )
       async with AsyncRemoteZip(reader) as rz:
           data = await rz.read("file.txt")

Writing a custom backend
-------------------------

Implement the :class:`~zipwire.SyncReader` or :class:`~zipwire.AsyncReader`
protocol and pass an instance to :class:`~zipwire.SyncRemoteZip` or
:class:`~zipwire.AsyncRemoteZip`:

.. code-block:: python

   from collections.abc import Iterator

   from zipwire import Headers, SyncReader, SyncRemoteZip, Whence


   class MyReader:
       """Minimal SyncReader implementation."""

       def __init__(self, url: str) -> None:
           self._url = url

       def head(self) -> Headers:
           ...  # HEAD request, check Accept-Ranges, return headers

       def read_range(
           self,
           offset: int,
           length: int,
           whence: int = Whence.OFFSET,
       ) -> tuple[bytes, Headers]:
           ...  # GET with Range header, return (data, response_headers)

       def stream_range(self, offset: int, length: int) -> Iterator[bytes]:
           ...  # GET with Range header, yield chunks

       def close(self) -> None:
           ...  # release resources

   assert isinstance(MyReader("..."), SyncReader)  # runtime-checkable

See the :class:`~zipwire.SyncReader` and :class:`~zipwire.AsyncReader`
protocol definitions for the full method signatures.
