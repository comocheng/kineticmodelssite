from django.test import TestCase
from django.urls import reverse
from database import models, views


# Create your tests here.
class TestKineticModelDetail(TestCase):
    def test_missing_thermo(self):
        """
        If not all species have transport data, all the species will still be displayed
        """
        source = models.Source.objects.create()
        kinetic_model = models.KineticModel.objects.create(source=source)
        paginate_per_page = views.KineticModelDetail.paginate_per_page
        for i in range(1, views.KineticModelDetail.paginate_per_page):
            species = models.Species.objects.create()
            transport = models.Transport.objects.create(species=species)
            kinetic_model.species.add(species)
            kinetic_model.transport.add(transport)
            if i <= paginate_per_page / 2:
                thermo = models.Thermo.objects.create(species=species)
                kinetic_model.thermo.add(thermo)

        response = self.client.get(reverse("kinetic-model-detail", args=[kinetic_model.pk]))
        self.assertEqual(len(response.context["thermo_transport"]), kinetic_model.species.count())

    def test_missing_transport(self):
        """
        If not all species have thermo data, all the species will still be displayed
        """
        source = models.Source.objects.create()
        kinetic_model = models.KineticModel.objects.create(source=source)
        paginate_per_page = views.KineticModelDetail.paginate_per_page
        for i in range(1, paginate_per_page):
            species = models.Species.objects.create()
            thermo = models.Thermo.objects.create(species=species)
            kinetic_model.species.add(species)
            kinetic_model.thermo.add(thermo)
            if i <= paginate_per_page / 2:
                transport = models.Transport.objects.create(species=species)
                kinetic_model.transport.add(transport)

        response = self.client.get(reverse("kinetic-model-detail", args=[kinetic_model.pk]))
        self.assertEqual(len(response.context["thermo_transport"]), kinetic_model.species.count())
