==========
User guide
==========

.. toctree::
   :maxdepth: 2


This guide is intended for end users of the MyTardis Sequencing Facility app
- those sharing and downloading data produced by a facility.

Logging in
~~~~~~~~~~
By default, all data in MyTardis-Seq is private so you'll need to login to see
your data. If the Facility Manager has assigned you are username/password
(a 'local' Django account), you can login using these. Depending on the MyTardis
configuration you may also be able to login using your institutional
username/password (eg LDAP or Monash authcate username / password).
Ask your Facility Manager for details on the login options available.

.. image:: images/login_button.png
   :width: 700px

The front page of MyTardis lists your recent sequencing projects.

.. image:: images/experiment_screenshot.png
   :width: 700px

.. image:: images/fastq_dataset_screenshot.png
   :width: 700px


MyTardis allows download of FASTQ file in the browser, however this method often
isn't preferred for large nucleotide short read datasets which are usually
transferred to a server for assembly/alignment and other downstream analysis.

Instead, data can be download via the commandline using SFTP or an obfusicated
HTTPS URL.

Direct download via SFTP
~~~~~~~~~~~~~~~~~~~~~~~~

Experiments are accessible via SFTP (eg using the ``sftp`` commandline tool or
software like `CyberDuck <https://cyberduck.io/>`_).

Click the SFTP button on the Project Experiment page to see instructions on how
to download your data via SFTP (note that there is no SFTP button on FASTQ dataset pages).

.. image:: images/sftp_login_button.png
   :width: 700px

Direct download via HTTPS
~~~~~~~~~~~~~~~~~~~~~~~~~

Data can also be downloaded directly using ``wget`` or ``curl`` using an
obfusicated link.

From the Experiment view, select the Sharing tab and then click the "Create New
Temporary Link" button. The links to the Experiment page and a direct download
link to a ``tar`` archive are provided.

.. image:: images/sftp_login_button.png
   :width: 700px

By default temporary links expire after a month. You can manually delete
them within the web interface once you data begins downloading. Avoid using
temporary links for sensitive datasets - use SFTP instead.
