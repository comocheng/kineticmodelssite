from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from database import models, views


def create_kinetic_model_with_detail_view_dependencies():
    source = models.Source.objects.create()
    kinetic_model = models.KineticModel.objects.create(source=source)
    return kinetic_model


# Create your tests here.
class TestKineticModelDetail(TestCase):
    def test_missing_thermo(self):
        """
        If not all species have transport data, all the species will still be displayed
        """

        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
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
        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
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
            <dt>Downloads</dt>
                <dd><a href='{}' download>Chemkin Reactions File</a></dd>
                <dd><a href='{}' download>Chemkin Thermo File</a></dd>
                <dd><a href='{}' download>Chemkin Transport File</a></dd>
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
        download_content = "<dt>Downloads</dt>"
        response_content = "".join(response.content.decode("utf-8").split()).replace('"', "'")
        self.assertFalse(download_content in response_content)
