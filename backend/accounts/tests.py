from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Team, User, WorkGroup


class SelfAssignGuardTests(APITestCase):
    """Solo SOPORTE se autoasigna (Soporte A/B); supervisores solo en sus grupos; el resto no cambia de equipo."""

    def setUp(self):
        g_tigo, _ = WorkGroup.objects.get_or_create(name="Tigo", defaults={"code": "tigo"})
        g_sa, _ = WorkGroup.objects.get_or_create(name="Soporte A", defaults={"code": "soporte-a"})
        g_sb, _ = WorkGroup.objects.get_or_create(name="Soporte B", defaults={"code": "soporte-b"})
        self.team_tigo, _ = Team.objects.get_or_create(code="tigo", defaults={"group": g_tigo, "name": "Tigo"})
        self.team_sa, _ = Team.objects.get_or_create(code="soporte-a", defaults={"group": g_sa, "name": "Soporte A"})
        self.team_sb, _ = Team.objects.get_or_create(code="soporte-b", defaults={"group": g_sb, "name": "Soporte B"})
        self.support = User.objects.create_user(
            username="sup-a@sestel.local", email="sup-a@sestel.local", password="Sestel2026!", role=User.Role.SUPPORT
        )
        self.support.teams.set([self.team_sa])
        self.dispatcher = User.objects.create_user(
            username="desp@sestel.local", email="desp@sestel.local", password="Sestel2026!", role=User.Role.DISPATCHER
        )
        self.dispatcher.teams.set([self.team_tigo])
        self.supervisor = User.objects.create_user(
            username="supv@sestel.local", email="supv@sestel.local", password="Sestel2026!", role=User.Role.SUPERVISOR
        )
        self.supervisor.managed_groups.set([g_sa])

    def _patch_teams(self, actor, team_ids):
        self.client.force_authenticate(actor)
        return self.client.patch("/api/auth/me/", {"teams": team_ids}, format="json")

    def test_support_can_switch_between_allowed_support_groups(self):
        response = self._patch_teams(self.support, [self.team_sa.id, self.team_sb.id])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(self.support.teams.values_list("code", flat=True)), {"soporte-a", "soporte-b"})

    def test_support_cannot_join_other_groups(self):
        response = self._patch_teams(self.support, [self.team_sa.id, self.team_tigo.id])
        self.assertEqual(response.status_code, 400)
        self.support.refresh_from_db()
        self.assertEqual(set(self.support.teams.values_list("code", flat=True)), {"soporte-a"})

    def test_dispatcher_cannot_change_teams(self):
        response = self._patch_teams(self.dispatcher, [self.team_sa.id])
        self.assertEqual(response.status_code, 400)
        self.dispatcher.refresh_from_db()
        self.assertEqual(set(self.dispatcher.teams.values_list("code", flat=True)), {"tigo"})

    def test_supervisor_only_within_supervised_groups(self):
        ok = self._patch_teams(self.supervisor, [self.team_sa.id])
        self.assertEqual(ok.status_code, 200)
        bad = self._patch_teams(self.supervisor, [self.team_tigo.id])
        self.assertEqual(bad.status_code, 400)

    def test_cannot_empty_teams_nor_touch_managed_groups(self):
        response = self._patch_teams(self.support, [])
        self.assertEqual(response.status_code, 400)
        self.client.force_authenticate(self.support)
        response = self.client.patch("/api/auth/me/", {"managed_groups": [1]}, format="json")
        self.assertEqual(response.status_code, 400)


