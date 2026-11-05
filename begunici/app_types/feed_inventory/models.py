"""Independent feed ledger. Animal and product inventory data are read-only bridges."""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from begunici.app_types.inventory.models import AppendOnly


class FeedSettings(models.Model):
    # One lock serializes accounting commands, including simultaneous confirmations.
    revision = models.PositiveIntegerField(default=1)


class FeedProduct(models.Model):
    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=12, choices=[
        ("hay", "Сено / сенаж"), ("feed", "Корма"),
        ("salt", "Соль"), ("other", "Прочее"),
    ])
    unit = models.CharField(max_length=8, choices=[("kg", "кг"), ("l", "л"), ("pcs", "шт.")])
    package = models.CharField(max_length=40, blank=True)
    revision = models.PositiveIntegerField(default=1)
    package_weight = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    plan_product = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="variants")

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.name


class FeedNorm(models.Model):
    product = models.ForeignKey(FeedProduct, on_delete=models.PROTECT, related_name="norms")
    group = models.CharField(max_length=40)
    per_head = models.DecimalField(max_digits=12, decimal_places=3, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "group"], name="feed_unique_norm"),
            models.CheckConstraint(check=Q(per_head__gte=0) | Q(per_head__isnull=True), name="feed_nonnegative_norm"),
        ]


class FeedOrder(AppendOnly):
    supplier = models.CharField(max_length=200)
    note = models.TextField(blank=True)
    lines = models.JSONField(default=list)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class FeedDocument(models.Model):
    kind = models.CharField(max_length=12, choices=[
        ("receipt", "Приходная накладная"), ("consume", "Расход кормов"),
        ("writeoff", "Акт списания кормов"),
        ("reversal", "Сторно"),
        ("transfer", "Поставка на овчарню"),
        ("barn_return", "Возврат с овчарни"),
    ])
    state = models.CharField(max_length=12, default="draft", choices=[
        ("draft", "Черновик"), ("posted", "Подтверждён"),
        ("reversed", "Сторнирован"), ("cancelled", "Отменён"),
    ])
    date = models.DateField(default=timezone.localdate)
    number = models.CharField(max_length=100, blank=True)
    order = models.ForeignKey(FeedOrder, on_delete=models.PROTECT, null=True, blank=True)
    reversal_of = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="feed_documents")
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="posted_feed_documents")

    class Meta:
        ordering = ["-pk"]
        constraints = [models.UniqueConstraint(
            fields=["date"], condition=Q(kind="consume", state="posted"),
            name="feed_one_posted_consumption_per_day",
        )]

    def __str__(self):
        return f"{self.get_kind_display()} № {self.act_number if self.kind == 'writeoff' else self.pk}"

    @property
    def act_number(self):
        if self.kind != "writeoff" or not self.pk:
            return self.number or str(self.pk)
        from begunici.app_types.animals.act_numbering import writeoff_number
        return writeoff_number(self, "feed_writeoff")


class FeedVersion(AppendOnly):
    document = models.ForeignKey(FeedDocument, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    payload = models.JSONField(default=dict)
    filename = models.CharField(max_length=200, blank=True)
    content = models.BinaryField(default=bytes, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-number"]
        constraints = [models.UniqueConstraint(fields=["document", "number"], name="feed_unique_version")]


class FeedMovement(AppendOnly):
    product = models.ForeignKey(FeedProduct, on_delete=models.PROTECT, related_name="movements")
    document = models.ForeignKey(FeedDocument, on_delete=models.PROTECT, related_name="movements")
    amount = models.DecimalField(max_digits=15, decimal_places=3)
    packages = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "product"], name="feed_unique_movement")]


class FeedAudit(AppendOnly):
    action = models.CharField(max_length=80)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class BarnFeedDocument(AppendOnly):
    barn = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=12, choices=[("delivery", "Поставка"), ("return", "Возврат на склад"),
        ("writeoff", "Списание по акту"), ("close", "Факт за месяц"), ("reversal", "Сторно")])
    date = models.DateField()
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    payload = models.JSONField(default=dict)
    central_document = models.OneToOneField(FeedDocument, null=True, blank=True, on_delete=models.PROTECT, related_name="barn_document")
    reversal_of = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal")
    filename = models.CharField(max_length=200, blank=True)
    content = models.BinaryField(default=bytes, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]
        constraints = [models.CheckConstraint(check=Q(barn__gte=1, barn__lte=4), name="feed_barn_1_to_4")]


class BarnFeedMovement(AppendOnly):
    document = models.ForeignKey(BarnFeedDocument, on_delete=models.PROTECT, related_name="movements")
    product = models.ForeignKey(FeedProduct, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=15, decimal_places=3)
    packages = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "product"], name="feed_barn_doc_product")]


class BarnFeedPeriod(models.Model):
    barn = models.PositiveSmallIntegerField()
    month = models.DateField()
    plan = models.JSONField(default=dict)
    captured_at = models.DateTimeField(default=timezone.now)
    closing = models.OneToOneField(BarnFeedDocument, null=True, blank=True, on_delete=models.PROTECT, related_name="closed_period")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["barn", "month"], name="feed_barn_month")]
