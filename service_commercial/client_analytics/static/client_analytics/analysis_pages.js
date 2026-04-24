// ==========================================
// SCIENTIFIC PARTICLES SYSTEM
// Style américain futuriste pour pages d'analyse
// ==========================================

(function() {
    'use strict';
    
    // ===== CONFIGURATION =====
    const CONFIG = {
        particles: {
            count: 80,
            countMobile: 40,
            speed: 0.8,
            size: { min: 2, max: 6 },
            opacity: { min: 0.3, max: 0.8 },
            colors: [
                { r: 0, g: 217, b: 255 },    // Cyan tech
                { r: 0, g: 255, b: 255 },    // Cyan bright
                { r: 0, g: 102, b: 204 },    // Blue tech
                { r: 255, g: 0, b: 128 },    // Pink américain
                { r: 0, g: 255, b: 136 }     // Green tech
            ],
            connectionDistance: 180,
            connectionOpacity: 0.2,
            connectionWidth: 1.5,
            dataNodes: {
                count: 12,
                size: { min: 8, max: 16 },
                pulseSpeed: 0.03,
                orbitSpeed: 0.001
            }
        }
    };
    
    // ===== STATE =====
    const State = {
        isMobile: false,
        reducedMotion: false,
        isDocumentHidden: false
    };
    
    // ===== UTILITY =====
    function isMobileDevice() {
        return window.innerWidth <= 768;
    }
    
    function checkReducedMotion() {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    
    // ===== SCIENTIFIC PARTICLES SYSTEM =====
    const ScientificParticlesSystem = {
        canvas: null,
        ctx: null,
        particles: [],
        dataNodes: [],
        dpr: 1,
        animationId: null,
        
        init() {
            this.canvas = document.getElementById('scientificParticles');
            if (!this.canvas) return;
            
            this.ctx = this.canvas.getContext('2d');
            this.dpr = window.devicePixelRatio || 1;
            
            State.isMobile = isMobileDevice();
            State.reducedMotion = checkReducedMotion();
            
            this.resize();
            window.addEventListener('resize', () => this.resize(), { passive: true });
            
            if (!State.reducedMotion) {
                this.animate();
            }
        },
        
        resize() {
            if (!this.canvas) return;
            
            const width = window.innerWidth;
            const height = window.innerHeight;
            
            this.canvas.width = width * this.dpr;
            this.canvas.height = height * this.dpr;
            this.ctx.scale(this.dpr, this.dpr);
            
            this.canvas.style.width = width + 'px';
            this.canvas.style.height = height + 'px';
            
            this.createParticles();
            this.createDataNodes();
        },
        
        createParticles() {
            const count = State.isMobile ? 
                CONFIG.particles.countMobile : 
                CONFIG.particles.count;
            
            this.particles = [];
            const w = window.innerWidth;
            const h = window.innerHeight;
            
            for (let i = 0; i < count; i++) {
                const color = CONFIG.particles.colors[
                    Math.floor(Math.random() * CONFIG.particles.colors.length)
                ];
                
                this.particles.push({
                    x: Math.random() * w,
                    y: Math.random() * h,
                    vx: (Math.random() - 0.5) * CONFIG.particles.speed,
                    vy: (Math.random() - 0.5) * CONFIG.particles.speed,
                    size: CONFIG.particles.size.min + 
                          Math.random() * (CONFIG.particles.size.max - CONFIG.particles.size.min),
                    opacity: CONFIG.particles.opacity.min + 
                            Math.random() * (CONFIG.particles.opacity.max - CONFIG.particles.opacity.min),
                    color: color,
                    pulsePhase: Math.random() * Math.PI * 2,
                    pulseSpeed: 0.02 + Math.random() * 0.02
                });
            }
        },
        
        createDataNodes() {
            this.dataNodes = [];
            const w = window.innerWidth;
            const h = window.innerHeight;
            const count = CONFIG.particles.dataNodes.count;
            
            for (let i = 0; i < count; i++) {
                const centerX = w / 2;
                const centerY = h / 2;
                const angle = (i / count) * Math.PI * 2;
                const radius = Math.min(w, h) * 0.3;
                
                const color = CONFIG.particles.colors[
                    Math.floor(Math.random() * CONFIG.particles.colors.length)
                ];
                
                this.dataNodes.push({
                    centerX: centerX,
                    centerY: centerY,
                    angle: angle,
                    radius: radius,
                    x: centerX + Math.cos(angle) * radius,
                    y: centerY + Math.sin(angle) * radius,
                    size: CONFIG.particles.dataNodes.size.min +
                          Math.random() * (CONFIG.particles.dataNodes.size.max - CONFIG.particles.dataNodes.size.min),
                    color: color,
                    pulsePhase: Math.random() * Math.PI * 2,
                    orbitSpeed: CONFIG.particles.dataNodes.orbitSpeed * (Math.random() > 0.5 ? 1 : -1)
                });
            }
        },
        
        drawParticle(particle, currentSize) {
            this.ctx.save();
            
            // Glow effet
            const gradient = this.ctx.createRadialGradient(
                particle.x, particle.y, 0,
                particle.x, particle.y, currentSize * 2
            );
            gradient.addColorStop(0, `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, ${particle.opacity})`);
            gradient.addColorStop(0.5, `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, ${particle.opacity * 0.3})`);
            gradient.addColorStop(1, `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, 0)`);
            
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, currentSize * 2, 0, Math.PI * 2);
            this.ctx.fillStyle = gradient;
            this.ctx.fill();
            
            // Core
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, currentSize, 0, Math.PI * 2);
            this.ctx.fillStyle = `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, ${particle.opacity})`;
            this.ctx.fill();
            
            this.ctx.restore();
        },
        
        drawDataNode(node) {
            this.ctx.save();
            
            // Update orbit
            node.angle += node.orbitSpeed;
            node.x = node.centerX + Math.cos(node.angle) * node.radius;
            node.y = node.centerY + Math.sin(node.angle) * node.radius;
            
            // Pulse
            node.pulsePhase += CONFIG.particles.dataNodes.pulseSpeed;
            const pulseFactor = 0.8 + Math.sin(node.pulsePhase) * 0.2;
            const currentSize = node.size * pulseFactor;
            
            // Outer glow (plus grand)
            const outerGradient = this.ctx.createRadialGradient(
                node.x, node.y, 0,
                node.x, node.y, currentSize * 4
            );
            outerGradient.addColorStop(0, `rgba(${node.color.r}, ${node.color.g}, ${node.color.b}, 0.6)`);
            outerGradient.addColorStop(0.5, `rgba(${node.color.r}, ${node.color.g}, ${node.color.b}, 0.2)`);
            outerGradient.addColorStop(1, `rgba(${node.color.r}, ${node.color.g}, ${node.color.b}, 0)`);
            
            this.ctx.beginPath();
            this.ctx.arc(node.x, node.y, currentSize * 4, 0, Math.PI * 2);
            this.ctx.fillStyle = outerGradient;
            this.ctx.fill();
            
            // Core hexagone (forme tech)
            this.ctx.beginPath();
            for (let i = 0; i < 6; i++) {
                const angle = (i / 6) * Math.PI * 2;
                const x = node.x + Math.cos(angle) * currentSize;
                const y = node.y + Math.sin(angle) * currentSize;
                if (i === 0) this.ctx.moveTo(x, y);
                else this.ctx.lineTo(x, y);
            }
            this.ctx.closePath();
            this.ctx.fillStyle = `rgba(${node.color.r}, ${node.color.g}, ${node.color.b}, 0.8)`;
            this.ctx.fill();
            this.ctx.strokeStyle = `rgba(255, 255, 255, 0.6)`;
            this.ctx.lineWidth = 2;
            this.ctx.stroke();
            
            this.ctx.restore();
        },
        
        drawConnections() {
            // Connections entre particules
            this.particles.forEach((p1, i) => {
                this.particles.slice(i + 1).forEach(p2 => {
                    const dx = p1.x - p2.x;
                    const dy = p1.y - p2.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    
                    if (distance < CONFIG.particles.connectionDistance) {
                        const opacity = (1 - distance / CONFIG.particles.connectionDistance) * 
                                      CONFIG.particles.connectionOpacity;
                        
                        this.ctx.beginPath();
                        this.ctx.strokeStyle = `rgba(0, 217, 255, ${opacity})`;
                        this.ctx.lineWidth = CONFIG.particles.connectionWidth;
                        this.ctx.moveTo(p1.x, p1.y);
                        this.ctx.lineTo(p2.x, p2.y);
                        this.ctx.stroke();
                    }
                });
            });
            
            // Connections entre data nodes
            this.dataNodes.forEach((n1, i) => {
                this.dataNodes.slice(i + 1).forEach(n2 => {
                    const dx = n1.x - n2.x;
                    const dy = n1.y - n2.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    
                    if (distance < 300) {
                        const gradient = this.ctx.createLinearGradient(n1.x, n1.y, n2.x, n2.y);
                        gradient.addColorStop(0, `rgba(${n1.color.r}, ${n1.color.g}, ${n1.color.b}, 0.3)`);
                        gradient.addColorStop(1, `rgba(${n2.color.r}, ${n2.color.g}, ${n2.color.b}, 0.3)`);
                        
                        this.ctx.beginPath();
                        this.ctx.strokeStyle = gradient;
                        this.ctx.lineWidth = 2;
                        this.ctx.moveTo(n1.x, n1.y);
                        this.ctx.lineTo(n2.x, n2.y);
                        this.ctx.stroke();
                    }
                });
            });
        },
        
        animate() {
            const w = window.innerWidth;
            const h = window.innerHeight;
            
            this.ctx.clearRect(0, 0, w, h);
            
            // Update and draw particles
            this.particles.forEach(p => {
                p.pulsePhase += p.pulseSpeed;
                const pulseFactor = 0.85 + Math.sin(p.pulsePhase) * 0.15;
                const currentSize = p.size * pulseFactor;
                
                p.x += p.vx;
                p.y += p.vy;
                
                if (p.x < 0 || p.x > w) { p.vx *= -1; p.x = Math.max(0, Math.min(p.x, w)); }
                if (p.y < 0 || p.y > h) { p.vy *= -1; p.y = Math.max(0, Math.min(p.y, h)); }
                
                this.drawParticle(p, currentSize);
            });
            
            // Draw data nodes
            this.dataNodes.forEach(node => {
                this.drawDataNode(node);
            });
            
            // Draw connections
            this.drawConnections();
            
            // Continue
            if (!State.isDocumentHidden && !State.reducedMotion) {
                this.animationId = requestAnimationFrame(() => this.animate());
            }
        },
        
        stop() {
            if (this.animationId) {
                cancelAnimationFrame(this.animationId);
                this.animationId = null;
            }
        }
    };
    
    // ===== DOCUMENT VISIBILITY =====
    function handleVisibilityChange() {
        State.isDocumentHidden = document.hidden;
        if (!State.isDocumentHidden && !State.reducedMotion) {
            ScientificParticlesSystem.animate();
        } else {
            ScientificParticlesSystem.stop();
        }
    }
    
    // ===== INITIALIZATION =====
    function init() {
        State.isMobile = isMobileDevice();
        State.reducedMotion = checkReducedMotion();
        
        ScientificParticlesSystem.init();
        
        document.addEventListener('visibilitychange', handleVisibilityChange);
        
        console.log('🔬 Scientific Particles System initialized');
    }
    
    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

// ==========================================
// PERIOD SELECTOR HANDLER
// Gestion du sélecteur de période (Mois/Trimestre/Année)
// ==========================================

(function() {
    'use strict';
    
    function initPeriodSelector() {
        const periodButtons = document.querySelectorAll('.period-btn');
        const periodTabs = document.querySelectorAll('#periodTabs .nav-link');
        
        if (periodButtons.length === 0) return;
        
        // Mapping entre les boutons et les onglets
        const periodMapping = {
            'month': 'month-tab',
            'quarter': 'quarter-tab',
            'year': 'fiscal-tab'
        };
        
        // Lire la granularité depuis l'URL au chargement
        const urlParams = new URLSearchParams(window.location.search);
        const currentGranularity = urlParams.get('granularity') || 'month';
        
        // Activer le bon bouton au chargement
        periodButtons.forEach(btn => {
            const period = btn.getAttribute('data-period');
            if (period === currentGranularity) {
                btn.classList.add('active');
                // Activer aussi l'onglet correspondant
                const tabId = periodMapping[period];
                const tabElement = document.getElementById(tabId);
                if (tabElement) {
                    const tab = new bootstrap.Tab(tabElement);
                    tab.show();
                }
            } else {
                btn.classList.remove('active');
            }
        });
        
        periodButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                const period = this.getAttribute('data-period');
                
                // Activer visuellement le bouton
                periodButtons.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                // Basculer vers l'onglet de période correspondant (client-side uniquement)
                const tabId = periodMapping[period];
                const tabElement = document.getElementById(tabId);
                if (tabElement) {
                    const tab = new bootstrap.Tab(tabElement);
                    tab.show();
                }
                
                // Reload all already-loaded AJAX tabs with the new granularity
                if (window.showPageLoader) window.showPageLoader('Changement de période…');
                const panesToReload = document.querySelectorAll('[data-ajax-tab][data-ajax-loaded="true"]');
                let pending = panesToReload.length;
                if (pending === 0 && window.hidePageLoader) {
                    setTimeout(window.hidePageLoader, 500);
                }
                panesToReload.forEach(pane => {
                    delete pane.dataset.ajaxLoaded;
                    if (window._ajaxTabSync) {
                        window._ajaxTabSync.reloadPane(pane);
                    }
                });

                // Redimensionner les graphiques Plotly après changement d'onglet
                setTimeout(() => {
                    if (window.Plotly) {
                        document.querySelectorAll('.plotly-graph-div').forEach(div => {
                            try { Plotly.Plots.resize(div); } catch(e) {}
                        });
                    }
                }, 200);
            });
        });
        
        // Synchroniser les onglets avec les boutons (optionnel, mais garde la cohérence visuelle)
        periodTabs.forEach(tab => {
            tab.addEventListener('shown.bs.tab', function(e) {
                const tabId = e.target.id;
                let period = null;
                
                // Trouver le period correspondant
                for (const [key, value] of Object.entries(periodMapping)) {
                    if (value === tabId) {
                        period = key;
                        break;
                    }
                }
                
                if (period) {
                    // Mettre à jour les boutons visuellement
                    periodButtons.forEach(btn => {
                        if (btn.getAttribute('data-period') === period) {
                            btn.classList.add('active');
                        } else {
                            btn.classList.remove('active');
                        }
                    });
                }
            });
        });
        
        console.log('📅 Period selector initialized (granularity: ' + currentGranularity + ')');
    }
    
    // Initialiser quand le DOM est prêt
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPeriodSelector);
    } else {
        initPeriodSelector();
    }
})();

