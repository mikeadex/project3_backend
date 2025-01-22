from django.shortcuts import render


# Create your views here.
def trainer(request):
    return render(request, "trainer.html")
