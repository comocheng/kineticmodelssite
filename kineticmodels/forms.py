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
from models import KineticModel, Source, Species, Reaction

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
class EditKineticModelForm(forms.ModelForm):
    """
    Django Form template for editing a Model
    """
    class Meta:
        model = KineticModel
        exclude = ()

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
class SourceSearchForm(forms.Form):
    """
    A django form for searching through a Sources
    """

    sPrimeID = forms.CharField(label = 'PrIMe ID', max_length=9, strip = True, required=False)
    formula = forms.CharField(label = 'Formula', max_length=50, strip = True, required=False)
    inchi = forms.CharField(label = 'InChI', max_length=500, strip = True, required=False)
    cas = forms.CharField(label = 'CAS Registry Number', max_length=400, strip = True, required=False)




