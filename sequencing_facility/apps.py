from tardis.app_config import AbstractTardisAppConfig


class SequencingFacilityConfig(AbstractTardisAppConfig):
    name = 'tardis.apps.sequencing_facility'
    verbose_name = 'Sequencing Facility'
    app_dependencies = ['storages']
