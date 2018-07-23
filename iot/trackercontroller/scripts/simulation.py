import threading
import json
import re
import sys, os, time, datetime
sys.path.append(os.path.abspath('..'))
sys.path.append('/var/www/www.mytrah.com/iot/')
sys.path.append('/var/www/www.mytrah.com/iot/mytrah/')
#dev server
#sys.path.append('/var/www/projects/mytrah/Solar-Tracker/Trunk/Source/Web/iot/')
#sys.path.append('/var/www/projects/mytrah/Solar-Tracker/Trunk/Source/Web/iot/mytrah/')

import settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mytrah.settings")
import django
django.setup()


import paho.mqtt.client as mqtt

from trackercontroller.models import Region, Gateway, MasterController, TrackerController, DriveController, ControlCommands, ActionProperties, User


def gateways():
    import time
    while True:
        time.sleep(5)
        region = Region.objects.get(region_id="CLX")
        gateways = Gateway.objects.filter(region=region)
        for gateway in gateways:
            client.publish('monitors/%s'%(gateway.device_id), '{"active":true}', 1)

def masters():
    import time
    from random import randint
    while True:
        time.sleep(3)
        region = Region.objects.get(region_id="CLX")
        masters = MasterController.objects.filter(gateway__region=region)
        windspeed = randint(30, 50)
        for master in masters:
            trackers = str(list(master.trackercontroller_set.all().values_list('device_id', flat='true')))
            message = ' {"latitude":12.9577 ,"longitude":77.7444 ,"altitude":904.3,"wind_speed":%s,"wind_direction":"NE"}' %windspeed
            client.publish('monitors/%s/%s'%(master.gateway.device_id, master.device_id), message, 1)
            message = '{"active_wireless_connectivity":%s,"inactive_wireless_connectivity":[],"active_wired_connectivity":[],"inactive_wired_connectivity":%s}' %(trackers, trackers)
            client.publish('monitors/%s/%s'%(master.gateway.device_id, master.device_id), message, 1)


def trackers():
    import time
    from random import randint
    while True:
        time.sleep(60)
        region = Region.objects.get(region_id="CLX")
        trackers = TrackerController.objects.filter(master_controller__gateway__region=region)
        for tracker in trackers:
            print  ">>>>>>>>>>>>>>>>>", tracker.device_id
            target_angle = tracker.target_angle
            if target_angle == 90:
                target_angle = -90
            else:
                target_angle = tracker.target_angle + 1
              
            inclinometer_tilt_angle = target_angle + randint(0, 9)
            if inclinometer_tilt_angle > 90:
                inclinometer_tilt_angle = 90

            inner_temperature =  randint(15,40) 
            current_consumption = randint(1, 9)
            
            params = [inner_temperature, target_angle] +[current_consumption, inclinometer_tilt_angle]*7

            drives_data = []
            drive_controllers = tracker.drivecontroller_set.all()
            for dc in drive_controllers:
                msg = {"device_id": dc.device_id, "current_consumption":current_consumption, "inclinometer_tilt_angle":inclinometer_tilt_angle}
                drives_data.append(msg)
            
            message = '{"operating_mode":"MANUAL","inner_temperature":%s,"target_angle":%s,"drive_controller": %s}' %(inner_temperature, target_angle, drives_data)
            client.publish('monitors/%s/%s/%s'%(tracker.master_controller.gateway.device_id, tracker.master_controller.device_id, tracker.device_id), message,2)

def on_connect(client, obj, flags, rc):
    print("Connected with Result Code: "+str(rc))
        
def on_publish(client, obj, mid):
    print("Publish mesage mid: "+str(mid))

QOS = 1
client = mqtt.Client('mytrah_simulation_client')
#client.tls_set("/etc/mosquitto/certs/ca.crt", '/etc/mosquitto/certs/server.crt', '/etc/mosquitto/certs/server.key', cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1)
client.on_connect = on_connect
client.on_publish = on_publish
client.connect("mytrah.embdev.in", 1883, 60)
#client.connect("10.99.91.26", 1883, 0)

print "******************************************************"
gateways_thread = threading.Thread(name='gateways', target=gateways)
gateways_thread.start()
print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
masters_thread = threading.Thread(name='masters', target=masters)
masters_thread.start()
print "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
trackers_thread = threading.Thread(name='trackers', target=trackers)
trackers_thread.start()

client.loop_forever()
