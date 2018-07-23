from django.template.defaulttags import register
from trackercontroller.models import TrackerController
@register.assignment_tag
def get_active_actuators(tracker_id):
    print tracker_id
    active_actuators = TrackerController.objects.get(id=tracker_id).drivecontroller_set.filter(active=True)
    print active_actuators
    return active_actuators

