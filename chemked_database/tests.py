import os
import tempfile

from django.test import TestCase

from chemked_database.utils.chemistry import rdkit_available

from .import_dispatcher import create_experiment_extension
from .models import (
	Apparatus,
	ApparatusKind,
	CommonProperties,
	Composition,
	CompositionKind,
	CompositionSpecies,
	EvaluatedStandardDeviationMethod,
	ExperimentDataset,
	ExperimentDatapoint,
	ExperimentType,
	LaminarBurningVelocityMeasurementDatapoint,
	IgnitionDelayDatapoint,
	IgnitionTarget,
	IgnitionType,
	MeasurementType,
	RateCoefficientDatapoint,
	RCMData,
	SpeciesThermo,
	ConcentrationTimeProfileMeasurementDatapoint,
	TimeHistory,
	TimeHistoryType,
	UncertaintyType,
	ValueWithUnit,
	VolumeHistory,
)
from .chemked_adapter import (
	ChemKEDDictAdapter,
	_Author,
	_EvaluatedStandardDeviation,
	_Reaction,
	_Reference,
	_Uncertainty,
	_parse_chemked_value,
)
from pyked.batch_convert import convert_file


class ChemKEDModelTests(TestCase):
	def setUp(self):
		self.apparatus = Apparatus.objects.create(
			kind=ApparatusKind.RCM,
			institution="Test Institute",
			facility="RCM-1",
		)
		self.dataset = ExperimentDataset.objects.create(
			chemked_file_path="rcm_test_001.yaml",
			file_version=0,
			chemked_version="0.4.1",
			apparatus=self.apparatus,
		)
		self.common_properties = CommonProperties.objects.create(
			dataset=self.dataset,
			composition=None,
			ignition_target=IgnitionTarget.PRESSURE,
			ignition_type=IgnitionType.DDT_MAX,
			pressure=101325.0,
		)
		composition = Composition.objects.create(kind=CompositionKind.MOLE_FRACTION)
		CompositionSpecies.objects.create(
			composition=composition,
			species_name="CH4",
			inchi="InChI=1S/CH4/h1H4",
			amount=0.05,
		)
		CompositionSpecies.objects.create(
			composition=composition,
			species_name="O2",
			inchi="InChI=1S/O2/c1-2",
			amount=0.21,
		)
		CompositionSpecies.objects.create(
			composition=composition,
			species_name="N2",
			inchi="InChI=1S/N2/c1-2",
			amount=0.74,
		)
		self.common_properties.composition = composition
		self.common_properties.save()

	def test_common_properties_fallback(self):
		datapoint = ExperimentDatapoint.objects.create(
			dataset=self.dataset,
			temperature=950.0,
			pressure=101325.0,
		)
		IgnitionDelayDatapoint.objects.create(
			datapoint=datapoint,
			ignition_delay=0.003,
		)

		self.assertEqual(datapoint.get_ignition_target(), IgnitionTarget.PRESSURE)
		self.assertEqual(datapoint.get_ignition_type(), IgnitionType.DDT_MAX)
		self.assertEqual(datapoint.get_composition_kind(), CompositionKind.MOLE_FRACTION)
		self.assertEqual(datapoint.get_composition(), self.common_properties.composition)

	def test_datapoint_overrides(self):
		composition = Composition.objects.create(kind=CompositionKind.MASS_FRACTION)
		CompositionSpecies.objects.create(
			composition=composition,
			species_name="H2",
			inchi="InChI=1S/H2/h1H",
			amount=0.1,
		)
		CompositionSpecies.objects.create(
			composition=composition,
			species_name="O2",
			inchi="InChI=1S/O2/c1-2",
			amount=0.3,
		)
		CompositionSpecies.objects.create(
			composition=composition,
			species_name="N2",
			inchi="InChI=1S/N2/c1-2",
			amount=0.6,
		)

		datapoint = ExperimentDatapoint.objects.create(
			dataset=self.dataset,
			temperature=900.0,
			pressure=150000.0,
			composition=composition,
		)
		IgnitionDelayDatapoint.objects.create(
			datapoint=datapoint,
			ignition_delay=0.002,
			ignition_target=IgnitionTarget.OH,
			ignition_type=IgnitionType.MAX,
		)

		self.assertEqual(datapoint.get_ignition_target(), IgnitionTarget.OH)
		self.assertEqual(datapoint.get_ignition_type(), IgnitionType.MAX)
		self.assertEqual(datapoint.get_composition_kind(), CompositionKind.MASS_FRACTION)
		self.assertEqual(datapoint.get_composition(), datapoint.composition)

	def test_time_and_volume_history(self):
		datapoint = ExperimentDatapoint.objects.create(
			dataset=self.dataset,
			temperature=1000.0,
			pressure=202650.0,
		)
		IgnitionDelayDatapoint.objects.create(
			datapoint=datapoint,
			ignition_delay=0.004,
		)

		time_history = TimeHistory.objects.create(
			datapoint=datapoint,
			history_type=TimeHistoryType.VOLUME,
			time_units="s",
			quantity_units="cm^3",
			values=[[0.0, 100.0], [0.01, 50.0], [0.02, 30.0]],
		)
		volume_history = VolumeHistory.objects.create(
			datapoint=datapoint,
			time_units="s",
			volume_units="cm^3",
			values=[[0.0, 100.0], [0.01, 60.0], [0.02, 35.0]],
		)

		self.assertEqual(time_history.num_points, 3)
		self.assertEqual(len(volume_history.values), 3)

	def test_composition_species_optional_fields(self):
		composition = Composition.objects.create(kind=CompositionKind.MOLE_FRACTION)
		datapoint = ExperimentDatapoint.objects.create(
			dataset=self.dataset,
			temperature=1100.0,
			pressure=150000.0,
			composition=composition,
		)
		IgnitionDelayDatapoint.objects.create(
			datapoint=datapoint,
			ignition_delay=0.001,
		)

		species = CompositionSpecies.objects.create(
			composition=composition,
			species_name="CH4",
			inchi="InChI=1S/CH4/h1H4",
			amount=0.05,
			amount_uncertainty=0.002,
			amount_uncertainty_type="relative",
			atomic_composition=[{"element": "C", "amount": 1}, {"element": "H", "amount": 4}],
		)

		self.assertEqual(species.species_name, "CH4")
		self.assertIsNotNone(species.atomic_composition)

		thermo = SpeciesThermo.objects.create(
			species=species,
			t_range_1="300",
			t_range_2="1000",
			t_range_3="3000",
			coeff_1=1.0,
			coeff_2=1.0,
			coeff_3=1.0,
			coeff_4=1.0,
			coeff_5=1.0,
			coeff_6=1.0,
			coeff_7=1.0,
			coeff_8=1.0,
			coeff_9=1.0,
			coeff_10=1.0,
			coeff_11=1.0,
			coeff_12=1.0,
			coeff_13=1.0,
			coeff_14=1.0,
		)

		self.assertEqual(thermo.t_range_1, "300")

	def test_laminar_burning_velocity_extension(self):
		datapoint = ExperimentDatapoint.objects.create(
			dataset=self.dataset,
			temperature=700.0,
			pressure=101325.0,
		)
		lbv = LaminarBurningVelocityMeasurementDatapoint.objects.create(
			datapoint=datapoint,
			laminar_burning_velocity=0.35,
			laminar_burning_velocity_quantity=ValueWithUnit.objects.create(
				value=0.35, units='m/s',
				uncertainty=0.02, uncertainty_type='relative',
			),
			stretch=50.0,
		)

		self.assertEqual(lbv.laminar_burning_velocity, 0.35)

	def test_concentration_time_profile_extension(self):
		datapoint = ExperimentDatapoint.objects.create(
			dataset=self.dataset,
			temperature=1200.0,
			pressure=101325.0,
		)
		composition = Composition.objects.create(kind=CompositionKind.MOLE_FRACTION)
		tracked = CompositionSpecies.objects.create(
			composition=composition,
			species_name="CO",
			amount=0.01,
		)
		profile = ConcentrationTimeProfileMeasurementDatapoint.objects.create(
			datapoint=datapoint,
			tracked_species=tracked,
			values=[[0.0, 0.01], [0.001, 0.009]],
		)

		self.assertEqual(profile.tracked_species.species_name, "CO")

	def test_dispatcher_creates_extensions(self):
		datapoint = ExperimentDatapoint.objects.create(
			dataset=self.dataset,
			temperature=800.0,
			pressure=101325.0,
		)

		ignition = create_experiment_extension(
			datapoint,
			ExperimentType.IGNITION_DELAY,
			{"ignition_delay": 0.005},
		)
		self.assertIsInstance(ignition, IgnitionDelayDatapoint)

		flame = create_experiment_extension(
			datapoint,
			ExperimentType.LAMINAR_BURNING_VELOCITY,
			{"laminar_burning_velocity": 0.4},
		)
		self.assertIsInstance(flame, LaminarBurningVelocityMeasurementDatapoint)

		composition = Composition.objects.create(kind=CompositionKind.MOLE_FRACTION)
		tracked = CompositionSpecies.objects.create(
			composition=composition,
			species_name="CO2",
			amount=0.1,
		)
		profile = create_experiment_extension(
			datapoint,
			ExperimentType.CONCENTRATION_TIME_PROFILE,
			{
				"tracked_species": tracked,
				"values": [[0.0, 0.1], [0.5, 0.08]],
			},
		)
		self.assertIsInstance(profile, ConcentrationTimeProfileMeasurementDatapoint)

	def test_inchi_inference_helpers(self):
		if not rdkit_available():
			self.skipTest("RDKit not available")
		composition = Composition.objects.create(kind=CompositionKind.MOLE_FRACTION)
		species = CompositionSpecies.objects.create(
			composition=composition,
			species_name="C2H6O",
			inchi="InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
			amount=0.1,
		)
		self.assertTrue(species.smiles)
		self.assertTrue(any(item["element"] == "C" for item in species.atomic_composition or []))

	def test_value_with_unit_links(self):
		temperature_quantity = ValueWithUnit.objects.create(value=1200.0, units="kelvin")
		pressure_quantity = ValueWithUnit.objects.create(value=1.5, units="bar")

		datapoint = ExperimentDatapoint.objects.create(
			dataset=self.dataset,
			temperature=temperature_quantity.value,
			pressure=pressure_quantity.value,
			temperature_quantity=temperature_quantity,
			pressure_quantity=pressure_quantity,
		)

		self.assertEqual(datapoint.temperature_quantity.units, "kelvin")
		self.assertEqual(datapoint.pressure_quantity.units, "bar")


