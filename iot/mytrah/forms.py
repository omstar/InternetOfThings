"""
Login and Registration forms to validate user forms
"""
#from django.contrib.auth.models import User
from trackercontroller.models import User
from django import forms
from django.core.exceptions import ObjectDoesNotExist

#pylint: disable=invalid-name

class LoginForm(forms.Form):
    """
    Validate login form and report errors if any
    """
    username = forms.EmailField(max_length=75, required=True)
    password = forms.CharField(widget=forms.PasswordInput(render_value=False),
                               max_length=100, required=True)

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if not username or not password:
            return self.cleaned_data
        try:
            user = User.objects.get(email=username)
            if user.check_password(password):
                pass
            else:
                user = None
        except ObjectDoesNotExist:
            user = None

        if user is None:
            self._errors["username"] = self.error_class(["Incorrect email/password!"])

        else:
            if not user.is_active:
                self._errors["username"] = self.error_class(["Inactive Account!"])
            elif not user.role:
                self._errors["username"] = self.error_class(
                    ["User Role has not been assigned! Please Contact Administrator!"])
            elif user.role.level in [3, 4] and not user.regions.all():
                self._errors["username"] = self.error_class(
                    ["User Region has not been assigned! Please Contact Administrator!"])

        #user = authenticate(email=email, password=password)
        return self.cleaned_data

class RegistrationForm(forms.Form):
    """
    forms used for registration.
    """
    register_email = forms.EmailField(label="register_email", max_length=60, required=True)
    register_password = forms.CharField(label="register_password", max_length=15, required=True,
                                        widget=forms.PasswordInput)
    confirm_password = forms.CharField(label="confirm_password", max_length=15, required=True,
                                       widget=forms.PasswordInput)
    # You can add a function to clean password (if any password restrictions)
    def clean_register_email(self):
        """
        clean data by performing validations
        """
        email = self.cleaned_data.get('register_email')
        try:
            User.objects.get(email=email)
            self._errors["register_email"] = self.error_class(["Account with this email id\
                                                                already exists!"])
        except User.DoesNotExist:
            pass
        return self.cleaned_data

    def clean_confirm_password(self):
        """
        clean data by performing password validations
        """
        password1 = self.cleaned_data.get('register_password')
        password2 = self.cleaned_data.get('confirm_password')
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError(("The two password fields didn't match."))
        return password2
