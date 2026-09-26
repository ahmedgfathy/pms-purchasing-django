from django.urls import path

from core import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("rfq/", views.rfq_list, name="rfq_list"),
    path("rfq/create/", views.rfq_create, name="rfq_create"),
    path("rfq/<int:pk>/", views.rfq_detail, name="rfq_detail"),
    path("rfq/<int:pk>/edit/", views.rfq_edit, name="rfq_edit"),
    path("rfq/<int:pk>/delete/", views.rfq_delete, name="rfq_delete"),
    path("rfq/<int:pk>/tender/create/", views.rfq_tender_create, name="rfq_tender_create"),
    # tenders by market (sidebar: Local Tender / Foreign Tender)
    path("tenders/local/", views.local_tender, name="local_tender"),
    path("tenders/foreign/", views.foreign_tender, name="foreign_tender"),
    # vendor list module (Access: Vendor List / Vendor View / New Vendor Enter)
    path("vendor-list/", views.vendor_list, name="vendor_list"),
    path("vendor-list/<int:pk>/", views.operation_detail, name="operation_detail"),
    path("vendor-list/<int:pk>/vendors/add/", views.operation_vendor_add, name="operation_vendor_add"),
    path("vendor-list/<int:pk>/vendors/<int:vendor_pk>/remove/",
         views.operation_vendor_remove, name="operation_vendor_remove"),
    path("vendors/", views.vendor_register, name="vendor_register"),
    path("vendors/new/", views.vendor_create, name="vendor_create"),
    path("vendors/<int:pk>/", views.vendor_detail, name="vendor_detail"),
    path("vendors/<int:pk>/edit/", views.vendor_edit, name="vendor_edit"),
    path("vendors/<int:pk>/activities/add/", views.vendor_activity_add, name="vendor_activity_add"),
    path("vendors/<int:pk>/activities/<int:activity_pk>/remove/",
         views.vendor_activity_remove, name="vendor_activity_remove"),
]
