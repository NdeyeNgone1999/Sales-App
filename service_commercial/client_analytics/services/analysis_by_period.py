"""
Service pour le sous-onglet ANALYSE PAR PÉRIODES
Génère les statistiques complètes pour une période donnée (mois, trimestre, année fiscale)
AUTONOME - Ne dépend d'aucun autre fichier de services
"""

import pandas as pd
import numpy as np
from scipy import stats
from .visualizations import viz_by_period


def analyze_correlations_detailed(df, variables):
    """
    Génère une analyse détaillée des corrélations avec interprétations business

    Args:
        df: DataFrame
        variables: Liste des variables numériques

    Returns:
        HTML avec l'analyse des corrélations
    """
    try:
        corr_matrix = df[variables].corr()

        html = "<div class='correlation-analysis'>"
        html += "<h6><strong>📊 Corrélations Significatives Détectées :</strong></h6>"
        html += "<ul>"

        # Analyser les paires de corrélations
        for i, var1 in enumerate(variables):
            for j, var2 in enumerate(variables):
                if i < j:  # Éviter les doublons et la diagonale
                    corr_value = corr_matrix.loc[var1, var2]

                    # Ne garder que les corrélations significatives (|r| > 0.3)
                    if abs(corr_value) > 0.3:
                        strength = ""
                        interpretation = ""

                        if abs(corr_value) > 0.7:
                            strength = "forte"
                            color = "danger"
                        elif abs(corr_value) > 0.5:
                            strength = "modérée"
                            color = "warning"
                        else:
                            strength = "faible à modérée"
                            color = "info"

                        direction = "positive" if corr_value > 0 else "négative"

                        # Interprétations business spécifiques
                        if var1 == "Montant" and var2 == "Quantité":
                            if corr_value > 0.5:
                                interpretation = "Les commandes avec plus d'unités génèrent des montants plus élevés."
                            else:
                                interpretation = "Corrélation faible : certains produits à forte valeur unitaire génèrent du CA même avec peu d'unités."
                        elif var1 == "Montant" and var2 == "PU Net":
                            if corr_value > 0.5:
                                interpretation = "Les produits à prix élevé contribuent significativement au CA."
                            else:
                                interpretation = "Le CA n'est pas uniquement dû aux prix élevés, le volume joue aussi un rôle important."
                        elif var1 == "Quantité" and var2 == "PU Net":
                            if corr_value < -0.3:
                                interpretation = "Les produits à bas prix sont achetés en plus grande quantité."
                            else:
                                interpretation = "Pas de relation claire entre prix et quantité commandée."
                        elif "Lead_Time_Days" in [var1, var2] and "Montant" in [
                            var1,
                            var2,
                        ]:
                            if abs(corr_value) > 0.3:
                                interpretation = f"Lien {'positif' if corr_value > 0 else 'négatif'} entre délai de livraison et montant des commandes."
                        elif "Lead_Time_Days" in [var1, var2] and "Quantité" in [
                            var1,
                            var2,
                        ]:
                            if abs(corr_value) > 0.3:
                                interpretation = f"Lien {'positif' if corr_value > 0 else 'négatif'} entre délai de livraison et volume commandé."
                        elif "Delai_Prev_Days" in [var1, var2] and "Lead_Time_Days" in [
                            var1,
                            var2,
                        ]:
                            if corr_value > 0.5:
                                interpretation = "Les délais prévisionnels correspondent bien aux délais réels."
                            elif corr_value < 0:
                                interpretation = "Les délais prévisionnels ne correspondent pas aux délais réels."
                        elif "Lead_Time_Deviation_Days" in [var1, var2]:
                            if abs(corr_value) > 0.3:
                                interpretation = f"L'écart aux délais prévisionnels est corrélé avec {var1 if var1 != 'Lead_Time_Deviation_Days' else var2}."

                        html += f"<li><span class='badge bg-{color}'>{var1} ↔ {var2}</span>: "
                        html += f"Corrélation <strong>{direction} {strength}</strong> (r = {corr_value:.3f})<br>"
                        if interpretation:
                            html += f"<em class='text-muted'>→ {interpretation}</em>"
                        html += "</li>"

        html += "</ul>"
        html += "</div>"

        return html
    except Exception as e:
        return "<p class='text-danger'>Erreur lors de l'analyse des corrélations</p>"


