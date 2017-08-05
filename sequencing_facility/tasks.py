from __future__ import print_function, absolute_import
import logging
from celery.task import task

from django.conf import settings
from django.db import transaction
from django.contrib.auth.models import User, Group, ContentType

from tardis.tardis_portal.models import Experiment, ExperimentParameter, \
    DatafileParameter, DatasetParameter, ObjectACL, DataFile, \
    DatafileParameterSet, ParameterName, GroupAdmin, Schema, \
    Dataset, ExperimentParameterSet, DatasetParameterSet, \
    License, UserProfile, UserAuthentication, Token

try:
    from tardis.tardis_portal.logging_middleware import LoggingMiddleware
    LoggingMiddleware()
except Exception:
    pass

logger = logging.getLogger(__name__)


@task(name='sequencing_facility.delete_all_trashed')
def delete_all_trashed_task():
    trash_username = getattr(settings, 'TRASH_USERNAME', '__trashman__')
    trashman_id = User.objects.get(username=trash_username).id
    expt_ct = ContentType.objects.get(model='experiment').id
    trashed = ObjectACL.objects.filter(pluginId='django_user',
                                       isOwner=True,
                                       content_type=expt_ct,
                                       entityId=trashman_id)
    results = {'deleted': [], 'failed': [], 'exceptions': []}
    expt_id = None
    for t in trashed:
        expt_id = t.object_id
        expt = Experiment.objects.get(id=expt_id)
        datasets = Dataset.objects.filter(experiments=t.object_id)
        datafiles = expt.get_datafiles()

        try:
            with transaction.atomic():
                datafiles.delete()
                datasets.delete()
                expt.delete()
                # t.delete()  # ? is this required or will it also cascade ?

                results['deleted'].append(expt_id)
                logger.info("Deleted trashed Experiment %s" % expt_id)
                
        except Exception as e:
            results['failed'].append(expt_id)
            results['exceptions'].append(e)
            logger.error("Failed to delete trashed Experiment %s (%s)" %
                         (expt_id, e))

    return results
