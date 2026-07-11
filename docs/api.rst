API Reference
=============

Core
----

.. autoclass:: zipwire.SyncRemoteZip
   :members:
   :special-members: __enter__, __exit__

.. autoclass:: zipwire.AsyncRemoteZip
   :members:
   :special-members: __aenter__, __aexit__

.. autoclass:: zipwire.RemoteZipInfo
   :show-inheritance:

Backends
--------

.. autoclass:: zipwire.backends._urllib3.Urllib3Reader
   :members:

.. autoclass:: zipwire.backends._httpx2_sync.Httpx2SyncReader
   :members:

.. autoclass:: zipwire.backends._httpx2_async.Httpx2AsyncReader
   :members:

.. autoclass:: zipwire.backends._requests.RequestsReader
   :members:

.. autoclass:: zipwire.backends._aiohttp.AiohttpReader
   :members:

Exceptions
----------

.. code-block:: text

   Exception
   └── ZipwireError
       ├── BadZipFile
       ├── UnsupportedCompression
       ├── CRCMismatch
       ├── RangeRequestUnsupported
       └── FileNotFoundInZip (also inherits KeyError)

.. autoexception:: zipwire.ZipwireError
   :show-inheritance:

.. autoexception:: zipwire.BadZipFile
   :show-inheritance:

.. autoexception:: zipwire.UnsupportedCompression
   :show-inheritance:

.. autoexception:: zipwire.CRCMismatch
   :show-inheritance:

.. autoexception:: zipwire.RangeRequestUnsupported
   :show-inheritance:

.. autoexception:: zipwire.FileNotFoundInZip
   :show-inheritance:
