from functools import wraps

from django.core.exceptions import PermissionDenied
from begunici.app_types.inventory.permissions import (
    can_manage_inventory, can_prepare_slaughter, can_view_inventory, is_inventory_read_only, require_inventory,
)


def can_view(user):
    return can_view_inventory(user) or can_prepare_slaughter(user)


def can_treat(user):
    return can_prepare_slaughter(user)


def require_treat(user):
    if not can_treat(user):
        raise PermissionDenied("Нормы и расход обработок изменяют vet и admin.")


def can_receive(user):
    return can_treat(user) or can_manage_inventory(user)


def require_receiving(user):
    if not can_receive(user):
        raise PermissionDenied("Номенклатуру и приход ветпрепаратов оформляют vet, finans и admin.")


def can_edit_document(user, kind):
    return can_receive(user) if kind == "receipt" else can_manage_inventory(user)


def require_document_editor(user, kind):
    if kind == "receipt":
        require_receiving(user)
    else:
        require_inventory(user)


def access_required(*, write=False):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not can_view(request.user):
                raise PermissionDenied("Склад ветпрепаратов доступен vet, finans и admin.")
            if is_inventory_read_only(request.user) and (write or request.method not in {"GET", "HEAD", "OPTIONS"}):
                raise PermissionDenied("Складской учёт доступен только для просмотра.")
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
