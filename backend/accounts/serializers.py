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
    groups = serializers.SerializerMethodField()
    teams = TeamSummarySerializer(many=True, read_only=True)
    is_locked = serializers.BooleanField(source="is_account_locked", read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "email", "username", "role", "group", "groups", "teams", "is_locked", "failed_login_attempts", "locked_at"]
        read_only_fields = ["failed_login_attempts", "locked_at"]

    def get_group(self, user):
        first_team = user.teams.select_related("group").first()
        if not first_team:
            return None
        return WorkGroupSerializer(first_team.group).data

    def get_groups(self, user):
        groups = WorkGroup.objects.filter(teams__members=user).distinct()
        return WorkGroupSerializer(groups, many=True).data


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name", read_only=True)
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    teams = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all(), many=True, required=False)
    teams_detail = TeamSummarySerializer(source="teams", many=True, read_only=True)
    is_locked = serializers.BooleanField(source="is_account_locked", read_only=True)

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
            "teams",
            "teams_detail",
            "is_active",
            "is_locked",
            "failed_login_attempts",
            "locked_at",
            "password",
        ]
        read_only_fields = ["is_locked", "failed_login_attempts", "locked_at"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        password = validated_data.pop("password")
        teams = validated_data.pop("teams", [])
        user = User.objects.create_user(password=password, **validated_data)
        if teams:
            user.teams.set(teams)
        return user

    def validate(self, attrs):
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "La contraseña es obligatoria al crear un usuario."})
        role = attrs.get("role", getattr(self.instance, "role", None))
        # For M2M, validated teams are in attrs if provided, otherwise check instance
        if self.instance:
            has_teams = attrs.get("teams") is not None and len(attrs.get("teams")) > 0 or self.instance.teams.exists()
        else:
            has_teams = "teams" in attrs and len(attrs["teams"]) > 0 if "teams" in attrs else False
            if "teams" not in attrs:
                has_teams = False
        if role in {User.Role.DISPATCHER, User.Role.SUPPORT} and not has_teams and "teams" in attrs:
            raise serializers.ValidationError({"teams": "Un despachador o agente de soporte requiere al menos un equipo asignado."})
        # Allow creation without teams initially, will be set via .set() in create()
        return attrs

    def update(self, instance, validated_data):
        teams_data = validated_data.pop("teams", None)
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
            if user.is_account_locked:
                user.unlock_via_password_reset()
        if teams_data is not None:
            user.teams.set(teams_data)
        return user
