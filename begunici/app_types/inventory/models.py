"""Inventory owns its data; source animal identifiers deliberately are not FKs.

Deleting/restoring an animal through the existing service must neither cascade into
accounting history nor acquire new restrictions from this optional module.
"""
import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from .animal_types import ANIMAL_TYPE_CHOICES, type_requirement


def write_stock_audit_log(user, area, action, data):
    from begunici.app_types.animals.models_user_log import UserActionLog

    if user is None or not user.is_authenticated:
        return
    labels = {"document": "Документ", "order": "Заявка", "product": "Позиция",
              "treatment": "Учёт обработки", "care": "Ветобработка", "revision": "Версия",
              "reversal": "Сторно", "name": "Название", "quantity": "Расход",
              "unit": "Единица", "reason": "Причина"}
    details = [action]
    details.extend(f"{label}: {data[key]}" for key, label in labels.items() if key in data)
    if "changes" in data:
        details.append(f"Изменено норм: {len(data['changes'])}")
        for change in data["changes"]:
            before = change.get("before") if change.get("before") is not None else "не задано"
            after = change.get("after") if change.get("after") is not None else "не задано"
            details.append(f"{change.get('name', '')}, {change.get('label', change.get('group', ''))}: {before} -> {after}")
    for key, label in (("before", "Было"), ("after", "Стало")):
        if isinstance(data.get(key), dict):
            field_labels = {"name": "Название", "category": "Категория", "unit": "Единица", "package": "Упаковка",
                            "mode_label": "Способ расчёта", "rate": "Норма", "bands": "Диапазоны веса", "revision": "Версия"}
            values = []
            for field, title in field_labels.items():
                if field not in data[key]:
                    continue
                value = data[key][field]
                if field == "bands":
                    value = "; ".join(f"{band['from']} - {band['to'] or 'без ограничения'} кг: {band['amount']}" for band in value)
                values.append(f"{title}: {value if value not in (None, '') else '-'}")
            details.append(label + ": " + ", ".join(values))
        elif key in data and data[key] is None:
            details.append(label + ": не задано")
    details.extend(stock_audit_context(area, data))
    object_id = next((str(data[key]) for key in ("document", "order", "product", "treatment", "care") if key in data), "")
    UserActionLog.objects.create(
        user=user, action_type=action[:50], object_type=area, object_id=object_id[:100],
        description="; ".join(details), additional_data={"stock_area": area, "data": data},
    )


def stock_audit_context(area, data):
    from django.apps import apps

    prefix = {"Склад кормов": "Feed", "Склад ветпрепаратов": "Vet"}.get(area)
    if prefix is None:
        return []
    app = "feed_inventory" if prefix == "Feed" else "vet_inventory"
    details, lines = [], []
    document = apps.get_model(app, prefix + "Document").objects.filter(pk=data.get("document")).first() if data.get("document") else None
    if document:
        details.append(f"{document.get_kind_display()} № {document.number or document.pk}; дата: {document.date:%d.%m.%Y}")
        version = document.versions.defer("content").first()
        lines = version.payload.get("lines", []) if version else []
        if document.order_id:
            details.append("Поставщик: " + document.order.supplier)
    elif data.get("order"):
        order = apps.get_model(app, prefix + "Order").objects.filter(pk=data["order"]).first()
        if order:
            details.append("Поставщик: " + order.supplier)
            lines = order.lines
    elif data.get("product"):
        product = apps.get_model(app, prefix + "Product").objects.filter(pk=data["product"]).first()
        if product:
            details.append("Позиция: " + product.name)
    for line in lines:
        item = f"{line['name']}: {line['amount']} {line['unit']}"
        if line.get("package"):
            item += f"; упаковки ({line['package']}): {line.get('packages', '0')}"
        details.append(item)
    if prefix == "Vet" and data.get("treatment"):
        entry = apps.get_model(app, "VetTreatment").objects.filter(pk=data["treatment"]).first()
        animal = data.get("animal") or (entry.snapshot if entry else {})
        if animal:
            try:
                care_date = date.fromisoformat(str(animal.get("date", ""))).strftime("%d.%m.%Y")
            except ValueError:
                care_date = animal.get("date", "-")
            details.append(f"Животное: {animal.get('tag', '-')}; обработка: {animal.get('care', '-')}; дата: {care_date}")
    return details


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("История неизменяема. Создайте новую запись.")

    def delete(self):
        raise ValidationError("Удаление истории запрещено.")


