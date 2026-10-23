"""
ChemKED Database Forms

Multi-step forms for creating and editing ChemKED datasets.
Inspired by ChemKED-gui structure with Django form handling.
"""

from django import forms
from django.forms import formset_factory, inlineformset_factory
from django.core.validators import MinValueValidator

from .models import (
    ExperimentDataset,
    ExperimentDatapoint,
    IgnitionDelayDatapoint,
    LaminarBurningVelocityMeasurementDatapoint,
    RateCoefficientDatapoint,
    ConcentrationTimeProfileMeasurementDatapoint,
    JetStirredReactorMeasurementDatapoint,
    OutletConcentrationMeasurementDatapoint,
    BurnerStabilizedFlameSpeciationMeasurementDatapoint,
    CommonProperties,
    Composition,
    CompositionSpecies,
    Apparatus,
    FileAuthor,
    ReferenceAuthor,
    ApparatusKind,
    ApparatusMode,
    ExperimentType,
    CompositionKind,
    IgnitionTarget,
    IgnitionType,
    UncertaintyType,
    MeasurementType,
    TimeShiftType,
)


# =============================================================================
# File Metadata Forms
# =============================================================================

class FileAuthorForm(forms.Form):
    """Form for a single file author."""
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Author name'
        })
    )
    orcid = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ORCID (e.g., 0000-0003-4425-7097)'
        })
    )


FileAuthorFormSet = formset_factory(FileAuthorForm, extra=1, min_num=1, validate_min=True)


class FileMetadataForm(forms.Form):
    """Form for ChemKED file metadata."""
    file_version = forms.IntegerField(
        initial=0,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'File version (e.g., 0)'
        })
    )
    chemked_version = forms.CharField(
        max_length=20,
        initial='0.4.1',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ChemKED version'
        })
    )


# =============================================================================
# Reference Forms
# =============================================================================

class ReferenceAuthorForm(forms.Form):
    """Form for a single reference/paper author."""
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Author name'
        })
    )
    orcid = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ORCID (optional)'
        })
    )


ReferenceAuthorFormSet = formset_factory(ReferenceAuthorForm, extra=1, min_num=1, validate_min=True)


class ReferenceForm(forms.Form):
    """Form for literature reference information."""
    doi = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'DOI (e.g., 10.1016/j.combustflame.2004.08.015)'
        })
    )
    journal = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Journal name'
        })
    )
    year = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Publication year'
        })
    )
    volume = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Volume number'
        })
    )
    pages = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Page range (e.g., 300-311)'
        })
    )
    detail = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Additional details about data source'
        })
    )


# =============================================================================
# Experiment & Apparatus Forms
# =============================================================================

class ExperimentForm(forms.Form):
    """Form for experiment type and apparatus."""
    experiment_type = forms.ChoiceField(
        choices=ExperimentType.choices,
        initial=ExperimentType.IGNITION_DELAY,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_experiment_type'})
    )
    apparatus_kind = forms.ChoiceField(
        choices=ApparatusKind.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    apparatus_mode = forms.ChoiceField(
        choices=[('', '-- Select --')] + list(ApparatusMode.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    apparatus_institution = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Institution (e.g., Stanford University)'
        })
    )
    apparatus_facility = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Facility name (e.g., low pressure shock tube)'
        })
    )


# =============================================================================
# Common Properties Forms
# =============================================================================

class IgnitionInfoForm(forms.Form):
    """Form for ignition detection parameters."""
    ignition_target = forms.ChoiceField(
        choices=[('', '-- Select --')] + list(IgnitionTarget.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    ignition_type = forms.ChoiceField(
        choices=[('', '-- Select --')] + list(IgnitionType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class CompositionSpeciesForm(forms.Form):
    """Form for a single species in composition."""
    species_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Species name (e.g., nC7H16)'
        })
    )
    inchi = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'InChI (e.g., 1S/C7H16/c1-3-5-7-6-4-2/h3-7H2,1-2H3)'
        })
    )
    smiles = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'SMILES (optional)'
        })
    )
    amount = forms.FloatField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Amount (e.g., 0.01874)',
            'step': 'any'
        })
    )


CompositionSpeciesFormSet = formset_factory(
    CompositionSpeciesForm, extra=1, min_num=1, validate_min=True
)


