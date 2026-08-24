from django.urls import path
from . import views

urlpatterns = [
    path("distributor/customers/add/", views.add_customer, name="billing_add_customer"),
]