"""
imports
"""
from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User as user
from django.core.validators import RegexValidator
from datetime import datetime

#pylint: disable=model-missing-unicode

ALPHABETS = RegexValidator(r'^[A-Z]*$', 'Only uppercase alphabets are allowed.')

class UserRole(models.Model):
    """
    Different levels
    Administration - 0
    Super User - 1
    Sourcing User - 2
    Maintenance User - 3
    """
    name = models.CharField(('Role Name'), max_length=30)
    description = models.CharField(('about'), blank=True, null=True, max_length=30)
    responsibilities = models.CharField(('Operations that can be performed'),
                                        blank=True, null=True, max_length=100)
    level = models.SmallIntegerField(('unique id'), unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s' % (self.name)

class Region(models.Model):
    """
    Region Model attributes
    """
    name = models.CharField(('Region Name'), max_length=30)
    description = models.CharField(('about'), blank=True, null=True, max_length=30)
    region_id = models.CharField(('Region ID'), max_length=3, unique=True, validators=[ALPHABETS])
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    city = models.CharField(('City'), blank=True, null=True, max_length=30)
    state = models.CharField(('State'), blank=True, null=True, max_length=30)
    country = models.CharField(('Country'), blank=True, null=True, max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s' % (self.name)

class User(user):
    """
    Django User model extended
    """
    dob = models.DateField("Date of Birth", blank=True, null=True)
    mobile_number = models.CharField(('Mobile Number'), blank=True, null=True, max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    role = models.ForeignKey(UserRole, null=True, blank=True)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, null=True, blank=True, related_name='old_region')
    regions = models.ManyToManyField(Region,  null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.role:
            role_level = self.role.level
            if role_level == 1:
                self.is_superuser = True
        self.is_staff = True
        self.email = self.username
        return super(User, self).save(*args, **kwargs)

    def __unicode__(self):
        return '%s' % (self.username)

class Gateway(models.Model):
    """
    Gateway Model attributes
    """
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    device_id = models.CharField(('device unique id'), max_length=30)
    description = models.CharField(('description if any'), blank=True, null=True, max_length=30)
    active = models.BooleanField(default=False)
    wireless_connectivity = models.BooleanField("wireless connectivity health", default=False)
    wired_connectivity = models.BooleanField("wired connectivity health", default=False)
    inactive_at = models.DateTimeField(blank=True, null=True)
    version = models.CharField(('FW version'), max_length=10, default="0.0")
    fw_status = models.PositiveSmallIntegerField("upgrade status", default=2)

    class Meta:
        """
        Meta
        """
        unique_together = (("region", "device_id",))
        ordering = ['id']

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s' % (self.device_id)

class MasterController(models.Model):
    """
    MasterController Model attributes
    """
    gateway = models.ForeignKey(Gateway, on_delete=models.PROTECT)
    device_id = models.CharField(('device unique id'), max_length=30)
    description = models.CharField(('description if any'), blank=True, null=True, max_length=30)
    active = models.BooleanField(default=False)
    fault_reason = models.CharField(('reason if device is inactive'), max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    altitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    wind_speed = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal(0))
    wind_direction = models.CharField(('device unique id'), max_length=9, blank=True, null=True)
    battery_level = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal(0))
    inactive_at = models.DateTimeField(blank=True, null=True)

    high_wind = models.BooleanField(default=False)
    version = models.CharField(('FW version'), max_length=10, default="0.0")
    fw_status = models.PositiveSmallIntegerField("upgrade status", default=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Meta
        """
        unique_together = (("gateway", "device_id"),)
        ordering = ['device_id']

    def __unicode__(self):
        return '%s' % (self.device_id)

class TrackerController(models.Model):
    """
    TrackerController Model attributes
    """
    STATE_CHOICES = (('ON', 'ON'), ('OFF', 'OFF'),)
    MODE_CHOICES = (('AUTO', 'AUTO'), ('MANUAL', 'MANUAL'), ("OFF", "OFF"))
    master_controller = models.ForeignKey(MasterController, on_delete=models.PROTECT)
    device_id = models.CharField(('device unique id'), max_length=30)
    description = models.CharField(('description if any'), blank=True, null=True, max_length=30)
    active = models.BooleanField(default=False)
    fault_reason = models.CharField(('reason if device is inactive'), max_length=100)
    inner_temperature = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal(0))
    target_angle = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal(0))
    inclinometers_count = models.IntegerField(('number of inclinometers'), default=0)
    maintanance = models.BooleanField(default=False)
    safe_mode = models.BooleanField("Stow position", default=False)
    wireless_connectivity = models.BooleanField("wireless Zigbee health", default=False)
    wired_connectivity = models.BooleanField("wired connectivity RS485 health", default=False)
    reconfigured = models.BooleanField("if device moved to other master", default=False)
    replaced_tracker_id = models.CharField(('device unique id'), max_length=30)
    state_switch = models.CharField(max_length=10, choices=STATE_CHOICES, default="OFF")
    operating_mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="OFF")
    clk_switch = models.BooleanField(default=False)
    aclk_switch = models.BooleanField(default=False)
    inactive_at = models.DateTimeField(blank=True, null=True)
    version = models.CharField(('FW version'), max_length=10, default="0.0")
    fw_status = models.PositiveSmallIntegerField("upgrade status", default=2)
    tracker_status = models.PositiveSmallIntegerField("actuator status", default=2)

    high_wind = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Meta
        """
        unique_together = (("master_controller", "device_id"),)
        ordering = ['device_id']

    def __unicode__(self):
        return '%s' % (self.device_id)

class DriveController(models.Model):
    """
    DriveController Model attributes
    """
    #except tilt_angle all fields are Actuator's fields
    ACTUATOR_CHOICES = (('AC', 'AC'), ('DC', 'DC'),)
    INSTALLATION_ROW_CHOICES = (('ODD', 'ODD'), ('EVEN', 'EVEN'),)
    tracker_controller = models.ForeignKey(TrackerController, on_delete=models.PROTECT)
    device_id = models.CharField(('device unique id'), max_length=30)
    active = models.BooleanField(default=True) #False incase of any issues
    fault_reason = models.CharField(('reason if device is inactive'), max_length=100)
    actuator_type = models.CharField(max_length=5, choices=ACTUATOR_CHOICES, null=True, blank=True)
    installation_row = models.CharField(max_length=5, choices=INSTALLATION_ROW_CHOICES,
                                        null=True, blank=True)
    current_consumption = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal(0))
    power_consumption = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal(0))
    inclinometer_tilt_angle = models.DecimalField(max_digits=6, decimal_places=2,
                                                  default=Decimal(0))
    inclinometer_status = models.PositiveSmallIntegerField("inclinometer status", default=2)
    actuator_status = models.PositiveSmallIntegerField("actuator status", default=2)

    class Meta:
        """
        Meta
        """
        unique_together = (("tracker_controller", "device_id"),)
        ordering = ['device_id']

    def __unicode__(self):
        return '%s' % (self.device_id)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ActionProperties(models.Model):
    """
    Actions done by users shall be logged
    """
    action = models.CharField('Action Performed', max_length=30, blank=True, null=True)
    action_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    email = models.EmailField('email id of user', blank=True, null=True)
    source = models.CharField('Web/PC/controller', max_length=20, blank=True, null=True)
    action_on = models.CharField('db property', max_length=30, blank=True, null=True)

    value_int = models.IntegerField('if type=int', blank=True, null=True)
    value_decimal = models.DecimalField("if type=decimal", max_digits=9,
                                        decimal_places=2, blank=True, null=True)
    value_char = models.CharField("if type=char", max_length=100, blank=True, null=True)
    value_bool = models.NullBooleanField("if type=boolean")

    drive_controller = models.ForeignKey(DriveController, blank=True, null=True)
    tracker_controller = models.ForeignKey(TrackerController, blank=True, null=True)
    master_controller = models.ForeignKey(MasterController, blank=True, null=True)
    gateway = models.ForeignKey(Gateway, blank=True, null=True)
    region = models.ForeignKey(Region, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    message_at = models.DateTimeField(default=datetime.now)

class ControlCommands(models.Model):
    """
    Commands sent by maintenance user will be stored in queue
    """
    command = models.TextField("json to be sent to client via active socket connection")
    publish_pattern = models.TextField('mqtt subscriptions', blank=True, null=True)
    sent = models.BooleanField("To check message sent or not", default=False)
    ack = models.BooleanField("To check message ack ", default=False)
    action = models.CharField("maintenance / stow", max_length=20, blank=True, null=True)
    user = models.ForeignKey(User, blank=True, null=True)
    tracker_controller = models.ForeignKey(TrackerController, blank=True, null=True)
    master_controller = models.ForeignKey(MasterController, blank=True, null=True)
    gateway = models.ForeignKey(Gateway, blank=True, null=True)
    region = models.ForeignKey(Region, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
