from django import template
from django.contrib.humanize.templatetags.humanize import naturalday
from tardis.tardis_portal.util import get_local_time
# from tardis.tardis_portal.util import render_mustache
from django.template import loader

register = template.Library()


@register.filter
def experiment_end_time_badge(experiment):
    c = {
        'actual_time': experiment.end_time.strftime('%a %d %b %Y %H:%M'),
        'iso_time': get_local_time(experiment.end_time).isoformat(),
        'natural_time': naturalday(experiment.end_time),
    }

    # We don't render via Mustache+Pystache - Django templating will do
    # return render_mustache('badges/end_time_badge', c)

    return loader.render_to_string('badges/end_time_badge.html', c)

