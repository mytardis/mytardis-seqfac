
# footer text
SPONSORED_TEXT = None

# For S3-compatible Object Stores, setup access_key, secret_key
# bucket_name, calling_format, host and port as StorageBoxOptions

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

FACILITY_MANAGER_GROUPS = ['mhtp-facility-managers']
TRASH_USERNAME = '__trashman__'
TRASH_GROUP_NAME = '__trashcan__'

NGS_PUBLICATION_DATASET_SCHEMA = 'http://www.tardis.org.au/pub/ngs/datasets/'

PUBLICATION_FORM_MAPPINGS = [
    {'dataset_schema': r'^http://www.tardis.edu.au/schemas/ngs/project/raw_reads$',
     'publication_schema': NGS_PUBLICATION_DATASET_SCHEMA,
     'form_template':
         '/static/publication-form/ngs-extra-info-dataset-template.html'},
]
