from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import RFQForm, RFQItemFormSet
from .models import RFQ


class CustomLoginView(LoginView):
    template_name = "core/login.html"
    redirect_authenticated_user = True

    def get_redirect_url(self):
        return reverse("dashboard")


def logout_view(request):
    logout(request)
    return redirect("login")


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


@login_required(login_url="login")
def dashboard(request):
    return render(request, "core/dashboard.html", {})


@login_required(login_url="login")
def rfq_list(request):
    rfqs = RFQ.objects.select_related("requesting_department", "cost_center").all()

    status_filter = request.GET.get("status", "")
    market_filter = request.GET.get("market", "")
    search = request.GET.get("q", "")

    if status_filter:
        rfqs = rfqs.filter(status=status_filter)
    if market_filter:
        rfqs = rfqs.filter(market_type=market_filter)
    if search:
        rfqs = rfqs.filter(request_number__icontains=search)

    context = {
        "rfqs": rfqs,
        "status_choices": RFQ.Status.choices,
        "market_choices": RFQ.MarketType.choices,
        "current_status": status_filter,
        "current_market": market_filter,
        "current_search": search,
    }
    return render(request, "core/rfq_list.html", context)


@login_required(login_url="login")
def rfq_detail(request, pk):
    rfq = get_object_or_404(
        RFQ.objects.select_related("requesting_department", "vessel", "cost_center"),
        pk=pk,
    )
    items = rfq.items.all()
    return render(request, "core/rfq_detail.html", {"rfq": rfq, "items": items})


@login_required(login_url="login")
def rfq_create(request):
    if request.method == "POST":
        form = RFQForm(request.POST)
        formset = RFQItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            rfq = form.save(commit=False)
            rfq.created_by = request.user
            rfq.save()
            formset.instance = rfq
            formset.save()
            messages.success(request, f"RFQ {rfq.request_number} created successfully.")
            return redirect("rfq_detail", pk=rfq.pk)
    else:
        form = RFQForm()
        formset = RFQItemFormSet()
    return render(request, "core/rfq_form.html", {
        "form": form,
        "formset": formset,
        "title": "Create RFQ",
        "action": "create",
    })


@login_required(login_url="login")
def rfq_edit(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if request.method == "POST":
        form = RFQForm(request.POST, instance=rfq)
        formset = RFQItemFormSet(request.POST, instance=rfq)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"RFQ {rfq.request_number} updated successfully.")
            return redirect("rfq_detail", pk=rfq.pk)
    else:
        form = RFQForm(instance=rfq)
        formset = RFQItemFormSet(instance=rfq)
    return render(request, "core/rfq_form.html", {
        "form": form,
        "formset": formset,
        "rfq": rfq,
        "title": f"Edit RFQ {rfq.request_number}",
        "action": "edit",
    })


@login_required(login_url="login")
def rfq_delete(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if request.method == "POST":
        num = rfq.request_number
        rfq.delete()
        messages.success(request, f"RFQ {num} deleted.")
        return redirect("rfq_list")
    return render(request, "core/rfq_confirm_delete.html", {"rfq": rfq})
