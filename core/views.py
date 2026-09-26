from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from .charts import PALETTE, abbrev, donut
from .forms import RFQForm, RFQItemFormSet, VendorActivityForm, VendorForm
from .models import (
    ClientCode, CostCenter, Department, Location, MainActivity, Operation,
    OperationVendor, Project, RFQ, SubActivity, Vendor, VendorActivity,
)


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


# ---------------------------------------------------------------------------
# Dashboard — every sum of the imported Access data, as cards and charts.
# No JS and no CDN: donuts are SVG (core/charts.py), bars are plain CSS.
# ---------------------------------------------------------------------------

_ICONS = {
    "tender": '<svg viewBox="0 0 20 20"><path d="M4 2h8l4 4v12H4z"/>'
              '<path d="M12 2v4h4"/><path d="M7 10h6M7 13h4"/></svg>',
    "vendor": '<svg viewBox="0 0 20 20"><circle cx="10" cy="7" r="3"/>'
              '<path d="M4 17a6 6 0 0 1 12 0"/></svg>',
    "list": '<svg viewBox="0 0 20 20"><rect x="3" y="3" width="14" height="14" rx="2"/>'
            '<path d="M7 8h6M7 11h6M7 14h3"/></svg>',
    "rfq": '<svg viewBox="0 0 20 20"><path d="M5 2h10v16H5z"/>'
           '<path d="M8 6h4M8 9h4M8 12h2"/></svg>',
    "activity": '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="3"/>'
                '<path d="M10 2v3M10 15v3M2 10h3M15 10h3M4.5 4.5l2 2M13.5 13.5l2 2'
                'M15.5 4.5l-2 2M6.5 13.5l-2 2"/></svg>',
    "money": '<svg viewBox="0 0 20 20"><path d="M10 3v14"/>'
             '<path d="M14 6H8a2.5 2.5 0 0 0 0 5h4a2.5 2.5 0 0 1 0 5H6"/></svg>',
}


def _donut(title, rows, colors=None):
    """(label, count) rows -> one donut chart dict for the template."""
    palette = colors or PALETTE
    rows = [(label, value) for label, value in rows if value]
    total = sum(value for _, value in rows)
    slices = [
        {
            "label": label,
            "value": "{:,}".format(value),
            "pct": "{:.1f}".format(value * 100 / total) if total else "0",
            "color": palette[index % len(palette)],
        }
        for index, (label, value) in enumerate(rows)
    ]
    return {
        "title": title,
        "slices": slices,
        "total": "{:,}".format(total),
        "svg": donut([value for _, value in rows],
                     [slice_["color"] for slice_ in slices]),
    }


def _bars(title, rows, limit=8, other=None, formatter=None):
    """(label, value) rows -> horizontal bars sized against the biggest."""
    fmt = formatter or (lambda value: "{:,}".format(value))
    rows = [(label, value) for label, value in rows if value]
    if other and len(rows) > limit:
        tail = rows[limit - 1:]
        rows = rows[:limit - 1] + [(other, sum(value for _, value in tail))]
    else:
        rows = rows[:limit]
    peak = max([value for _, value in rows], default=0)
    plotted = []
    for label, value in rows:
        pct = round(value * 100 / peak, 1) if peak else 0
        if value > 0 and pct < 0.8:
            pct = 0.8  # keep a hairline for tiny slices instead of nothing
        plotted.append({"label": label, "value": fmt(value), "pct": pct})
    return {"title": title, "rows": plotted}


def _count_by(field, blank):
    """Tender counts grouped by one of Operation's columns, biggest first."""
    grouped = Operation.objects.values(field).annotate(n=Count("id")).order_by("-n")
    return [(row[field] or blank, row["n"]) for row in grouped]


