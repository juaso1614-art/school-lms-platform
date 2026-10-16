from django import forms

from .models import SchoolStaffProfile, User


class CreateAccountForm(forms.Form):
    first_name = forms.CharField(max_length=100, strip=True)
    last_name = forms.CharField(max_length=100, strip=True)
    email = forms.EmailField(max_length=254)
    password = forms.CharField(
        min_length=8,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirm_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        label="Confirm password",
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already exists with this email.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data


class SchoolStaffProfileForm(forms.ModelForm):
    class Meta:
        model = SchoolStaffProfile
        fields = (
            "role",
            "full_name",
            "email",
            "phone",
            "department",
            "campus",
            "staff_id",
        )
