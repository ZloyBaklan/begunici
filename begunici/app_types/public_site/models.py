from django.db import models


class CatalogPhoto(models.Model):
    digest = models.CharField(max_length=64, primary_key=True)
    content_type = models.CharField(max_length=10)
    content = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)


class CatalogProduct(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    storefront_name = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=10, choices=[('meat', 'Мясо'), ('offal', 'Субпродукты')])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_unit = models.CharField(max_length=3, choices=[('kg', 'кг'), ('pcs', 'шт.')])
    photo = models.ForeignKey(CatalogPhoto, null=True, blank=True, on_delete=models.PROTECT)
    position = models.PositiveIntegerField()
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['position', 'code']


class CatalogSyncState(models.Model):
    name = models.CharField(max_length=10, primary_key=True)
    version = models.PositiveBigIntegerField(default=0)
    digest = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)


class CatalogSyncNonce(models.Model):
    nonce = models.CharField(max_length=32, primary_key=True)
    expires_at = models.DateTimeField(db_index=True)