# ---------------------------------------------------------------------------
# ReSpecTh v2 Converter / Parser Tests
# ---------------------------------------------------------------------------

# Minimal kdetermination XML with branching ratio, multiple reactions,
# per-datapoint uncertainty + evaluated standard deviation, bibliography
# number/type, method, and comment.
KDETERMINATION_XML = """\
<kdetermination>
    <fileAuthor>Test Author</fileAuthor>
    <fileDOI>10.24388/k99999901</fileDOI>
    <fileVersion><major>1</major><minor>0</minor></fileVersion>
    <ReSpecThVersion><major>2</major><minor>5</minor></ReSpecThVersion>
    <firstPublicationDate>2025-01-01</firstPublicationDate>
    <lastModificationDate>2025-06-01</lastModificationDate>
    <bibliographyLink>
        <description>Smith, J., J. Chem. Phys. 100 (2020), 1-10</description>
        <referenceDOI>10.1234/test</referenceDOI>
        <location>Main article</location>
        <table>Table 1</table>
        <figure>Figure 2</figure>
        <details>
            <author>Smith, John and Doe, Jane</author>
            <journal>J. Chem. Phys.</journal>
            <number>42</number>
            <pages>1-10</pages>
            <title>A Test Paper</title>
            <type>Journal Article</type>
            <volume>100</volume>
            <year>2020</year>
        </details>
    </bibliographyLink>
    <reaction preferredKey="A + B = C + D" order="2" bulkgas="Ar">
        <reactant1>A</reactant1><reactant2>B</reactant2>
        <product1>C</product1><product2>D</product2>
    </reaction>
    <reaction preferredKey="A + B = E + F" order="2" bulkgas="N2">
        <reactant1>A</reactant1><reactant2>B</reactant2>
        <product1>E</product1><product2>F</product2>
    </reaction>
    <commonProperties>
        <property name="evaluated standard deviation" sourcetype="estimated"
                  units="unitless" reference="branching ratio" kind="absolute">
            <value>0.01</value>
        </property>
    </commonProperties>
    <dataGroup id="dg1">
        <property name="temperature"                   id="x1" label="T"       sourcetype="reported"  units="K"        />
        <property name="branching ratio"               id="x2" label="alpha"   sourcetype="reported"  units="unitless" />
        <property name="uncertainty"                   id="x3" label="d_alpha" sourcetype="estimated" units="unitless"
                  reference="branching ratio" kind="absolute" bound="plusminus" />
        <property name="evaluated standard deviation"  id="x4" label="sigma"   sourcetype="estimated" units="unitless"
                  reference="branching ratio" kind="absolute" />
        <dataPoint><x1>1800</x1><x2>0.590</x2><x3>0.020</x3><x4>0.010</x4></dataPoint>
        <dataPoint><x1>2000</x1><x2>0.620</x2><x3>0.030</x3><x4>0.015</x4></dataPoint>
    </dataGroup>
    <method>Shock tube, LP-frequency modulation</method>
    <comment>Test comment line 1</comment>
    <comment>Test comment line 2</comment>
</kdetermination>
"""

