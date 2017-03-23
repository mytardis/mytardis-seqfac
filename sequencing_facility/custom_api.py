import logging
from django.conf import settings
from django.db import transaction
from django.contrib.auth.models import User, Group, ContentType
from django.core.exceptions import PermissionDenied

from django.http import HttpRequest, HttpResponseRedirect, HttpResponse, \
    HttpResponseForbidden, HttpResponseNotFound, JsonResponse, \
    HttpResponseNotAllowed, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import user_passes_test

from tardis.tardis_portal.auth import decorators as authz
from tardis.tardis_portal.models import Experiment, ExperimentParameter, \
    DatafileParameter, DatasetParameter, ObjectACL, DataFile, \
    DatafileParameterSet, ParameterName, GroupAdmin, Schema, \
    Dataset, ExperimentParameterSet, DatasetParameterSet, \
    License, UserProfile, UserAuthentication, Token

from tardis.tardis_portal.api import MyTardisAuthentication

import tasks

logger = logging.getLogger(__name__)

# we use the same custom tastypie Authentication class used by the core REST API
authentication = MyTardisAuthentication()


def require_authentication(f):
    def wrap(*args, **kwargs):
        request = args[0]
        if not isinstance(request, HttpRequest):
            request = args[1]
        if not authentication.is_authenticated(request):
            return jsend_fail_response('Unauthorized', 401, None)
        return f(*args, **kwargs)

    wrap.__doc__ = f.__doc__
    wrap.__name__ = f.__name__
    return wrap


def _jsend_response(status, message, status_code, data):
    """
    Send a simple JSend-style JSON response with an HTTP status code.

    https://labs.omniti.com/labs/jsend

    """
    return JsonResponse({'status': status,
                         'message': message,
                         'data': data,
                         status: status_code})


def jsend_success_response(message, status_code=200, data=None):
    return _jsend_response('success', message, status_code, data)


def jsend_error_response(message, status_code, data=None):
    return _jsend_response('error', message, status_code, data)


def jsend_fail_response(message, status_code, data=None):
    return _jsend_response('fail', message, status_code, data)


def get_version_json(request):
    from . import __version__
    return JsonResponse({'version': __version__})


@require_authentication
@user_passes_test(lambda u: u.is_superuser)
def stats_ingestion_timeline(request):
    """
    Returns JSON or CSV summarizing title, number and size of files in all runs.
    Could be used to render a Javascript timeline of ingestion.

    (eg, like this: https://plot.ly/javascript/range-slider/ )

    Example URL for request:
    /apps/sequencing-facility/api/_stats?format=json&include_titles

    format may by `json` or `csv`.

    :param include_titles:
    :type include_titles:
    :param as_csv:
    :type as_csv:
    :return:
    :rtype:
    """
    import json
    from datetime import datetime
    import csv
    from StringIO import StringIO
    from .views import _get_paramset_by_subtype

    # custom datetime formatter, vanilla json.dumps can't serialize datetimes
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, datetime):
                return o.isoformat()

            return json.JSONEncoder.default(self, o)

    trash_username = '__trashman__'
    format = request.GET.get('format', 'json').lower().strip()
    include_titles = ('include_titles' in request.GET)

    runs = []
    projects = []
    datafile_size_cum = 0
    datafile_count_cum = 0
    for e in Experiment.objects.all().order_by('end_time'):
        trashed = False
        for user in e.get_owners():
            if user.username == trash_username:
                trashed = True
                break

        if not trashed:
            datafiles_size = e.get_size()
            datafiles_count = e.get_datafiles().count()
            datafile_size_cum += datafiles_size
            datafile_count_cum += datafiles_count

            title = ''
            if include_titles:
                title = e.title

            row = (e.end_time, title,
                   datafiles_count, datafiles_size,
                   datafile_count_cum, datafile_size_cum)

            if _get_paramset_by_subtype(e, 'illumina-sequencing-run'):
                runs.append(row)
            if _get_paramset_by_subtype(e, 'demultiplexed-samples'):
                projects.append(row)

    if format == 'csv':
        header = 'Date,Title,Files,Size,Files(Cumulative),Size(Cumulative)'
        run_csv = StringIO()
        run_csvwriter = csv.writer(run_csv, delimiter=',', quotechar='"',
                                   quoting=csv.QUOTE_NONNUMERIC)
        run_csvwriter.writerow(header.split(','))
        for r in runs:
            run_csvwriter.writerow(r)

        project_csv = StringIO()
        project_csvwriter = csv.writer(run_csv, delimiter=',', quotechar='"',
                                       quoting=csv.QUOTE_NONNUMERIC)
        project_csvwriter.writerow(header.split(','))
        for p in projects:
            project_csvwriter.writerow(p)

        return JsonResponse({'run_csv': run_csv.getvalue(),
                             'project_csv': project_csv.getvalue()})
    else:
        jdict = {'runs': runs, 'projects': projects}
        return JsonResponse(json.loads(json.dumps(jdict, cls=DateTimeEncoder)))


