"""Tests for chemked_database.repo_check (duplicate and folder checks)."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .github_pr_service import GitHubPRService
from .repo_check import RepoIndex, load_chemked, load_index

O2 = ("O2", "1S/O2/c1-2", 0.1)
AR = ("Ar", "1S/Ar", 0.88)
CH4 = ("CH4", "1S/CH4/h1H4", 0.02)
ETHANOL = ("C2H5OH", "1S/C2H6O/c1-2-3/h3H,2H2,1H3", 0.02)
BUTANOL = ("nC4H9OH", "1S/C4H10O/c1-2-3-4-5/h5H,2-4H2,1H3", 0.02)
METHANOL = ("CH3OH", "1S/CH4O/c1-2/h2H,1H3", 0.02)
NO = ("NO", "1S/NO/c1-2", 0.001)
HEPTANE = ("nC7H16", "1S/C7H16/c1-3-5-7-6-4-2/h3-7H2,1-2H3", 0.01)


def chemked(species, temperatures, doi="10.1000/a", author="J. Aul", year=2013):
    """ChemKED YAML text for an ignition delay file."""
    data = {
        "file-authors": [{"name": "Test"}],
        "file-version": 0,
        "chemked-version": "0.4.1",
        "reference": {"doi": doi, "authors": [{"name": author}], "journal": "J", "year": year},
        "experiment-type": "ignition delay",
        "apparatus": {"kind": "shock tube"},
        "common-properties": {
            "composition": {
                "kind": "mole fraction",
                "species": [
                    {"species-name": n, "InChI": i, "amount": [a]} for n, i, a in species
                ],
            },
            "ignition-type": {"target": "OH*", "type": "d/dt max"},
        },
        "datapoints": [
            {"temperature": [f"{t} kelvin"], "pressure": ["1.5 atm"],
             "ignition-delay": [f"{1e5 / t:.1f} us"]}
            for t in temperatures
        ],
    }
    return yaml.safe_dump(data, sort_keys=False)


FILES = {
    "methane/Aul_2013/Aul_2013_st.yaml": chemked([CH4, O2, AR], [1200, 1300]),
    "methane/Aul_2013/Aul_2013_st_2.yaml": chemked([CH4, O2, AR], [1400, 1500]),
    "methane/Smith_2010/Smith_2010_st.yaml": chemked(
        [CH4, O2, AR], [1100], doi="10.1000/s", author="A. Smith", year=2010),
    # One paper, one file per fuel, same file name
    "ethanol/Beeckmann_2014/Beeckmann_2014_opf_p10bar.yaml": chemked(
        [ETHANOL, O2, AR], [900], doi="10.1000/b", author="J. Beeckmann", year=2014),
    "butanol/Beeckmann_2014/Beeckmann_2014_opf_p10bar.yaml": chemked(
        [BUTANOL, O2, AR], [900], doi="10.1000/b", author="J. Beeckmann", year=2014),
    "methanol/Alzueta_2001/Alzueta_2001_fr.yaml": chemked(
        [METHANOL, O2, AR], [800], doi="10.1000/c", author="M. Alzueta", year=2001),
    "methanol_NOx/Alzueta_2001/Alzueta_2001_fr.yaml": chemked(
        [METHANOL, NO, O2, AR], [800], doi="10.1000/c", author="M. Alzueta", year=2001),
    "n-heptane/Gauthier 2004/st_gauthier_2004-1.yaml": chemked(
        [HEPTANE, O2, AR], [700], doi="10.1000/g", author="B. M. Gauthier", year=2004),
    ".github/workflows/ci.yml": "name: ci\n",
}


def build_clone():
    """Temporary git clone with FILES committed."""
    clone = tempfile.mkdtemp()
    for path, text in FILES.items():
        target = Path(clone, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    git = ["git", "-C", clone, "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", clone], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "data"], check=True)
    return clone


class RepoFixture(SimpleTestCase):
    """A git clone with FILES committed, indexed once per class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.clone = build_clone()
        cls.index = RepoIndex.from_git(cls.clone)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.clone)
        super().tearDownClass()


