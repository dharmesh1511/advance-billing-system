from django.urls import path
from . import views

urlpatterns = [
    path("admin/login/", views.admin_login, name="admin_login"),
    path("distributor/login/", views.distributor_login, name="distributor_login"),
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("distributor/dashboard/", views.distributor_dashboard, name="distributor_dashboard"),
    path("logout/", views.logout_view, name="logout"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    path("reset-password/", views.reset_password, name="reset_password"),
]