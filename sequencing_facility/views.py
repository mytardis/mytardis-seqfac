import logging
import os
import os.path as path
import json
from django.conf import settings
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.http import HttpResponseRedirect, HttpResponse, \
    HttpResponseForbidden, HttpResponseNotFound, JsonResponse, \
    HttpResponseNotAllowed
from django.utils.text import slugify

from tardis.tardis_portal.views.pages import IndexView, DatasetView, \
    use_rapid_connect
from tardis.tardis_portal.auth import decorators as authz
from tardis.tardis_portal.models import Experiment, ExperimentParameter, \
    DatafileParameter, DatasetParameter, ObjectACL, DataFile, \
    DatafileParameterSet, ParameterName, GroupAdmin, Schema, \
    Dataset, ExperimentParameterSet, DatasetParameterSet, \
    License, UserProfile, UserAuthentication, Token
from tardis.tardis_portal.shortcuts import render_response_index, \
    return_response_error, return_response_not_found, \
    render_response_search, get_experiment_referer
from tardis.tardis_portal.views.utils import _add_protocols_and_organizations
# from tardis.tardis_portal.views.pages import index_context
from tardis.tardis_portal.download import view_datafile

logger = logging.getLogger(__name__)


def _get_paramset_by_subtype(model, schema_subtype, default=None):
    for param_set in model.getParameterSets():
        if param_set.schema.subtype == schema_subtype:
            return param_set

    return default


def _get_param_value(model, param_name, schema_subtype, default=None):
    param_set = _get_paramset_by_subtype(model, schema_subtype)
    if param_set:
        try:
            return param_set.get_param(param_name, value=True)
        except (ExperimentParameter.DoesNotExist,
                DatasetParameter.DoesNotExist,
                DatafileParameter.DoesNotExist):
            return default
    else:
        return default


def _format_read_number(read, read_type=None):
    """
    Catch read values without a letter prefix (legacy format), convert
    them to Rn format. This could be fixed by a database migration that
    updates the JSON blobs.

    :param read: The read number. May be eg 'R1', 'R2', 'I1', or
                 the old format used previously, '1', '2', '3'
                 (as string or int).
    :type read: str | int
    :return: The read number properly formatted for output - Rn or In.
    :rtype: str
    """
    try:
        read = int(read)
        if read_type is None:
            read_type = 'R'
        read = '%s%s' % (read_type, read)
    except ValueError:
        # read is in the format 'Rn' or 'In', so just return it unmodified
        pass
    return read


def _format_bootstrap_table_json(fastqc_summary, fastqc_dataset_id,
                                 skip_index_reads=True):
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
        sample_name = sample['sample_name']

        # just skip index reads in the table
        if skip_index_reads and \
                (sample.get('read_type', None) == 'I' or
                 str(sample.get('read', '')).startswith('I')):
            continue

        read = _format_read_number(sample['read'],
                                   read_type=sample.get('read_type', None))

        sample_id_text = '%s<br/>(L%s, %s)' % (sample_name,
                                               sample['lane'],
                                               read)
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


def _format_read_count_summary(fastqc_summary):
    if not fastqc_summary or ('samples' not in fastqc_summary):
        return None

    sample_stats_table = {'thead': [], 'tbody': []}
    for sample in fastqc_summary['samples']:
        sample_name = sample['sample_name']

        basic_stats = sample['basic_stats']
        sample_stats_table['thead'] = sorted(basic_stats.keys())
        extra_fields = ['sample_name', 'index', 'lane', 'read']
        for k in extra_fields:
            basic_stats[k] = sample[k]
        basic_stats['read'] = _format_read_number(
            basic_stats['read'],
            read_type=sample.get('read_type', None))

        sample_stats_table['thead'] = extra_fields + sample_stats_table['thead']

        # modify the sample name for prettier HTML output (eg wrapping)
        basic_stats['sample_name'] = sample_name

        row = []
        for col in sample_stats_table['thead']:
            row.append(basic_stats[col])

        # modify the thead keys to be prettier titles for the table
        sample_stats_table['thead'] = [thead.replace('_', ' ').capitalize()
                                       for thead in sample_stats_table['thead']]

        sample_stats_table['tbody'].append(row)

    return sample_stats_table


