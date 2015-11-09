import logging
import os
import os.path as path
import json

from django.conf import settings
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden, HttpResponseNotFound
from django.utils.text import slugify

from tardis.tardis_portal.auth import decorators as authz
from tardis.tardis_portal.models import Experiment, ExperimentParameter, \
    DatafileParameter, DatasetParameter, ObjectACL, DataFile, \
    DatafileParameterSet, ParameterName, GroupAdmin, Schema, \
    Dataset, ExperimentParameterSet, DatasetParameterSet, \
    License, UserProfile, UserAuthentication, Token

from tardis.tardis_portal.shortcuts import render_response_index, \
    return_response_error, return_response_not_found, \
    render_response_search, get_experiment_referer

from tardis.tardis_portal.views import _add_protocols_and_organizations

logger = logging.getLogger(__name__)


def _get_paramset_by_subtype(model, schema_subtype):
    for param_set in model.getParameterSets():
        if param_set.schema.subtype == schema_subtype:
            return param_set

    return None


def _get_param_value(model, param_name, schema_subtype):
    param_set = _get_paramset_by_subtype(model, schema_subtype)
    if param_set:
        return param_set.get_param(param_name)
    else:
        return None


def _format_bootstrap_table_json(fastqc_summary, fastqc_dataset_id):
    """
    Unpack the datastructure representing a summary of
    FastQC results for all samples in the project and repackage it
    as JSON suitable for presentation by bootstrap-table, including a
    separate list used for table column headers.

    :type fastqc_dataset_id: int
    :type fastqc_summary: dict
    :rtype: str, list
    """

    if not fastqc_summary or ('samples' not in fastqc_summary):
        return None, None

    qc_descriptions = []
    qc_fields = []
    fastqc_data = []
    for sample in fastqc_summary['samples']:
        sample_name = _format_sample_name(sample['sample_name'])
        sample_id_text = sample_name + " (R%s)" % (sample['read'])
        qc_checks = sample['qc_checks']
        fastqc_filename = sample.get('fastqc_report_filename', None)
        if fastqc_filename:
            _alnk = '<a target="_blank" ' \
                'href="/apps/sequencing-facility/report/%s/%s' \
                '?ignore_verification_status=1">%s</a>'
            sample_link = _alnk % (fastqc_dataset_id,
                                   fastqc_filename,
                                   sample_id_text)
        else:
            sample_link = '<a href="#">%s</a>' % sample_name
        results_for_sample = {'sample_name': sample_link}
        qc_anchor_index = 0
        for desc, result in qc_checks:
            qc_field_name = slugify(desc)
            if qc_field_name not in qc_fields:
                qc_fields.append(qc_field_name)
            if desc not in qc_descriptions:
                qc_descriptions.append(desc)
            if fastqc_filename:
                _alnk = '<a target="_blank" ' \
                        'href="/apps/sequencing-facility/report/%s/%s' \
                        '?ignore_verification_status=1#M%i">%s</a>'
                result_link = _alnk % (fastqc_dataset_id,
                                       fastqc_filename,
                                       qc_anchor_index,
                                       result)
            else:
                result_link = '<a href="#">%s</a>' % result
            results_for_sample[qc_field_name] = result_link
            results_for_sample['filename'] = fastqc_filename
            results_for_sample['fastqc_report_filename'] = fastqc_filename
            qc_anchor_index += 1
        fastqc_data.append(results_for_sample)

    fastqc_summary_headers = zip(qc_fields, qc_descriptions)
    if fastqc_data:
        fastqc_data_json = json.dumps(fastqc_data)
    else:
        fastqc_data_json = None

    return fastqc_data_json, fastqc_summary_headers


def _get_fastqc_json_parameter(dataset):
    """
    Find the Parameter containing the FastQC results (JSON) in the Dataset,
    return the deserialized Python datastructure, or None if not found.

    :type dataset: tardis.tardis_portal.models.Dataset
    :rtype: dict
    """

    subtype = 'hidden-fastqc-project-summary'
    fastqc_summary = None
    param_set = _get_paramset_by_subtype(dataset, subtype)
    if param_set:
        try:
            fastqc_summary_json = param_set.get_param(
                'hidden_fastqc_summary_json',
                True)
            fastqc_summary = json.loads(fastqc_summary_json)
        except DatasetParameter.DoesNotExist:
            pass

    return fastqc_summary


