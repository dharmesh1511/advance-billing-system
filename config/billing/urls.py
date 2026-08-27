from django.urls import path
from . import views

urlpatterns = [
    path("distributor/customers/", views.customer_list, name="billing_customer_list"),
    path("distributor/customers/add/", views.add_customer, name="billing_add_customer"),
    path("distributor/customers/<int:pk>/edit/", views.edit_customer, name="billing_edit_customer"),
]