"""
trackercontroller views
"""
import json
import re
import datetime
import csv
import commands
import simplejson

from django.shortcuts import render_to_response
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger #pagination
from django.db.models import Count, Q

from trackercontroller.models import User, Region, Gateway, MasterController, \
                                     TrackerController, DriveController, \
                                     ControlCommands, ActionProperties
from trackercontroller.decorators import is_standard_user
from trackercontroller.constants import STYLES, FIRMWARE_DIR, MASTER_VERSION, \
                                        GATEWAY_VERSION, TRACKER_VERSION

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib import colors
from reportlab.platypus.tables import Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet


#pylint: disable=too-many-arguments
#pylint: disable=too-many-lines
#pylint: disable=eval-used
#pylint: disable=too-many-locals
#pylint: disable=too-many-return-statements
#pylint: disable=too-many-branches
#pylint: disable=too-many-statements
#pylint: disable=no-member
#pylint: disable=anomalous-backslash-in-string
#pylint: disable=unused-variable

def wrap_text(text):
    """
    to wrap text if string is too long for pdf generation
    """
    text = Paragraph('<b>%s</b>'%text, getSampleStyleSheet()['Normal'])
    return text
##Utils

def get_user(user):
    """
    returns trackercontroller.user object by passing request.user
    """
    user = User.objects.get(email=user.email)
    return user

def get_region_wise_gateways(user, selected_regions=None):
    """
    Return devices of selective regions for which user \
    is permitted to access
    """
    if user.role:
        if selected_regions:
            gateways = Gateway.objects.filter(region__id__in=selected_regions)
        elif user.role.level == 2:
            gateways = Gateway.objects.all().order_by('id')
        elif user.role.level in [3, 4]: 
            gateways = Gateway.objects.filter(region__in=user.regions.all())
    return gateways

def get_user_regions(user):
    """
    Return user permitted regions by passing user
    """
    regions = []
    if int(user.role.level) in [3, 4]:
        #regions = Region.objects.filter(id=user.region.id)
        regions = user.regions.all()
    else:
        regions = Region.objects.all().order_by('name')
    return regions
#Util functions ends here


def base_dict(request):
    """
    Return base dict which hasic basic info which \
    is essential for all templates
    """
    user = User.objects.get(email=request.user.email)
    regions = get_user_regions(user)
    default_base_dict = {"user": user, "regions": regions}
    return default_base_dict


@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def dashboard(request):
    """
    Get overview of devices and their status for user \
    permiited devices and display on dashboard
    """
    user = get_user(request.user)
    result_dict = base_dict(request)

    region_objects = get_user_regions(user)
    regions = region_objects.annotate(gateway_count=Count('gateway')).values(
        'name', 'gateway_count')

    gateway_objects = Gateway.objects.filter(region__id__in=regions.values_list('id', flat='true'))
    gateways = gateway_objects.annotate(masters_count=Count('mastercontroller')).values(
        'device_id', 'masters_count', 'region__name')

    #master_objects = MasterController.objects.filter(gateway__id__in=gateway_objects.values_list(
    #    'id', flat='true'))
    #masters = master_objects.annotate(trackers_count=Count('trackercontroller')).values(
    #    'device_id', 'trackers_count', 'gateway__device_id')

    drilldown_list = []
    summary = []
    inactive_devices = {
        "total_inactive_gw": 0,
        "total_inactive_mc": 0,
        "total_inactive_tc": 0}

    for region in region_objects:
        summary_data = {
            "active_gw": 0,
            "inactive_gw": 0,
            "active_mc": 0,
            "inactive_mc": 0,
            "active_tc": 0,
            "inactive_tc":0}#region_wise
        summary_data["region"] = region.name

        gateways_dict = {"name": "Master Controllers"} #regionwise
        gateways_dict["id"] = region.name
        gateways = Gateway.objects.filter(region=region)

        gateways_dict['active_gw'] = gateways.filter(active=True).count()
        gateways_dict['inactive_gw'] = gateways.filter(active=False).count()

        summary_data["active_gw"] = gateways_dict['active_gw']
        summary_data["inactive_gw"] = gateways_dict['inactive_gw']

        inactive_devices["total_inactive_gw"] += gateways_dict['inactive_gw']

        gateways_dict["data"] = []
        for gateway in gateways:
            master_controllers = gateway.mastercontroller_set

            summary_data["active_mc"] += master_controllers.filter(active=True).count()
            summary_data["inactive_mc"] += master_controllers.filter(active=False).count()

            gateways_dict["data"].append({
                "name": gateway.device_id,
                "y": master_controllers.count(),
                "drilldown": region.region_id + gateway.device_id})

            if not master_controllers.count():
                continue
            masters_dict = {"name": "Tracker Controllers",
                            "id": region.region_id + gateway.device_id}
            masters_dict["data"] = []
            for master_controller in master_controllers.all():
                tracker_controllers = master_controller.trackercontroller_set
                masters_dict["data"].append([master_controller.device_id,
                                             tracker_controllers.count()])

                summary_data["active_tc"] += tracker_controllers.filter(active=True).count()
                summary_data["inactive_tc"] += tracker_controllers.filter(active=False).count()
            drilldown_list.append(masters_dict)

        drilldown_list.append(gateways_dict)

        summary.append(summary_data)
        inactive_devices["total_inactive_tc"] += summary_data['inactive_tc']
        inactive_devices["total_inactive_mc"] += summary_data['inactive_mc']

    result_dict.update({"drilldown_list": json.dumps(drilldown_list)})
    result_dict.update({"regions_list": json.dumps(list(regions))})
    result_dict.update({"summary": summary})
    result_dict.update({"inactive_devices": inactive_devices})

    response = render_to_response('dashboard.html', result_dict)
    return response


