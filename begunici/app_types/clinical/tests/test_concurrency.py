from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from decimal import Decimal
from django.db import connections, close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone
from begunici.app_types.vet_inventory.models import VetSettings, VetMovement
from begunici.app_types.vet_inventory import services as stock
from begunici.app_types.clinical import services
from begunici.app_types.clinical.models import Event
from . import test_workflow as workflow


class ConcurrentDischarge(TransactionTestCase):
    setUp = workflow.Workflow.setUp
    make_animal = workflow.Workflow.make_animal
    admit = workflow.Workflow.admit
    care = workflow.Workflow.care
    receipt = workflow.Workflow.receipt

    def test_simultaneous_discharge_has_one_expense(self):
        VetSettings.objects.get_or_create(pk=1)
        ep=self.admit();self.care([ep]);self.receipt("10");ep.refresh_from_db()
        barrier=Barrier(2)
        def close():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                services.close_episode(self.users["vet"],ep.pk,ep.revision,"Выздоровление",str(timezone.localdate()),services.totals(ep),"",None,True)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(close) for _ in range(2)]
            for future in futures:
                future.result(timeout=20)
        self.assertEqual(VetMovement.objects.filter(amount__lt=0).count(),1)
        self.assertEqual(stock.balances()[self.product.pk][0],Decimal("7"))
        self.assertEqual(Event.objects.filter(episode=ep,kind="discharge").count(),1)
