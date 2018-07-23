"""
MQTT Script to publish and subscribe data packets
"""
import threading
import json
import re
import sys
import os
import  time
import datetime
import ssl
from decimal import Decimal
import django
from django.db import connection
import paho.mqtt.client as mqtt

sys.path.append(os.path.abspath('..'))
sys.path.append('/var/www/www.mytrah.com/iot/')
sys.path.append('/var/www/www.mytrah.com/iot/mytrah/')

import settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mytrah.settings")

django.setup()

from trackercontroller.models import Region, Gateway, MasterController,\
                                     TrackerController, DriveController, ControlCommands,\
                                     ActionProperties, User
from trackercontroller.mail import send_mail


TESTING = True

QOS = 1
SEND_MAIL = False
OFFLINE_TIME = 240
FOTA_UPDATE_HOURS = 19
FOTA_UPDATE_MINS = 15
RESEND_COMMAND = 300 #in Seconds
COMMAND_EXPIRY = 3600 #in seconds


def create_gateway(device_id):
    region = Region.objects.get(region_id=device_id[:3])
    device, created = Gateway.objects.get_or_create(device_id=device_id, region=region)
    connection.close()
    return device

def create_master(gateway_id, device_id):
    gateway = create_gateway(gateway_id)
    device, created = MasterController.objects.get_or_create(device_id=device_id, gateway=gateway)
    connection.close()
    return device

def create_tracker(gateway_id, master_id, device_id):
    master = create_master(gateway_id, master_id)
    device, created = TrackerController.objects.get_or_create(device_id=device_id,
                                                              master_controller=master)
    connection.close()
    return device

def create_drive_controller(tracker, device_id):
    device = DriveController.objects.create(device_id=device_id, actuator_type=device_id[:2],
                                            tracker_controller=tracker)
    connection.close()
    DriveController.objects.filter(tracker_controller=tracker,
                                   active=True).exclude(actuator_type=device_id[:2]
                                                        ).update(active=False)
    DriveController.objects.filter(tracker_controller=tracker,
                                   active=False, actuator_type=device_id[:2]).update(active=True)
    return device

def get_device_object(model, **kwargs):
    try:
        if model == Gateway:
            try:
                device = model.objects.get(device_id=kwargs['gateway_id'])
            except Gateway.DoesNotExist:
                device = create_gateway(kwargs['gateway_id'])

        elif model == MasterController:
            try:
                device = model.objects.get(device_id=kwargs['master_id'],
                                           gateway__device_id=kwargs['gateway_id'])
            except MasterController.DoesNotExist:
                device = create_master(kwargs['gateway_id'], kwargs['master_id'])

        elif model == TrackerController:
            try:
                device = model.objects.get(device_id=kwargs['tracker_id'],
                                           master_controller__device_id=kwargs['master_id'],
                                           master_controller__gateway__device_id=
                                           kwargs['gateway_id'])
            except TrackerController.DoesNotExist:
                device = create_tracker(kwargs['gateway_id'],
                                        kwargs['master_id'],
                                        kwargs['tracker_id'])
        connection.close()
    except Exception, e:
        device = None
        print "No such Device", str(e)
    return device

def set_properties(instance, data):
    offline_data = False
    message_at = datetime.datetime.now()
    if data.has_key('datetime'):
        _datetime = str(data.pop('datetime'))
        try:
            message_at = datetime.datetime.strptime(_datetime, "%Y%m%d%H%M%S")
            #Logic to identify offline data / current data
            if message_at < datetime.datetime.now()-datetime.timedelta(seconds=OFFLINE_TIME):
                offline_data = True
        except Exception, e:
            pass
    if data.has_key('version'):
        data['version'] = '.'.join([str(int(ver)) for ver in data['version'].split('.')])

    for attr, value in data.iteritems():
        try:
            attr_value = eval("instance.%s" %attr)
            action = None
            if isinstance(attr_value, Decimal):
                action = ActionProperties.objects.create(action="DATA",
                                                         action_on=attr,
                                                         value_decimal=value)
            elif isinstance(attr_value, bool) and attr_value != value:
                action = ActionProperties.objects.create(action="DATA",
                                                         action_on=attr,
                                                         value_bool=value)
                if attr == 'high_wind':
                    if value:
                        action.action = "HIGH_WIND"
                    else:
                        action.action = "RESET_HIGH_WIND"
                    action.region = instance.gateway.region
                    action.gateway = instance.gateway
                    action.master_controller = instance
            else:
                if str(attr_value) != str(value):
                    action = ActionProperties.objects.create(action="DATA",
                                                             action_on=attr,
                                                             value_char=value)
            if action:
                if message_at:
                    action.message_at = message_at
                model_field = '_'.join(re.findall('[A-Z][^A-Z]*',
                                                  instance.__class__.__name__)).lower()
                setattr(action, model_field, instance)
                action.save()
                connection.close()

        except Exception, e:
            print ">>>>>>>>>>>>>", str(e)
            pass

        if not offline_data or attr in ["fw_status"] or instance.updated_at < message_at:
            setattr(instance, attr, value)
    instance.save()
    connection.close()
    return instance

