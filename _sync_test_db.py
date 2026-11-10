"""Sync test_kms database with migrations 0024 and 0025."""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname='test_kms', user='postgres', password='postgres',
    host='localhost', port='5432'
)
conn.autocommit = True
cur = conn.cursor()

alter_cmds = [
    # Migration 0024
    'ALTER TABLE chemked_value_units DROP COLUMN IF EXISTS uncertainty_bound',
    'ALTER TABLE chemked_laminar_burning_velocity_measurement DROP COLUMN IF EXISTS laminar_burning_velocity_uncertainty_bound',
    'ALTER TABLE chemked_rate_coefficient DROP COLUMN IF EXISTS rate_coefficient_uncertainty_bound',
    'ALTER TABLE chemked_rate_coefficient ADD COLUMN IF NOT EXISTS rate_coefficient_upper_uncertainty double precision',
    'ALTER TABLE chemked_rate_coefficient ADD COLUMN IF NOT EXISTS rate_coefficient_lower_uncertainty double precision',
    # Migration 0025
    'ALTER TABLE chemked_common_properties ADD COLUMN IF NOT EXISTS pressure_lower_uncertainty double precision',
    'ALTER TABLE chemked_common_properties ADD COLUMN IF NOT EXISTS pressure_rise_lower_uncertainty double precision',
    'ALTER TABLE chemked_common_properties ADD COLUMN IF NOT EXISTS pressure_rise_upper_uncertainty double precision',
    'ALTER TABLE chemked_common_properties ADD COLUMN IF NOT EXISTS pressure_upper_uncertainty double precision',
    'ALTER TABLE chemked_datapoints ADD COLUMN IF NOT EXISTS pressure_lower_uncertainty double precision',
    'ALTER TABLE chemked_datapoints ADD COLUMN IF NOT EXISTS pressure_upper_uncertainty double precision',
    'ALTER TABLE chemked_datapoints ADD COLUMN IF NOT EXISTS temperature_lower_uncertainty double precision',
    'ALTER TABLE chemked_datapoints ADD COLUMN IF NOT EXISTS temperature_upper_uncertainty double precision',
    'ALTER TABLE chemked_ignition_delay ADD COLUMN IF NOT EXISTS ignition_delay_lower_uncertainty double precision',
    'ALTER TABLE chemked_ignition_delay ADD COLUMN IF NOT EXISTS ignition_delay_upper_uncertainty double precision',
    'ALTER TABLE chemked_laminar_burning_velocity_measurement ADD COLUMN IF NOT EXISTS laminar_burning_velocity_lower_uncertainty double precision',
    'ALTER TABLE chemked_laminar_burning_velocity_measurement ADD COLUMN IF NOT EXISTS laminar_burning_velocity_upper_uncertainty double precision',
    'ALTER TABLE chemked_rcm_data ADD COLUMN IF NOT EXISTS compressed_pressure_lower_uncertainty double precision',
    'ALTER TABLE chemked_rcm_data ADD COLUMN IF NOT EXISTS compressed_pressure_upper_uncertainty double precision',
    'ALTER TABLE chemked_rcm_data ADD COLUMN IF NOT EXISTS compressed_temperature_lower_uncertainty double precision',
    'ALTER TABLE chemked_rcm_data ADD COLUMN IF NOT EXISTS compressed_temperature_upper_uncertainty double precision',
]

for cmd in alter_cmds:
    cur.execute(cmd)
    print(f'OK: {cmd[:80]}')

now = datetime.now().isoformat()
for mig in ['0024_remove_uncertainty_bound', '0025_add_upper_lower_uncertainty_fields']:
    cur.execute(
        "INSERT INTO django_migrations (app, name, applied) "
        "SELECT 'chemked_database', %s, %s "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM django_migrations WHERE app='chemked_database' AND name=%s"
        ")",
        (mig, now, mig),
    )
    print(f'Migration record: {mig}')

cur.close()
conn.close()
print('Done syncing test_kms')
