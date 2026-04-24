from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile, Role


class CustomUserCreationForm(UserCreationForm):
    """Custom user registration form"""

    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    department = forms.CharField(max_length=100, required=False)
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=False)
    registration_notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="Optional: Tell us why you need access to the recipe system",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if field_name != "registration_notes":
                field.widget.attrs["placeholder"] = field.label

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]

        if commit:
            user.save()
            # Update the user profile
            profile = user.profile
            profile.phone_number = self.cleaned_data.get("phone_number", "")
            profile.department = self.cleaned_data.get("department", "")
            profile.role = self.cleaned_data.get("role")
            profile.registration_notes = self.cleaned_data.get("registration_notes", "")
            profile.save()

        return user


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["placeholder"] = field.label


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile"""

    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = UserProfile
        fields = ["phone_number", "department", "role"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"

        # Populate user fields if instance exists
        if self.instance and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)

        if commit:
            # Update user fields
            user = profile.user
            user.first_name = self.cleaned_data["first_name"]
            user.last_name = self.cleaned_data["last_name"]
            user.email = self.cleaned_data["email"]
            user.save()
            profile.save()

        return profile


class RoleForm(forms.ModelForm):
    """Form for creating/editing roles"""

    class Meta:
        model = Role
        fields = ["name", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class AdminPasswordChangeForm(forms.Form):
    """Form for admin to change user password"""

    new_password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        help_text="Le mot de passe doit contenir au moins 8 caractères.",
    )
    new_password2 = forms.CharField(
        label="Confirmation du mot de passe",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        help_text="Entrez le même mot de passe pour confirmation.",
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")

        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError(
                    "Les deux mots de passe ne correspondent pas."
                )
            if len(password1) < 8:
                raise forms.ValidationError(
                    "Le mot de passe doit contenir au moins 8 caractères."
                )

        return cleaned_data
