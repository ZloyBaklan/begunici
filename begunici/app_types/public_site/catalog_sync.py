"""One-way publication of a strictly limited catalogue, never warehouse records."""
import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from urllib.parse import urlsplit

import requests
from PIL import Image
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponseNotAllowed, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import CatalogPhoto, CatalogProduct, CatalogSyncNonce, CatalogSyncState


SYNC_PATH = '/site/catalog-sync/'
MAX_PRODUCTS = 1000
MAX_JSON = 1024 * 1024
MAX_PHOTO = 5 * 1024 * 1024
MAX_AGE = 300
PHOTO_TYPES = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}
PRODUCT_FIELDS = {'code', 'name', 'storefront_name', 'category', 'unit_price', 'price_unit', 'photo'}
HEX = re.compile(r'[a-f0-9]{64}\Z')
PRICE = re.compile(r'(?:0|[1-9][0-9]{0,7})\.[0-9]{2}\Z')


class SyncError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def catalogue_digest(products):
    return hashlib.sha256(canonical({'schema': 1, 'products': products})).hexdigest()


def signing_headers(key, action, body, *, timestamp=None, nonce=None):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    nonce = nonce or secrets.token_hex(16)
    digest = hashlib.sha256(body).hexdigest()
    message = '\n'.join(('POST', SYNC_PATH, action, timestamp, nonce, digest)).encode('ascii')
    return {'X-Catalog-Action': action, 'X-Catalog-Time': timestamp, 'X-Catalog-Nonce': nonce,
            'X-Catalog-Digest': digest,
            'X-Catalog-Signature': hmac.new(key.encode('utf-8'), message, hashlib.sha256).hexdigest(),
            'Content-Type': 'application/octet-stream' if action == 'photo' else 'application/json'}


def validate_manifest(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'version', 'products'}:
        raise SyncError('Invalid manifest fields')
    if type(value['schema']) is not int or value['schema'] != 1:
        raise SyncError('Unsupported schema')
    if type(value['version']) is not int or not 0 < value['version'] < 2 ** 63:
        raise SyncError('Invalid version')
    products = value['products']
    if not isinstance(products, list) or not 1 <= len(products) <= MAX_PRODUCTS:
        raise SyncError('An empty or oversized catalogue cannot be published')
    seen = set()
    for item in products:
        if not isinstance(item, dict) or set(item) != PRODUCT_FIELDS:
            raise SyncError('Invalid product fields')
        code = item['code']
        if not isinstance(code, str) or not re.fullmatch(r'[-a-zA-Z0-9_]{1,50}', code) or code in seen:
            raise SyncError('Invalid or duplicate product code')
        seen.add(code)
        for field in ('name', 'storefront_name'):
            text = item[field]
            if not isinstance(text, str) or len(text) > 120 or not all(c.isprintable() for c in text):
                raise SyncError('Invalid product name')
        if not item['name'].strip() or item['category'] not in ('meat', 'offal'):
            raise SyncError('Invalid product category or name')
        if item['price_unit'] not in ('kg', 'pcs'):
            raise SyncError('Invalid price unit')
        price = item['unit_price']
        if price is not None and (not isinstance(price, str) or not PRICE.fullmatch(price)):
            raise SyncError('Invalid price')
        if item['photo'] is not None and (not isinstance(item['photo'], str) or not HEX.fullmatch(item['photo'])):
            raise SyncError('Invalid photograph digest')
    return value


def missing_photos(products):
    wanted = {p['photo'] for p in products if p['photo']}
    return sorted(wanted - set(CatalogPhoto.objects.filter(pk__in=wanted).values_list('pk', flat=True)))


def version_status(state, manifest, digest):
    if state and manifest['version'] < state.version:
        return 'stale'
    if state and manifest['version'] == state.version:
        return 'unchanged' if state.digest == digest else 'version_conflict'
    return 'ready'


