from django.contrib.auth.models import User


ANIMAL_ARCHIVE_DENIED_MESSAGE = 'Пользователю main запрещено архивировать животных'


def can_archive_animals(user):
    """Restrict the main account, without changing the other Main-group users."""
    return getattr(user, 'username', None) != 'main'


def get_user_role(user):
    """Возвращает роль пользователя"""
    if not user.is_authenticated:
        return None
    
    if user.groups.filter(name='Admin').exists():
        return 'admin'
    elif user.groups.filter(name='Main').exists():
        return 'main'
    elif user.groups.filter(name='Vet').exists():
        return 'vet'
    elif user.groups.filter(name='Zootech').exists():
        return 'zootech'
    
    return None


def can_view_statistics(user):
    """Проверяет, может ли пользователь видеть статистику"""
    role = get_user_role(user)
    return role in ['main', 'admin']


def can_edit_dashboard_plans(user):
    """Keep plan editing for existing unrestricted accounts, not veterinary viewers."""
    return bool(
        user.is_authenticated and user.is_active and user.username != 'vet'
        and not user.groups.filter(name__in=['Vet', 'Zootech']).exists()
    )


def can_view_dashboard_plans(user):
    return can_edit_dashboard_plans(user) or bool(
        user.is_authenticated and user.is_active
        and (user.username == 'vet' or user.groups.filter(name='Vet').exists())
    )


def can_delete_objects(user):
    """Проверяет, может ли пользователь удалять объекты"""
    role = get_user_role(user)
    return role in ['main', 'admin']


def can_restore_from_archive(user):
    """Проверяет, может ли пользователь восстанавливать из архива"""
    role = get_user_role(user)
    return role in ['main', 'admin']


def can_access_admin_panel(user):
    """Проверяет, может ли пользователь получить доступ к панели администратора"""
    role = get_user_role(user)
    return role in ['main', 'admin']


def get_user_permissions(user):
    """Возвращает словарь с разрешениями пользователя"""
    return {
        'role': get_user_role(user),
        'can_view_statistics': can_view_statistics(user),
        'can_view_plans': can_view_dashboard_plans(user),
        'can_edit_plans': can_edit_dashboard_plans(user),
        'can_delete_objects': can_delete_objects(user),
        'can_restore_from_archive': can_restore_from_archive(user),
        'can_archive_animals': can_archive_animals(user),
        'can_access_admin_panel': can_access_admin_panel(user),
    }
