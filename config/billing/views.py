from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomerForm


def is_distributor(user):
    return user.groups.filter(name="Distributor").exists()


@login_required(login_url="/distributor/login/")
def add_customer(request):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    error = None

    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            try:
                customer = form.save(commit=False)
                customer.distributor = request.user
                customer.save()

                messages.success(request, "Customer added successfully.")
                return redirect("distributor_dashboard")
            except Exception as e:
                error = "Unable to add customer right now. Please try again."
    else:
        form = CustomerForm()

    return render(
        request,
        "billing/add_customer.html",
        {
            "form": form,
            "error": error
        }
    )
