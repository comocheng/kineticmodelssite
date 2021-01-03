from dal import autocomplete
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.forms import inlineformset_factory

from database.models import (
    Reaction,
    Stoichiometry,
    KineticModel,
    SpeciesName,
    KineticsComment,
    ThermoComment,
    TransportComment,
)


class RegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ("email",)


class RevisionForm(forms.ModelForm):
    def has_changed(self):
        return True


class StoichiometryForm(RevisionForm):
    class Meta:
        model = Stoichiometry
        fields = "__all__"
        widgets = {
            "species": autocomplete.ModelSelect2(
                url="species-autocomplete", attrs={"data-html": True}
            )
        }


StoichiometryFormSet = inlineformset_factory(
    Reaction,
    Stoichiometry,
    form=StoichiometryForm,
    can_delete=True,
    fields=("species", "coeff"),
    extra=0,
)


class SpeciesNameForm(RevisionForm):
    class Meta:
        model = SpeciesName
        fields = "__all__"
        widgets = {
            "species": autocomplete.ModelSelect2(
                url="species-autocomplete", attrs={"data-html": True}
            )
        }


SpeciesNameFormSet = inlineformset_factory(
    KineticModel,
    SpeciesName,
    form=SpeciesNameForm,
    fields=("species", "name"),
    extra=0,
)


class KineticsCommentForm(RevisionForm):
    class Meta:
        model = KineticsComment
        fields = "__all__"
        widgets = {
            "kinetics": autocomplete.ModelSelect2(
                url="kinetics-autocomplete", attrs={"data-html": True}
            )
        }


KineticsCommentFormSet = inlineformset_factory(
    KineticModel,
    KineticsComment,
    form=KineticsCommentForm,
    fields=("kinetics", "comment"),
    extra=0,
)


class ThermoCommentForm(RevisionForm):
    class Meta:
        model = ThermoComment
        fields = "__all__"
        widgets = {
            "thermo": autocomplete.ModelSelect2(
                url="thermo-autocomplete", attrs={"data-html": True}
            )
        }


ThermoCommentFormSet = inlineformset_factory(
    KineticModel,
    ThermoComment,
    form=ThermoCommentForm,
    fields=("thermo", "comment"),
    extra=0,
)


class TransportCommentForm(RevisionForm):
    class Meta:
        model = TransportComment
        fields = "__all__"
        widgets = {
            "transport": autocomplete.ModelSelect2(
                url="transport-autocomplete", attrs={"data-html": True}
            )
        }


TransportCommentFormSet = inlineformset_factory(
    KineticModel,
    TransportComment,
    form=TransportCommentForm,
    fields=("transport", "comment"),
    extra=0,
)