def _dashboard_context():
    blank = _("Not set")

    tender_total = Operation.objects.count()
    by_market = {
        row["market"]: row["n"]
        for row in Operation.objects.values("market").annotate(n=Count("id"))
    }
    local_tenders = by_market.get(Operation.Market.LOCAL, 0)
    foreign_tenders = by_market.get(Operation.Market.FOREIGN, 0)
    covered = (
        Operation.objects.filter(operation_vendors__isnull=False)
        .values("pk").distinct().count()
    )
    links = OperationVendor.objects.count()

    vendor_total = Vendor.objects.count()
    local_vendors = _scoped_vendors(Operation.Market.LOCAL).count()
    foreign_vendors = _scoped_vendors(Operation.Market.FOREIGN).count()
    registrations = VendorActivity.objects.count()
    main_activities = MainActivity.objects.count()
    sub_activities = SubActivity.objects.count()

    rfq_total = RFQ.objects.count()
    rfq_orphans = RFQ.objects.filter(tender__isnull=True).count()

    # The Access file mixes EGP, USD, EUR… — sum each currency on its own.
    value_by_currency = list(
        Operation.objects.filter(estimated_value__isnull=False)
        .values("currency")
        .annotate(total=Sum("estimated_value"), n=Count("id"))
        .order_by("-total")
    )
    base = next(
        (row for row in value_by_currency if row["currency"] == "جنيه مصرى"),
        value_by_currency[0] if value_by_currency else None,
    )

    cards = [
        {
            "label": _("Tenders"),
            "value": "{:,}".format(tender_total),
            "tag": "{} {} · {} {}".format(
                "{:,}".format(local_tenders), _("Local"),
                "{:,}".format(foreign_tenders), _("Foreign"),
            ),
            "href": reverse("rfq_list"),
            "icon": _ICONS["tender"],
        },
        {
            "label": _("Vendors"),
            "value": "{:,}".format(vendor_total),
            "tag": "{} {} · {} {}".format(
                "{:,}".format(local_vendors), _("Local"),
                "{:,}".format(foreign_vendors), _("Foreign"),
            ),
            "href": reverse("vendor_register"),
            "icon": _ICONS["vendor"],
        },
        {
            "label": _("Vendor List Entries"),
            "value": "{:,}".format(links),
            "tag": "{} / {} {}".format(
                "{:,}".format(covered), "{:,}".format(tender_total), _("Tenders"),
            ),
            "href": reverse("rfq_list"),
            "icon": _ICONS["list"],
        },
        {
            "label": _("RFQs"),
            "value": "{:,}".format(rfq_total),
            "tag": "{} {}".format("{:,}".format(rfq_orphans), _("without a tender")),
            "href": reverse("rfq_list"),
            "icon": _ICONS["rfq"],
        },
        {
            "label": _("Vendor Activities"),
            "value": "{:,}".format(registrations),
            "tag": "{} {} · {} {}".format(
                "{:,}".format(sub_activities), _("Sub Activities"),
                "{:,}".format(main_activities), _("Main Activities"),
            ),
            "href": reverse("vendor_register"),
            "icon": _ICONS["activity"],
        },
        {
            "label": _("Estimated Value"),
            "value": abbrev(base["total"]) if base else "—",
            "tag": "{} · {} {}".format(
                (base["currency"] or blank) if base else "",
                "{:,}".format(base["n"]) if base else "0",
                _("Tenders"),
            ),
            "href": reverse("rfq_list"),
            "icon": _ICONS["money"],
        },
    ]

    reg_counts = {
        row["registration_status_new"]: row["n"]
        for row in Vendor.objects.values("registration_status_new")
        .annotate(n=Count("supplier_id"))
    }
    reg_order = [
        ("مسجل", _("Registered")),
        ("غير مسجل", _("Not registered")),
        ("تحت التسجيل", _("Under registration")),
        ("شطب", _("Struck off")),
    ]
    reg_rows = [(label, reg_counts.pop(raw, 0)) for raw, label in reg_order]
    if sum(reg_counts.values()):
        reg_rows.append((_("Other"), sum(reg_counts.values())))

    donuts = [
        _donut(
            _("Tenders by Market"),
            [(_("Local"), local_tenders), (_("Foreign"), foreign_tenders)],
            colors=("#1d4ed8", "#f59e0b"),
        ),
        _donut(
            _("Vendor List Coverage"),
            [
                (_("With vendors"), covered),
                (_("Without vendors"), tender_total - covered),
            ],
            colors=("#16a34a", "#94a3b8"),
        ),
        _donut(
            _("Vendors by Scope"),
            [
                (_("Local"), local_vendors),
                (_("Foreign"), foreign_vendors),
                (_("Other"), vendor_total - local_vendors - foreign_vendors),
            ],
            colors=("#1d4ed8", "#f59e0b", "#94a3b8"),
        ),
        _donut(
            _("Vendor Registration Status"),
            reg_rows,
            colors=("#16a34a", "#94a3b8", "#f59e0b", "#ef4444", "#a855f7"),
        ),
    ]

    bars = [
        _bars(
            _("Tenders by Execution Method"),
            _count_by("execution_method", blank),
            limit=6, other=_("Other"),
        ),
        _bars(
            _("Tenders by File Department"),
            _count_by("file_dept", blank),
            limit=6, other=_("Other"),
        ),
        _bars(
            _("Tenders by Region"),
            _count_by("region", blank),
            limit=4, other=_("Other"),
        ),
        _bars(
            _("Estimated Value by Currency"),
            [
                (row["currency"] or blank, float(row["total"]))
                for row in value_by_currency
            ],
            limit=6, other=_("Other"),
            formatter=lambda amount: "{:,.0f}".format(amount),
        ),
        _bars(
            _("Top Vendors by Tenders"),
            [
                (row["vendor__name_ar"] or str(row["vendor__supplier_id"]), row["n"])
                for row in OperationVendor.objects
                .values("vendor__supplier_id", "vendor__name_ar")
                .annotate(n=Count("id")).order_by("-n")[:10]
            ],
            limit=10,
        ),
        _bars(
            _("Vendor Registrations by Activity"),
            [
                (row["sub_activity__main_activity__name_ar"] or blank, row["n"])
                for row in VendorActivity.objects
                .values("sub_activity__main_activity__name_ar")
                .annotate(n=Count("id")).order_by("-n")[:8]
            ],
            limit=8,
        ),
    ]

    status_counts = {
        row["status"]: row["n"]
        for row in RFQ.objects.values("status").annotate(n=Count("id"))
    }
    rfq_chart = _donut(
        _("RFQs by Status"),
        [
            (label, status_counts.get(value, 0))
            for value, label in (
                (RFQ.Status.DRAFT, _("Draft")),
                (RFQ.Status.SUBMITTED, _("Submitted")),
                (RFQ.Status.UNDER_REVIEW, _("Under Review")),
                (RFQ.Status.CHAIRMAN_APPROVED, _("Chairman Approved")),
                (RFQ.Status.REJECTED, _("Rejected")),
                (RFQ.Status.VENDOR_SELECTION, _("Vendor Selection")),
                (RFQ.Status.COMPLETED, _("Completed")),
            )
        ],
        colors=("#94a3b8", "#60a5fa", "#f59e0b", "#1d4ed8",
                "#ef4444", "#16a34a", "#a855f7"),
    )

    summary = [
        {"label": _("Tenders"), "count": tender_total, "href": reverse("rfq_list")},
        {"label": _("Vendors"), "count": vendor_total,
         "href": reverse("vendor_register")},
        {"label": _("Vendor List Entries"), "count": links,
         "href": reverse("rfq_list")},
        {"label": _("Vendor Activities"), "count": registrations,
         "href": reverse("vendor_register")},
        {"label": _("RFQs"), "count": rfq_total, "href": reverse("rfq_list")},
        {"label": _("Main Activities"), "count": main_activities},
        {"label": _("Sub Activities"), "count": sub_activities},
        {"label": _("Projects"), "count": Project.objects.count()},
        {"label": _("Clients"), "count": ClientCode.objects.count()},
        {"label": _("Cost Centers"), "count": CostCenter.objects.count()},
        {"label": _("Locations"), "count": Location.objects.count()},
        {"label": _("Departments"), "count": Department.objects.count()},
    ]
    for row in summary:
        row["count"] = "{:,}".format(row["count"])

    return {
        "cards": cards,
        "donuts": donuts,
        "bars": bars,
        "rfq": {
            "chart": rfq_chart,
            "total": "{:,}".format(rfq_total),
            "opened": "{:,}".format(rfq_total - rfq_orphans),
            "orphan": "{:,}".format(rfq_orphans),
        },
        "summary": summary,
    }


