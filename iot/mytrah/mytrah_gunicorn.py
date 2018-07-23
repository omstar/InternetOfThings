workers = 9

bind = '127.0.0.1:8005'

pidfile = '/var/run/gunicorn-mytrah.pid'

user = 'root'

#daemon = True

errorlog = '/var/log/gunicorn/error-mytrah.log'

accesslog = '/var/log/gunicorn/access-mytrah.log'

keepalive = 5

proc_name = 'gunicorn-mytrah'

loglevel = 'info'
