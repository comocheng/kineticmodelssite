import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Iterator, Optional, Sequence

import cantera as ct
import numpy as np

try:
    from pyteck.simulation import get_ignition_delay
except ImportError:  # PyTeCK >= 0.2.6 moved it onto HomogeneousReactorSimulation
    from pyteck.simulation import HomogeneousReactorSimulation

    get_ignition_delay = HomogeneousReactorSimulation.get_ignition_delay

from database.models import KineticModel

from .simulation import get_cantera_mechanism_from_model


CT_ONE_ATM = ct.one_atm
IGNITION_TYPE_CHOICES = ('max', 'd/dt max', '1/2 max', 'd/dt max extrapolated')


@dataclass(frozen=True)
class GridDefinition:
    temperatures: tuple[float, ...]
    pressures_atm: tuple[float, ...]
    phis: tuple[float, ...]

    @property
    def total_conditions(self) -> int:
        return (
            len(self.temperatures) * len(self.pressures_atm) * len(self.phis)
        )


def default_temperature_grid() -> tuple[float, ...]:
    return tuple(np.arange(800.0, 3001.0, 100.0))


def default_pressure_grid_atm() -> tuple[float, ...]:
    pressures = np.logspace(np.log10(0.05), np.log10(500.0), 20)
    pressures = np.unique(np.sort(np.append(pressures, 1.0)))
    return tuple(float(value) for value in pressures)


def default_phi_grid() -> tuple[float, ...]:
    phi_lean = np.arange(0.05, 1.0 + 1e-9, 0.05)
    phi_rich = np.arange(1.5, 8.0 + 1e-9, 0.5)
    phis = np.unique(np.concatenate([phi_lean, phi_rich]))
    return tuple(float(value) for value in phis)


def default_grid_definition() -> GridDefinition:
    return GridDefinition(
        temperatures=default_temperature_grid(),
        pressures_atm=default_pressure_grid_atm(),
        phis=default_phi_grid(),
    )


def parse_float_sequence(raw_value: Optional[str]) -> Optional[tuple[float, ...]]:
    if raw_value is None:
        return None

    pieces = [piece.strip() for piece in raw_value.split(',') if piece.strip()]
    if not pieces:
        return tuple()

    return tuple(float(piece) for piece in pieces)


def build_grid_definition(
    temperatures: Optional[Sequence[float]] = None,
    pressures_atm: Optional[Sequence[float]] = None,
    phis: Optional[Sequence[float]] = None,
) -> GridDefinition:
    default_grid = default_grid_definition()
    return GridDefinition(
        temperatures=tuple(float(value) for value in (temperatures or default_grid.temperatures)),
        pressures_atm=tuple(float(value) for value in (pressures_atm or default_grid.pressures_atm)),
        phis=tuple(float(value) for value in (phis or default_grid.phis)),
    )


def normalize_species_label(label: str) -> str:
    return re.sub(r'\(\d+\)$', '', label).replace(' ', '').upper()


@lru_cache(maxsize=None)
def get_model_name(model_pk: int) -> str:
    return KineticModel.objects.only('model_name').get(pk=model_pk).model_name


@lru_cache(maxsize=None)
def export_mechanism_path(model_pk: int) -> str:
    model = KineticModel.objects.get(pk=model_pk)
    mechanism_path = get_cantera_mechanism_from_model(model)
    if not mechanism_path:
        raise RuntimeError(
            f'Failed to export mechanism for model {model.model_name}'
        )
    return mechanism_path


def load_gas_for_model(model_pk: int) -> ct.Solution:
    return ct.Solution(export_mechanism_path(model_pk))


def resolve_species_label(
    species_names: Sequence[str], aliases: Sequence[str]
) -> Optional[str]:
    lookup = {
        normalize_species_label(name): name
        for name in species_names
    }
    for alias in aliases:
        match = lookup.get(normalize_species_label(alias))
        if match is not None:
            return match
    return None


def methane_air_inputs_for_model(model_pk: int) -> tuple[str, str]:
    gas = load_gas_for_model(model_pk)
    species_names = gas.species_names

    fuel_label = resolve_species_label(species_names, ['CH4', 'methane'])
    o2_label = resolve_species_label(species_names, ['O2'])
    n2_label = resolve_species_label(species_names, ['N2'])

    if fuel_label is None:
        raise ValueError(
            f'No methane species label found in {get_model_name(model_pk)}'
        )
    if o2_label is None or n2_label is None:
        raise ValueError(
            'Could not resolve O2/N2 labels in '
            f'{get_model_name(model_pk)}; found only a partial oxidizer set.'
        )

    fuel = f'{fuel_label}:1'
    oxidizer = f'{o2_label}:1, {n2_label}:3.76'
    return fuel, oxidizer


