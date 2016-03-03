import logging
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.core.exceptions import PermissionDenied

from django.http import HttpRequest, HttpResponseRedirect, HttpResponse, \
    HttpResponseForbidden, HttpResponseNotFound, JsonResponse, \
    HttpResponseNotAllowed

from tardis.tardis_portal.auth import decorators as authz
from tardis.tardis_portal.models import Experiment, ExperimentParameter, \
    DatafileParameter, DatasetParameter, ObjectACL, DataFile, \
    DatafileParameterSet, ParameterName, GroupAdmin, Schema, \
    Dataset, ExperimentParameterSet, DatasetParameterSet, \
    License, UserProfile, UserAuthentication, Token

from tardis.tardis_portal.api import MyTardisAuthentication

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


# @authz.experiment_access_required  # won't do tastypie API key auth ?
@require_authentication
def trash_experiment(request, experiment_id=None):

    # TODO: This should actually be a DELETE, or maybe a PUT (since technically
    #       it's only a logical delete, not a real database delete ?)
    #       However, it appears the CSRF middleware is blocking POST, DELETE
    #       and PUT requests without a csrf_token ? (which we don't have in this
    #       context)
    if request.method != 'GET':
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

    # TODO: Should we just create trashman/trashcan here if they are missing ?
    try:
        trashman = User.objects.filter(username=trash_username)[0]
    except IndexError as ex:
        logger.error('Cannot find ID for trash user: %s (Does it exist ? Are '
                     'ingestor user permissions correct ?)' % trashman)
        raise ex
    try:
        trashcan = Group.objects.filter(name=trash_group_name)[0]
    except IndexError as ex:
        logger.error('Cannot find ID for trash group: %s (Does it exist ? Are '
                     'ingestor user permissions correct ?)' % trashcan)
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
