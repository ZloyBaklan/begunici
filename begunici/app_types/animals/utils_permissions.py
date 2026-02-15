from django.contrib.auth.models import User


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
    return role == 'admin'


def get_user_permissions(user):
    """Возвращает словарь с разрешениями пользователя"""
    return {
        'role': get_user_role(user),
        'can_view_statistics': can_view_statistics(user),
        'can_delete_objects': can_delete_objects(user),
        'can_restore_from_archive': can_restore_from_archive(user),
        'can_access_admin_panel': can_access_admin_panel(user),
    }