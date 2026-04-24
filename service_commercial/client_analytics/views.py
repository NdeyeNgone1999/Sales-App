from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from importlib import import_module
from .models import Dataset
from .forms import UploadDatasetForm, SelectDatasetForm
import threading
import os
import uuid
import tempfile
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings

import logging

logger = logging.getLogger(__name__)


class LazyModule:
    def __init__(self, module_path):
        self.module_path = module_path
        self._module = None

    def _load(self):
        if self._module is None:
            self._module = import_module(self.module_path)
        return self._module

    def __getattr__(self, name):
        return getattr(self._load(), name)


dataset_io = LazyModule("service_commercial.client_analytics.services.dataset_io")
data_processing = LazyModule("service_commercial.client_analytics.services.data_processing")
analysis_currency_dependency = LazyModule(
    "service_commercial.client_analytics.services.analysis_currency_dependency"
)
analysis_overview = LazyModule("service_commercial.client_analytics.services.analysis_overview")
analysis_by_period = LazyModule("service_commercial.client_analytics.services.analysis_by_period")
analysis_time_series = LazyModule("service_commercial.client_analytics.services.analysis_time_series")
analysis_clustering = LazyModule("service_commercial.client_analytics.services.analysis_clustering")
analysis_products = LazyModule("service_commercial.client_analytics.services.analysis_products")
analysis_geographic = LazyModule("service_commercial.client_analytics.services.analysis_geographic")
analysis_clients = LazyModule("service_commercial.client_analytics.services.analysis_clients")
analysis_behavioral_monitoring = LazyModule(
    "service_commercial.client_analytics.services.analysis_behavioral_monitoring"
)
analysis_projection = LazyModule("service_commercial.client_analytics.services.analysis_projection")
aggregations = LazyModule("service_commercial.client_analytics.services.aggregations")
insights = LazyModule("service_commercial.client_analytics.services.insights")
period_svc = LazyModule("service_commercial.client_analytics.services.periods")
pd = LazyModule("pandas")


def home(request):
    """Home page with upload and selection forms"""
    upload_form = UploadDatasetForm()
    select_form = SelectDatasetForm()

    if request.method == "POST":
        logger.info("[home] POST received. POST keys: %s, FILES keys: %s",
                     list(request.POST.keys()), list(request.FILES.keys()))
        if "upload" in request.POST:
            upload_form = UploadDatasetForm(request.POST, request.FILES)
            logger.info("[home] Form created. is_valid=%s, errors=%s",
                         upload_form.is_valid(), upload_form.errors)
            if upload_form.is_valid():
                dataset = upload_form.save()
                logger.info("[home] Dataset saved pk=%s, redirecting to processing", dataset.pk)
                messages.success(
                    request, f'Dataset "{dataset.name}" uploadé avec succès!'
                )
                return redirect("client_analytics:dataset_processing", pk=dataset.pk)
            else:
                logger.warning("[home] Form INVALID: %s", upload_form.errors.as_json())

        elif "select" in request.POST:
            select_form = SelectDatasetForm(request.POST)
            if select_form.is_valid():
                dataset = select_form.cleaned_data["existing_dataset"]
                return redirect("client_analytics:dataset_overview", pk=dataset.pk)
        else:
            logger.warning("[home] POST but neither 'upload' nor 'select' in POST keys")

    context = {
        "upload_form": upload_form,
        "select_form": select_form,
    }
    return render(request, "client_analytics/home.html", context)


def workflow(request):
    """Workflow explanation page"""
    return render(request, "client_analytics/workflow.html")


def dataset_overview(request, pk):
    """Dataset overview page"""
    dataset = get_object_or_404(Dataset, pk=pk)

    # Redirect to processing page if not yet processed
    if dataset.processing_status != 'done':
        return redirect("client_analytics:dataset_processing", pk=pk)

    # Load dataframe (already processed during upload in forms.py)
    df = dataset_io.load_dataset_df(dataset)

    if df is None:
        messages.error(request, "Erreur lors du chargement du dataset")
        return redirect("client_analytics:home")

    # Get dataset info using analysis_overview
    overview_analysis = analysis_overview.generate_overview_analysis(df)
    info = overview_analysis.get("info", {})
    missing_info = overview_analysis.get("missing_info", [])
    numeric_summary = overview_analysis.get("numeric_summary")
    column_types = overview_analysis.get("column_types", {})

    # Convert dataframe head to HTML
    df_head_html = df.head(10).to_html(
        classes="table table-striped table-sm", index=False
    )

    # Convert numeric summary to HTML
    numeric_summary_html = None
    if numeric_summary is not None:
        numeric_summary_html = numeric_summary.to_html(
            classes="table table-striped table-sm"
        )

    context = {
        "dataset": dataset,
        "info": info,
        "missing_info": missing_info,
        "df_head_html": df_head_html,
        "numeric_summary_html": numeric_summary_html,
        "column_types": column_types,
    }
    return render(request, "client_analytics/dataset_overview.html", context)


