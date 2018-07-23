"""
WSGI config for mytrah project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

import os
import sys
import site

sys.stdout = sys.stderr

# Project root
root = '/var/www/www.mytrah.com/iot/'
sys.path.insert(0, root)
#pylint: disable=invalid-name

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mytrah.settings")

# Packages from virtualenv
activate_this = '/var/www/www.mytrah.com/venv/stage/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

# Set environmental variable for Django and fire WSGI handler 
os.environ['DJANGO_SETTINGS_MODULE'] = 'mytrah.settings'
#os.environ['DJANGO_CONF'] = 'conf.stage'
os.environ["CELERY_LOADER"] = "django"
#os.environ['HTTPS'] = "on"

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