@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def display_gateways(request, region_id=None):
    """
    Get gateway devices and their details along with region \
    to display region-wise gateways
    """

    data = request.GET
    if data:
        region_id = data.get('region_id')
    if not data:
        data = request.POST.copy()
    user = get_user(request.user)

    if region_id:
        if region_id == "ALL":
            selected_regions = get_user_regions(user).values_list('id', flat='true')
        else:
            selected_regions = [int(region_id)]
    else:
        selected_regions = [int(region) for region in data.getlist('regions')]
    gateways = get_region_wise_gateways(user, selected_regions)
    gateways = gateways.annotate(masters_count=Count('mastercontroller', distinct=True)).annotate(
        trackers_count=Count('mastercontroller__trackercontroller')).order_by('region').values(
            'device_id', 'masters_count', 'trackers_count', 'active', 'id', 'region__name', 'version', 'fw_status')

    result_dict = base_dict(request)
    result_dict.update({"devices": list(gateways), "selected_regions": selected_regions, "latest_version": GATEWAY_VERSION})
    response = render_to_response('gateways.html', result_dict)
    return response

@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def display_master_controllers(request, gateway_id):
    """
    Get master controller and tracker controller devices \
    and their details for selected gateway
    """
    master_controllers = MasterController.objects.filter(gateway__id=gateway_id).order_by('id')

    result_dict = base_dict(request)
    result_dict.update({"masters": master_controllers,
                        "master_latest_version": MASTER_VERSION,
                        "tracker_latest_version": TRACKER_VERSION})
    response = render_to_response('master_controllers.html', result_dict)
    return response

@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def maintenance(request):
    """
    Maintenance commands initiated by user from scada \
    shall be stored in database in queue to trigger
    """
    try:
        tracker = TrackerController.objects.get(id=request.POST.get('value'))
        try:
            if ControlCommands.objects.get(action="CLEANING", tracker_controller=tracker):
                return HttpResponse(json.dumps({"msg": "Please wait! Previous command still in Queue!"}), content_type='application/json')
        except ControlCommands.DoesNotExist:
            pass

        master = tracker.master_controller
        gateway = master.gateway
        control_command = ControlCommands.objects.create(
            command='{"command":"CLEANING"}',
            publish_pattern='control/%s/%s/%s' %(gateway.device_id,
                                                 master.device_id,
                                                 tracker.device_id))
        control_command.user = get_user(request.user)
        control_command.action = "CLEANING"
        control_command.tracker_controller = tracker
        control_command.region = gateway.region
        control_command.save()
        #Delete all the scheduled previous commands(other than cleaning)
        msg = "Command scheduled successfully!"
        previous_commands = ControlCommands.objects.filter(tracker_controller=tracker).exclude(action="CLEANING")
        if previous_commands.count():
            msg += " Previous %s commands has been deleted from the queue!" %(', '.join(previous_commands.values_list('action', flat='true')))
            previous_commands.delete()

    except TrackerController.DoesNotExist:
        msg = "No such Tracker Found!"

    return HttpResponse(json.dumps({"msg": msg}), content_type='application/json')

@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def stow(request):
    """
    stow commands initiated by user from scada \
    shall be stored in database in queue to trigger
    """
    try:
        tracker = TrackerController.objects.get(id=request.POST.get('value'))
        try:
            if ControlCommands.objects.get(action="STOW", tracker_controller=tracker):
                return HttpResponse(json.dumps({"msg": "Please wait! Previous command still in Queue!"}), content_type='application/json')
        except ControlCommands.DoesNotExist:
            pass

        master = tracker.master_controller
        gateway = master.gateway
        control_command = ControlCommands.objects.create(command='{"command":"STOW"}',
                                                         publish_pattern='control/%s/%s/%s' %(
                                                             gateway.device_id,
                                                             master.device_id,
                                                             tracker.device_id))
        control_command.user = get_user(request.user)
        control_command.action = "STOW"
        control_command.tracker_controller = tracker
        control_command.region = gateway.region
        control_command.save()

        #Delete all the scheduled previous commands(other than stow)
        msg = "Command scheduled successfully!"
        previous_commands = ControlCommands.objects.filter(tracker_controller=tracker).exclude(action="STOW")
        if previous_commands.count():
            msg += " Previous %s commands has been deleted from the queue!" %(', '.join(previous_commands.values_list('action', flat='true')))
            previous_commands.delete()

    except TrackerController.DoesNotExist:
        msg = "No such Tracker Found!"

    return HttpResponse(json.dumps({"msg": msg}), content_type='application/json')

@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def reset(request):
    """
    stow commands initiated by user from scada \
    shall be stored in database in queue to trigger
    """
    try:
        tracker = TrackerController.objects.get(id=request.POST.get('value'))
        try:
            if ControlCommands.objects.get(action="RESET", tracker_controller=tracker):
                return HttpResponse(json.dumps({"msg": "Please wait! Previous command still in Queue!"}), content_type='application/json')
        except ControlCommands.DoesNotExist:
            pass

        master = tracker.master_controller
        gateway = master.gateway
        control_command = ControlCommands.objects.create(command='{"command":"RESET"}',
                                                         publish_pattern='control/%s/%s/%s' %(
                                                             gateway.device_id,
                                                             master.device_id,
                                                             tracker.device_id))
        control_command.user = get_user(request.user)
        control_command.action = "RESET"
        control_command.tracker_controller = tracker
        control_command.region = gateway.region
        control_command.save()

        #Delete all the scheduled previous commands(other than Reset)
        msg = "Command scheduled successfully!"
        previous_commands = ControlCommands.objects.filter(tracker_controller=tracker).exclude(action="RESET")
        if previous_commands.count():
            msg += " Previous %s commands has been deleted from the queue!" %(', '.join(previous_commands.values_list('action', flat='true')))
            previous_commands.delete()

    except TrackerController.DoesNotExist:
        msg = "No such Tracker Found!"

    return HttpResponse(json.dumps({"msg": msg}), content_type='application/json')


def is_command_in_queue(action, gateway, master, tracker):
    """
    To verify whether command is already scheduled or not!
    """
    try:
        if master and tracker == None:
            exists = ControlCommands.objects.get(action=action, master_controller=master, tracker_controller=None)
        elif gateway and master == None:
            exists = ControlCommands.objects.get(action=action, gateway=gateway, master_controller=None)
        else:
            exists = ControlCommands.objects.get(action=action, tracker_controller=tracker)
    except Exception, e:
        exists = False
    return exists