class CommonPropertiesForm(forms.Form):
    """Form for properties common to all datapoints."""
    composition_kind = forms.ChoiceField(
        choices=CompositionKind.choices,
        initial=CompositionKind.MOLE_FRACTION,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # Pressure (optional - if same for all datapoints)
    pressure = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Pressure with units (e.g., 1.5 bar) - leave empty if varies'
        })
    )
    # Temperature (optional - if same for all datapoints)
    temperature = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Temperature with units (e.g., 298 K) - leave empty if varies'
        })
    )
    # Pressure rise rate (for shock tubes)
    pressure_rise = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Pressure rise rate (e.g., 0.03 1/ms) - optional'
        })
    )
    # Equivalence ratio (common for all datapoints)
    equivalence_ratio = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Equivalence ratio (e.g., 1.0)',
            'step': 'any'
        })
    )
    # Reactor volume (JSR, flow reactors)
    reactor_volume = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Reactor volume with units (e.g., 85 cm3)'
        })
    )
    # Residence time (JSR, outlet concentration, flow reactors)
    residence_time = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Residence time with units (e.g., 2.0 s)'
        })
    )
    # Flow rate (BSFS experiments)
    flow_rate = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mass flow rate with units (e.g., 0.04 kg m-2 s-1)'
        })
    )


# =============================================================================
# Datapoint Forms
# =============================================================================

class DatapointForm(forms.Form):
    """Form for a single experimental datapoint."""
    temperature = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Temperature with units (e.g., 1249 K)'
        })
    )
    temperature_uncertainty = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Uncertainty value',
            'step': 'any'
        })
    )
    temperature_uncertainty_type = forms.ChoiceField(
        choices=[('', '-- None --')] + list(UncertaintyType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    pressure = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Pressure with units (e.g., 1.97 bar)'
        })
    )
    pressure_uncertainty = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Uncertainty value',
            'step': 'any'
        })
    )
    pressure_uncertainty_type = forms.ChoiceField(
        choices=[('', '-- None --')] + list(UncertaintyType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    equivalence_ratio = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Equivalence ratio (e.g., 1.0)',
            'step': 'any'
        })
    )


DatapointFormSet = formset_factory(DatapointForm, extra=1, min_num=1, validate_min=True)


class IgnitionDelayForm(forms.Form):
    """Form for ignition delay specific data."""
    ignition_delay = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ignition delay with units (e.g., 529 us)'
        })
    )
    ignition_delay_uncertainty = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Uncertainty value',
            'step': 'any'
        })
    )
    ignition_delay_uncertainty_type = forms.ChoiceField(
        choices=[('', '-- None --')] + list(UncertaintyType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # Override ignition target/type per datapoint (usually inherits from common)
    ignition_target_override = forms.ChoiceField(
        choices=[('', '-- Use Common --')] + list(IgnitionTarget.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    ignition_type_override = forms.ChoiceField(
        choices=[('', '-- Use Common --')] + list(IgnitionType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


IgnitionDelayFormSet = formset_factory(IgnitionDelayForm, extra=1, min_num=1, validate_min=True)


class LaminarBurningVelocityForm(forms.Form):
    """Form for laminar burning velocity specific data."""
    laminar_burning_velocity = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Burning velocity with units (e.g., 0.35 m/s)'
        })
    )
    laminar_burning_velocity_uncertainty = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Uncertainty value',
            'step': 'any'
        })
    )
    laminar_burning_velocity_uncertainty_type = forms.ChoiceField(
        choices=[('', '-- None --')] + list(UncertaintyType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


LaminarBurningVelocityFormSet = formset_factory(LaminarBurningVelocityForm, extra=1, min_num=1, validate_min=True)


class RateCoefficientForm(forms.Form):
    """Form for rate coefficient specific data."""
    measurement_type = forms.ChoiceField(
        choices=MeasurementType.choices,
        initial=MeasurementType.RATE_COEFFICIENT,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    rate_coefficient = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rate coefficient with units (e.g., 1.2e10 cm3 mol-1 s-1)'
        })
    )
    rate_coefficient_uncertainty = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Uncertainty value',
            'step': 'any'
        })
    )
    rate_coefficient_uncertainty_type = forms.ChoiceField(
        choices=[('', '-- None --')] + list(UncertaintyType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    reaction = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Reaction equation (e.g., NO2 + HO2 = HNO2 + O2)'
        })
    )
    reaction_order = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Overall reaction order'
        })
    )
    bulk_gas = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bulk gas (e.g., N2, Ar)'
        })
    )
    method = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Method (e.g., ab initio CBS-QB3)'
        })
    )


RateCoefficientFormSet = formset_factory(RateCoefficientForm, extra=1, min_num=1, validate_min=True)


class JetStirredReactorForm(forms.Form):
    """Form for jet stirred reactor specific data per datapoint."""
    environment_temperature = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Environment temperature with units (e.g., 900 K)'
        })
    )


JetStirredReactorFormSet = formset_factory(JetStirredReactorForm, extra=1, min_num=1, validate_min=True)


