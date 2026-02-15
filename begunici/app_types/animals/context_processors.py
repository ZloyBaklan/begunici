def user_permissions(request):
    """Context processor для передачи прав пользователя в шаблоны"""
    permissions = {
        'can_view_statistics': True,
        'can_delete_animals': True,
        'can_restore_from_archive': True,
        'can_delete_vet_data': True,
        'can_access_admin_panel': False,
    }
    
    if request.user.is_authenticated:
        user_groups = [group.name for group in request.user.groups.all()]
        
        # Права для Vet и Zootech (ограниченные)
        if 'Vet' in user_groups or 'Zootech' in user_groups:
            permissions.update({
                'can_view_statistics': False,
                'can_delete_animals': False,
                'can_restore_from_archive': False,
                'can_delete_vet_data': False,
            })
        
        # Права для Admin (все права + панель администратора)
        elif 'Admin' in user_groups:
            permissions.update({
                'can_access_admin_panel': True,
            })
        
        # Права для main (все права, но без панели администратора)
        # Остаются по умолчанию True
    
    return {'user_permissions': permissions}