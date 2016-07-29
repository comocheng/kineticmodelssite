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
        exclude = ()

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
        fields = ('source', 'mPrimeID', 'model_name', 'additional_info')
        widgets =  {
            'source': autocomplete.ModelSelect2(url='source-autocomplete')
        }
 
    # mPrimeID = forms.CharField(label = 'mPrIMe ID', max_length=9, strip = True, required=False)
    # source = forms.ModelChoiceField(label="Source",
    #     queryset=Source.objects.all(), required=False,
    #     widget=autocomplete.ModelSelect2Multiple(url='source-autocomplete'))
    # model_name = forms.CharField(label = 'Model Name', max_length=200, strip = True, required=False)
    # additional_info = forms.CharField(label = 'Additional Info', max_length=1000, strip = True, required=False)    




class EditKineticModelFileForm(forms.ModelForm):
    """
    Django Form template for editing a Model
    """
    class Meta:
        model = KineticModel
    #    exclude = ('kinetics', 'thermo', 'transport')
        fields = ('chemkin_reactions_file', 'chemkin_thermo_file', 'chemkin_transport_file')


class UploadKineticModelForm(forms.ModelForm):
    """
    A Django form for uploading a kinetic model.
    """
    class Meta:
        model = KineticModel
        fields = ('chemkin_reactions_file', 'chemkin_thermo_file', 'chemkin_transport_file')


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


#Form for searching Species
class SpeciesSearchForm(forms.Form):
    """
    A django form for searching through a Species
    """
    # class Meta:
    #     model = Species
    #     fields = ('formula', 'sPrimeID', 'inchi', 'cas')


    sPrimeID = forms.CharField(label = 'PrIMe ID', max_length=9, strip = True, required=False)
    formula = forms.CharField(label = 'Formula', max_length=50, strip = True, required=False)
    inchi = forms.CharField(label = 'InChI', max_length=500, strip = True, required=False)
    cas = forms.CharField(label = 'CAS Registry Number', max_length=400, strip = True, required=False)    


#Form for searching Sources
# class SourceSearchForm(forms.Form):
#     """
#     A django form for searching through a Sources
#     """

#     bPrimeID = forms.CharField(label = 'PrIMe ID', max_length=9, strip = True, required=False)
#     publication_year = forms.CharField(label = 'Year of Publication', max_length=4, strip = True, required=False)
#     source_title = forms.CharField(label = 'Source Title', max_length=300, strip = True, required=False)
#     journal_name = forms.CharField(label = 'Journal Name', max_length=300, strip = True, required=False)
#     journal_volume_number = forms.CharField(label = 'Journal Volume Number', max_length=10, strip = True, required=False)
#     page_numbers = forms.CharField(label = 'Page Number ([page #]-[page #])', max_length=100, strip = True, required=False)
#     doi = forms.CharField(label = 'DOI', max_length=80, strip = True, required=False)
# #    author = forms.CharField(label = 'Author', max_length=80, strip = True, required=False)

#     author = forms.ModelChoiceField( queryset=Author.objects.all(), required=False,
#             widget=autocomplete.ModelSelect2Multiple(url='author-autocomplete') )

class SourceSearchForm(forms.ModelForm):

    class Meta:
        model = Source
        fields = ('bPrimeID', 'publication_year', 'source_title', 'journal_name', 'journal_volume_number', 'page_numbers', 'doi', 'authors')
        widgets =  {
            'authors': autocomplete.ModelSelect2Multiple(url='author-autocomplete')
        }




#Form for searching Reactions
class ReactionSearchForm(forms.Form):
    """
    A django form for searching through a Reaction
    """

    rPrimeID = forms.CharField(label = 'Reaction PrIMe ID', max_length=9, strip = True, required=False)

    # reactant1Formula = forms.ModelChoiceField(
    #     queryset=Species.objects.all(), required=False,
    #     widget=autocomplete.ModelSelect2(url='species-autocomplete')
    # )
    # reactant2Formula = forms.ModelChoiceField(
    #     queryset=Species.objects.all(), required=False,
    #     widget=autocomplete.ModelSelect2(url='species-autocomplete')
    # )
    reactants = forms.ModelMultipleChoiceField(label="Reactant(s)",
        queryset=Species.objects.all(), required=False,
        widget=autocomplete.ModelSelect2Multiple(url='species-autocomplete')
    )
   

    CHOICES = (('unknown','Don\'t Care'), ('yes', 'Yes'),('no', 'No'))
    is_reversible = forms.ChoiceField(label="Is Reversible?", required=False,widget=forms.Select,choices=CHOICES)

    products = forms.ModelMultipleChoiceField(label="Product(s)",
        queryset=Species.objects.all(), required=False,
        widget=autocomplete.ModelSelect2Multiple(url='species-autocomplete')
    )
