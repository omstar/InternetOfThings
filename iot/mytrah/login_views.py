"""
Django imports
"""
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import AnonymousUser
from django.views.decorators.cache import cache_control

#from forms import LoginForm, RegistrationForm
from mytrah.forms import LoginForm, RegistrationForm
from trackercontroller.models import User

#pylint: disable=broad-except

def reg_login(request):
    """
    If role level = 1 -> redirect to admin flow
    Else redirect to standard users flow
    Using custom login url and template instead django default
    """

    if request.user.is_authenticated():
        user = User.objects.get(username=request.user.email)
        if user.role.level == 1: #admin user
            redirect_url = '/admin/'
        else:
            redirect_url = '/iot/dashboard/'
        response = HttpResponseRedirect(redirect_url)
        return response

    elif request.path == '/admin/login/':
        return HttpResponseRedirect('/login/')

    return render_to_response('login.html')


@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
def login_proc(request):
    """
    Validate login form and autenticate
    Redirect to admin / standard user flow based on their role level
    Displays form errors if validation fails
    """

    logout(request)

    data = request.POST.copy()
    source = 'web'

    email = data.get('username', '')
    password = data.get('password', '')
    if not email or not password:
        return HttpResponseRedirect('/login/')

    if source == 'web':
        form_data = request.POST.copy()
        form = LoginForm(form_data)
        errors = form.errors
        if errors:
            return render_to_response('login.html', {'form': form, 'username':email})
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return render_to_response('login.html', {'form': form})

    user = authenticate(username=email, password=password)

    login(request, user)
    if user.email:
        user = User.objects.get(username=user.email)
        if not user.role:
            redirect_url = '/login/'
        elif user.role.level == 1: #admin user
            redirect_url = '/admin/'
        else:
            redirect_url = '/iot/dashboard/'

    response = HttpResponseRedirect(redirect_url)
    #response.set_cookie("generate_token", True)
    return response

def logout_view(request):
    """
    Logout and redirect to login url
    """
    logout(request)
    return HttpResponseRedirect('/login/')
    # Redirect to a success page.

@csrf_exempt
@cache_control(no_store=True, no_cache=True, must_revalidate=True,)
def register(request):
    """
    Register a new user
    Which is not being used, since users being created by admin users
    No registration page available
    """
    form_data = request.POST.copy()
    form = RegistrationForm(form_data)
    errors = form.errors
    print "Errors in registration part", errors
    if errors:
        return render_to_response('login.html', {'form': form})

    # logout the existing user
    if isinstance(request.user, AnonymousUser):
        user = None
    else:
        user = request.user
        logout(request)

    email = request.POST['register_email']
    password = request.POST['register_password']

    try:
        user = User(username=email)
        user.set_password(password)
        user.email = email
        user.first_name = email.split('@')[0]
        user.save()
    except Exception:
        return render_to_response('login.html', {'form': form})
    response = render_to_response('login.html',
                                  {'registration_status': "Registered successfully! \
                                    Now you can login with your credentials!"
                                  })
    #text = '''Hi,\n\nYou\'ve successfully registered !.\'''
    #send_mail('donotreply@embitel.com', 'prakash.p@embitel.com',
    #           'Registration Confirmation!', text, [], [])
    return response
