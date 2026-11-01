import json
import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, Client
from django.utils import timezone
from rest_framework.exceptions import ValidationError as APIValidationError
from begunici.app_types.animals.models import Ram, Ewe, Maker, ArchiveAct
from begunici.app_types.animals.serializers import RamSerializer
from begunici.app_types.veterinary.vet_models import Tag, Place, PlaceMovement, Status, Veterinary, VeterinaryCare
from begunici.app_types.vet_inventory.models import VetProduct, VetSettings, VetDocument, VetMovement
from begunici.app_types.vet_inventory import services as stock
from begunici.app_types.vet_inventory.rules import save_rule
from begunici.app_types.clinical import services
from begunici.app_types.clinical.models import Episode, Event, Dose


class Workflow(TestCase):
    def setUp(self):
        self.users = {name: User.objects.create_user(name, password="clinical-test") for name in ("admin", "vet", "zootech", "main", "finans", "outsider")}
        self.admin = self.users["admin"]
        self.place = Place.objects.create(sheepfold="1-1")
        self.isolator = Place.objects.create(sheepfold="Изолятор")
        self.status = Status.objects.create(status_type="Ремонт")
        self.product = VetProduct.objects.create(name="Антибиотик", category="medicine", unit="ml")
        self.bandage = VetProduct.objects.create(name="Бинт", category="material", unit="pcs")
        self.animal = self.make_animal("1001")

    def make_animal(self, tag):
        return Ram.objects.create(tag=Tag.objects.create(tag_number=tag, animal_type="Ram"), animal_status=self.status, place=self.place, birth_date=timezone.localdate()-timedelta(days=90))

    def admit(self, animal=None):
        ep = services.admit(self.users["main"], (animal or self.animal).tag_id)
        services.update_intake(self.users["vet"], ep.pk, ep.revision, "Травма", str(timezone.localdate()), "")
        ep.refresh_from_db()
        return ep

    def care(self, episodes, quantity="3", mode="head", token=None):
        for episode in episodes:
            episode.refresh_from_db()
        services.add_care(self.users["zootech"], [{"id":e.pk,"revision":e.revision} for e in episodes], str(timezone.localdate()), "Обработка раны", [{"product":self.product.pk,"amount":quantity}], mode, token or uuid.uuid4())

    def receipt(self, quantity="100"):
        order=stock.create_order(self.admin,"Поставщик", "", [{"product":self.product.pk,"amount":quantity}],uuid.uuid4())
        doc=stock.create_document(self.admin,"receipt",str(timezone.localdate()),"TEST-RECEIPT",[{"product":self.product.pk,"amount":quantity}],"",uuid.uuid4(),order_id=order.pk)
        stock.confirm_document(self.admin,doc.pk,doc.revision)

    def close(self, episode, **kwargs):
        episode.refresh_from_db()
        return services.close_episode(self.users["vet"],episode.pk,episode.revision,"Выздоровление",str(timezone.localdate()),services.totals(episode),"",None,True,**kwargs)

    def test_admission_roles_and_independent_assignments(self):
        self.animal.is_for_sale=True
        self.animal.save()
        ep=self.admit()
        self.animal.refresh_from_db()
        self.assertTrue(self.animal.is_for_sale and self.animal.is_in_treatment)
        self.assertEqual(ep.created_by,self.users["main"])
        self.assertEqual(Episode.objects.count(),1)
        self.assertEqual(services.admit(self.admin,self.animal.tag_id).pk,ep.pk)
        for name in ("finans","outsider"):
            with self.assertRaises(PermissionDenied):
                services.admit(self.users[name],self.animal.tag_id)

    def test_card_assignment_and_unset_redirect(self):
        serializer=RamSerializer(self.animal,data={"is_in_treatment":True},partial=True,context={"request":SimpleNamespace(user=self.users["main"])})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.assertTrue(Episode.objects.filter(tag=self.animal.tag).exists())
        serializer=RamSerializer(self.animal,data={"is_in_treatment":False},partial=True,context={"request":SimpleNamespace(user=self.users["main"])})
        self.assertFalse(serializer.is_valid())
        self.assertIn("treatment_url",serializer.errors)

    def test_model_prevents_unconfirmed_discharge(self):
        self.admit()
        self.animal.refresh_from_db()
        self.animal.is_in_treatment=False
        with self.assertRaises(ValidationError):
            self.animal.save()
        self.animal.refresh_from_db()
        self.assertTrue(self.animal.is_in_treatment)

    def test_group_doses_preserve_total_and_do_not_charge(self):
        a=self.admit()
        b=self.admit(self.make_animal("1002"))
        c=self.admit(self.make_animal("1003"))
        self.care([a,b,c],"1",mode="group")
        self.assertEqual(sum(Dose.objects.values_list("quantity",flat=True)),Decimal("1"))
        self.assertEqual(sorted(Dose.objects.values_list("quantity",flat=True)),[Decimal(".333"),Decimal(".333"),Decimal(".334")])
        self.assertFalse(VetMovement.objects.exists())
        self.assertFalse(Veterinary.objects.exists())

    def test_per_head_and_repeat_submission(self):
        a=self.admit();b=self.admit(self.make_animal("1002"));token=uuid.uuid4()
        self.care([a,b],"2.5",token=token)
        self.care([a,b],"2.5",token=token)
        self.assertEqual(Dose.objects.count(),2)
        self.assertEqual(sum(Dose.objects.values_list("quantity",flat=True)),Decimal("5"))

    def test_shortage_discharge_retry_and_single_charge(self):
        ep=self.admit();self.care([ep])
        result=self.close(ep)
        self.assertTrue(result.stock_pending)
        self.animal.refresh_from_db()
        self.assertFalse(self.animal.is_in_treatment)
        self.receipt("10")
        services.reconcile(self.users["zootech"],ep.pk)
        services.reconcile(self.users["zootech"],ep.pk)
        self.close(ep)
        self.assertEqual(stock.balances()[self.product.pk][0],Decimal("7"))
        self.assertEqual(VetDocument.objects.filter(kind="consume").count(),1)

    def test_corrected_final_consumption_requires_reason(self):
        ep=self.admit();self.care([ep]);ep.refresh_from_db()
        lines=[{"product":self.product.pk,"amount":"2"}]
        args=[self.users["vet"],ep.pk,ep.revision,"Выздоровление",str(timezone.localdate()),lines]
        with self.assertRaises(ValidationError):
            services.close_episode(*args,"",None,True)
        self.receipt()
        result=services.close_episode(*args,"Уточнение фактической дозы",None,True)
        self.assertEqual(result.expense_expected[0]["amount"],"3")
        self.assertEqual(result.expense_confirmed[0]["amount"],"2")
        self.assertEqual(stock.balances()[self.product.pk][0],Decimal("98"))

    def test_dates_revision_and_readonly_roles(self):
        ep=self.admit()
        for name in ("main","finans","outsider"):
            with self.assertRaises(PermissionDenied):
                services.add_care(self.users[name],[{"id":ep.pk,"revision":ep.revision}],str(timezone.localdate()),"Осмотр",[],"head",uuid.uuid4())
        with self.assertRaises(ValidationError):
            services.update_intake(self.users["vet"],ep.pk,0,"x",str(timezone.localdate()),"")
        with self.assertRaises(ValidationError):
            services.add_care(self.users["vet"],[{"id":ep.pk,"revision":ep.revision}],str(timezone.localdate()+timedelta(days=1)),"Осмотр",[],"head",uuid.uuid4())

    def test_real_movement_and_history(self):
        ep=self.admit()
        services.update_intake(self.users["vet"],ep.pk,ep.revision,"Травма",str(ep.admitted_on),self.isolator.pk)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.place,self.isolator)
        self.assertTrue(PlaceMovement.objects.filter(tag=self.animal.tag,new_place=self.isolator).exists())
        ep.refresh_from_db()
        self.assertEqual(ep.origin,"1-1")

    def test_all_archive_statuses_require_clinical_completion(self):
        ep=self.admit()
        for label in ("Падеж","Убой на мясо","Вынужденная прирезка","Реализация в живом весе"):
            status,_=Status.objects.get_or_create(status_type=label)
            serializer=RamSerializer(self.animal,data={"animal_status_id":status.pk,"status_date":str(timezone.localdate())},partial=True,context={"request":SimpleNamespace(user=self.admin)})
            self.assertFalse(serializer.is_valid())
            self.assertIn("treatment_url",serializer.errors)
        client=Client();client.force_login(self.admin)
        response=client.post("/animals/actions/bulk_archive/",data=json.dumps({"animal_ids":[self.animal.tag_id],"status_id":status.pk}),content_type="application/json")
        self.assertEqual(response.status_code,409)

    def test_standard_archive_act_created_on_clinical_close(self):
        ep=self.admit();ep.refresh_from_db()
        status=Status.objects.create(status_type="Падеж")
        result=services.close_episode(self.users["zootech"],ep.pk,ep.revision,"Погибло",str(ep.admitted_on),[],"",status.pk,True,{"archive_act_date":str(ep.admitted_on),"archive_act_fatness":"3","archive_act_death_reason":"Травма","archive_act_diagnosis":"Перелом"})
        self.animal.refresh_from_db()
        self.assertTrue(self.animal.is_archived)
        self.assertFalse(self.animal.is_in_treatment)
        self.assertTrue(ArchiveAct.objects.filter(tag=self.animal.tag,status_name="Падеж").exists())

    def test_other_archive_statuses_use_existing_acts(self):
        for index,label in enumerate(("Убой на мясо","Вынужденная прирезка","Реализация в живом весе")):
            animal=self.make_animal("ARCH-"+str(index))
            ep=self.admit(animal);ep.refresh_from_db()
            status,_=Status.objects.get_or_create(status_type=label)
            services.close_episode(self.users["vet"],ep.pk,ep.revision,label,str(ep.admitted_on),[],"",status.pk,True,{"archive_act_date":str(ep.admitted_on),"archive_act_fatness":"3","archive_act_diagnosis":"Основание архивации"})
            animal.refresh_from_db()
            self.assertTrue(animal.is_archived)
            self.assertFalse(animal.is_in_treatment)
            self.assertTrue(ArchiveAct.objects.filter(tag=animal.tag,status_name=label).exists())

    def test_archive_completion_sale_assignment_controls_stock_discovery(self):
        from begunici.app_types.inventory.bridges import discover, source_animal, source_info, require_eligible
        client = Client()
        client.force_login(self.users["vet"])
        for index, label in enumerate(("Убой на мясо", "Вынужденная прирезка", "Реализация в живом весе")):
            for for_sale in (False, True):
                with self.subTest(status=label, for_sale=for_sale):
                    animal = self.make_animal(f"SALE-{index}-{int(for_sale)}")
                    # Check both setting and removing a pre-existing assignment.
                    animal.is_for_sale = not for_sale
                    animal.save()
                    ep = self.admit(animal)
                    status, _ = Status.objects.get_or_create(status_type=label)
                    response = client.post(f"/animals/treatment/{ep.pk}/command/close/", data=json.dumps({
                        "revision": ep.revision, "outcome": label, "closed_on": str(ep.admitted_on),
                        "lines": [], "confirm_status": True, "confirm_expense": True, "status_id": status.pk,
                        "archive": {"archive_act_date": str(ep.admitted_on), "archive_act_fatness": "3",
                                    "archive_act_diagnosis": "Травма", "is_for_sale": for_sale},
                    }), content_type="application/json")
                    self.assertEqual(response.status_code, 200, response.content)
                    animal.refresh_from_db()
                    self.assertTrue(animal.is_archived)
                    self.assertFalse(animal.is_in_treatment)
                    self.assertEqual(animal.is_for_sale, for_sale)
                    self.assertTrue(ArchiveAct.objects.filter(tag=animal.tag, status_name=label).exists())
                    self.assertEqual(animal.tag_id in {row["tag_id"] for row in discover("pending")}, for_sale)
                    if for_sale:
                        require_eligible(source_info(source_animal(animal.tag_id)))

    def test_completion_without_sale_field_preserves_assignment(self):
        self.animal.is_for_sale = True
        self.animal.save()
        ep = self.admit()
        self.close(ep)
        self.animal.refresh_from_db()
        self.assertTrue(self.animal.is_for_sale)

    def test_api_requires_explicit_expense_confirmation(self):
        ep=self.admit()
        client=Client();client.force_login(self.users["vet"])
        data={"revision":ep.revision,"outcome":"Выздоровление","closed_on":str(ep.admitted_on),"lines":[],"confirm_status":True}
        response=client.post(f"/animals/treatment/{ep.pk}/command/close/",data=json.dumps(data),content_type="application/json")
        self.assertEqual(response.status_code,400)
        ep.refresh_from_db();self.assertIsNone(ep.closed_on)
        data["confirm_expense"]=True
        response=client.post(f"/animals/treatment/{ep.pk}/command/close/",data=json.dumps(data),content_type="application/json")
        self.assertEqual(response.status_code,200)

    def test_history_survives_retag_and_type_conversion_and_readmission(self):
        ep=self.admit()
        self.animal.tag.update_tag("NEW-1001")
        self.animal.refresh_from_db()
        self.animal.birth_date=timezone.localdate()-timedelta(days=400);self.animal.save()
        maker=self.animal.to_maker("Племенной","Рабочий")
        self.assertTrue(maker.is_in_treatment)
        self.assertEqual(Episode.objects.count(),1)
        ep.refresh_from_db();self.assertEqual(ep.tag_number,"NEW-1001")
        self.close(ep)
        next_ep=services.admit(self.users["main"],maker.tag_id)
        self.assertNotEqual(next_ep.pk,ep.pk)
        self.assertEqual(Episode.objects.count(),2)

    def test_catalog_units_locked_by_unposted_clinical_doses(self):
        ep=self.admit();self.care([ep])
        self.assertTrue(stock.product_restrictions(self.product)["unit_locked"])

    def test_normal_veterinary_care_still_charges_immediately(self):
        self.receipt("10")
        care=VeterinaryCare.objects.create(medication="Препарат")
        save_rule(self.users["vet"],care.pk,0,self.product.pk,"head","2",[])
        self.admit()
        Veterinary.objects.create(tag=self.animal.tag,veterinary_care=care)
        self.assertEqual(stock.balances()[self.product.pk][0],Decimal("8"))
        self.assertEqual(Dose.objects.count(),0)

    def test_clinical_documents_cannot_be_modified_through_general_stock(self):
        ep=self.admit();self.care([ep]);ep=self.close(ep)
        with self.assertRaises(ValidationError):
            stock.edit_draft(self.admin,ep.expense_document_id,1,[],"test")
        with self.assertRaises(ValidationError):
            stock.cancel_draft(self.admin,ep.expense_document_id,1)

    def test_pages_roles_search_and_analytics(self):
        ep=self.admit();self.care([ep])
        for name in ("admin","vet","zootech","main","finans"):
            client=Client();client.force_login(self.users[name])
            for url in ("/animals/treatment/",f"/animals/treatment/{ep.pk}/",f"/animals/treatment/care/?episodes={ep.pk}","/animals/ram/1001/analytics/","/animals/vet-list/"):
                response=client.get(url)
                self.assertEqual(response.status_code,200,(name,url,response.content[:300]))
            response=client.get(f"/animals/treatment/{ep.pk}/")
            self.assertEqual('data-clinical-form="close"' in response.content.decode(),name in ("admin","vet","zootech"))
        client=Client();client.force_login(self.users["outsider"])
        self.assertEqual(client.get("/animals/treatment/").status_code,403)
        client.force_login(self.users["finans"])
        self.assertContains(client.get("/animals/treatment/?q=1001"),"1001")
        self.assertNotContains(client.get("/animals/treatment/?q=NO-MATCH"),'class="fw-bold"')
