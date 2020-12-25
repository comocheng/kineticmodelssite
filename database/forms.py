from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.forms import inlineformset_factory

from database.models import Reaction, Stoichiometry


class RegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ("email",)


class StoichiometryForm(forms.ModelForm):
    class Meta:
        model = Stoichiometry
        exclude = []


StoichiometryFormSet = inlineformset_factory(
    Reaction, Stoichiometry, form=StoichiometryForm, can_delete=True
)
