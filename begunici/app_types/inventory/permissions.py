from functools import wraps

from django.core.exceptions import PermissionDenied


def is_inventory_read_only(user):
    return bool(user.is_authenticated and user.is_active and user.username == "main")


def can_manage_inventory(user):
    return bool(user.is_authenticated and user.is_active and user.username != "main" and (
        user.is_superuser or user.username in {"admin", "finans"}
        or user.groups.filter(name="Admin").exists()
    ))


def can_view_inventory(user):
    return is_inventory_read_only(user) or can_manage_inventory(user)


def can_prepare_slaughter(user):
    return bool(
        user.is_authenticated and user.is_active and user.username != "main" and (
            user.is_superuser or user.username in {"admin", "vet"}
            or user.groups.filter(name__in=["Admin", "Vet"]).exists()
        )
    )


def can_access_slaughter(user):
    return bool(user.is_authenticated and user.is_active and (
        user.username == "main" or can_prepare_slaughter(user) or can_manage_inventory(user)
    ))


def can_edit_meat_catalog(user):
    return can_manage_inventory(user)


def require_meat_catalog_editor(user):
    require_inventory(user)


def require_inventory(user, *, write=True):
    if not (can_manage_inventory(user) if write else can_view_inventory(user)):
        raise PermissionDenied("Изменение складского учёта доступно finans и admin." if write else "Нет доступа к складскому учёту.")


def require_slaughter(user):
    if not can_prepare_slaughter(user):
        raise PermissionDenied("Подготовка СП-55 доступна ветврачу и admin.")


def access_required(slaughter=False, *, write=False):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if slaughter:
                if not can_access_slaughter(request.user):
                    raise PermissionDenied("Нет доступа к СП-55.")
                if is_inventory_read_only(request.user) and (write or request.method not in {"GET", "HEAD", "OPTIONS"}):
                    raise PermissionDenied("Складской учёт доступен только для просмотра.")
            else:
                require_inventory(request.user, write=write or request.method not in {"GET", "HEAD", "OPTIONS"})
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