@login_required(login_url="login")
def dashboard(request):
    """Home screen: the sums of the whole purchasing data set."""
    return render(request, "core/dashboard.html", _dashboard_context())


@login_required(login_url="login")
def rfq_list(request):
    """The RFQ screen: every tender there is — local, foreign and the ones
    opened from an RFQ.  RFQs that have no tender yet are listed on top."""
    return _tender_list(
        request,
        default_title=_("All Tenders"),
        extra={
            "orphan_rfqs": RFQ.objects.select_related("requesting_department")
            .filter(tender__isnull=True)
            .order_by("-preparation_date"),
            "show_new_rfq": True,
        },
    )


@login_required(login_url="login")
def rfq_detail(request, pk):
    rfq = get_object_or_404(
        RFQ.objects.select_related("requesting_department", "vessel", "cost_center", "tender"),
        pk=pk,
    )
    items = rfq.items.all()
    context = {"rfq": rfq, "items": items}

    tender = rfq.tender
    context["tender"] = tender
    if tender:
        vendors = tender.operation_vendors.select_related("vendor").all()
        context["vendors"] = vendors
        context.update(_vendor_picker_context(request, tender, vendors))
    else:
        context["vendors"] = []
        context["candidates"] = []
        context["search"] = request.GET.get("vq", "").strip()
        context["scope"] = "market"
        context["market"] = (
            Operation.Market.FOREIGN if rfq.market_type == RFQ.MarketType.FOREIGN
            else Operation.Market.LOCAL
        )
    return render(request, "core/rfq_detail.html", context)