// ==========================================
// PLOTLY RESPONSIVE RESIZE HANDLER
// Redimensionne les graphiques Plotly lors des changements d'onglets et de fenêtre
// ==========================================

(function() {
    'use strict';
    
    /**
     * Redimensionne tous les graphiques Plotly dans un conteneur donné
     * @param {HTMLElement|Document} container - Le conteneur à rechercher (ou document)
     */
    function resizePlotlyIn(container) {
        if (!window.Plotly) return;
        
        const plotlyDivs = container.querySelectorAll('.plotly-graph-div');
        
        if (plotlyDivs.length === 0) return;
        
        // Utiliser requestAnimationFrame pour éviter les problèmes de layout
        requestAnimationFrame(() => {
            // Petit délai pour laisser le layout se stabiliser
            setTimeout(() => {
                plotlyDivs.forEach(div => {
                    try {
                        if (Plotly.Plots && Plotly.Plots.resize) {
                            Plotly.Plots.resize(div);
                        }
                    } catch (e) {
                        // Ignore silencieusement les erreurs (graph pas encore initialisé, etc.)
                    }
                });
            }, 100);
        });
    }
    
    /**
     * Debounce helper pour éviter trop d'appels
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Initialise les event listeners pour le resize
     */
    function initPlotlyResize() {
        // 1. Resize initial au chargement de la page
        resizePlotlyIn(document);
        
        // 2. Resize lors du changement de taille de fenêtre (debounced)
        const debouncedResize = debounce(() => {
            resizePlotlyIn(document);
        }, 200);
        
        window.addEventListener('resize', debouncedResize, { passive: true });
        
        // 3. Resize lors du changement d'onglet Bootstrap (onglets principaux)
        const mainTabButtons = document.querySelectorAll('#analysisTabs [data-bs-toggle="tab"]');
        mainTabButtons.forEach(button => {
            button.addEventListener('shown.bs.tab', (event) => {
                const targetId = event.target.getAttribute('data-bs-target');
                if (targetId) {
                    const targetPane = document.querySelector(targetId);
                    if (targetPane) {
                        resizePlotlyIn(targetPane);
                    }
                }
            });
        });
        
        // 4. Resize lors du changement de sous-onglets période (pills)
        const periodTabButtons = document.querySelectorAll('#periodTabs [data-bs-toggle="pill"]');
        periodTabButtons.forEach(button => {
            button.addEventListener('shown.bs.tab', (event) => {
                const targetId = event.target.getAttribute('data-bs-target');
                if (targetId) {
                    const targetPane = document.querySelector(targetId);
                    if (targetPane) {
                        resizePlotlyIn(targetPane);
                    }
                }
            });
        });

        // 4b. Resize lors du changement de sous-onglets Série temporelle (pills)
        // (Mois / Trimestre / Année fiscale) : ces panes sont masqués au load.
        const temporalPillButtons = document.querySelectorAll('#temporal [data-bs-toggle="pill"]');
        temporalPillButtons.forEach(button => {
            button.addEventListener('shown.bs.tab', (event) => {
                const targetId = event.target.getAttribute('data-bs-target');
                if (targetId) {
                    const targetPane = document.querySelector(targetId);
                    if (targetPane) {
                        resizePlotlyIn(targetPane);
                    }
                }
            });
        });
        
        // 5. Observer pour les sections qui deviennent visibles (display: none -> block)
        // Utile pour les sections "Analyse avancée" qui sont toggles
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    const target = mutation.target;
                    // Si l'élément devient visible
                    if (target.style.display !== 'none' && target.offsetParent !== null) {
                        const plotlyDivs = target.querySelectorAll('.plotly-graph-div');
                        if (plotlyDivs.length > 0) {
                            resizePlotlyIn(target);
                        }
                    }
                }
            });
        });
        
        // Observer les changements de style sur les sections potentielles
        const sections = document.querySelectorAll('.collapse, [class*="advanced"]');
        sections.forEach(section => {
            observer.observe(section, { 
                attributes: true, 
                attributeFilter: ['style', 'class'] 
            });
        });
        
        console.log('📊 Plotly responsive resize handler initialized');
    }
    
    // Initialiser quand le DOM est prêt
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPlotlyResize);
    } else {
        initPlotlyResize();
    }
})();

