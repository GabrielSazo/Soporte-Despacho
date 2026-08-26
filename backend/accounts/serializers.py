from rest_framework import serializers

from .models import Team, User, WorkGroup


class WorkGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkGroup
        fields = ["id", "name", "code", "is_active"]


class TeamSummarySerializer(serializers.ModelSerializer):
    group = WorkGroupSerializer(read_only=True)

    class Meta:
        model = Team
        fields = ["id", "name", "code", "group"]


class TeamSerializer(serializers.ModelSerializer):
    group_detail = WorkGroupSerializer(source="group", read_only=True)

    class Meta:
        model = Team
        fields = ["id", "name", "code", "group", "group_detail", "is_active"]


class UserSummarySerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "username", "role"]


class CurrentUserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name", read_only=True)
    group = serializers.SerializerMethodField()
    team = TeamSummarySerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "email", "username", "role", "group", "team"]

    def get_group(self, user):
        if not user.group:
            return None
        return WorkGroupSerializer(user.group).data


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name", read_only=True)
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    team_detail = TeamSummarySerializer(source="team", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "name",
            "role",
            "team",
            "team_detail",
            "is_active",
            "password",
        ]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)

    def validate(self, attrs):
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "La contraseña es obligatoria al crear un usuario."})
        role = attrs.get("role", getattr(self.instance, "role", None))
        team = attrs.get("team", getattr(self.instance, "team", None))
        if role in {User.Role.DISPATCHER, User.Role.SUPPORT} and not team:
            raise serializers.ValidationError({"team": "Un despachador o agente de soporte requiere un equipo asignado."})
        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user
