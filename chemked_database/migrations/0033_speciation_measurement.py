"""Replace the four speciation types with one ChemKED 0.5 speciation measurement.

The jet stirred reactor, outlet concentration, concentration time profile and burner
stabilized flame speciation types stored one row per condition and lost profiles. PyKED
converts the four ReSpecTh types into one speciation measurement, whose datapoint is
SpeciationMeasurementDatapoint with its independent variables, concentration profiles and
auxiliary profiles. Datasets of the old types are deleted by 0032 first.

Also: ValueWithUnit.uncertainty_sourcetype, the missing ChemKED common properties, the
concentration composition kinds and PyKED apparatus kinds, and an optional datapoint
temperature (a speciation datapoint may give none).
"""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chemked_database', '0032_delete_old_speciation_datasets'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='concentrationtimeprofilemeasurementdatapoint',
            name='datapoint',
        ),
        migrations.RemoveField(
            model_name='concentrationtimeprofilemeasurementdatapoint',
            name='timeshift_amount_quantity',
        ),
        migrations.RemoveField(
            model_name='concentrationtimeprofilemeasurementdatapoint',
            name='tracked_species',
        ),
        migrations.RemoveField(
            model_name='jetstirredreactormeasurementdatapoint',
            name='datapoint',
        ),
        migrations.RemoveField(
            model_name='jetstirredreactormeasurementdatapoint',
            name='environment_temperature_quantity',
        ),
        migrations.RemoveField(
            model_name='jetstirredreactormeasurementdatapoint',
            name='measured_composition',
        ),
        migrations.RemoveField(
            model_name='outletconcentrationmeasurementdatapoint',
            name='datapoint',
        ),
        migrations.RemoveField(
            model_name='outletconcentrationmeasurementdatapoint',
            name='initial_composition',
        ),
        migrations.RemoveField(
            model_name='outletconcentrationmeasurementdatapoint',
            name='measured_composition',
        ),
        migrations.RemoveField(
            model_name='outletconcentrationmeasurementdatapoint',
            name='residence_time_quantity',
        ),
        migrations.RemoveField(
            model_name='outletconcentrationmeasurementdatapoint',
            name='volumetric_flow_quantity',
        ),
        migrations.AlterModelOptions(
            name='concentrationprofile',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='experimentdatapoint',
            options={'ordering': ['dataset', 'temperature', 'id']},
        ),
        migrations.RemoveField(
            model_name='concentrationprofile',
            name='time_units',
        ),
        migrations.AddField(
            model_name='commonproperties',
            name='ignition_delay_quantity',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='common_ignition_delay_sets', to='chemked_database.valuewithunit'),
        ),
        migrations.AddField(
            model_name='commonproperties',
            name='volumetric_flow_in_reference_state_quantity',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='common_volumetric_flow_ref_state_sets', to='chemked_database.valuewithunit'),
        ),
        migrations.AddField(
            model_name='concentrationprofile',
            name='evaluated_standard_deviation',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='concentrationprofile',
            name='evaluated_standard_deviation_method',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='concentrationprofile',
            name='evaluated_standard_deviation_sourcetype',
            field=models.CharField(blank=True, choices=[('reported', 'Reported'), ('estimated', 'Estimated'), ('calculated', 'Calculated'), ('digitized', 'Digitized')], max_length=100),
        ),
        migrations.AddField(
            model_name='concentrationprofile',
            name='evaluated_standard_deviation_type',
            field=models.CharField(blank=True, choices=[('absolute', 'Absolute'), ('relative', 'Relative')], max_length=20),
        ),
        migrations.AddField(
            model_name='concentrationprofile',
            name='lower_uncertainty',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='concentrationprofile',
            name='uncertainty',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='concentrationprofile',
            name='uncertainty_sourcetype',
            field=models.CharField(blank=True, choices=[('reported', 'Reported'), ('estimated', 'Estimated'), ('calculated', 'Calculated'), ('digitized', 'Digitized')], help_text='How the uncertainty was obtained', max_length=100),
        ),
        migrations.AddField(
            model_name='concentrationprofile',
            name='uncertainty_text',
            field=models.CharField(blank=True, help_text='Raw uncertainty string if provided as text', max_length=100),
        ),
        migrations.AddField(
            model_name='concentrationprofile',
            name='uncertainty_type',
            field=models.CharField(blank=True, choices=[('absolute', 'Absolute'), ('relative', 'Relative')], max_length=20),
        ),
        migrations.AddField(
            model_name='concentrationprofile',
            name='upper_uncertainty',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='valuewithunit',
            name='uncertainty_sourcetype',
            field=models.CharField(blank=True, choices=[('reported', 'Reported'), ('estimated', 'Estimated'), ('calculated', 'Calculated'), ('digitized', 'Digitized')], help_text='How the uncertainty was obtained (reported, estimated, calculated, digitized)', max_length=100),
        ),
        migrations.AlterField(
            model_name='apparatus',
            name='kind',
            field=models.CharField(choices=[('shock tube', 'Shock Tube'), ('rapid compression machine', 'Rapid Compression Machine'), ('stirred reactor', 'Stirred Reactor'), ('stirred reactor (quartz)', 'Stirred Reactor (Quartz)'), ('stirred reactor (fused silica)', 'Stirred Reactor (Fused Silica)'), ('stirred reaction', 'Stirred Reaction'), ('jet stirred reactor', 'Jet Stirred Reactor'), ('flow reactor', 'Flow Reactor'), ('flow reactor (quartz)', 'Flow Reactor (Quartz)'), ('flow reactor (alumina)', 'Flow Reactor (Alumina)'), ('flow reactor (recrystallized alumina)', 'Flow Reactor (Recrystallized Alumina)'), ('flame', 'Flame'), ('outwardly propagating spherical flame', 'Outwardly Propagating Spherical Flame'), ('heat flux burner', 'Heat Flux Burner'), ('burner stabilized flame', 'Burner Stabilized Flame'), ('counterflow twin flame', 'Counterflow Twin Flame'), ('bunsen burner', 'Bunsen Burner')], help_text='Type of apparatus', max_length=50),
        ),
        migrations.AlterField(
            model_name='composition',
            name='kind',
            field=models.CharField(choices=[('mole fraction', 'Mole Fraction'), ('mass fraction', 'Mass Fraction'), ('mole percent', 'Mole Percent'), ('mol/cm3', 'mol/cm3'), ('mol/m3', 'mol/m3'), ('mol/L', 'mol/L'), ('mol/dm3', 'mol/dm3')], max_length=20),
        ),
        migrations.AlterField(
            model_name='compositionspecies',
            name='amount',
            field=models.FloatField(blank=True, help_text='Amount (units depend on composition kind)', null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='concentrationprofile',
            name='values',
            field=models.JSONField(help_text='Rows of [independent values..., amount] or [independent values..., amount, uncertainty]'),
        ),
        migrations.AlterField(
            model_name='experimentdatapoint',
            name='temperature',
            field=models.FloatField(blank=True, help_text='Temperature in Kelvin', null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='experimentdataset',
            name='experiment_type',
            field=models.CharField(choices=[('ignition delay', 'Ignition Delay'), ('laminar burning velocity measurement', 'Laminar Burning Velocity Measurement'), ('speciation measurement', 'Speciation Measurement'), ('rate coefficient', 'Rate Coefficient'), ('thermochemical', 'Thermochemical')], default='ignition delay', max_length=100),
        ),
        migrations.CreateModel(
            name='SpeciationMeasurementDatapoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('environment_temperature', models.FloatField(blank=True, help_text='Environment temperature in K', null=True)),
                ('residence_time', models.FloatField(blank=True, help_text='Residence time in s', null=True)),
                ('reactor_volume', models.FloatField(blank=True, help_text='Reactor volume in m³', null=True)),
                ('reactor_length', models.FloatField(blank=True, help_text='Flow reactor length in m', null=True)),
                ('reactor_diameter', models.FloatField(blank=True, help_text='Flow reactor diameter in m', null=True)),
                ('flow_rate', models.FloatField(blank=True, help_text='Mass flow rate in kg m⁻² s⁻¹', null=True)),
                ('volumetric_flow_in_reference_state', models.FloatField(blank=True, help_text='Volumetric flow rate at the reference state in m³/s', null=True)),
                ('pressure_in_reference_state', models.FloatField(blank=True, help_text='Reference state pressure in Pa', null=True)),
                ('temperature_in_reference_state', models.FloatField(blank=True, help_text='Reference state temperature in K', null=True)),
                ('global_heat_exchange_coefficient', models.FloatField(blank=True, help_text='Jet stirred reactor heat exchange coefficient in W m⁻² K⁻¹', null=True)),
                ('exchange_area', models.FloatField(blank=True, help_text='Jet stirred reactor heat exchange area in m²', null=True)),
                ('laminar_burning_velocity', models.FloatField(blank=True, help_text='Burning velocity of a burner stabilized flame in m/s', null=True)),
                ('timeshift_target', models.CharField(blank=True, help_text='Species name used as time shift reference', max_length=255)),
                ('timeshift_type', models.CharField(blank=True, choices=[('half decrease', 'Half Decrease'), ('relative decrease', 'Relative Decrease')], help_text='Method for determining time shift', max_length=30)),
                ('timeshift_amount', models.FloatField(blank=True, help_text='Time shift amount in s', null=True)),
                ('datapoint', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='speciation_measurement', to='chemked_database.experimentdatapoint')),
                ('environment_temperature_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('exchange_area_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('flow_rate_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('global_heat_exchange_coefficient_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('laminar_burning_velocity_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('pressure_in_reference_state_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('reactor_diameter_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('reactor_length_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('reactor_volume_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('residence_time_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('temperature_in_reference_state_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('timeshift_amount_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
                ('volumetric_flow_in_reference_state_quantity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='chemked_database.valuewithunit')),
            ],
            options={
                'verbose_name': 'Speciation Measurement Datapoint',
                'verbose_name_plural': 'Speciation Measurement Datapoints',
                'db_table': 'chemked_speciation_measurement',
            },
        ),
        migrations.CreateModel(
            name='IndependentVariable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('column', models.PositiveSmallIntegerField(help_text='Column of the variable in the profile rows')),
                ('name', models.CharField(choices=[('temperature', 'Temperature'), ('residence-time', 'Residence Time'), ('distance', 'Distance'), ('time', 'Time'), ('equivalence-ratio', 'Equivalence Ratio'), ('initial-composition', 'Initial Composition'), ('pressure', 'Pressure')], max_length=30)),
                ('units', models.CharField(max_length=50)),
                ('primary', models.BooleanField(blank=True, help_text='The swept axis, for plotting and comparison', null=True)),
                ('species_name', models.CharField(blank=True, max_length=255)),
                ('inchi', models.CharField(blank=True, max_length=500)),
                ('smiles', models.CharField(blank=True, max_length=500)),
                ('measurement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='independent_variables', to='chemked_database.speciationmeasurementdatapoint')),
            ],
            options={
                'db_table': 'chemked_independent_variables',
                'ordering': ['measurement', 'column'],
            },
        ),
        migrations.CreateModel(
            name='AuxiliaryProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('profile_type', models.CharField(choices=[('temperature', 'Temperature'), ('pressure', 'Pressure'), ('volume', 'Volume'), ('velocity', 'Velocity')], max_length=30)),
                ('independent_name', models.CharField(help_text='Independent variable: distance or time', max_length=30)),
                ('independent_units', models.CharField(max_length=50)),
                ('quantity_units', models.CharField(max_length=50)),
                ('values', models.JSONField(help_text='Rows of [independent, value] or [independent, value, uncertainty]')),
                ('measurement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='auxiliary_profiles', to='chemked_database.speciationmeasurementdatapoint')),
            ],
            options={
                'db_table': 'chemked_auxiliary_profiles',
                'ordering': ['id'],
            },
        ),
        migrations.AlterField(
            model_name='concentrationprofile',
            name='measurement',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='concentration_profiles', to='chemked_database.speciationmeasurementdatapoint'),
        ),
        migrations.DeleteModel(
            name='BurnerStabilizedFlameSpeciationMeasurementDatapoint',
        ),
        migrations.DeleteModel(
            name='JetStirredReactorMeasurementDatapoint',
        ),
        migrations.DeleteModel(
            name='OutletConcentrationMeasurementDatapoint',
        ),
        migrations.AddConstraint(
            model_name='independentvariable',
            constraint=models.UniqueConstraint(fields=('measurement', 'column'), name='chemked_unique_independent_variable_column'),
        ),
        migrations.DeleteModel(
            name='ConcentrationTimeProfileMeasurementDatapoint',
        ),
    ]
