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

import datetime

import paho.mqtt.client as mqtt

from trackercontroller.models import Region, Gateway, MasterController, TrackerController, DriveController, ControlCommands, ActionProperties, User

while True:
    time.sleep(60)
    DriveController.objects.get(tracker_controller__id=1932, device_id="AC00").delete()