@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def firmware_update(request):
    """
    Firmware update commands initiated by user from scada \
    shall be stored in database in queue to trigger
    """
            
    try:
        data = request.POST.get('value')
        device_type, device_id = data.split('_')
        if device_type == 'tracker':
            model = TrackerController
        elif device_type == 'master':
            model = MasterController
        elif device_type == 'gateway':
            model = Gateway

        device = model.objects.get(id=device_id)

        if device_type == 'tracker':
            exists = is_command_in_queue("FIRMWARE_UPDATE", None, None, device)
            if exists:
                return HttpResponse(json.dumps({"msg": "Please wait!  Previous command still in Queue!"}), content_type='application/json')

            master = device.master_controller
            gateway = master.gateway
            control_command = ControlCommands.objects.create(
                command='{"command":"FIRMWARE_UPDATE"}',
                publish_pattern='control/%s/%s/%s' %(
                    gateway.device_id,
                    master.device_id,
                    device.device_id))
            control_command.tracker_controller = device
            previous_commands = ControlCommands.objects.filter(tracker_controller=device).exclude(action="FIRMWARE_UPDATE")
        elif device_type == 'master':
            exists = is_command_in_queue("FIRMWARE_UPDATE", None, device, None)
            if exists:
                return HttpResponse(json.dumps({"msg": "Please wait! Previous command still in Queue!"}), content_type='application/json')
            gateway = device.gateway
            control_command = ControlCommands.objects.create(
                command='{"command":"FIRMWARE_UPDATE"}',
                publish_pattern='control/%s/%s' %(
                    gateway.device_id,
                    device.device_id))
            control_command.master_controller = device
            previous_commands = ControlCommands.objects.filter(tracker_controller=None, master_controller=device).exclude(action="FIRMWARE_UPDATE")
        elif device_type == 'gateway':
            exists = is_command_in_queue("FIRMWARE_UPDATE", device, None, None)
            if exists:
                return HttpResponse(json.dumps({"msg": "Please wait! Previous command still in Queue!"}), content_type='application/json')
            gateway = device
            control_command = ControlCommands.objects.create(
                command='{"command":"FIRMWARE_UPDATE"}',
                publish_pattern='control/%s' %(device.device_id))
            control_command.gateway = device
            previous_commands = ControlCommands.objects.filter(tracker_controller=None, master_controller=None, gateway=device).exclude(action="FIRMWARE_UPDATE")

        control_command.user = get_user(request.user)
        control_command.action = "FIRMWARE_UPDATE"
        control_command.region = gateway.region
        control_command.save()

        #Delete all the scheduled previous commands(other than FW Update)
        msg = "Command scheduled successfully!"
        if previous_commands.count():
            msg += " Previous %s commands has been deleted from the queue!" %(', '.join(previous_commands.values_list('action', flat='true')))
            previous_commands.delete()

    except model.DoesNotExist:
        msg = "No such Tracker Found!"

    return HttpResponse(json.dumps({"msg": msg}), content_type='application/json')

@csrf_exempt
def firmware_update_version(request):
    """
    sends version and crc when gateway requests for fimware upgrade
    """
    data = request.POST
    device_type = data.get('device_type', '')
    device_type = data.get('device_type', 'master')
    if device_type == 'gateway':
        file_name = FIRMWARE_DIR + 'gateway/gateway.zip'
        #zip_file = open(file_name, 'r')
    elif device_type == 'master':
        file_name = FIRMWARE_DIR + 'master/master.zip'
        #zip_file = open(FIRMWARE_DIR + 'master/master.zip', 'r')
    elif device_type == 'tracker':
        file_name = FIRMWARE_DIR + 'tracker/tracker.zip'
        #zip_file = open(FIRMWARE_DIR + 'tracker/tracker.zip', 'r')
    checksum = commands.getoutput('sha1sum %s' %(file_name))
    checksum = checksum.split(' ')[0]
    version_file = open(file_name.rsplit('/', 1)[0] + '/version.txt')
    version = version_file.read().strip()
    version_file.close()

    response = HttpResponse("%s\ncrc = %s"%(version, checksum),
                            content_type='application/force-download')
    response['Content-Disposition'] = 'attachment; filename="%s"' % 'version.txt'
    return response

@csrf_exempt
def firmware_update_files(request):
    """
    Send image files stored at server when gateway \
    device request after confirming with version
    """
    data = request.POST
    device_type = data.get('device_type', '')
    if device_type == 'gateway':
        zip_file = open(FIRMWARE_DIR + 'gateway/gateway.zip', 'r')
    elif device_type == 'master':
        zip_file = open(FIRMWARE_DIR + 'master/master.zip', 'r')
    elif device_type == 'tracker':
        zip_file = open(FIRMWARE_DIR + 'tracker/tracker.zip', 'r')
    else:
        return HttpResponse(json.dumps({"Error": "Please specify device_type"}),
                            content_type='application/json')

    response = HttpResponse(zip_file, content_type='application/force-download')
    response['Content-Disposition'] = 'attachment; filename="%s"' % 'update.zip'
    return response

@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
def redirect_default_page(request):
    """
    Unknown urls will be redirected to home page instead 404 error
    """

    if isinstance(request.user, AnonymousUser):
        return HttpResponseRedirect('/login/')
    return HttpResponseRedirect('/iot/dashboard/')


