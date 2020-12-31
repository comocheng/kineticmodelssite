from dal import autocomplete
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
        fields = "__all__"
        widgets = {
            "species": autocomplete.ModelSelect2(
                url="species-autocomplete", attrs={"data-html": True}
            )
        }

    def has_changed(self):
        return True


StoichiometryFormSet = inlineformset_factory(
    Reaction,
    Stoichiometry,
    form=StoichiometryForm,
    can_delete=True,
    fields=("species", "coeff"),
    extra=0,
)
