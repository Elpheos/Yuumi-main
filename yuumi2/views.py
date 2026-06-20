from django.shortcuts import render


def home(request):
    return render(request, "yuumi2/home.html")
