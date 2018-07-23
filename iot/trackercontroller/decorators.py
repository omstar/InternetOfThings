"""
define decorators
"""
from django.http import HttpResponseRedirect
from trackercontroller.models import User

def is_standard_user(view_func):
    """
    Check user role and redirect accordingly
    """
    def _wrapped_view_func(request, *args, **kwargs):
        if request.user.email:
            user = User.objects.get(email=request.user.email)
            if user.role.level == 1:
                return HttpResponseRedirect('/admin/')
            else:
                return view_func(request, *args, **kwargs)
        else:
            return HttpResponseRedirect('/login/')
    return _wrapped_view_func
