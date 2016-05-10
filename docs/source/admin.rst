===================
Administrator guide
===================

.. toctree::
   :maxdepth: 2

Audience
--------

This guide is intended for system administrators and/or facility managers
who need to configure the MyTardis Sequencing Facility app.


Default database fixtures
-------------------------

see :doc:`installation`.


Creating a Facility
-------------------


Creating Facility groups and users
----------------------------------

**TODO:** facility manager group
**TODO:** ingestor user


Adding Instruments to a Facility
--------------------------------



Adding new storage locations     
----------------------------

MyTardis uses the concept of a ``StorageBox`` to mount storage locations for
files - these might be locations on local disk or network file shares,
SFTP locations or object storage services like Amazon S3 or OpenStack Swift.

See the `MyTardis StorageBox <http://mytardis.readthedocs.io/en/develop/admin/storage.html>`_
documentation for more detail on how to configure a ``StorageBox``.

The `mytardis_ngs_ingestor <https://github.com/pansapiens/mytardis_ngs_ingestor>`_
client can be configured to push data to any StorageBox configured in MyTardis.
The ingestor uses two ``StorageBox`` targets - one for large files that aren't
guaranteed to be immediately available on demand, and one for small files that
need to be served immediately upon page views (eg. FastQC HTML reports).
These are the ``storage_box_name`` and ``live_storage_box_name``, respectively, in
the ingestors ``uploader_config.yaml``.

This segregation allows large (eg ``*.fastq.gz``) files to be migrated to an
archival storage box flagged with the ``StorageBoxAttribute`` ``{'type': 'tape'}``,
such as a tape library or HSM, where MyTardis will notify the user once a
delayed retrieval is complete.