# How the RFQ purchase method reads on the tender (Access [طريقة التنفيذ]).
# Only the three that exist in the Access list are mapped; the rest stay blank.
EXECUTION_METHODS = {
    RFQ.PurchaseMethod.GENERAL_TENDER.value: "مناقصة عامة",
    RFQ.PurchaseMethod.DIRECT_ORDER.value: "أمر مباشر",
    RFQ.PurchaseMethod.LIMITED_TENDER.value: "مناقصة محدودة",
}


@login_required(login_url="login")
def rfq_tender_create(request, pk):
    """POST: open the tender that carries this RFQ's vendor list.

    The Access back end keeps one 'Oprations' row per tender with the vendor
    list underneath it, so a new RFQ gets one too — market and file
    department follow the RFQ's market field.
    """
    if request.method != "POST":
        return redirect("rfq_detail", pk=pk)
    rfq = get_object_or_404(RFQ, pk=pk)
    if rfq.tender_id:
        return redirect("rfq_detail", pk=pk)

    foreign = rfq.market_type == RFQ.MarketType.FOREIGN
    next_no = (Operation.objects.aggregate(m=Max("operation_no"))["m"] or 0) + 1
    tender = Operation.objects.create(
        operation_no=next_no,
        file_dept="المشتريات الخارجية" if foreign else "المشتريات المحلية",
        market=Operation.Market.FOREIGN if foreign else Operation.Market.LOCAL,
        year=(rfq.budget_year or "")[:4],
        overall_status="open",
        execution_method=EXECUTION_METHODS.get(rfq.purchase_method, ""),
        task_statement=(rfq.project.strip() or "RFQ %s" % rfq.request_number)[:255],
        requesting_entity=(rfq.requesting_department.name or "")[:50],
        project_name=rfq.project[:50],
        estimated_value=rfq.estimated_value,
        sap_no=rfq.sap_number[:255],
        cost_center=rfq.cost_center,
        currency="جنيه مصرى",
        budget=rfq.budget_code[:50],
        requisition_rec_date=rfq.requisition_rec_date,
        vendor_register_executor=(
            request.user.get_full_name() or request.user.username or ""
        )[:50],
    )
    rfq.tender = tender
    rfq.save(update_fields=["tender"])
    messages.success(
        request,
        _("Vendor list opened for this RFQ (tender %(no)s).") % {"no": next_no},
    )
    return redirect("rfq_detail", pk=pk)