def process_on_message(topic, data):
    gateway_id, master_id, tracker_id = ['', '', '']

    device_ids = topic.rsplit('/')[1:]
    if len(device_ids) == 1:
        gateway_id = device_ids[0]
    elif len(device_ids) == 2:
        gateway_id, master_id = device_ids
    elif len(device_ids) == 3:
        gateway_id, master_id, tracker_id = device_ids
    else:
        return

    if tracker_id:
        device = get_device_object(TrackerController, tracker_id=tracker_id,
                                   master_id=master_id, gateway_id=gateway_id)
        if not device:
            return

        #Logic to receive ack for commands from SCADA
        if topic.startswith('ack'):
            commands = ControlCommands.objects.filter(sent=True, ack=False, action=data['command'], tracker_controller=device)
            #commands.update(ack=True)
            commands.delete()
            return

        drive_controllers = data.pop('drive_controller', '')
        _datetime = data.get('datetime', False)
        set_properties(device, data)
        drivecontroller_set = device.drivecontroller_set.all()
        for drive_count, drive_controller_data in enumerate(drive_controllers):
            drive_controller_device_id = drive_controller_data.pop('device_id')
            try:
                drivecontroller = drivecontroller_set.get(device_id=drive_controller_device_id)
                #alternate drive types will be marked inactive AC / DC
                if drive_count == 0:
                    drivecontroller_set.exclude(actuator_type=drive_controller_device_id[:2], active=True).update(active=False)
                    drivecontroller_set.filter(actuator_type=drive_controller_device_id[:2], active=False).update(active=True) 
            except DriveController.DoesNotExist:
                if drive_controller_data['actuator_status'] == 2:
                    #dont create drive controllers if not connected to tracker
                    continue
                drivecontroller = create_drive_controller(device, drive_controller_device_id)
            if _datetime:
                drive_controller_data['datetime'] = _datetime
            drive_controller_data['active'] = True
            set_properties(drivecontroller, drive_controller_data)

    elif master_id:
        device = get_device_object(MasterController, master_id=master_id, gateway_id=gateway_id)
        if not device:
            return


        if topic.startswith('ack'):
            commands = ControlCommands.objects.filter(sent=True, ack=False, action=data['command'], master_controller=device, tracker_controller=None)
            #commands.update(ack=True)
            commands.delete()
            return

        previous_device_state = device.active

        #Flag to check data pack is regarding trackers connectivity or not
        connectivity_check = False
        if data.has_key('active_wireless_connectivity'):
            connectivity_check = True

        #Logic to update active and inactive trackers connectivity wired / wireless
        inactive_wired_connectivity = data.pop('inactive_wired_connectivity', [])
        inactive_wireless_connectivity = data.pop('inactive_wireless_connectivity', [])
        active_wired_connectivity = data.pop('active_wired_connectivity', [])
        active_wireless_connectivity = data.pop('active_wireless_connectivity', [])

        if data.has_key('active'):
            if data['active'] == True:
                data['inactive_at'] = None
            else:
                data['inactive_at'] = datetime.datetime.now()
        else:
            data['active'] = True
            data['inactive_at'] = None

        offline_data = False
        if data.has_key('datetime'):
            _datetime = data['datetime']
            try:
                message_at = datetime.datetime.strptime(_datetime, "%Y%m%d%H%M%S")
                #Logic to identify offline data / current data
                if message_at < datetime.datetime.now()-timedelta(seconds=OFFLINE_TIME):
                    offline_data = True
            except:
                pass

        _master = set_properties(device, data)
        current_device_state = _master.active

        if current_device_state == False and current_device_state != previous_device_state:
            if SEND_MAIL:
                message = '''Hello,<br/><br/><b>Master Controller</b> \
is inactive and details below! Please take an immediate action!'''
                message += '''<br/><br/><table border="2"><tr><td><b>Region Name</b>\
</td><td><b>GatewayID</b></td><td><b>Master ID</b></td></tr>'''
                message += '''<tr><td>%s</td><td>%s</td><td>%s</td></tr>\
''' %(_master.gateway.region.name, _master.gateway.device_id, _master.device_id)
                message += '</table>'
                message += '<br/>Regards,<br/>SCADA Report<br/>'

                subject = 'Solar Tracker - Inactive Master Controllers Alert!'
                receivers = list(User.objects.filter(regions=device.gateway.region,
                                                     role__level=3).values_list(
                                                         'email', flat='true'))
                send_mail("dontreply@mytrah.com", receivers, subject, message, [], [])
            connection.close()

        message = ''

        #check -  To find out trackers exists or not? if not create and update
        tracker_ids = list(set(inactive_wired_connectivity +
                               active_wired_connectivity +
                               inactive_wireless_connectivity +
                               active_wireless_connectivity))
        all_trackers = device.trackercontroller_set
        available_trackers = all_trackers.filter(device_id__in=tracker_ids).values_list(
            'device_id', flat='true')

        #logic for trackers which might be reconfigured -  marking them as inactive!
        if connectivity_check: # and offline_data == False:
            reconfigured_trackers = device.trackercontroller_set.filter(
                device_id__in=list(set(all_trackers.values_list('device_id', flat='true')) -
                                   set(tracker_ids)), reconfigured=False)
            reconfigured_trackers.update(wired_connectivity=False,
                                         wireless_connectivity=False,
                                         inactive_at=datetime.datetime.now(),
                                         active=False, reconfigured=True)
            connection.close()
        #End

        missing_trackers = list(set(tracker_ids) - set(available_trackers))
        create_trackers = []
        for missing_tracker in missing_trackers:
            create_trackers.append(TrackerController(master_controller=device,
                                                     device_id=missing_tracker))
        TrackerController.objects.bulk_create(create_trackers)
        connection.close()
        device = get_device_object(MasterController, master_id=master_id, gateway_id=gateway_id)


        if inactive_wired_connectivity:
            _trackers = device.trackercontroller_set.filter(
                device_id__in=inactive_wired_connectivity, wired_connectivity=True)

            if _trackers:
                if SEND_MAIL:
                    message += '''Hello,<br/><br/><b>RS485 Connectivity</b>\
 failed for the following devices! Please take an immediate action!'''
                    message += '''<br/><br/><table border="2">\
<tr><td><b>Region Name</b></td><td><b>GatewayID</b></td>\
<td><b>Master ID</b></td><td><b>Tracker ID</b></td></tr>'''

                    for _tracker in _trackers:
                        message += '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' %(
                            _tracker.master_controller.gateway.region.name,
                            _tracker.master_controller.gateway.device_id,
                            _tracker.master_controller.device_id, _tracker.device_id)
                    message += '</table>'

                trackers_to_mark_inactive = _trackers.filter(wireless_connectivity=False)
                trackers_to_mark_inactive.update(active=False, inactive_at=datetime.datetime.now())
                _trackers.update(wired_connectivity=False, reconfigured=False)
                connection.close()

        if active_wired_connectivity:
            _trackers = device.trackercontroller_set.filter(device_id__in=active_wired_connectivity,
                                                            wired_connectivity=False)
            _trackers.update(wired_connectivity=True, active=True, inactive_at=None,
                             reconfigured=False)
            connection.close()

        if inactive_wireless_connectivity:
            _trackers = device.trackercontroller_set.filter(
                device_id__in=inactive_wireless_connectivity,
                wireless_connectivity=True)

            if _trackers:
                if SEND_MAIL:
                    message += '''Hello,<br/><br/><b>ZigBee Connectivity</b>\
failed for the following devices! Please take an immediate action!'''
                    message += '''<br/><br/><table border="2"><tr><td><b>Region Name</b></td>\
<td><b>GatewayID</b></td><td><b>Master ID</b></td><td><b>Tracker ID</b></td></tr>'''
                    for _tracker in _trackers:
                        message += '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' %(
                            _tracker.master_controller.gateway.region.name,
                            _tracker.master_controller.gateway.device_id,
                            _tracker.master_controller.device_id, _tracker.device_id)
                    message += '</table>'

                trackers_to_mark_inactive = _trackers.filter(wired_connectivity=False)
                trackers_to_mark_inactive.update(active=False, inactive_at=datetime.datetime.now())
                _trackers.update(wireless_connectivity=False, reconfigured=False)
                connection.close()

        if active_wireless_connectivity:
            _trackers = device.trackercontroller_set.filter(
                device_id__in=active_wireless_connectivity,
                wireless_connectivity=False)
            if _trackers:
                _trackers.update(wireless_connectivity=True, active=True,
                                 inactive_at=None, reconfigured=False)
                connection.close()

        if message and SEND_MAIL:
            message += '<br/>Regards,<br/>SCADA Intelligence Report!<br/>'
            subject = 'Solar Tracker - TrackerControllers Connectivity Failure Alert!'
            receivers = list(User.objects.filter(regions=device.gateway.region,
                                                 role__level=3).values_list('email', flat='true'))
            connection.close()
            send_mail("dontreply@mytrah.com", receivers, subject, message, [], [])
            time.sleep(1)

    elif gateway_id:
        device = get_device_object(Gateway, gateway_id=gateway_id)

        if topic.startswith('ack'):
            commands = ControlCommands.objects.filter(sent=True, ack=False, action=data['command'], gateway=device, master_controller=None)
            #commands.update(ack=True)
            commands.delete()
            return

        if device:
            data['inactive_at'] = None
            set_properties(device, data)


