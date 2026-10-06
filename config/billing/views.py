from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, ProtectedError, RestrictedError
from django.core.paginator import Paginator
from .forms import CustomerForm, ProductForm
from .models import Customer, Product



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


@login_required(login_url="/distributor/login/")
def delete_customer(request, pk):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    customer = get_object_or_404(Customer, pk=pk, distributor=request.user)

    if request.method == "POST":
        customer_name = customer.name
        try:
            customer.delete()
            messages.success(request, f'"{customer_name}" deleted successfully.')
        except (ProtectedError, RestrictedError):
            messages.error(request, f'"{customer_name}" cannot be deleted because it is used in existing billing records.')
        except Exception as e:
            messages.error(request, f'Unable to delete "{customer_name}" right now. Please try again.')
        return redirect("customer_list")

    return redirect("customer_list")



@login_required(login_url="/distributor/login/")
def add_product(request):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    error = None

    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            try:
                product = form.save(commit=False)
                product.distributor = request.user
                product.save()

                messages.success(request, "Product added successfully.")
                return redirect("distributor_dashboard")
            except Exception as e:
                error = "Unable to add product right now. Please try again."
    else:
        form = ProductForm()

    return render(
        request,
        "billing/add_product.html",
        {
            "form": form,
            "error": error
        }
    )


@login_required(login_url="/distributor/login/")
def product_list(request):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    queryset = Product.objects.filter(distributor=request.user)
    total_count = queryset.count()

    query = request.GET.get("q", "").strip()

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(category__icontains=query) |
            Q(sku__icontains=query) |
            Q(description__icontains=query)
        )

    filtered_count = queryset.count()

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "billing/product_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "total_count": total_count,
            "filtered_count": filtered_count,
        }
    )


@login_required(login_url="/distributor/login/")
def edit_product(request, pk):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    product = get_object_or_404(Product, pk=pk, distributor=request.user)
    error = None

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Product updated successfully.")
                return redirect("product_list")
            except Exception as e:
                error = "Unable to update product right now. Please try again."
    else:
        form = ProductForm(instance=product)

    return render(
        request,
        "billing/edit_product.html",
        {
            "form": form,
            "product": product,
            "error": error
        }
    )


@login_required(login_url="/distributor/login/")
def delete_product(request, pk):
    if not is_distributor(request.user):
        return redirect("distributor_login")

    product = get_object_or_404(Product, pk=pk, distributor=request.user)

    if request.method == "POST":
        product_name = product.name
        try:
            product.delete()
            messages.success(request, f'"{product_name}" deleted successfully.')
        except (ProtectedError, RestrictedError):
            messages.error(request, f'"{product_name}" cannot be deleted because it is used in existing billing records.')
        except Exception:
            messages.error(request, f'Unable to delete "{product_name}" right now. Please try again.')
        return redirect("product_list")

    return redirect("product_list")

