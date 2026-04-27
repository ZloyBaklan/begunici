from django.shortcuts import render

def home(request):
    return render(request, "home.html")

def products(request):
    return render(request, "products.html")

def tribe(request):
    return render(request, "tribe.html")

def contacts(request):
    return render(request, "contacts.html")