def on_connect(client, obj, flags, rc):
    print("Connected with Result Code: "+str(rc))
    client.subscribe("monitor/#", QOS)
    client.subscribe("ack/#", QOS)

def on_message(client, obj, msg):
    print(msg.topic+" "+str(msg.qos)+" "+str(msg.payload))
    try:
        if "TMJ" in msg.topic:
            f = open("mqtt_2ndFT.log", 'a')
            f.write("%s -  %s\n\n" %(msg.topic, str(msg.payload)))
            f.close()
        data = eval(str(msg.payload).replace('true', 'True').replace('false', 'False'))

        if data.has_key('msgid'):
            msgid = data.pop('msgid')
            #send ack to gateway
            client.publish('control/%s/msgack' %(msg.topic.split('/')[1]), '{"msgid": "%s"}' %msgid , QOS)


        if data.has_key('datetime'):
            #Check -> to avoid data with future datetime (if RTC issue)
            message_at = datetime.datetime.strptime(str(data['datetime']), "%Y%m%d%H%M%S")
            if message_at > datetime.datetime.now() + datetime.timedelta(hours=1):
                return
        
        async_on_message_thread = threading.Thread(target=process_on_message,
                                                   args=(msg.topic, data))
        print "threading.active_count()", threading.active_count()
        if threading.active_count() > 250:
            time.sleep(5)
        async_on_message_thread.start()

    except Exception, e:
        print "Error parsing", str(e)
        pass

