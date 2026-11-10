"""
Analysis Forms
"""

from django import forms
from django.db.models import Q

from database.models import KineticModel
from chemked_database.models import ExperimentDataset, ExperimentType, ApparatusKind


class SimulationCreateForm(forms.Form):
    """Form for creating new simulation runs."""
    
    kinetic_model = forms.ModelChoiceField(
        queryset=KineticModel.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Kinetic Model"
    )
    
    datasets = forms.ModelMultipleChoiceField(
        queryset=ExperimentDataset.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Datasets to Evaluate",
        required=True
    )
    
    experiment_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(ExperimentType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Filter by Experiment Type"
    )
    
    apparatus_kind = forms.ChoiceField(
        choices=[('', 'All Apparatus')] + list(ApparatusKind.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Filter by Apparatus"
    )
    
    skip_validation = forms.BooleanField(
        initial=True,
        required=False,
        label="Skip ChemKED validation",
        help_text="Skip schema validation for faster execution"
    )
    
    auto_execute = forms.BooleanField(
        initial=True,
        required=False,
        label="Start simulation automatically",
        help_text="Uncheck to create the run without starting it immediately"
    )
    
    def __init__(self, *args, **kwargs):
        # Allow pre-filtering datasets
        initial_model = kwargs.pop('initial_model', None)
        initial_fuel = kwargs.pop('initial_fuel', None)
        dataset_queryset = kwargs.pop('dataset_queryset', None)
        super().__init__(*args, **kwargs)

        if initial_model:
            self.fields['kinetic_model'].initial = initial_model

        # Filter datasets to ignition delay by default
        if dataset_queryset is None:
            dataset_queryset = ExperimentDataset.objects.filter(
                experiment_type='ignition delay'
            )
        self.fields['datasets'].queryset = dataset_queryset.order_by('chemked_file_path')

        # Pre-select all datasets that contain this fuel species
        if initial_fuel:
            from chemked_database.models import (
                CompositionSpecies, ExperimentDatapoint, CommonProperties,
            )
            from django.db.models import Q

            # Find compositions containing this fuel (by InChI or SMILES)
            inchi = initial_fuel.inchi or ''
            smiles = initial_fuel.smiles or ''
            norm_inchi = inchi.replace('InChI=', '') if inchi else ''

            inchi_variants = [norm_inchi]
            if norm_inchi and not norm_inchi.startswith('InChI='):
                inchi_variants.append(f'InChI={norm_inchi}')

            q = Q(inchi__in=inchi_variants)
            if smiles:
                q |= Q(smiles=smiles)

            comp_ids = set(
                CompositionSpecies.objects.filter(q)
                .values_list('composition_id', flat=True)
            )

            if comp_ids:
                # Datasets via datapoints
                dp_ds_ids = set(
                    ExperimentDatapoint.objects
                    .filter(composition_id__in=comp_ids)
                    .values_list('dataset_id', flat=True)
                )
                # Datasets via common_properties
                cp_ds_ids = set(
                    CommonProperties.objects
                    .filter(composition_id__in=comp_ids)
                    .values_list('dataset_id', flat=True)
                )
                fuel_ds_ids = dp_ds_ids | cp_ds_ids

                # Pre-select these datasets (initial value for the field)
                self.fields['datasets'].initial = list(fuel_ds_ids)

                # Store for context info
                self.fuel_info = {
                    'name': initial_fuel.common_name or initial_fuel.smiles,
                    'dataset_count': len(fuel_ds_ids),
                }


class DatasetFilterForm(forms.Form):
    """Form for filtering datasets in the selection interface."""
    
    experiment_type = forms.ChoiceField(
        choices=[('', 'All')] + list(ExperimentType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    apparatus_kind = forms.ChoiceField(
        choices=[('', 'All')] + list(ApparatusKind.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    fuel_species = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Search by fuel name, SMILES, or InChI...'
        })
    )
    
    min_temperature = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Min T (K)'
        })
    )
    
    max_temperature = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Max T (K)'
        })
    )


class SpeciesMappingForm(forms.Form):
    """Form for manually overriding species mapping."""
    
    dataset_species_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True})
    )
    
    model_species_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    override_reason = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Reason for override...'
        })
    )


# ---------------------------------------------------------------------------
# Inline species-mapping review (pre-simulation)
# ---------------------------------------------------------------------------

class SpeciesMappingReviewForm(forms.Form):
    """
    One row per species in the mapping table shown before launching a run.

    Hidden fields carry the auto-matched values; the user can edit
    ``model_species_name`` to override.
    """
    dataset_species_name = forms.CharField(
        max_length=200,
        widget=forms.HiddenInput(),
    )
    original_model_species_name = forms.CharField(
        max_length=200,
        widget=forms.HiddenInput(),
        required=False,
    )
    model_species_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
        }),
    )
    confidence = forms.FloatField(
        widget=forms.HiddenInput(),
        required=False,
    )
    mapping_method = forms.CharField(
        max_length=30,
        widget=forms.HiddenInput(),
        required=False,
    )
    # True when the user edits the auto-matched value
    is_override = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
    )
    override_reason = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Reason (optional)...',
        }),
    )


from django.forms import formset_factory

SpeciesMappingReviewFormSet = formset_factory(
    SpeciesMappingReviewForm,
    extra=0,
)
