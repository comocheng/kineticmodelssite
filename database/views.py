from functools import lru_cache
from django.views.generic import TemplateView, DetailView
from .models import Species, SpeciesName


class IndexView(TemplateView):
    template_name = "index.html"


class ResourcesView(TemplateView):
    template_name = "resources.html"

    @staticmethod
    def parse_file_name(file_name):
        name = os.path.splitext(file_name)[0]
        parts = name.split('_')
        date = parts[0]
        date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
        title = ' '.join(parts[1:])
        title = title.replace('+', ' and ')

        return (title, date, file_name)

    @property
    @lru_cache
    def presentations(self):
        pres_list = []
        folder = os.path.join(settings.STATIC_ROOT, 'presentations')
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


def molecule_search(request):
    pass

class MoleculeResultView(DetailView):
    model = Species

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["names"] = self.get_object().species_name_set.all().values_list("name", flat=True)
        context["adjlists"] = self.get_object().isomer_set.select_related("structure").values_list("adjacencyList", flat=True)
        

def molecule_result(request, pk):
    pass

def transport_results(request):
    pass

def thermo_results(request):
    pass

def kinetics_results(request):
    pass

def transport_result(request):
    pass

def thermo_result(request):
    pass

def kinetics_result(request):
    pass

def kinetics_search(request):
    pass

def reaction_results(request):
    pass

def solvation_search(request):
    pass