# Experiment XML with global temperature uncertainty + global ESD
EXPERIMENT_XML_GLOBAL_UNC = """\
<experiment>
    <fileAuthor>Lab Author</fileAuthor>
    <fileDOI>10.24388/x99999901</fileDOI>
    <fileVersion><major>2</major><minor>0</minor></fileVersion>
    <ReSpecThVersion><major>2</major><minor>3</minor></ReSpecThVersion>
    <firstPublicationDate>2013-11-25</firstPublicationDate>
    <lastModificationDate>2020-11-18</lastModificationDate>
    <bibliographyLink>
        <description>Author A, Combust Flame 112 (1998), 1-15</description>
        <referenceDOI>10.1016/test</referenceDOI>
        <location>Main Article</location>
        <details>
            <author>Author, A</author>
            <journal>Combust Flame</journal>
            <volume>112</volume>
            <year>1998</year>
        </details>
    </bibliographyLink>
    <experimentType>laminar burning velocity measurement</experimentType>
    <apparatus><kind>flame</kind></apparatus>
    <commonProperties>
        <property name="pressure"      label="P"  sourcetype="reported" units="atm"><value>0.5</value></property>
        <property name="temperature"   label="T"  sourcetype="reported" units="K"><value>298</value></property>
        <property name="uncertainty"   label="dT" sourcetype="reported" units="K"
                  reference="temperature" kind="absolute" bound="plusminus"><value>3</value></property>
        <property name="evaluated standard deviation" sourcetype="estimated" units="cm/s"
                  reference="laminar burning velocity" kind="absolute"
                  method="generic uncertainty"><value>2.0</value></property>
    </commonProperties>
    <dataGroup id="dg1">
        <property name="laminar burning velocity" id="x1" label="Sl" sourcetype="reported" units="mm/s" />
        <property name="composition" id="x2" label="X_H2" sourcetype="calculated" units="mole fraction">
            <speciesLink preferredKey="H2" CAS="1333-74-0" InChI="1S/H2/h1H" SMILES="[HH]" chemName="hydrogen" />
        </property>
        <property name="composition" id="x3" label="X_O2" sourcetype="calculated" units="mole fraction">
            <speciesLink preferredKey="O2" CAS="7782-44-7" InChI="1S/O2/c1-2" SMILES="O=O" chemName="oxygen" />
        </property>
        <dataPoint><x1>640</x1><x2>0.16</x2><x3>0.18</x3></dataPoint>
        <dataPoint><x1>1370</x1><x2>0.24</x2><x3>0.16</x3></dataPoint>
    </dataGroup>
</experiment>
"""

