from functools import wraps

from django.core.exceptions import PermissionDenied


def can_manage_inventory(user):
    return bool(user.is_authenticated and user.is_active and (
        user.is_superuser or user.username in {"admin", "finans"}
        or user.groups.filter(name="Admin").exists()
    ))


def can_prepare_slaughter(user):
    return bool(
        user.is_authenticated and user.is_active and (
            user.is_superuser or user.username in {"admin", "vet"}
            or user.groups.filter(name__in=["Admin", "Vet"]).exists()
        )
    )


def can_access_slaughter(user):
    return can_prepare_slaughter(user) or can_manage_inventory(user)


def require_inventory(user):
    if not can_manage_inventory(user):
        raise PermissionDenied("Складской учёт доступен finans и admin.")


def require_slaughter(user):
    if not can_prepare_slaughter(user):
        raise PermissionDenied("Подготовка СП-55 доступна ветврачу и admin.")


def access_required(slaughter=False):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if slaughter:
                if not can_access_slaughter(request.user):
                    raise PermissionDenied("Нет доступа к СП-55.")
            else:
                require_inventory(request.user)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
