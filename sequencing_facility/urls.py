from django.conf import settings
from django.conf.urls import patterns, url

# urlpatterns = patterns('')

urlpatterns = patterns('',
    # url(r'^results/(?P<path>.*)$', 'django.views.static.serve', {
    #     'document_root': settings.WEBCACHE_FILE_PATH,
    # }),

    # url(r'^results/(?P<dataset_id>\d+)/(?P<filename>.*)$',
    #     'sequencing_facility.views.view_html_result_file'),

    url(r'^report/(?P<dataset_id>\d+)/(?P<filename>.*)$',
        'sequencing_facility.views.view_fastqc_html_report'),


    # custom (non-tastypie) API endpoints
    url(r'^api/version$',
        'sequencing_facility.custom_api.get_version_json'),

    url(r'^api/trash_experiment/(?P<experiment_id>\d+)$',
        'sequencing_facility.custom_api.trash_experiment'),

    url(r'^api/_delete_all_trashed/$',
        'sequencing_facility.custom_api._delete_all_trashed'),

    url(r'^api/_stats/$',
        'sequencing_facility.custom_api.stats_ingestion_timeline'),
)