# Experiment XML with BOTH per-species uncertainty AND per-species ESD in
# commonProperties (models methanol_NOx x00202010 pattern).
EXPERIMENT_XML_SPECIES_UNC_ESD = """\
<experiment>
    <fileAuthor>Lab Author 2</fileAuthor>
    <fileDOI>10.24388/x99999902</fileDOI>
    <fileVersion><major>1</major><minor>0</minor></fileVersion>
    <ReSpecThVersion><major>2</major><minor>3</minor></ReSpecThVersion>
    <firstPublicationDate>2020-01-01</firstPublicationDate>
    <lastModificationDate>2020-06-01</lastModificationDate>
    <bibliographyLink>
        <description>Test Ref</description>
        <referenceDOI>10.9999/test2</referenceDOI>
    </bibliographyLink>
    <experimentType>jet stirred reactor measurement</experimentType>
    <apparatus><kind>jet stirred reactor</kind></apparatus>
    <commonProperties>
        <property name="pressure"      label="P"   sourcetype="reported" units="atm"><value>10</value></property>
        <property name="temperature"   label="T"   sourcetype="reported" units="K"><value>900</value></property>
        <property name="uncertainty"   label="d_T" sourcetype="reported" units="K"
                  reference="temperature" kind="absolute" bound="plusminus"><value>10</value></property>
        <property name="initial composition" sourcetype="reported">
            <component>
                <speciesLink preferredKey="CH3OH" CAS="67-56-1"
                             InChI="1S/CH4O/c1-2/h2H,1H3" SMILES="CO" chemName="methanol" />
                <amount units="mole fraction">0.009</amount>
            </component>
            <component>
                <speciesLink preferredKey="O2" CAS="7782-44-7"
                             InChI="1S/O2/c1-2" SMILES="O=O" chemName="oxygen" />
                <amount units="mole fraction">0.0135</amount>
            </component>
            <component>
                <speciesLink preferredKey="N2" CAS="7727-37-9"
                             InChI="1S/N2/c1-2" SMILES="N#N" chemName="nitrogen" />
                <amount units="mole fraction">0.9775</amount>
            </component>
        </property>
        <property name="uncertainty" label="d_[CH3OH]" sourcetype="estimated"
                  units="mole fraction" reference="composition" kind="relative" bound="plusminus">
            <speciesLink preferredKey="CH3OH" CAS="67-56-1"
                         InChI="1S/CH4O/c1-2/h2H,1H3" SMILES="CO" chemName="methanol" />
            <value>0.10</value>
        </property>
        <property name="uncertainty" label="d_[CO]" sourcetype="reported"
                  units="mole fraction" reference="composition" kind="relative" bound="plusminus">
            <speciesLink preferredKey="CO" CAS="630-08-0"
                         InChI="1S/CO/c1-2" SMILES="[C-]#[O+]" chemName="carbon monoxide" />
            <value>0.10</value>
        </property>
        <property name="evaluated standard deviation" sourcetype="estimated"
                  units="mole fraction" reference="composition" kind="absolute"
                  method="combined from scatter and reported uncertainty">
            <speciesLink preferredKey="CH3OH" CAS="67-56-1"
                         InChI="1S/CH4O/c1-2/h2H,1H3" SMILES="CO" chemName="methanol" />
            <value>0.000261</value>
        </property>
        <property name="evaluated standard deviation" sourcetype="estimated"
                  units="mole fraction" reference="composition" kind="absolute"
                  method="combined from scatter and reported uncertainty">
            <speciesLink preferredKey="CO" CAS="630-08-0"
                         InChI="1S/CO/c1-2" SMILES="[C-]#[O+]" chemName="carbon monoxide" />
            <value>0.000539</value>
        </property>
    </commonProperties>
    <dataGroup id="dg1">
        <property name="composition" id="x1" label="X_CH3OH" sourcetype="digitized" units="mole fraction">
            <speciesLink preferredKey="CH3OH" CAS="67-56-1"
                         InChI="1S/CH4O/c1-2/h2H,1H3" SMILES="CO" chemName="methanol" />
        </property>
        <property name="composition" id="x2" label="X_CO" sourcetype="digitized" units="mole fraction">
            <speciesLink preferredKey="CO" CAS="630-08-0"
                         InChI="1S/CO/c1-2" SMILES="[C-]#[O+]" chemName="carbon monoxide" />
        </property>
        <property name="temperature" id="x3" label="T" sourcetype="reported" units="K" />
        <dataPoint><x1>0.008</x1><x2>0.001</x2><x3>900</x3></dataPoint>
        <dataPoint><x1>0.006</x1><x2>0.003</x2><x3>950</x3></dataPoint>
    </dataGroup>
</experiment>
"""


def _write_xml(content):
	"""Write XML string to a temporary file and return the path."""
	fd, path = tempfile.mkstemp(suffix='.xml')
	os.write(fd, content.encode('utf-8'))
	os.close(fd)
	return path


class BatchConvertBibliographyTests(TestCase):
	"""Tests for bibliography/reference parsing via batch_convert."""

	def test_bibliography_fields(self):
		path = _write_xml(KDETERMINATION_XML)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		ref = d['reference']
		self.assertEqual(ref['doi'], '10.1234/test')
		self.assertEqual(ref['journal'], 'J. Chem. Phys.')
		self.assertEqual(ref['volume'], 100)
		self.assertEqual(ref['pages'], '1-10')
		self.assertEqual(ref['year'], 2020)
		self.assertEqual(ref['title'], 'A Test Paper')
		self.assertEqual(ref['number'], '42')
		self.assertEqual(ref['publication-type'], 'Journal Article')
		self.assertEqual(ref['location'], 'Main article')
		self.assertEqual(ref['table'], 'Table 1')
		self.assertEqual(ref['figure'], 'Figure 2')

	def test_bibliography_authors(self):
		path = _write_xml(KDETERMINATION_XML)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		authors = d['reference']['authors']
		self.assertEqual(len(authors), 2)
		self.assertEqual(authors[0]['name'], 'John Smith')
		self.assertEqual(authors[1]['name'], 'Jane Doe')

	def test_adapter_reference(self):
		path = _write_xml(KDETERMINATION_XML)
		try:
			data = ChemKEDDictAdapter(convert_file(path))
		finally:
			os.unlink(path)

		ref = data.reference
		self.assertIsNotNone(ref)
		self.assertEqual(ref.doi, '10.1234/test')
		self.assertEqual(ref.year, 2020)
		self.assertEqual(len(ref.authors), 2)


class BatchConvertReactionsTests(TestCase):
	"""Tests for reaction parsing via batch_convert."""

	def test_multiple_reactions(self):
		path = _write_xml(KDETERMINATION_XML)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		rxns = d['reactions']
		self.assertEqual(len(rxns), 2)
		self.assertEqual(rxns[0]['preferred-key'], 'A + B = C + D')
		self.assertEqual(rxns[0]['order'], 2)
		self.assertEqual(rxns[0]['bulk-gas'], 'Ar')
		self.assertEqual(rxns[0]['reactants'], ['A', 'B'])
		self.assertEqual(rxns[0]['products'], ['C', 'D'])
		self.assertEqual(rxns[1]['preferred-key'], 'A + B = E + F')

	def test_adapter_reaction_convenience(self):
		path = _write_xml(KDETERMINATION_XML)
		try:
			data = ChemKEDDictAdapter(convert_file(path))
		finally:
			os.unlink(path)

		self.assertEqual(len(data.reactions), 2)
		self.assertEqual(data.reaction.preferred_key, data.reactions[0].preferred_key)
		self.assertEqual(data.reaction.preferred_key, 'A + B = C + D')


class BatchConvertCommentsTests(TestCase):
	"""Tests for comment parsing."""

	def test_comments_parsed(self):
		path = _write_xml(KDETERMINATION_XML)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		self.assertEqual(len(d['comments']), 2)
		self.assertIn('Test comment line 1', d['comments'])
		self.assertIn('Test comment line 2', d['comments'])


class BatchConvertMethodTests(TestCase):
	"""Tests for method parsing."""

	def test_method_parsed(self):
		path = _write_xml(KDETERMINATION_XML)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		self.assertEqual(d['method'], 'Shock tube, LP-frequency modulation')


