NAME = 'Sequencing Facility'
SITE_TITLE = 'Sequencing Facility'

INDEX_VIEWS = {1: 'tardis.apps.sequencing_facility.views.'
                  'SequencingFacilityIndexView'}

DATASET_VIEWS = [
    ('http://www.tardis.edu.au/schemas/ngs/project/raw_reads',
     'tardis.apps.sequencing_facility.views.FastqDatasetView'),
    ('http://www.tardis.edu.au/schemas/ngs/project/fastqc',
     'tardis.apps.sequencing_facility.views.FastqcDatasetView')
]

# footer text
SPONSORED_TEXT = None

# For S3-compatible Object Stores, setup access_key, secret_key
# bucket_name, calling_format, host and port as StorageBoxOptions
