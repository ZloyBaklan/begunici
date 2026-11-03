from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from . import invoices, receipts
from .models import AnimalCase, Document, Product, StockLot, StockMovement


class CatalogPriceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user("admin")
        cls.main = get_user_model().objects.create_user("main")
        cls.reader = get_user_model().objects.create_superuser("other", password="test")
        cls.meat = Product.objects.get(code="tenderloin")
        cls.offal = Product.objects.get(code="liver")

    def test_catalog_edits_and_public_cards_share_prices(self):
        listing = reverse("inventory_catalog:meat-products")
        edit = reverse("inventory_catalog:meat-product-edit", args=[self.meat.pk])
        values = {"name": self.meat.name, "category": "meat", "unit": "kg_pcs",
                  "parts_per_animal": self.meat.parts_per_animal, "revision": self.meat.revision,
                  "unit_price": "123.45", "price_unit": "pcs"}

        self.client.force_login(self.reader)
        self.assertContains(self.client.get(listing), self.meat.name)
        self.assertNotContains(self.client.get(listing), "Добавить номенклатуру")
        self.assertEqual(self.client.post(edit, values).status_code, 403)
        self.assertEqual(self.client.post(listing, values).status_code, 403)
        self.client.force_login(self.main)
        self.assertRedirects(self.client.post(edit, values), listing)
        self.client.force_login(self.reader)
        self.assertContains(self.client.get(listing), "123,45")
        self.client.logout()

        meat = self.client.get(reverse("public_site:products"))
        self.assertContains(meat, "Вырезка ягнёнка премиум")
        self.assertContains(meat, "123,45 ₽ / шт.")
        self.assertNotContains(meat, "Печень ягнёнка")
        self.assertNotContains(meat, "Штук с животного")
        offal = self.client.get(reverse("public_site:offal"))
        self.assertContains(offal, "Печень ягнёнка")
        self.assertContains(offal, "Уточнить цену")
        self.assertNotContains(offal, "Вырезка")

    def test_receipt_and_invoice_freeze_prices_and_print_totals(self):
        Product.objects.filter(pk=self.meat.pk).update(unit_price="10.01")
        Product.objects.filter(pk=self.offal.pk).update(unit_price="20.00", price_unit="pcs")
        act = Document.objects.create(kind=Document.Kind.SP55, created_by=self.admin, date=date(2026, 11, 3))
        animal = AnimalCase.objects.create(source_tag_id=1, tag_number="A123", animal_type="ram",
                                           kind="meat", archive_date=act.date, receipt=act)
        payload = {
            "animals": {str(animal.pk): {"weight": "50", "fatness": "Хорошая", "comment": "Осмотрено"}},
            "outputs": [
                {"animal_id": animal.pk, "product": self.meat.code, "weight": "1.500", "quantity": 1},
                {"animal_id": animal.pk, "product": self.offal.code, "weight": "0.800", "quantity": 1},
            ],
        }
        receipts.save_receipt(self.admin, act.pk, payload=payload, expected_revision=0)
        act.refresh_from_db()
        generated = act.versions.get(number=act.revision)
        original = bytes(generated.content)
        form = load_workbook(BytesIO(original))
        self.assertEqual(form.worksheets[0]["Y16"].value, 10.01)
        self.assertEqual(form.worksheets[0]["AC16"].value, 15.02)
        self.assertIn(35.02, [row[28].value for row in form.worksheets[0].iter_rows(min_col=1, max_col=32)])
        self.assertEqual(form["Выход продукции"].page_setup.fitToWidth, 1)
        self.assertIn("$H$", str(form["Выход продукции"].print_area))
        upload = SimpleUploadedFile("vet.xlsx", original)
        receipts.save_receipt(self.admin, act.pk, payload=payload, expected_revision=act.revision,
                              upload=upload, reason="Подписан", replace_confirmed=True, submit=True)
        act.refresh_from_db()

        lot = StockLot.objects.create(animal=animal, product=self.offal)
        StockMovement.objects.create(lot=lot, kind="receipt", weight="0.800", quantity=1,
                                     document=act, created_by=self.admin)
        with patch("begunici.app_types.inventory.stock.validate_case_source"):
            invoice = invoices.save_invoice(self.admin, payload={"customer": "Ферма", "lines": [
                {"lot_id": lot.pk, "weight": "0.800", "quantity": 1, "unit_price": "0.01"},
            ]})
        Product.objects.filter(pk__in=[self.meat.pk, self.offal.pk]).update(unit_price="99.00")
        self.client.force_login(self.admin)
        args = [act.pk, act.revision]
        self.assertEqual(self.client.get(reverse("inventory:download", args=args)).content, original)
        printed = self.client.get(reverse("inventory:print-version", args=args))
        self.assertEqual(printed.status_code, 200)
        self.assertEqual(load_workbook(BytesIO(printed.content)).worksheets[0]["Y16"].value, 10.01)
        printed_invoice = load_workbook(BytesIO(bytes(invoice.versions.get().content))).active
        self.assertEqual(printed_invoice["G6"].value, 20)
        self.assertEqual(printed_invoice["H6"].value, 20)
        self.assertEqual(printed_invoice["H4"].value, 20)
        self.assertEqual(printed_invoice.page_setup.fitToWidth, 1)
        self.assertEqual(printed_invoice.print_title_rows.replace("$", ""), "1:5")