class PasswordChangeGuardTests(APITestCase):
    """Un administrador no puede cambiar la clave de otro administrador; nadie toca la del superadmin."""

    def setUp(self):
        group, _ = WorkGroup.objects.get_or_create(name="Tigo", defaults={"code": "tigo"})
        self.team, _ = Team.objects.get_or_create(code="soporte-a", defaults={"group": group, "name": "Soporte A"})
        self.admin = User.objects.create_user(
            username="admin@sestel.local", email="admin@sestel.local", password="Sestel2026!", role=User.Role.ADMIN
        )
        self.other_admin = User.objects.create_user(
            username="admin2@sestel.local", email="admin2@sestel.local", password="Sestel2026!", role=User.Role.ADMIN
        )
        self.superadmin = User.objects.create_superuser(
            username="root@sestel.local", email="root@sestel.local", password="Sestel2026!"
        )
        self.support = User.objects.create_user(
            username="soporte@sestel.local", email="soporte@sestel.local", password="Sestel2026!", role=User.Role.SUPPORT
        )
        self.support.teams.set([self.team])

    def _patch_password(self, actor, target, password="NuevaClave2026!"):
        self.client.force_authenticate(actor)
        return self.client.patch(
            reverse("user-detail", args=[target.id]), {"password": password}, format="json"
        )

    def test_admin_cannot_change_another_admin_password(self):
        response = self._patch_password(self.admin, self.other_admin)
        self.assertEqual(response.status_code, 400)
        self.other_admin.refresh_from_db()
        self.assertTrue(self.other_admin.check_password("Sestel2026!"))

    def test_nobody_can_change_superadmin_password_except_himself(self):
        for actor in (self.admin, self.other_admin, self.support):
            response = self._patch_password(actor, self.superadmin)
            self.assertIn(response.status_code, (400, 403), f"{actor.email} no debió poder cambiarla")
        self.superadmin.refresh_from_db()
        self.assertTrue(self.superadmin.check_password("Sestel2026!"))

        response = self._patch_password(self.superadmin, self.superadmin)
        self.assertEqual(response.status_code, 200)
        self.superadmin.refresh_from_db()
        self.assertTrue(self.superadmin.check_password("NuevaClave2026!"))

    def test_superadmin_can_change_any_admin_password(self):
        response = self._patch_password(self.superadmin, self.other_admin)
        self.assertEqual(response.status_code, 200)
        self.other_admin.refresh_from_db()
        self.assertTrue(self.other_admin.check_password("NuevaClave2026!"))

    def test_admin_can_still_change_support_password(self):
        response = self._patch_password(self.admin, self.support)
        self.assertEqual(response.status_code, 200)
        self.support.refresh_from_db()
        self.assertTrue(self.support.check_password("NuevaClave2026!"))

    def test_supervisor_cannot_create_users_nor_admins(self):
        supervisor = User.objects.create_user(
            username="sup@sestel.local", email="sup@sestel.local", password="Sestel2026!", role=User.Role.SUPERVISOR
        )
        self.client.force_authenticate(supervisor)
        payload = {
            "username": "nuevo@sestel.local",
            "email": "nuevo@sestel.local",
            "first_name": "Nuevo",
            "last_name": "Usuario",
            "password": "Sestel2026!",
            "role": User.Role.ADMIN,
            "teams": [self.team.id],
            "is_active": True,
        }
        response = self.client.post(reverse("user-list"), payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email="nuevo@sestel.local").exists())

        bulk = self.client.post(
            reverse("users_bulk"),
            {"file": __import__("io").BytesIO(b"email,first_name,last_name,role,team_codes\nx@sestel.local,X,Y,ADMIN,soporte-a\n")},
            format="multipart",
        )
        self.assertEqual(bulk.status_code, 403)