def publish(manifest):
    digest = catalogue_digest(manifest['products'])
    with transaction.atomic():
        state, _ = CatalogSyncState.objects.select_for_update().get_or_create(name='receiver')
        status = version_status(state, manifest, digest)
        if status != 'ready':
            return {'status': status, 'version': state.version}
        missing = missing_photos(manifest['products'])
        if missing:
            return {'status': 'missing_photos', 'missing': missing, 'version': state.version}
        existing = {p.code: p for p in CatalogProduct.objects.select_for_update().all()}
        for position, row in enumerate(manifest['products']):
            values = {k: row[k] for k in ('name', 'storefront_name', 'category', 'price_unit')}
            values.update(unit_price=Decimal(row['unit_price']) if row['unit_price'] is not None else None,
                          photo_id=row['photo'], position=position)
            product = existing.get(row['code'])
            if product is None:
                CatalogProduct.objects.create(code=row['code'], **values)
            elif any(getattr(product, k) != v for k, v in values.items()):
                for key, val in values.items():
                    setattr(product, key, val)
                product.revision += 1
                product.save()
        CatalogProduct.objects.exclude(code__in=[p['code'] for p in manifest['products']]).delete()
        state.version, state.digest, state.updated_at = manifest['version'], digest, timezone.now()
        state.save()
        CatalogPhoto.objects.defer('content').filter(created_at__lt=timezone.now() - timedelta(days=30),
                                                     catalogproduct__isnull=True).delete()
        return {'status': 'published', 'version': state.version, 'products': len(manifest['products'])}


def _response(data, status=200):
    response = JsonResponse(data, status=status)
    response['Cache-Control'] = 'no-store'
    return response