class FastqDatasetView(DatasetView):
    template_name = 'view_project_dataset.html'

    def get_context_data(self, request, dataset, **kwargs):
        c = super(FastqDatasetView, self).get_context_data(request,
                                                           dataset,
                                                           **kwargs)

        c = self._prepare_fastq_summary_tables_context(request, c)

        return c

    def _prepare_fastq_summary_tables_context(self, request, c):
        """
        For FASTQ and FastQC datasets, adds the FastQC summary table,
        sample stats table and overall stats summary to the context.

        :param request: The Django HTTP request object
        :type request: HTTPRequest
        :param c: The context dictionary
        :type c: dict
        :return: The context dictionary
        :rtype: dict
        """

        dataset = c.get('dataset', None)
        if dataset is None:
            raise AttributeError("Context must contain a 'dataset' key.")

        fastqc_dataset_id = None

        # For a FASTQ dataset, inspect parameters to retrieve the associated
        # fastqc_dataset_id if present
        fq_param_set = _get_paramset_by_subtype(dataset,
                                                'nucleotide-raw-reads-dataset')

        if fq_param_set:
            try:
                fastqc_link = fq_param_set.get_param('fastqc_dataset')
            except DatasetParameter.DoesNotExist:
                return c

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

        # For a FastQC reports dataset, the fastqc_dataset_id is the dataset.id
        fqc_param_set = _get_paramset_by_subtype(dataset, 'fastqc-reports')
        if fqc_param_set and dataset is not None:
            fastqc_dataset_id = dataset.id

        fastqc_summary = _get_fastqc_json_parameter(dataset)
        fastqc_version = ''
        if fastqc_summary:
            fastqc_version = fastqc_summary.get('fastqc_version', '')

        c['fastqc_version'] = fastqc_version
        c['fastqc_summary'] = fastqc_summary

        # TODO: rather than use the fastqc_summary JSON blob associated with the
        #       FASTQ dataset, always use the one associated with a FastQC
        #       dataset, if one exists (then we can make the ingestor only add
        #       that ParameterSet set to the FastQC dataset, not the FASTQ one,
        #       to reduce duplication)
        #       Then we remove can also fastqc_summary and fastqc_version from
        #       prepare_project_dataset_view
        if fastqc_summary and fastqc_dataset_id:
            fastqc_table_json, fastqc_table_headers = \
                _format_bootstrap_table_json(fastqc_summary, fastqc_dataset_id)
            c['fastqc_table_json'] = fastqc_table_json
            c['fastqc_table_headers'] = fastqc_table_headers

        if fastqc_summary:
            overall_stats = _get_project_stats_from_fastqc(fastqc_summary)
        else:
            overall_stats = _get_project_stats_from_datafiles(dataset)

        sample_stats_table = _format_read_count_summary(fastqc_summary)

        c['overall_stats'] = overall_stats
        c['sample_stats_table'] = sample_stats_table

        return c

    @authz.dataset_access_required  # too complex # noqa
    def get(self, request, *args, **kwargs):
        """


        :param request: a HTTP request object
        :type request: :class:`django.http.HttpRequest`
        :return: The Django response object
        :rtype: :class:`django.http.HttpResponse`
        """

        dataset_id = kwargs.get('dataset_id', None)
        if dataset_id is None:
            return return_response_error(request)

        dataset = Dataset.objects.get(id=dataset_id)
        if not dataset:
            return return_response_not_found(request)

        c = self.get_context_data(request, dataset, **kwargs)

        template_name = kwargs.get('template_name', None)
        if template_name is None:
            template_name = self.template_name

        return HttpResponse(render_response_index(
                request,
                template_name,
                c)
        )