class RepoCheckTests(RepoFixture):
    def test_no_stays_a_species_name(self):
        self.assertEqual(load_chemked("species-name: NO\nflag: true\n"),
                         {"species-name": "NO", "flag": True})

    def test_indexes_data_files_only(self):
        self.assertEqual(set(self.index.files), set(FILES) - {".github/workflows/ci.yml"})

    def test_same_bytes_anywhere_is_exact(self):
        match = self.index.find_duplicate(FILES["methane/Aul_2013/Aul_2013_st.yaml"])
        self.assertEqual((match.kind, match.path), ("exact", "methane/Aul_2013/Aul_2013_st.yaml"))

    def test_same_data_with_other_format_and_metadata(self):
        data = yaml.safe_load(FILES["methane/Aul_2013/Aul_2013_st.yaml"])
        data["file-authors"] = [{"name": "Someone Else"}]
        data["file-version"] = 2
        data["datapoints"].reverse()
        data["datapoints"][0]["temperature"] = ["1300.0 kelvin"]
        text = yaml.safe_dump(data, sort_keys=True, width=40)

        match = self.index.find_duplicate(text)

        self.assertEqual((match.kind, match.path), ("same-data", "methane/Aul_2013/Aul_2013_st.yaml"))

    def test_changed_value_is_not_a_duplicate(self):
        self.assertIsNone(self.index.find_duplicate(chemked([CH4, O2, AR], [1200, 1301])))

    def test_same_name_in_other_folder_is_not_a_duplicate(self):
        path = "butanol/Beeckmann_2014/Beeckmann_2014_opf_p10bar.yaml"
        self.assertIsNone(self.index.find_duplicate(FILES[path], exclude_path=path))
        methanol = chemked([METHANOL, O2, AR], [950], doi="10.1000/b", author="J. Beeckmann", year=2014)
        self.assertIsNone(self.index.check_upload("Beeckmann_2014_opf_p10bar.yaml", methanol))
        self.assertEqual(
            self.index.suggest_path("Beeckmann_2014_opf_p10bar.yaml", methanol),
            "methanol/Beeckmann_2014/Beeckmann_2014_opf_p10bar.yaml",
        )

    def test_folder_of_same_fuels_and_same_paper(self):
        suggestion = self.index.suggest_folder(chemked([CH4, O2, AR], [1600]))
        self.assertEqual(suggestion.directory, "methane/Aul_2013")
        self.assertIn("same fuels", suggestion.reason)
        self.assertIn("same paper", suggestion.reason)

    def test_new_paper_gets_author_year_folder(self):
        text = chemked([CH4, O2, AR], [1600], doi="10.1000/new", author="Jones, K.", year=2020)
        self.assertEqual(self.index.suggest_folder(text).directory, "methane/Jones_2020")

    def test_existing_author_folder_with_other_spelling(self):
        text = chemked([HEPTANE, O2, AR], [750], doi="10.1000/other", author="B. GAUTHIER", year=2004)
        self.assertEqual(self.index.suggest_folder(text).directory, "n-heptane/Gauthier 2004")

    def test_nox_mixture_goes_to_nox_folder(self):
        text = chemked([METHANOL, NO, O2, AR], [850], doi="10.1000/n", author="P. Glarborg", year=2003)
        self.assertEqual(self.index.suggest_folder(text).folder, "methanol_NOx")
        text = chemked([METHANOL, O2, AR], [850], doi="10.1000/n", author="P. Glarborg", year=2003)
        self.assertEqual(self.index.suggest_folder(text).folder, "methanol")

    def test_species_without_inchi_match_by_name(self):
        text = chemked([("CH4", "", 0.02), ("O2", "", 0.1), ("Ar", "", 0.88)], [1600],
                       doi="10.1000/x", author="A. B", year=1999)
        self.assertEqual(self.index.suggest_folder(text).folder, "methane")

    def test_new_fuel_gets_new_folder(self):
        toluene = ("toluene", "1S/C7H8/c1-7-5-3-2-4-6-7/h2-6H,1H3", 0.01)
        text = chemked([toluene, O2, AR], [1000], doi="10.1000/t", author="A. Burcat", year=1986)
        self.assertEqual(self.index.suggest_folder(text).directory, "toluene/Burcat_1986")

    def test_determine_path_reuses_path_of_same_data(self):
        path = "methane/Smith_2010/Smith_2010_st.yaml"
        reformatted = yaml.safe_dump(yaml.safe_load(FILES[path]), sort_keys=True)
        self.assertEqual(self.index.determine_path("upload.yaml", reformatted), path)

    def test_load_index_caches_by_head(self):
        self.assertIs(load_index(self.clone), load_index(self.clone))
        self.assertIsNone(load_index(tempfile.gettempdir()))

    def test_pr_service_uses_local_clone(self):
        gh = GitHubPRService(token="unused", owner="o", repo="r", local_clone=self.clone)
        reformatted = yaml.safe_dump(yaml.safe_load(FILES["methane/Aul_2013/Aul_2013_st.yaml"]))

        dup = gh.check_for_duplicates("upload.yaml", reformatted)

        self.assertEqual((dup["match_type"], dup["path"]), ("content", "methane/Aul_2013/Aul_2013_st.yaml"))
        self.assertIn("datapoints", dup["existing_content"])
        self.assertEqual(
            gh.determine_repo_path("new.yaml", chemked([CH4, O2, AR], [1700])),
            "methane/Aul_2013/new.yaml",
        )


class UploadPreviewTests(TestCase):
    """The web upload preview names the folder and the matching file."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.clone = build_clone()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.clone)
        super().tearDownClass()

    def _preview(self, text):
        from django.core.files.uploadedfile import SimpleUploadedFile

        url = reverse("chemked_database:dataset-upload")
        with self.settings(CHEMKED_DATABASE_PATH=self.clone, GITHUB_TOKEN="unused"):
            response = self.client.post(url, {
                "data_file": SimpleUploadedFile("upload_7.yaml", text.encode()),
                "file_format": "auto",
                "contribute_to_github": "on",
            }, follow=True)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_new_file_shows_folder(self):
        page = self._preview(chemked([CH4, O2, AR], [2000]))

        self.assertIn("Repository folder", page)
        self.assertIn("<code>methane/Aul_2013/</code>", page)
        self.assertNotIn("Same data already in repository", page)

    def test_same_data_shows_match(self):
        reformatted = yaml.safe_dump(yaml.safe_load(FILES["methane/Smith_2010/Smith_2010_st.yaml"]))

        page = self._preview(reformatted)

        self.assertIn("Same data already in repository", page)
        self.assertIn("<code>methane/Smith_2010/Smith_2010_st.yaml</code>", page)
        self.assertIn("<code>methane/Smith_2010/</code>", page)