def process_gateway_status_report(selected_regions, download=False):
    """
    Generates gateway devices report which is \
    available as pdf and csv along with HTML display
    """
    #gateway_report = []
    gateway_objects = Gateway.objects.filter(
        region__id__in=selected_regions).order_by('region').annotate(
            masters_count=Count('mastercontroller', distinct=True)).annotate(
                trackers_count=Count('mastercontroller__trackercontroller'))
    if not download:
        return gateway_objects.values('region__name',
                                      'device_id',
                                      'masters_count',
                                      'trackers_count',
                                      'active',
                                      'inactive_at')

    if download == 'pdf':
        centimeter = 2.54

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; \
filename="GatewayReport_%s.pdf"' %str(datetime.datetime.now())

        elements = []
        elements.append(Paragraph("<u>Gateways Report</u>", STYLES['title']))

        doc = SimpleDocTemplate(response, pagesize=A4,
                                rightMargin=0, leftMargin=6.5 * centimeter,
                                topMargin=0.3 * centimeter, bottomMargin=0)

        data = list(gateway_objects.values_list('region__name',
                                                'device_id',
                                                'masters_count',
                                                'trackers_count',
                                                'active'))
        data.insert(0, ('Region', 'Device ID', 'Masters', 'Trackers', 'Active'))

        table = Table(data, colWidths=70, rowHeights=25)
        table.setStyle(TableStyle([
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('BOX', (0, 0), (-1, -1), 0.25, colors.grey),
            ('FONT', (0, 0), (4, 0), 'Helvetica-Bold'),
            ]))
        elements.append(table)
        doc.build(elements)

    elif download == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; \
filename="GatewayReport_%s.csv"' %str(datetime.datetime.now())
        gateway_values = list(gateway_objects.values('region__name',
                                                     'device_id',
                                                     'masters_count',
                                                     'trackers_count',
                                                     'active'))
        gateway_values.insert(0, {'region__name': 'Region Name',
                                  'device_id': 'Device ID',
                                  'masters_count':'Masters',
                                  'trackers_count':'Trackers',
                                  'active': 'Active'})
        keys = ['region__name', 'device_id',
                'masters_count', 'trackers_count',
                'active'
               ]
        writer = csv.DictWriter(response, keys)
        #writer.writeheader()
        writer.writerows(gateway_values)

    return response

def process_masters_status_report(selected_regions, download=False):
    """
    Generates master devices report which is available \
    as pdf and csv along with HTML display
    """
    #masters_report = []
    master_objects = MasterController.objects.filter(
        gateway__region__id__in=selected_regions).order_by('gateway__region').annotate(
            trackers_count=Count('trackercontroller')).order_by('gateway__id')
    if not download:
        return master_objects.values('gateway__region__name',
                                     'device_id', 'gateway__device_id',
                                     'trackers_count', 'wind_speed', 'active', 'inactive_at')

    if download == 'pdf':
        centimeter = 2.54

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; \
filename="MasterControllersReport_%s.pdf"' %str(datetime.datetime.now())

        elements = []
        elements.append(Paragraph("<u>Master Controllers Report</u>", STYLES['title']))

        doc = SimpleDocTemplate(response, pagesize=A4,
                                rightMargin=0, leftMargin=6.5 * centimeter,
                                topMargin=0.3 * centimeter, bottomMargin=0)

        data = list(master_objects.values_list('gateway__region__name',
                                               'device_id',
                                               'gateway__device_id',
                                               'trackers_count',
                                               'wind_speed',
                                               'active'))
        data.insert(0, ('Region', 'Device ID', 'Gateway ID', 'Trackers', 'Wind Speed', 'Active'))

        table = Table(data, colWidths=70, rowHeights=25)
        table.setStyle(TableStyle([
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('BOX', (0, 0), (-1, -1), 0.25, colors.grey),
            ('FONT', (0, 0), (5, 0), 'Helvetica-Bold'),
            ]))
        elements.append(table)
        doc.build(elements)

    elif download == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; \
filename="MasterControllerReport_%s.csv"' %str(datetime.datetime.now())
        master_values = list(master_objects.values('gateway__region__name',
                                                   'device_id', 'gateway__device_id',
                                                   'trackers_count', 'wind_speed', 'active'))
        master_values.insert(0, {'gateway__region__name': 'Region Name',
                                 'device_id': 'Device ID',
                                 'gateway__device_id':'Gateway ID',
                                 'trackers_count':'Trackers Count',
                                 'wind_speed':'Wind Speed',
                                 'active': 'Active'})
        keys = [
            'gateway__region__name', 'device_id',
            'gateway__device_id', 'trackers_count',
            'wind_speed', 'active']
        writer = csv.DictWriter(response, keys)
        #writer.writeheader()
        writer.writerows(master_values)

    return response

def process_trackers_status_report(selected_regions, download=False):
    """
    Generates tracker devices report which is available \
    as pdf and csv along with HTML display
    """
    #trackers_report = []
    tracker_objects = TrackerController.objects.filter(
        master_controller__gateway__region__id__in=selected_regions).order_by(
            'master_controller__gateway__region').annotate(
                drive_controllers_count=Count('drivecontroller')).order_by(
                    'master_controller__gateway__id')
    if not download:
        return tracker_objects.values('master_controller__gateway__region__name',
                                      'device_id', 'master_controller__device_id',
                                      'master_controller__gateway__device_id',
                                      'drive_controllers_count', 'inner_temperature',
                                      'wired_connectivity', 'wireless_connectivity', 'active', 'inactive_at')

    if download == 'pdf':
        centimeter = 2.54

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; \
filename="TrackerControllersReport_%s.pdf"' %str(datetime.datetime.now())

        elements = []
        elements.append(Paragraph("<u>Tracker Controllers Report</u>", STYLES['title']))

        doc = SimpleDocTemplate(response, pagesize=A4,
                                rightMargin=0, leftMargin=0,
                                topMargin=0.3 * centimeter, bottomMargin=0)

        data = list(tracker_objects.values_list('master_controller__gateway__region__name',
                                                'device_id', 'master_controller__device_id',
                                                'master_controller__gateway__device_id',
                                                'drive_controllers_count', 'inner_temperature',
                                                'wired_connectivity',
                                                'wireless_connectivity', 'active'))
        data.insert(0, ('Region', 'Device ID',
                        'Master ID', 'Gateway ID',
                        'Actuators', 'Inner Temp',
                        'RS485', 'ZigBee', 'Active'))

        table = Table(data, colWidths=65, rowHeights=25)
        table.setStyle(TableStyle([
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('BOX', (0, 0), (-1, -1), 0.10, colors.grey),
            ('FONT', (0, 0), (8, 0), 'Helvetica-Bold'),
            ]))
        elements.append(table)
        doc.build(elements)

    elif download == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; \
