from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from .forms import CustomerForm
from .models import Customer


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


@login_required(login_url="/distributor/login/")
def customer_list(request):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    queryset = Customer.objects.filter(distributor=request.user)
    total_count = queryset.count()

    query = request.GET.get("q", "").strip()

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(address__icontains=query) |
            Q(city__icontains=query) |
            Q(state__icontains=query) |
            Q(pincode__icontains=query)
        )

    filtered_count = queryset.count()

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "billing/customer_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "total_count": total_count,
            "filtered_count": filtered_count,
        }
    )


@login_required(login_url="/distributor/login/")
def edit_customer(request, pk):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    customer = get_object_or_404(Customer, pk=pk, distributor=request.user)
    error = None

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Customer updated successfully.")
                return redirect("customer_list")
            except Exception as e:
                error = "Unable to update customer information right now. Please try again."
    else:
        form = CustomerForm(instance=customer)

    return render(
        request,
        "billing/edit_customer.html",
        {
            "form": form,
            "customer": customer,
            "error": error
        }
    )