# ─── helpers (used by stats() and ajax_tab()) ────────────────────────────────


def _normalize_granularity(param: str) -> str:
    if param in ("fiscal_year", "fiscal"):
        return "year"
    return param if param in ("month", "quarter", "year") else "month"


def _build_global_kpis(df: "pd.DataFrame") -> dict:
    nb_clients = df["Cpt Client"].nunique() if "Cpt Client" in df.columns else 0
    return {
        "total_transactions": int(len(df)),
        "ca_total": f"{df['Montant'].sum():,.2f} \u20ac",
        "nb_clients": int(nb_clients),
        "nb_familles": int(df["Famille"].nunique()) if "Famille" in df.columns else 0,
        "panier_moyen": f"{df['Montant'].mean():,.2f} \u20ac",
        "nb_pays": int(df["Pays"].nunique()) if "Pays" in df.columns else 0,
        "ca_moyen_client": (
            float(df["Montant"].sum() / nb_clients) if nb_clients else None
        ),
    }


def _safe_run(fn, *args, fallback=None, label="", **kwargs):
    """Call fn(*args, **kwargs), log exceptions and return fallback on error."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.exception("[%s] ERROR", label)
        return fallback if fallback is not None else {}


def _build_temporal_context(df: "pd.DataFrame", granularity: str = "month") -> dict:
    df_daily = _safe_run(
        analysis_time_series.aggregate_daily, df, label="temporal:daily"
    )
    result = _safe_run(
        analysis_time_series.generate_temporal_analysis,
        df,
        granularity=granularity,
        df_daily_cache=df_daily,
        anomaly_report_cache=None,
        label=f"temporal:{granularity}",
        fallback={"results": {}, "graphs": {}},
    )
    return {
        "results": result.get("results", {}),
        "graphs": result.get("graphs", {}),
        "granularity": granularity,
    }


def _build_products_context(
    df: "pd.DataFrame",
    granularity: str = "month",
    selected_product: str = "",
    selected_family: str = "",
) -> dict:
    result = _safe_run(
        analysis_products.analyze_product_families,
        df,
        time_granularity=granularity,
        selected_product=selected_product,
        selected_family=selected_family,
        compare_products=None,
        compare_families=None,
        compare_products_metric="Qty_Total",
        compare_families_metric="Qty_Total",
        max_compare_items=5,
        label=f"products:{granularity}",
        fallback={},
    )
    return {
        "family_analysis": result,
        "granularity": granularity,
    }


def _build_clients_context(
    df: "pd.DataFrame", granularity: str = "month", selected_client: str = ""
) -> dict:
    client_analysis = _safe_run(
        analysis_clients.analyze_clients,
        df,
        time_granularity=granularity,
        label="clients:analyze",
        fallback={},
    )
    client_options = _safe_run(
        analysis_clients.get_client_options,
        df,
        max_clients=500,
        label="clients:options",
        fallback=[],
    )

    portfolio = portfolio_m = portfolio_q = portfolio_f = None
    if selected_client:

        def _port(g):
            return _safe_run(
                analysis_clients.analyze_client_portfolio_full,
                df,
                selected_client,
                time_granularity=g,
                top_n_families=8,
                top_n_products=10,
                label=f"clients:portfolio:{g}",
                fallback={"client_id": selected_client, "kpis": {}, "graphs": {}},
            )

        portfolio_m = _port("month")
        portfolio_q = _port("quarter")
        portfolio_f = _port("year")
        portfolio = portfolio_m

    return {
        "client_analysis": client_analysis,
        "client_stats": client_analysis.get("client_stats"),
        "top10_clients": client_analysis.get("top10_clients"),
        "top20_clients": client_analysis.get("top20_clients"),
        "concentration_top20_pct": client_analysis.get("concentration_top20_pct"),
        "concentration_top10_pct": client_analysis.get("concentration_top10_pct"),
        "client_graphs": client_analysis.get("client_graphs", {}),
        "client_options": client_options,
        "selected_client": selected_client,
        "client_portfolio": portfolio,
        "client_portfolio_month": portfolio_m,
        "client_portfolio_quarter": portfolio_q,
        "client_portfolio_fiscal": portfolio_f,
    }


def _geo_analysis_to_dict(result: dict) -> dict:
    """Converts raw analyze_geographic_data result to template-ready dicts."""

    def _recs(df):
        try:
            return df.to_dict("records") if not df.empty else []
        except Exception:
            return []

    return {
        "stats_zone": _recs(result.get("stats_zone", pd.DataFrame())),
        "stats_pays": _recs(result.get("stats_pays", pd.DataFrame())),
        "classif_summary": _recs(result.get("classif_summary", pd.DataFrame())),
        "top10_score": _recs(result.get("top10_score", pd.DataFrame())),
        "geo_graphs": result.get("geo_graphs", {}),
    }


def _build_geographic_context(df: "pd.DataFrame", granularity: str = "month") -> dict:
    raw = _safe_run(
        analysis_geographic.analyze_geographic_data,
        df,
        granularity=granularity,
        label=f"geographic:{granularity}",
        fallback={
            "stats_zone": pd.DataFrame(),
            "stats_pays": pd.DataFrame(),
            "classif_summary": pd.DataFrame(),
            "top10_score": pd.DataFrame(),
            "geo_graphs": {},
        },
    )
    d = _geo_analysis_to_dict(raw)
    return {
        "stats_zone": d["stats_zone"],
        "stats_pays": d["stats_pays"],
        "classif_summary": d["classif_summary"],
        "top10_score": d["top10_score"],
        "geo_graphs": d["geo_graphs"],
        "granularity": granularity,
    }


def _build_currency_context(df: "pd.DataFrame", granularity: str = "month") -> dict:
    report = _safe_run(
        analysis_currency_dependency.analyze_currency_dependency,
        df,
        output_dir=None,
        granularity=granularity,
        label=f"currency:{granularity}",
        fallback={},
    )
    return {
        "currency_kpi": report.get("kpi", {}),
        "currency_charts": report.get("charts", {}),
        "granularity": granularity,
    }


# ─── main stats view (initial load: statistics tab only) ─────────────────────


def stats(request, pk):
    """
    Statistics dashboard.

    On initial page load only the statistics analysis is computed (the default
    tab). All other tabs are loaded lazily via the ajax_tab endpoint when the
    user first navigates to them, avoiding unnecessary computation.
    """
    dataset = get_object_or_404(Dataset, pk=pk)

    granularity = _normalize_granularity(request.GET.get("granularity", "month"))
    active_tab = request.GET.get("tab", "statistics")
    selected_client = request.GET.get("client", "")

    df_processed = dataset_io.load_dataset_df(dataset)
    if df_processed is None:
        messages.error(request, "Erreur lors du chargement du dataset")
        return redirect("client_analytics:home")

    # Global KPIs (always needed for the top cards)
    global_kpis = _build_global_kpis(df_processed)

    # Statistics analysis – the only one computed on initial load
    def _stat(g):
        return _safe_run(
            analysis_by_period.generate_period_analysis,
            df_processed,
            granularity=g,
            skip_preprocessing=True,
            label=f"statistics:{g}",
            fallback={"results": {}, "graphs": {}, "kpis": {}},
        )

    stat_m = _stat("month")
    stat_q = _stat("quarter")
    stat_y = _stat("year")

    all_kpis = {**global_kpis, **stat_m.get("kpis", {})}

    available_periods = _safe_run(
        data_processing.get_available_periods,
        df_processed,
        label="available_periods",
        fallback={},
    )
    temporal_metrics = _safe_run(
        analysis_time_series.get_temporal_metrics,
        df_processed,
        granularity=granularity,
        label="temporal_metrics",
        fallback={},
    )

    # Lead-time (optional, rendered outside the main tab panes)
    import json

    period_param = period_svc.normalize_period(request.GET.get("period", "month"))
    lead_time_analysis = _safe_run(
        aggregations.lead_time_pack,
        df_processed,
        period=period_param,
        label="lead_time",
        fallback={"error": "N/A"},
    )
    lead_time_interpretation = insights.explain_lead_time(lead_time_analysis)
    lead_time_dist_json = json.dumps(lead_time_analysis.get("distribution", []))
    lead_time_series_json = json.dumps(lead_time_analysis.get("series_over_time", []))

    _empty_geo = {
        "stats_zone": [],
        "stats_pays": [],
        "classif_summary": [],
        "top10_score": [],
        "geo_graphs": {},
    }

    context = {
        "dataset": dataset,
        "granularity": granularity,
        "active_tab": active_tab,
        "kpis": all_kpis,
        "temporal_metrics": temporal_metrics,
        "available_periods": available_periods,
        # Statistics per granularity (stats tab content)
        "results_month": stat_m.get("results", {}),
        "graphs_month": stat_m.get("graphs", {}),
        "kpis_month": stat_m.get("kpis", {}),
        "results_quarter": stat_q.get("results", {}),
        "graphs_quarter": stat_q.get("graphs", {}),
        "kpis_quarter": stat_q.get("kpis", {}),
        "results_fiscal": stat_y.get("results", {}),
        "graphs_fiscal": stat_y.get("graphs", {}),
        "kpis_fiscal": stat_y.get("kpis", {}),
        "results": stat_m.get("results", {}),
        "graphs": stat_m.get("graphs", {}),
        # Date info
        "date_min": (
            df_processed["Date Fact."].min()
            if "Date Fact." in df_processed.columns
            else None
        ),
        "date_max": (
            df_processed["Date Fact."].max()
            if "Date Fact." in df_processed.columns
            else None
        ),
        "n_lignes": len(df_processed),
        "n_colonnes": len(df_processed.columns),
        # Lead-time
        "period": period_param,
        "lead_time_analysis": lead_time_analysis,
        "lead_time_interpretation": lead_time_interpretation,
        "lead_time_dist_json": lead_time_dist_json,
        "lead_time_series_json": lead_time_series_json,
        # Empty defaults for AJAX-loaded tabs
        "client_analysis": {},
        "client_options": [],
        "selected_client": selected_client,
        "client_graphs": {},
        "top10_clients": None,
        "top20_clients": None,
        "concentration_top20_pct": None,
        "concentration_top10_pct": None,
        "client_portfolio": None,
        "client_portfolio_month": None,
        "client_portfolio_quarter": None,
        "client_portfolio_fiscal": None,
        "family_analysis": {},
        "family_analysis_month": {},
        "family_analysis_quarter": {},
        "family_analysis_year": {},
        "family_analysis_fiscal": {},
        "stats_famille": None,
        "family_graphs": {},
        "geo_analysis": _empty_geo,
        "geo_analysis_month": _empty_geo,
        "geo_analysis_quarter": _empty_geo,
        "geo_analysis_fiscal": _empty_geo,
        "stats_pays": [],
        "stats_zone": [],
        "geo_graphs": {},
        "currency_kpi": {},
        "currency_charts": {},
        "currency_kpi_month": {},
        "currency_charts_month": {},
        "currency_kpi_quarter": {},
        "currency_charts_quarter": {},
        "currency_kpi_fiscal": {},
        "currency_charts_fiscal": {},
    }
    return render(request, "client_analytics/stats.html", context)


# ─── AJAX: lazy-load a specific analysis tab ─────────────────────────────────


@require_http_methods(["GET"])
def ajax_tab(request, pk):
    """
    Returns the rendered HTML fragment for a specific analysis tab.
    Called by JavaScript when the user first clicks a non-default tab.

    Query params:
      tab         – one of: temporal | products | clients | geographic | currency
      granularity – month | quarter | year  (default: month)
      client      – (optional) client ID for the clients tab
      product     – (optional) product filter for the products tab
      family      – (optional) family filter for the products tab
    """
    from django.template.loader import render_to_string

    dataset = get_object_or_404(Dataset, pk=pk)
    tab = request.GET.get("tab", "")
    granularity = _normalize_granularity(request.GET.get("granularity", "month"))

    if tab not in ("temporal", "products", "clients", "geographic", "currency"):
        return JsonResponse({"error": f"Unknown tab: {tab!r}"}, status=400)

    df = dataset_io.load_dataset_df(dataset)
    if df is None:
        return JsonResponse({"error": "Dataset load failed"}, status=500)

    try:
        if tab == "temporal":
            ctx = _build_temporal_context(df, granularity=granularity)
            template = "client_analytics/partials/tab_temporal.html"

        elif tab == "products":
            ctx = _build_products_context(
                df,
                granularity=granularity,
                selected_product=request.GET.get("product", ""),
                selected_family=request.GET.get("family", ""),
            )
            template = "client_analytics/partials/tab_products.html"

        elif tab == "clients":
            ctx = _build_clients_context(
                df,
                granularity=granularity,
                selected_client=request.GET.get("client", ""),
            )
            template = "client_analytics/partials/tab_clients.html"

        elif tab == "geographic":
            ctx = _build_geographic_context(df, granularity=granularity)
            template = "client_analytics/partials/tab_geographic.html"

        elif tab == "currency":
            ctx = _build_currency_context(df, granularity=granularity)
            template = "client_analytics/partials/tab_currency.html"

        html = render_to_string(template, ctx, request=request)
        return JsonResponse({"success": True, "html": html})

    except Exception as e:
        logger.exception("[ajax_tab:%s] ERROR", tab)
        return JsonResponse({"error": str(e)}, status=500)


def anomalies(request, pk):
    """Page Monitoring Comportemental Client — granularité mensuelle fixe."""
    dataset = get_object_or_404(Dataset, pk=pk)

    df_processed = dataset_io.load_dataset_df(dataset)
    if df_processed is None:
        messages.error(request, "Erreur lors du chargement du dataset")
        return redirect("client_analytics:home")

    # Portfolio overview (tous les clients, mensuel)
    portfolio = {}
    try:
        portfolio = analysis_behavioral_monitoring.analyze_portfolio(df_processed)
    except Exception:
        logger.exception("[anomalies] ERROR analyze_portfolio")
        portfolio = {
            "error": "Erreur lors du calcul du portfolio",
            "portfolio": [],
            "counts": {},
        }

    # Pré-sélection d'un client via GET ?client=...
    selected_client = (request.GET.get("client") or "").strip()

    context = {
        "dataset": dataset,
        "portfolio": portfolio,
        "selected_client": selected_client,
    }
    return render(request, "client_analytics/anomalies.html", context)


def ajax_behavioral_client(request, pk):
    """AJAX — profil comportemental détaillé d'un client (mensuel)."""
    dataset = get_object_or_404(Dataset, pk=pk)
    client_id = (request.GET.get("client") or "").strip()
    if not client_id:
        return JsonResponse({"success": False, "error": "client manquant"}, status=400)

    df_processed = dataset_io.load_dataset_df(dataset)
    if df_processed is None:
        return JsonResponse(
            {"success": False, "error": "Dataset introuvable"}, status=404
        )

    try:
        result = analysis_behavioral_monitoring.analyze_client(df_processed, client_id)
    except Exception as e:
        logger.exception("[behavioral] ERROR analyze_client (client=%s)", client_id)
        return JsonResponse({"success": False, "error": str(e)}, status=500)

    if result.get("error"):
        return JsonResponse({"success": False, "error": result["error"]}, status=422)

    return JsonResponse({"success": True, "data": result})