// ==========================================
// GESTION DES ONGLETS PRINCIPAUX
// ==========================================
(function() {
    'use strict';
    
    function initTabTracking() {
        const tabButtons = document.querySelectorAll('#analysisTabs button[data-bs-toggle="tab"]');
        
        if (tabButtons.length === 0) return;
        
        // Mapping entre les ID d'onglets et les noms de tabs
        const tabMapping = {
            'stats-tab': 'statistics',
            'temporal-tab': 'temporal',
            'products-tab': 'products',
            'clients-tab': 'clients',
            'geography-tab': 'geographic',
            'currency-tab': 'currency'
        };
        
        // Écouter les changements d'onglets
        tabButtons.forEach(btn => {
            btn.addEventListener('shown.bs.tab', function(e) {
                const tabId = e.target.id;
                const tabName = tabMapping[tabId];
                
                if (tabName) {
                    // Mettre à jour l'URL sans recharger la page
                    const currentUrl = new URL(window.location.href);
                    currentUrl.searchParams.set('tab', tabName);
                    window.history.pushState({tab: tabName}, '', currentUrl.toString());
                    
                    console.log('📑 Onglet activé:', tabName);
                }
            });
        });
        
        // Au chargement, activer l'onglet correspondant au paramètre tab
        const urlParams = new URLSearchParams(window.location.search);
        const currentTab = urlParams.get('tab');
        
        if (currentTab) {
            // Trouver le bouton d'onglet correspondant
            for (const [btnId, tabName] of Object.entries(tabMapping)) {
                if (tabName === currentTab) {
                    const tabElement = document.getElementById(btnId);
                    if (tabElement) {
                        const tab = new bootstrap.Tab(tabElement);
                        tab.show();
                    }
                    break;
                }
            }
        }
        
        console.log('📑 Tab tracking initialized');
    }
    
    // Initialiser quand le DOM est prêt
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTabTracking);
    } else {
        initTabTracking();
    }
})();

