Quick Start
===========

Synchronous usage
-----------------

List files in a remote ZIP
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from zipwire import SyncRemoteZip
   from zipwire.backends import Urllib3Reader

   reader = Urllib3Reader("https://archive.example/data.zip")
   with SyncRemoteZip(reader) as rz:
       for info in rz.infolist():
           print(f"{info.filename}  {info.file_size} bytes")

Read a single file into memory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from zipwire import SyncRemoteZip
   from zipwire.backends import Httpx2SyncReader

   reader = Httpx2SyncReader("https://archive.example/data.zip")
   with SyncRemoteZip(reader) as rz:
       data = rz.read("path/to/file.txt")

Stream a file to disk
^^^^^^^^^^^^^^^^^^^^^

:meth:`~zipwire.SyncRemoteZip.read_into` streams the compressed payload in
chunks and decompresses on the fly, keeping peak memory low even for large
entries:

.. code-block:: python

   from zipwire import SyncRemoteZip
   from zipwire.backends import RequestsReader

   reader = RequestsReader("https://archive.example/large.zip")
   with SyncRemoteZip(reader) as rz:
       with open("output.bin", "wb") as f:
           rz.read_into("big-file.bin", f)

Asynchronous usage
------------------

Async with aiohttp
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   import asyncio

   from zipwire import AsyncRemoteZip
   from zipwire.backends import AiohttpReader


   async def main():
       reader = AiohttpReader("https://archive.example/data.zip")
       async with AsyncRemoteZip(reader) as rz:
           data = await rz.read("path/to/file.txt")
           print(data.decode())


   asyncio.run(main())

Async with httpx2
^^^^^^^^^^^^^^^^^

.. code-block:: python

   import asyncio

   from zipwire import AsyncRemoteZip
   from zipwire.backends import Httpx2AsyncReader


   async def main():
       reader = Httpx2AsyncReader("https://archive.example/data.zip")
       async with AsyncRemoteZip(reader) as rz:
           names = await rz.namelist()
           print(names)


   asyncio.run(main())

Async streaming to disk
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   import asyncio

   from zipwire import AsyncRemoteZip
   from zipwire.backends import AiohttpReader


   async def main():
       reader = AiohttpReader("https://archive.example/large.zip")
       async with AsyncRemoteZip(reader) as rz:
           with open("output.bin", "wb") as f:
               await rz.read_into("big-file.bin", f)


   asyncio.run(main())

Passing a pre-configured client
--------------------------------

All backends accept an optional pre-configured client or session:

.. code-block:: python

   import httpx2

   from zipwire import SyncRemoteZip
   from zipwire.backends import Httpx2SyncReader

   with httpx2.Client(headers={"Authorization": "Bearer token"}) as client:
       reader = Httpx2SyncReader(
           "https://archive.example/data.zip", client=client
       )
       with SyncRemoteZip(reader) as rz:
           data = rz.read("secret.txt")
