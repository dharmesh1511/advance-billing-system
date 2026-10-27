from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    path("api/products/", api_views.ProductListCreateAPIView.as_view(), name="billing_api_product_list_create"),
    path("api/products/<int:pk>/", api_views.ProductDetailAPIView.as_view(), name="billing_api_product_detail"),
    path("api/qr/decode/", api_views.QRCodeDecodeAPIView.as_view(), name="billing_api_qr_decode"),
    path("distributor/customers/", views.customer_list, name="billing_customer_list"),
    path("distributor/customers/register/", views.customer_register_view, name="billing_customer_register"),
    path("distributor/customers/add/", views.add_customer, name="billing_add_customer"),
    path("distributor/customers/<int:pk>/edit/", views.edit_customer, name="billing_edit_customer"),
    path("distributor/customers/<int:pk>/delete/", views.delete_customer, name="billing_delete_customer"),
    path("distributor/products/", views.product_list, name="billing_product_list"),
    path("distributor/products/add/", views.add_product, name="billing_add_product"),
    path("distributor/products/<int:pk>/edit/", views.edit_product, name="billing_edit_product"),
    path("distributor/products/<int:pk>/delete/", views.delete_product, name="billing_delete_product"),
    path("distributor/products/<int:pk>/details/", views.product_details, name="billing_product_details"),
    path("distributor/invoices/", views.invoice_list, name="billing_invoice_list"),
    path("distributor/invoices/create/", views.create_invoice, name="billing_create_invoice"),
    path("distributor/invoices/<int:pk>/", views.invoice_detail, name="billing_invoice_detail"),
    path("distributor/invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("distributor/invoices/<int:pk>/details/", views.invoice_detail, name="billing_invoice_details"),
    path("distributor/invoices/<int:pk>/details/", views.invoice_detail, name="invoice_details"),
    path("distributor/invoices/<int:pk>/pdf/", views.invoice_pdf_view, name="billing_invoice_pdf"),
    path("distributor/invoices/<int:pk>/download-pdf/", views.invoice_pdf_download, name="billing_invoice_pdf_download"),
    path("distributor/invoices/<int:pk>/download-pdf/", views.invoice_pdf_download, name="invoice_pdf_download"),
    path("distributor/invoices/<int:pk>/qr/", views.invoice_qr_view, name="billing_invoice_qr"),
]