def on_publish(client, obj, mid):
    print("Publish mesage mid: "+str(mid))

def on_subscribe(client, obj, mid, granted_qos):
    print("Subscribed: "+str(mid)+" "+str(granted_qos))

def on_log(client, obj, level, string):
    print(string)



client = mqtt.Client('mytrah_mqtt_client')
client.tls_set("/etc/mosquitto/certs/ca.crt", '/etc/mosquitto/certs/server.crt',
               '/etc/mosquitto/certs/server_new.key',
               cert_reqs=ssl.CERT_REQUIRED,
               tls_version=ssl.PROTOCOL_TLSv1)
client.on_message = on_message
client.on_connect = on_connect
client.on_publish = on_publish
client.on_subscribe = on_subscribe
client.connect("mytrah.embdev.in", 8883, 60)

def publish_messages():
    while True:
        time.sleep(5)
        ControlCommands.objects.filter(sent=True, created_at__lt=datetime.datetime.now() - datetime.timedelta(seconds=COMMAND_EXPIRY)).delete()
        try:
            controls = list(ControlCommands.objects.filter(sent=False))
            #Resend commands fpr which no ack received
            controls += list(ControlCommands.objects.filter(sent=True, ack=False, updated_at__lt=datetime.datetime.now()-datetime.timedelta(seconds=RESEND_COMMAND)))
            if not TESTING and \
                datetime.datetime.now() < datetime.datetime.now().replace(hour=FOTA_UPDATE_HOURS,
                                                                          minute=FOTA_UPDATE_MINS):
                ##Firmware upgrade comands should deliver to masters/trackers only in evenings!
                controls = controls.exclude(action__in=['FIRMWARE_UPDATE', 'FIRMWARE_UPDATE_ALL'])
            for control in controls:
                print control.publish_pattern, "%s" %(control.command)
                client.publish(control.publish_pattern, "%s" %(control.command), QOS)
                #if not control.sent:
                control.sent = True
                control.save()
                action = ActionProperties.objects.create(action=control.action,
                                                         action_by=control.user,
                                                         region=control.region)
                if control.user:
                    action.email = control.user.email
                tracker_controller = control.tracker_controller
                master_controller = control.master_controller
                gateway = control.gateway

                if tracker_controller:
                    action.tracker_controller = tracker_controller
                    action.master_controller = tracker_controller.master_controller
                    action.gateway = action.master_controller.gateway
                elif master_controller:
                    action.master_controller = master_controller
                    action.gateway = master_controller.gateway
                elif gateway:
                    action.gateway = gateway
                action.save()
                #control.delete()
                connection.close()
            pass
        except Exception, e:
            print "In Exception block", str(e)
            pass