# @authz.experiment_access_required  # won't do tastypie API key auth ?
@csrf_exempt  # so we can use the PUT method without a csrf_token
@require_authentication
def trash_experiment(request, experiment_id=None):

    if request.method != 'PUT':
        raise HttpResponseNotAllowed()

    try:
        expt = Experiment.safe.get(request.user, experiment_id)
    except PermissionDenied as ex:
        return jsend_fail_response('Permission denied', 401,
                                   {'id': experiment_id})

    if expt:
        ct = expt.get_ct()
        user_acls = ObjectACL.objects.filter(content_type=ct,
                                             object_id=expt.id,
                                             pluginId='django_user')
        group_acls = ObjectACL.objects.filter(content_type=ct,
                                              object_id=expt.id,
                                              pluginId='django_group')
    else:
        return jsend_fail_response('Experiment %s not found' % experiment_id,
                                   404, {'id': experiment_id})

    trash_username = getattr(settings, 'TRASH_USERNAME', '__trashman__')
    trash_group_name = getattr(settings, 'TRASH_GROUP_NAME', '__trashcan__')

    try:
        trashman = User.objects.filter(username=trash_username)[0]
    except IndexError as ex:
        logger.error('Cannot find ID for trash user: %s (Does it exist ? Are '
                     'ingestor user permissions correct ?)' % trash_username)
        raise ex
    try:
        trashcan = Group.objects.filter(name=trash_group_name)[0]
    except IndexError as ex:
        logger.error('Cannot find ID for trash group: %s (Does it exist ? Are '
                     'ingestor user permissions correct ?)' % trash_group_name)
        raise ex

    acls_to_remove = []
    has_trashman = False
    for acl in user_acls:
        if acl.entityId == trashman.id:
            has_trashman = True
            continue
        acls_to_remove.append(acl)
    has_trashcan = False
    for acl in group_acls:
        if acl.entityId == trashcan.id:
            has_trashcan = True
            continue
        acls_to_remove.append(acl)

    # Add ObjectACLs to experiment for trashman/trashcan
    if not has_trashman:
        acl = ObjectACL(content_type=ct,
                        object_id=expt.id,
                        pluginId='django_user',
                        entityId=trashman.id,
                        aclOwnershipType=ObjectACL.OWNER_OWNED,
                        isOwner=True,
                        canRead=True,
                        canWrite=True,
                        canDelete=False)
        acl.save()
    if not has_trashcan:
        acl = ObjectACL(content_type=ct,
                        object_id=expt.id,
                        pluginId='django_group',
                        entityId=trashcan.id,
                        aclOwnershipType=ObjectACL.OWNER_OWNED,
                        isOwner=True,
                        canRead=True,
                        canWrite=True,
                        canDelete=False)
        acl.save()

    # remove all the non-trashman/trashcan ACLs
    [acl.delete() for acl in acls_to_remove]

    # ensure experiment is not publicly accessible
    expt.public_access = Experiment.PUBLIC_ACCESS_NONE
    expt.save()

    return jsend_success_response(
        'Experiment %s moved to trash' % experiment_id, {'id': experiment_id})


@require_authentication
@user_passes_test(lambda u: u.is_superuser)
def _delete_all_trashed(request):
    try:
        # tasks.delete_all_trashed_task.delay()
        tasks.delete_all_trashed_task()

    except Exception as e:
        return jsend_fail_response('Delete operation failed. '
                                   'Some trashed experiments were not deleted.',
                                   500, {})

    return jsend_success_response('Queued trashed Experiments for deletion',
                                  200, {})