def generate_deep_synthesis(df, kpis, variables_num):
    """
    Génère une synthèse approfondie de l'analyse mensuelle

    Args:
        df: DataFrame nettoyé
        kpis: Dictionnaire des KPIs
        variables_num: Liste des variables numériques

    Returns:
        HTML avec la synthèse détaillée
    """
    try:
        html = "<div class='synthesis'>"

        # 1. Vue d'ensemble
        html += "<h6><strong>📈 Vue d'Ensemble de la Performance</strong></h6>"
        html += "<div class='alert alert-light border'>"
        html += f"<p>Sur la période analysée, nous observons <strong>{kpis.get('total_transactions', 'N/A')} transactions</strong> "
        html += f"générées par <strong>{kpis.get('nb_clients', 'N/A')} clients</strong> distincts, "
        html += f"pour un chiffre d'affaires total de <strong>{kpis.get('ca_total', 'N/A')}</strong>.</p>"

        panier_moyen = df["Montant"].mean() if "Montant" in df.columns else 0
        html += (
            f"<p>Le panier moyen s'établit à <strong>{panier_moyen:,.2f} €</strong>. "
        )

        # Analyser la distribution du panier moyen
        if "Montant" in df.columns:
            median = df["Montant"].median()
            if panier_moyen > median * 1.2:
                html += "La moyenne est significativement supérieure à la médiane, indiquant la présence de quelques commandes de très haute valeur qui tirent la moyenne vers le haut.</p>"
            else:
                html += "La moyenne est proche de la médiane, suggérant une distribution relativement homogène des montants.</p>"

        html += "</div>"

        # 2. Qualité des données et normalité
        html += "<h6 class='mt-4'><strong>📊 Caractéristiques Statistiques des Données</strong></h6>"
        html += "<div class='alert alert-info border'>"

        # Tests de normalité
        normality_results = {}
        for var in variables_num:
            if var in df.columns:
                data = df[var].dropna()
                if len(data) > 3:
                    stat, p_value = stats.shapiro(
                        data[:5000]
                    )  # Limite à 5000 échantillons
                    normality_results[var] = p_value

        html += "<p><strong>Distribution des données :</strong></p>"
        html += "<ul>"
        non_normal = [var for var, p in normality_results.items() if p < 0.05]
        if len(non_normal) == len(normality_results):
            html += "<li>✓ Toutes les variables présentent une distribution <strong>non normale</strong> (test de Shapiro-Wilk, p < 0.05). "
            html += "Ceci est attendu dans les données commerciales qui présentent souvent des distributions asymétriques avec des valeurs extrêmes.</li>"
        else:
            html += f"<li>✓ {len(non_normal)}/{len(normality_results)} variables ont une distribution non normale.</li>"
        html += "</ul>"

        # Valeurs aberrantes
        html += "<p><strong>Valeurs aberrantes :</strong></p>"
        html += "<ul>"
        for var in variables_num:
            if var in df.columns:
                Q1 = df[var].quantile(0.25)
                Q3 = df[var].quantile(0.75)
                IQR = Q3 - Q1
                outliers = df[(df[var] < Q1 - 1.5 * IQR) | (df[var] > Q3 + 1.5 * IQR)]
                pct_outliers = (len(outliers) / len(df)) * 100

                html += (
                    f"<li><strong>{var}</strong> : {len(outliers):,} outliers détectés "
                )
                html += f"({pct_outliers:.1f}% des données)"

                if pct_outliers > 10:
                    html += " - <span class='text-warning'>⚠️ Proportion élevée, nécessite une attention particulière</span>"
                elif pct_outliers > 5:
                    html += " - <span class='text-info'>ℹ️ Proportion modérée, à surveiller</span>"
                else:
                    html += " - <span class='text-success'>✓ Proportion normale</span>"

                html += "</li>"
        html += "</ul>"
        html += "</div>"

        # 3. Insights business
        html += "<h6 class='mt-4'><strong>💼 Insights Business</strong></h6>"
        html += "<div class='alert alert-success border'>"
        html += "<ul>"

        # Analyser la variabilité
        if "Montant" in df.columns:
            cv = (df["Montant"].std() / df["Montant"].mean()) * 100
            html += f"<li><strong>Variabilité des montants</strong> : Coefficient de variation = {cv:.1f}%. "
            if cv > 100:
                html += "Très forte dispersion des montants, indiquant une grande diversité dans les types de transactions.</li>"
            elif cv > 50:
                html += "Dispersion modérée, typique d'un portefeuille client diversifié.</li>"
            else:
                html += "Faible dispersion, les transactions sont relativement homogènes.</li>"

        # Concentration du CA
        if "Cpt Client" in df.columns and "Montant" in df.columns:
            ca_by_client = (
                df.groupby("Cpt Client")["Montant"].sum().sort_values(ascending=False)
            )
            top_20_pct_ca = (
                ca_by_client.head(int(len(ca_by_client) * 0.2)).sum()
                / ca_by_client.sum()
            ) * 100
            html += f"<li><strong>Concentration client</strong> : Les 20% de clients les plus importants représentent {top_20_pct_ca:.1f}% du CA. "

            if top_20_pct_ca > 80:
                html += "<span class='text-danger'>⚠️ Forte concentration (principe de Pareto dépassé), risque de dépendance élevé.</span></li>"
            elif top_20_pct_ca > 60:
                html += "<span class='text-warning'>Concentration modérée, conforme au principe de Pareto.</span></li>"
            else:
                html += "<span class='text-success'>CA bien réparti entre les clients.</span></li>"

        # Analyse géographique si disponible
        if "Country" in df.columns and "Montant" in df.columns:
            ca_by_country = (
                df.groupby("Country")["Montant"].sum().sort_values(ascending=False)
            )
            top_country_pct = (ca_by_country.iloc[0] / ca_by_country.sum()) * 100
            html += f"<li><strong>Concentration géographique</strong> : Le pays principal représente {top_country_pct:.1f}% du CA. "

            if top_country_pct > 50:
                html += "⚠️ Forte dépendance à un seul marché.</li>"
            else:
                html += "✓ Bonne diversification géographique.</li>"

        html += "</ul>"
        html += "</div>"

        # 4. Points d'attention
        html += "<h6 class='mt-4'><strong>⚠️ Points d'Attention</strong></h6>"
        html += "<div class='alert alert-danger border'>"
        html += "<ul>"

        # Vérifier les valeurs nulles
        null_counts = df[variables_num].isnull().sum()
        if null_counts.sum() > 0:
            html += "<li><strong>Données manquantes</strong> : "
            for var, count in null_counts[null_counts > 0].items():
                pct = (count / len(df)) * 100
                html += f"{var} : {count} valeurs manquantes ({pct:.1f}%). "
            html += "</li>"

        # Vérifier les valeurs négatives
        for var in variables_num:
            if var in df.columns:
                neg_count = (df[var] < 0).sum()
                if neg_count > 0:
                    html += f"<li><strong>Valeurs négatives dans {var}</strong> : {neg_count} valeurs négatives détectées. Vérifiez s'il s'agit d'avoirs ou d'erreurs de saisie.</li>"

        html += "<li><strong>Qualité des analyses</strong> : Les distributions non normales indiquent que certains tests statistiques classiques (t-test, ANOVA) ne sont pas appropriés. Les tests non-paramétriques (Mann-Whitney, Kruskal-Wallis) sont plus adaptés.</li>"
        html += "</ul>"
        html += "</div>"

        html += "</div>"

        return html
    except Exception as e:
        import traceback

        traceback.print_exc()
        return "<p class='text-danger'>Erreur lors de la génération de la synthèse</p>"


