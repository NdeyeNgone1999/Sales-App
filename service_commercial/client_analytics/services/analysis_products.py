"""
Service pour le sous-onglet ANALYSE PRODUITS
Analyse détaillée par famille de produits : ABC, Segmentation Volume/Valeur
AUTONOME - Ne dépend d'aucun autre fichier de services
"""
import pandas as pd
import numpy as np

from .visualizations import viz_products


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _minmax(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors='coerce')
    if s.isna().all():
        return pd.Series([0.0] * len(series), index=series.index)
    vmin = float(np.nanmin(s.values))
    vmax = float(np.nanmax(s.values))
    if vmax - vmin == 0:
        return pd.Series([0.5] * len(series), index=series.index)
    return (s - vmin) / (vmax - vmin)


def analyze_product_families(
    df_final: pd.DataFrame,
    time_granularity: str = 'month',
    selected_product: str | None = None,
    selected_family: str | None = None,
    max_product_options: int = 300,
    max_family_options: int = 200,
    compare_products: list[str] | None = None,
    compare_families: list[str] | None = None,
    compare_products_metric: str = 'Qty_Total',
    compare_families_metric: str = 'Qty_Total',
    max_compare_items: int = 5,
) -> dict:
    """Analyse produits (familles) sérialisée pour templates.

    Retourne un dict conforme au contrat front (list[dict] et graphes Plotly HTML).
    """

    empty_payload = {
        "stats_famille": [],
        "abc_summary": {},
        "classe_a": [],
        "classe_b": [],
        "classe_c": [],
        "classe_a_nb": 0,
        "classe_a_ca": 0.0,
        "classe_a_part": 0.0,
        "classe_b_nb": 0,
        "classe_b_ca": 0.0,
        "classe_b_part": 0.0,
        "classe_c_nb": 0,
        "classe_c_ca": 0.0,
        "classe_c_part": 0.0,
        "segment_summary": [],
        "top20_score": [],
        "corr_matrix": None,
        "product_options": [],
        "selected_product": None,
        "product_corr": None,
        "product_corr_table": [],
        "family_options": [],
        "selected_family": None,
        "family_corr": None,
        "family_corr_table": [],
        "compare_selected_products": [],
        "compare_selected_families": [],
        "compare_products_metric": compare_products_metric,
        "compare_families_metric": compare_families_metric,
        "insights": {},
        "family_graphs": {},
    }

    if df_final is None or len(df_final) == 0:
        out = dict(empty_payload)
        out["error"] = "Dataset vide"
        return out

    try:
        # Mapping colonnes temps imposées
        if time_granularity == 'month':
            time_col = 'Month'
        elif time_granularity == 'quarter':
            time_col = 'Fiscal_Quarter'
        elif time_granularity == 'year':
            time_col = 'Fiscal_Year_Label'
        else:
            time_col = 'Month'

        required_cols = ['Famille', 'Montant', 'Quantité', 'PU Net', 'N° Bon', 'Cpt Client', 'Country', 'Lead_Time_Days']
        missing_required = [c for c in required_cols if c not in df_final.columns]
        if missing_required:
            print(f"[products:{time_granularity}] Colonnes manquantes: {missing_required}")

        # Déviation et délai prévu: optionnels
        deviation_col = 'Lead_Time_Deviation_Days' if 'Lead_Time_Deviation_Days' in df_final.columns else None

        # Colonne produit (robuste) pour l'analyse corrélation par produit
        product_col = _first_existing_column(
            df_final,
            [
                'Code Recette',
                'Code Produit',
                'Produit',
                'Article',
                'Libelle 1',
                'Libellé 1',
                'Désignation',
                'Designation',
                'Item',
            ],
        )

        if 'Famille' not in df_final.columns:
            out = dict(empty_payload)
            out['error'] = "Colonne 'Famille' manquante"
            return out

        if 'Montant' not in df_final.columns:
            out = dict(empty_payload)
            out['error'] = "Colonne 'Montant' manquante"
            return out

        # Aggrégats par famille
        base = df_final.copy()
        base['Montant'] = pd.to_numeric(base.get('Montant'), errors='coerce')
        base['Quantité'] = pd.to_numeric(base.get('Quantité'), errors='coerce')

        agg = {
            'Montant': 'sum',
        }
        if 'Quantité' in base.columns:
            agg['Quantité'] = 'sum'
        if 'N° Bon' in base.columns:
            agg['N° Bon'] = pd.Series.nunique
        if 'Cpt Client' in base.columns:
            agg['Cpt Client'] = pd.Series.nunique
        if 'Lead_Time_Days' in base.columns:
            agg['Lead_Time_Days'] = 'median'

        stats = base.groupby('Famille', sort=False).agg(agg)
        stats = stats.rename(
            columns={
                'Montant': 'CA_Total',
                'Quantité': 'Qty_Total',
                'N° Bon': 'Nb_Commandes',
                'Cpt Client': 'Nb_Clients',
                'Lead_Time_Days': 'LeadTime_Median',
            }
        )

        if deviation_col:
            dev = pd.to_numeric(base[deviation_col], errors='coerce')
            # P90 par famille
            dev_p90 = base.groupby('Famille', sort=False)[deviation_col].quantile(0.90)
            stats['Deviation_P90'] = pd.to_numeric(dev_p90, errors='coerce')
            # Late rate % (déviation > 0)
            late_rate = base.groupby('Famille', sort=False).apply(
                lambda x: (pd.to_numeric(x[deviation_col], errors='coerce') > 0).mean()
            )
            stats['Late_Rate_Pct'] = pd.to_numeric(late_rate, errors='coerce') * 100.0
        else:
            stats['Deviation_P90'] = np.nan
            stats['Late_Rate_Pct'] = np.nan

        stats = stats.reset_index()

        # Compléments
        stats['Qty_Total'] = pd.to_numeric(stats.get('Qty_Total'), errors='coerce')
        stats['CA_Total'] = pd.to_numeric(stats.get('CA_Total'), errors='coerce')
        stats['PU_Pondere'] = np.where(stats['Qty_Total'].fillna(0) > 0, stats['CA_Total'] / stats['Qty_Total'], np.nan)

        total_ca = float(stats['CA_Total'].fillna(0).sum())
        stats = stats.sort_values('CA_Total', ascending=False, na_position='last')
        stats['Part_Pct'] = np.where(total_ca > 0, (stats['CA_Total'] / total_ca) * 100.0, 0.0)
        stats['Part_Cumul_Pct'] = stats['Part_Pct'].cumsum()
        stats['Rang'] = np.arange(1, len(stats) + 1)

        def _classe_abc(cumul: float) -> str:
            if pd.isna(cumul):
                return 'C'
            if cumul <= 80:
                return 'A'
            if cumul <= 95:
                return 'B'
            return 'C'

        stats['Classe_ABC'] = stats['Part_Cumul_Pct'].apply(_classe_abc)

        # ABC summary -> dict
        abc_df = (
            stats.groupby('Classe_ABC', dropna=False)
            .agg(CA_Total=('CA_Total', 'sum'), Nb_Familles=('Famille', 'count'), Part_CA_Pct=('Part_Pct', 'sum'))
            .reset_index()
        )
        abc_summary = {row['Classe_ABC']: {
            'CA_Total': float(pd.to_numeric(row['CA_Total'], errors='coerce') or 0.0),
            'Nb_Familles': int(row['Nb_Familles'] or 0),
            'Part_CA_Pct': float(pd.to_numeric(row['Part_CA_Pct'], errors='coerce') or 0.0),
        } for _, row in abc_df.iterrows()}

        classe_a_df = stats[stats['Classe_ABC'] == 'A'].head(20)
        classe_b_df = stats[stats['Classe_ABC'] == 'B'].head(20)
        classe_c_df = stats[stats['Classe_ABC'] == 'C'].head(20)

        classe_a_ca = float(pd.to_numeric(classe_a_df['CA_Total'], errors='coerce').fillna(0).sum())
        classe_b_ca = float(pd.to_numeric(classe_b_df['CA_Total'], errors='coerce').fillna(0).sum())
        classe_c_ca = float(pd.to_numeric(classe_c_df['CA_Total'], errors='coerce').fillna(0).sum())
        classe_a_part = float(pd.to_numeric(classe_a_df['Part_Pct'], errors='coerce').fillna(0).sum())
        classe_b_part = float(pd.to_numeric(classe_b_df['Part_Pct'], errors='coerce').fillna(0).sum())
        classe_c_part = float(pd.to_numeric(classe_c_df['Part_Pct'], errors='coerce').fillna(0).sum())

        # Segmentation volume x valeur (médianes)
        median_qty = float(pd.to_numeric(stats['Qty_Total'], errors='coerce').median()) if 'Qty_Total' in stats.columns else np.nan
        median_pu = float(pd.to_numeric(stats['PU_Pondere'], errors='coerce').median()) if 'PU_Pondere' in stats.columns else np.nan

        def _segment(row) -> str:
            qty = pd.to_numeric(row.get('Qty_Total'), errors='coerce')
            pu = pd.to_numeric(row.get('PU_Pondere'), errors='coerce')
            if pd.isna(qty) or pd.isna(pu) or pd.isna(median_qty) or pd.isna(median_pu):
                return 'Unknown'
            vol = 'HighVolume' if qty >= median_qty else 'LowVolume'
            val = 'HighPrice' if pu >= median_pu else 'LowPrice'
            return f"{vol} x {val}"

        stats['Segment'] = stats.apply(_segment, axis=1)
        segment_summary_df = (
            stats.groupby('Segment', dropna=False)
            .agg(CA_Total=('CA_Total', 'sum'), Nb_Familles=('Famille', 'count'))
            .reset_index()
            .sort_values('CA_Total', ascending=False)
        )

        # Familles par segment (pour affichage dans le tableau de segmentation)
        segment_families = (
            stats[['Segment', 'Famille', 'CA_Total']]
            .copy()
            .assign(Famille=lambda d: d['Famille'].astype(str))
            .sort_values(['Segment', 'CA_Total', 'Famille'], ascending=[True, False, True])
            .groupby('Segment', dropna=False)['Famille']
            .apply(list)
            .reset_index(name='Familles')
        )
        segment_summary_df = segment_summary_df.merge(segment_families, on='Segment', how='left')

        def _families_preview(fams, limit: int = 8) -> str:
            if not isinstance(fams, list) or len(fams) == 0:
                return ''
            if len(fams) <= limit:
                return ', '.join(fams)
            return ', '.join(fams[:limit]) + f"… (+{len(fams) - limit})"

        segment_summary_df['Familles_Preview'] = segment_summary_df['Familles'].apply(_families_preview)

        # Score global (0-100)
        score_ca = _minmax(stats['CA_Total'])
        score_qty = _minmax(stats['Qty_Total'])
        score_pu = _minmax(stats['PU_Pondere'])
        if 'Late_Rate_Pct' in stats.columns and stats['Late_Rate_Pct'].notna().any():
            service = 1.0 - _minmax(stats['Late_Rate_Pct'])
        else:
            service = pd.Series([0.5] * len(stats), index=stats.index)

        score_global = (0.45 * score_ca + 0.20 * score_qty + 0.20 * score_pu + 0.15 * service) * 100.0
        stats['Score_Global'] = pd.to_numeric(score_global, errors='coerce').round(2)
        stats['Rank_Score'] = stats['Score_Global'].rank(ascending=False, method='dense').astype(int)
        top20_score_df = stats.sort_values(['Score_Global', 'CA_Total'], ascending=False).head(20)

        # Corr Spearman
        corr_cols = [
            c for c in ['CA_Total', 'Qty_Total', 'PU_Pondere', 'LeadTime_Median', 'Deviation_P90', 'Late_Rate_Pct', 'Nb_Clients', 'Nb_Commandes']
            if c in stats.columns
        ]
        corr_matrix_df = pd.DataFrame()
        if len(corr_cols) >= 2:
            corr_matrix_df = stats[corr_cols].corr(method='spearman')

        corr_matrix = None
        if not corr_matrix_df.empty:
            corr_matrix = {
                'columns': corr_matrix_df.columns.astype(str).tolist(),
                'index': corr_matrix_df.index.astype(str).tolist(),
                'values': corr_matrix_df.round(3).values.tolist(),
            }

        # Insights
        insights = {
            'top_ca': None,
            'top_qty': None,
            'top_pu': None,
            'worst_delay': None,
            'dominant_country': None,
        }
        if len(stats):
            try:
                insights['top_ca'] = str(stats.iloc[0]['Famille'])
            except Exception:
                pass
        if 'Qty_Total' in stats.columns and len(stats):
            try:
                insights['top_qty'] = str(stats.sort_values('Qty_Total', ascending=False).iloc[0]['Famille'])
            except Exception:
                pass
        if 'PU_Pondere' in stats.columns and len(stats):
            try:
                insights['top_pu'] = str(stats.sort_values('PU_Pondere', ascending=False).iloc[0]['Famille'])
            except Exception:
                pass
        if 'Deviation_P90' in stats.columns and stats['Deviation_P90'].notna().any():
            try:
                insights['worst_delay'] = str(stats.sort_values('Deviation_P90', ascending=False).iloc[0]['Famille'])
            except Exception:
                pass
        # dominant_country: sur la famille top_ca si possible, sinon global
        if 'Country' in df_final.columns and 'Montant' in df_final.columns:
            try:
                if insights['top_ca']:
                    sub = df_final[df_final['Famille'] == insights['top_ca']]
                    if len(sub):
                        insights['dominant_country'] = str(sub.groupby('Country')['Montant'].sum().sort_values(ascending=False).index[0])
                    else:
                        insights['dominant_country'] = str(df_final.groupby('Country')['Montant'].sum().sort_values(ascending=False).index[0])
                else:
                    insights['dominant_country'] = str(df_final.groupby('Country')['Montant'].sum().sort_values(ascending=False).index[0])
            except Exception:
                pass

        # Time series pour evolutions
        time_series_famille = pd.DataFrame()
        if time_col in df_final.columns:
            ts = df_final.groupby([time_col, 'Famille'], sort=False).agg(Montant=('Montant', 'sum'), Quantité=('Quantité', 'sum')).reset_index()
            ts['CA'] = pd.to_numeric(ts['Montant'], errors='coerce')
            ts['Qty'] = pd.to_numeric(ts['Quantité'], errors='coerce')
            ts['PU_Pondere'] = np.where(ts['Qty'].fillna(0) > 0, ts['CA'] / ts['Qty'], np.nan)
            time_series_famille = ts[[time_col, 'Famille', 'CA', 'Qty', 'PU_Pondere']]

        # Corrélation par produit (séries temporelles)
        product_options: list[dict] = []
        selected_product_norm = (str(selected_product).strip() if selected_product is not None else '')
        selected_family_norm = (str(selected_family).strip() if selected_family is not None else '')
        if product_col and product_col in df_final.columns and 'Montant' in df_final.columns:
            tmp = df_final[[product_col, 'Montant']].copy()
            tmp[product_col] = tmp[product_col].astype(str)
            tmp['Montant'] = pd.to_numeric(tmp['Montant'], errors='coerce')
            agg_prod = tmp.groupby(product_col, dropna=False)['Montant'].sum().sort_values(ascending=False)
            for prod_id in agg_prod.head(int(max_product_options)).index:
                if pd.isna(prod_id):
                    continue
                value = str(prod_id)
                if not value or value == 'nan':
                    continue
                product_options.append({'value': value, 'label': value})

        product_corr = None
        product_corr_table: list[dict] = []
        product_corr_df = None

        family_options: list[dict] = []
        family_corr = None
        family_corr_table: list[dict] = []
        family_corr_df = None

        # Options famille (top par CA)
        try:
            fam_ca = (
                df_final[['Famille', 'Montant']]
                .assign(Montant=lambda d: pd.to_numeric(d['Montant'], errors='coerce'))
                .groupby('Famille', dropna=False)['Montant']
                .sum()
                .sort_values(ascending=False)
            )
            for fam in fam_ca.head(int(max_family_options)).index:
                if pd.isna(fam):
                    continue
                v = str(fam)
                if not v or v == 'nan':
                    continue
                family_options.append({'value': v, 'label': v})
        except Exception:
            family_options = []

        def _corr_for_subset(dsub: pd.DataFrame) -> tuple[pd.DataFrame | None, list[dict]]:
            """Calcule corr Spearman sur séries temporelles (périodes) et renvoie (corr_df, table rho vs CA_Total)."""
            if dsub is None or len(dsub) < 3 or time_col not in dsub.columns:
                return None, []

            dsub = dsub.copy()
            dsub['Montant'] = pd.to_numeric(dsub.get('Montant'), errors='coerce')
            if 'Quantité' in dsub.columns:
                dsub['Quantité'] = pd.to_numeric(dsub.get('Quantité'), errors='coerce')
            if 'Lead_Time_Days' in dsub.columns:
                dsub['Lead_Time_Days'] = pd.to_numeric(dsub.get('Lead_Time_Days'), errors='coerce')
            if deviation_col and deviation_col in dsub.columns:
                dsub[deviation_col] = pd.to_numeric(dsub.get(deviation_col), errors='coerce')

            agg_ts = {"CA_Total": ('Montant', 'sum')}
            if 'Quantité' in dsub.columns:
                agg_ts['Qty_Total'] = ('Quantité', 'sum')
            if 'N° Bon' in dsub.columns:
                agg_ts['Nb_Commandes'] = ('N° Bon', pd.Series.nunique)
            if 'Cpt Client' in dsub.columns:
                agg_ts['Nb_Clients'] = ('Cpt Client', pd.Series.nunique)
            if 'Lead_Time_Days' in dsub.columns:
                agg_ts['LeadTime_Median'] = ('Lead_Time_Days', 'median')

            ts_any = dsub.groupby(time_col, dropna=False).agg(**agg_ts).reset_index()

            if 'Qty_Total' in ts_any.columns:
                ts_any['PU_Pondere'] = np.where(
                    pd.to_numeric(ts_any['Qty_Total'], errors='coerce').fillna(0) > 0,
                    pd.to_numeric(ts_any['CA_Total'], errors='coerce') / pd.to_numeric(ts_any['Qty_Total'], errors='coerce'),
                    np.nan,
                )
            else:
                ts_any['PU_Pondere'] = np.nan

            if deviation_col and deviation_col in dsub.columns:
                dev_p90_ts = dsub.groupby(time_col, dropna=False)[deviation_col].quantile(0.90).rename('Deviation_P90')
                ts_any = ts_any.merge(dev_p90_ts.reset_index(), on=time_col, how='left')
                late_rate_ts = dsub.groupby(time_col, dropna=False).apply(
                    lambda x: (pd.to_numeric(x[deviation_col], errors='coerce') > 0).mean()
                ).rename('Late_Rate_Pct')
                ts_any = ts_any.merge(late_rate_ts.reset_index(), on=time_col, how='left')
                ts_any['Late_Rate_Pct'] = pd.to_numeric(ts_any['Late_Rate_Pct'], errors='coerce') * 100.0
            else:
                ts_any['Deviation_P90'] = np.nan
                ts_any['Late_Rate_Pct'] = np.nan

            corr_cols_any = [
                c for c in ['CA_Total', 'Qty_Total', 'PU_Pondere', 'LeadTime_Median', 'Deviation_P90', 'Late_Rate_Pct', 'Nb_Clients', 'Nb_Commandes']
                if c in ts_any.columns
            ]
            if len(corr_cols_any) < 2:
                return None, []

            ts_num = ts_any[corr_cols_any].copy()
            if len(ts_num.dropna(how='all')) < 3:
                return None, []

            corr_df_any = ts_num.corr(method='spearman')

            table_any: list[dict] = []
            if 'CA_Total' in corr_df_any.columns:
                for v in corr_df_any.columns:
                    if v == 'CA_Total':
                        continue
                    val = corr_df_any.loc[v, 'CA_Total']
                    table_any.append({'variable': str(v), 'rho': float(val) if pd.notna(val) else None})

            return corr_df_any, table_any

        def _timeseries_for_subset(dsub: pd.DataFrame) -> pd.DataFrame | None:
            """Agrège un sous-ensemble par période et calcule les métriques standard."""
            if dsub is None or len(dsub) == 0 or time_col not in dsub.columns:
                return None

            dsub = dsub.copy()
            dsub['Montant'] = pd.to_numeric(dsub.get('Montant'), errors='coerce')
            if 'Quantité' in dsub.columns:
                dsub['Quantité'] = pd.to_numeric(dsub.get('Quantité'), errors='coerce')
            if 'Lead_Time_Days' in dsub.columns:
                dsub['Lead_Time_Days'] = pd.to_numeric(dsub.get('Lead_Time_Days'), errors='coerce')
            if deviation_col and deviation_col in dsub.columns:
                dsub[deviation_col] = pd.to_numeric(dsub.get(deviation_col), errors='coerce')

            agg_ts = {"CA_Total": ('Montant', 'sum')}
            if 'Quantité' in dsub.columns:
                agg_ts['Qty_Total'] = ('Quantité', 'sum')
            if 'N° Bon' in dsub.columns:
                agg_ts['Nb_Commandes'] = ('N° Bon', pd.Series.nunique)
            if 'Cpt Client' in dsub.columns:
                agg_ts['Nb_Clients'] = ('Cpt Client', pd.Series.nunique)
            if 'Lead_Time_Days' in dsub.columns:
                agg_ts['LeadTime_Median'] = ('Lead_Time_Days', 'median')

            ts = dsub.groupby(time_col, dropna=False).agg(**agg_ts).reset_index()

            if 'Qty_Total' in ts.columns:
                ts['PU_Pondere'] = np.where(
                    pd.to_numeric(ts['Qty_Total'], errors='coerce').fillna(0) > 0,
                    pd.to_numeric(ts['CA_Total'], errors='coerce') / pd.to_numeric(ts['Qty_Total'], errors='coerce'),
                    np.nan,
                )
            else:
                ts['PU_Pondere'] = np.nan

            if deviation_col and deviation_col in dsub.columns:
                dev_p90_ts = dsub.groupby(time_col, dropna=False)[deviation_col].quantile(0.90).rename('Deviation_P90')
                ts = ts.merge(dev_p90_ts.reset_index(), on=time_col, how='left')
                late_rate_ts = dsub.groupby(time_col, dropna=False).apply(
                    lambda x: (pd.to_numeric(x[deviation_col], errors='coerce') > 0).mean()
                ).rename('Late_Rate_Pct')
                ts = ts.merge(late_rate_ts.reset_index(), on=time_col, how='left')
                ts['Late_Rate_Pct'] = pd.to_numeric(ts['Late_Rate_Pct'], errors='coerce') * 100.0
            else:
                ts['Deviation_P90'] = np.nan
                ts['Late_Rate_Pct'] = np.nan

            return ts

        # Produit ciblé
        if selected_product_norm and product_col and product_col in df_final.columns:
            dpp = df_final.copy()
            dpp[product_col] = dpp[product_col].astype(str)
            dpp = dpp[dpp[product_col] == selected_product_norm].copy()
            product_corr_df, product_corr_table = _corr_for_subset(dpp)
            if product_corr_df is not None and not product_corr_df.empty:
                product_corr = {
                    'columns': product_corr_df.columns.astype(str).tolist(),
                    'index': product_corr_df.index.astype(str).tolist(),
                    'values': product_corr_df.round(3).values.tolist(),
                }

        # Famille ciblée
        if (not selected_product_norm) and selected_family_norm:
            dff = df_final.copy()
            dff['Famille'] = dff['Famille'].astype(str)
            dff = dff[dff['Famille'] == selected_family_norm].copy()
            family_corr_df, family_corr_table = _corr_for_subset(dff)
            if family_corr_df is not None and not family_corr_df.empty:
                family_corr = {
                    'columns': family_corr_df.columns.astype(str).tolist(),
                    'index': family_corr_df.index.astype(str).tolist(),
                    'values': family_corr_df.round(3).values.tolist(),
                }

        # Comparaison (séparée) : produits entre eux / familles entre elles
        allowed_metrics = {'CA_Total', 'Qty_Total', 'PU_Pondere', 'Late_Rate_Pct', 'LeadTime_Median'}
        prod_metric_norm = (str(compare_products_metric or 'Qty_Total').strip() or 'Qty_Total')
        fam_metric_norm = (str(compare_families_metric or 'Qty_Total').strip() or 'Qty_Total')
        if prod_metric_norm not in allowed_metrics:
            prod_metric_norm = 'Qty_Total'
        if fam_metric_norm not in allowed_metrics:
            fam_metric_norm = 'Qty_Total'

        compare_products_norm = [str(x).strip() for x in (compare_products or []) if str(x).strip()]
        compare_families_norm = [str(x).strip() for x in (compare_families or []) if str(x).strip()]

        # Dédupliquer en gardant l'ordre
        seen = set()
        compare_products_norm = [x for x in compare_products_norm if not (x in seen or seen.add(x))]
        seen = set()
        compare_families_norm = [x for x in compare_families_norm if not (x in seen or seen.add(x))]

        # Limiter séparément
        compare_products_norm = compare_products_norm[: int(max_compare_items)]
        compare_families_norm = compare_families_norm[: int(max_compare_items)]

        compare_products_html = None
        compare_families_html = None

        # Préparer un ordre de périodes (catégories) cohérent (mois vs fiscal)
        if time_col in df_final.columns:
            period_order_str = [str(p) for p in viz_products._sorted_periods(df_final[time_col].dropna().unique())]
        else:
            period_order_str = []

        def _make_compare_line(df_rows: pd.DataFrame, title: str) -> str | None:
            if df_rows is None or df_rows.empty:
                return None
            try:
                import plotly.graph_objects as go

                df_rows = df_rows.copy()
                df_rows['PeriodLabel'] = df_rows['Period'].map(viz_products._short_period_label)
                df_rows['Value'] = pd.to_numeric(df_rows['Value'], errors='coerce')

                fig = go.Figure()
                for item, d in df_rows.groupby('Item', dropna=False):
                    fig.add_trace(
                        go.Scatter(
                            x=d['PeriodLabel'],
                            y=d['Value'],
                            mode='lines+markers',
                            name=str(item),
                        )
                    )

                fig.update_layout(
                    title=title,
                    height=430,
                    margin=dict(l=10, r=10, t=60, b=10),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
                )
                fig.update_xaxes(
                    type='category',
                    categoryorder='array',
                    categoryarray=[viz_products._short_period_label(p) for p in period_order_str],
                    tickangle=-45,
                    automargin=True,
                )
                fig.update_yaxes(automargin=True)

                return fig.to_html(full_html=False, include_plotlyjs=False)
            except Exception:
                return None

        # Produits
        if compare_products_norm and time_col in df_final.columns and product_col and product_col in df_final.columns:
            rows = []
            dpx = df_final.copy()
            dpx[product_col] = dpx[product_col].astype(str)
            for prod in compare_products_norm:
                dsub = dpx[dpx[product_col] == prod].copy()
                ts = _timeseries_for_subset(dsub)
                if ts is None or prod_metric_norm not in ts.columns:
                    continue
                for _, r in ts.iterrows():
                    rows.append({
                        'Period': str(r[time_col]),
                        'Item': str(prod),
                        'Value': r.get(prod_metric_norm),
                    })

            compare_products_html = _make_compare_line(
                pd.DataFrame(rows) if rows else pd.DataFrame(),
                title=f"Comparaison produits — {prod_metric_norm} (par {time_granularity})",
            )

        # Familles
        if compare_families_norm and time_col in df_final.columns and 'Famille' in df_final.columns:
            rows = []
            dfx = df_final.copy()
            dfx['Famille'] = dfx['Famille'].astype(str)
            for fam in compare_families_norm:
                dsub = dfx[dfx['Famille'] == fam].copy()
                ts = _timeseries_for_subset(dsub)
                if ts is None or fam_metric_norm not in ts.columns:
                    continue
                for _, r in ts.iterrows():
                    rows.append({
                        'Period': str(r[time_col]),
                        'Item': str(fam),
                        'Value': r.get(fam_metric_norm),
                    })

            compare_families_html = _make_compare_line(
                pd.DataFrame(rows) if rows else pd.DataFrame(),
                title=f"Comparaison familles — {fam_metric_norm} (par {time_granularity})",
            )

        # Graphiques Plotly

        top10_fams = stats.head(10)['Famille'].astype(str).tolist()

        pareto_html = None
        top_ca_html = None
        top_qty_html = None
        top_pu_html = None
        bubble_html = None
        heatmap_html = None

        if time_granularity == 'month':
            if hasattr(viz_products, 'create_pareto_abc_animated_by_month'):
                pareto_html = viz_products.create_pareto_abc_animated_by_month(df_final, time_col=time_col)
            if hasattr(viz_products, 'create_top_bar_animated_by_month'):
                top_ca_html = viz_products.create_top_bar_animated_by_month(df_final, metric='CA_Total', title='Top 15 familles - CA', time_col=time_col, top_n=15)
                top_qty_html = viz_products.create_top_bar_animated_by_month(df_final, metric='Qty_Total', title='Top 15 familles - Quantité', time_col=time_col, top_n=15)
                top_pu_html = viz_products.create_top_bar_animated_by_month(df_final, metric='PU_Pondere', title='Top 15 familles - PU pondéré', time_col=time_col, top_n=15)
            if hasattr(viz_products, 'create_bubble_value_volume_animated_by_month'):
                bubble_html = viz_products.create_bubble_value_volume_animated_by_month(df_final, time_col=time_col)
            if hasattr(viz_products, 'create_heatmap_family_country_animated_by_month'):
                heatmap_html = viz_products.create_heatmap_family_country_animated_by_month(df_final, time_col=time_col, top_families=12, top_countries=10)

        if not pareto_html:
            pareto_html = viz_products.create_pareto_abc(stats)

        family_graphs = {
            'pareto_abc': pareto_html,
            'top_ca': top_ca_html or viz_products.create_top_bar(stats, 'CA_Total', 'Top 15 familles - CA', top_n=15),
            'top_qty': top_qty_html or viz_products.create_top_bar(stats, 'Qty_Total', 'Top 15 familles - Quantité', top_n=15),
            'top_pu': top_pu_html or viz_products.create_top_bar(stats, 'PU_Pondere', 'Top 15 familles - PU pondéré', top_n=15),
            'bubble_value_volume': bubble_html or viz_products.create_bubble_value_volume(stats),
            'heatmap_family_country': heatmap_html or (
                viz_products.create_heatmap_family_country(df_final, top_families=12, top_countries=10)
                if hasattr(viz_products, 'create_heatmap_family_country') else None
            ),
            'evolution_ca_top': viz_products.create_evolution(time_series_famille, metric='CA', title='Évolution CA (Top 5 + Others)', top_n=5),
            'evolution_pu_top': viz_products.create_evolution(time_series_famille, metric='PU_Pondere', title='Évolution PU pondéré (Top 5 + Others)', top_n=5),
            'delay_by_family': viz_products.create_delay_by_family_box(df_final, top10_fams)
            if hasattr(viz_products, 'create_delay_by_family_box') else None,
        }

        if product_corr_df is not None and not product_corr_df.empty:
            family_graphs['product_corr_heatmap'] = viz_products.create_corr_heatmap(
                product_corr_df,
                title=f"Corrélations (Spearman) — Produit {selected_product_norm}",
            )

        if family_corr_df is not None and not family_corr_df.empty:
            family_graphs['family_corr_heatmap'] = viz_products.create_corr_heatmap(
                family_corr_df,
                title=f"Corrélations (Spearman) — Famille {selected_family_norm}",
            )

        if compare_products_html:
            family_graphs['compare_products_timeseries'] = compare_products_html
        if compare_families_html:
            family_graphs['compare_families_timeseries'] = compare_families_html

        # --- NEW: SKU-level charts when a product is selected ---
        if selected_product_norm and product_col and product_col in df_final.columns and time_col in df_final.columns:
            try:
                family_graphs["sku_pu_distribution"] = viz_products.create_sku_pu_distribution_bubble(
                    df_final=df_final,
                    selected_product=selected_product_norm,
                    product_col=product_col,
                    time_col=time_col,
                    window_periods=6,
                )
                family_graphs["sku_price_impact"] = viz_products.create_sku_price_impact_scatter(
                    df_final=df_final,
                    selected_product=selected_product_norm,
                    product_col=product_col,
                    time_col=time_col,
                    window_periods=6,
                )
            except Exception:
                pass

        family_graphs = {k: v for k, v in family_graphs.items() if v}

        if len(stats) == 0:
            print(f"[products:{time_granularity}] stats_famille vide. Colonnes df: {list(df_final.columns)}")

        # Sérialisation pour template
        stats_records = stats.replace({np.nan: None}).to_dict(orient='records')
        segment_records = segment_summary_df.replace({np.nan: None}).to_dict(orient='records')
        top20_records = top20_score_df.replace({np.nan: None}).to_dict(orient='records')

        out = {
            'stats_famille': stats_records,
            'abc_summary': abc_summary,
            'classe_a': classe_a_df.replace({np.nan: None}).to_dict(orient='records'),
            'classe_b': classe_b_df.replace({np.nan: None}).to_dict(orient='records'),
            'classe_c': classe_c_df.replace({np.nan: None}).to_dict(orient='records'),
            'classe_a_nb': int(len(classe_a_df)),
            'classe_a_ca': float(classe_a_ca),
            'classe_a_part': float(classe_a_part),
            'classe_b_nb': int(len(classe_b_df)),
            'classe_b_ca': float(classe_b_ca),
            'classe_b_part': float(classe_b_part),
            'classe_c_nb': int(len(classe_c_df)),
            'classe_c_ca': float(classe_c_ca),
            'classe_c_part': float(classe_c_part),
            'segment_summary': segment_records,
            'top20_score': top20_records,
            'corr_matrix': corr_matrix,
            'product_options': product_options,
            'selected_product': selected_product_norm or None,
            'product_corr': product_corr,
            'product_corr_table': product_corr_table,
            'family_options': family_options,
            'selected_family': selected_family_norm or None,
            'family_corr': family_corr,
            'family_corr_table': family_corr_table,
            'compare_selected_products': compare_products_norm,
            'compare_selected_families': compare_families_norm,
            'compare_products_metric': prod_metric_norm,
            'compare_families_metric': fam_metric_norm,
            'insights': insights,
            'family_graphs': family_graphs,
        }
        return out

    except Exception as e:
        print(f"[products:{time_granularity}] ERROR: {e}")
        out = dict(empty_payload)
        out['error'] = str(e)
        return out


def generate_product_analysis(df_final: pd.DataFrame) -> dict:
    """
    Wrapper pour l'analyse produits - utilisé dans les views
    
    Args:
        df_final: DataFrame nettoyé
    
    Returns:
        dict avec l'analyse complète des produits
    """
    return analyze_product_families(df_final)