filename="TrackerControllerReport_%s.csv"' %str(datetime.datetime.now())
        tracker_values = list(tracker_objects.values('master_controller__gateway__region__name',
                                                     'device_id', 'master_controller__device_id',
                                                     'master_controller__gateway__device_id',
                                                     'drive_controllers_count', 'inner_temperature',
                                                     'wired_connectivity', 'wireless_connectivity',
                                                     'active'))
        tracker_values.insert(0, {'master_controller__gateway__region__name': 'Region Name',
                                  'device_id': 'Device ID',
                                  'master_controller__device_id':'Master ID',
                                  'master_controller__gateway__device_id':'Gateway ID',
                                  'drive_controllers_count':'Actuators Count',
                                  'inner_temperature':'Inner Temp',
                                  'wired_connectivity':'RS485',
                                  'wireless_connectivity':'ZigBee',
                                  'active': 'Active'})
        keys = [
            'master_controller__gateway__region__name',
            'device_id', 'master_controller__device_id',
            'master_controller__gateway__device_id',
            'drive_controllers_count', 'inner_temperature',
            'wired_connectivity', 'wireless_connectivity', 'active']
        writer = csv.DictWriter(response, keys)
        #writer.writeheader()
        writer.writerows(tracker_values)

    return response

def process_drive_controller_report(selected_regions, download=False):
    """
    Generates drive controllers devices report which is \
    available as pdf and csv along with HTML display
    """
    #drive_report = []
    drive_objects = DriveController.objects.filter(
        tracker_controller__master_controller__gateway__region__id__in=selected_regions, active=True).order_by(
            'tracker_controller__master_controller__gateway__region').order_by(
                'tracker_controller__master_controller__gateway__id')
    if not download:
        return drive_objects.values('tracker_controller__master_controller__gateway__region__name',
                                    'device_id', 'tracker_controller__device_id',
                                    'tracker_controller__master_controller__device_id',
                                    'tracker_controller__master_controller__gateway__device_id',
                                    'inclinometer_tilt_angle', 'current_consumption')

    if download == 'pdf':
        centimeter = 2.54

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; \
filename="DriveControllersReport_%s.pdf"' %str(datetime.datetime.now())

        elements = []
        elements.append(Paragraph("<u>Drive Controllers Report</u>", STYLES['title']))

        doc = SimpleDocTemplate(response, pagesize=A4,
                                rightMargin=0, leftMargin=0,
                                topMargin=0.3 * centimeter, bottomMargin=0)

        data = list(drive_objects.values_list(
            'tracker_controller__master_controller__gateway__region__name',
            'device_id', 'tracker_controller__device_id',
            'tracker_controller__master_controller__device_id',
            'tracker_controller__master_controller__gateway__device_id',
            'inclinometer_tilt_angle', 'current_consumption'))
        data.insert(0, ('Region', 'Device ID',
                        'Tracker ID', 'Master ID', 'Gateway ID',
                        wrap_text('Inclinometer <br/>Angle'),
                        wrap_text('Current <br/>Consumption')))

        table = Table(data, colWidths=[70, 70, 70, 70, 70, 90, 90], rowHeights=25)
        table.setStyle(TableStyle([
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('BOX', (0, 0), (-1, -1), 0.10, colors.grey),
            ('FONT', (0, 0), (6, 0), 'Helvetica-Bold'),
            ]))
        elements.append(table)
        doc.build(elements)

    elif download == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; \
filename="DriveControllerReport_%s.csv"' %str(datetime.datetime.now())
        drive_values = list(drive_objects.values(
            'tracker_controller__master_controller__gateway__region__name',
            'device_id', 'tracker_controller__device_id',
            'tracker_controller__master_controller__device_id',
            'tracker_controller__master_controller__gateway__device_id',
            'inclinometer_tilt_angle',
            'current_consumption'))
        drive_values.insert(0, {
            'tracker_controller__master_controller__gateway__region__name': 'Region Name',
            'device_id': 'Device ID',
            'tracker_controller__device_id':'Tracker ID',
            'tracker_controller__master_controller__device_id':'Master ID',
            'tracker_controller__master_controller__gateway__device_id':'Gateway ID',
            'inclinometer_tilt_angle': 'Inclinometer Angle',
            'current_consumption':'Current Consumption'})
        keys = [
            'tracker_controller__master_controller__gateway__region__name',
            'device_id', 'tracker_controller__device_id',
            'tracker_controller__master_controller__device_id',
            'tracker_controller__master_controller__gateway__device_id',
            'inclinometer_tilt_angle', 'current_consumption'
            ]
        writer = csv.DictWriter(response, keys)
        #writer.writeheader()
        writer.writerows(drive_values)

    return response


