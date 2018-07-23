"""
Defines url patterns and their respective view functions
"""

from django.conf.urls import include, url
from django.contrib import admin

urlpatterns = [
    # Examples:
    # url(r'^$', 'mytrah.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^$', 'mytrah.login_views.reg_login', name='login'),
    url(r'^iot/', include('trackercontroller.urls')),
    url(r'^admin/login/$', 'mytrah.login_views.reg_login', name='login'),
    url(r'^login/$', 'mytrah.login_views.reg_login', name='login'),
    url(r'^register/$', 'mytrah.login_views.register', name='registration'),
    url(r'^login/proc/$', 'mytrah.login_views.login_proc', name='login_proc'),
    url(r'^logout/$', 'mytrah.login_views.logout_view', name='logout'),

    #Admin
    url(r'^admin/', include(admin.site.urls)),

    #REDIRECT DEFAULT PAGE
    url(r'^.*', 'trackercontroller.views.redirect_default_page',
        name='Default page for unknown urls'),
]