class OutletConcentrationForm(forms.Form):
    """Form for outlet concentration measurement specific data per datapoint."""
    residence_time = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Per-datapoint residence time with units (e.g., 2.0 s)'
        })
    )
    volumetric_flow = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Volumetric flow at reference state with units (e.g., 1.5e-5 m3/s)'
        })
    )


OutletConcentrationFormSet = formset_factory(OutletConcentrationForm, extra=1, min_num=1, validate_min=True)


class ConcentrationTimeProfileForm(forms.Form):
    """Form for concentration time profile measurement specific data per datapoint."""
    tracked_species_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tracked species name (e.g., OH)'
        })
    )
    quantity_units = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Concentration units (e.g., ppm, mole fraction)'
        })
    )
    time_units = forms.CharField(
        max_length=20,
        initial='s',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Time units (e.g., s, ms, us)'
        })
    )
    values_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Time-value pairs, one per line:\ntime1, value1\ntime2, value2\n...'
        }),
        help_text='Enter time-value pairs separated by commas, one pair per line'
    )
    uncertainty_type = forms.ChoiceField(
        choices=[('', '-- None --')] + list(UncertaintyType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    uncertainty_value = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Uncertainty value',
            'step': 'any'
        })
    )
    timeshift_target = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Time shift reference species (optional)'
        })
    )
    timeshift_type = forms.ChoiceField(
        choices=[('', '-- None --')] + list(TimeShiftType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    timeshift_amount = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Time shift amount with units (e.g., 10 us)'
        })
    )


ConcentrationTimeProfileFormSet = formset_factory(ConcentrationTimeProfileForm, extra=1, min_num=1, validate_min=True)


class BurnerStabilizedFlameSpeciationForm(forms.Form):
    """Form for burner stabilized flame speciation measurement specific data per datapoint."""
    distance = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Distance from burner with units (e.g., 5.0 mm)'
        })
    )
    flow_rate = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mass flow rate with units (e.g., 0.04 kg m-2 s-1)'
        })
    )


BurnerStabilizedFlameSpeciationFormSet = formset_factory(BurnerStabilizedFlameSpeciationForm, extra=1, min_num=1, validate_min=True)


# =============================================================================
# YAML Upload Form
# =============================================================================

class MultipleFileInput(forms.ClearableFileInput):
    """Custom widget that allows multiple file selection."""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Custom field that handles multiple file uploads."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class ChemKEDUploadForm(forms.Form):
    """Form for uploading existing ChemKED YAML or ReSpecTh XML files."""
    data_file = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': '.yaml,.yml,.xml',
        }),
        help_text='Upload ChemKED YAML or ReSpecTh XML files (you can select multiple files)'
    )
    file_format = forms.ChoiceField(
        choices=[
            ('auto', 'Auto-detect'),
            ('yaml', 'ChemKED YAML'),
            ('xml', 'ReSpecTh XML'),
        ],
        initial='auto',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='File format (auto-detects based on extension if not specified)'
    )
    validate_on_upload = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Validate the file against ChemKED schema before importing'
    )
    file_author = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your name'
        }),
        help_text='File author name for attribution'
    )
    file_author_orcid = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0000-0000-0000-0000 (optional)'
        }),
        help_text='ORCID for the file author (optional)'
    )

    # ---- Contribution / GitHub PR options ----
    contribute_to_github = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Also create a GitHub pull request for community review and CI validation'
    )
    run_pyteck = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Request PyTeCK simulation validation against a kinetic model in CI'
    )
    github_username = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. octocat (optional)'
        }),
        help_text='Optional: your GitHub username for direct attribution on the PR'
    )
    contribution_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Brief description of this data contribution (optional)'
        }),
        help_text='Optional note for the PR description'
    )


class ReSpecThPreviewForm(forms.Form):
    """Form for previewing and editing ReSpecTh import details before confirmation."""
    dataset_name = forms.CharField(
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Dataset name'
        }),
        help_text='Human-readable name for this dataset (auto-generated, but you can modify it)'
    )
    original_filename = forms.CharField(
        widget=forms.HiddenInput()
    )
    temp_file_path = forms.CharField(
        widget=forms.HiddenInput()
    )
    file_type = forms.CharField(
        widget=forms.HiddenInput()
    )
    file_author = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.HiddenInput()
    )
    file_author_orcid = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.HiddenInput()
    )


# =============================================================================
# Export Form
# =============================================================================

class ExportOptionsForm(forms.Form):
    """Form for export options when downloading datasets."""
    format_choice = forms.ChoiceField(
        choices=[
            ('yaml', 'ChemKED YAML'),
            ('xml', 'ReSpecTh XML'),
            ('csv', 'CSV (datapoints only)'),
        ],
        initial='yaml',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    include_uncertainties = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