class BatchConvertMetadataTests(TestCase):
	"""Tests for file metadata parsing."""

	def test_file_metadata(self):
		path = _write_xml(KDETERMINATION_XML)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		self.assertEqual(d['file-type'], 'kdetermination')
		self.assertEqual(d['file-authors'][0]['name'], 'Test Author')
		self.assertEqual(d['file-doi'], '10.24388/k99999901')
		self.assertEqual(d['respecth-version'], '2.5')
		self.assertEqual(d['first-publication-date'], '2025-01-01')
		self.assertEqual(d['last-modification-date'], '2025-06-01')

	def test_experiment_type_and_apparatus(self):
		path = _write_xml(EXPERIMENT_XML_GLOBAL_UNC)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		self.assertEqual(d['experiment-type'], 'laminar burning velocity measurement')
		self.assertEqual(d['apparatus']['kind'], 'flame')

	def test_adapter_metadata(self):
		path = _write_xml(KDETERMINATION_XML)
		try:
			data = ChemKEDDictAdapter(convert_file(path))
		finally:
			os.unlink(path)

		self.assertEqual(data.file_type, 'kdetermination')
		self.assertEqual(data.file_author, 'Test Author')
		self.assertEqual(data.file_doi, '10.24388/k99999901')


class BatchConvertUncertaintyTests(TestCase):
	"""Tests for uncertainty handling via batch_convert (inline in property values)."""

	def test_global_temperature_uncertainty_in_common(self):
		"""Global uncertainty inlined into common-properties temperature value."""
		path = _write_xml(EXPERIMENT_XML_GLOBAL_UNC)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		temp = d['common-properties']['temperature']
		self.assertIsInstance(temp, list)
		self.assertEqual(len(temp), 2)
		self.assertIn('298', temp[0])
		unc_dict = temp[1]
		self.assertEqual(unc_dict['uncertainty-type'], 'absolute')
		self.assertIn('3', str(unc_dict['uncertainty']))

	def test_per_species_uncertainty_in_composition(self):
		"""Per-species uncertainty inlined into composition species amounts."""
		path = _write_xml(EXPERIMENT_XML_SPECIES_UNC_ESD)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		comp = d['common-properties']['composition']
		species_by_name = {s['species-name']: s for s in comp['species']}
		# CH3OH should have uncertainty inlined
		ch3oh = species_by_name['CH3OH']
		self.assertIsInstance(ch3oh['amount'], list)
		self.assertTrue(len(ch3oh['amount']) >= 2)
		meta = ch3oh['amount'][1]
		self.assertAlmostEqual(float(meta['uncertainty']), 0.10)
		self.assertEqual(meta['uncertainty-type'], 'relative')

	def test_adapter_global_uncertainty(self):
		"""Adapter extracts global uncertainty from common-properties inline dicts."""
		path = _write_xml(EXPERIMENT_XML_GLOBAL_UNC)
		try:
			data = ChemKEDDictAdapter(convert_file(path))
		finally:
			os.unlink(path)

		temp_uncs = [u for u in data.uncertainties if u.reference == 'temperature']
		self.assertEqual(len(temp_uncs), 1)
		self.assertAlmostEqual(temp_uncs[0].value, 3.0)


class BatchConvertEvaluatedStdDevTests(TestCase):
	"""Tests for evaluated standard deviation handling via batch_convert."""

	def test_per_species_esd_in_composition(self):
		"""Per-species ESD is inlined into composition species amount metadata."""
		path = _write_xml(EXPERIMENT_XML_SPECIES_UNC_ESD)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		comp = d['common-properties']['composition']
		species_by_name = {s['species-name']: s for s in comp['species']}
		ch3oh = species_by_name['CH3OH']
		meta = ch3oh['amount'][1]
		self.assertAlmostEqual(float(meta['evaluated-standard-deviation']), 0.000261)
		self.assertEqual(meta['evaluated-standard-deviation-type'], 'absolute')
		self.assertIn('combined from scatter', meta.get('evaluated-standard-deviation-method', ''))

	def test_global_esd_inlined_on_property(self):
		"""Global ESD (e.g. for LBV) is inlined into the datapoint property."""
		path = _write_xml(EXPERIMENT_XML_GLOBAL_UNC)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		# ESD for laminar burning velocity is inlined into each datapoint's LBV value
		dp0 = d['datapoints'][0]
		lbv = dp0['laminar-burning-velocity']
		self.assertIsInstance(lbv, list)
		self.assertTrue(len(lbv) >= 2)
		meta = lbv[1]
		self.assertIn('evaluated-standard-deviation', meta)


class BatchConvertDatapointTests(TestCase):
	"""Tests for datapoint parsing via batch_convert."""

	def test_kdetermination_datapoints(self):
		path = _write_xml(KDETERMINATION_XML)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		dps = d['datapoints']
		self.assertEqual(len(dps), 2)
		# First datapoint
		self.assertIn('temperature', dps[0])
		self.assertIn('branching-ratio', dps[0])
		# Temperature value
		temp_val, temp_units, _ = _parse_chemked_value(dps[0]['temperature'])
		self.assertEqual(temp_val, 1800)
		self.assertEqual(temp_units, 'K')
		# Branching ratio with inline uncertainty+ESD
		br_val, br_units, br_meta = _parse_chemked_value(dps[0]['branching-ratio'])
		self.assertAlmostEqual(br_val, 0.59)
		self.assertIsNotNone(br_meta)
		self.assertAlmostEqual(float(br_meta['uncertainty']), 0.02)
		self.assertAlmostEqual(float(br_meta['evaluated-standard-deviation']), 0.01)

	def test_experiment_datapoints(self):
		path = _write_xml(EXPERIMENT_XML_GLOBAL_UNC)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		dps = d['datapoints']
		self.assertEqual(len(dps), 2)
		# LBV measurement
		lbv_val, lbv_units, _ = _parse_chemked_value(dps[0]['laminar-burning-velocity'])
		self.assertEqual(lbv_val, 640)
		self.assertEqual(lbv_units, 'mm/s')
		# Composition in datapoint
		comp = dps[0]['composition']
		self.assertIn('species', comp)
		species_names = {s['species-name'] for s in comp['species']}
		self.assertEqual(species_names, {'H2', 'O2'})

	def test_experiment_species_link_preserved(self):
		"""Species identity (InChI, CAS) is preserved in datapoints."""
		path = _write_xml(EXPERIMENT_XML_GLOBAL_UNC)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		comp = d['datapoints'][0]['composition']
		h2 = next(s for s in comp['species'] if s['species-name'] == 'H2')
		self.assertEqual(h2['InChI'], '1S/H2/h1H')


