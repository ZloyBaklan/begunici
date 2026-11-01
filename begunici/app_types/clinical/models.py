import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from begunici.app_types.inventory.models import AppendOnly


class Episode(models.Model):
    tag = models.ForeignKey("veterinary.Tag", on_delete=models.SET_NULL, null=True, related_name="clinical_episodes")
    snapshot = models.JSONField(default=dict)
    admitted_on = models.DateField(default=timezone.localdate)
    diagnosis = models.CharField(max_length=1000, blank=True)
    origin = models.CharField(max_length=200, blank=True)
    revision = models.PositiveIntegerField(default=1)
    closed_on = models.DateField(null=True, blank=True)
    outcome = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="closed_clinical_episodes")
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="clinical_episodes")
    expense_expected = models.JSONField(default=list)
    expense_confirmed = models.JSONField(default=list)
    expense_document = models.OneToOneField("vet_inventory.VetDocument", on_delete=models.PROTECT, null=True, blank=True, related_name="clinical_episode")
    expense_issue = models.TextField(blank=True)

    class Meta:
        ordering = ["-admitted_on", "-pk"]
        constraints = [models.UniqueConstraint(fields=["tag"], condition=Q(closed_on__isnull=True), name="clinical_one_open_episode")]

    @property
    def tag_number(self):
        return self.tag.tag_number if self.tag_id else self.snapshot.get("tag", "—")

    @property
    def duration(self):
        return ((self.closed_on or timezone.localdate()) - self.admitted_on).days + 1

    @property
    def stock_pending(self):
        return bool(self.expense_document_id and self.expense_document.state == "draft")


class Event(AppendOnly):
    episode = models.ForeignKey(Episode, on_delete=models.PROTECT, related_name="events")
    date = models.DateField(default=timezone.localdate)
    kind = models.CharField(max_length=16, default="care", choices=[("care", "Лечебное мероприятие"), ("intake", "Уточнение поступления"), ("discharge", "Завершение лечения")])
    note = models.TextField()
    details = models.JSONField(default=dict)
    token = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)

    class Meta:
        ordering = ["date", "pk"]
        constraints = [models.UniqueConstraint(fields=["episode", "token"], name="clinical_event_once")]


class Dose(AppendOnly):
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="doses")
    product = models.ForeignKey("vet_inventory.VetProduct", on_delete=models.PROTECT, related_name="clinical_doses")
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=15, decimal_places=3)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "product"], name="clinical_event_product_once"), models.CheckConstraint(check=Q(quantity__gt=0), name="clinical_positive_dose")]
