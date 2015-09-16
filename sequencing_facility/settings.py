NAME = 'Sequencing Facility'

DATASET_VIEWS = [
    ('http://www.tardis.edu.au/schemas/ngs/project/raw_reads',
     'tardis.apps.sequencing_facility.views.view_fastq_dataset'),
    ('http://www.tardis.edu.au/schemas/ngs/project/fastqc',
     'tardis.apps.sequencing_facility.views.view_fastqc_reports_dataset')
]

SITE_TITLE = "Sequencing Facility"

# footer text
SPONSORED_TEXT = None

# For S3-compatible Object Stores, setup access_key, secret_key
# bucket_name, calling_format, host and port as StorageBoxOptions