def process_maintenance_report(selected_regions, download=False):
    """
    Generates maintenance commands report which \
    is available as pdf and csv along with HTML display
    """
    #maintenance_report = []
    maintenance_actions = [
        'STOW', 'CLEANING', 'RESET',
        'STOW_ALL', 'CLEANING_ALL', 'RESET_ALL',
        'FIRMWARE_UPDATE', 'FIRMWARE_UPDATE_ALL',
        'HIGH_WIND', 'RESET_HIGH_WIND']
    maintenance_objects = ActionProperties.objects.filter(
        region__id__in=selected_regions,
        action__in=maintenance_actions).order_by('-id')

    if not download:
        return maintenance_objects.values('region__name',
                                          'action', 'email',
                                          'tracker_controller__device_id',
                                          'master_controller__device_id',
                                          'gateway__device_id', 'created_at')

    if download == 'pdf':
        centimeter = 2.54

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; \
filename="MaintenanceReport_%s.pdf"' %str(datetime.datetime.now())

        elements = []

        elements.append(Paragraph("<u>Maintenance Report</u>", STYLES['title']))


        doc = SimpleDocTemplate(response, pagesize=A4,
                                rightMargin=0, leftMargin=0,
                                topMargin=0.3 * centimeter, bottomMargin=0)


        data = list(maintenance_objects.extra(
            select={'date':"to_char(trackercontroller_actionproperties.created_at,\
                'YYYY-MM-DD HH:mi AM')"}).values_list(
                    'region__name', 'action', 'email', 'tracker_controller__device_id',
                    'master_controller__device_id', 'gateway__device_id', 'date'))
        data.insert(0, ('Region', 'Action',
                        "Action By", "Tracker",
                        "Master", "Gateway ID",
                        "Action Time"))

        table = Table(data, colWidths=[70, 130, 120, 50, 50, 65, 110], rowHeights=25)
        table.setStyle(TableStyle([
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('BOX', (0, 0), (-1, -1), 0.25, colors.grey),
            ('FONT', (0, 0), (6, 0), 'Helvetica-Bold'),
            ]))

        elements.append(table)
        doc.build(elements)

    elif download == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; \
filename="maintenanceReport_%s.csv"' %str(datetime.datetime.now())

        maintenance_values = list(maintenance_objects.extra(
            select={'date':"to_char(trackercontroller_actionproperties.created_at,\
            'YYYY-MM-DD HH:mi AM')"}).values(
                'region__name', 'action',
                'email', 'tracker_controller__device_id',
                'master_controller__device_id',
                'gateway__device_id', 'date'))
        maintenance_values.insert(0, {'region__name':'Region',
                                      'action': 'Action', 'email':'Action By',
                                      'tracker_controller__device_id':'Tracker ID',
                                      'master_controller__device_id':'Master ID',
                                      'gateway__device_id':'Gateway ID',
                                      'date': 'Action Time'})
        keys = [
            'region__name', 'action', 'email',
            'tracker_controller__device_id',
            'master_controller__device_id',
            'gateway__device_id', 'date']
        writer = csv.DictWriter(response, keys)
        writer.writerows(maintenance_values)

    return response




@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def reports(request):
    """
    Generates devices report which is available as \
    HTML display 15 records per page
    """

    data = request.POST.copy()
    if not data:
        data = request.GET
        selected_regions = re.findall('\d+', data.get('selected_regions', ''))
    else:
        #POST DATA
        selected_regions = data.getlist('selected_regions')

    result_dict = base_dict(request)
    result_dict.update({"device_types": ["gateway", "master controller",
                                         "tracker controller", "drive controller",
                                         "maintenance"]})
    if not data:
        response = render_to_response('reports.html', result_dict)
        return response
    device_type = data.get('device_type')
    selected_regions = [int(region_id) for region_id in selected_regions]
    download = data.get('download', '')

    if not selected_regions or not device_type:
        #render the response with error message
        response = render_to_response('reports.html', result_dict)
        return response

    if device_type == 'gateway':
        if download:
            response = process_gateway_status_report(selected_regions, download=download)
            return response

        gateways = process_gateway_status_report(selected_regions)
        paginator = Paginator(gateways, 15)
        page = request.GET.get('page')

        try:
            gateways_pagination = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            gateways_pagination = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            gateways_pagination = paginator.page(paginator.num_pages)
        result_dict.update({"gateways": gateways_pagination})

    elif device_type == 'master controller':
        if download:
            response = process_masters_status_report(selected_regions, download=download)
            return response

        masters = process_masters_status_report(selected_regions)

        paginator = Paginator(masters, 15)
        page = request.GET.get('page')

        try:
            masters_pagination = paginator.page(page)
        except PageNotAnInteger:
            masters_pagination = paginator.page(1)
        except EmptyPage:
            masters_pagination = paginator.page(paginator.num_pages)
        result_dict.update({"masters": masters_pagination})

    elif device_type == 'tracker controller':
        if download:
            response = process_trackers_status_report(selected_regions, download=download)
            return response

        trackers = process_trackers_status_report(selected_regions)

        paginator = Paginator(trackers, 15)
        page = request.GET.get('page')

        try:
            trackers_pagination = paginator.page(page)
        except PageNotAnInteger:
            trackers_pagination = paginator.page(1)
        except EmptyPage:
            trackers_pagination = paginator.page(paginator.num_pages)
        result_dict.update({"trackers": trackers_pagination})

    elif device_type == 'maintenance':
        if download:
            response = process_maintenance_report(selected_regions, download=download)
            return response

        maintenance_reports = process_maintenance_report(selected_regions)

        paginator = Paginator(maintenance_reports, 15)
        page = request.GET.get('page')

        try:
            maintenance_reports_pagination = paginator.page(page)
        except PageNotAnInteger:
            maintenance_reports_pagination = paginator.page(1)
        except EmptyPage:
            maintenance_reports_pagination = paginator.page(paginator.num_pages)
        result_dict.update({"maintenance_reports": maintenance_reports_pagination})

    elif device_type == 'drive controller':
        if download:
            response = process_drive_controller_report(selected_regions, download=download)
            return response

        drive_controllers = process_drive_controller_report(selected_regions)

        paginator = Paginator(drive_controllers, 15)
        page = request.GET.get('page')

        try:
            drive_controllers_pagination = paginator.page(page)
        except PageNotAnInteger:
            drive_controllers_pagination = paginator.page(1)
        except EmptyPage:
            drive_controllers_pagination = paginator.page(paginator.num_pages)
        result_dict.update({"drive_controllers": drive_controllers_pagination})


    result_dict.update({"selected_device_type": device_type})
    result_dict.update({"selected_regions": selected_regions})
    response = render_to_response('reports.html', result_dict)

    return response


