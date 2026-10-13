"""Independent medicine ledger; treatment history stays in the veterinary app."""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from begunici.app_types.inventory.models import AppendOnly


class VetSettings(models.Model):
    # One lock serializes accounting commands, including simultaneous confirmations.
    revision = models.PositiveIntegerField(default=1)
    legacy_treatment_id = models.PositiveBigIntegerField(default=0)


class VetProduct(models.Model):
    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=12, choices=[
        ("medicine", "Препарат"), ("vaccine", "Вакцина"),
        ("material", "Материал"), ("other", "Прочее"),
    ])
    unit = models.CharField(max_length=8, choices=[("ml", "мл"), ("g", "г"), ("pcs", "шт."), ("dose", "доз"), ("l", "л"), ("kg", "кг")])
    package = models.CharField(max_length=40, blank=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.name


class VetNorm(models.Model):
    care = models.OneToOneField("veterinary.VeterinaryCare", on_delete=models.CASCADE, related_name="stock_norm")
    product = models.ForeignKey(VetProduct, on_delete=models.PROTECT, related_name="norms")
    mode = models.CharField(max_length=12, choices=[("head", "На голову"), ("weight", "На 1 кг веса"), ("bands", "По диапазонам веса")])
    rate = models.DecimalField(max_digits=12, decimal_places=3, null=True)
    bands = models.JSONField(default=list)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(rate__gte=0) | Q(rate__isnull=True), name="vet_nonnegative_norm"),
        ]


class VetOrder(AppendOnly):
    supplier = models.CharField(max_length=200)
    note = models.TextField(blank=True)
    lines = models.JSONField(default=list)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class VetDocument(models.Model):
    kind = models.CharField(max_length=12, choices=[
        ("receipt", "Приходная накладная"), ("consume", "Прочий расход препаратов"),
        ("treatment", "Расход по ветобработке"), ("writeoff", "Акт списания препаратов"),
        ("reversal", "Сторно"),
    ])
    state = models.CharField(max_length=12, default="draft", choices=[
        ("draft", "Черновик"), ("posted", "Подтверждён"),
        ("reversed", "Сторнирован"), ("cancelled", "Отменён"),
    ])
    date = models.DateField(default=timezone.localdate)
    number = models.CharField(max_length=100, blank=True)
    order = models.ForeignKey(VetOrder, on_delete=models.PROTECT, null=True, blank=True)
    reversal_of = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vet_documents", null=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="posted_vet_documents")

    class Meta:
        ordering = ["-pk"]

    def __str__(self):
        return f"{self.get_kind_display()} № {self.pk}"


class VetVersion(AppendOnly):
    document = models.ForeignKey(VetDocument, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    payload = models.JSONField(default=dict)
    filename = models.CharField(max_length=200, blank=True)
    content = models.BinaryField(default=bytes, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)

    class Meta:
        ordering = ["-number"]
        constraints = [models.UniqueConstraint(fields=["document", "number"], name="vet_unique_version")]


class VetMovement(AppendOnly):
    product = models.ForeignKey(VetProduct, on_delete=models.PROTECT, related_name="movements")
    document = models.ForeignKey(VetDocument, on_delete=models.PROTECT, related_name="movements")
    amount = models.DecimalField(max_digits=15, decimal_places=3)
    packages = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "product"], name="vet_unique_movement")]


class VetAudit(AppendOnly):
    action = models.CharField(max_length=80)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)


class VetTreatment(models.Model):
    # Stable source id survives deletion of the original treatment and its tag.
    source_id = models.PositiveBigIntegerField(unique=True)
    snapshot = models.JSONField(default=dict)
    calculation = models.JSONField(default=dict)
    product = models.ForeignKey(VetProduct, on_delete=models.PROTECT, null=True)
    quantity = models.DecimalField(max_digits=15, decimal_places=3, null=True)
    document = models.ForeignKey(VetDocument, on_delete=models.PROTECT, null=True)
    state = models.CharField(max_length=12, default="pending", choices=[
        ("pending", "Требует сверки"), ("posted", "Учтён"),
        ("excluded", "Без расхода"), ("deleted", "Обработка удалена"),
    ])
    issue = models.TextField(blank=True)
    manual = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-pk"]