class FastqcDatasetView(FastqDatasetView):
    pass


def _get_experiments_by_schema(schema_subtype, user, order_by='-end_time'):
    private_experiments = Experiment.safe.owned_and_shared(
            user).order_by(order_by)

    with_subtype = private_experiments.filter(
            experimentparameterset__schema__subtype=
            schema_subtype,
            experimentparameterset__schema__type=
            Schema.EXPERIMENT,
    )

    return with_subtype


def _get_projects_for_run(run, user):

    projects_in_run = _get_experiments_by_schema(
            'demultiplexed-samples', user).filter(
            experimentparameterset__experimentparameter__name__name__exact=
            'run_experiment',
            experimentparameterset__experimentparameter__link_id=run.id,
    )

    # An alternative to matching based on the linked
    # run_experiment is to match based on run_id, but
    # it assumes that run_id is always unique and this
    # isn't strictly the case for users that can see
    # 'trashed' experiments (eg admins)

    # paramset = run.experimentparameterset_set.filter(
    #        schema__subtype='illumina-sequencing-run',
    #        schema__type=Schema.EXPERIMENT).get()
    # run_id = paramset.get_param('run_id').get()

    # projects_in_run = Experiment.safe.owned_and_shared(
    #         request.user).filter(
    #         experimentparameterset__schema__subtype=
    #         'demultiplexed-samples',
    #         experimentparameterset__schema__type=
    #         Schema.EXPERIMENT,
    #         experimentparameterset__experimentparameter__name__name__exact=
    #         'run_id',
    #         experimentparameterset__experimentparameter__string_value__exact=
    #         run_id,
    # )

    return projects_in_run


def _is_in_group(user, group_names):
    """
    Returns True if a given user is a member of one or more groups.

    :param user: The User object
    :type user: django.User
    :param group_names: A list of group names
    :type group_names: list[str]
    :return: Returns True if the user is in at least one of the named groups
    :rtype: bool
    """
    return user.groups.filter(name__in=group_names).exists()


class SequencingFacilityIndexView(IndexView):
    template_name = 'index.html'

    @use_rapid_connect
    def get_context_data(self, request, **kwargs):
        """
        Prepares the values to be passed to the default index view - a list of
        experiments, respecting authorization rules.

        :param request: a HTTP request object
        :type request: :class:`django.http.HttpRequest`
        :return: A dictionary of values for the view/template.
        :rtype: dict
        """

        limit = 8
        # c = super(IndexView, self).get_context_data(**kwargs)
        c = {}
        c['private_experiments'] = None

        facility_manager_groups = getattr(settings,
                                          'FACILITY_MANAGER_GROUPS',
                                          ['mhtp-facility-managers'])
        run_expts = []
        if request.user.is_authenticated():
            if _is_in_group(request.user, facility_manager_groups):
                runs = _get_experiments_by_schema('illumina-sequencing-run',
                                                  request.user)

                for run in runs[:limit]:
                    if run:
                        run.projects = _get_projects_for_run(run, request.user)
                        run_expts.append(run)

            else:
                runs = _get_experiments_by_schema('demultiplexed-samples',
                                                  request.user)
                run_expts = runs

            c['private_experiments'] = run_expts

        c['public_experiments'] = None

        return c

    def get(self, request, *args, **kwargs):
        c = self.get_context_data(request, **kwargs)

        return HttpResponse(render_response_index(request,
                                                  self.template_name, c))


@authz.dataset_access_required
def view_fastqc_html_report(request, dataset_id=None, filename=None):
    # NOTE: the argument dataset_id must be called dataset_id
    # for the authz decorator to work (since it's treated as a
    # named keyword arg)

    # dataset = Dataset.objects.get(id=fastqc_dataset_id)
    datafile = DataFile.objects.filter(filename__exact=filename,
                                       dataset__id=dataset_id).get()

    return view_datafile(request, datafile.id)