@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def display_inactive_devices(request):
    """
    Inactive devices detailed list will be displayed in \
    tabular format on SCADA portal
    """
    user = get_user(request.user)
    regions = get_user_regions(user)

    inactive_gateways = Gateway.objects.filter(active=False, region__in=regions).order_by('region')
    inactive_masters = MasterController.objects.filter(active=False,
                                                       gateway__region__in=regions).order_by(
                                                           'gateway__region')
    inactive_trackers = TrackerController.objects.filter(
        master_controller__gateway__region__in=regions).filter(
            Q(wired_connectivity=False) | Q(wireless_connectivity=False)).order_by(
                'master_controller__gateway__region')

    result_dict = base_dict(request)
    result_dict.update({"inactive_gateways": inactive_gateways})
    result_dict.update({"inactive_masters": inactive_masters})
    result_dict.update({"inactive_trackers": inactive_trackers})
    response = render_to_response('inactive_devices.html', result_dict)
    return response


###Graphs
@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def live_data_streaming(request):
    """
    Live streaming of selected param shall be displayed in \
    graphical representation. (Live streaming is only for today's data)
    """

    series = []
    #summary = []

    result_dict = base_dict(request)
    data = request.GET

    if not data:
        data = request.POST
        request_type = "historical"
        template = 'historical_data.html'
        now = datetime.date.strftime(datetime.datetime.today(), '%m/%d/%Y')
        from_date = data.get('from_date', '')
        till_date = data.get('till_date', '')

        if not from_date and not till_date:
            from_date = now
            till_date = now

        #format to datetime for django query
        if from_date:
            result_dict["from_date"] = from_date
            from_date = datetime.datetime.strptime(from_date, '%m/%d/%Y').date()
        if till_date:
            result_dict["till_date"] = till_date
            till_date = datetime.datetime.strptime(
                till_date, '%m/%d/%Y').date() + datetime.timedelta(days=1)
    else:
        request_type = "live" #GET
        template = 'live_data.html'
        result_dict["today"] = datetime.datetime.today().date()


    device_model = eval(data.get('device_type', 'None'))
    device_id = data.get('device_id', '')
    param = data.get('param')



    result_dict["device_id"] = int(device_id)
    result_dict["param"] = param
    result_dict["device_type"] = data.get('device_type', 'None')

    if device_model == DriveController:
        device = DriveController.objects.get(id=device_id)
    elif device_model == TrackerController:
        device = TrackerController.objects.get(id=device_id)
    elif device_model == MasterController:
        device = MasterController.objects.get(id=device_id)
    elif device_model == Gateway:
        device = Gateway.objects.get(id=device_id)

    #if not device return error msg instead 404
    if request_type == 'live':
        actions_query = "ActionProperties.objects.filter(\
                         %s=device, action_on=param, message_at__range=('%s', '%s')\
                         ).order_by('message_at')" %(
                             '_'.join(re.findall('[A-Z][^A-Z]*',
                                                 device.__class__.__name__)).lower(),
                             datetime.datetime.today().date(),
                             (datetime.datetime.now()+datetime.timedelta(days=1)).date())
    elif request_type == 'historical':
        if from_date and till_date:
            actions_query = "ActionProperties.objects.filter(\
                             %s=device, action_on=param, message_at__range=['%s', '%s']\
                             ).order_by('message_at')" %(
                                 '_'.join(re.findall('[A-Z][^A-Z]*',
                                                     device.__class__.__name__)).lower(),
                                 from_date, till_date)
        elif from_date:
            actions_query = "ActionProperties.objects.filter(\
                             %s=device, action_on=param, message_at__gt='%s'\
                             ).order_by('message_at')" %(
                                 '_'.join(re.findall('[A-Z][^A-Z]*',
                                                     device.__class__.__name__)).lower(),
                                 from_date)
        elif till_date:
            actions_query = "ActionProperties.objects.filter(\
                             %s=device, action_on=param, message_at__lt='%s'\
                             ).order_by('message_at')" %(
                                 '_'.join(re.findall('[A-Z][^A-Z]*',
                                                     device.__class__.__name__)).lower(),
                                 till_date)

    records_data = eval(actions_query)

    try:
        latest_record = list(records_data)[-1]
    except IndexError:
        latest_record = None

    #count = records_data.count()
    #if count > 20:
    #    devices_data = records_data.filter(
    #         id__gte=int(latest_record.id)-20).extra(
    #              select={'value': 'value_decimal',
    #                       "on": "extract(epoch from created_at)"
    #                      }).values('value', 'on')
    #else:
    devices_data = records_data.extra(select={'value': 'value_decimal',
                                              "on": "extract(epoch from message_at)"}
                                     ).values('value', 'on')
    for record in devices_data:
        record['value'] = float(record['value'])

    if request_type == 'live':
        series.append(list(devices_data)[-2500:])
    elif request_type == 'historical':
        series.append(list(devices_data))

    if latest_record:
        result_dict["devices_data_id"] = latest_record.id

    result_dict["device_names"] = [str(param).replace('_', ' ').title()]

    #only for target angle
    result_dict["target_angle_devices_data_id"] = 0 #work around to make js work for all params
    if param == 'inclinometer_tilt_angle':
        if request_type == 'live':
            actions_query = "ActionProperties.objects.filter(\
                             tracker_controller=device.tracker_controller,\
                              action_on='target_angle', message_at__range=('%s', '%s')\
                              ).order_by('message_at')" %(datetime.datetime.today().date(),
                              (datetime.datetime.now()+datetime.timedelta(days=1)).date())
        elif request_type == 'historical':

            if from_date and till_date:
                actions_query = "ActionProperties.objects.filter(\
                                 tracker_controller=device.tracker_controller,\
                                 action_on='target_angle',\
                                 message_at__range=['%s', '%s']\
                                 ).order_by('message_at')" %(from_date, till_date)
            elif from_date:
                actions_query = "ActionProperties.objects.filter(\
                                 tracker_controller=device.tracker_controller,\
                                 action_on='target_angle', message_at__gt='%s'\
                                 ).order_by('message_at')" %(from_date)
            elif till_date:
                actions_query = "ActionProperties.objects.filter(\
                                 tracker_controller=device.tracker_controller,\
                                 action_on='target_angle', message_at__lt='%s'\
                                 ).order_by('message_at')" %(till_date)

        target_angle_data = eval(actions_query)
        result_dict["device_names"].append("Target Angle")
        try:
            target_data_latest_record = list(target_angle_data)[-1]
            result_dict["target_angle_devices_data_id"] = target_data_latest_record.id
        except IndexError:
            target_data_latest_record = ''

        target_angle_data = target_angle_data.extra(
            select={'value': 'value_decimal',
                    "on": "extract(epoch from message_at)"
                   }).values('value', 'on')
        for record in target_angle_data:
            record['value'] = float(record['value'])

        series.append(list(target_angle_data)) #Target

    result_dict["data"] = series
    response = render_to_response(template, result_dict)
    return response


