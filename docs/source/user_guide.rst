==========
User guide
==========

.. toctree::
   :maxdepth: 2


This guide is intended for end users of the MyTardis Sequencing Facility app
- those sharing and downloading data produced by a facility.


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

**TODO:** Brief info here.

Direct download via HTTPS
~~~~~~~~~~~~~~~~~~~~~~~~~

Data can also be downloaded directly using ``wget`` or ``curl`` using an
obfusicated link.

From the Experiment view, select the Sharing tab and then click the "Create New
Temporary Link" button. The link provided leads to the Experiment page, however
the ``token`` in the link can be used to download a tar archive
of the data directly.

For example, if the provided link is:

  https://facility.example.com/experiment/view/757/?token=864CRT1TTURSIV1ITS0CV6BCWPG1JX

The direct download link is:

  https://facility.example.com/download/experiment/757/tar/?token=864CRT1TTURSIV1ITS0CV6BCWPG1JX

(where 757 is the experiment ID)

By default, temporary links expire after a month, or you can manually delete
them within the web interface once you data begins downloading. Avoid using
temporary links for sensitive datasets - use SFTP instead.