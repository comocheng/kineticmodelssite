from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from database import models, views


def create_kinetic_model_with_detail_view_dependencies():
    source = models.Source.objects.create()
    kinetic_model = models.KineticModel.objects.create(source=source)
    return kinetic_model

def create_thermo(species):
    fields = {
        "coeffs_poly1": list(range(7)),
        "coeffs_poly2": list(range(7)),
        "temp_min_1": 0,
        "temp_max_1": 0,
        "temp_min_2": 0,
        "temp_max_2": 0,
    }
    thermo = models.Thermo.objects.create(species=species, **fields)

    return thermo

# Create your tests here.
class TestKineticModelDetail(TestCase):
    def test_missing_thermo(self):
        """
        If not all species have transport data, all the species will still be displayed
        """

        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
        paginate_per_page = views.KineticModelDetail.cls.paginate_per_page
        for i in range(1, paginate_per_page):
            species = models.Species.objects.create()
            transport = models.Transport.objects.create(species=species)
            kinetic_model.species.add(species)
            kinetic_model.transport.add(transport)
            if i <= paginate_per_page / 2:
                thermo = create_thermo(species=species)
                kinetic_model.thermo.add(thermo)

        response = self.client.get(reverse("kinetic-model-detail", args=[kinetic_model.pk]))
        self.assertEqual(len(response.context["thermo_transport"]), kinetic_model.species.count())

    def test_missing_transport(self):
        """
        If not all species have thermo data, all the species will still be displayed
        """
        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
        paginate_per_page = views.KineticModelDetail.cls.paginate_per_page
        for i in range(1, paginate_per_page):
            species = models.Species.objects.create()
            thermo = create_thermo(species=species)
            kinetic_model.species.add(species)
            kinetic_model.thermo.add(thermo)
            if i <= paginate_per_page / 2:
                transport = models.Transport.objects.create(species=species)
                kinetic_model.transport.add(transport)

        response = self.client.get(reverse("kinetic-model-detail", args=[kinetic_model.pk]))
        self.assertEqual(len(response.context["thermo_transport"]), kinetic_model.species.count())

    def test_thermo_transport_aligned(self):
        """
        The thermo-transport pairs passed to the context should be related to the same species
        """
        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
        paginate_per_page = views.KineticModelDetail.cls.paginate_per_page
        for _ in range(1, paginate_per_page):
            species = models.Species.objects.create()
            thermo = create_thermo(species=species)
            transport = models.Transport.objects.create(species=species)
            kinetic_model.species.add(species)
            kinetic_model.thermo.add(thermo)
            kinetic_model.transport.add(transport)

        response = self.client.get(reverse("kinetic-model-detail", args=[kinetic_model.pk]))
        thermo_transport = response.context["thermo_transport"]
        for thermo, transport in thermo_transport:
            self.assertEqual(thermo.thermo.species.pk, transport.transport.species.pk)


    def test_download_links_present(self):
        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
        kinetic_model.chemkin_reactions_file.save(
            "test_reactions.txt", ContentFile("test_reactions")
        )
        kinetic_model.chemkin_thermo_file.save("test_thermo.txt", ContentFile("test_thermo"))
        kinetic_model.chemkin_transport_file.save(
            "test_transport.txt", ContentFile("test_transport")
        )
        response = self.client.get(reverse("kinetic-model-detail", args=[kinetic_model.pk]))
        download_content = "".join(
            """
            <h2>Downloads</h2>
                <ul class='list-group'>
                    <li class='list-group-item'><a href='{}' download>Chemkin Reactions File</a></li>
                    <li class='list-group-item'><a href='{}' download>Chemkin Thermo File</a></li>
                    <li class='list-group-item'><a href='{}' download>Chemkin Transport File</a></li>
                </ul>
            """.format(
                kinetic_model.chemkin_reactions_file.url,
                kinetic_model.chemkin_thermo_file.url,
                kinetic_model.chemkin_transport_file.url,
            ).split()
        )

        response_content = "".join(response.content.decode("utf-8").split()).replace('"', "'")
        self.assertTrue(download_content in response_content)

    def test_download_links_missing(self):
        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
        response = self.client.get(reverse("kinetic-model-detail", args=[kinetic_model.pk]))
        download_content = "<h2>Downloads</h2>"
        response_content = "".join(response.content.decode("utf-8").split()).replace('"', "'")
        self.assertFalse(download_content in response_content)