class AppendOnly(models.Model):
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("История неизменяема. Создайте новую запись.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Удаление истории запрещено.")


class Product(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=10, choices=[
        ("live", "Животное"), ("meat", "Мясо"), ("offal", "Субпродукт"),
    ])
    counted = models.BooleanField(default=True)
    parts_per_animal = models.PositiveSmallIntegerField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Order(models.Model):
    kind = models.CharField(max_length=10, choices=[("live", "Живьём"), ("meat", "Мясо")])
    customer = models.CharField(max_length=200)
    contact = models.CharField(max_length=200, blank=True)
    note = models.TextField(blank=True)
    required_heads = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=12, default="open", choices=[
        ("open", "Открыта"), ("partial", "Частично выполнена"),
        ("fulfilled", "Выполнена"), ("closed", "Закрыта"),
    ])
    # Future website bridge: retries cannot create duplicate incoming orders.
    external_key = models.CharField(max_length=160, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-id"]


class OrderLine(models.Model):
    order = models.ForeignKey(Order, related_name="lines", on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    weight = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity = models.PositiveIntegerField(default=0)
    animal_type = models.CharField(max_length=10, blank=True, default="", choices=ANIMAL_TYPE_CHOICES)
    # Retained for existing orders; new forms collect the precise animal type.
    sex = models.CharField(max_length=6, blank=True, choices=[("", "Любой"), ("male", "Самец"), ("female", "Самка")])
    age_min = models.PositiveIntegerField(null=True, blank=True)
    age_max = models.PositiveIntegerField(null=True, blank=True)
    purity_min = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    purity_max = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)

    @property
    def type_requirement(self):
        return type_requirement(self.animal_type, self.sex)

    class Meta:
        constraints = [models.CheckConstraint(
            check=Q(weight__gte=0) & (Q(weight__gt=0) | Q(quantity__gt=0)),
            name="inventory_order_line_positive",
        )]


class Document(models.Model):
    class Kind(models.TextChoices):
        SP54 = "sp54", "СП-54"
        SP55 = "sp55", "СП-55"
        INVOICE = "invoice", "Товарная накладная"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    state = models.CharField(max_length=12, default="draft", choices=[
        ("draft", "Черновик"), ("ready", "На проверке"),
        ("confirmed", "Подтверждён"), ("reversed", "Сторнирован"),
    ])
    number = models.CharField(max_length=100, blank=True)
    date = models.DateField(default=timezone.localdate)
    payload = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=0)
    order = models.ForeignKey(Order, null=True, blank=True, related_name="invoices", on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="inventory_documents", on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="inventory_confirmations", on_delete=models.PROTECT)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.get_kind_display()} № {self.number or self.pk}"


class AnimalCase(AppendOnly):
    source_tag_id = models.PositiveBigIntegerField(unique=True)
    animal_type = models.CharField(max_length=10)
    tag_number = models.CharField(max_length=100)
    kind = models.CharField(max_length=10)
    archive_date = models.DateField()
    source_fingerprint = models.CharField(max_length=64)
    snapshot = models.JSONField(default=dict)
    receipt = models.ForeignKey(Document, related_name="animals", on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)


class DocumentVersion(AppendOnly):
    document = models.ForeignKey(Document, related_name="versions", on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    filename = models.CharField(max_length=180)
    content_type = models.CharField(max_length=100)
    # Private and transactional: no public media URL, no overwritten filesystem file.
    content = models.BinaryField()
    sha256 = models.CharField(max_length=64)
    snapshot = models.JSONField(default=dict)
    origin = models.CharField(max_length=12, default="generated")
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-number"]
        constraints = [models.UniqueConstraint(fields=["document", "number"], name="inventory_document_version_unique")]


class StockLot(AppendOnly):
    animal = models.ForeignKey(AnimalCase, related_name="lots", on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)


class StockMovement(AppendOnly):
    lot = models.ForeignKey(StockLot, related_name="movements", on_delete=models.PROTECT)
    kind = models.CharField(max_length=12, choices=[
        ("receipt", "Приход"), ("sale", "Реализация"), ("reversal", "Сторно"),
        ("cut_in", "Выход разделки"), ("cut_out", "Передано в разделку"),
    ])
    weight = models.DecimalField(max_digits=12, decimal_places=3)
    quantity = models.IntegerField(default=0)
    document = models.ForeignKey(Document, null=True, blank=True, related_name="movements", on_delete=models.PROTECT)
    order_line = models.ForeignKey(OrderLine, null=True, blank=True, on_delete=models.PROTECT)
    operation = models.UUIDField(default=uuid.uuid4, db_index=True)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(check=~Q(weight=0), name="inventory_movement_nonzero"),
            models.UniqueConstraint(fields=["document", "lot", "kind"], name="inventory_document_lot_kind_unique"),
        ]