// ==========================================
// AJAX HANDLERS POUR ANALYSES CIBLÉES
// Évite le rechargement complet de la page
// ==========================================
(function() {
    'use strict';
    
    /**
     * Injecte du HTML et exécute les scripts qu'il contient
     * (nécessaire pour les graphiques Plotly qui ont des <script>)
     */
    function injectHTMLWithScripts(container, htmlString) {
        // Créer un élément temporaire pour parser le HTML
        const temp = document.createElement('div');
        temp.innerHTML = htmlString;
        
        // Extraire tous les scripts
        const scripts = temp.querySelectorAll('script');
        const scriptContents = [];
        scripts.forEach(script => {
            if (script.src) {
                // Script externe
                scriptContents.push({type: 'external', src: script.src});
            } else {
                // Script inline
                scriptContents.push({type: 'inline', content: script.textContent});
            }
            script.remove(); // Retirer le script du HTML
        });
        
        // Injecter le HTML sans les scripts
        container.innerHTML = temp.innerHTML;
        
        // Exécuter les scripts un par un
        scriptContents.forEach(script => {
            const scriptElement = document.createElement('script');
            if (script.type === 'external') {
                scriptElement.src = script.src;
            } else {
                scriptElement.textContent = script.content;
            }
            container.appendChild(scriptElement);
        });
    }
    
    function initAjaxForms() {
        // Récupérer le dataset PK depuis l'URL
        const pathParts = window.location.pathname.split('/');
        const pkIndex = pathParts.indexOf('dataset');
        const datasetPk = pkIndex >= 0 ? pathParts[pkIndex + 1] : null;
        
        if (!datasetPk) return;
        
        // ===== 1. PORTEFEUILLE CLIENT =====
        const clientPortfolioForms = document.querySelectorAll('form:has(select[name="client"]):has(input[name="tab"][value="clients"])');
        clientPortfolioForms.forEach(form => {
            if (form.hasAttribute('data-ajax-handled')) return;
            form.setAttribute('data-ajax-handled', 'true');
            
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const clientId = this.querySelector('select[name="client"]').value;
                const granularity = this.querySelector('input[name="granularity"]').value || 'month';
                
                if (!clientId) {
                    alert('Veuillez sélectionner un client');
                    return;
                }
                
                // Trouver le conteneur de résultats (après le formulaire)
                let resultsContainer = this.parentElement.querySelector('.client-portfolio-results');
                if (!resultsContainer) {
                    // Chercher le conteneur existant avec condition {% if selected_client %}
                    const nextDiv = this.nextElementSibling;
                    if (nextDiv && nextDiv.classList.contains('mt-4')) {
                        resultsContainer = nextDiv;
                        resultsContainer.classList.add('client-portfolio-results');
                    } else {
                        resultsContainer = document.createElement('div');
                        resultsContainer.className = 'mt-4 client-portfolio-results';
                        this.parentElement.appendChild(resultsContainer);
                    }
                }
                
                // Afficher un loader
                resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Chargement...</span></div></div>';
                
                // Requête AJAX
                const url = `/dataset/${datasetPk}/ajax/client-portfolio/?client=${encodeURIComponent(clientId)}&granularity=${granularity}`;
                
                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            injectHTMLWithScripts(resultsContainer, data.html);
                            // Redimensionner les graphiques Plotly si présents
                            if (window.Plotly) {
                                setTimeout(() => {
                                    const plotlyDivs = resultsContainer.querySelectorAll('.plotly-graph-div');
                                    plotlyDivs.forEach(div => {
                                        try {
                                            Plotly.Plots.resize(div);
                                        } catch(e) {}
                                    });
                                }, 100);
                            }
                        } else {
                            resultsContainer.innerHTML = `<div class="alert alert-danger">${data.error || 'Erreur lors du chargement'}</div>`;
                        }
                    })
                    .catch(error => {
                        console.error('Erreur AJAX:', error);
                        resultsContainer.innerHTML = '<div class="alert alert-danger">Erreur de chargement</div>';
                    });
            });
        });
        
        // ===== 2. CORRÉLATION CIBLÉE (PRODUIT/FAMILLE) =====
        const correlationForms = document.querySelectorAll('form:has(select[name="product"]):has(select[name="family"]):has(input[name="tab"][value="products"])');
        correlationForms.forEach(form => {
            if (form.hasAttribute('data-ajax-handled')) return;
            form.setAttribute('data-ajax-handled', 'true');
            
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const product = this.querySelector('select[name="product"]').value;
                const family = this.querySelector('select[name="family"]').value;
                const granularity = this.querySelector('input[name="granularity"]').value || 'month';
                
                if (!product && !family) {
                    alert('Veuillez sélectionner un produit OU une famille');
                    return;
                }
                
                // Trouver ou créer le conteneur de résultats
                let resultsContainer = this.parentElement.querySelector('.correlation-results');
                if (!resultsContainer) {
                    // Chercher le conteneur existant après le formulaire
                    const conditionalResults = Array.from(this.parentElement.children)
                        .find(el => el.classList.contains('mt-3') && !el.querySelector('form'));
                    
                    if (conditionalResults) {
                        resultsContainer = conditionalResults;
                        resultsContainer.classList.add('correlation-results');
                    } else {
                        resultsContainer = document.createElement('div');
                        resultsContainer.className = 'correlation-results mt-3';
                        this.parentElement.appendChild(resultsContainer);
                    }
                }
                
                resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Chargement...</span></div></div>';
                
                const params = new URLSearchParams({
                    product: product,
                    family: family,
                    granularity: granularity
                });
                
                fetch(`/dataset/${datasetPk}/ajax/product-correlation/?${params}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            injectHTMLWithScripts(resultsContainer, data.html);
                            if (window.Plotly) {
                                setTimeout(() => {
                                    const plotlyDivs = resultsContainer.querySelectorAll('.plotly-graph-div');
                                    plotlyDivs.forEach(div => {
                                        try {
                                            Plotly.Plots.resize(div);
                                        } catch(e) {}
                                    });
                                }, 100);
                            }
                        } else {
                            resultsContainer.innerHTML = `<div class="alert alert-danger">${data.error || 'Erreur'}</div>`;
                        }
                    })
                    .catch(error => {
                        console.error('Erreur AJAX:', error);
                        resultsContainer.innerHTML = '<div class="alert alert-danger">Erreur de chargement</div>';
                    });
            });
        });
        
        // ===== 3. COMPARAISON PRODUITS =====
        const compareProductsForms = document.querySelectorAll('form:has(select[name="compare_products"][multiple]):has(select[name="compare_products_metric"])');
        compareProductsForms.forEach(form => {
            if (form.hasAttribute('data-ajax-handled')) return;
            form.setAttribute('data-ajax-handled', 'true');
            
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const productsSelect = this.querySelector('select[name="compare_products"]');
                const selectedProducts = Array.from(productsSelect.selectedOptions).map(opt => opt.value);
                const metric = this.querySelector('select[name="compare_products_metric"]').value;
                const granularity = this.querySelector('input[name="granularity"]').value || 'month';
                
                if (selectedProducts.length === 0) {
                    alert('Veuillez sélectionner au moins un produit');
                    return;
                }
                
                let resultsContainer = this.parentElement.querySelector('.compare-products-results');
                if (!resultsContainer) {
                    // Chercher résultats existants
                    const conditionalResults = Array.from(this.parentElement.children)
                        .find(el => el.classList.contains('mt-3') && !el.querySelector('form'));
                    
                    if (conditionalResults) {
                        resultsContainer = conditionalResults;
                        resultsContainer.classList.add('compare-products-results');
                    } else {
                        resultsContainer = document.createElement('div');
                        resultsContainer.className = 'compare-products-results mt-3';
                        this.parentElement.appendChild(resultsContainer);
                    }
                }
                
                resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Chargement...</span></div></div>';
                
                const params = new URLSearchParams({
                    compare_products_metric: metric,
                    granularity: granularity
                });
                selectedProducts.forEach(p => params.append('compare_products', p));
                
                fetch(`/dataset/${datasetPk}/ajax/compare-products/?${params}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            injectHTMLWithScripts(resultsContainer, data.html);
                            if (window.Plotly) {
                                setTimeout(() => {
                                    const plotlyDivs = resultsContainer.querySelectorAll('.plotly-graph-div');
                                    plotlyDivs.forEach(div => {
                                        try {
                                            Plotly.Plots.resize(div);
                                        } catch(e) {}
                                    });
                                }, 100);
                            }
                        } else {
                            resultsContainer.innerHTML = `<div class="alert alert-danger">${data.error || 'Erreur'}</div>`;
                        }
                    })
                    .catch(error => {
                        console.error('Erreur AJAX:', error);
                        resultsContainer.innerHTML = '<div class="alert alert-danger">Erreur de chargement</div>';
                    });
            });
        });
        
        // ===== 4. COMPARAISON FAMILLES =====
        const compareFamiliesForms = document.querySelectorAll('form:has(select[name="compare_families"][multiple]):has(select[name="compare_families_metric"])');
        compareFamiliesForms.forEach(form => {
            if (form.hasAttribute('data-ajax-handled')) return;
            form.setAttribute('data-ajax-handled', 'true');
            
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const familiesSelect = this.querySelector('select[name="compare_families"]');
                const selectedFamilies = Array.from(familiesSelect.selectedOptions).map(opt => opt.value);
                const metric = this.querySelector('select[name="compare_families_metric"]').value;
                const granularity = this.querySelector('input[name="granularity"]').value || 'month';
                
                if (selectedFamilies.length === 0) {
                    alert('Veuillez sélectionner au moins une famille');
                    return;
                }
                
                let resultsContainer = this.parentElement.querySelector('.compare-families-results');
                if (!resultsContainer) {
                    // Chercher résultats existants
                    const conditionalResults = Array.from(this.parentElement.children)
                        .find(el => el.classList.contains('mt-3') && !el.querySelector('form'));
                    
                    if (conditionalResults) {
                        resultsContainer = conditionalResults;
                        resultsContainer.classList.add('compare-families-results');
                    } else {
                        resultsContainer = document.createElement('div');
                        resultsContainer.className = 'compare-families-results mt-3';
                        this.parentElement.appendChild(resultsContainer);
                    }
                }
                
                resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Chargement...</span></div></div>';
                
                const params = new URLSearchParams({
                    compare_families_metric: metric,
                    granularity: granularity
                });
                selectedFamilies.forEach(f => params.append('compare_families', f));
                
                fetch(`/dataset/${datasetPk}/ajax/compare-families/?${params}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            injectHTMLWithScripts(resultsContainer, data.html);
                            if (window.Plotly) {
                                setTimeout(() => {
                                    const plotlyDivs = resultsContainer.querySelectorAll('.plotly-graph-div');
                                    plotlyDivs.forEach(div => {
                                        try {
                                            Plotly.Plots.resize(div);
                                        } catch(e) {}
                                    });
                                }, 100);
                            }
                        } else {
                            resultsContainer.innerHTML = `<div class="alert alert-danger">${data.error || 'Erreur'}</div>`;
                        }
                    })
                    .catch(error => {
                        console.error('Erreur AJAX:', error);
                        resultsContainer.innerHTML = '<div class="alert alert-danger">Erreur de chargement</div>';
                    });
            });
        });
        
        console.log('🔄 AJAX forms initialized');
    }
    
    // Initialiser quand le DOM est prêt
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAjaxForms);
    } else {
        initAjaxForms();
    }
})();

// ==========================================
// AJAX TAB LAZY LOADING
// Loads tab content on first click via /ajax/tab/
// ==========================================
(function() {
    'use strict';

    function getDatasetPk() {
        const parts = window.location.pathname.split('/');
        const idx = parts.indexOf('dataset');
        return idx >= 0 ? parts[idx + 1] : null;
    }

    function injectHTMLWithScripts(container, htmlString) {
        const temp = document.createElement('div');
        temp.innerHTML = htmlString;
        const scripts = [];
        temp.querySelectorAll('script').forEach(s => {
            scripts.push(s.src ? {type: 'external', src: s.src} : {type: 'inline', content: s.textContent});
            s.remove();
        });
        container.innerHTML = temp.innerHTML;
        scripts.forEach(s => {
            const el = document.createElement('script');
            if (s.type === 'external') el.src = s.src;
            else el.textContent = s.content;
            container.appendChild(el);
        });
    }

    // Sub-tab pill IDs for each ajax tab name
    const SUB_TAB_PILLS = {
        temporal:   { month: 'temporal-month-tab',  quarter: 'temporal-quarter-tab',  year: 'temporal-fiscal-tab'  },
        products:   { month: 'products-month-tab',  quarter: 'products-quarter-tab',  year: 'products-fiscal-tab'  },
        geographic: { month: 'geo-month-tab',        quarter: 'geo-quarter-tab',        year: 'geo-fiscal-tab'        },
        currency:   { month: 'currency-month-tab',   quarter: 'currency-quarter-tab',   year: 'currency-fiscal-tab'   },
        // clients has no sub-tab pills (single granularity per load)
    };

    function syncPeriodInPane(pane, period) {
        const tabName = pane.dataset.ajaxTab;
        const pillMap = SUB_TAB_PILLS[tabName];
        if (!pillMap) return;
        const pillId = pillMap[period] || pillMap['month'];
        const pill = pane.querySelector('#' + pillId);
        if (pill && window.bootstrap) {
            new bootstrap.Tab(pill).show();
        }
    }

    function resizePlotsIn(pane) {
        if (!window.Plotly) return;
        setTimeout(() => {
            pane.querySelectorAll('.plotly-graph-div').forEach(div => {
                try { Plotly.Plots.resize(div); } catch(e) {}
            });
        }, 250);
    }

    function getCurrentPeriod() {
        const active = document.querySelector('.period-btn.active');
        return active ? active.dataset.period : 'month';
    }

    function loadAjaxTab(pane, datasetPk) {
        if (pane.dataset.ajaxLoaded === 'true') return;

        const tabName = pane.dataset.ajaxTab;
        const period  = getCurrentPeriod();
        const params  = new URLSearchParams({ tab: tabName, granularity: period });

        // Keep spinner visible during load
        fetch(`/dataset/${datasetPk}/ajax/tab/?${params}`)
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    injectHTMLWithScripts(pane, data.html);
                    pane.dataset.ajaxLoaded = 'true';
                    syncPeriodInPane(pane, period);
                    resizePlotsIn(pane);
                } else {
                    pane.innerHTML = `<div class="alert alert-danger mt-4"><i class="bi bi-exclamation-triangle"></i> ${data.error || 'Erreur de chargement'}</div>`;
                }
            })
            .catch(() => {
                pane.innerHTML = '<div class="alert alert-danger mt-4"><i class="bi bi-exclamation-triangle"></i> Erreur réseau lors du chargement.</div>';
            })
            .finally(() => {
                // Masquer le loader si plus aucun onglet n'est en cours de chargement
                const stillLoading = document.querySelectorAll('[data-ajax-tab]:not([data-ajax-loaded])');
                // Un onglet non chargé = placeholder visible = en cours
                const spinners = document.querySelectorAll('[data-ajax-tab] .ajax-tab-placeholder');
                if (spinners.length === 0 && window.hidePageLoader) window.hidePageLoader();
            });
    }

    function reloadPane(pane) {
        loadAjaxTab(pane, getDatasetPk());
    }

    // Expose for use by period selector
    window._ajaxTabSync = { syncPeriodInPane, reloadPane, SUB_TAB_PILLS };

    function initAjaxTabLoading() {
        const datasetPk = getDatasetPk();
        if (!datasetPk) return;

        document.querySelectorAll('#analysisTabs button[data-bs-toggle="tab"]').forEach(btn => {
            btn.addEventListener('shown.bs.tab', function() {
                const pane = document.querySelector(this.dataset.bsTarget);
                if (pane && pane.dataset.ajaxTab) {
                    loadAjaxTab(pane, datasetPk);
                }
            });
        });

        // Load the active AJAX tab on page init (in case URL param pre-selects a tab)
        const activePane = document.querySelector('#analysisTabContent .tab-pane.active[data-ajax-tab]');
        if (activePane) {
            loadAjaxTab(activePane, datasetPk);
        }

        console.log('⚡ AJAX tab lazy loading initialized');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAjaxTabLoading);
    } else {
        initAjaxTabLoading();
    }
})();

// ==========================================
// GLOBAL PAGE LOADER
// Spinner plein écran sur:
//  - clics sur .period-btn (rechargement granularité)
//  - submit de tout formulaire d'analyse (.analysis-form)
//  - submit du formulaire anomalies (#bmForm)
// ==========================================
(function() {
    'use strict';

    // ----- Injection de l'overlay dans le body -----
    function ensureOverlay() {
        let el = document.getElementById('pageLoaderOverlay');
        if (!el) {
            el = document.createElement('div');
            el.id = 'pageLoaderOverlay';
            el.className = 'page-loader-overlay';
            el.innerHTML = '<div class="page-loader-spinner"></div><div class="page-loader-text" id="pageLoaderText">Calcul en cours…</div>';
            document.body.appendChild(el);
        }
        return el;
    }

    function showLoader(text) {
        const overlay = ensureOverlay();
        const textEl = overlay.querySelector('#pageLoaderText');
        if (textEl) textEl.textContent = text || 'Calcul en cours…';
        overlay.classList.add('active');
    }

    function hideLoader() {
        const overlay = document.getElementById('pageLoaderOverlay');
        if (overlay) overlay.classList.remove('active');
    }

    // Expose globally so AJAX handlers can call it
    window.showPageLoader = showLoader;
    window.hidePageLoader = hideLoader;

    function init() {
        ensureOverlay();

        // === 1. Period buttons (stats page) ===
        // Ces boutons déclenchent des reloads AJAX des onglets → on affiche
        // le loader et on le masque quand les fetches sont terminés.
        document.querySelectorAll('.period-btn').forEach(btn => {
            // Les <a> period-btn naviguent → loader simple avant navigation
            if (btn.tagName === 'A') {
                btn.addEventListener('click', function() {
                    showLoader('Changement de période…');
                });
            } else {
                // Les <button> period-btn rechargent les onglets AJAX
                btn.addEventListener('click', function() {
                    showLoader('Changement de période…');
                    // On masque après un délai max (les AJAX reloads gèrent leur propre spinner)
                    setTimeout(hideLoader, 4000);
                });
            }
        });

        // === 2. Formulaires d'analyse avec classe .analysis-form (stats, etc.) ===
        document.querySelectorAll('form.analysis-form').forEach(form => {
            if (form.hasAttribute('data-loader-handled')) return;
            form.setAttribute('data-loader-handled', 'true');
            form.addEventListener('submit', function() {
                showLoader('Analyse en cours…');
            });
        });

        // === 3. Bouton clustering (form POST) ===
        document.querySelectorAll('form[method="post"]').forEach(form => {
            if (form.hasAttribute('data-loader-handled')) return;
            const btn = form.querySelector('button[type="submit"]');
            if (!btn) return;
            form.setAttribute('data-loader-handled', 'true');
            form.addEventListener('submit', function() {
                showLoader('Analyse en cours…');
                // Remplace le texte du bouton
                btn.disabled = true;
                const icon = btn.querySelector('i');
                if (icon) icon.className = '';
                const original = btn.innerHTML;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Calcul…';
                // Restaurer si erreur (ex. validation)
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerHTML = original;
                    hideLoader();
                }, 30000);
            });
        });

        // === 4. Formulaire anomalies / monitoring comportemental (GET) ===
        const bmForm = document.getElementById('bmForm');
        if (bmForm && !bmForm.hasAttribute('data-loader-handled')) {
            bmForm.setAttribute('data-loader-handled', 'true');
            bmForm.addEventListener('submit', function() {
                showLoader('Analyse comportementale…');
            });
        }

        // === 5. Boutons "Analyser" avec data-loader-text ===
        document.querySelectorAll('[data-loader-text]').forEach(el => {
            if (el.hasAttribute('data-loader-handled')) return;
            el.setAttribute('data-loader-handled', 'true');
            el.addEventListener('click', function() {
                showLoader(this.getAttribute('data-loader-text') || 'Calcul…');
            });
        });

        // Cacher le loader quand la page est complètement chargée
        // (au cas où on revient en arrière)
        window.addEventListener('pageshow', hideLoader);
    }

    // Masquer si déjà affiché au chargement (ex: back navigation)
    document.addEventListener('DOMContentLoaded', function() {
        hideLoader();
        init();
    });
    if (document.readyState !== 'loading') {
        hideLoader();
        init();
    }
})();

// ==========================================
// THEME CHANGE HANDLER FOR PLOTLY
// Updates Plotly chart colors when theme switches
// ==========================================
(function() {
    'use strict';

    function getPlotlyThemeColors() {
        const style = getComputedStyle(document.documentElement);
        return {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: style.getPropertyValue('--plotly-bg').trim(),
            font: { color: style.getPropertyValue('--plotly-text').trim() },
            xaxis: {
                gridcolor: style.getPropertyValue('--plotly-grid').trim(),
                zerolinecolor: style.getPropertyValue('--plotly-grid').trim()
            },
            yaxis: {
                gridcolor: style.getPropertyValue('--plotly-grid').trim(),
                zerolinecolor: style.getPropertyValue('--plotly-grid').trim()
            }
        };
    }

    function updatePlotlyTheme() {
        if (!window.Plotly) return;
        const colors = getPlotlyThemeColors();
        document.querySelectorAll('.plotly-graph-div').forEach(div => {
            try {
                Plotly.relayout(div, colors);
            } catch (e) { /* graph not ready */ }
        });
    }

    document.addEventListener('themeChanged', () => {
        setTimeout(updatePlotlyTheme, 100);
    });
})();
