#!/usr/bin/env python
# -*- coding: utf-8 -*-

################################################################################
#
#	RMG Website - A Django-powered website for Reaction Mechanism Generator
#
#	Copyright (c) 2011 Prof. William H. Green (whgreen@mit.edu) and the
#	RMG Team (rmg_dev@mit.edu)
#
#	Permission is hereby granted, free of charge, to any person obtaining a
#	copy of this software and associated documentation files (the 'Software'),
#	to deal in the Software without restriction, including without limitation
#	the rights to use, copy, modify, merge, publish, distribute, sublicense,
#	and/or sell copies of the Software, and to permit persons to whom the
#	Software is furnished to do so, subject to the following conditions:
#
#	The above copyright notice and this permission notice shall be included in
#	all copies or substantial portions of the Software.
#
#	THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#	AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#	LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#	FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#	DEALINGS IN THE SOFTWARE.
#
################################################################################

"""
This module defines the Django forms used by the kineticsmodels app.
"""

from django import forms
from models import KineticModel, Source, Species, Reaction, Author
from dal import autocomplete
################################################################################

# Form for Editing Sources
class EditSourceForm(forms.ModelForm):
    """
    A Django form for editing a Source.
    """
    class Meta:
        model = Source
        fields = ('bPrimeID', 'publicationYear', 'sourceTitle', 'journalName',
                     'journalVolumeNumber', 'pageNumbers', 'doi', 'authors')
        widgets =  {
            'authors': autocomplete.ModelSelect2Multiple(
                                                    url='authorAutocomplete')
        }


# For for editing a Species
class EditSpeciesForm(forms.ModelForm):
    """
    Django Form template for editing a Species
    """
    class Meta:
        model = Species
        exclude = ()

# For for editing a Model
class EditKineticModelMetaDataForm(forms.ModelForm):
    """
    Django Form template for editing a Model
    """
    class Meta:
        model = KineticModel
    #    exclude = ('kinetics', 'thermo', 'transport')
        fields = ('source', 'mPrimeID', 'modelName', 'additionalInfo')
        widgets =  {
            'source': autocomplete.ModelSelect2(url='sourceAutocomplete')
        }


class EditKineticModelFileForm(forms.ModelForm):
    """
    Django Form template for editing a Model
    """
    class Meta:
        model = KineticModel
    #    exclude = ('kinetics', 'thermo', 'transport')
        fields = ('chemkinReactionsFile', 'chemkinThermoFile', 
                                                    'chemkinTransportFile')


class UploadKineticModelForm(forms.ModelForm):
    """
    A Django form for uploading a kinetic model.
    """
    class Meta:
        model = KineticModel
        fields = ('chemkinReactionsFile', 'chemkinThermoFile', 
                                                    'chemkinTransportFile')


# For for editing a Reaction
class EditReactionForm(forms.ModelForm):
    """
    Django Form template for editing a Reaction
    """
    class Meta:
        model = Reaction
        exclude = ()        
################################################################################

################################################################################


class FileEditorForm(forms.Form):
    "For editing generic text files"
    content = forms.CharField(label="File content", widget=forms.Textarea(attrs={'rows': 30, 'cols': 80}))


# Form for searching Species
class SpeciesSearchForm(forms.Form):
    """
    A django form for searching through a Species
    """
    # class Meta:
    #     model = Species
    #     fields = ('formula', 'sPrimeID', 'inchi', 'cas')

    sPrimeID = forms.CharField(label = 'PrIMe ID', max_length=9,
                                             strip = True, required=False)
    formula = forms.CharField(label = 'Formula', max_length=50,
                                             strip = True, required=False)
    inchi = forms.CharField(label = 'InChI', max_length=500,
                                             strip = True, required=False)
    cas = forms.CharField(label = 'CAS Registry Number', max_length=400,
                                             strip = True, required=False)    


class SourceSearchForm(forms.ModelForm):

    class Meta:
        model = Source
        fields = ('bPrimeID', 'publicationYear', 'sourceTitle', 'journalName',
                     'journalVolumeNumber', 'pageNumbers', 'doi', 'authors')
        widgets = {
            'authors': autocomplete.ModelSelect2Multiple(
                                                url='authorAutocomplete')
        }


class KineticModelSearchForm(forms.Form):
    model_name = forms.CharField(label="Model Name", max_length=50, required=False)
    m_prime_ID = forms.CharField(label="PrIMe ID",    max_length=9,  required=False)
    source = forms.CharField(label="Source",        max_length=50, required=False)




#Form for searching Reactions
class ReactionSearchForm(forms.Form):
    """
    A django form for searching through a Reaction
    """

    rPrimeID = forms.CharField(label = 'Reaction PrIMe ID', max_length=9,
                                                 strip = True, required=False)

    reactants = forms.ModelMultipleChoiceField(label="Reactant(s)",
        queryset=Species.objects.all(), required=False,
        widget=autocomplete.ModelSelect2Multiple(url='speciesAutocomplete')
    )
   

    CHOICES = (('unknown','Don\'t Care'), ('yes', 'Yes'),('no', 'No'))
    is_reversible = forms.ChoiceField(label="Is Reversible?",
                         required=False,widget=forms.Select,choices=CHOICES)

    products = forms.ModelMultipleChoiceField(label="Product(s)",
        queryset=Species.objects.all(), required=False,
        widget=autocomplete.ModelSelect2Multiple(url='speciesAutocomplete')
    )

#Form for generating the SMILES.txt
class GenerateSMILESForm(forms.Form):
    """
    A django form for generating the SMILES file for a Kinetic Model
    """
    # In case you want to get rid of the options for an input
    # c = forms.CharField(label = '[C]', max_length=50,
    #                                      strip = True, required=False)
    # ch2s= forms.CharField(label = 'singlet[CH2]', max_length=50,
    #                                      strip = True, required=False)
    # ch2t = forms.CharField(label = 'triplet[CH2]', max_length=50,
    #                                      strip = True, required=False)
    # c2h2 = forms.CharField(label = 'C#C', max_length=50,
    #                                      strip = True, required=False)  


    def __init__(self, *args, **kwargs):
        C = kwargs.pop('C')
        CH2 = kwargs.pop('CH2')
        C2H2 = kwargs.pop('C2H2')
        super(GenerateSMILESForm, self).__init__(*args, **kwargs)
        self.fields['c'] = forms.ChoiceField(label='[C]', required=False,
                                                widget=forms.Select,choices=C)
        self.fields['ch2s'] = forms.ChoiceField(label='singlet[CH2]',
                             required=False,widget=forms.Select,choices=CH2)
        self.fields['ch2t'] = forms.ChoiceField(label='triplet[CH2]',
                             required=False,widget=forms.Select,choices=CH2)
        self.fields['c2h2'] = forms.ChoiceField(label='C#C',
                             required=False,widget=forms.Select,choices=C2H2)

#Form for adding compounds to the SMILES.txt
class AddSMILESForm(forms.Form):
    """
    A django form for adding compounds to the SMILES file for a Kinetic Model
    """

    smiles = forms.CharField(label = 'SMILES form of the compound',
                                 max_length=50, strip = True, required=False)
    chemkin = forms.CharField(
    label = 'The formula of the compound as represented in the CHEMKIN file',
                                 max_length=50, strip = True, required=False)
 
