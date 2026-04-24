"""
Service de génération de textes d'interprétation pour les analyses.
Explications simples et compréhensibles pour les utilisateurs métier.
"""
from typing import Dict, Any, List


def explain_pareto(pareto_dict: Dict[str, Any]) -> str:
    """
    Génère un texte d'explication pour une analyse de Pareto.
    
    Args:
        pareto_dict: Résultat de aggregations.pareto()
    
    Returns:
        Texte d'interprétation HTML
    """
    top_20pct = pareto_dict.get('top_20pct_share', 0)
    top_10 = pareto_dict.get('top_10_share', 0)
    n_total = pareto_dict.get('n_total', 0)
    n_20pct = pareto_dict.get('n_20pct', 0)
    
    html = f"""
    <div class="interpretation-box">
        <h5><i class="bi bi-lightbulb"></i> Interprétation Pareto</h5>
        <p><strong>Principe 80/20 :</strong> Le principe de Pareto suggère que 80% du chiffre d'affaires 
        provient de 20% des clients.</p>
        
        <p><strong>Votre situation :</strong></p>
        <ul>
            <li>Les <strong>top {n_20pct} clients</strong> (20% de {n_total} clients) représentent 
                <strong>{top_20pct:.1f}% du CA</strong>.</li>
            <li>Les <strong>top 10 clients</strong> représentent <strong>{top_10:.1f}% du CA</strong>.</li>
        </ul>
    """
    
    if top_20pct > 85:
        html += """
            <p class="text-warning"><i class="bi bi-exclamation-triangle"></i> 
            <strong>Concentration très élevée</strong> : Dépendance forte d'un petit 
            nombre de clients. Risque élevé en cas de perte d'un client majeur.</p>
        """
    elif top_20pct > 70:
        html += """
            <p class="text-info"><i class="bi bi-info-circle"></i> 
            <strong>Concentration modérée</strong> : Bonne concentration avec marge de sécurité.</p>
        """
    else:
        html += """
            <p class="text-success"><i class="bi bi-check-circle"></i> 
            <strong>Bonne diversification</strong> : CA bien réparti entre les clients.</p>
        """
    
    html += """
    </div>
    """
    
    return html


def explain_lead_time(lead_pack: Dict[str, Any]) -> str:
    """
    Génère un texte d'explication pour l'analyse des délais.
    
    Args:
        lead_pack: Résultat de aggregations.lead_time_pack()
    
    Returns:
        Texte d'interprétation HTML
    """
    if 'error' in lead_pack:
        return f"""
        <div class="interpretation-box">
            <h5><i class="bi bi-exclamation-triangle text-warning"></i> Analyse des délais</h5>
            <p class="text-muted">{lead_pack['error']}</p>
        </div>
        """
    
    median = lead_pack.get('median', 0)
    mean = lead_pack.get('mean', 0)
    pct_anomalies = lead_pack.get('pct_anomalies', 0)
    pct_extremes = lead_pack.get('pct_extremes', 0)
    
    html = f"""
    <div class="interpretation-box">
        <h5><i class="bi bi-lightbulb"></i> Interprétation des délais de livraison</h5>
        
        <p><strong>Lecture des métriques :</strong></p>
        <ul>
            <li><strong>Médiane : {median:.1f} jours</strong> - C'est le délai "typique". 
                50% des commandes sont livrées plus vite, 50% plus lentement.</li>
            <li><strong>Moyenne : {mean:.1f} jours</strong> - Moyenne arithmétique de tous les délais.</li>
        </ul>
        
        <p><strong>Qualité des données :</strong></p>
        <ul>
    """
    
    if pct_anomalies > 5:
        html += f"""
            <li class="text-warning"><i class="bi bi-exclamation-triangle"></i> 
            <strong>{pct_anomalies:.1f}% de délais négatifs</strong> détectés 
            (date expédition < date commande). Vérifiez la qualité des données.</li>
        """
    else:
        html += f"""
            <li class="text-success"><i class="bi bi-check-circle"></i> 
            Seulement {pct_anomalies:.1f}% d'anomalies - Bonne qualité des données.</li>
        """
    
    if pct_extremes > 10:
        html += f"""
            <li class="text-info"><i class="bi bi-info-circle"></i> 
            <strong>{pct_extremes:.1f}% de délais > 1 an</strong> - Commandes exceptionnelles 
            ou erreurs de saisie.</li>
        """
    
    html += """
        </ul>
        
        <p><strong>Performance logistique :</strong></p>
        <ul>
    """
    
    if median < 7:
        html += """
            <li class="text-success"><i class="bi bi-check-circle"></i> 
            <strong>Excellent</strong> : Délai médian très court (< 1 semaine).</li>
        """
    elif median < 14:
        html += """
            <li class="text-success"><i class="bi bi-check-circle"></i> 
            <strong>Bon</strong> : Délai médian court (< 2 semaines).</li>
        """
    elif median < 30:
        html += """
            <li class="text-info"><i class="bi bi-info-circle"></i> 
            <strong>Correct</strong> : Délai médian standard (< 1 mois).</li>
        """
    else:
        html += """
            <li class="text-warning"><i class="bi bi-exclamation-triangle"></i> 
            <strong>À améliorer</strong> : Délai médian long (> 1 mois). 
            Explorez les opportunités d'optimisation logistique.</li>
        """
    
    html += """
        </ul>
    </div>
    """
    
    return html