class BatchConvertCommonPropertiesTests(TestCase):
	"""Tests for common-properties parsing via batch_convert."""

	def test_common_scalar_properties(self):
		path = _write_xml(EXPERIMENT_XML_GLOBAL_UNC)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		common = d['common-properties']
		# Pressure
		p_val, p_units, _ = _parse_chemked_value(common['pressure'])
		self.assertAlmostEqual(p_val, 0.5)
		self.assertEqual(p_units, 'atm')
		# Temperature (has inline uncertainty)
		t_val, t_units, t_meta = _parse_chemked_value(common['temperature'])
		self.assertEqual(t_val, 298)
		self.assertEqual(t_units, 'K')

	def test_initial_composition(self):
		path = _write_xml(EXPERIMENT_XML_SPECIES_UNC_ESD)
		try:
			d = convert_file(path)
		finally:
			os.unlink(path)

		comp = d['common-properties']['composition']
		self.assertEqual(comp['kind'], 'mole fraction')
		species_by_name = {s['species-name']: s for s in comp['species']}
		self.assertEqual(len(species_by_name), 3)
		self.assertAlmostEqual(species_by_name['CH3OH']['amount'][0], 0.009)

	def test_adapter_initial_composition(self):
		path = _write_xml(EXPERIMENT_XML_SPECIES_UNC_ESD)
		try:
			data = ChemKEDDictAdapter(convert_file(path))
		finally:
			os.unlink(path)

		self.assertEqual(len(data.initial_composition), 3)
		ch3oh = next(c for c in data.initial_composition if c.species_name == 'CH3OH')
		self.assertAlmostEqual(ch3oh.amount, 0.009)


# ---------------------------------------------------------------------------
# Model field tests for new/updated models
# ---------------------------------------------------------------------------

class RateCoefficientDatapointModelTests(TestCase):
	"""Tests for RateCoefficientDatapoint model fields."""

	def setUp(self):
		self.apparatus = Apparatus.objects.filter(kind=ApparatusKind.SHOCK_TUBE).first() or Apparatus.objects.create(kind=ApparatusKind.SHOCK_TUBE)
		self.dataset = ExperimentDataset.objects.create(
			chemked_file_path='rc_test.yaml',
			file_version=0,
			chemked_version='0.4.1',
			experiment_type=ExperimentType.RATE_COEFFICIENT,
			apparatus=self.apparatus,
		)

	def test_rate_coefficient_with_all_fields(self):
		rc_vu = ValueWithUnit.objects.create(
			value=1.23e10,
			units='cm3 mol-1 s-1',
			sourcetype='reported',
			uncertainty=5e8,
			uncertainty_type=UncertaintyType.ABSOLUTE,
			evaluated_standard_deviation=2.5e8,
			evaluated_standard_deviation_type=UncertaintyType.ABSOLUTE,
			evaluated_standard_deviation_sourcetype='estimated',
		)

		dp = ExperimentDatapoint.objects.create(
			dataset=self.dataset, temperature=1800, pressure=101325,
		)
		rc = RateCoefficientDatapoint.objects.create(
			datapoint=dp,
			measurement_type=MeasurementType.RATE_COEFFICIENT,
			rate_coefficient=1.23e10,
			rate_coefficient_units='cm3 mol-1 s-1',
			rate_coefficient_quantity=rc_vu,
			reaction='A + B = C + D',
			reaction_order=2,
			bulk_gas='Ar',
			method='Shock tube, LP-FM',
		)

		rc.refresh_from_db()
		self.assertEqual(rc.measurement_type, MeasurementType.RATE_COEFFICIENT)
		self.assertAlmostEqual(rc.rate_coefficient, 1.23e10)
		self.assertIsNotNone(rc.rate_coefficient_quantity)
		self.assertAlmostEqual(rc.rate_coefficient_quantity.uncertainty, 5e8)
		self.assertAlmostEqual(rc.rate_coefficient_quantity.evaluated_standard_deviation, 2.5e8)
		self.assertEqual(rc.reaction, 'A + B = C + D')
		self.assertEqual(rc.reaction_order, 2)
		self.assertEqual(rc.bulk_gas, 'Ar')
		self.assertEqual(rc.method, 'Shock tube, LP-FM')

	def test_upper_lower_uncertainty(self):
		"""Test PyKED-style upper/lower uncertainty fields on ValueWithUnit."""
		rc_vu = ValueWithUnit.objects.create(
			value=2.5e9,
			units='cm3 mol-1 s-1',
			upper_uncertainty=1e8,
			lower_uncertainty=2e8,
			uncertainty_type=UncertaintyType.ABSOLUTE,
		)
		dp = ExperimentDatapoint.objects.create(
			dataset=self.dataset, temperature=1900, pressure=101325,
		)
		rc = RateCoefficientDatapoint.objects.create(
			datapoint=dp,
			measurement_type=MeasurementType.RATE_COEFFICIENT,
			rate_coefficient=2.5e9,
			rate_coefficient_units='cm3 mol-1 s-1',
			rate_coefficient_quantity=rc_vu,
		)
		rc.refresh_from_db()
		self.assertAlmostEqual(rc.rate_coefficient_quantity.upper_uncertainty, 1e8)
		self.assertAlmostEqual(rc.rate_coefficient_quantity.lower_uncertainty, 2e8)
		self.assertIsNone(rc.rate_coefficient_quantity.uncertainty)

	def test_branching_ratio_measurement_type(self):
		dp = ExperimentDatapoint.objects.create(
			dataset=self.dataset, temperature=2000, pressure=0,
		)
		rc = RateCoefficientDatapoint.objects.create(
			datapoint=dp,
			measurement_type=MeasurementType.BRANCHING_RATIO,
			rate_coefficient=0.62,
			rate_coefficient_units='unitless',
		)

		rc.refresh_from_db()
		self.assertEqual(rc.measurement_type, MeasurementType.BRANCHING_RATIO)
		self.assertAlmostEqual(rc.rate_coefficient, 0.62)

	def test_str_representation(self):
		dp = ExperimentDatapoint.objects.create(
			dataset=self.dataset, temperature=1500, pressure=0,
		)
		rc = RateCoefficientDatapoint.objects.create(
			datapoint=dp,
			rate_coefficient=1.0e12,
			rate_coefficient_units='cm3 mol-1 s-1',
		)
		self.assertIn('1.00e+12', str(rc))

	def test_str_representation_none(self):
		dp = ExperimentDatapoint.objects.create(
			dataset=self.dataset, temperature=1500, pressure=0,
		)
		rc = RateCoefficientDatapoint.objects.create(
			datapoint=dp,
			rate_coefficient=None,
		)
		self.assertIn('n/a', str(rc))