@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def live_data_streaming_ajax(request):
    """
    Live streaming of selected param shall be displayed \
    in graphical representation. Ajax call checks for any \
    update in data and updates the same in graph for every 3 seconds
    """
    try:
        data = eval(str(request.body))
    except SyntaxError:
        data = request.POST.copy()

    device_id = data['device_id']
    devices_data_id = data['devices_data_id']
    param = data['param']
    device_model = eval(data['device_type'])
    if device_model == DriveController:
        device = DriveController.objects.get(id=device_id)
    elif device_model == TrackerController:
        device = TrackerController.objects.get(id=device_id)
    elif device_model == MasterController:
        device = MasterController.objects.get(id=device_id)
    elif device_model == Gateway:
        device = Gateway.objects.get(id=device_id)

    actions_query = "ActionProperties.objects.filter(\
                     %s=device, action_on=param, id__gt=devices_data_id, \
                     message_at__range=(datetime.datetime.today().date(),\
                     (datetime.datetime.now()+datetime.timedelta(days=1)).date())).order_by('message_at')" %(
                         '_'.join(re.findall('[A-Z][^A-Z]*',
                                             device.__class__.__name__)).lower())


    devices_data = eval(actions_query)
    updated_data = devices_data.extra(
        select={'value': 'value_decimal',
                "on": "extract(epoch from message_at)"
               }).values('value', 'on')
    try:
        latest_record = list(devices_data)[-1]
    except IndexError:
        latest_record = None

    response = {'data':[[], []]}

    if latest_record:
        response.update({"devices_data_id": latest_record.id})
        response['data'][0] = list(updated_data)

    if param == 'inclinometer_tilt_angle':
        target_angle_devices_data_id = data['target_angle_devices_data_id']
        actions_query = "ActionProperties.objects.filter(\
                         tracker_controller=device.tracker_controller,\
                         action_on='target_angle', message_at__range=('%s', '%s'), id__gt='%s'\
                         ).order_by('message_at')" %(datetime.datetime.today().date(),
                                             (datetime.datetime.now()+datetime.timedelta(days=1)).date(),
                                             target_angle_devices_data_id)

        devices_data = eval(actions_query)
        updated_data = devices_data.extra(
            select={'value': 'value_decimal',
                    "on": "extract(epoch from message_at)"
                   }).values('value', 'on')

        try:
            latest_record = list(devices_data)[-1]
        except IndexError:
            latest_record = None

        if latest_record:
            response.update({"target_angle_devices_data_id": latest_record.id})
            response['data'][1] = list(updated_data)

    return HttpResponse(simplejson.dumps(response), content_type='application/json')

@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def bulk_updates(request):
    """
    Bulk selection of devices to send commands for \
    cleaning, stow and firmwate update.
    Eg: All masters of selected Gateway
    """

    actions = ['CLEANING', 'STOW', 'RESET', 'FIRMWARE_UPDATE']

    result_dict = base_dict(request)
    regions = result_dict['regions']

    gateways = Gateway.objects.filter(region__id__in=regions.values_list('id', flat='true'))

    masters = MasterController.objects.filter(
        gateway__id__in=gateways.values_list('id', flat='true'))

    result_dict.update({"actions": actions})
    result_dict.update({"gateways": gateways})
    result_dict.update({"masters": masters})
    response = render_to_response('bulk_updates.html', result_dict)
    return response

@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
@login_required(login_url='/login/')
@is_standard_user
def bulk_updates_proc(request):

    """
    Bulk selection of devices submitted by user along with \
    the action will be processed and stored in queue to trigger commands
    """
    data = request.POST
    device_type = data.get('device_type', '')
    if not device_type:
        device_type = data.get('property', '')
    action = data.get('selected_action', '')
    device_ids = data.getlist('devices')
    if device_type and action:
        action = action + '_ALL'
        if device_type == 'TrackerController':
            model = MasterController
        elif device_type == 'MasterController':
            model = Gateway

        devices = model.objects.filter(id__in=device_ids)
        for device in devices:
            if device_type == 'TrackerController':
                gateway = device.gateway
                try:
                    ControlCommands.objects.get(action=action, master_controller=device)
                    continue
                except ControlCommands.DoesNotExist:
                    pass
                publish_pattern = 'control/%s/%s' %(gateway.device_id, device.device_id)
                control_command = ControlCommands.objects.create(
                    command='{"command":"%s"}' %action, publish_pattern=publish_pattern)
                control_command.user = get_user(request.user)
                control_command.action = action
                control_command.region = gateway.region
                control_command.master_controller = device
                control_command.gateway = gateway
                control_command.save()
            elif device_type == 'MasterController':
                try:
                    ControlCommands.objects.get(action=action, master_controller=None, gateway=device)
                    continue
                except ControlCommands.DoesNotExist:
                    pass

                publish_pattern = 'control/%s' %(device.device_id)
                control_command = ControlCommands.objects.create(
                    command='{"command":"%s"}' %action, publish_pattern=publish_pattern)
                control_command.user = get_user(request.user)
                control_command.action = action
                control_command.region = device.region
                control_command.gateway = device
                control_command.save()
            else:
                #print "Failed", model
                pass

    return HttpResponseRedirect('/iot/bulk_updates/')
