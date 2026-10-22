"""
Helpers to attach experiment-type-specific extension models to generic datapoints,
and to import ChemKED YAML outside the web upload form (e.g. from the REST API).
"""

from typing import Optional, Union

import yaml

from .models import (
    ExperimentType,
    ExperimentDatapoint,
    BurnerStabilizedFlameSpeciationMeasurementDatapoint,
    ConcentrationTimeProfileMeasurementDatapoint,
    IgnitionDelayDatapoint,
    JetStirredReactorMeasurementDatapoint,
    LaminarBurningVelocityMeasurementDatapoint,
    OutletConcentrationMeasurementDatapoint,
)


def create_experiment_extension(
    datapoint: ExperimentDatapoint,
    experiment_type: str,
    payload: Optional[dict] = None,
):
    """
    Create an extension model for the given experiment type.

    Args:
        datapoint: Base ExperimentDatapoint instance.
        experiment_type: One of ExperimentType values.
        payload: Optional dict of fields for the extension model.

    Returns:
        Created extension model instance, or None if experiment type unsupported.
    """
    payload = payload or {}

    if experiment_type == ExperimentType.IGNITION_DELAY:
        return IgnitionDelayDatapoint.objects.create(datapoint=datapoint, **payload)
    if experiment_type == ExperimentType.LAMINAR_BURNING_VELOCITY:
        return LaminarBurningVelocityMeasurementDatapoint.objects.create(datapoint=datapoint, **payload)
    if experiment_type == ExperimentType.CONCENTRATION_TIME_PROFILE:
        return ConcentrationTimeProfileMeasurementDatapoint.objects.create(datapoint=datapoint, **payload)
    if experiment_type == ExperimentType.JSR_MEASUREMENT:
        return JetStirredReactorMeasurementDatapoint.objects.create(datapoint=datapoint, **payload)
    if experiment_type == ExperimentType.OUTLET_CONCENTRATION:
        return OutletConcentrationMeasurementDatapoint.objects.create(datapoint=datapoint, **payload)
    if experiment_type == ExperimentType.BSFS_MEASUREMENT:
        return BurnerStabilizedFlameSpeciationMeasurementDatapoint.objects.create(datapoint=datapoint, **payload)

    return None


def import_chemked_to_db(
    content: Union[bytes, str],
    filename: str,
    file_author: str = "",
    dataset_name: Optional[str] = None,
):
    """
    Import ChemKED YAML into the database with the web upload's importer.

    Uses the same code path as a confirmed upload on /chemked/dataset/upload/
    (DatasetUploadView._import_from_chemked_dict), so datasets created here and
    from the web form are identical.

    Args:
        content: ChemKED YAML document (bytes or str).
        filename: Original file name; its trailing number becomes the dataset ID.
        file_author: Contributor name recorded as a file author.
        dataset_name: Optional dataset name; generated from the file if omitted.

    Returns:
        The created or updated ExperimentDataset.
    """
    # Imported here because views imports most of the app.
    from .views import DatasetUploadView

    chemked_dict = yaml.safe_load(content)
    if not isinstance(chemked_dict, dict):
        raise ValueError(f"{filename} is not a ChemKED YAML mapping")
    return DatasetUploadView()._import_from_chemked_dict(
        chemked_dict, filename, file_author, custom_name=dataset_name
    )
