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
]