def explain_currency_concentration(currency_data: Dict[str, Any]) -> str:
    """
    Génère un texte d'explication pour la dépendance aux devises.
    
    Args:
        currency_data: KPIs devises avec nb_currencies, non_eur_pct, hhi, top_currency
    
    Returns:
        Texte d'interprétation HTML
    """
    nb_currencies = currency_data.get('nb_currencies', 0)
    non_eur_pct = currency_data.get('non_eur_pct', 0)
    hhi = currency_data.get('hhi', 0)
    top_currency = currency_data.get('top_currency', 'N/A')
    
    html = f"""
    <div class="interpretation-box">
        <h5><i class="bi bi-lightbulb"></i> Interprétation de l'exposition aux devises</h5>
        
        <p><strong>Contexte :</strong> L'analyse mesure votre <strong>exposition</strong> aux différentes 
        devises basée sur la colonne "Nom Devise". Cela indique les marchés sur lesquels vous opérez, 
        <strong>sans conversion de taux de change</strong> (montants déjà en EUR).</p>
        
        <p><strong>Votre situation :</strong></p>
        <ul>
            <li><strong>{nb_currencies} devises</strong> détectées dans vos transactions.</li>
            <li><strong>{non_eur_pct:.1f}% du CA</strong> provient de marchés hors zone Euro.</li>
            <li><strong>Devise principale :</strong> {top_currency}</li>
        </ul>
        
        <p><strong>Indice HHI (Herfindahl-Hirschman Index) : {hhi:.0f}</strong></p>
        <ul>
    """
    
    if hhi > 5000:
        html += """
            <li class="text-warning"><i class="bi bi-exclamation-triangle"></i> 
            <strong>Concentration élevée</strong> (HHI > 5000) : Votre CA est très concentré 
            sur une ou deux devises. Risque de dépendance à un marché spécifique.</li>
        """
    elif hhi > 2500:
        html += """
            <li class="text-info"><i class="bi bi-info-circle"></i> 
            <strong>Concentration modérée</strong> (HHI 2500-5000) : Bonne diversification 
            avec quelques devises dominantes.</li>
        """
    else:
        html += """
            <li class="text-success"><i class="bi bi-check-circle"></i> 
            <strong>Bonne diversification</strong> (HHI < 2500) : Votre CA est bien réparti 
            entre plusieurs marchés/devises.</li>
        """
    
    html += """
        </ul>
    </div>
    """
    
    return html


def explain_normality(series: List[Dict[str, Any]]) -> str:
    """
    Génère une explication simple sur la distribution d'une série.
    (Version simplifiée sans tests statistiques)
    
    Args:
        series: Liste de valeurs [{label, value}]
    
    Returns:
        Texte d'interprétation HTML
    """
    if not series or len(series) < 3:
        return """
        <div class="interpretation-box">
            <h5><i class="bi bi-info-circle"></i> Distribution</h5>
            <p class="text-muted">Données insuffisantes pour analyser la distribution.</p>
        </div>
        """
    
    values = [s['value'] for s in series]
    mean_val = sum(values) / len(values)
    max_val = max(values)
    min_val = min(values)
    
    # Détection asymétrie simple
    is_skewed = (max_val - mean_val) > 2 * (mean_val - min_val)
    
    html = f"""
    <div class="interpretation-box">
        <h5><i class="bi bi-graph-up"></i> À propos de la distribution</h5>
        <p><strong>Tendance observée :</strong></p>
        <ul>
    """
    
    if is_skewed:
        html += """
            <li>Distribution <strong>asymétrique</strong> : Quelques périodes exceptionnelles 
            tirent les résultats vers le haut.</li>
            <li>Regardez les périodes avec les valeurs les plus élevées pour identifier 
            des opportunités ou événements spéciaux.</li>
        """
    else:
        html += """
            <li>Distribution <strong>relativement équilibrée</strong> : 
            Les valeurs sont réparties de manière assez uniforme.</li>
            <li>Activité stable dans le temps.</li>
        """
    
    html += """
        </ul>
    </div>
    """
    
    return html
