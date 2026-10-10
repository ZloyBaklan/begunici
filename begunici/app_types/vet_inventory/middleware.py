"""Pass the author to the independent treatment bridge without changing views."""
from contextvars import ContextVar

current_actor = ContextVar("vet_inventory_actor", default=None)


class VetInventoryActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        actor = request.user if request.user.is_authenticated else None
        token = current_actor.set(actor)
        try:
            return self.get_response(request)
        finally:
            current_actor.reset(token)
