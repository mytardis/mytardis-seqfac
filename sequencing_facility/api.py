from tastypie.contrib.contenttypes.fields import GenericForeignKeyField
from tastypie.exceptions import Unauthorized

from tardis.tardis_portal import api as tardis_api

from tardis.tardis_portal.models.experiment import Experiment
from tardis.tardis_portal.models.parameters import ParameterName
from tardis.tardis_portal.models.access_control import ObjectACL
from tardis.tardis_portal.auth.decorators import has_delete_permissions
from tardis.tardis_portal.auth.decorators import has_write_permissions

default_authentication = tardis_api.MyTardisAuthentication()


class AppACLAuthorization(tardis_api.ACLAuthorization):
    """
    Authorisation class for Tastypie.
    Subclasses default MyTardis API authorization to add permission for
    additional operations (eg delete ObjectACLs)
    """

    def delete_list(self, object_list, bundle):
        if isinstance(bundle.obj, ObjectACL):
            # must be allowed to delete ObjectACLs and change the associated
            # Experiment to be able to delete the ObjectACL
            return bundle.request.user.has_perm(
                'tardis_portal.delete_objectacl') and \
                   has_write_permissions(bundle.request,
                                          bundle.obj.object_id)

        return super(tardis_api.ACLAuthorization,
                     self).delete_list(object_list, bundle)

    def delete_detail(self, object_list, bundle):
        if isinstance(bundle.obj, ObjectACL):
            # must be allowed to delete ObjectACLs and change the associated
            # Experiment to be able to delete the ObjectACL
            return bundle.request.user.has_perm(
                'tardis_portal.delete_objectacl') and \
                   has_write_permissions(bundle.request,
                                          bundle.obj.object_id)

        return super(tardis_api.ACLAuthorization,
                     self).delete_detail(object_list, bundle)


# this class name must end in AppResource to be detected by tardis.urls
class ExperimentAppResource(tardis_api.ExperimentResource):
    """
    Extends MyTardis's RESTful API for Experiments to allow queries to retrieve
    experiment records by matching parameter values.
    """

    class Meta(tardis_api.ExperimentResource.Meta):
        # This will be mapped to <app_name>_experiment by MyTardis's urls.py
        # (eg /api/v1/sequencing_facility_experiment/)
        resource_name = 'experiment'

    def obj_get_list(self, bundle, **kwargs):
        """
        Responds to queries for an experiment based on the existence
        of a parameter with a particular value.

        HTTP GET query parameters are:
        schema_namespace - a schema URI
        parameter_name - the parameter name
        parameter_value - the value of the parameter. For numeric and datetime
                          values this must always expressed as a comma separated
                          range.
        parameter_type - (optional) one of 'string', 'numeric_range' or
                         'datetime_range'. If this query parameter is absent,
                         the ParameterName is first retrieved to determine its
                         type.
        """

        if hasattr(bundle.request, 'GET') and \
                'schema_namespace' in bundle.request.GET and \
                'parameter_name' in bundle.request.GET and \
                'parameter_value' in bundle.request.GET:
            namespace = bundle.request.GET['schema_namespace']
            name = bundle.request.GET['parameter_name']
            value = bundle.request.GET['parameter_value']

            parameter_type = None
            if 'parameter_type' in bundle.request.GET:
                parameter_type = bundle.request.GET['parameter_type']
            else:
                pname = ParameterName.objects.get(schema__namespace=namespace,
                                                  name=name)
                if pname.isString() \
                        or pname.isLongString() \
                        or pname.isLink() \
                        or pname.isURL \
                        or pname.isFilename() \
                        or pname.is_json():
                    parameter_type = 'string'
                if pname.isNumeric():
                    parameter_type = 'numeric_range'
                if pname.isDateTime():
                    parameter_type = 'datetime_range'

            expt = []
            filter_prefix = 'experimentparameterset__experimentparameter__'
            if parameter_type == 'string':
                expts = Experiment.safe.all(bundle.request.user).filter(
                    **{'experimentparameterset__schema__namespace': namespace,
                       filter_prefix + 'name__name__exact': name,
                       filter_prefix + 'string_value__exact': value}
                )
            if parameter_type == 'numeric_range':
                lower, upper = [float(v) for v in value.split(',')][:2]
                expts = Experiment.safe.all(bundle.request.user).filter(
                    **{'experimentparameterset__schema__namespace': namespace,
                       filter_prefix + 'name__name__exact': name,
                       filter_prefix + 'numeric_value__range': (lower, upper)}
                )
            if parameter_type == 'datetime_range':
                import dateutil
                start, end = [dateutil.parser.parse(v)
                              for v in value.split(',')][:2]
                expts = Experiment.safe.all(bundle.request.user).filter(
                    **{'experimentparameterset__schema__namespace': namespace,
                       filter_prefix + 'name__name__exact': name,
                       filter_prefix + 'datetime_value__range': (start, end)}
                )

            return expts

        return super(tardis_api.ExperimentResource, self).obj_get_list(bundle,
                                                                       **kwargs)


# TODO: This is a temporary subclass of ObjectACLResource to allow
#       queries via object_id and content_type. Once the bug/feature is
#       added to MyTardis develop, this class can be removed (and clients
#       updated to use /api/v1/objectacl/ instead of
#       /api/v1/sequencing_facility_objectacl/
class ObjectACLAppResource(tardis_api.ObjectACLResource):
    content_object = GenericForeignKeyField({
        Experiment: tardis_api.ExperimentResource,
        # ...
    }, 'content_object')

    class Meta(tardis_api.ObjectACLResource.Meta):
        # This will be mapped to <app_name>_experiment by MyTardis's urls.py
        # (eg /api/v1/sequencing_facility_objectacl/)
        resource_name = 'objectacl'
        authorization = AppACLAuthorization()

        filtering = {
            'pluginId': ('exact', ),
            'entityId': ('exact', ),
            'object_id': ('exact', ),
            'content_type': ('exact', ),
            'aclOwnershipType': ('exact', ),
        }