def _get_project_stats_from_fastqc(fastqc_summary):
    if not fastqc_summary or ('samples' not in fastqc_summary):
        return None

    import numpy
    read_numbers = []
    gc_percents = []
    read_lengths = []
    for sample in fastqc_summary['samples']:
        params = sample['basic_stats']
        read_numbers.append(params.get('number_of_reads', None))
        read_lengths.append(params.get('read_length', None))
        gc_percents.append(params.get('percent_gc', None))

    # if one of the values isn't set, don't return misleading
    # overall stats, just return None
    if None in read_lengths or \
       None in read_numbers or \
       None in gc_percents:
        return None

    read_length_mean = numpy.mean(read_lengths)
    read_length_stddev = numpy.std(read_lengths)
    gc_mean = numpy.mean(gc_percents)
    gc_stddev = numpy.std(gc_percents)

    return {'total_reads': sum(read_numbers),
            'read_length_mean': read_length_mean,
            'read_length_stddev': read_length_stddev,
            'gc_mean': gc_mean,
            'gc_stddev': gc_stddev}


def _get_project_stats_from_datafiles(dataset):
    import numpy
    read_numbers = []
    gc_percents = []
    read_lengths = []
    subtype = 'fastq-raw-reads'
    for datafile in dataset.datafile_set.all():
        param_set = _get_paramset_by_subtype(datafile, subtype)
        read_numbers.append(int(param_set.get_param('number_of_reads', True)))
        read_lengths.append(int(param_set.get_param('read_length', True)))
        # no GC content in we can't get this from FASTQ DataFile metadata,
        # gc_percents.append(param_set.get_param('percent_gc', True))

    read_length_mean = numpy.mean(read_lengths)
    read_length_stddev = numpy.std(read_lengths)

    return {'total_reads': sum(read_numbers),
            'read_length_mean': read_length_mean,
            'read_length_stddev': read_length_stddev}


def _format_sample_name(sample_name, break_entity=u'<wbr>'):
    """
    Inserts an HTML entity after every underscore in a string, to allow
    the browser to wrap long names with linebreaks at underscores in addition
    to the default breaks at spaces and dashes.

    Default entity is <wbr> (word break). Other alternatives are &#8203;
    (a zero width space) and &shy;

    :param sample_name: A sample name, potentially containing underscores.
    :type sample_name: basestring
    :param after_underscore: The HTML entity to insert after underscores.
    :type after_underscore: basestring
    :return: The modified sample name.
    :rtype: basestring
    """
    return sample_name.replace('_', '_%s' % break_entity)


def _format_read_number_summary(fastqc_summary):

    if not fastqc_summary or ('samples' not in fastqc_summary):
        return None

    sample_stats_table = {'thead': [], 'tbody': []}
    for sample in fastqc_summary['samples']:
        sample_name_html = _format_sample_name(sample['sample_name'])

        basic_stats = sample['basic_stats']
        sample_stats_table['thead'] = sorted(basic_stats.keys())
        extra_fields = ['sample_name', 'index', 'lane', 'read']
        for k in extra_fields:
            basic_stats[k] = sample[k]
        sample_stats_table['thead'] = extra_fields + sample_stats_table['thead']

        # modify the sample name for prettier HTML output (eg wrapping)
        basic_stats['sample_name'] = sample_name_html

        row = []
        for col in sample_stats_table['thead']:
            row.append(basic_stats[col])

        # modify the thead keys to be prettier titles for the table
        sample_stats_table['thead'] = [thead.replace('_', ' ').capitalize()
                                       for thead in sample_stats_table['thead']]

        sample_stats_table['tbody'].append(row)

    return sample_stats_table


@authz.dataset_access_required
def view_fastqc_report(request, dataset_id=None, filename=None):
    # NOTE: the argument dataset_id must be called dataset_id
    # for the authz decorator to work (since it's treated as a
    # named keyword arg)

    # dataset = Dataset.objects.get(id=fastqc_dataset_id)
    datafile = DataFile.objects.filter(filename__exact=filename,
                                       dataset__id=dataset_id).get()

    from tardis.tardis_portal.download import view_datafile
    return view_datafile(request, datafile.id)


