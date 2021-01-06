from rest_framework import serializers
from drf_writable_nested.serializers import NestedCreateMixin
from database import models

from database.scripts.import_rmg_models import get_species_hash, get_reaction_hash


class NestedModelSerializer(NestedCreateMixin, serializers.ModelSerializer):
    def update(self, instance, validated_data):
        for model in self.models:
            new_objects = []
            related_name = f"{model.__name__.lower()}_set"
            for data in validated_data.pop(related_name):
                data[self.Meta.model.__name__.lower()] = instance
                obj, _ = model.objects.get_or_create(**data)
                new_objects.append(obj.pk)

            getattr(instance, related_name).exclude(pk__in=new_objects).delete()

        return super().update(instance, validated_data)


class FormulaSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Formula
        fields = "__all__"


class IsomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Isomer
        fields = "__all__"


class SpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Species
        exclude = ["hash"]

    def create(self, validated_data):
        isomers = models.Isomer.objects.filter(pk__in=validated_data["isomers"])
        validated_data["hash"] = get_species_hash(isomers)

        return super().update(validated_data)


class StoichiometrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Stoichiometry
        exclude = ["reaction"]


class ReactionSerializer(NestedModelSerializer):
    stoichiometry_set = StoichiometrySerializer(many=True)
    models = [models.Stoichiometry]

    class Meta:
        model = models.Reaction
        exclude = ["species", "hash"]

    def create(self, validated_data):
        stoich_data = [
            (d.get("coeff"), d.get("species")) for d in validated_data["stoichiometry_set"]
        ]
        validated_data["hash"] = get_reaction_hash(stoich_data)

        return super().create(validated_data)


class ThermoSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Thermo
        fields = "__all__"


class TransportSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Transport
        fields = "__all__"


class KineticsDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.KineticsData
        fields = "__all__"


class KineticsDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.KineticsData
        fields = "__all__"


class ArrheniusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Arrhenius
        fields = "__all__"


class ArrheniusEPSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ArrheniusEP
        fields = "__all__"


class MultiArrheniusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MultiArrhenius
        fields = "__all__"


class PressureSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Pressure
        exclude = ["pdep_arrhenius"]


class PDepArrheniusSerializer(serializers.ModelSerializer):
    pressure_set = PressureSerializer(many=True)

    class Meta:
        model = models.PDepArrhenius
        exclude = ["arrhenius"]


class MultiPDepArrheniusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MultiPDepArrhenius
        fields = "__all__"


class ChebyshevSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Chebyshev
        fields = "__all__"


class ThirdBodySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ThirdBody
        fields = "__all__"


class LindemannSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Lindemann
        fields = "__all__"


class TroeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Troe
        fields = "__all__"


class EfficiencySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Efficiency
        exclude = ["kinetics_data"]


class BaseKineticsDataSerializer(serializers.ModelSerializer):
    kineticsdata = KineticsDataSerializer()
    arrhenius = ArrheniusSerializer()
    arrheniusep = ArrheniusEPSerializer()
    pdeparrhenius = PDepArrheniusSerializer()
    multiarrhenius = MultiArrheniusSerializer()
    multipdeparrhenius = MultiPDepArrheniusSerializer()
    chebyshev = ChebyshevSerializer()
    thirdbody = ThirdBodySerializer()
    lindemann = LindemannSerializer()
    troe = TroeSerializer()

    efficiency_set = EfficiencySerializer(many=True)

    class Meta:
        model = models.BaseKineticsData
        exclude = ["collider_efficiencies"]


class KineticsSerializer(serializers.ModelSerializer):
    data = BaseKineticsDataSerializer()

    class Meta:
        model = models.Kinetics
        fields = "__all__"


class SpeciesNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SpeciesName
        exclude = ["kinetic_model"]


class ThermoCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ThermoComment
        exclude = ["kinetic_model"]


class TransportCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TransportComment
        exclude = ["kinetic_model"]


class KineticsCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.KineticsComment
        exclude = ["kinetic_model"]


class KineticModelSerializer(NestedModelSerializer):
    speciesname_set = SpeciesNameSerializer(many=True)
    thermocomment_set = ThermoCommentSerializer(many=True)
    transportcomment_set = TransportCommentSerializer(many=True)
    kineticscomment_set = KineticsCommentSerializer(many=True)

    models = [
        models.SpeciesName,
        models.ThermoComment,
        models.TransportComment,
        models.KineticsComment,
    ]

    class Meta:
        model = models.KineticModel
        exclude = [
            "chemkin_reactions_file",
            "chemkin_thermo_file",
            "chemkin_transport_file",
            "species",
            "kinetics",
            "thermo",
            "transport",
        ]
