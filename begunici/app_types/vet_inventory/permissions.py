from functools import wraps

from django.core.exceptions import PermissionDenied
from begunici.app_types.inventory.permissions import can_manage_inventory, can_prepare_slaughter


def can_view(user):
    return can_manage_inventory(user) or can_prepare_slaughter(user)


def can_treat(user):
    return can_prepare_slaughter(user)


def require_treat(user):
    if not can_treat(user):
        raise PermissionDenied("Нормы и расход обработок изменяют vet и admin.")


def access_required():
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not can_view(request.user):
                raise PermissionDenied("Склад ветпрепаратов доступен vet, finans и admin.")
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
