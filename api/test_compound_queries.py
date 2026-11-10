"""Query conventions of the list endpoints: paging, strict parameters, records listed once,
``__in`` lookups, mixture filters, conditions on one datapoint and ``has_`` filters."""

from django.test import TestCase

from chemked_database import models as cm
from database import models as dm

NH3, H2, O2 = "1S/H3N/h1H3", "1S/H2/h1H", "1S/O2/c1-2"


def make_species(inchi, electronic_state=""):
    formula, _ = dm.Formula.objects.get_or_create(formula=inchi.split("/")[1])
    isomer, _ = dm.Isomer.objects.get_or_create(inchi=f"InChI={inchi}", formula=formula)
    species = dm.Species.objects.create(hash=f"{inchi}{electronic_state}", electronic_state=electronic_state)
    species.isomers.add(isomer)
    return species


def make_composition(*components):
    composition = cm.Composition.objects.create(kind="mole fraction")
    for name, inchi, *link in components:
        cm.CompositionSpecies.objects.create(
            composition=composition, species_name=name, inchi=inchi, amount=0.1,
            database_species=link[0] if link else None,
        )
    return composition


def make_dataset(path, experiment_type="ignition delay", common_composition=None, **common):
    dataset = cm.ExperimentDataset.objects.create(chemked_file_path=path, experiment_type=experiment_type)
    if common_composition is not None or common:
        cm.CommonProperties.objects.create(dataset=dataset, composition=common_composition, **common)
    return dataset


def make_point(dataset, pressure, temperature, composition=None, ignition_type=""):
    point = cm.ExperimentDatapoint.objects.create(
        dataset=dataset, pressure=pressure, temperature=temperature, composition=composition
    )
    if dataset.experiment_type == "ignition delay":
        cm.IgnitionDelayDatapoint.objects.create(
            datapoint=point, ignition_delay=1e-3, ignition_type=ignition_type
        )
    return point


class CompoundQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.nh3 = make_species(NH3)
        cls.h2 = make_species(H2)

        # NH3/H2 blends at 0.5 and 2 MPa, each datapoint with its own mixture
        cls.blend = make_dataset("blend.yaml")
        cls.blend_low = make_point(cls.blend, 5e5, 1000, make_composition(("NH3", NH3), ("H2", H2)),
                                   ignition_type="d/dt max")
        cls.blend_high = make_point(cls.blend, 2e6, 1200, make_composition(("NH3", NH3), ("H2", H2)),
                                    ignition_type="d/dt max")
        cm.TimeHistory.objects.create(datapoint=cls.blend_low, history_type="pressure",
                                      quantity_units="Pa", values=[[0, 1]])
        cm.VolumeHistory.objects.create(datapoint=cls.blend_high, volume_units="cm3", values=[[0, 1]])

        # NH3/O2 given once in the common properties; the datapoints have no mixture of their own
        cls.common = make_dataset("common.yaml", common_composition=make_composition(("NH3", NH3), ("O2", O2)),
                                  ignition_type="max")
        cls.common_point = make_point(cls.common, 1.5e6, 1300)

        # H2/O2: hot at high pressure, cool at low pressure; no ignition type anywhere
        cls.h2_only = make_dataset("h2.yaml")
        cls.h2_cool = make_point(cls.h2_only, 1e5, 900, make_composition(("H2", H2), ("O2", O2)))
        cls.h2_hot = make_point(cls.h2_only, 3e6, 1500, make_composition(("H2", H2), ("O2", O2)))

        cls.flame = make_dataset("flame.yaml", experiment_type="laminar burning velocity measurement")
        make_point(cls.flame, 1e5, 300, make_composition(("H2", H2)))

        # Common properties without a mixture, next to an NH3 row without a composition (the
        # species of a concentration profile): the two empty values must not match.
        cls.no_mixture = make_dataset("no_mixture.yaml", pressure=1e5)
        make_point(cls.no_mixture, 1e5, 1000, ignition_type="max")
        cm.CompositionSpecies.objects.create(species_name="NH3", inchi=NH3)

    def _get(self, path, **params):
        return self.client.get(path, params)

    def _ids(self, path, **params):
        response = self._get(path, **params)
        self.assertEqual(response.status_code, 200, response.content[:400])
        body = response.json()
        ids = [row["id"] for row in body["results"]]
        self.assertEqual(body["count"], len(ids))
        return sorted(ids)

    def _datasets(self, query):
        response = self.client.get(f"/api/experiment-dataset/?{query}")
        self.assertEqual(response.status_code, 200, response.content[:400])
        body = response.json()
        self.assertEqual(body["count"], len(body["results"]))
        return sorted(row["chemked_file_path"] for row in body["results"])

    # 1. Paging -----------------------------------------------------------------------------
    def test_page_size_is_honoured(self):
        body = self._get("/api/experiment-datapoint/", page_size=2).json()
        self.assertEqual(len(body["results"]), 2)
        self.assertIn("page_size=2", body["next"])

    def test_page_size_is_capped(self):
        from api.pagination import PageNumberPagination

        self.assertEqual(PageNumberPagination.max_page_size, 1000)
        body = self._get("/api/experiment-datapoint/", page_size=100000).json()
        self.assertEqual(len(body["results"]), cm.ExperimentDatapoint.objects.count())

    # 2. Unknown parameters -----------------------------------------------------------------
    def test_unknown_parameter_is_an_error(self):
        response = self._get("/api/experiment-datapoint/", presure__gte=1e6)
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["unknown_parameters"], ["presure__gte"])
        self.assertIn("pressure__gte", body["allowed_parameters"])

    def test_unsupported_lookup_is_an_error(self):
        self.assertEqual(self._get("/api/experiment-datapoint/", pressure__gt=1e6).status_code, 400)

    def test_search_only_where_the_endpoint_searches(self):
        self.assertEqual(self._get("/api/experiment-dataset/", search="x").status_code, 200)
        self.assertEqual(self._get("/api/experiment-datapoint/", search="x").status_code, 400)

    def test_paging_format_and_expansion_parameters_are_allowed(self):
        response = self._get("/api/ignition-delay/", page=1, page_size=1, format="json",
                             expand="datapoint", fields="id,datapoint", ordering="-id")
        self.assertEqual(response.status_code, 200, response.content[:400])

    def test_unknown_ordering_is_an_error(self):
        response = self._get("/api/ignition-delay/", ordering="datapoint__dataset")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["unknown_ordering"], ["datapoint__dataset"])
        self.assertIn("datapoint__temperature", response.json()["allowed_ordering"])

    def test_measurements_ordered_by_datapoint_conditions(self):
        delays = self._get("/api/ignition-delay/", ordering="-datapoint__temperature").json()["results"]
        self.assertEqual(delays[0]["datapoint"], self.h2_hot.pk)

    def test_a_single_record_ignores_list_parameters(self):
        response = self._get(f"/api/experiment-dataset/{self.blend.pk}/", unknown="1")
        self.assertEqual(response.status_code, 200)

    # 3. Records listed once ----------------------------------------------------------------
    def test_dataset_listed_once_for_many_matching_datapoints(self):
        self.assertEqual(
            self._datasets("datapoints__composition__species__species_name__icontains=NH3"),
            ["blend.yaml"],
        )

    def test_filterset_fields_list_a_record_once(self):
        species = dm.Species.objects.create(hash="two isomers")
        formula = dm.Formula.objects.create(formula="C2H6O")
        for inchi in ("InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3", "InChI=1S/C2H6O/c1-3-2/h1-2H3"):
            species.isomers.add(dm.Isomer.objects.create(inchi=inchi, formula=formula))
        self.assertEqual(self._ids("/api/species/", isomers__formula=formula.pk), [species.pk])

    # 4. __in lookups -----------------------------------------------------------------------
    def test_in_lookups(self):
        self.assertEqual(
            self._ids("/api/experiment-datapoint/", dataset__in=f"{self.blend.pk},{self.common.pk}"),
            sorted([self.blend_low.pk, self.blend_high.pk, self.common_point.pk]),
        )
        self.assertEqual(
            self._datasets("experiment_type__in=laminar+burning+velocity+measurement,rate+coefficient"),
            ["flame.yaml"],
        )
        self.assertEqual(self._ids("/api/experiment-dataset/", id__in=f"{self.flame.pk}"), [self.flame.pk])

    def test_in_lookup_with_an_unknown_record_is_an_error(self):
        self.assertEqual(self._get("/api/experiment-datapoint/", dataset__in="999999").status_code, 400)

    # 5. Mixtures that contain every species given ------------------------------------------
    def test_repeated_inchi_requires_every_component(self):
        both = f"/api/experiment-datapoint/?inchi={NH3}&inchi={H2}"
        self.assertEqual(self._ids(both), sorted([self.blend_low.pk, self.blend_high.pk]))

    def test_common_mixture_counts_for_points_without_their_own(self):
        self.assertEqual(
            self._ids("/api/experiment-datapoint/", inchi=NH3),
            sorted([self.blend_low.pk, self.blend_high.pk, self.common_point.pk]),
        )
        # The datapoint's own composition only, as before
        self.assertEqual(
            self._ids("/api/experiment-datapoint/", composition__species__inchi=NH3),
            sorted([self.blend_low.pk, self.blend_high.pk]),
        )

    def test_inchi_prefix_is_optional(self):
        self.assertEqual(
            self._ids("/api/experiment-datapoint/", inchi=f"InChI={NH3}"),
            self._ids("/api/experiment-datapoint/", inchi=NH3),
        )

    def test_mixture_filters_on_a_measurement_endpoint(self):
        delays = self._get(f"/api/ignition-delay/?inchi={NH3}&inchi={O2}").json()["results"]
        self.assertEqual([d["datapoint"] for d in delays], [self.common_point.pk])

    # 6. Conditions on one datapoint --------------------------------------------------------
    def test_dataset_conditions_apply_to_one_datapoint(self):
        self.assertEqual(self._datasets(f"inchi={H2}&pressure__gte=2e6"), ["blend.yaml", "h2.yaml"])
        # h2.yaml has a point at 3 MPa and a point at 900 K, but not one point with both
        self.assertEqual(
            self._datasets(f"inchi={H2}&pressure__gte=2e6&temperature__lte=1000"), []
        )
        self.assertEqual(
            self._datasets(f"experiment_type=ignition+delay&inchi={H2}&pressure__lte=2e5"
                           "&temperature__lte=1000"),
            ["h2.yaml"],
        )

    def test_dataset_mixture_from_common_properties(self):
        self.assertEqual(
            self._datasets(f"experiment_type=ignition+delay&inchi={NH3}&pressure__gte=1e6"),
            ["blend.yaml", "common.yaml"],
        )

    def test_empty_common_mixture_does_not_match(self):
        self.assertNotIn("no_mixture.yaml", self._datasets(f"inchi={NH3}"))

    # 7. Species records --------------------------------------------------------------------
    def test_species_record_selects_datasets_and_datapoints(self):
        self.assertEqual(self._datasets(f"species={self.nh3.pk}"), ["blend.yaml", "common.yaml"])
        self.assertEqual(
            self._datasets(f"species={self.nh3.pk}&species={self.h2.pk}"), ["blend.yaml"]
        )
        self.assertEqual(
            self._ids("/api/experiment-datapoint/", species=self.h2.pk, pressure__gte=1e6),
            sorted([self.blend_high.pk, self.h2_hot.pk]),
        )

    def test_component_linked_to_the_species_record(self):
        argon = dm.Species.objects.create(hash="argon")
        dataset = make_dataset("argon.yaml")
        point = make_point(dataset, 1e5, 1000, make_composition(("Ar", "", argon)))
        self.assertEqual(self._ids("/api/experiment-datapoint/", species=argon.pk), [point.pk])

    def test_excited_state_matches_only_linked_components(self):
        nh3_excited = make_species(NH3, electronic_state="excited")
        self.assertEqual(self._datasets(f"species={nh3_excited.pk}"), [])

    def test_species_records_match_by_standard_inchi(self):
        # RMG writes the unpaired electrons of triplet O2 and of OH as a /u layer
        o2 = make_species("1S/O2/c1-2/u1,2")
        oh = make_species("1S/HO/h1H/u1")
        flame = make_dataset("oh.yaml")
        make_point(flame, 1e5, 1500, make_composition(("OH", "1S/HO/h1H"), ("Ar", "1S/Ar")))
        self.assertEqual(self._datasets(f"species={o2.pk}"), ["common.yaml", "h2.yaml"])
        self.assertEqual(self._datasets(f"species={oh.pk}"), ["oh.yaml"])
        self.assertEqual(
            self._ids("/api/experiment-dataset/", inchi="InChI=1S/O2/c1-2/u1,2"),
            sorted([self.common.pk, self.h2_only.pk]),
        )

    def test_spin_states_match_the_same_components(self):
        # A standard InChI has no spin layer, so triplet O2 and singlet O2 ("O2X") select the
        # same rows, also a row that is linked to the singlet record.
        o2 = make_species("1S/O2/c1-2/u1,2")
        o2_singlet = make_species(O2)
        linked = make_dataset("linked.yaml")
        make_point(linked, 1e5, 1000, make_composition(("O2", O2, o2_singlet)))
        expected = ["common.yaml", "h2.yaml", "linked.yaml"]
        self.assertEqual(self._datasets(f"species={o2.pk}"), expected)
        self.assertEqual(self._datasets(f"species={o2_singlet.pk}"), expected)

    def test_link_to_an_excited_state_is_kept(self):
        oh = make_species("1S/HO/h1H/u1")
        oh_excited = make_species("1S/HO/h1H/u1", electronic_state="excited")
        ground = make_dataset("oh.yaml")
        make_point(ground, 1e5, 1500, make_composition(("OH", "1S/HO/h1H")))
        excited = make_dataset("oh_star.yaml")
        make_point(excited, 1e5, 1500, make_composition(("OH*", "1S/HO/h1H", oh_excited)))
        self.assertEqual(self._datasets(f"species={oh.pk}"), ["oh.yaml"])
        self.assertEqual(self._datasets(f"species={oh_excited.pk}"), ["oh_star.yaml"])

    def test_unknown_species_record_is_an_error(self):
        self.assertEqual(self._get("/api/experiment-dataset/", species=999999).status_code, 400)

    # 8. has_ filters -----------------------------------------------------------------------
    def test_has_histories(self):
        self.assertEqual(self._ids("/api/experiment-datapoint/", has_time_histories="true"),
                         [self.blend_low.pk])
        self.assertEqual(self._ids("/api/experiment-datapoint/", has_volume_history="true"),
                         [self.blend_high.pk])
        self.assertEqual(self._datasets("has_time_histories=true"), ["blend.yaml"])
        self.assertEqual(len(self._datasets("has_volume_history=false")), 4)

    def test_has_ignition_type_uses_the_common_properties(self):
        missing = self._get("/api/ignition-delay/", has_ignition_type="false").json()["results"]
        self.assertEqual(sorted(d["datapoint"] for d in missing), sorted([self.h2_cool.pk, self.h2_hot.pk]))
        given = self._get("/api/ignition-delay/", has_ignition_type="true").json()["count"]
        self.assertEqual(given, 4)

    def test_has_license_and_common_properties(self):
        self.assertEqual(len(self._datasets("has_license=false")), 5)
        self.assertEqual(self._datasets("has_common_properties=true"), ["common.yaml", "no_mixture.yaml"])
        self.assertEqual(
            self._ids("/api/common-properties/", has_ignition_type="false"),
            [self.no_mixture.common_properties.pk],
        )
