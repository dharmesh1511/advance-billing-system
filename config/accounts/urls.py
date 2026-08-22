from django.urls import path
from . import views

urlpatterns = [
    path("admin/login/",views.admin_login,name="admin_login"),
    path("distributor/login/",views.distributor_login,name="distributor_login"),
    path("admin/dashboard/",views.admin_dashboard,name="admin_dashboard"),
    path("distributor/dashboard/",views.distributor_dashboard,name="distributor_dashboard"),
    path("logout/",views.logout_view,name="logout"),
    
]