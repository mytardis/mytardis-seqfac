from tardis.tardis_portal.api import ExperimentResource
from tardis.tardis_portal.models.experiment import Experiment
from tardis.tardis_portal.models.parameters import ParameterName


# this class name must end in AppResource to be detected by tardis.urls
class ExperimentAppResource(ExperimentResource):
    """
    Extends MyTardis's RESTful API for Experiments to allow queries to retrieve
    experiment records by matching parameter values.
    """

    class Meta(ExperimentResource.Meta):
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

        return super(ExperimentResource, self).obj_get_list(bundle, **kwargs)