class AuditEvent(AppendOnly):
    document = models.ForeignKey(Document, null=True, blank=True, related_name="events", on_delete=models.PROTECT)
    order = models.ForeignKey(Order, null=True, blank=True, related_name="events", on_delete=models.PROTECT)
    action = models.CharField(max_length=50)
    data = models.JSONField(default=dict)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]

    @transaction.atomic
    def save(self, *args, **kwargs):
        from begunici.app_types.animals.models_user_log import UserActionLog

        result = super().save(*args, **kwargs)
        details = [self.action_label]
        if self.document_id:
            object_type = {"sp54": "Акт СП-54", "sp55": "Акт СП-55", "invoice": "Товарная накладная"}[self.document.kind]
            object_id = str(self.document_id)
            details.append(str(self.document))
            tags = list(self.document.animals.values_list("tag_number", flat=True))
            if tags:
                details.append("Животные: " + ", ".join(tags))
            details.append(f"Дата документа: {self.document.date:%d.%m.%Y}")
            payload = self.document.payload
            if self.document.kind == "invoice":
                details.append("Получатель: " + str(payload.get("customer", "")))
                lines = payload.get("lines", [])
                lots = {lot.pk: lot for lot in StockLot.objects.select_related("animal", "product").filter(pk__in=[line["lot_id"] for line in lines])}
                for line in lines:
                    lot = lots.get(line["lot_id"])
                    if lot:
                        details.append(f"{lot.animal.tag_number}, {lot.product.name}: {line['weight']} кг / {line['quantity']} шт.")
            else:
                cases = {str(case.pk): case.tag_number for case in self.document.animals.all()}
                products = dict(Product.objects.values_list("code", "name"))
                for line in payload.get("outputs", []):
                    label = "Брак" if line.get("rejected") else "Выход"
                    details.append(f"{label}: {cases.get(str(line['animal_id']), '-')}, {products.get(line['product'], line['product'])}: {line['weight']} кг / {line['quantity']} шт.")
            if self.order_id:
                details.append(f"Заявка № {self.order_id}")
        elif self.order_id:
            object_type, object_id = "Складская заявка", str(self.order_id)
            details.append(f"Заявка № {self.order_id}; получатель: {self.order.customer}")
        else:
            object_type, object_id = "Складской учёт", ""
        if self.summary:
            details.append(self.summary)
        if self.action == "cut":
            lots = StockLot.objects.filter(pk__in=self.data.get("outputs", [])).select_related("product")
            for lot in lots:
                movement = lot.movements.filter(kind="cut_in", operation=self.data.get("operation")).first()
                if movement:
                    details.append(f"Получено: {lot.product.name}: {movement.weight} кг / {movement.quantity} шт.")
        UserActionLog.objects.create(
            user=self.actor, action_type=self.action_label[:50],
            object_type=object_type, object_id=object_id,
            description="; ".join(details), timestamp=self.created_at,
            additional_data={"inventory_event_id": self.pk, "document_id": self.document_id,
                             "order_id": self.order_id, "action": self.action, "data": self.data},
        )
        return result

    @property
    def action_label(self):
        return {
            "version_created": "Сохранена версия документа", "receipt_confirmed": "Акт подтверждён, оформлен приход",
            "invoice_confirmed": "Товарная накладная проведена", "invoice_reversed": "Сторно товарной накладной",
            "order_created": "Заявка создана", "order_closed": "Заявка закрыта",
            "returned_to_vet": "Акт возвращён ветврачу", "cut": "Разделка продукции",
            "product_created": "Добавлена номенклатура", "product_updated": "Изменена номенклатура",
        }.get(self.action, self.action)

    @property
    def summary(self):
        parts = []
        if self.data.get("version") or self.data.get("revision"):
            parts.append(f"Версия {self.data.get('version') or self.data.get('revision')}")
        if self.action == "cut":
            parts.append(f"Передано {self.data.get('weight')} кг / {self.data.get('quantity')} шт.; потери {self.data.get('loss_weight')} кг")
        if self.data.get("reason"):
            parts.append(str(self.data["reason"]))
        if self.data.get("kept_open"):
            parts.append("Заявка оставлена открытой для дополнения")
        return "; ".join(parts)