def generate_period_analysis(df, granularity="month", skip_preprocessing=True):
    """
    Génère l'analyse statistique pour une période spécifique

    Args:
        df: DataFrame filtré pour la période
        granularity: 'month', 'quarter', 'year' - détermine l'agrégation temporelle
        skip_preprocessing: Si True, ne fait PAS de nettoyage supplémentaire
                           (les données sont déjà filtrées et nettoyées)

    Returns:
        dict: {
            'results': dict avec tous les tableaux HTML,
            'graphs': dict avec tous les graphiques HTML,
            'kpis': dict avec les KPIs principaux
        }
    """
    results = {}
    graphs = {}
    kpis = {}

    # Mapping des colonnes temporelles selon la granularité
    time_columns = {"month": "Month", "quarter": "Quarter", "year": "Fiscal_Year_Label"}
    time_col = time_columns.get(granularity, "Month")

    lignes_initiales = len(df)
    variables_num = ["Montant", "Quantité", "PU Net"]

    # Option A (matrice simple et lisible) :
    # conserver uniquement une variable "délai" compréhensible.
    if "Lead_Time_Days" in df.columns:
        variables_num.append("Lead_Time_Days")

    # Utiliser les données telles quelles en mode skip
    df_clean = df.copy()
    lignes_finales = len(df_clean)

    # KPIs de base
    kpis["total_transactions"] = f"{len(df_clean):,}"
    kpis["ca_total"] = (
        f"{df_clean['Montant'].sum():,.2f} €"
        if "Montant" in df_clean.columns
        else "N/A"
    )
    kpis["nb_clients"] = (
        f"{df_clean['Cpt Client'].nunique():,}"
        if "Cpt Client" in df_clean.columns
        else "N/A"
    )
    kpis["panier_moyen"] = (
        f"{df_clean['Montant'].mean():.2f} €"
        if "Montant" in df_clean.columns
        else "N/A"
    )

    # KPI Familles / Pays (robuste aux noms de colonnes)
    def _pick_col(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    fam_col = _pick_col(df_clean, ["FAMILLE", "Famille", "famille", "Famille 1"])
    country_col = _pick_col(df_clean, ["COUNTRY", "Country", "PAYS", "Pays", "country"])

    families_count = int(df_clean[fam_col].nunique(dropna=True)) if fam_col else 0
    countries_count = (
        int(df_clean[country_col].nunique(dropna=True)) if country_col else 0
    )

    kpis["nb_familles"] = f"{families_count:,}"
    kpis["nb_pays"] = f"{countries_count:,}"

    # ═══════════════════════════════════════════════════════════════════
    # AGRÉGATION PAR PÉRIODE SELON LA GRANULARITÉ
    # ═══════════════════════════════════════════════════════════════════
    # Créer df_agg pour les analyses de corrélation/distributions
    # au lieu d'utiliser les transactions brutes
    df_agg = df_clean  # Fallback par défaut
    use_aggregated = False

    if time_col in df_clean.columns:
        try:
            # Définir les colonnes à agréger qui existent
            agg_dict = {}
            if "Montant" in df_clean.columns:
                agg_dict["Montant"] = "sum"
            if "Quantité" in df_clean.columns:
                agg_dict["Quantité"] = "sum"
            if "PU Net" in df_clean.columns:
                agg_dict["PU Net"] = "mean"

            # Ajouter les variables de délai si elles existent
            if "Lead_Time_Days" in df_clean.columns:
                agg_dict["Lead_Time_Days"] = "mean"
            if "Delai_Prev_Days" in df_clean.columns:
                agg_dict["Delai_Prev_Days"] = "mean"
            if "Lead_Time_Deviation_Days" in df_clean.columns:
                agg_dict["Lead_Time_Deviation_Days"] = "mean"

            if agg_dict:
                df_agg = df_clean.groupby(time_col, as_index=False).agg(agg_dict)

                # Vérifier que df_agg est suffisamment grand pour les analyses
                if len(df_agg) >= 3:  # Minimum pour des analyses statistiques
                    use_aggregated = True
                else:
                    df_agg = df_clean
            else:
                pass
        except Exception as e:
            df_agg = df_clean
    else:
        pass

    # Sélection du DataFrame pour les analyses statistiques (corrélations, distributions)
    df_stats = df_agg if use_aggregated else df_clean

    # Statistiques descriptives PAR MOIS
    stats_by_month = {}
    if time_col in df_clean.columns:
        months = sorted(df_clean[time_col].unique())
        for month in months:
            month_data = df_clean[df_clean[time_col] == month]
            stats_table = []
            for var in variables_num:
                if var in month_data.columns:
                    stats_table.append(
                        {
                            "Variable": var,
                            "Moyenne": f"{month_data[var].mean():.2f}",
                            "Médiane": f"{month_data[var].median():.2f}",
                            "Écart-type": f"{month_data[var].std():.2f}",
                            "Min": f"{month_data[var].min():.2f}",
                            "Max": f"{month_data[var].max():.2f}",
                            "Count": f"{month_data[var].count()}",
                        }
                    )

            stats_by_month[str(month)] = pd.DataFrame(stats_table).to_html(
                classes="stats-table", index=False, border=0, justify="left"
            )

        # Stocker les mois disponibles
        results["available_months"] = [str(m) for m in months]

    # Statistiques descriptives globales (toute la période)
    stats_table = []
    for var in variables_num:
        if var in df_clean.columns:
            stats_table.append(
                {
                    "Variable": var,
                    "Moyenne": f"{df_clean[var].mean():.2f}",
                    "Médiane": f"{df_clean[var].median():.2f}",
                    "Écart-type": f"{df_clean[var].std():.2f}",
                    "Min": f"{df_clean[var].min():.2f}",
                    "Max": f"{df_clean[var].max():.2f}",
                    "Count": f"{df_clean[var].count()}",
                }
            )

    results["stats_descriptives"] = pd.DataFrame(stats_table).to_html(
        classes="stats-table", index=False, border=0, justify="left"
    )
    results["stats_by_month"] = stats_by_month

    # ═══════════════════════════════════════════════════════════════════
    # GÉNÉRATION DES GRAPHIQUES
    # ═══════════════════════════════════════════════════════════════════

    # 1. Matrice de corrélation évolutive dans le temps (uniquement)
    if all(col in df_stats.columns for col in variables_num):
        # Matrice de corrélation évolutive dans le temps
        if time_col in df_clean.columns and use_aggregated:
            try:
                # Calculer les corrélations pour chaque période
                periods = sorted(df_clean[time_col].unique())
                correlation_evolution = []

                for period in periods:
                    period_data = df_clean[df_clean[time_col] == period]
                    if len(period_data) >= 3:  # Minimum pour calculer une corrélation
                        # Calculer la corrélation si on a assez de colonnes
                        if (
                            len(
                                [
                                    col
                                    for col in variables_num
                                    if col in period_data.columns
                                ]
                            )
                            >= 2
                        ):
                            corr = period_data[variables_num].corr()

                            # Extraire les paires de corrélation
                            for i, var1 in enumerate(variables_num):
                                for j, var2 in enumerate(variables_num):
                                    if (
                                        i < j
                                        and var1 in corr.index
                                        and var2 in corr.columns
                                    ):
                                        correlation_evolution.append(
                                            {
                                                "Period": str(period),
                                                "Pair": f"{var1} vs {var2}",
                                                "Correlation": corr.loc[var1, var2],
                                            }
                                        )

                # Créer le graphique d'évolution sous forme de heatmap
                if correlation_evolution:
                    import plotly.graph_objects as go

                    df_corr_evol = pd.DataFrame(correlation_evolution)

                    # Créer une matrice pivot : lignes = paires, colonnes = périodes
                    pivot_matrix = df_corr_evol.pivot(
                        index="Pair", columns="Period", values="Correlation"
                    )

                    # Filtrer les colonnes qui contiennent des NaN
                    pivot_matrix = pivot_matrix.dropna(axis=1, how="any")

                    # Vérifier qu'il reste des données après filtrage
                    if not pivot_matrix.empty:
                        # Créer la heatmap
                        fig = go.Figure(
                            data=go.Heatmap(
                                z=pivot_matrix.values,
                                x=pivot_matrix.columns.tolist(),
                                y=pivot_matrix.index.tolist(),
                                colorscale="RdBu",  # Rouge-Blanc-Bleu (négatif-neutre-positif)
                                zmid=0,  # Centre de l'échelle à 0
                                zmin=-1,
                                zmax=1,
                                text=pivot_matrix.values.round(3),
                                texttemplate="%{text}",
                                textfont={"size": 10},
                                colorbar=dict(
                                    title="Corrélation",
                                    tickvals=[-1, -0.5, 0, 0.5, 1],
                                    ticktext=["-1.0", "-0.5", "0.0", "+0.5", "+1.0"],
                                ),
                                hovertemplate="<b>%{y}</b><br>Période: %{x}<br>Corrélation: %{z:.3f}<extra></extra>",
                            )
                        )

                        fig.update_layout(
                            title=f"📊 Matrice d'Évolution des Corrélations ({granularity.title()})",
                            xaxis_title="Période",
                            yaxis_title="Paire de Variables",
                            height=max(
                                400, len(pivot_matrix) * 50
                            ),  # Hauteur adaptative
                            template="plotly_white",
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=dict(tickangle=-45),
                        )

                        graphs["correlation_evolution"] = fig.to_html(
                            full_html=False, include_plotlyjs="cdn"
                        )

                        graphs["correlation_evolution"] = fig.to_html(
                            full_html=False, include_plotlyjs=False
                        )
                    else:
                        pass
                else:
                    pass
            except Exception as e:
                import traceback

                traceback.print_exc()

    # 2. Graphiques d'évolution mensuelle pour Montant et PU Net
    if time_col in df_clean.columns:
        # Évolution moyenne du Montant par mois
        if "Montant" in df_clean.columns:
            graphs["monthly_evolution_montant_mean"] = (
                viz_by_period.create_monthly_evolution_plot(
                    df_clean,
                    time_col,
                    "Montant",
                    stat_type="mean",
                    title="📈 Évolution du Montant Moyen par Mois",
                )
            )
            graphs["monthly_evolution_montant_median"] = (
                viz_by_period.create_monthly_evolution_plot(
                    df_clean,
                    time_col,
                    "Montant",
                    stat_type="median",
                    title="📈 Évolution du Montant Médian par Mois",
                )
            )
            # Distribution par mois
            graphs["distribution_montant_by_month"] = (
                viz_by_period.create_distribution_by_month(
                    df_clean,
                    time_col,
                    "Montant",
                    title="📊 Distribution du Montant par Mois",
                    granularity=granularity,
                )
            )
            graphs["boxplot_montant_by_month"] = viz_by_period.create_boxplot_by_month(
                df_clean, time_col, "Montant", title="📦 Boxplot du Montant par Mois"
            )

        # Évolution du PU Net par mois
        if "PU Net" in df_clean.columns:
            graphs["monthly_evolution_pu_net_mean"] = (
                viz_by_period.create_monthly_evolution_plot(
                    df_clean,
                    time_col,
                    "PU Net",
                    stat_type="mean",
                    title="📈 Évolution du PU Net Moyen par Mois",
                )
            )
            graphs["monthly_evolution_pu_net_median"] = (
                viz_by_period.create_monthly_evolution_plot(
                    df_clean,
                    time_col,
                    "PU Net",
                    stat_type="median",
                    title="📈 Évolution du PU Net Médian par Mois",
                )
            )
            # Distribution par mois
            graphs["distribution_pu_net_by_month"] = (
                viz_by_period.create_distribution_by_month(
                    df_clean,
                    time_col,
                    "PU Net",
                    title="📊 Distribution du PU Net par Mois",
                    granularity=granularity,
                )
            )
            graphs["boxplot_pu_net_by_month"] = viz_by_period.create_boxplot_by_month(
                df_clean, time_col, "PU Net", title="📦 Boxplot du PU Net par Mois"
            )

        # Quantité par mois (si disponible)
        if "Quantité" in df_clean.columns:
            graphs["distribution_quantite_by_month"] = (
                viz_by_period.create_distribution_by_month(
                    df_clean,
                    time_col,
                    "Quantité",
                    title="📊 Distribution de la Quantité par Mois",
                    granularity=granularity,
                )
            )
            graphs["boxplot_quantite_by_month"] = viz_by_period.create_boxplot_by_month(
                df_clean,
                time_col,
                "Quantité",
                title="📦 Boxplot de la Quantité par Mois",
            )

    # 3. Boxplot pour les valeurs aberrantes (sur données agrégées)
    if all(col in df_agg.columns for col in variables_num):
        graphs["outliers_boxplot"] = viz_by_period.create_outliers_boxplot(
            df_agg, variables_num
        )

    # 4. Distributions des variables (sur données agrégées)
    for var in ["Montant", "Quantité", "PU Net"]:
        if var in df_stats.columns:
            graph_key = f'dist_complete_{var.lower().replace(" ", "_")}'
            graphs[graph_key] = viz_by_period.create_distribution_plot(df_stats, var)

    # 5. Top pays
    if "Country" in df_clean.columns and "Montant" in df_clean.columns:
        graphs["top_pays"] = viz_by_period.create_top_categories_plot(
            df_clean, "Country", "Montant", n_top=10, title="Top 10 Pays par CA"
        )

    # 6. Top familles
    if "Famille" in df_clean.columns and "Montant" in df_clean.columns:
        graphs["top_familles"] = viz_by_period.create_top_categories_plot(
            df_clean, "Famille", "Montant", n_top=10, title="Top 10 Familles par CA"
        )

    # 5. Agrégation temporelle selon la granularité choisie
    if time_col in df_clean.columns and "Montant" in df_clean.columns:
        # Graphique en barres
        graphs["ca_par_trimestre"] = viz_by_period.create_temporal_aggregation_plot(
            df_clean, time_col, "Montant", granularity
        )

        # Graphique d'évolution (barres)
        graphs["evolution_mensuelle"] = viz_by_period.create_temporal_evolution_plot(
            df_clean, time_col, "Montant", granularity
        )

        # Graphique de variation
        graphs["variation_trimestrielle"] = viz_by_period.create_variation_plot(
            df_clean, time_col, "Montant", granularity
        )

        # Nouveaux graphiques d'analyse CA

        # Pie chart répartition du CA
        graphs["ca_repartition_pie"] = viz_by_period.create_ca_repartition_pie(
            df_clean, time_col, "Montant", granularity
        )

        # Top 5 et Bottom 5 périodes par CA
        graphs["top_periods_high"] = viz_by_period.create_top_periods_bar(
            df_clean, time_col, "Montant", granularity, n_top=5, direction="top"
        )
        graphs["top_periods_low"] = viz_by_period.create_top_periods_bar(
            df_clean, time_col, "Montant", granularity, n_top=5, direction="bottom"
        )

        # CA moyen par transaction
        graphs["ca_moyen_transaction"] = viz_by_period.create_ca_moyen_per_transaction(
            df_clean, time_col, "Montant", granularity
        )

        # Stabilité des ventes
        graphs["stability_chart"] = viz_by_period.create_stability_chart(
            df_clean, time_col, "Montant", granularity
        )

    # ═══════════════════════════════════════════════════════════════════
    # SYNTHÈSE APPROFONDIE
    # ═══════════════════════════════════════════════════════════════════
    results["synthese_analyse"] = generate_deep_synthesis(df_clean, kpis, variables_num)

    return {"results": results, "graphs": graphs, "kpis": kpis}