class ValueWithUnitESDFieldsTests(TestCase):
	"""Tests for ValueWithUnit inline evaluated standard deviation fields."""

	def test_value_with_unit_esd_fields(self):
		vu = ValueWithUnit.objects.create(
			value=1200.0,
			units='K',
			evaluated_standard_deviation=15.0,
			evaluated_standard_deviation_type=UncertaintyType.ABSOLUTE,
			evaluated_standard_deviation_sourcetype='estimated',
			evaluated_standard_deviation_method=EvaluatedStandardDeviationMethod.GENERIC_UNCERTAINTY,
		)

		vu.refresh_from_db()
		self.assertAlmostEqual(vu.evaluated_standard_deviation, 15.0)
		self.assertEqual(vu.evaluated_standard_deviation_type, UncertaintyType.ABSOLUTE)
		self.assertEqual(vu.evaluated_standard_deviation_method,
		                 EvaluatedStandardDeviationMethod.GENERIC_UNCERTAINTY)

	def test_value_with_unit_uncertainty_bound(self):
		"""Test that symmetric uncertainty is stored in the uncertainty field (no bound)."""
		vu = ValueWithUnit.objects.create(
			value=5.0,
			units='atm',
			uncertainty=0.5,
			uncertainty_type=UncertaintyType.ABSOLUTE,
		)

		vu.refresh_from_db()
		self.assertAlmostEqual(vu.uncertainty, 0.5)
		self.assertIsNone(vu.upper_uncertainty)
		self.assertIsNone(vu.lower_uncertainty)

	def test_value_with_unit_upper_lower_uncertainty(self):
		"""Test upper/lower uncertainty fields on ValueWithUnit (PyKED convention)."""
		vu = ValueWithUnit.objects.create(
			value=10.0,
			units='K',
			upper_uncertainty=2.0,
			lower_uncertainty=3.0,
			uncertainty_type=UncertaintyType.ABSOLUTE,
		)

		vu.refresh_from_db()
		self.assertIsNone(vu.uncertainty)
		self.assertAlmostEqual(vu.upper_uncertainty, 2.0)
		self.assertAlmostEqual(vu.lower_uncertainty, 3.0)


class CompositionSpeciesUncertaintyESDTests(TestCase):
	"""Tests for CompositionSpecies amount_uncertainty and amount_evaluated_standard_deviation fields."""

	def test_separate_uncertainty_and_esd(self):
		composition = Composition.objects.create(kind=CompositionKind.MOLE_FRACTION)
		species = CompositionSpecies.objects.create(
			composition=composition,
			species_name='CH3OH',
			inchi='InChI=1S/CH4O/c1-2/h2H,1H3',
			amount=0.009,
			amount_uncertainty=0.10,
			amount_uncertainty_type=UncertaintyType.RELATIVE,
			amount_uncertainty_sourcetype='estimated',
			amount_evaluated_standard_deviation=0.000261,
			amount_evaluated_standard_deviation_type=UncertaintyType.ABSOLUTE,
			amount_evaluated_standard_deviation_sourcetype='estimated',
			amount_evaluated_standard_deviation_method=EvaluatedStandardDeviationMethod.COMBINED_SCATTER_REPORTED,
		)

		species.refresh_from_db()
		# Uncertainty fields
		self.assertAlmostEqual(species.amount_uncertainty, 0.10)
		self.assertEqual(species.amount_uncertainty_type, UncertaintyType.RELATIVE)
		self.assertEqual(species.amount_uncertainty_sourcetype, 'estimated')
		# ESD fields (separate)
		self.assertAlmostEqual(species.amount_evaluated_standard_deviation, 0.000261)
		self.assertEqual(species.amount_evaluated_standard_deviation_type, UncertaintyType.ABSOLUTE)
		self.assertEqual(species.amount_evaluated_standard_deviation_method,
		                 EvaluatedStandardDeviationMethod.COMBINED_SCATTER_REPORTED)


class MeasurementTypeEnumTests(TestCase):
	"""Tests for the MeasurementType enum choices."""

	def test_rate_coefficient_choice(self):
		self.assertEqual(MeasurementType.RATE_COEFFICIENT, 'rate coefficient')
		self.assertEqual(MeasurementType.RATE_COEFFICIENT.label, 'Rate Coefficient')

	def test_branching_ratio_choice(self):
		self.assertEqual(MeasurementType.BRANCHING_RATIO, 'branching ratio')
		self.assertEqual(MeasurementType.BRANCHING_RATIO.label, 'Branching Ratio')

	def test_uncertainty_bound_removed(self):
		"""UncertaintyBound enum was removed; upper/lower uncertainty replaces it."""
		# Verify UncertaintyBound is no longer importable from models
		import chemked_database.models as m
		self.assertFalse(hasattr(m, 'UncertaintyBound'))

	def test_esd_method_choices(self):
		self.assertEqual(EvaluatedStandardDeviationMethod.GENERIC_UNCERTAINTY, 'generic uncertainty')
		self.assertEqual(EvaluatedStandardDeviationMethod.COMBINED_SCATTER_REPORTED,
		                 'combined from scatter and reported uncertainty')
		self.assertEqual(EvaluatedStandardDeviationMethod.STATISTICAL_SCATTER, 'statistical scatter')