def mark_inactive_gateways():

    #mark masters and gateways as inactive if no data for so long
    while True:
        time.sleep(10)
        try:
            gateways = Gateway.objects.filter(
                updated_at__lt=datetime.datetime.now()-datetime.timedelta(seconds=120), active=True)
            if gateways:
                if SEND_MAIL:
                    subject = 'Solar Tracker - Inactive Gateway Devices Alert!'
                    message = """Hello,<br/><br/>The following gateway devices are not active\
 at this moment! Please take an immediate action!<br/><br/>"""
                    message += """<table border='2'><tr><td><b>Region</b>\
</td><td><b>Gateway ID</b></td><td><b>Inactive Time</b></td></tr>"""
                    for gateway in gateways:
                        message += '<tr><td>%s</td><td>%s</td><td>%s</td></tr>'%(
                            gateway.region.name, gateway.device_id, str(gateway.updated_at))

                    message += '</table><br/>Regards,<br/>SCADA Intelligence Report!<br/>'

                    receivers = list(User.objects.filter(regions=gateway.region,
                                                         role__level=3).values_list('email',
                                                                                    flat='true'))
                    send_mail("dontreply@mytrah.com", receivers, subject, message, [], [])

                gateways.update(active=False, inactive_at=datetime.datetime.now())
                connection.close()
        except Exception, e:
            print "In Exception block", str(e)
            pass

        try:
            masters = MasterController.objects.filter(
                updated_at__lt=datetime.datetime.now()-datetime.timedelta(seconds=10),
                active=True, gateway__active=True)
            masters.update(active=False, inactive_at=datetime.datetime.now())
            connection.close()
            if masters:
                if SEND_MAIL:
                    subject = 'Solar Tracker - Inactive Master Devices Alert!'
                    message = """Hello,<br/><br/>The following Master devices are not active\
at this moment! Please take an immediate action!<br/><br/>"""
                    message += """<table border='2'><tr><td><b>Region</b></td>\
<td><b>Gateway ID</b></td><td><b>Master ID</b></td><td><b>Inactive Time</b></td></tr>"""
                    for master in masters:
                        message += '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'%(
                            master.gateway.region.name, master.gateway.device_id,
                            str(master.gateway.updated_at))

                    message += '</table><br/>Regards,<br/>SCADA Intelligence Report!<br/>'

                    receivers = list(User.objects.filter(regions=master.gateway.region,
                                                         role__level=3).values_list('email',
                                                                                    flat='true'))
                    send_mail("dontreply@mytrah.com", receivers, subject, message, [], [])


        except Exception, e:
            pass

control_messages_thread = threading.Thread(name='publish_messages', target=publish_messages)
control_messages_thread.start()

inactive_devices_thread = threading.Thread(name='mark_inactive_gateways',
                                           target=mark_inactive_gateways)
inactive_devices_thread.start()

client.loop_forever()