class AuthenticationTests(APITestCase):
    def setUp(self):
        group, _ = WorkGroup.objects.get_or_create(name="Tigo", defaults={"code": "tigo"})
        self.team, _ = Team.objects.get_or_create(group=group, name="FTTH Norte", defaults={"code": "ftth-norte"})
        self.user = User.objects.create_user(
            username="despacho@sestel.local",
            email="despacho@sestel.local",
            password="Sestel2026!",
            role=User.Role.DISPATCHER,
        )
        self.user.teams.set([self.team])
        self.admin = User.objects.create_user(
            username="admin@sestel.local",
            email="admin@sestel.local",
            password="Sestel2026!",
            role=User.Role.ADMIN,
        )
        self.admin.teams.set([self.team])

    def test_user_can_request_a_token_with_email(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": self.user.email, "password": "Sestel2026!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["email"], self.user.email)

    def test_logout_blacklists_the_refresh_token(self):
        login = self.client.post(
            reverse("token_obtain_pair"),
            {"email": self.user.email, "password": "Sestel2026!"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        logout = self.client.post(reverse("logout"), {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(logout.status_code, 204)

        refresh = self.client.post(reverse("token_refresh"), {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 401)

    def test_only_administrators_can_manage_users(self):
        self.client.force_authenticate(self.user)
        denied = self.client.get(reverse("user-list"))
        # Dispatcher can list same-group users (includes self)
        self.assertEqual(denied.status_code, 200)
        self.assertTrue(any(u["id"] == self.user.id for u in denied.data["results"]))

        # Dispatcher cannot create
        forbidden = self.client.post(
            reverse("user-list"),
            {
                "username": "otro@sestel.local",
                "email": "otro@sestel.local",
                "first_name": "Otro",
                "last_name": "Usuario",
                "password": "Sestel2026!",
                "role": User.Role.SUPPORT,
                "teams": [self.team.id],
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(self.admin)
        created = self.client.post(
            reverse("user-list"),
            {
                "username": "nuevo@sestel.local",
                "email": "nuevo@sestel.local",
                "first_name": "Nuevo",
                "last_name": "Usuario",
                "password": "Sestel2026!",
                "role": User.Role.SUPPORT,
                "teams": [self.team.id],
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        new_user = User.objects.get(pk=created.data["id"])
        self.assertTrue(new_user.check_password("Sestel2026!"))

        updated = self.client.patch(reverse("user-detail", args=[new_user.id]), {"is_active": False}, format="json")
        self.assertEqual(updated.status_code, 200)
        new_user.refresh_from_db()
        self.assertFalse(new_user.is_active)

        own_account = self.client.patch(reverse("user-detail", args=[self.admin.id]), {"is_active": False}, format="json")
        self.assertEqual(own_account.status_code, 400)


class SingleSessionTests(APITestCase):
    """Un solo login global: el nuevo login (o un reset de contraseña) invalida todos los tokens anteriores."""

    def setUp(self):
        group, _ = WorkGroup.objects.get_or_create(name="Tigo", defaults={"code": "tigo"})
        self.team, _ = Team.objects.get_or_create(group=group, name="FTTH Norte", defaults={"code": "ftth-norte"})
        self.user = User.objects.create_user(
            username="despacho@sestel.local",
            email="despacho@sestel.local",
            password="Sestel2026!",
            role=User.Role.DISPATCHER,
        )
        self.user.teams.set([self.team])

    def _login(self):
        return self.client.post(
            reverse("token_obtain_pair"),
            {"email": self.user.email, "password": "Sestel2026!"},
            format="json",
        )

    def _me(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return self.client.get("/api/auth/me/")

    def test_new_login_invalidates_previous_tokens(self):
        first = self._login()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self._me(first.data["access"]).status_code, 200)

        second = self._login()
        self.assertEqual(second.status_code, 200)

        # El access anterior deja de servir aunque no haya expirado.
        self.assertEqual(self._me(first.data["access"]).status_code, 401)
        # El refresh anterior también queda invalidado.
        stale_refresh = self.client.post(reverse("token_refresh"), {"refresh": first.data["refresh"]}, format="json")
        self.assertEqual(stale_refresh.status_code, 401)
        # La sesión nueva funciona.
        self.assertEqual(self._me(second.data["access"]).status_code, 200)

    def test_refresh_within_same_session_still_works(self):
        login = self._login()
        refresh = self.client.post(reverse("token_refresh"), {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 200)
        self.assertIn("access", refresh.data)
        self.assertEqual(self._me(refresh.data["access"]).status_code, 200)

    def test_logout_invalidates_the_access_token(self):
        login = self._login()
        self.assertEqual(self._me(login.data["access"]).status_code, 200)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        logout = self.client.post(reverse("logout"), {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(logout.status_code, 204)

        # Ni el access ni el refresh sobreviven al cierre de sesión.
        self.assertEqual(self._me(login.data["access"]).status_code, 401)
        reuse = self.client.post(reverse("token_refresh"), {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(reuse.status_code, 401)

    def test_logout_with_stale_refresh_still_closes_session(self):
        """El logout es idempotente: un refresh ya rotado no impide cerrar la sesión."""
        login = self._login()
        # Rota el refresh (queda en lista negra el original).
        rotated = self.client.post(reverse("token_refresh"), {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(rotated.status_code, 200)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {rotated.data['access']}")
        logout = self.client.post(reverse("logout"), {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(logout.status_code, 204)

        # El access vigente queda invalidado aunque el refresh enviado estuviera obsoleto.
        self.assertEqual(self._me(rotated.data["access"]).status_code, 401)

    def test_tokens_carry_the_session_claim(self):
        from rest_framework_simplejwt.tokens import AccessToken

        login = self._login()
        payload = AccessToken(login.data["access"]).payload
        self.user.refresh_from_db()
        self.assertEqual(payload.get("sid"), str(self.user.session_id))


class PasswordResetNoEnumerationTests(APITestCase):
    """RF-004 (sin enumerar usuarios): el restablecimiento responde SIEMPRE igual,
    exista o no el correo y esté o no activa la cuenta."""

    def setUp(self):
        group, _ = WorkGroup.objects.get_or_create(name="Tigo", defaults={"code": "tigo"})
        team, _ = Team.objects.get_or_create(group=group, name="FTTH Norte", defaults={"code": "ftth-norte"})
        self.user = User.objects.create_user(
            username="despacho@sestel.local",
            email="despacho@sestel.local",
            password="Sestel2026!",
            role=User.Role.DISPATCHER,
        )
        self.user.teams.set([team])
        self.inactive = User.objects.create_user(
            username="baja@sestel.local",
            email="baja@sestel.local",
            password="Sestel2026!",
            role=User.Role.DISPATCHER,
        )
        self.inactive.is_active = False
        self.inactive.save(update_fields=["is_active"])

    def _request(self, email):
        return self.client.post(reverse("password_reset"), {"email": email}, format="json")

    def _assert_generic(self, resp):
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("detail", "").startswith("Si existe una cuenta con ese correo"))
        self.assertNotIn("No existe", resp.data.get("detail", ""))
        self.assertNotIn("desactivada", resp.data.get("detail", ""))

    def test_unknown_email_gets_the_generic_answer(self):
        self._assert_generic(self._request("noexiste@sestel.local"))

    def test_existing_email_gets_the_same_generic_answer(self):
        self._assert_generic(self._request(self.user.email))

    def test_inactive_account_gets_the_same_generic_answer(self):
        self._assert_generic(self._request(self.inactive.email))

    def test_empty_email_is_still_a_validation_error(self):
        resp = self._request("")
        self.assertEqual(resp.status_code, 400)