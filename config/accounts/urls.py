from django.urls import path
from . import views
from billing import views as billing_views

urlpatterns = [
    path("admin/login/", views.admin_login, name="admin_login"),
    path("distributor/login/", views.distributor_login, name="distributor_login"),
    path("distributor/register/", views.distributor_register, name="distributor_register"),
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("distributor/dashboard/", views.distributor_dashboard, name="distributor_dashboard"),
    path("distributor/profile/", views.distributor_profile, name="distributor_profile"),
    path("distributor/profile/edit/", views.edit_distributor_profile, name="edit_distributor_profile"),
    path("distributor/profile/update/", views.edit_distributor_profile, name="distributor_profile_edit"),
    path("distributor/customers/", billing_views.customer_list, name="customer_list"),
    path("distributor/customers/add/", billing_views.add_customer, name="add_customer"),
    path("distributor/customers/<int:pk>/edit/", billing_views.edit_customer, name="customer_edit"),
    path("distributor/customers/<int:pk>/delete/", billing_views.delete_customer, name="customer_delete"),
    path("distributor/products/", billing_views.product_list, name="product_list"),
    path("distributor/products/add/", billing_views.add_product, name="product_add"),
    path("distributor/products/add/", billing_views.add_product, name="add_product"),
    path("distributor/products/<int:pk>/edit/", billing_views.edit_product, name="product_edit"),
    path("distributor/products/<int:pk>/edit/", billing_views.edit_product, name="edit_product"),
    path("distributor/products/<int:pk>/delete/", billing_views.delete_product, name="product_delete"),
    path("distributor/products/<int:pk>/delete/", billing_views.delete_product, name="delete_product"),

    path("logout/", views.logout_view, name="logout"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    path("reset-password/", views.reset_password, name="reset_password"),
]