"""client_analytics.services.visualizations.viz_products

Visualisations Plotly pour le sous-onglet "Analyse produits".

Objectifs:
- Snippets HTML autonomes (include_plotlyjs=False, CDN chargé dans base.html).
- Robustesse: si colonnes manquantes ou dataset vide, retourner None.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re


def _tight_plotly(fig: go.Figure) -> go.Figure:
    fig.update_layout(autosize=True, margin=dict(l=40, r=15, t=60, b=40))
    fig.update_xaxes(constrain="domain")
    return fig


def _to_html(fig: go.Figure) -> str:
    fig = _tight_plotly(fig)
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={'responsive': True, 'displayModeBar': True},
    )


def _require_cols(df: pd.DataFrame, cols: list[str]) -> bool:
    return df is not None and len(df) > 0 and all(c in df.columns for c in cols)


def _sorted_periods(values) -> list[str]:
    s = pd.Series(list(values), dtype='string').dropna().astype(str)
    if s.empty:
        return []

    # Fiscal quarters / fiscal years: try to parse FYyyyy and Qn
    # Examples seen in datasets: "Q1 (Apr-Jun) FY2025", "FY2025 Q1", "FY2025-Q1", "FY2025"
    try:
        fy = s.str.extract(r'FY\s*(\d{4})', expand=False)
        q = s.str.extract(r'Q\s*([1-4])', expand=False)
        fy_num = pd.to_numeric(fy, errors='coerce')
        q_num = pd.to_numeric(q, errors='coerce')

        # If we can parse FY for most values, sort by (FY, Q)
        if fy_num.notna().sum() >= max(2, int(0.6 * len(s))):
            dfk = pd.DataFrame({'val': s, 'fy': fy_num, 'q': q_num})
            # Missing quarter => treat as 0 (year-only labels)
            dfk['q'] = dfk['q'].fillna(0)
            dfk = dfk.sort_values(['fy', 'q', 'val'])
            order = dfk['val'].tolist()
            return list(dict.fromkeys(order))
    except Exception:
        pass

    try:
        dt = pd.to_datetime(s + '-01', errors='coerce')
        if dt.notna().sum() >= max(2, int(0.6 * len(dt))):
            order = s.iloc[dt.sort_values().index].tolist()
            return list(dict.fromkeys(order))
    except Exception:
        pass
    return sorted(s.unique().tolist())


def _short_period_label(v: str) -> str:
    """Raccourcit les labels de périodes longs (ex: Fiscal_Quarter) pour améliorer la lisibilité."""
    if v is None:
        return ''
    s = str(v)
    mfy = re.search(r'FY\s*(\d{4})', s)
    mq = re.search(r'Q\s*([1-4])', s)
    if mfy and mq:
        return f"FY{mfy.group(1)} Q{mq.group(1)}"
    return s


def create_pareto_abc(stats_famille: pd.DataFrame) -> str | None:
    """Pareto/ABC: bar CA + ligne cumul Part_Cumul_Pct avec seuils 80/95."""
    if not _require_cols(stats_famille, ['Famille', 'CA_Total', 'Part_Cumul_Pct']):
        return None
    try:
        df = stats_famille.sort_values('CA_Total', ascending=False)
        x = df['Famille'].astype(str)

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=x,
                y=pd.to_numeric(df['CA_Total'], errors='coerce'),
                name='CA',
                marker_color='#3b82f6',
                hovertemplate='<b>%{x}</b><br>CA=%{y:,.0f}€<extra></extra>',
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=x,
                y=pd.to_numeric(df['Part_Cumul_Pct'], errors='coerce'),
                name='Cumul (%)',
                mode='lines+markers',
                line=dict(color='#ef4444', width=3),
                hovertemplate='<b>%{x}</b><br>Cumul=%{y:.1f}%<extra></extra>',
            ),
            secondary_y=True,
        )

        fig.update_yaxes(title_text='CA (€)', secondary_y=False)
        fig.update_yaxes(title_text='Cumul (%)', secondary_y=True, range=[0, 105])
        fig.update_xaxes(title_text='Famille', tickangle=-45)
        fig.update_layout(title='Pareto / ABC des familles', height=520, hovermode='x unified')

        for y, label, col in [(80, 'A (80%)', '#10b981'), (95, 'B (95%)', '#f59e0b')]:
            fig.add_hline(
                y=y,
                line_width=1,
                line_dash='dot',
                line_color=col,
                annotation_text=label,
                annotation_position='top right',
                secondary_y=True,
            )

        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_pareto_abc error: {e}")
        return None


def create_pareto_abc_animated_by_month(
    df_final: pd.DataFrame,
    time_col: str = 'Month',
    top_n: int = 25,
) -> str | None:
    """Pareto/ABC animé par mois.

    Construit une animation (frames) où chaque frame représente un mois.
    X = rang (1..N), barres = CA des familles triées, ligne = cumul %.
    """
    if df_final is None or len(df_final) == 0:
        return None
    required = {'Famille', 'Montant', time_col}
    if not required.issubset(set(df_final.columns)):
        return None

    try:
        base = df_final[[time_col, 'Famille', 'Montant']].copy()
        base[time_col] = base[time_col].astype(str)
        base['Famille'] = base['Famille'].astype(str)
        base['Montant'] = pd.to_numeric(base['Montant'], errors='coerce').fillna(0)

        periods = _sorted_periods(base[time_col].dropna().unique())
        if len(periods) < 2:
            return None

        def build_month_pareto(period: str) -> pd.DataFrame:
            sub = base[base[time_col] == period]
            if sub.empty:
                return pd.DataFrame(columns=['Rang', 'Famille', 'CA_Total', 'Part_Pct', 'Part_Cumul_Pct', 'Classe_ABC'])

            fam = sub.groupby('Famille', sort=False)['Montant'].sum().sort_values(ascending=False)
            if fam.empty:
                return pd.DataFrame(columns=['Rang', 'Famille', 'CA_Total', 'Part_Pct', 'Part_Cumul_Pct', 'Classe_ABC'])

            if top_n and len(fam) > top_n:
                top = fam.head(top_n)
                other_sum = float(fam.iloc[top_n:].sum())
                fam = pd.concat([top, pd.Series({'Autres': other_sum})])

            df = fam.reset_index()
            df.columns = ['Famille', 'CA_Total']
            df['CA_Total'] = pd.to_numeric(df['CA_Total'], errors='coerce').fillna(0)
            total = float(df['CA_Total'].sum())
            df['Part_Pct'] = (df['CA_Total'] / total * 100.0) if total > 0 else 0.0
            df['Part_Cumul_Pct'] = df['Part_Pct'].cumsum()
            df['Rang'] = range(1, len(df) + 1)

            def _classe_abc(cumul: float) -> str:
                if pd.isna(cumul):
                    return 'C'
                if cumul <= 80:
                    return 'A'
                if cumul <= 95:
                    return 'B'
                return 'C'

            df['Classe_ABC'] = df['Part_Cumul_Pct'].apply(_classe_abc)
            return df[['Rang', 'Famille', 'CA_Total', 'Part_Pct', 'Part_Cumul_Pct', 'Classe_ABC']]

        first_period = periods[0]
        first_df = build_month_pareto(first_period)
        if first_df.empty:
            return None

        color_map = {'A': '#10b981', 'B': '#f59e0b', 'C': '#6b7280'}

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Bar(
                x=first_df['Rang'],
                y=first_df['CA_Total'],
                name='CA',
                marker_color=first_df['Classe_ABC'].map(color_map).fillna('#3b82f6'),
                customdata=first_df[['Famille', 'Classe_ABC', 'Part_Pct']].to_numpy(),
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    'Rang=%{x}<br>'
                    'CA=%{y:,.0f}€<br>'
                    'Part=%{customdata[2]:.2f}%<br>'
                    'ABC=%{customdata[1]}<extra></extra>'
                ),
            ),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=first_df['Rang'],
                y=first_df['Part_Cumul_Pct'],
                name='Cumul (%)',
                mode='lines+markers',
                line=dict(color='#ef4444', width=3),
                customdata=first_df[['Famille']].to_numpy(),
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>'
                    'Rang=%{x}<br>'
                    'Cumul=%{y:.1f}%<extra></extra>'
                ),
            ),
            secondary_y=True,
        )

        frames = []
        for p in periods:
            dfp = build_month_pareto(p)
            if dfp.empty:
                continue
            frames.append(
                go.Frame(
                    name=str(p),
                    data=[
                        go.Bar(
                            x=dfp['Rang'],
                            y=dfp['CA_Total'],
                            marker_color=dfp['Classe_ABC'].map(color_map).fillna('#3b82f6'),
                            customdata=dfp[['Famille', 'Classe_ABC', 'Part_Pct']].to_numpy(),
                        ),
                        go.Scatter(
                            x=dfp['Rang'],
                            y=dfp['Part_Cumul_Pct'],
                            customdata=dfp[['Famille']].to_numpy(),
                        ),
                    ],
                    layout=go.Layout(title_text=f"Pareto / ABC des familles — {p}"),
                )
            )

        if len(frames) < 2:
            return None

        fig.frames = frames

        # Slider + play/pause
        steps = [
            {
                'args': [[f.name], {'frame': {'duration': 400, 'redraw': True}, 'mode': 'immediate', 'transition': {'duration': 200}}],
                'label': f.name,
                'method': 'animate',
            }
            for f in frames
        ]

        fig.update_layout(
            title=f"Pareto / ABC des familles — {first_period}",
            height=560,
            hovermode='x unified',
            xaxis_title='Rang (familles triées par CA)',
            yaxis_title='CA (€)',
            yaxis2_title='Cumul (%)',
            yaxis2=dict(range=[0, 105]),
            updatemenus=[
                {
                    'type': 'buttons',
                    'direction': 'left',
                    'x': 0.0,
                    'y': 1.15,
                    'showactive': False,
                    'buttons': [
                        {
                            'label': 'Play',
                            'method': 'animate',
                            'args': [None, {'frame': {'duration': 500, 'redraw': True}, 'fromcurrent': True, 'transition': {'duration': 200}}],
                        },
                        {
                            'label': 'Pause',
                            'method': 'animate',
                            'args': [[None], {'frame': {'duration': 0, 'redraw': False}, 'mode': 'immediate', 'transition': {'duration': 0}}],
                        },
                    ],
                }
            ],
            sliders=[
                {
                    'active': 0,
                    'x': 0.05,
                    'y': -0.06,
                    'len': 0.9,
                    'currentvalue': {'prefix': 'Mois: '},
                    'pad': {'t': 20, 'b': 10},
                    'steps': steps,
                }
            ],
        )

        for y, label, col in [(80, 'A (80%)', '#10b981'), (95, 'B (95%)', '#f59e0b')]:
            fig.add_hline(
                y=y,
                line_width=1,
                line_dash='dot',
                line_color=col,
                annotation_text=label,
                annotation_position='top right',
                secondary_y=True,
            )

        return _to_html(fig)

    except Exception as e:
        print(f"viz_products.create_pareto_abc_animated_by_month error: {e}")
        return None


def _animation_controls(periods: list[str], prefix: str = 'Mois: '):
    steps = [
        {
            'args': [[p], {'frame': {'duration': 450, 'redraw': True}, 'mode': 'immediate', 'transition': {'duration': 200}}],
            'label': str(p),
            'method': 'animate',
        }
        for p in periods
    ]

    updatemenus = [
        {
            'type': 'buttons',
            'direction': 'left',
            'x': 0.0,
            'y': 1.12,
            'showactive': False,
            'buttons': [
                {
                    'label': 'Play',
                    'method': 'animate',
                    'args': [None, {'frame': {'duration': 500, 'redraw': True}, 'fromcurrent': True, 'transition': {'duration': 200}}],
                },
                {
                    'label': 'Pause',
                    'method': 'animate',
                    'args': [[None], {'frame': {'duration': 0, 'redraw': False}, 'mode': 'immediate', 'transition': {'duration': 0}}],
                },
            ],
        }
    ]

    sliders = [
        {
            'active': 0,
            'x': 0.05,
            'y': -0.08,
            'len': 0.9,
            'currentvalue': {'prefix': prefix},
            'pad': {'t': 20, 'b': 10},
            'steps': steps,
        }
    ]

    return updatemenus, sliders


def create_top_bar_animated_by_month(
    df_final: pd.DataFrame,
    metric: str,
    title: str,
    time_col: str = 'Month',
    top_n: int = 15,
) -> str | None:
    """Barres horizontales animées (par mois) pour un indicateur famille."""
    if df_final is None or len(df_final) == 0:
        return None
    required = {'Famille', time_col}
    if not required.issubset(set(df_final.columns)):
        return None

    amount_col = 'Montant' if 'Montant' in df_final.columns else None
    qty_col = 'Quantité' if 'Quantité' in df_final.columns else None

    if metric == 'CA_Total' and not amount_col:
        return None
    if metric == 'Qty_Total' and not qty_col:
        return None
    if metric == 'PU_Pondere' and (not amount_col or not qty_col):
        return None

    try:
        base_cols = [time_col, 'Famille'] + ([amount_col] if amount_col else []) + ([qty_col] if qty_col else [])
        base = df_final[base_cols].copy()
        base[time_col] = base[time_col].astype(str)
        base['Famille'] = base['Famille'].astype(str)
        if amount_col:
            base[amount_col] = pd.to_numeric(base[amount_col], errors='coerce').fillna(0)
        if qty_col:
            base[qty_col] = pd.to_numeric(base[qty_col], errors='coerce').fillna(0)

        periods = _sorted_periods(base[time_col].dropna().unique())
        if len(periods) < 2:
            return None

        g = base.groupby([time_col, 'Famille'], sort=False).agg(
            CA_Total=(amount_col, 'sum') if amount_col else (amount_col, 'sum'),
            Qty_Total=(qty_col, 'sum') if qty_col else (qty_col, 'sum'),
        ).reset_index()

        if metric == 'PU_Pondere':
            g['PU_Pondere'] = g.apply(
                lambda r: (float(r['CA_Total']) / float(r['Qty_Total'])) if float(r['Qty_Total'] or 0) > 0 else 0.0,
                axis=1,
            )

        # Top familles globales (axes stables)
        fam_totals = g.groupby('Famille')[metric].sum().sort_values(ascending=False)
        fams = fam_totals.head(top_n).index.astype(str).tolist()
        if not fams:
            return None

        # Table période × famille (valeurs manquantes -> 0)
        pivot = g[g['Famille'].isin(fams)].pivot_table(index=time_col, columns='Famille', values=metric, aggfunc='sum', fill_value=0)
        for f in fams:
            if f not in pivot.columns:
                pivot[f] = 0
        pivot = pivot.reindex(index=[str(p) for p in periods]).fillna(0)

        max_x = float(pd.to_numeric(pivot.values.ravel(), errors='coerce').max()) if pivot.size else 0.0
        max_x = max_x if max_x > 0 else 1.0

        first = str(periods[0])
        x0 = pivot.loc[first, fams].values.tolist() if first in pivot.index else [0] * len(fams)

        fig = go.Figure(
            data=[
                go.Bar(
                    y=fams,
                    x=x0,
                    orientation='h',
                    marker_color='#3b82f6',
                    hovertemplate='<b>%{y}</b><br>%{x}<extra></extra>',
                )
            ]
        )

        frames = []
        for p in periods:
            ps = str(p)
            if ps not in pivot.index:
                continue
            frames.append(
                go.Frame(
                    name=ps,
                    data=[go.Bar(y=fams, x=pivot.loc[ps, fams].values.tolist())],
                    layout=go.Layout(title_text=f"{title} — {ps}"),
                )
            )
        if len(frames) < 2:
            return None

        fig.frames = frames
        updatemenus, sliders = _animation_controls([f.name for f in frames], prefix='Mois: ')
        fig.update_layout(
            title=f"{title} — {first}",
            height=520,
            xaxis_title=metric,
            yaxis_title='Famille',
            yaxis=dict(autorange='reversed'),
            xaxis=dict(range=[0, max_x * 1.08]),
            updatemenus=updatemenus,
            sliders=sliders,
        )

        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_top_bar_animated_by_month({metric}) error: {e}")
        return None


def create_bubble_value_volume_animated_by_month(
    df_final: pd.DataFrame,
    time_col: str = 'Month',
    top_n: int = 25,
) -> str | None:
    """Bubble animé par mois: x=Qty, y=PU, size=CA, color=ABC."""
    if df_final is None or len(df_final) == 0:
        return None
    required = {'Famille', 'Montant', 'Quantité', time_col}
    if not required.issubset(set(df_final.columns)):
        return None

    try:
        base = df_final[[time_col, 'Famille', 'Montant', 'Quantité']].copy()
        base[time_col] = base[time_col].astype(str)
        base['Famille'] = base['Famille'].astype(str)
        base['Montant'] = pd.to_numeric(base['Montant'], errors='coerce').fillna(0)
        base['Quantité'] = pd.to_numeric(base['Quantité'], errors='coerce').fillna(0)

        periods = _sorted_periods(base[time_col].dropna().unique())
        if len(periods) < 2:
            return None

        g = base.groupby([time_col, 'Famille'], sort=False).agg(CA_Total=('Montant', 'sum'), Qty_Total=('Quantité', 'sum')).reset_index()
        g['PU_Pondere'] = g.apply(lambda r: (float(r['CA_Total']) / float(r['Qty_Total'])) if float(r['Qty_Total'] or 0) > 0 else 0.0, axis=1)

        fams = g.groupby('Famille')['CA_Total'].sum().sort_values(ascending=False).head(top_n).index.astype(str).tolist()
        if not fams:
            return None

        # ABC par mois sur toutes les familles (classes stables par frame)
        def abc_map_for(period: str) -> dict[str, str]:
            sub = g[g[time_col].astype(str) == period]
            if sub.empty:
                return {}
            fam = sub.groupby('Famille')['CA_Total'].sum().sort_values(ascending=False)
            total = float(fam.sum()) if float(fam.sum()) else 0.0
            if total <= 0:
                return {}
            part = fam / total * 100.0
            cumul = part.cumsum()
            out = {}
            for fam_name, c in cumul.items():
                if c <= 80:
                    out[str(fam_name)] = 'A'
                elif c <= 95:
                    out[str(fam_name)] = 'B'
                else:
                    out[str(fam_name)] = 'C'
            return out

        color_map = {'A': '#10b981', 'B': '#f59e0b', 'C': '#6b7280'}

        # Matrices période × famille
        pvt_ca = g[g['Famille'].isin(fams)].pivot_table(index=time_col, columns='Famille', values='CA_Total', aggfunc='sum', fill_value=0)
        pvt_qty = g[g['Famille'].isin(fams)].pivot_table(index=time_col, columns='Famille', values='Qty_Total', aggfunc='sum', fill_value=0)
        pvt_pu = g[g['Famille'].isin(fams)].pivot_table(index=time_col, columns='Famille', values='PU_Pondere', aggfunc='mean', fill_value=0)
        for f in fams:
            if f not in pvt_ca.columns:
                pvt_ca[f] = 0
            if f not in pvt_qty.columns:
                pvt_qty[f] = 0
            if f not in pvt_pu.columns:
                pvt_pu[f] = 0
        pvt_ca = pvt_ca.reindex(index=[str(p) for p in periods]).fillna(0)
        pvt_qty = pvt_qty.reindex(index=[str(p) for p in periods]).fillna(0)
        pvt_pu = pvt_pu.reindex(index=[str(p) for p in periods]).fillna(0)

        max_ca = float(pd.to_numeric(pvt_ca.values.ravel(), errors='coerce').max()) if pvt_ca.size else 0.0
        max_ca = max_ca if max_ca > 0 else 1.0

        def sizes_for(ca_values: list[float]) -> list[float]:
            s = pd.to_numeric(pd.Series(ca_values), errors='coerce').fillna(0).clip(lower=0)
            return ((s / max_ca) * 40 + 10).tolist()

        first = str(periods[0])
        ca0 = pvt_ca.loc[first, fams].values.tolist() if first in pvt_ca.index else [0] * len(fams)
        qty0 = pvt_qty.loc[first, fams].values.tolist() if first in pvt_qty.index else [0] * len(fams)
        pu0 = pvt_pu.loc[first, fams].values.tolist() if first in pvt_pu.index else [0] * len(fams)
        abc0 = abc_map_for(first)
        col0 = [color_map.get(abc0.get(f, 'C'), '#3b82f6') for f in fams]

        custom0 = pd.DataFrame({'Famille': fams, 'CA': ca0, 'ABC': [abc0.get(f, 'C') for f in fams]}).to_numpy()

        fig = go.Figure(
            data=[
                go.Scatter(
                    x=qty0,
                    y=pu0,
                    mode='markers',
                    text=fams,
                    marker=dict(
                        size=sizes_for(ca0),
                        color=col0,
                        opacity=0.85,
                        line=dict(width=0.5, color='rgba(255,255,255,0.4)'),
                    ),
                    customdata=custom0,
                    hovertemplate=(
                        '<b>%{customdata[0]}</b><br>'
                        'Qty=%{x:,.0f}<br>'
                        'PU=%{y:,.2f}€<br>'
                        'CA=%{customdata[1]:,.0f}€<br>'
                        'ABC=%{customdata[2]}<extra></extra>'
                    ),
                )
            ]
        )

        frames = []
        for p in periods:
            ps = str(p)
            if ps not in pvt_ca.index:
                continue
            ca = pvt_ca.loc[ps, fams].values.tolist()
            qty = pvt_qty.loc[ps, fams].values.tolist()
            pu = pvt_pu.loc[ps, fams].values.tolist()
            abc = abc_map_for(ps)
            cols = [color_map.get(abc.get(f, 'C'), '#3b82f6') for f in fams]
            custom = pd.DataFrame({'Famille': fams, 'CA': ca, 'ABC': [abc.get(f, 'C') for f in fams]}).to_numpy()
            frames.append(
                go.Frame(
                    name=ps,
                    data=[
                        go.Scatter(
                            x=qty,
                            y=pu,
                            marker=dict(size=sizes_for(ca), color=cols),
                            customdata=custom,
                            text=fams,
                        )
                    ],
                    layout=go.Layout(title_text=f"Volume / Valeur (taille=CA, couleur=ABC) — {ps}"),
                )
            )
        if len(frames) < 2:
            return None

        fig.frames = frames
        updatemenus, sliders = _animation_controls([f.name for f in frames], prefix='Mois: ')
        fig.update_layout(
            title=f"Volume / Valeur (taille=CA, couleur=ABC) — {first}",
            height=560,
            xaxis_title='Quantité totale',
            yaxis_title='PU pondéré (€)',
            updatemenus=updatemenus,
            sliders=sliders,
        )

        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_bubble_value_volume_animated_by_month error: {e}")
        return None


def create_heatmap_family_country_animated_by_month(
    df_final: pd.DataFrame,
    time_col: str = 'Month',
    top_families: int = 12,
    top_countries: int = 10,
) -> str | None:
    """Heatmap CA familles×pays animé par mois (axes fixes sur top globaux)."""
    if df_final is None or len(df_final) == 0:
        return None

    amount_col = 'Montant' if 'Montant' in df_final.columns else None
    if not amount_col:
        return None

    if 'Famille' not in df_final.columns or time_col not in df_final.columns:
        return None

    country_col = 'Country' if 'Country' in df_final.columns else ('Pays' if 'Pays' in df_final.columns else None)
    if not country_col:
        return None

    try:
        base = df_final[[time_col, 'Famille', country_col, amount_col]].copy()
        base[time_col] = base[time_col].astype(str)
        base['Famille'] = base['Famille'].astype(str)
        base[country_col] = base[country_col].astype(str)
        base[amount_col] = pd.to_numeric(base[amount_col], errors='coerce').fillna(0)

        periods = _sorted_periods(base[time_col].dropna().unique())
        if len(periods) < 2:
            return None

        fc = (
            base.groupby([time_col, 'Famille', country_col], sort=False)[amount_col]
            .sum()
            .rename('CA')
            .reset_index()
        )
        top_f = fc.groupby('Famille')['CA'].sum().sort_values(ascending=False).head(top_families).index.astype(str).tolist()
        top_c = fc.groupby(country_col)['CA'].sum().sort_values(ascending=False).head(top_countries).index.astype(str).tolist()
        if not top_f or not top_c:
            return None

        def matrix_for(period: str) -> pd.DataFrame:
            sub = fc[fc[time_col].astype(str) == period]
            if sub.empty:
                return pd.DataFrame(0, index=top_f, columns=top_c)
            sub = sub[sub['Famille'].isin(top_f) & sub[country_col].isin(top_c)]
            if sub.empty:
                return pd.DataFrame(0, index=top_f, columns=top_c)
            pivot = sub.pivot_table(index='Famille', columns=country_col, values='CA', aggfunc='sum', fill_value=0)
            pivot = pivot.reindex(index=top_f, columns=top_c).fillna(0)
            return pivot

        first = str(periods[0])
        z0 = matrix_for(first)
        zmax = float(pd.to_numeric(z0.values.ravel(), errors='coerce').max()) if z0.size else 0.0
        # zmax global (pour échelle fixe)
        for p in periods[1:]:
            zp = matrix_for(str(p))
            if zp.size:
                zmax = max(zmax, float(pd.to_numeric(zp.values.ravel(), errors='coerce').max()))
        zmax = zmax if zmax > 0 else 1.0

        fig = go.Figure(
            data=[
                go.Heatmap(
                    z=z0.values,
                    x=[str(c) for c in z0.columns],
                    y=[str(r) for r in z0.index],
                    zmin=0,
                    zmax=zmax,
                    colorscale='Blues',
                    hovertemplate='Famille=%{y}<br>Pays=%{x}<br>CA=%{z:,.0f}€<extra></extra>',
                )
            ]
        )

        frames = []
        for p in periods:
            ps = str(p)
            zp = matrix_for(ps)
            frames.append(
                go.Frame(
                    name=ps,
                    data=[go.Heatmap(z=zp.values, x=[str(c) for c in zp.columns], y=[str(r) for r in zp.index])],
                    layout=go.Layout(title_text=f"Heatmap CA (top familles x top pays) — {ps}"),
                )
            )
        if len(frames) < 2:
            return None

        fig.frames = frames
        updatemenus, sliders = _animation_controls([f.name for f in frames], prefix='Mois: ')
        fig.update_layout(
            title=f"Heatmap CA (top familles x top pays) — {first}",
            height=560,
            xaxis_title='Pays',
            yaxis_title='Famille',
            updatemenus=updatemenus,
            sliders=sliders,
        )

        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_heatmap_family_country_animated_by_month error: {e}")
        return None


def create_top_bar(stats_famille: pd.DataFrame, metric: str, title: str, top_n: int = 15) -> str | None:
    if not _require_cols(stats_famille, ['Famille', metric]):
        return None
    try:
        df = stats_famille.sort_values(metric, ascending=False).head(top_n)
        fig = go.Figure(
            data=[
                go.Bar(
                    y=df['Famille'].astype(str),
                    x=pd.to_numeric(df[metric], errors='coerce'),
                    orientation='h',
                    marker_color='#3b82f6',
                    hovertemplate='<b>%{y}</b><br>%{x}<extra></extra>',
                )
            ]
        )
        fig.update_layout(title=title, height=520)
        fig.update_yaxes(title_text='Famille', autorange='reversed')
        fig.update_xaxes(title_text=metric)
        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_top_bar({metric}) error: {e}")
        return None


def create_bubble_value_volume(stats_famille: pd.DataFrame) -> str | None:
    """Scatter: x=Qty_Total, y=PU_Pondere, size=CA_Total, color=Classe_ABC."""
    if not _require_cols(stats_famille, ['Famille', 'Qty_Total', 'PU_Pondere', 'CA_Total', 'Classe_ABC']):
        return None
    try:
        df = stats_famille.copy()
        size_raw = pd.to_numeric(df['CA_Total'], errors='coerce').fillna(0).clip(lower=0)
        denom = float(size_raw.max()) if float(size_raw.max()) else 1.0
        size = (size_raw / denom) * 40 + 10

        color_map = {'A': '#10b981', 'B': '#f59e0b', 'C': '#6b7280'}
        colors = df['Classe_ABC'].astype(str).str[0].map(color_map).fillna('#3b82f6')

        fig = go.Figure(
            data=[
                go.Scatter(
                    x=pd.to_numeric(df['Qty_Total'], errors='coerce'),
                    y=pd.to_numeric(df['PU_Pondere'], errors='coerce'),
                    mode='markers',
                    text=df['Famille'].astype(str),
                    marker=dict(
                        size=size,
                        color=colors,
                        opacity=0.85,
                        line=dict(width=0.5, color='rgba(255,255,255,0.4)'),
                    ),
                    customdata=pd.concat(
                        [
                            pd.to_numeric(df['CA_Total'], errors='coerce'),
                            df['Classe_ABC'].astype(str),
                        ],
                        axis=1,
                    ).to_numpy(),
                    hovertemplate=(
                        '<b>%{text}</b><br>'
                        'Qty=%{x:,.0f}<br>'
                        'PU=%{y:,.2f}€<br>'
                        'CA=%{customdata[0]:,.0f}€<br>'
                        'ABC=%{customdata[1]}<br>'
                        '<extra></extra>'
                    ),
                )
            ]
        )
        fig.update_layout(title='Volume / Valeur (taille=CA, couleur=ABC)', height=520)
        fig.update_xaxes(title_text='Quantité totale')
        fig.update_yaxes(title_text='PU pondéré (€)')
        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_bubble_value_volume error: {e}")
        return None


def create_heatmap_family_country(df_final: pd.DataFrame, top_families: int = 12, top_countries: int = 10) -> str | None:
    if df_final is None or len(df_final) == 0 or 'Famille' not in df_final.columns:
        return None

    amount_col = 'Montant' if 'Montant' in df_final.columns else None
    if not amount_col:
        return None

    country_col = 'Country' if 'Country' in df_final.columns else ('Pays' if 'Pays' in df_final.columns else None)
    if not country_col:
        return None

    try:
        fc = (
            df_final.groupby(['Famille', country_col], sort=False)[amount_col]
            .sum()
            .rename('CA')
            .reset_index()
        )
        top_f = fc.groupby('Famille')['CA'].sum().sort_values(ascending=False).head(top_families).index
        top_c = fc.groupby(country_col)['CA'].sum().sort_values(ascending=False).head(top_countries).index
        fc = fc[fc['Famille'].isin(top_f) & fc[country_col].isin(top_c)]
        pivot = fc.pivot_table(index='Famille', columns=country_col, values='CA', aggfunc='sum', fill_value=0)
        pivot = pivot.loc[list(top_f)]

        fig = go.Figure(
            data=[
                go.Heatmap(
                    z=pivot.values,
                    x=pivot.columns.astype(str),
                    y=pivot.index.astype(str),
                    colorscale='Blues',
                    hovertemplate='Famille=%{y}<br>Pays=%{x}<br>CA=%{z:,.0f}€<extra></extra>',
                )
            ]
        )
        fig.update_layout(title='Heatmap CA (top familles x top pays)', height=520)
        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_heatmap_family_country error: {e}")
        return None


def create_evolution(time_series_famille: pd.DataFrame, metric: str, title: str, top_n: int = 5) -> str | None:
    if time_series_famille is None or len(time_series_famille) == 0:
        return None
    if 'Famille' not in time_series_famille.columns or metric not in time_series_famille.columns:
        return None

    time_col = None
    for c in ('Month', 'Fiscal_Quarter', 'Fiscal_Year_Label'):
        if c in time_series_famille.columns:
            time_col = c
            break
    if not time_col:
        return None

    try:
        df = time_series_famille.copy()
        totals = df.groupby('Famille')[metric].sum().sort_values(ascending=False)
        top_fams = totals.head(top_n).index.tolist()

        df['Famille_Group'] = df['Famille'].where(df['Famille'].isin(top_fams), other='Others')
        g = df.groupby([time_col, 'Famille_Group'])[metric].sum().reset_index()
        periods = _sorted_periods(g[time_col].unique())

        # Labels courts pour éviter un axe X illisible (notamment Fiscal_Quarter)
        period_order = [str(p) for p in periods]
        period_order_short = [_short_period_label(p) for p in period_order]
        g['_period_raw'] = g[time_col].astype(str)
        g['_period_label'] = g['_period_raw'].map(_short_period_label)
        g['_period_label'] = pd.Categorical(g['_period_label'], categories=period_order_short, ordered=True)
        g = g.sort_values(['_period_label', 'Famille_Group'])

        fig = go.Figure()
        series_order = top_fams + (['Others'] if 'Others' in set(g['Famille_Group']) else [])
        for fam in series_order:
            sub = g[g['Famille_Group'] == fam]
            fig.add_trace(
                go.Scatter(
                    x=sub['_period_label'].astype(str),
                    y=pd.to_numeric(sub[metric], errors='coerce'),
                    mode='lines+markers',
                    name=str(fam),
                    hovertemplate='<b>%{x}</b><br>%{y:,.2f}<extra></extra>',
                )
            )

        fig.update_layout(
            title=title,
            height=430,
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        )
        fig.update_xaxes(title_text='Période', tickangle=-45, automargin=True)
        fig.update_yaxes(title_text=metric, automargin=True)
        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_evolution({metric}) error: {e}")
        return None


def create_delay_by_family_box(df_processed: pd.DataFrame, top_families: list[str]) -> str | None:
    """Boxplot des Lead_Time_Days par famille (top familles par CA)."""
    if df_processed is None or len(df_processed) == 0 or not top_families:
        return None
    required = {'Famille', 'Lead_Time_Days'}
    if not required.issubset(set(df_processed.columns)):
        return None
    try:
        df = df_processed[df_processed['Famille'].isin(top_families)].copy()
        fig = go.Figure()
        for fam in top_families:
            sub = df[df['Famille'] == fam]
            if sub.empty:
                continue
            fig.add_trace(
                go.Box(
                    y=pd.to_numeric(sub['Lead_Time_Days'], errors='coerce'),
                    name=str(fam),
                    boxmean='sd',
                    marker_color='#3b82f6',
                    hovertemplate='<b>%{x}</b><br>LeadTime=%{y}<extra></extra>',
                )
            )
        fig.update_layout(title='Délais (Lead_Time_Days) - Top familles', height=520)
        fig.update_yaxes(title_text='Jours')
        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_delay_by_family_box error: {e}")
        return None


def create_corr_heatmap(corr_matrix: pd.DataFrame, title: str = 'Corrélations (Spearman)') -> str | None:
    if corr_matrix is None or corr_matrix.empty:
        return None
    try:
        fig = go.Figure(
            data=[
                go.Heatmap(
                    z=corr_matrix.values,
                    x=corr_matrix.columns.astype(str),
                    y=corr_matrix.index.astype(str),
                    zmin=-1,
                    zmax=1,
                    colorscale='RdBu',
                    hovertemplate='%{y} vs %{x}<br>rho=%{z:.2f}<extra></extra>',
                )
            ]
        )
        fig.update_layout(title=title, height=520)
        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_corr_heatmap error: {e}")
        return None


# --- NEW: SKU PU distribution among customers (bubble) ---
def create_sku_pu_distribution_bubble(
    df_final: pd.DataFrame,
    selected_product: str,
    product_col: str,
    time_col: str,
    window_periods: int = 6,
    client_col: str = "Cpt Client",
    qty_col: str = "Quantité",
    amount_col: str = "Montant",
    country_col: str | None = "Country",
    label_top_n: int = 6,          # labels: top CA (recommandé petit)
    label_outliers_n: int = 1,      # + outliers PU/Qty
    bubble_cap_q: float = 0.98,     # cap tailles bulles (98% par défaut)
) -> str | None:
    try:
        import math

        def _log_ticks_125(vmin: float, vmax: float):
            """Ticks log lisibles: 1–2–5 * 10^k couvrant [vmin, vmax]."""
            if vmin <= 0 or vmax <= 0:
                return [], []
            kmin = int(math.floor(math.log10(vmin)))
            kmax = int(math.ceil(math.log10(vmax)))
            vals = []
            for k in range(kmin, kmax + 1):
                for m in (1, 2, 5):
                    vals.append(m * (10 ** k))
            vals = sorted(set(vals))
            vals = [v for v in vals if vmin <= v <= vmax]

            def fmt(v: float) -> str:
                if v >= 1:
                    # 1, 2, 5, 10, 20, 50, 100, ...
                    return f"{v:g}"
                # 0.1, 0.2, 0.5, 0.05, ...
                # garde assez de décimales sans trailing zeros excessifs
                s = f"{v:.6f}".rstrip("0").rstrip(".")
                return s

            return vals, [fmt(v) for v in vals]

        if df_final is None or df_final.empty:
            return None
        if selected_product is None or str(selected_product).strip() == "":
            return None
        if product_col not in df_final.columns or time_col not in df_final.columns:
            return None
        if client_col not in df_final.columns or amount_col not in df_final.columns:
            return None

        d = df_final.copy()
        d[product_col] = d[product_col].astype(str)
        d = d[d[product_col] == str(selected_product)].copy()
        if d.empty:
            return None

        periods_sorted = _sorted_periods(d[time_col].dropna().unique())
        if not periods_sorted:
            return None
        last_periods = periods_sorted[-window_periods:]
        d = d[d[time_col].astype(str).isin([str(p) for p in last_periods])].copy()
        if d.empty:
            return None

        d[amount_col] = pd.to_numeric(d[amount_col], errors="coerce")
        if qty_col in d.columns:
            d[qty_col] = pd.to_numeric(d[qty_col], errors="coerce")
        else:
            d[qty_col] = np.nan

        grp_cols = [client_col]
        if country_col and country_col in d.columns:
            grp_cols.append(country_col)

        g = d.groupby(grp_cols, dropna=False).agg(
            CA=(amount_col, "sum"),
            QTY=(qty_col, "sum"),
        ).reset_index()

        g["PU"] = np.where(g["QTY"] > 0, g["CA"] / g["QTY"], np.nan)

        # Clean log-safety (X et Y en log => strictement positifs)
        g["CA"] = pd.to_numeric(g["CA"], errors="coerce")
        g["QTY"] = pd.to_numeric(g["QTY"], errors="coerce")
        g["PU"] = pd.to_numeric(g["PU"], errors="coerce")
        g = g.replace([np.inf, -np.inf], np.nan).dropna(subset=["CA", "QTY", "PU"])
        g = g[(g["CA"] >= 0) & (g["QTY"] > 0) & (g["PU"] > 0)]
        if g.empty:
            return None

        # Bubble sizing: cap extrêmes pour éviter qu'un "whale" écrase tout
        size_raw = g["CA"].clip(lower=0).fillna(0)
        cap_val = float(size_raw.quantile(bubble_cap_q)) if len(size_raw) else 0.0
        size_for_plot = size_raw.clip(upper=cap_val) if cap_val > 0 else size_raw

        desired_max = 46  # px
        max_ca = float(size_for_plot.max()) if float(size_for_plot.max()) else 1.0
        sizeref = 2.0 * max_ca / (desired_max ** 2)

        # Labels: top CA + outliers (PU haut + QTY haut)
        top_ca = g.nlargest(label_top_n, "CA")
        out_pu_high = g.nlargest(label_outliers_n, "PU")
        out_qty_high = g.nlargest(label_outliers_n, "QTY")
        labels_df = (
            pd.concat([top_ca, out_pu_high, out_qty_high], ignore_index=True)
            .drop_duplicates(subset=grp_cols)
        )

        # Log ticks X (1–2–5)
        pu_min = float(g["PU"].min())
        pu_max = float(g["PU"].max())
        tickvals, ticktext = _log_ticks_125(pu_min, pu_max)

        # Build figure
        fig = go.Figure()

        # Trace 1: points only (lisible)
        fig.add_trace(
            go.Scatter(
                x=g["PU"],
                y=g["QTY"],
                mode="markers",
                text=g[client_col].astype(str),
                customdata=np.stack([size_raw.values], axis=1),  # vrai CA dans hover
                marker=dict(
                    size=size_for_plot,
                    sizemode="area",
                    sizeref=sizeref,
                    sizemin=6,
                    opacity=0.55,
                    line=dict(width=1, color="white"),
                ),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "PU=%{x:,.4g}€<br>"
                    "Qty=%{y:,.4g}<br>"
                    "CA=%{customdata[0]:,.4g}€<br>"
                    "<extra></extra>"
                ),
            )
        )

        # Trace 2: labels (peu nombreux)
        if not labels_df.empty:
            fig.add_trace(
                go.Scatter(
                    x=labels_df["PU"],
                    y=labels_df["QTY"],
                    mode="text",
                    text=labels_df[client_col].astype(str),
                    textposition="top center",
                    textfont=dict(size=10),
                    hoverinfo="skip",
                    cliponaxis=False,
                )
            )

        fig.update_layout(
            title=f"Distribution PU (€) — SKU {selected_product} (fenêtre {len(last_periods)} périodes)",
            height=560,
            margin=dict(l=30, r=20, t=70, b=45),
            template="plotly_white",
            hovermode="closest",
            showlegend=False,
        )

        # Axes
        fig.update_xaxes(
            title_text="PU moyen pondéré (€)",
            type="log",
            tickmode="array" if tickvals else "auto",
            tickvals=tickvals if tickvals else None,
            ticktext=ticktext if tickvals else None,
            showgrid=True,
            zeroline=False,
        )
        fig.update_yaxes(
            title_text="Quantité (sur la fenêtre)",
            type="log",
            tickformat="~s",
            showgrid=True,
            zeroline=False,
        )

        return _to_html(fig)

    except Exception as e:
        print(f"viz_products.create_sku_pu_distribution_bubble error: {e}")
        return None


# --- NEW: Price impact per customer (scatter %ΔPU vs %ΔQty) ---
def create_sku_price_impact_scatter(
    df_final: pd.DataFrame,
    selected_product: str,
    product_col: str,
    time_col: str,
    window_periods: int = 6,
    client_col: str = "Cpt Client",
    qty_col: str = "Quantité",
    amount_col: str = "Montant",
) -> str | None:
    try:
        if df_final is None or df_final.empty:
            return None
        if not selected_product:
            return None
        if product_col not in df_final.columns or time_col not in df_final.columns:
            return None
        if client_col not in df_final.columns or amount_col not in df_final.columns:
            return None
        if qty_col not in df_final.columns:
            return None

        d = df_final.copy()
        d[product_col] = d[product_col].astype(str)
        d = d[d[product_col] == str(selected_product)].copy()
        if d.empty:
            return None

        periods_sorted = _sorted_periods(d[time_col].dropna().unique())
        if len(periods_sorted) < 2 * window_periods:
            # pas assez d'historique pour last6 vs prev6
            return None

        last = [str(p) for p in periods_sorted[-window_periods:]]
        prev = [str(p) for p in periods_sorted[-2 * window_periods : -window_periods]]

        d[amount_col] = pd.to_numeric(d[amount_col], errors="coerce")
        d[qty_col] = pd.to_numeric(d[qty_col], errors="coerce")

        def _agg_for(period_list: list[str]) -> pd.DataFrame:
            x = d[d[time_col].astype(str).isin(period_list)].copy()
            g = x.groupby(client_col, dropna=False).agg(
                CA=(amount_col, "sum"),
                QTY=(qty_col, "sum"),
            ).reset_index()
            g["PU"] = np.where(g["QTY"] > 0, g["CA"] / g["QTY"], np.nan)
            return g

        g_last = _agg_for(last).rename(columns={"CA": "CA_last", "QTY": "QTY_last", "PU": "PU_last"})
        g_prev = _agg_for(prev).rename(columns={"CA": "CA_prev", "QTY": "QTY_prev", "PU": "PU_prev"})

        m = g_prev.merge(g_last, on=client_col, how="outer")

        m["dPU_pct"] = (m["PU_last"] - m["PU_prev"]) / m["PU_prev"]
        m["dQTY_pct"] = (m["QTY_last"] - m["QTY_prev"]) / m["QTY_prev"]
        m = m.replace([np.inf, -np.inf], np.nan).dropna(subset=["dPU_pct", "dQTY_pct"])
        
        # Filtrer les clients avec variation de prix nulle ou quasi-nulle (< 0.1%)
        m = m[np.abs(m["dPU_pct"]) >= 0.001]

        if m.empty:
            return None

        # size by CA_prev
        size_raw = pd.to_numeric(m["CA_prev"], errors="coerce").fillna(0).clip(lower=0)
        denom = float(size_raw.max()) if float(size_raw.max()) else 1.0
        size = (size_raw / denom) * 40 + 10

        fig = go.Figure(
            data=[
                go.Scatter(
                    x=(m["dPU_pct"] * 100.0),
                    y=(m["dQTY_pct"] * 100.0),
                    mode="markers+text",
                    text=m[client_col].astype(str),
                    textposition="top center",
                    textfont=dict(size=9),
                    marker=dict(size=size, opacity=0.7, line=dict(width=1, color='white')),
                    customdata=np.stack([m["CA_prev"].fillna(0).values, m[client_col].astype(str)], axis=1),
                    hovertemplate=(
                        "<b>%{customdata[1]}</b><br>"
                        "ΔPU=%{x:.1f}%<br>"
                        "ΔQty=%{y:.1f}%<br>"
                        "CA prev=%{customdata[0]:,.0f}€<br>"
                        "<extra></extra>"
                    ),
                )
            ]
        )
        fig.update_layout(
            title=f"Impact prix → volume (clients) — SKU {selected_product} (last{window_periods} vs prev{window_periods})",
            height=520,
            margin=dict(l=20, r=20, t=60, b=40),
        )
        fig.update_xaxes(title_text="%ΔPU")
        fig.update_yaxes(title_text="%ΔQuantité")

        return _to_html(fig)
    except Exception as e:
        print(f"viz_products.create_sku_price_impact_scatter error: {e}")
        return None


# --- Compat: alias de noms historiques ---
def create_pareto_abc_chart(stats_famille: pd.DataFrame) -> str | None:
    return create_pareto_abc(stats_famille)


def create_top_ca(stats_famille: pd.DataFrame) -> str | None:
    return create_top_bar(stats_famille, 'CA_Total', 'Top 15 familles - CA', top_n=15)


def create_top_qty(stats_famille: pd.DataFrame) -> str | None:
    return create_top_bar(stats_famille, 'Qty_Total', 'Top 15 familles - Quantité', top_n=15)


def create_top_pu(stats_famille: pd.DataFrame) -> str | None:
    return create_top_bar(stats_famille, 'PU_Pondere', 'Top 15 familles - PU pondéré', top_n=15)
