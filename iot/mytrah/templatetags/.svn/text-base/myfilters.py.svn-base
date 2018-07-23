from trackercontroller.models import TrackerController
@register.assignment_tag
def get_actuators(tracker_id):
    active_actuators = TrackerController.objects.get(tracker_id).drivecontroller_set.filter(active=True)
    return active_actuators

