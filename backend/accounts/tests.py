from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Team, User, WorkGroup


class AuthenticationTests(APITestCase):
    def setUp(self):
        group = WorkGroup.objects.create(name="Tigo", code="tigo")
        self.team = Team.objects.create(group=group, name="FTTH Norte", code="ftth-norte")
        self.user = User.objects.create_user(
            username="despacho@sestel.local",
            email="despacho@sestel.local",
            password="Sestel2026!",
            role=User.Role.DISPATCHER,
            team=self.team,
        )
        self.admin = User.objects.create_user(
            username="admin@sestel.local",
            email="admin@sestel.local",
            password="Sestel2026!",
            role=User.Role.ADMIN,
            team=self.team,
        )

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
        self.assertEqual(denied.status_code, 403)

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
                "team": self.team.id,
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
