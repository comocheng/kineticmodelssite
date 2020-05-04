from functools import lru_cache

import django_filters
from django.views.generic import TemplateView, DetailView, FormView, ListView
from django.urls import reverse
from django.db.models.fields import related

from .models import Species, Structure, SpeciesName, KineticModel, Thermo,\
    Transport, Source, Reaction, Stoichiometry, BaseKineticsData, Kinetics


class BaseView(TemplateView):
    template_name = "base.html"

    
class IndexView(TemplateView):
    template_name = "index.html"


class ResourcesView(TemplateView):
    template_name = "resources.html"

    @staticmethod
    def parse_file_name(file_name):
        name = os.path.splitext(file_name)[0]
        parts = name.split("_")
        date = parts[0]
        date = date[0:4] + "-" + date[4:6] + "-" + date[6:]
        title = " ".join(parts[1:])
        title = title.replace("+", " and ")

        return (title, date, file_name)

    @property
    @lru_cache()
    def presentations(self):
        pres_list = []
        folder = os.path.join(settings.STATIC_ROOT, "presentations")
        if os.path.isdir(folder):
            for root, dirs, files in os.walk(folder):
                for file in files:
                    parsed = self.parse_file_name(file_name)
                    pres_list.append(parsed)

        return pres_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["presentations"] = self.presentations
        return context


class SpeciesFilter(django_filters.FilterSet):
    speciesname__name = django_filters.CharFilter(field_name="speciesname", lookup_expr="name", label="Species Name")
    isomer__inchi = django_filters.CharFilter(field_name="isomer", lookup_expr="inchi", label="Isomer InChI")
    isomer__structure__smiles = django_filters.CharFilter(field_name="isomer", lookup_expr="structure__smiles", label="Structure SMILES")
    isomer__structure__adjacencyList = django_filters.CharFilter(field_name="isomer", lookup_expr="structure__adjacencyList", label="Structure Adjacency List")
    isomer__structure__electronicState = django_filters.NumberFilter(field_name="isomer", lookup_expr="structure__electronicState", label="Structure Electronic State")
    
    class Meta:
        model = Species
        fields = ["sPrimeID", "formula", "inchi", "cas"]

class SourceFilter(django_filters.FilterSet):
    sourcename_name = django_filters.CharFilter(field_name="sourcename", lookup_expr="name", label="Source Name")
    class Meta:
        model = Source
        fields = ["name", "bPrimeID", "publicationYear", "sourceTitle", "doi"]

class ReactionFilter(django_filters.FilterSet):
    #reaction = django_filters.CharFilter(field_name="sourcename", lookup_expr="name", label="Source Name")
    class Meta:
        model = Reaction
        fields = ["species", "rPrimeID", "isReversible"]


class SpeciesDetail(DetailView):
    model = Species

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        structures = Structure.objects.filter(isomer__species=self.get_object())
        context["names"] = (
            set(self.get_object().speciesname_set.all().values_list("name", flat=True))
        )
        context["adjlists"] = structures.values_list("adjacencyList", flat=True)
        context["smiles"] = structures.values_list("smiles", flat=True)
        context["isomer_inchis"] = self.get_object().isomer_set.values_list(
            "inchi", flat=True
        )
        context["thermo_list"] = Thermo.objects.filter(species=self.get_object())
        context["transport_list"] = Transport.objects.filter(species=self.get_object())

        return context


class ThermoDetail(DetailView):
    model = Thermo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thermo = self.get_object()
        kinetic_model = KineticModel.objects.get(thermo=thermo)
        context["species_name"] = kinetic_model.speciesname_set.get(species=thermo.species).name
        context["thermo"] = thermo
        context["species"] = thermo.species 
        context['source'] = thermo.source
        context["species_name"] = kinetic_model.speciesname_set.get(species=thermo.species).name
        return context


class TransportDetail(DetailView):
    model = Transport

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transport = self.get_object()
        kinetic_model = KineticModel.objects.get(transport=transport)
        context["species_name"] = kinetic_model.speciesname_set.get(species=transport.species).name

        return context
        
class SourceDetail(DetailView):
    model = Source

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source = self.get_object()
        kinetic_model = KineticModel.objects.get(source=source)
        context['source'] = source
        return context

class ReactionDetail(DetailView):
    model = Reaction

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reaction = self.get_object()
        #kinetic_model = KineticModel.objects.get()
        context['reaction'] = reaction
        context['reactants'] = reaction.reactants()
        context['products'] = reaction.products()
        try:
            context['kinetics'] = reaction.kinetics_set.all()
        except:
            context['kinetics'] = None
        return context

class KineticsDetail(DetailView):
    model = Kinetics

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kinetics = self.get_object()
        kineticdata = None
        for kin_type in ['arrhenius', 'arrheniusep', 'chebyshev', 'lindemann', 'multiarrhenius', 'multipdeparrhenius', 'pdeparrhenius', 'thirdbody', 'troe']:
            try:
                kineticdata = eval(f'kinetics.basekineticsdata.{kin_type}')
                break
            except:
                continue
        try:
            context['kinetics'] = kinetics
            context['kin_type'] = kin_type
            context['kineticdata'] = kineticdata
        except: 
            context['kinetics'] = None
            context['kin_type'] = None
            context['kineticdata'] = None
        return context