def resolve_target_series(
    ignition_target: str,
    gas: ct.Solution,
    temperatures_array: np.ndarray,
    pressures_array: np.ndarray,
    species_history: dict[str, np.ndarray],
) -> tuple[str, np.ndarray]:
    normalized_target = normalize_species_label(ignition_target)
    if normalized_target == 'TEMPERATURE':
        return 'temperature', temperatures_array
    if normalized_target == 'PRESSURE':
        return 'pressure', pressures_array

    species_name = resolve_species_label(gas.species_names, [ignition_target])
    if species_name is None:
        raise ValueError(
            f"Ignition target '{ignition_target}' is not present in the mechanism."
        )

    target = species_history.get(species_name)
    if target is None or np.isnan(target).all():
        raise ValueError(
            f"Ignition target '{species_name}' could not be sampled during the simulation."
        )

    return species_name, target


def run_ignition_delay_case(
    model_pk: int,
    temperature: float,
    pressure_atm: float,
    phi: float,
    fuel: Optional[str] = None,
    oxidizer: Optional[str] = None,
    max_time: float = 10.0,
    max_steps: int = 5000,
    ignition_target: str = 'temperature',
    ignition_type: str = 'd/dt max',
    reactor_type=ct.IdealGasReactor,
) -> dict:
    if ignition_type not in IGNITION_TYPE_CHOICES:
        raise ValueError(
            f'ignition_type must be one of {IGNITION_TYPE_CHOICES}, got {ignition_type!r}.'
        )

    gas = load_gas_for_model(model_pk)

    if fuel is None or oxidizer is None:
        auto_fuel, auto_oxidizer = methane_air_inputs_for_model(model_pk)
        fuel = fuel or auto_fuel
        oxidizer = oxidizer or auto_oxidizer

    gas.TP = float(temperature), float(pressure_atm) * CT_ONE_ATM
    gas.set_equivalence_ratio(float(phi), fuel, oxidizer)

    reactor = reactor_type(gas)
    network = ct.ReactorNet([reactor])
    sampled_species_name = None
    normalized_target = normalize_species_label(ignition_target)
    if normalized_target not in {'TEMPERATURE', 'PRESSURE'}:
        sampled_species_name = resolve_species_label(gas.species_names, [ignition_target])

    times = [0.0]
    temperatures = [reactor.T]
    pressures = [reactor.thermo.P / CT_ONE_ATM]
    species_history = {}
    if sampled_species_name is not None:
        species_history[sampled_species_name] = np.asarray(
            [reactor.thermo[sampled_species_name].X[0]],
            dtype=float,
        )

    for _ in range(max_steps):
        if network.time >= max_time:
            break
        time_value = network.step()
        times.append(float(time_value))
        temperatures.append(float(reactor.T))
        pressures.append(float(reactor.thermo.P / CT_ONE_ATM))
        if sampled_species_name is not None:
            species_history[sampled_species_name] = np.append(
                species_history[sampled_species_name],
                reactor.thermo[sampled_species_name].X[0],
            )

    if len(times) < 3:
        raise RuntimeError(
            'Simulation ended before enough states were recorded.'
        )

    times_array = np.asarray(times, dtype=float)
    temperatures_array = np.asarray(temperatures, dtype=float)
    pressures_array = np.asarray(pressures, dtype=float)

    # Guard against false-positive ignition detection when using
    # temperature as the target.  For species targets (e.g. OH) the
    # temperature guard is skipped because chain-branching indicators
    # can peak even when the bulk temperature rise is modest.
    if normalize_species_label(ignition_target) == 'TEMPERATURE':
        delta_T = float(temperatures_array.max() - temperatures_array[0])
        if delta_T < 50.0:
            raise RuntimeError(
                f'No significant temperature rise detected '
                f'(delta_T = {delta_T:.1f} K < 50 K); ignition did not occur.'
            )

    target_name, target = resolve_target_series(
        ignition_target=ignition_target,
        gas=gas,
        temperatures_array=temperatures_array,
        pressures_array=pressures_array,
        species_history=species_history,
    )

    ignition_delays = get_ignition_delay(
        times_array,
        target,
        target_name,
        ignition_type,
    )

    if ignition_delays.size == 0:
        raise RuntimeError('PyTeCK ignition detection returned no ignition delays.')

    ignition_delay_s = float(ignition_delays[0])
    if ignition_delay_s <= 0.0:
        raise RuntimeError(
            'PyTeCK ignition detection did not find a valid positive ignition delay.'
        )

    return {
        'model_pk': int(model_pk),
        'model_name': get_model_name(model_pk),
        'mechanism_path': export_mechanism_path(model_pk),
        'temperature_K': float(temperature),
        'pressure_atm': float(pressure_atm),
        'phi': float(phi),
        'fuel': fuel,
        'oxidizer': oxidizer,
        'ignition_target': target_name,
        'ignition_type': ignition_type,
        'ignition_delay_s': ignition_delay_s,
        'n_saved_steps': len(times),
    }


