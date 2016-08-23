==================
Installation guide
==================

.. toctree::
   :maxdepth: 2

Audience
--------

This guide is intended for system administrator installing the of the
MyTardis Sequencing Facility in a production setting.


Install MyTardis
----------------

Refer to the `MyTardis installation documentation <https://mytardis.readthedocs.io/en/develop/admin/install.html>`_.

Install the mytardis-seqfac app
-------------------------------

Install the ``sequencing_facility`` app in the same virtual environment as
your MyTardis server.

``pip install -U git+https://github.com/mytardis/mytardis-seqfac.git#egg=sequencing-facility``

Add the app ``sequencing_facility`` to your ``INSTALLED_APPS`` in MyTardis/Django settings.

eg, ``INSTALLED_APPS += ('sequencing_facility',)``

The ``sequencing_facility`` app comes with it's own `default settings <https://github.com/mytardis/mytardis-seqfac/blob/master/sequencing_facility/settings.py>`_.


Edit the mytardis-seqfac settings.py
------------------------------------



Create required database records from fixtures
----------------------------------------------

**TODO:** Pre-populating the database with models from fixtures.
          Setting correct permissions on ingestor and facility manager user


Install and configure the ingestion client
------------------------------------------

``mytardis-seq`` is designed to work with the `mytardis_ngs_ingestor <https://github.com/pansapiens/mytardis_ngs_ingestor>`_
client for registering and uploading files from sequencing runs.

TODO: Link to client install guide

TODO: Command to run test from test data included with the client
