from rest_framework import serializers
from drf_writable_nested.serializers import NestedCreateMixin
from django.contrib.contenttypes.models import ContentType

from database import models
from database.scripts.import_rmg_models import get_species_hash, get_reaction_hash
from database.models.kinetic_data import validate_kinetics_data
from api.models import Revision


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


class EfficiencySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Efficiency
        exclude = ["kinetics"]


class KineticsSerializer(NestedModelSerializer):
    efficiency_set = EfficiencySerializer(many=True)
    models = [models.Efficiency]
    data = serializers.JSONField(source="raw_data", validators=[validate_kinetics_data])

    class Meta:
        model = models.Kinetics
        exclude = ["species", "raw_data"]


class SpeciesNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SpeciesName
        exclude = ["kinetic_model"]

    def validate_data(self, value):
        return validate_kinetics_data(value)


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


class RevisionSerializer(serializers.ModelSerializer):
    content_type = serializers.CharField(source="content_type.model")
    created_by = serializers.CharField(source="created_by.username")
    reviewed_by = serializers.CharField(source="reviewed_by.username", default=None)

    class Meta:
        model = Revision
        fields = "__all__"