def iter_condition_grid(grid: GridDefinition) -> Iterator[dict]:
    condition_index = 0
    for temperature in grid.temperatures:
        for pressure_atm in grid.pressures_atm:
            for phi in grid.phis:
                yield {
                    'condition_index': condition_index,
                    'temperature_K': float(temperature),
                    'pressure_atm': float(pressure_atm),
                    'phi': float(phi),
                }
                condition_index += 1


def iter_condition_grid_shard(
    grid: GridDefinition,
    task_index: int,
    task_count: int,
    limit_conditions: Optional[int] = None,
) -> Iterator[dict]:
    if task_count < 1:
        raise ValueError('task_count must be at least 1')
    if task_index < 0 or task_index >= task_count:
        raise ValueError('task_index must be in [0, task_count)')

    emitted = 0
    for condition in iter_condition_grid(grid):
        if condition['condition_index'] % task_count != task_index:
            continue
        yield condition
        emitted += 1
        if limit_conditions is not None and emitted >= limit_conditions:
            break


def get_models_for_fuel_smiles(
    fuel_smiles: str,
    limit_models: Optional[int] = None,
) -> list[KineticModel]:
    queryset = (
        KineticModel.objects
        .filter(species__isomers__structure__smiles=fuel_smiles)
        .distinct()
        .order_by('model_name')
    )
    if limit_models is not None:
        queryset = queryset[:limit_models]
    return list(queryset)


def get_models_by_pk(model_pks: Sequence[int]) -> list[KineticModel]:
    models = list(
        KineticModel.objects
        .filter(pk__in=model_pks)
        .order_by('model_name')
    )
    found_pks = {model.pk for model in models}
    missing = sorted(set(int(pk) for pk in model_pks) - found_pks)
    if missing:
        raise ValueError(f'Unknown model PK(s): {missing}')
    return models


def fixed_result_columns() -> list[str]:
    return [
        'task_index',
        'task_count',
        'condition_index',
        'model_pk',
        'model_name',
        'temperature_K',
        'pressure_atm',
        'phi',
        'ignition_target',
        'ignition_type',
        'ignition_delay_s',
        'fuel',
        'oxidizer',
        'mechanism_path',
        'n_saved_steps',
        'error',
    ]


def iter_grid_results(
    model_pks: Sequence[int],
    grid: GridDefinition,
    task_index: int = 0,
    task_count: int = 1,
    fuel: Optional[str] = None,
    oxidizer: Optional[str] = None,
    max_time: float = 10.0,
    max_steps: int = 5000,
    ignition_target: str = 'temperature',
    ignition_type: str = 'd/dt max',
    limit_conditions: Optional[int] = None,
) -> Iterator[dict]:
    for condition in iter_condition_grid_shard(
        grid=grid,
        task_index=task_index,
        task_count=task_count,
        limit_conditions=limit_conditions,
    ):
        for model_pk in model_pks:
            try:
                row = run_ignition_delay_case(
                    model_pk=model_pk,
                    temperature=condition['temperature_K'],
                    pressure_atm=condition['pressure_atm'],
                    phi=condition['phi'],
                    fuel=fuel,
                    oxidizer=oxidizer,
                    max_time=max_time,
                    max_steps=max_steps,
                    ignition_target=ignition_target,
                    ignition_type=ignition_type,
                )
                row['error'] = ''
            except Exception as exc:
                row = {
                    'model_pk': int(model_pk),
                    'model_name': get_model_name(model_pk),
                    'mechanism_path': '',
                    'temperature_K': condition['temperature_K'],
                    'pressure_atm': condition['pressure_atm'],
                    'phi': condition['phi'],
                    'fuel': fuel or '',
                    'oxidizer': oxidizer or '',
                    'ignition_target': ignition_target,
                    'ignition_type': ignition_type,
                    'ignition_delay_s': np.nan,
                    'n_saved_steps': 0,
                    'error': str(exc),
                }

            row['task_index'] = int(task_index)
            row['task_count'] = int(task_count)
            row['condition_index'] = int(condition['condition_index'])
            yield row