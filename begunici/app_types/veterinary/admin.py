from django.contrib import admin
from .models import Veterinary, Status, Tag, VeterinaryCare, WeightRecord, Place

admin.site.register(Status)
admin.site.register(Place)
admin.site.register(VeterinaryCare)
admin.site.register(Veterinary)
admin.site.register(Tag)
admin.site.register(WeightRecord)