def clustering(request, pk):
    """Clustering page - Automatic K-Means clustering"""
    dataset = get_object_or_404(Dataset, pk=pk)

    # Load dataframe (already processed during upload in forms.py)
    df = dataset_io.load_dataset_df(dataset)

    if df is None:
        messages.error(request, "Erreur lors du chargement du dataset")
        return redirect("client_analytics:home")

    available_quarterly_years = (
        analysis_clustering.get_quarterly_clustering_available_years(df)
    )

    mode = request.GET.get("mode", "global")
    selected_year = request.GET.get("year")
    if mode in {"quarterly_2024", "quarterly_notebook"}:
        mode = "quarterly_notebook"
        if request.GET.get("mode") == "quarterly_2024" and selected_year is None:
            selected_year = "2024"
        elif selected_year is None and available_quarterly_years:
            selected_year = str(available_quarterly_years[-1])
        clustering_result = analysis_clustering.generate_quarterly_clustering_analysis(
            df,
            year=selected_year,
        )
    else:
        mode = "global"
        selected_year = None
        clustering_result = analysis_clustering.generate_clustering_analysis(df)

    resolved_selected_year = clustering_result.get("kpis", {}).get("annee_analysee")
    if resolved_selected_year is None and selected_year and str(selected_year).isdigit():
        resolved_selected_year = int(selected_year)

    context = {
        "dataset": dataset,
        "kpis": clustering_result.get("kpis", {}),
        "results": clustering_result.get("results", {}),
        "graphs": clustering_result.get("graphs", {}),
        "error": clustering_result.get("error"),
        "mode": mode,
        "selected_year": resolved_selected_year,
        "available_quarterly_years": available_quarterly_years,
    }
    return render(request, "client_analytics/clustering.html", context)


