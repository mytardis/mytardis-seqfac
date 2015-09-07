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
