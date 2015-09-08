NAME = 'Sequencing Facility'

DATASET_VIEWS = [('http://www.tardis.edu.au/schemas/ngs/project/raw_reads',
                  'tardis.apps.sequencing_facility.views.view_project_dataset'),
                 ('http://www.tardis.edu.au/schemas/ngs/project/fastqc',
                  'tardis.apps.sequencing_facility.views.view_project_dataset')
                ]

SITE_TITLE = "Sequencing Facility"

# footer text
SPONSORED_TEXT = None

WEBCACHE_FILE_PATH = '/data/cached/'

# Workaround for using StorageBoxes on the NeCTAR Object Store
# with storages.backends.s3.S3Storage
# StorageBoxOptions can't seem to override these settings ?
#import S3
#S3.DEFAULT_HOST = 'swift.rc.nectar.org.au'
#S3.PORTS_BY_SECURITY[False] = 8888
#S3.PORTS_BY_SECURITY[True] = 8888

# When using an S3-compatible object store, ensure 'storages'
# is added to INSTALLED_APPS in the site-wide settings.py
# When using storages.backends.s3boto.S3BotoStorage with the
# NeCTAR Object Store
AWS_S3_HOST = 'swift.rc.nectar.org.au'
AWS_S3_PORT = 8888

# For S3-compatible Object Stores, setup access_key, secret_key
# and bucket_name as StorageBoxOptions
