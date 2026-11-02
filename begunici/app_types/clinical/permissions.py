from functools import wraps
from django.core.exceptions import PermissionDenied


def roles(user):
    if user is None or not user.is_authenticated or not user.is_active:
        return set()
    result = {user.username.lower()}
    result.update(name.lower() for name in user.groups.values_list("name", flat=True))
    if user.is_superuser:
        result.add("admin")
    return result


def can_manage(user):
    return getattr(user, "username", "").lower() != "main" and bool(roles(user) & {"admin", "vet", "zootech"})


def can_admit(user):
    return can_manage(user) or "main" in roles(user)


def can_view(user):
    return can_admit(user) or "finans" in roles(user)


def require_manage(user):
    if not can_manage(user):
        raise PermissionDenied("Лечение ведут и завершают vet, zootech и admin.")


def require_admit(user):
    if not can_admit(user):
        raise PermissionDenied("Назначение «Лечение» доступно vet, zootech, main и admin.")


def access_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not can_view(request.user):
            raise PermissionDenied("Нет доступа к истории болезни.")
        return view(request, *args, **kwargs)
    return wrapped
