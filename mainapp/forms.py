from django import forms
from django.core.exceptions import ValidationError
from .models import File
from django.core.validators import RegexValidator
from . import tools


class CreateClass(forms.Form):
    def no_duplicate(chosen_name):
        if tools.class_exists(chosen_name):
            raise ValidationError("Class with this name already exists")

    name = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "cols": 30,
                "rows": 1,
                "style": "border-radius: 7px; border-color: black;",
            }
        ),
        label="Class name:",
        max_length=50,
        min_length=10,
        required=True,
        # https://stackoverflow.com/questions/17165147/how-can-i-make-a-django-form-field-contain-only-alphanumeric-characters
        validators=[
            RegexValidator(
                r"^[0-9a-zA-Z ]*$", "Only alphanumeric characters are allowed."
            ),
            no_duplicate,
        ],
    )
    description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "cols": 30,
                "rows": 4,
                "style": "border-radius: 7px; border-color: black;",
            }
        ),
        label="Class description:",
        max_length=300,
        min_length=10,
        required=True,
    )


class FileForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ("title", "pdf")
