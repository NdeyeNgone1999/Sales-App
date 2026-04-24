"""
Visualisations pour l'onglet CLUSTERING
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.decomposition import PCA


def _make_responsive(fig):
    """Helper pour rendre un graphique Plotly responsive."""
    fig.update_layout(
        autosize=True,
        width=None,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _to_html_responsive(fig):
    """Convertit une figure Plotly en HTML avec config responsive."""
    fig = _make_responsive(fig)
    return fig.to_html(
        full_html=False, include_plotlyjs=False, config={"responsive": True}
    )


def create_clustering_pca_plot(df_client, X, title="Clustering K-Means (PCA 2D)"):
    """
    Crée le graphique de clustering en 2D avec réduction PCA.
    """
    try:
        pca = PCA(n_components=2)
        X_pca = pca.fit_transform(X)

        # Handle both column naming conventions
        client_col = (
            "Cpt_Client"
            if "Cpt_Client" in df_client.columns
            else "Cpt Client"
        )

        df_pca = pd.DataFrame(
            {
                "PC1": X_pca[:, 0],
                "PC2": X_pca[:, 1],
                "Cluster": df_client["Cluster"].astype(str),
                "CA_Total": df_client["CA_Total"],
                "Client": (
                    df_client[client_col].values
                    if client_col in df_client.columns
                    else np.arange(len(df_client))
                ),
            }
        )

        fig = px.scatter(
            df_pca,
            x="PC1",
            y="PC2",
            color="Cluster",
            size="CA_Total",
            hover_data=["Client", "CA_Total"],
            title=title,
            labels={
                "PC1": f"PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)",
                "PC2": f"PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)",
                "Cluster": "Cluster",
                "CA_Total": "CA Total (€)",
            },
            color_discrete_sequence=px.colors.qualitative.Set2,
        )

        fig.update_layout(
            height=600,
            font=dict(size=12),
            title_font=dict(size=16, family="Arial Black"),
            legend=dict(
                title=dict(text="Cluster", font=dict(size=14)),
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        fig.update_traces(
            marker=dict(line=dict(width=0.5, color="DarkSlateGrey"))
        )

        return _to_html_responsive(fig)

    except Exception as e:
        print(f"Erreur PCA plot: {e}")
        return None


def create_elbow_silhouette_plot(metrics, optimal_k):
    """Crée un graphique double : Méthode du Coude + Silhouette Score."""
    if not metrics:
        return None
    try:
        ks = [m["k"] for m in metrics]
        inertias = [m["inertia"] for m in metrics]
        silhouettes = [m["silhouette"] for m in metrics]

        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=[
                "Méthode du Coude (Elbow)",
                "Silhouette Score",
            ],
        )

        # Elbow
        fig.add_trace(
            go.Scatter(
                x=ks,
                y=inertias,
                mode="lines+markers",
                marker=dict(size=10, color="#e74c3c"),
                line=dict(width=3),
                name="Inertie",
            ),
            row=1,
            col=1,
        )
        fig.add_vline(
            x=optimal_k, line_dash="dash", line_color="green",
            annotation_text=f"K={optimal_k}", row=1, col=1,
        )

        # Silhouette
        colors = [
            "#2ecc71" if k == optimal_k else "#3498db" for k in ks
        ]
        fig.add_trace(
            go.Bar(
                x=ks,
                y=silhouettes,
                marker_color=colors,
                text=[f"{s:.3f}" for s in silhouettes],
                textposition="outside",
                name="Silhouette",
            ),
            row=1,
            col=2,
        )

        fig.update_layout(
            height=400,
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_xaxes(title_text="K", row=1, col=1)
        fig.update_xaxes(title_text="K", row=1, col=2)
        fig.update_yaxes(title_text="Inertie", row=1, col=1)
        fig.update_yaxes(title_text="Score", row=1, col=2)

        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur elbow/silhouette plot: {e}")
        return None


def create_cluster_distribution_plot(profiles):
    """Crée un graphique de distribution des clusters (donut)."""
    if not profiles:
        return None
    try:
        labels = [f"Cluster {p['id']}" for p in profiles]
        values = [p["nb_clients"] for p in profiles]

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.4,
                    marker=dict(
                        colors=px.colors.qualitative.Set2[: len(profiles)]
                    ),
                    textinfo="label+percent+value",
                    texttemplate="%{label}<br>%{value} clients<br>(%{percent})",
                )
            ]
        )

        fig.update_layout(
            title="Distribution des Clusters",
            height=400,
            paper_bgcolor="rgba(0,0,0,0)",
        )

        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur distribution plot: {e}")
        return None