def clustering_export(request, pk):
    """Export clustering results to CSV"""
    dataset = get_object_or_404(Dataset, pk=pk)

    # Get clustering results from session
    clustering_results = request.session.get("clustering_results")

    if not clustering_results or clustering_results["dataset_pk"] != pk:
        messages.error(
            request,
            "Aucun résultat de clustering trouvé. Veuillez effectuer un clustering d'abord.",
        )
        return redirect("client_analytics:clustering", pk=pk)

    # Load dataframe
    df = dataset_io.load_dataset_df(dataset)

    if df is None:
        messages.error(request, "Erreur lors du chargement du dataset")
        return redirect("client_analytics:home")

    # Add cluster labels to dataframe (simplifié)
    df_export = df.copy()
    # L'export sera géré différemment maintenant
    messages.info(request, "Fonctionnalité d'export en cours de mise à jour")
    return redirect("client_analytics:clustering", pk=pk)


# ═══════════════════════════════════════════════════════════════════
# VUES AJAX POUR ANALYSES CIBLÉES (éviter rechargement complet)
# ═══════════════════════════════════════════════════════════════════


@require_http_methods(["GET"])
def ajax_client_portfolio(request, pk):
    """AJAX: Charger le portefeuille d'un client spécifique"""
    dataset = get_object_or_404(Dataset, pk=pk)

    client_id = request.GET.get("client", "")
    granularity = request.GET.get("granularity", "month")

    if not client_id:
        return JsonResponse({"error": "Client ID manquant"}, status=400)

    df_processed = dataset_io.load_dataset_df(dataset)
    if df_processed is None:
        return JsonResponse({"error": "Erreur chargement dataset"}, status=500)

    try:
        portfolio = analysis_clients.analyze_client_portfolio_full(
            df_processed,
            client_id,
            time_granularity=granularity,
            top_n_families=8,
            top_n_products=10,
        )

        # Rendre le partial HTML et le retourner
        from django.template.loader import render_to_string

        html = render_to_string(
            "client_analytics/partials/_client360_block.html",
            {"client_portfolio": portfolio},
        )

        return JsonResponse({"success": True, "html": html})

    except Exception as e:
        logger.exception("[ajax_client_portfolio] ERROR")
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def ajax_product_correlation(request, pk):
    """AJAX: Calculer corrélation ciblée pour produit ou famille"""
    dataset = get_object_or_404(Dataset, pk=pk)

    product = request.GET.get("product", "")
    family = request.GET.get("family", "")
    granularity = request.GET.get("granularity", "month")

    if not product and not family:
        return JsonResponse({"error": "Produit ou famille manquant"}, status=400)

    df_processed = dataset_io.load_dataset_df(dataset)
    if df_processed is None:
        return JsonResponse({"error": "Erreur chargement dataset"}, status=500)

    try:
        # Recalculer uniquement l'analyse produits avec les paramètres ciblés
        family_analysis = analysis_products.analyze_product_families(
            df_processed,
            time_granularity=granularity,
            selected_product=product,
            selected_family=family,
            compare_products=None,
            compare_families=None,
            compare_products_metric="Qty_Total",
            compare_families_metric="Qty_Total",
            max_compare_items=5,
        )

        # Extraire le graphique approprié
        family_graphs = family_analysis.get("family_graphs", {})

        if product:
            graph_html = family_graphs.get("product_corr_heatmap", "")
            if not graph_html:
                return JsonResponse(
                    {
                        "success": True,
                        "html": '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Pas assez de données pour calculer une corrélation fiable pour ce produit.</div>',
                    }
                )
        elif family:
            graph_html = family_graphs.get("family_corr_heatmap", "")
            if not graph_html:
                return JsonResponse(
                    {
                        "success": True,
                        "html": '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Pas assez de données pour calculer une corrélation fiable pour cette famille.</div>',
                    }
                )

        return JsonResponse({"success": True, "html": graph_html})

    except Exception as e:
        logger.exception("[ajax_product_correlation] ERROR")
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def ajax_compare_products(request, pk):
    """AJAX: Comparer plusieurs produits"""
    dataset = get_object_or_404(Dataset, pk=pk)

    compare_products = request.GET.getlist("compare_products")
    metric = request.GET.get("compare_products_metric", "Qty_Total")
    granularity = request.GET.get("granularity", "month")

    if not compare_products:
        return JsonResponse({"error": "Aucun produit sélectionné"}, status=400)

    df_processed = dataset_io.load_dataset_df(dataset)
    if df_processed is None:
        return JsonResponse({"error": "Erreur chargement dataset"}, status=500)

    try:
        # Recalculer uniquement avec les produits à comparer
        family_analysis = analysis_products.analyze_product_families(
            df_processed,
            time_granularity=granularity,
            selected_product=None,
            selected_family=None,
            compare_products=compare_products,
            compare_families=None,
            compare_products_metric=metric,
            compare_families_metric="Qty_Total",
            max_compare_items=5,
        )

        graph_html = family_analysis.get("family_graphs", {}).get(
            "compare_products_timeseries", ""
        )

        if not graph_html:
            return JsonResponse(
                {
                    "success": True,
                    "html": '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Pas de données disponibles pour cette comparaison.</div>',
                }
            )

        return JsonResponse({"success": True, "html": graph_html})

    except Exception as e:
        logger.exception("[ajax_compare_products] ERROR")
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def ajax_compare_families(request, pk):
    """AJAX: Comparer plusieurs familles"""
    dataset = get_object_or_404(Dataset, pk=pk)

    compare_families = request.GET.getlist("compare_families")
    metric = request.GET.get("compare_families_metric", "Qty_Total")
    granularity = request.GET.get("granularity", "month")

    if not compare_families:
        return JsonResponse({"error": "Aucune famille sélectionnée"}, status=400)

    df_processed = dataset_io.load_dataset_df(dataset)
    if df_processed is None:
        return JsonResponse({"error": "Erreur chargement dataset"}, status=500)

    try:
        # Recalculer uniquement avec les familles à comparer
        family_analysis = analysis_products.analyze_product_families(
            df_processed,
            time_granularity=granularity,
            selected_product=None,
            selected_family=None,
            compare_products=None,
            compare_families=compare_families,
            compare_products_metric="Qty_Total",
            compare_families_metric=metric,
            max_compare_items=5,
        )

        graph_html = family_analysis.get("family_graphs", {}).get(
            "compare_families_timeseries", ""
        )

        if not graph_html:
            return JsonResponse(
                {
                    "success": True,
                    "html": '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Pas de données disponibles pour cette comparaison.</div>',
                }
            )

        return JsonResponse({"success": True, "html": graph_html})

    except Exception as e:
        logger.exception("[ajax_compare_families] ERROR")
        return JsonResponse({"error": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════
# PROJECTION DE PORTEFEUILLE CLIENT
# ═══════════════════════════════════════════════════════════════════


def projection(request, pk):
    """Page Projection de Portefeuille — STL + HistGBM Quantile Ensemble."""
    dataset = get_object_or_404(Dataset, pk=pk)

    df_processed = dataset_io.load_dataset_df(dataset)
    if df_processed is None:
        messages.error(request, "Erreur lors du chargement du dataset")
        return redirect("client_analytics:home")

    import json

    proj_result = {}
    try:
        proj_result = analysis_projection.analyze_portfolio_projection(df_processed)
    except Exception:
        logger.exception("[projection] ERROR analyze_portfolio_projection")
        proj_result = {
            "error": "Erreur lors du calcul des projections",
            "portfolio": {},
            "clients": [],
        }

    portfolio = proj_result.get("portfolio", {})
    clients = proj_result.get("clients", [])
    model_info = proj_result.get("model_info", {})
    error = proj_result.get("error")

    # Sérialiser pour JS
    timeline_history_json = json.dumps(portfolio.get("timeline_history", []))
    timeline_forecast_json = json.dumps(portfolio.get("timeline_forecast", []))
    clients_json = json.dumps(clients)
    by_horizon_json = json.dumps(portfolio.get("by_horizon", {}))
    current_ca_js = json.dumps(portfolio.get("current_ca", 0))

    context = {
        "dataset": dataset,
        "portfolio": portfolio,
        "clients": clients,
        "model_info": model_info,
        "projection_error": error,
        "timeline_history_json": timeline_history_json,
        "timeline_forecast_json": timeline_forecast_json,
        "clients_json": clients_json,
        "by_horizon_json": by_horizon_json,
        "current_ca_js": current_ca_js,
    }
    return render(request, "client_analytics/projection.html", context)


@require_http_methods(["GET"])
def ajax_projection_client(request, pk):
    """AJAX — projection détaillée pour un client unique."""
    dataset = get_object_or_404(Dataset, pk=pk)
    client_id = (request.GET.get("client") or "").strip()
    if not client_id:
        return JsonResponse({"success": False, "error": "client manquant"}, status=400)

    df_processed = dataset_io.load_dataset_df(dataset)
    if df_processed is None:
        return JsonResponse(
            {"success": False, "error": "Dataset introuvable"}, status=404
        )

    try:
        result = analysis_projection.analyze_client_projection(df_processed, client_id)
    except Exception as e:
        logger.exception(
            "[projection] ERROR analyze_client_projection (client=%s)", client_id
        )
        return JsonResponse({"success": False, "error": str(e)}, status=500)

    if result.get("error"):
        return JsonResponse({"success": False, "error": result["error"]}, status=422)

    return JsonResponse({"success": True, "data": result})


# ═══════════════════════════════════════════════════════════════════════════
# DATASET PROCESSING (background thread + AJAX polling)
# ═══════════════════════════════════════════════════════════════════════════

def _process_dataset_background(pk):
    """Background thread: read raw file, process, overwrite with processed data."""
    from django.db import connection
    try:
        dataset = Dataset.objects.get(pk=pk)
        file_path = dataset.get_file_path()

        logger.info("[processing] START dataset %s: %s", pk, file_path)

        if not file_path or not os.path.exists(file_path):
            logger.error("[processing] File not found: %s", file_path)
            Dataset.objects.filter(pk=pk).update(processing_status='error')
            return

        # Read raw Excel using openpyxl engine (fast), then drop last 2 rows
        # NOTE: skipfooter=2 forces the slow Python engine — avoid it!
        df = dataset_io.read_excel_file(file_path)
        if len(df) > 2:
            df = df.iloc[:-2]
        logger.info("[processing] Read %d rows, %d cols", *df.shape)

        # Apply full processing pipeline
        df_final = data_processing.process_raw_data(df)
        logger.info("[processing] Processed → %d rows, %d cols", *df_final.shape)

        # Overwrite file with processed data
        output = BytesIO()
        df_final.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)

        file_name = dataset_io.get_processed_output_name(os.path.basename(dataset.file.name))
        dataset.file.save(file_name, ContentFile(output.read()), save=False)
        dataset.processing_status = 'done'
        dataset.save(update_fields=['processing_status', 'file'])

        logger.info("[processing] DONE dataset %s", pk)

    except Exception as e:
        logger.exception("[processing] ERROR dataset %s: %s", pk, e)
        try:
            Dataset.objects.filter(pk=pk).update(processing_status='error')
        except Exception:
            pass
    finally:
        connection.close()


def dataset_processing(request, pk):
    """Page showing processing spinner with AJAX polling."""
    dataset = get_object_or_404(Dataset, pk=pk)
    if dataset.processing_status == 'done':
        return redirect("client_analytics:dataset_overview", pk=pk)
    return render(request, "client_analytics/dataset_processing.html", {"dataset": dataset})


def start_dataset_processing(request, pk):
    """AJAX endpoint: trigger background processing (atomic)."""
    dataset = get_object_or_404(Dataset, pk=pk)
    if dataset.processing_status == 'done':
        return JsonResponse({"status": "done"})

    # Allow retry from error state or stuck processing state
    if dataset.processing_status in ('error', 'processing'):
        Dataset.objects.filter(pk=pk).update(processing_status='pending')

    # Atomic transition: only one request can start processing
    updated = Dataset.objects.filter(pk=pk, processing_status='pending').update(
        processing_status='processing'
    )
    if updated:
        t = threading.Thread(
            target=_process_dataset_background, args=(pk,), daemon=True
        )
        t.start()
        return JsonResponse({"status": "started"})

    return JsonResponse({"status": dataset.processing_status})


def check_dataset_status(request, pk):
    """AJAX endpoint: return current processing status."""
    dataset = get_object_or_404(Dataset, pk=pk)
    return JsonResponse({"status": dataset.processing_status})


# ═══════════════════════════════════════════════════════════════════════════
# CHUNKED FILE UPLOAD (for slow connections)
# ═══════════════════════════════════════════════════════════════════════════

def _get_chunk_dir(upload_id):
    """Return temp directory for chunks of a given upload."""
    safe_id = str(upload_id).replace('..', '').replace('/', '').replace('\\', '')
    return os.path.join(tempfile.gettempdir(), 'chunked_uploads', safe_id)


@require_http_methods(["POST"])
def upload_chunk(request):
    """Receive a single chunk of a file upload. Each chunk is ~500KB."""
    upload_id = request.POST.get('upload_id', '')
    chunk_index = request.POST.get('chunk_index', '')
    total_chunks = request.POST.get('total_chunks', '')

    if not upload_id or not chunk_index or not total_chunks:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    # Validate upload_id format (UUID)
    try:
        uuid.UUID(upload_id)
    except ValueError:
        return JsonResponse({"error": "Invalid upload_id"}, status=400)

    chunk_file = request.FILES.get('chunk')
    if not chunk_file:
        return JsonResponse({"error": "No chunk file"}, status=400)

    chunk_dir = _get_chunk_dir(upload_id)
    os.makedirs(chunk_dir, exist_ok=True)

    chunk_path = os.path.join(chunk_dir, f'chunk_{int(chunk_index):05d}')
    with open(chunk_path, 'wb') as f:
        for part in chunk_file.chunks():
            f.write(part)

    logger.info("[chunk] upload_id=%s chunk=%s/%s saved", upload_id, chunk_index, total_chunks)
    return JsonResponse({"status": "ok", "chunk": int(chunk_index)})


@require_http_methods(["POST"])
def finalize_upload(request):
    """Assemble chunks into a file, create Dataset, redirect to processing."""
    upload_id = request.POST.get('upload_id', '')
    file_name = request.POST.get('file_name', 'upload.xlsx')
    dataset_name = request.POST.get('dataset_name', '')
    total_chunks = int(request.POST.get('total_chunks', '0'))

    if not upload_id or not dataset_name or total_chunks < 1:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    try:
        uuid.UUID(upload_id)
    except ValueError:
        return JsonResponse({"error": "Invalid upload_id"}, status=400)

    chunk_dir = _get_chunk_dir(upload_id)

    # Verify all chunks exist
    for i in range(total_chunks):
        chunk_path = os.path.join(chunk_dir, f'chunk_{i:05d}')
        if not os.path.exists(chunk_path):
            return JsonResponse({"error": f"Missing chunk {i}"}, status=400)

    # Assemble file
    assembled = BytesIO()
    for i in range(total_chunks):
        chunk_path = os.path.join(chunk_dir, f'chunk_{i:05d}')
        with open(chunk_path, 'rb') as f:
            assembled.write(f.read())
    assembled.seek(0)

    # Create Dataset
    dataset = Dataset(
        name=dataset_name,
        source_type='upload',
        processing_status='pending',
    )
    dataset.file.save(file_name, ContentFile(assembled.read()), save=True)

    logger.info("[finalize] Dataset pk=%s created from %d chunks", dataset.pk, total_chunks)

    # Cleanup chunks
    import shutil
    shutil.rmtree(chunk_dir, ignore_errors=True)

    return JsonResponse({
        "status": "ok",
        "dataset_pk": dataset.pk,
        "redirect_url": f"/dataset/{dataset.pk}/processing/",
    })
