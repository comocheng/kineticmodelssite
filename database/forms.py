from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms import inlineformset_factory

from .models import Source, Author, Authorship, KineticModel


class RegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ("email",)


# =============================================================================
# Source Forms
# =============================================================================

class AuthorForm(forms.ModelForm):
    """Form for creating/editing an Author."""
    
    class Meta:
        model = Author
        fields = ['firstname', 'lastname']
        widgets = {
            'firstname': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'First name'
            }),
            'lastname': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Last name'
            }),
        }


class AuthorshipForm(forms.ModelForm):
    """Form for managing author-source relationships."""
    
    # Allow creating new authors inline
    author_firstname = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'First name'
        })
    )
    author_lastname = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Last name'
        })
    )
    
    class Meta:
        model = Authorship
        fields = ['author', 'order']
        widgets = {
            'author': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'order': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'style': 'width: 70px;',
                'min': 1
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['author'].required = False
        self.fields['author'].queryset = Author.objects.order_by('lastname', 'firstname')


class SourceForm(forms.ModelForm):
    """Form for creating/editing a Source (publication)."""
    
    class Meta:
        model = Source
        fields = [
            'doi', 'prime_id', 'source_title', 'publication_year',
            'journal_name', 'journal_volume_number', 'page_numbers'
        ]
        widgets = {
            'doi': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 10.1021/acs.jpca.1c00234'
            }),
            'prime_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., b00000001'
            }),
            'source_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Article title'
            }),
            'publication_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'YYYY',
                'style': 'width: 100px;'
            }),
            'journal_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Journal of Physical Chemistry A'
            }),
            'journal_volume_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 125',
                'style': 'width: 100px;'
            }),
            'page_numbers': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 1234-1250'
            }),
        }
        labels = {
            'doi': 'DOI',
            'prime_id': 'PrIMe ID',
            'source_title': 'Article Title',
            'publication_year': 'Year',
            'journal_name': 'Journal',
            'journal_volume_number': 'Volume',
            'page_numbers': 'Pages',
        }


# Inline formset for managing authors within a source
AuthorshipFormSet = inlineformset_factory(
    Source,
    Authorship,
    form=AuthorshipForm,
    extra=3,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


# =============================================================================
# KineticModel Forms
# =============================================================================

class KineticModelForm(forms.ModelForm):
    """Form for creating/editing a KineticModel."""
    
    class Meta:
        model = KineticModel
        fields = [
            'model_name', 'prime_id', 'source', 'info',
            'chemkin_reactions_file', 'chemkin_thermo_file', 'chemkin_transport_file'
        ]
        widgets = {
            'model_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., GRI-Mech 3.0'
            }),
            'prime_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., m00000001'
            }),
            'source': forms.Select(attrs={
                'class': 'form-select'
            }),
            'info': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional information about this model...'
            }),
            'chemkin_reactions_file': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),
            'chemkin_thermo_file': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),
            'chemkin_transport_file': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'model_name': 'Model Name',
            'prime_id': 'PrIMe ID',
            'source': 'Source Publication',
            'info': 'Description',
            'chemkin_reactions_file': 'CHEMKIN Reactions File',
            'chemkin_thermo_file': 'CHEMKIN Thermo File',
            'chemkin_transport_file': 'CHEMKIN Transport File',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source'].queryset = Source.objects.order_by('-publication_year', 'source_title')
        self.fields['source'].required = False