class ExperimentDatasetMetadataTests(TestCase):
	"""Tests for new ExperimentDataset metadata fields."""

	def test_rate_coefficient_experiment_type(self):
		apparatus = Apparatus.objects.filter(kind=ApparatusKind.SHOCK_TUBE).first() or Apparatus.objects.create(kind=ApparatusKind.SHOCK_TUBE)
		dataset = ExperimentDataset.objects.create(
			chemked_file_path='k_test.yaml',
			experiment_type=ExperimentType.RATE_COEFFICIENT,
			apparatus=apparatus,
			file_doi='10.24388/k00000001',
			respecth_version='2.5',
			method='ab initio CBS-QB3',
			comments=['Comment A', 'Comment B'],
		)

		dataset.refresh_from_db()
		self.assertEqual(dataset.experiment_type, ExperimentType.RATE_COEFFICIENT)
		self.assertEqual(dataset.file_doi, '10.24388/k00000001')
		self.assertEqual(dataset.respecth_version, '2.5')
		self.assertEqual(dataset.method, 'ab initio CBS-QB3')
		self.assertEqual(dataset.comments, ['Comment A', 'Comment B'])


# ---------------------------------------------------------------------------
# Converter Dataclass Tests
# ---------------------------------------------------------------------------

class AdapterDataclassTests(TestCase):
	"""Tests for adapter dataclass defaults and field behaviour."""

	def test_uncertainty_defaults(self):
		unc = _Uncertainty(value=5.0)
		self.assertEqual(unc.reference, '')
		self.assertEqual(unc.kind, 'absolute')
		self.assertEqual(unc.bound, 'plusminus')
		self.assertIsNone(unc.species_name)

	def test_uncertainty_with_species(self):
		unc = _Uncertainty(value=0.10, reference='composition', species_name='CH4')
		self.assertEqual(unc.species_name, 'CH4')
		self.assertEqual(unc.reference, 'composition')

	def test_evaluated_standard_deviation_defaults(self):
		esd = _EvaluatedStandardDeviation(species_name='O2', value=0.001)
		self.assertEqual(esd.units, 'mole fraction')
		self.assertEqual(esd.kind, 'absolute')
		self.assertEqual(esd.method, '')

	def test_reference_with_number_and_type(self):
		ref = _Reference(
			number='42',
			publication_type='Journal Article',
		)
		self.assertEqual(ref.number, '42')
		self.assertEqual(ref.publication_type, 'Journal Article')

	def test_reaction_defaults(self):
		rxn = _Reaction(preferred_key='A = B')
		self.assertEqual(rxn.reactants, [])
		self.assertEqual(rxn.products, [])
		self.assertIsNone(rxn.order)
		self.assertEqual(rxn.bulk_gas, '')


# ---------------------------------------------------------------------------
# Real XML file integration tests (if ReSpecTh data available)
# ---------------------------------------------------------------------------

RESPECTH_DIR = '/Users/lekiaprosper/Documents/CoMoChEng/Prometheus/ReSpecTh'


class RealXMLParserTests(TestCase):
	"""Integration tests parsing real ReSpecTh XML files via batch_convert + adapter."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.k_branching_xml = os.path.join(
			RESPECTH_DIR, 'thermal_DeNOx_direct_v2.4', 'k00299019.xml')
		cls.x_lbv_unc_xml = os.path.join(
			RESPECTH_DIR, 'indirect', 'hydrogen', 'H2_indirect_v2_3', 'x20000026_x.xml')
		cls.x_species_unc_esd_xml = os.path.join(
			RESPECTH_DIR, 'indirect', 'methanol_NOx', 'MeOH_NOx_indirect_v2_3', 'x00202010.xml')

	def test_k00299019_branching_ratio(self):
		if not os.path.isfile(self.k_branching_xml):
			self.skipTest('ReSpecTh k00299019.xml not available')
		raw = convert_file(self.k_branching_xml)
		data = ChemKEDDictAdapter(raw)

		self.assertEqual(data.file_type, 'kdetermination')
		self.assertEqual(len(data.reactions), 2)
		self.assertEqual(data.reactions[0].preferred_key, 'NH2 + NO = NNH + OH')
		self.assertEqual(data.reactions[1].preferred_key, 'NH2 + NO = N2 + H2O')
		self.assertEqual(len(raw['datapoints']), 15)

		# Bibliography
		self.assertEqual(data.reference.number, '40')
		self.assertEqual(data.reference.publication_type, 'Journal Article')
		self.assertEqual(data.reference.year, 2002)

		# Datapoints contain branching ratio with inline uncertainty+ESD
		dp0 = raw['datapoints'][0]
		self.assertIn('branching-ratio', dp0)

		# Comment
		self.assertTrue(len(data.comments) >= 1)

		# Method
		self.assertIn('Shock tube', data.method)

	def test_x20000026_global_temperature_uncertainty(self):
		if not os.path.isfile(self.x_lbv_unc_xml):
			self.skipTest('ReSpecTh x20000026_x.xml not available')
		raw = convert_file(self.x_lbv_unc_xml)
		data = ChemKEDDictAdapter(raw)

		self.assertEqual(data.file_type, 'experiment')
		self.assertEqual(data.experiment_type, 'laminar burning velocity measurement')

		# Global temperature uncertainty via adapter
		temp_uncs = [u for u in data.uncertainties if u.reference == 'temperature']
		self.assertEqual(len(temp_uncs), 1)
		self.assertEqual(temp_uncs[0].value, 3.0)
		self.assertIsNone(temp_uncs[0].species_name)

	def test_x00202010_species_uncertainty_and_esd(self):
		if not os.path.isfile(self.x_species_unc_esd_xml):
			self.skipTest('ReSpecTh x00202010.xml not available')
		raw = convert_file(self.x_species_unc_esd_xml)
		data = ChemKEDDictAdapter(raw)

		# Per-species uncertainties from adapter
		species_uncs = [u for u in data.uncertainties if u.species_name is not None]
		self.assertTrue(len(species_uncs) >= 2)
		species_names_unc = {u.species_name for u in species_uncs}
		self.assertIn('CH3OH', species_names_unc)

		# Per-species ESD
		self.assertTrue(len(data.evaluated_standard_deviations) >= 2)
		esd_species = {e.species_name for e in data.evaluated_standard_deviations}
		self.assertIn('CH3OH', esd_species)

		# All ESD entries have method
		for esd in data.evaluated_standard_deviations:
			self.assertTrue(esd.method, f'ESD for {esd.species_name} missing method')
