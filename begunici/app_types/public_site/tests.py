from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class CatalogNavigationTests(TestCase):
    def test_storefront_shows_packaging_and_working_order_destination(self):
        products = self.client.get(reverse("public_site:products"))
        self.assertContains(products, "Упаковка: 700 г")
        self.assertContains(products, "Наличие: много")
        self.assertContains(products, "Нежная вырезка для быстрой обжарки")
        self.assertContains(products, 'href="/site/products/" aria-current="page"')
        self.assertContains(products, 'href="/site/contacts/#order"')
        contacts = self.client.get(reverse("public_site:contacts"))
        self.assertContains(contacts, 'id="order"')
        self.assertContains(contacts, 'href="tel:+79313290208"')
        self.assertContains(contacts, 'href="mailto:aeg@pf60.ru"')

    def test_login_retry_keeps_destination(self):
        get_user_model().objects.create_user("finans", password="test-password")
        login = reverse("login")
        catalog = reverse("inventory_catalog:meat-products")
        rejected = self.client.post(login, {"username": "finans", "password": "wrong", "next": catalog})
        self.assertContains(rejected, f'name="next" value="{catalog}"')
        self.assertRedirects(
            self.client.post(login, {"username": "finans", "password": "test-password", "next": catalog}),
            catalog,
        )