@login_required(login_url="login")
def rfq_create(request):
    # /rfq/create/?market=local opens the form for that division.
    initial = {}
    market = request.GET.get("market", "")
    if market in (RFQ.MarketType.LOCAL, RFQ.MarketType.FOREIGN):
        initial["market_type"] = market
    if request.method == "POST":
        form = RFQForm(request.POST)
        formset = RFQItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            rfq = form.save(commit=False)
            rfq.created_by = request.user
            rfq.save()
            formset.instance = rfq
            formset.save()
            messages.success(
                request,
                _("RFQ %(num)s created successfully.") % {"num": rfq.request_number},
            )
            return redirect("rfq_detail", pk=rfq.pk)
    else:
        form = RFQForm(initial=initial)
        formset = RFQItemFormSet()
    return render(request, "core/rfq_form.html", {
        "form": form,
        "formset": formset,
        "title": _("Create RFQ"),
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
            messages.success(
                request,
                _("RFQ %(num)s updated successfully.") % {"num": rfq.request_number},
            )
            return redirect("rfq_detail", pk=rfq.pk)
    else:
        form = RFQForm(instance=rfq)
        formset = RFQItemFormSet(instance=rfq)
    return render(request, "core/rfq_form.html", {
        "form": form,
        "formset": formset,
        "rfq": rfq,
        "title": _("Edit RFQ %(num)s") % {"num": rfq.request_number},
        "action": "edit",
    })


@login_required(login_url="login")
def rfq_delete(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if request.method == "POST":
        num = rfq.request_number
        rfq.delete()
        messages.success(request, _("RFQ %(num)s deleted.") % {"num": num})
        return redirect("rfq_list")
    return render(request, "core/rfq_confirm_delete.html", {"rfq": rfq})


# ---------------------------------------------------------------------------
# Vendor list module
#
# The legacy Access front end (2026.accdb) exposes the vendor list through
# these screens, which are rebuilt here one to one:
#
#   Vendor List            -> vendor_list / operation_detail
#   Vendor Select Vendor   -> vendor sub table + add/remove on operation page
#   Vendor View            -> vendor_detail
#   New Vendor Enter       -> vendor_create / vendor_edit
#   Vendor VS Tasks        -> activity registration on vendor_detail
# ---------------------------------------------------------------------------


def _distinct(model, field):
    """Sorted, non-empty distinct values of a column (filter drop-downs)."""
    return sorted({v for v in model.objects.values_list(field, flat=True).distinct() if v})


def _vendor_search(vendors, search):
    if not search:
        return vendors
    if search.isdigit():
        return vendors.filter(
            Q(supplier_id=int(search))
            | Q(name_ar__icontains=search)
            | Q(name_en__icontains=search)
        )
    return vendors.filter(Q(name_ar__icontains=search) | Q(name_en__icontains=search))


# Vendors are sold either locally or abroad, so a tender's vendor list is
# built from the matching half of the register (Access: Booklet Type /
# Country).  "all" keeps both for the odd vendor with a blank booklet.
def _scoped_vendors(market, scope="market"):
    vendors = Vendor.objects.all()
    if scope == "all" or not market:
        return vendors
    if market == Operation.Market.LOCAL:
        return vendors.filter(
            Q(booklet_type=Vendor.BookletType.LOCAL)
            | (Q(booklet_type="") & Q(country__in=("مصر", "Egypt")))
        )
    return vendors.filter(
        Q(booklet_type=Vendor.BookletType.FOREIGN)
        | (Q(booklet_type="") & Q(country__gt="") & ~Q(country__in=("مصر", "Egypt")))
    )


def _redirect_target(request, default):
    """POST extra: where to go back to (operation page or RFQ page)."""
    target = request.POST.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return target
    return default


def _vendor_picker_context(request, operation, vendors):
    """Search box + candidate list shared by the tender page and the RFQ card."""
    search = request.GET.get("vq", "").strip()
    scope = request.GET.get("scope", "market")
    candidates = []
    if search:
        taken = [link.vendor_id for link in vendors]
        pool = _scoped_vendors(operation.market if operation else None, scope)
        candidates = _vendor_search(pool, search).exclude(pk__in=taken)[:25]
    return {
        "candidates": candidates,
        "search": search,
        "scope": scope,
        "market": operation.market if operation else "",
    }


@login_required(login_url="login")
def vendor_list(request):
    """Removed from the UI: the tender list lives on the RFQ screen now.
    The route stays as a redirect so old links keep working."""
    return redirect("rfq_list")


@login_required(login_url="login")
def local_tender(request):
    """Sidebar 'Local Tender' — the division that builds local vendor lists."""
    return _division_list(request, Operation.Market.LOCAL)


@login_required(login_url="login")
def foreign_tender(request):
    """Sidebar 'Foreign Tender' — the division for tenders from abroad."""
    return _division_list(request, Operation.Market.FOREIGN)


def _division_list(request, market):
    """One division: its RFQs and tenders, with the vendor list behind each."""
    return _tender_list(
        request,
        market=market,
        extra={
            "orphan_rfqs": RFQ.objects.select_related("requesting_department")
            .filter(tender__isnull=True, market_type=market)
            .order_by("-preparation_date"),
            "show_new_rfq": True,
        },
    )


def _tender_list(
    request,
    market=None,
    default_title=None,
    template="core/rfq_list.html",
    extra=None,
):
    # ?market=local|foreign narrows any list page — kept for deep links;
    # the sidebar is what switches between the divisions.
    get_market = request.GET.get("market", "")
    if get_market in (Operation.Market.LOCAL, Operation.Market.FOREIGN):
        market = get_market

    operations = Operation.objects.select_related(
        "project", "client", "cost_center", "location",
    ).prefetch_related("operation_vendors", "rfqs")
    if market:
        operations = operations.filter(market=market)

    search = request.GET.get("q", "").strip()
    year = request.GET.get("year", "")
    status = request.GET.get("status", "")
    region = request.GET.get("region", "")
    dept = request.GET.get("dept", "")

    if search:
        query = (
            Q(task_statement__icontains=search)
            | Q(requesting_entity__icontains=search)
            | Q(project_name__icontains=search)
            | Q(sap_no__icontains=search)
        )
        if search.isdigit():
            query |= Q(operation_no=int(search))
        operations = operations.filter(query)
    if year:
        operations = operations.filter(year=year)
    if status:
        operations = operations.filter(overall_status=status)
    if region:
        operations = operations.filter(region=region)
    if dept:
        operations = operations.filter(file_dept=dept)

    page_obj = Paginator(operations, 25).get_page(request.GET.get("page"))
    qs = request.GET.copy()
    qs.pop("page", None)

    scoped = (
        Operation.objects.filter(market=market) if market else Operation.objects.all()
    )

    context = {
        "page_obj": page_obj,
        "query_string": qs.urlencode(),
        "operations": page_obj.object_list,
        "search": search,
        "current_year": year,
        "current_status": status,
        "current_region": region,
        "current_dept": dept,
        "year_choices": _distinct(Operation, "year"),
        "status_choices": _distinct(Operation, "overall_status"),
        "region_choices": _distinct(Operation, "region"),
        "dept_choices": _distinct(Operation, "file_dept"),
        "market": market or "",
        "market_label": (
            _("Local Tender") if market == Operation.Market.LOCAL
            else _("Foreign Tender") if market == Operation.Market.FOREIGN
            else (default_title or _("Vendor List"))
        ),
        "total_operations": scoped.count(),
        "total_links": OperationVendor.objects.filter(
            operation__in=scoped,
        ).count(),
        "total_vendors": Vendor.objects.count(),
    }
    context.update(extra or {})
    return render(request, template, context)


@login_required(login_url="login")
def operation_detail(request, pk):
    """One operation: data + the vendor list sub form of the Access screen."""
    operation = get_object_or_404(
        Operation.objects.select_related("project", "client", "cost_center", "location"),
        pk=pk,
    )
    vendors = operation.operation_vendors.select_related("vendor").all()

    context = {
        "operation": operation,
        "vendors": vendors,
        "rfq": operation.rfqs.first(),
    }
    context.update(_vendor_picker_context(request, operation, vendors))
    return render(request, "core/operation_detail.html", context)


@login_required(login_url="login")
def operation_vendor_add(request, pk):
    """POST: put a vendor on the vendor list of an operation."""
    if request.method != "POST":
        return redirect("operation_detail", pk=pk)
    operation = get_object_or_404(Operation, pk=pk)
    target = _redirect_target(request, None)
    try:
        vendor = Vendor.objects.get(supplier_id=int(request.POST.get("supplier_id", "")))
    except (ValueError, Vendor.DoesNotExist):
        messages.error(request, _("Vendor not found."))
        return redirect(target) if target else redirect("operation_detail", pk=pk)

    if OperationVendor.objects.filter(operation=operation, vendor=vendor).exists():
        messages.warning(request, _("This vendor is already on the vendor list."))
    else:
        OperationVendor.objects.create(
            operation=operation,
            operation_no=operation.operation_no,
            vendor=vendor,
        )
        messages.success(request, _("Vendor added to the vendor list."))
    return redirect(target) if target else redirect("operation_detail", pk=pk)


@login_required(login_url="login")
def operation_vendor_remove(request, pk, vendor_pk):
    """POST: drop a vendor from the vendor list of an operation."""
    if request.method != "POST":
        return redirect("operation_detail", pk=pk)
    operation = get_object_or_404(Operation, pk=pk)
    target = _redirect_target(request, None)
    removed, _deleted = OperationVendor.objects.filter(
        operation=operation, vendor_id=vendor_pk,
    ).delete()
    if removed:
        messages.success(request, _("Vendor removed from the vendor list."))
    return redirect(target) if target else redirect("operation_detail", pk=pk)


@login_required(login_url="login")
def vendor_register(request):
    """The [Vendors] register with search, filters and paging."""
    vendors = Vendor.objects.all()

    search = request.GET.get("q", "").strip()
    country = request.GET.get("country", "")
    booklet = request.GET.get("booklet", "")
    status = request.GET.get("status", "")
    category = request.GET.get("category", "")

    vendors = _vendor_search(vendors, search)
    if country:
        vendors = vendors.filter(country=country)
    if booklet:
        vendors = vendors.filter(booklet_type=booklet)
    if status:
        vendors = vendors.filter(registration_status_new=status)
    if category:
        vendors = vendors.filter(category=category)

    page_obj = Paginator(vendors, 25).get_page(request.GET.get("page"))
    qs = request.GET.copy()
    qs.pop("page", None)

    return render(request, "core/vendor_register.html", {
        "page_obj": page_obj,
        "query_string": qs.urlencode(),
        "vendors": page_obj.object_list,
        "search": search,
        "current_country": country,
        "current_booklet": booklet,
        "current_status": status,
        "current_category": category,
        "country_choices": _distinct(Vendor, "country"),
        "status_choices": _distinct(Vendor, "registration_status_new"),
        "category_choices": _distinct(Vendor, "category"),
        "booklet_choices": Vendor.BookletType.choices,
        "total_vendors": Vendor.objects.count(),
    })


@login_required(login_url="login")
def vendor_detail(request, pk):
    """Access form 'Vendor View' - vendor file, activities and operations."""
    vendor = get_object_or_404(Vendor, pk=pk)
    activities = vendor.activities.select_related(
        "sub_activity", "sub_activity__main_activity",
    ).all()
    operations = vendor.operation_links.select_related("operation").order_by(
        "-operation_no",
    ).all()

    return render(request, "core/vendor_detail.html", {
        "vendor": vendor,
        "activities": activities,
        "operations": operations,
        "activity_form": VendorActivityForm(),
        "activity_count": activities.count(),
        "operation_count": operations.count(),
    })


@login_required(login_url="login")
def vendor_create(request):
    """Access form 'New Vendor Enter'."""
    if request.method == "POST":
        form = VendorForm(request.POST)
        if form.is_valid():
            vendor = form.save()
            messages.success(
                request,
                _("Vendor %(num)s created.") % {"num": vendor.supplier_id},
            )
            return redirect("vendor_detail", pk=vendor.pk)
    else:
        form = VendorForm()
    return render(request, "core/vendor_form.html", {
        "form": form,
        "action": "create",
        "title": _("New Vendor"),
    })


@login_required(login_url="login")
def vendor_edit(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk)
    if request.method == "POST":
        form = VendorForm(request.POST, instance=vendor)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                _("Vendor %(num)s updated.") % {"num": vendor.supplier_id},
            )
            return redirect("vendor_detail", pk=vendor.pk)
    else:
        form = VendorForm(instance=vendor)
    return render(request, "core/vendor_form.html", {
        "form": form,
        "vendor": vendor,
        "action": "edit",
        "title": _("Edit Vendor %(num)s") % {"num": vendor.supplier_id},
    })


@login_required(login_url="login")
def vendor_activity_add(request, pk):
    """POST: register the vendor on a sub activity ([Vendor VS Tasks])."""
    vendor = get_object_or_404(Vendor, pk=pk)
    if request.method != "POST":
        return redirect("vendor_detail", pk=pk)

    form = VendorActivityForm(request.POST)
    if form.is_valid():
        activity = form.save(commit=False)
        activity.vendor = vendor
        if VendorActivity.objects.filter(
            vendor=vendor, sub_activity=activity.sub_activity,
        ).exists():
            messages.warning(request, _("This vendor is already registered on that activity."))
        else:
            activity.save()
            messages.success(request, _("Vendor registered on the activity."))
    else:
        messages.error(request, _("Please select a valid activity."))
    return redirect("vendor_detail", pk=pk)


@login_required(login_url="login")
def vendor_activity_remove(request, pk, activity_pk):
    """POST: drop one activity registration of a vendor."""
    vendor = get_object_or_404(Vendor, pk=pk)
    if request.method != "POST":
        return redirect("vendor_detail", pk=pk)
    removed, _deleted = VendorActivity.objects.filter(
        pk=activity_pk, vendor=vendor,
    ).delete()
    if removed:
        messages.success(request, _("Registration removed."))
    return redirect("vendor_detail", pk=pk)
