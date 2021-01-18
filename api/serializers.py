from rest_framework import serializers
from django.db import transaction
from drf_writable_nested.serializers import NestedCreateMixin
from drf_writable_nested.mixins import UniqueFieldsMixin

from database import models
from database.scripts.import_rmg_models import get_species_hash, get_reaction_hash
from database.models.kinetic_data import validate_kinetics_data
from api.models import Revision


class FormulaSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Formula
        fields = "__all__"


class StructureSerializer(UniqueFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = models.Structure
        exclude = ["isomer"]


class IsomerSerializer(NestedCreateMixin, serializers.ModelSerializer):
    structure_set = StructureSerializer(many=True)
    formula = serializers.CharField(source="formula.formula")

    class Meta:
        model = models.Isomer
        fields = "__all__"

    def get_structure_serializer(self, validated_data):
        structure_serializer = StructureSerializer(
            many=True, data=validated_data.pop("structure_set")
        )

        return structure_serializer, validated_data

    def get_formula(self, validated_data):
        formula_str = validated_data.pop("formula")["formula"]
        formula = models.Formula.objects.get_or_create(formula=formula_str)[0]

        return formula, validated_data

    def create(self, validated_data):
        structure_serializer, validated_data = self.get_structure_serializer(validated_data)
        formula, validated_data = self.get_formula(validated_data)

        instance = models.Isomer.objects.create(formula=formula, **validated_data)

        structure_serializer.is_valid()
        structure_serializer.save(isomer=instance)

        return instance

    def update(self, instance, validated_data):
        with transaction.atomic():
            structure_serializer, validated_data = self.get_structure_serializer(validated_data)
            formula, validated_data = self.get_formula(validated_data)

            instance.formula = formula
            instance.save()

            structure_serializer.is_valid()
            structure_serializer.save(isomer=instance)

            return super().update(instance, validated_data)


class SpeciesSerializer(serializers.ModelSerializer):
    new_isomers = IsomerSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = models.Species
        exclude = ["hash"]
        extra_kwargs = {"isomers": {"required": False}}

    def to_internal_value(self, data):
        internal_value = super().to_internal_value(data)
        new_isomers = data.get("new_isomers")
        if new_isomers:
            internal_value["new_isomers"] = new_isomers

        return internal_value

    def validate(self, attrs):
        if not attrs.get("isomers") and not attrs.get("new_isomers"):
            raise serializers.ValidationError("Must have either 'isomers' or 'new_isomers' field")

        if not attrs.get("new_isomers"):
            isomers = attrs.get("isomers")
            existing_species = models.Species.objects.filter(hash=get_species_hash(isomers))
            if existing_species:
                raise serializers.ValidationError(
                    f"Another species already exists with isomers {isomers}"
                )

        return super().validate(attrs)

    def update_isomers(self, instance, isomers_data, new_isomers_data):
        with transaction.atomic():
            instance.isomers.clear()
            isomers = isomers_data
            if new_isomers_data:
                serializer = IsomerSerializer(many=True, data=new_isomers_data)
                serializer.is_valid()
                new_isomers = serializer.save()
                isomers.extend(new_isomers)

            instance.isomers.add(*isomers)

        return instance

    def update(self, instance, validated_data):
        instance = self.update_isomers(
            instance, validated_data.pop("isomers", []), validated_data.pop("new_isomers", None)
        )

        return super().update(instance, validated_data)

    def create(self, validated_data):
        isomers_data = validated_data.pop("isomers", [])
        new_isomers_data = validated_data.pop("new_isomers", None)

        with transaction.atomic():
            instance = super().create(validated_data)

            return self.update_isomers(instance, isomers_data, new_isomers_data)


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


class KineticsSerializer(serializers.ModelSerializer):
    efficiency_set = EfficiencySerializer(many=True)
    models = [models.Efficiency]

    def validate_diff(self, value):
        return validate_kinetics_data(value)

    class Meta:
        model = models.Kinetics
        exclude = ["species", "raw_data"]


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


class KineticModelSerializer(serializers.ModelSerializer):
    speciesname_set = SpeciesNameSerializer(many=True)
    thermocomment_set = ThermoCommentSerializer(many=True)
    transportcomment_set = TransportCommentSerializer(many=True)
    kineticscomment_set = KineticsCommentSerializer(many=True)

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
