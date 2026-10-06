from django.urls import path
from . import views

urlpatterns = [
    path("distributor/customers/", views.customer_list, name="billing_customer_list"),
    path("distributor/customers/add/", views.add_customer, name="billing_add_customer"),
    path("distributor/customers/<int:pk>/edit/", views.edit_customer, name="billing_edit_customer"),
    path("distributor/customers/<int:pk>/delete/", views.delete_customer, name="billing_delete_customer"),
    path("distributor/products/", views.product_list, name="billing_product_list"),
    path("distributor/products/add/", views.add_product, name="billing_add_product"),
    path("distributor/products/<int:pk>/edit/", views.edit_product, name="billing_edit_product"),
    path("distributor/products/<int:pk>/delete/", views.delete_product, name="billing_delete_product"),
]