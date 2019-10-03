from django import forms
from .models import Species

class SpeciesForm(forms.ModelForm):
    
    class Meta:
        model = Species
        fields = "__all__"
