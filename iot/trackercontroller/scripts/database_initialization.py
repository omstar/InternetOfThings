import sys, os
sys.path.append('/var/www/www.mytrah.com/iot/')
sys.path.append('/var/www/www.mytrah.com/')
sys.path.append('/var/www/www.mytrah.com/iot/mytrah')
#sys.path.append('/var/www/www.embitel.com/it/')
#sys.path.append('/var/www/www.embitel.com/')

import settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mytrah.settings")

import django
django.setup()

from trackercontroller.models import UserRole, User, Region, Gateway, MasterController, TrackerController, DriveController
from decimal import Decimal

roles = {1 : "Administration",
         2 : "Super User",
         3 : "Sourcing User",
         4 : "Maintenance User",
}

def create_roles():
    UserRole.objects.all().delete()
    for role_id, role_name in roles.iteritems():
        role = UserRole.objects.create(level=role_id, name=role_name)
        role.save()

create_roles()
print "Created User Roles\n", UserRole.objects.all().values('name')


regions = {"GAC" : "Gachibowli",
           "MAD" : "Madhapur",
           "KAR" : "Karnool",
}

def create_regions():
    DriveController.objects.all().delete()
    TrackerController.objects.all().delete()
    MasterController.objects.all().delete()
    Gateway.objects.all().delete()
    
    Region.objects.all().delete()
    for region_id, region_name in regions.iteritems():
        region = Region.objects.create(region_id=region_id, name=region_name, city="Hyderabad", state="Telangana", country="India")
        region.save()

def create_admin_users():
    User.objects.all().delete()
    email_id = 'admin@embitel.com'
    role = UserRole.objects.get(level=1)
    region = Region.objects.all()[0]
    user = User.objects.create(role=role, email=email_id, username=email_id, region=region, is_staff=True, is_superuser=True)
    user.set_password('admin@12')
    user.save()

def create_standard_users():
    email_id = 'demo%s@embitel.com'
    role = UserRole.objects.get(level=2)
    region = Region.objects.all()[0]
    for i in range(5,10):
        email = email_id%str(i+1)
        user = User.objects.create(role=role, email=email, username=email, region=region, is_staff=True)
        user.set_password('121212')
        user.save()

def create_gateways():
    Gateway.objects.all().delete()
    regions = Region.objects.all()
    for region in regions:
        device_ids = []
        for i in range(5):
            device_ids.append("%sG00%s" %(region.region_id, i))
        for device_id in device_ids:
            gateway = Gateway.objects.create(region=region, device_id=device_id)
            gateway.save()

def create_mcs():
    gateways = Gateway.objects.all()
    for gateway in gateways:
        device_ids = []
        for i in range(1):
            device_ids.append("M00%s"%i)
        for device_id in device_ids:
            mc = MasterController.objects.create(gateway=gateway, device_id=device_id, wind_speed=Decimal('30.00'))
            mc.save()

def create_tcs():
    masters = MasterController.objects.all()
    for master in masters:
        device_ids = []
        for i in range(2):
            device_ids.append('T00%s' %i)
        for device_id in device_ids:
            tc = TrackerController.objects.create(master_controller=master, device_id=device_id, inner_temperature=Decimal('25.00'))
            tc.save()

def create_dcs():
    trackers = TrackerController.objects.all()
    for count, tracker in enumerate(trackers):
        if count%2 == 0:
            device_ids = []
            for i in range(7):
                actuator_type = "DC"
                if i%2 == 0:
                    installation_row = "EVEN"
                else:    
                    installation_row = "ODD"
                dc = DriveController.objects.create(tracker_controller=tracker, device_id="DC00%s"%i, inclinometer_tilt_angle=Decimal('60.00'), installation_row=installation_row, current_consumption=Decimal('9.00'), actuator_type=actuator_type)
                dc.save()

        else:
            device_ids = []
            for i in range(2):
                actuator_type = "AC"
                if i%2 == 0:
                    installation_row = "EVEN"
                else:    
                    installation_row = "ODD"
                dc = DriveController.objects.create(tracker_controller=tracker, device_id="AC00%s"%i, inclinometer_tilt_angle=Decimal('60.00'), installation_row=installation_row, current_consumption=Decimal('9.00'), actuator_type=actuator_type)
                dc.save()
    
create_roles()
print "Created User Roles\n", UserRole.objects.all().values('name')

create_regions()
print "\nCreated Regions\n", Region.objects.all().values('name')

create_admin_users()
print "\nCreated Admin Users\n", User.objects.filter(role__level=1).values('email')

create_standard_users()
print "\nCreated standatd Users\n", User.objects.filter(role__level=2).values('email')

create_gateways()
print "\nCreated gateways"
create_mcs()
print "\nCreated Masters"
create_tcs()
print "\nCreated Trackers"
create_dcs()
print "\nCreated DriveControllers"
