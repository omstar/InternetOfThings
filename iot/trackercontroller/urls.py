"""
urls for trackercontroller app
"""
from django.conf.urls import url

urlpatterns = [
    url(r'^dashboard/$', 'trackercontroller.views.dashboard', name="Charts and overview"),
    url(r'^gateways/?region_id=', 'trackercontroller.views.display_gateways',
        name="Gateways of specific region"),
    url(r'^gateways/$', 'trackercontroller.views.display_gateways', name="all gateways"),

    url(r'^masters/(?P<gateway_id>[\w=-]+)/$', 'trackercontroller.views.display_master_controllers',
        name="Master Controllers"),

    url(r'^maintenance/$', 'trackercontroller.views.maintenance', name="For Maintenance"),
    url(r'^stow/$', 'trackercontroller.views.stow', name="For trackers to stow position"),
    url(r'^reset/$', 'trackercontroller.views.reset', name="For trackers to reset position"),
    url(r'^firmwareupdate/$', 'trackercontroller.views.firmware_update',
        name="Update firmware remotely"),
    url(r'^firmware/update/version/$', 'trackercontroller.views.firmware_update_version',
        name="Send version and checksum"),
    url(r'^firmware/update/$', 'trackercontroller.views.firmware_update_files',
        name="Send Firmware update tar files"),

    url(r'^reports/$', 'trackercontroller.views.reports', name="extract reports"),

    url(r'^bulk_updates/$', 'trackercontroller.views.bulk_updates',
        name="Group commands for clean, stow and upgrade"),
    url(r'^bulk_updates_proc/$', 'trackercontroller.views.bulk_updates_proc',
        name="Group commands for clean, stow and upgrade"),

    url(r'^inactive_devices/$', 'trackercontroller.views.display_inactive_devices',
        name="Inactive devices"),

    url(r'^live_data/$', 'trackercontroller.views.live_data_streaming',
        name="Graphs live data"),
    url(r'^live_data/streaming/$', 'trackercontroller.views.live_data_streaming_ajax',
        name='ajax streaming'),
]