@authz.dataset_access_required
def view_fastq_dataset(request, dataset_id):
    """

    This view should be used for Datasets using the FASTQ raw reads schema, by
    defining a mapping in settings.DATASET_VIEWS.

    :param request: The Django HTTP request object
    :type request: HTTPRequest
    :param dataset_id: The ID of the Dataset to be viewed (primary key)
    :type dataset_id: int
    :return: The Django HTTP response object
    :rtype: HttpResponse
    """
    c, dataset = prepare_project_dataset_view(request, dataset_id)

    # inspect parameters to retrieve the associated fastqc_dataset id,
    # if present
    fastqc_dataset_id = None
    fq_dataset_subtype = 'nucleotide-raw-reads-dataset'
    param_set = _get_paramset_by_subtype(dataset, fq_dataset_subtype)
    if param_set:
        fastqc_link = param_set.get_param('fastqc_dataset')
        if fastqc_link.link_id:
            fastqc_dataset_id = fastqc_link.link_id
        else:
            # this is a fallback, just in case link_id isn't set
            # but string_value is ...

            # TODO: We would prefer to use link_url rather than string_value
            #       but need to wait for appropriate patches in mytardis
            #       develop branch that return string_value as a fallback
            #       rather than NotImplementedError
            fastqc_link_url = fastqc_link.string_value

            import re
            dataset_view_regex = r'/dataset/(?P<dataset_id>\d+)$'
            match = re.match(dataset_view_regex, fastqc_link_url)
            fastqc_dataset_id = match.group('dataset_id')


    # TODO: rather than use the fastqc_summary JSON blob associated with the
    #       FASTQ dataset, always use the one associated with a FastQC dataset,
    #       if one exists (then we can make the ingestor only add that
    #       ParameterSet set to the FastQC dataset, not the FASTQ one,
    #       to reduce duplication)
    #       Then we remove can also fastqc_summary and fastqc_version from
    #       prepare_project_dataset_view
    fastqc_summary = c.get('fastqc_summary', None)
    if fastqc_summary and fastqc_dataset_id:
        fastqc_table_json, fastqc_table_headers = \
            _format_bootstrap_table_json(fastqc_summary, fastqc_dataset_id)
        c['fastqc_table_json'] = fastqc_table_json
        c['fastqc_table_headers'] = fastqc_table_headers

    overall_stats = None
    if fastqc_summary:
        overall_stats = _get_project_stats_from_fastqc(fastqc_summary)
    else:
        overall_stats = _get_project_stats_from_datafiles(dataset)

    sample_stats_table = _format_read_number_summary(fastqc_summary)

    c['overall_stats'] = overall_stats
    c['sample_stats_table'] = sample_stats_table

    return HttpResponse(render_response_index(
        request,
        'view_project_dataset.html',
        c)
    )


@authz.dataset_access_required
def view_fastqc_reports_dataset(request, dataset_id):
    """

    This view should be used for Datasets using the FastQC reports schema, by
    defining a mapping in settings.DATASET_VIEWS.

    :param request: The Django HTTP request object
    :type request: HTTPRequest
    :param dataset_id: The ID of the Dataset to be viewed (primary key)
    :type dataset_id: int
    :return: The Django HTTP response object
    :rtype: HttpResponse
    """
    c, dataset = prepare_project_dataset_view(request, dataset_id)

    fastqc_summary = c.get('fastqc_summary', None)
    if fastqc_summary:
        fastqc_table_json, fastqc_table_headers = \
            _format_bootstrap_table_json(fastqc_summary, dataset_id)
        c['fastqc_table_json'] = fastqc_table_json
        c['fastqc_table_headers'] = fastqc_table_headers

    return HttpResponse(render_response_index(
        request,
        'view_project_dataset.html',
        c)
    )


def prepare_project_dataset_view(request, dataset_id):
    """
    Prepares the basic dictionary template for a 'Project' Dataset
    and associated information, and the Dataset instance.
    Caller of this method will typically add or override various
    values before returning their own HttpResponse (and template).

    Views using this method show the dataset, its metadata and a list of
    associated files with the option to show metadata of each file and ways
    to download those files.

    :param request: The Django HTTP request object
    :type request: HTTPRequest
    :param dataset_id: The ID of the Dataset to be viewed (primary key)
    :type dataset_id: int
    :return: The template dictionary and Dataset model instance
    :rtype: (dict, tardis.tardis_portal.Dataset)
    """
    dataset = Dataset.objects.get(id=dataset_id)

    def get_datafiles_page():
        # pagination was removed by someone in the interface but not here.
        # need to fix.
        pgresults = 100

        paginator = Paginator(dataset.datafile_set.all(), pgresults)

        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1

        # If page request (9999) is out of range, deliver last page of results.
        try:
            return paginator.page(page)
        except (EmptyPage, InvalidPage):
            return paginator.page(paginator.num_pages)

    upload_method = getattr(settings, "UPLOAD_METHOD", False)

    fastqc_summary = _get_fastqc_json_parameter(dataset)

    fastqc_version = ''
    if fastqc_summary:
        fastqc_version = fastqc_summary.get('fastqc_version', '')

    c = {
        'dataset': dataset,
        'datafiles': get_datafiles_page(),
        'parametersets': dataset.getParameterSets()
                                .exclude(schema__hidden=True),
        'has_download_permissions':
        authz.has_dataset_download_access(request, dataset_id),
        'has_write_permissions':
        authz.has_dataset_write(request, dataset_id),
        'from_experiment':
        get_experiment_referer(request, dataset_id),
        'other_experiments':
        authz.get_accessible_experiments_for_dataset(request, dataset_id),
        'upload_method': upload_method,
        'fastqc_version': fastqc_version,
        'fastqc_summary': fastqc_summary,
    }
    _add_protocols_and_organizations(request, dataset, c)

    return c, dataset