@csrf_exempt
def receive_catalog(request):
    key = settings.CATALOG_SYNC_KEY
    if settings.APP_MODE != 'public' or len(key) < 32 or settings.DEBUG:
        return _response({'error': 'Not found'}, 404)
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.is_secure():
        return _response({'error': 'HTTPS required'}, 400)
    action = request.headers.get('X-Catalog-Action', '')
    stamp = request.headers.get('X-Catalog-Time', '')
    nonce = request.headers.get('X-Catalog-Nonce', '')
    digest = request.headers.get('X-Catalog-Digest', '')
    signature = request.headers.get('X-Catalog-Signature', '')
    if (action not in ('status', 'photo', 'publish') or not re.fullmatch(r'[0-9]{1,12}', stamp)
            or abs(time.time() - int(stamp)) > MAX_AGE or not re.fullmatch(r'[a-f0-9]{32}', nonce)
            or not HEX.fullmatch(digest) or not HEX.fullmatch(signature)):
        return _response({'error': 'Authentication failed'}, 403)
    message = '\n'.join(('POST', SYNC_PATH, action, stamp, nonce, digest)).encode('ascii')
    expected = hmac.new(key.encode('utf-8'), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return _response({'error': 'Authentication failed'}, 403)
    expected_type = 'application/octet-stream' if action == 'photo' else 'application/json'
    if request.content_type != expected_type:
        return _response({'error': 'Unsupported content type'}, 415)
    maximum = MAX_PHOTO if action == 'photo' else MAX_JSON
    try:
        if int(request.META.get('CONTENT_LENGTH') or 0) > maximum:
            return _response({'error': 'Request too large'}, 413)
        body = request.read(maximum + 1)
    except (ValueError, OSError):
        return _response({'error': 'Invalid request'}, 400)
    if len(body) > maximum:
        return _response({'error': 'Request too large'}, 413)
    if not hmac.compare_digest(hashlib.sha256(body).hexdigest(), digest):
        return _response({'error': 'Authentication failed'}, 403)
    try:
        with transaction.atomic():
            CatalogSyncNonce.objects.filter(expires_at__lt=timezone.now()).delete()
            CatalogSyncNonce.objects.create(nonce=nonce, expires_at=timezone.now() + timedelta(seconds=MAX_AGE * 2))
    except IntegrityError:
        return _response({'error': 'Authentication failed'}, 403)
    try:
        if action == 'photo':
            if not CatalogPhoto.objects.filter(pk=digest).exists():
                try:
                    with Image.open(BytesIO(body), formats=tuple(PHOTO_TYPES)) as image:
                        if image.width * image.height > 25_000_000:
                            raise SyncError('Photograph resolution is too large')
                        image.load()
                        content_type = PHOTO_TYPES[image.format]
                except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
                    raise SyncError('Invalid photograph') from None
                CatalogPhoto.objects.get_or_create(digest=digest, defaults={'content_type': content_type, 'content': body})
            return _response({'status': 'stored', 'digest': digest})
        manifest = validate_manifest(json.loads(body))
        if action == 'status':
            state = CatalogSyncState.objects.filter(name='receiver').first()
            status = version_status(state, manifest, catalogue_digest(manifest['products']))
            result = {'status': status, 'version': state.version if state else 0}
            if status == 'ready':
                result['missing'] = missing_photos(manifest['products'])
        else:
            result = publish(manifest)
        return _response(result, 409 if result['status'] in ('stale', 'version_conflict', 'missing_photos') else 200)
    except (SyncError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return _response({'error': 'Invalid catalogue data'}, 400)


def sender_config():
    url, key = settings.CATALOG_SYNC_URL, settings.CATALOG_SYNC_KEY
    try:
        parsed = urlsplit(url)
        parsed.port
    except ValueError:
        raise SyncError('Invalid CATALOG_SYNC_URL') from None
    if settings.APP_MODE != 'internal':
        raise SyncError('Sending is permitted only in internal mode')
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path != SYNC_PATH):
        raise SyncError('CATALOG_SYNC_URL must be an HTTPS URL ending with ' + SYNC_PATH)
    if len(key) < 32:
        raise SyncError('CATALOG_SYNC_KEY must contain at least 32 characters')
    return url, key


def capture_catalogue():
    from begunici.app_types.inventory.models import Product, ProductPhoto

    with transaction.atomic():
        state, _ = CatalogSyncState.objects.select_for_update().get_or_create(name='sender')
        products = list(Product.objects.select_for_update().filter(category__in=('meat', 'offal'))
                        .order_by('pk')[:MAX_PRODUCTS + 1])
        if not 1 <= len(products) <= MAX_PRODUCTS:
            raise SyncError('An empty or oversized catalogue cannot be published')
        rows, photos = [], {}
        for product in products:
            photo = ProductPhoto.objects.filter(product=product).only('pk', 'content').first()
            if photo and len(photo.content) > MAX_PHOTO:
                raise SyncError('Source photograph is too large')
            digest = hashlib.sha256(bytes(photo.content)).hexdigest() if photo else None
            if photo:
                photos[digest] = photo.pk
            rows.append({'code': product.code, 'name': product.name, 'storefront_name': product.storefront_name,
                         'category': product.category, 'unit_price': format(product.unit_price, '.2f')
                         if product.unit_price is not None else None, 'price_unit': product.price_unit, 'photo': digest})
        manifest = {'schema': 1, 'version': max(1, state.version), 'products': rows}
        validate_manifest(manifest)
        if len(canonical(manifest)) > MAX_JSON:
            raise SyncError('Catalogue metadata is too large')
        digest = catalogue_digest(rows)
        if state.digest != digest or state.version < 1:
            state.version += 1
            state.digest, state.updated_at = digest, None
            state.save()
        manifest['version'] = state.version
        return manifest, photos


def send_catalogue(session=None):
    from begunici.app_types.inventory.models import ProductPhoto

    url, key = sender_config()
    manifest, photos = capture_catalogue()

    def exchange(client, action, body):
        try:
            with client.post(url, data=body, headers=signing_headers(key, action, body),
                             timeout=(10, 60), verify=True, allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise SyncError(f'Receiver returned HTTP {response.status_code}; publication not confirmed')
                chunks, size = [], 0
                for chunk in response.iter_content(8192):
                    size += len(chunk)
                    if size > 256 * 1024:
                        raise SyncError('Receiver response is too large')
                    chunks.append(chunk)
                result = json.loads(b''.join(chunks))
                if not isinstance(result, dict):
                    raise SyncError('Invalid receiver response')
                return result
        except (requests.RequestException, json.JSONDecodeError, UnicodeDecodeError, RecursionError):
            raise SyncError('Catalogue exchange failed; check connectivity and receiver configuration') from None

    def run(client):
        body = canonical(manifest)
        result = exchange(client, 'status', body)
        if result.get('status') == 'ready':
            missing = result.get('missing')
            if not isinstance(missing, list) or any(not isinstance(d, str) or d not in photos for d in missing):
                raise SyncError('Invalid missing photograph list')
            for digest in set(missing):
                photo = ProductPhoto.objects.filter(pk=photos[digest]).first()
                if photo is None:
                    raise SyncError('Source photograph changed during publication; retry later')
                content = bytes(photo.content)
                if len(content) > MAX_PHOTO or hashlib.sha256(content).hexdigest() != digest:
                    raise SyncError('Source photograph changed during publication; retry later')
                uploaded = exchange(client, 'photo', content)
                if uploaded.get('status') != 'stored' or uploaded.get('digest') != digest:
                    raise SyncError('Photograph was not acknowledged')
            result = exchange(client, 'publish', body)
        if result.get('status') not in ('unchanged', 'published') or result.get('version') != manifest['version']:
            raise SyncError('Publication was not acknowledged')
        CatalogSyncState.objects.filter(name='sender', version=manifest['version'],
                                        digest=catalogue_digest(manifest['products'])).update(updated_at=timezone.now())
        return {'status': result['status'], 'version': manifest['version'], 'products': len(manifest['products'])}

    if session is not None:
        return run(session)
    with requests.Session() as client:
        client.trust_env = False
        return run(client)
