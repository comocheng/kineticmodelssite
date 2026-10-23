import io
import random
import string
import zipfile
from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from database import models, views
from database.services import exports


def create_kinetic_model_with_detail_view_dependencies():
    source = models.Source.objects.create()
    kinetic_model = models.KineticModel.objects.create(source=source)
    return kinetic_model


def create_species():
    hsh = "".join(random.choices(string.ascii_letters, k=10))
    formula = models.Formula.objects.create(formula=hsh)
    isomer = models.Isomer.objects.create(inchi=hsh, formula=formula)
    species = models.Species.objects.create(hash=hsh)
    species.isomers.add(isomer)

    return species


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
            species = create_species()
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
            species = create_species()
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
        for i in range(1, paginate_per_page):
            species = create_species()
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
        response = self.client.get(reverse("kinetic-model-detail", args=[kinetic_model.pk]))

        self.assertContains(
            response,
            reverse("kinetic-model-download", args=[kinetic_model.pk, "chemkin"]),
        )
        self.assertContains(
            response,
            reverse("kinetic-model-download", args=[kinetic_model.pk, "cantera"]),
        )
        self.assertContains(response, kinetic_model.chemkin_reactions_file.url)
        self.assertContains(response, kinetic_model.chemkin_thermo_file.url)
        self.assertContains(response, kinetic_model.chemkin_transport_file.url)

    def test_download_links_missing(self):
        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
        response = self.client.get(reverse("kinetic-model-detail", args=[kinetic_model.pk]))
        self.assertNotContains(
            response,
            reverse("kinetic-model-download", args=[kinetic_model.pk, "chemkin"]),
        )


class TestKineticModelDownloads(TestCase):
    def test_download_chemkin_bundle(self):
        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
        kinetic_model.chemkin_reactions_file.save(
            "test_reactions.txt", ContentFile("test_reactions")
        )
        kinetic_model.chemkin_thermo_file.save("test_thermo.txt", ContentFile("test_thermo"))
        kinetic_model.chemkin_transport_file.save(
            "test_transport.txt", ContentFile("test_transport")
        )

        response = self.client.get(
            reverse("kinetic-model-download", args=[kinetic_model.pk, "chemkin"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            filenames = set(archive.namelist())

        self.assertEqual(
            filenames,
            {"chemkin_reactions.txt", "chemkin_thermo.txt", "chemkin_transport.txt"},
        )

    @mock.patch("database.views.exports.build_cantera_yaml")
    def test_download_cantera_yaml(self, build_cantera_yaml):
        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
        build_cantera_yaml.return_value = exports.ExportResult(
            content=b"yaml-content",
            filename="test.yaml",
            content_type="application/x-yaml",
        )

        response = self.client.get(
            reverse("kinetic-model-download", args=[kinetic_model.pk, "cantera"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"yaml-content")
        self.assertEqual(response["Content-Type"], "application/x-yaml")

    @mock.patch("database.services.exports._generate_chemkin_files")
    def test_download_chemkin_bundle_generated(self, generate_chemkin_files):
        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
        generate_chemkin_files.return_value = {"chemkin_reactions.txt": b"chem"}

        response = self.client.get(
            reverse("kinetic-model-download", args=[kinetic_model.pk, "chemkin"])
        )

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(set(archive.namelist()), {"chemkin_reactions.txt"})

    @mock.patch("database.views.exports.build_chemkin_bundle")
    def test_download_chemkin_bundle_strict_toggle(self, build_chemkin_bundle):
        kinetic_model = create_kinetic_model_with_detail_view_dependencies()
        build_chemkin_bundle.return_value = exports.ExportResult(
            content=b"chem",
            filename="test.zip",
            content_type="application/zip",
        )

        response = self.client.get(
            reverse("kinetic-model-download", args=[kinetic_model.pk, "chemkin"]),
            {"strict": "1"},
        )

        self.assertEqual(response.status_code, 200)
        build_chemkin_bundle.assert_called_once_with(kinetic_model, strict=True)
