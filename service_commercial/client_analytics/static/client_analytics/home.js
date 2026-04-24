// ==========================================
// HOME.JS - PARTICLES ULTRA-INTENSE SYSTEM
// Canvas avec particules nombreuses, grosses et connectées
// ==========================================

(function() {
    'use strict';
    
    // ===== CONFIGURATION =====
    const CONFIG = {
        particles: {
            count: 100,
            countMobile: 50,
            speed: 1.2,
            size: { min: 6, max: 14 },
            opacity: { min: 0.5, max: 0.95 },
            connectionDistance: 200,
            connectionOpacity: 0.3,
            connectionWidth: 2,
            colors: [
                { r: 149, g: 11, b: 57 },   // Bordeaux
                { r: 197, g: 111, b: 66 },  // Amber
                { r: 218, g: 170, b: 134 }, // Sand
                { r: 255, g: 255, b: 255 }, // White
                { r: 122, g: 8, b: 45 },    // Deep bordeaux
                { r: 255, g: 223, b: 205 }  // Light peach
            ]
        },
        parallax: {
            layer1: 0.04,
            layer2: 0.07,
            layer3: 0.10,
            maxOffset: 18,
            maxOffsetMobile: 6
        }
    };
    
    // Messages typewriter thématique produits protéinés
    const TYPEWRITER_MESSAGES = [
        "Comprenez vos clients. Optimisez vos offres protéinées.",
        "Segmentez les acheteurs : barres, pains, shakers…",
        "Statistiques claires. Clustering actionnable.",
        "Importez vos ventes. Découvrez vos segments."
    ];
    
    // ===== STATE MANAGEMENT =====
    const State = {
        effectsEnabled: true,
        reducedMotion: false,
        isMobile: false,
        isDocumentHidden: false,
        animationFrameId: null,
        particlesAnimationId: null,
        typewriterInterval: null,
        currentMessageIndex: 0
    };
    
    // ===== UTILITY FUNCTIONS =====
    function isMobileDevice() {
        return window.innerWidth <= 768 || 
               /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }
    
    function checkReducedMotion() {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    
    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }
    
    function loadEffectsPreference() {
        const saved = localStorage.getItem('analytics_effects_enabled');
        if (saved !== null) {
            return saved === 'true';
        }
        return !State.reducedMotion;
    }
    
    function saveEffectsPreference(enabled) {
        localStorage.setItem('analytics_effects_enabled', enabled.toString());
    }
    
    // ===== NEURAL NETWORK SYSTEM (BACKGROUND) =====
    const NeuralNetworkSystem = {
        canvas: null,
        ctx: null,
        nodes: [],
        connections: [],
        pulses: [],
        dpr: 1,
        
        init() {
            this.canvas = document.getElementById('neuralNetwork');
            if (!this.canvas) return;
            
            this.ctx = this.canvas.getContext('2d');
            this.dpr = window.devicePixelRatio || 1;
            
            this.resize();
            window.addEventListener('resize', () => this.resize(), { passive: true });
            
            if (State.effectsEnabled && !State.reducedMotion) {
                this.animate();
            }
        },
        
        resize() {
            if (!this.canvas) return;
            
            const parent = this.canvas.parentElement;
            const width = parent.offsetWidth;
            const height = parent.offsetHeight;
            
            this.canvas.width = width * this.dpr;
            this.canvas.height = height * this.dpr;
            this.ctx.scale(this.dpr, this.dpr);
            
            this.canvas.style.width = width + 'px';
            this.canvas.style.height = height + 'px';
            
            this.createNetwork();
        },
        
        createNetwork() {
            if (!this.canvas) return;
            
            const w = this.canvas.width / this.dpr;
            const h = this.canvas.height / this.dpr;
            
            // Créer nœuds (15-20 selon taille écran)
            const nodeCount = State.isMobile ? 20 : 35;
            this.nodes = [];
            
            for (let i = 0; i < nodeCount; i++) {
                const color = CONFIG.particles.colors[Math.floor(Math.random() * CONFIG.particles.colors.length)];
                this.nodes.push({
                    x: Math.random() * w,
                    y: Math.random() * h,
                    vx: (Math.random() - 0.5) * 0.3,
                    vy: (Math.random() - 0.5) * 0.3,
                    size: 6 + Math.random() * 6,
                    color: color,
                    pulsePhase: Math.random() * Math.PI * 2
                });
            }
            
            // Créer connexions (distance max 300px)
            this.connections = [];
            for (let i = 0; i < this.nodes.length; i++) {
                for (let j = i + 1; j < this.nodes.length; j++) {
                    const dx = this.nodes[j].x - this.nodes[i].x;
                    const dy = this.nodes[j].y - this.nodes[i].y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    
                    if (distance < 300) {
                        this.connections.push({
                            from: i,
                            to: j,
                            distance: distance
                        });
                    }
                }
            }
            
            // Initialiser pulses (impulsions lumineuses)
            this.pulses = [];
            this.createRandomPulses();
        },
        
        createRandomPulses() {
            // Créer 3-5 pulses aléatoires
            const pulseCount = 3 + Math.floor(Math.random() * 3);
            for (let i = 0; i < pulseCount; i++) {
                if (this.connections.length > 0) {
                    const conn = this.connections[Math.floor(Math.random() * this.connections.length)];
                    this.pulses.push({
                        connection: conn,
                        progress: Math.random(),
                        speed: 0.005 + Math.random() * 0.01,
                        size: 3 + Math.random() * 3,
                        opacity: 0.6 + Math.random() * 0.4
                    });
                }
            }
        },
        
        animate() {
            if (!this.canvas || !this.ctx) return;
            
            const w = this.canvas.width / this.dpr;
            const h = this.canvas.height / this.dpr;
            
            this.ctx.clearRect(0, 0, w, h);
            
            // Update et draw nodes
            this.nodes.forEach(node => {
                // Move
                node.x += node.vx;
                node.y += node.vy;
                
                // Bounce
                if (node.x < 0 || node.x > w) {
                    node.vx *= -1;
                    node.x = Math.max(0, Math.min(node.x, w));
                }
                if (node.y < 0 || node.y > h) {
                    node.vy *= -1;
                    node.y = Math.max(0, Math.min(node.y, h));
                }
                
                // Pulse animation
                node.pulsePhase += 0.02;
                const pulseFactor = 0.8 + Math.sin(node.pulsePhase) * 0.2;
                const currentSize = node.size * pulseFactor;
                
                // Draw node avec glow
                this.ctx.save();
                
                // Glow
                const glowGradient = this.ctx.createRadialGradient(
                    node.x, node.y, 0,
                    node.x, node.y, currentSize * 4
                );
                glowGradient.addColorStop(0, `rgba(${node.color.r}, ${node.color.g}, ${node.color.b}, 0.4)`);
                glowGradient.addColorStop(0.5, `rgba(${node.color.r}, ${node.color.g}, ${node.color.b}, 0.1)`);
                glowGradient.addColorStop(1, `rgba(${node.color.r}, ${node.color.g}, ${node.color.b}, 0)`);
                
                this.ctx.beginPath();
                this.ctx.arc(node.x, node.y, currentSize * 4, 0, Math.PI * 2);
                this.ctx.fillStyle = glowGradient;
                this.ctx.fill();
                
                // Node core
                this.ctx.beginPath();
                this.ctx.arc(node.x, node.y, currentSize, 0, Math.PI * 2);
                this.ctx.fillStyle = `rgba(${node.color.r}, ${node.color.g}, ${node.color.b}, 0.8)`;
                this.ctx.fill();
                
                // Highlight
                this.ctx.beginPath();
                this.ctx.arc(node.x - currentSize * 0.3, node.y - currentSize * 0.3, currentSize * 0.4, 0, Math.PI * 2);
                this.ctx.fillStyle = `rgba(255, 255, 255, 0.6)`;
                this.ctx.fill();
                
                this.ctx.restore();
            });
            
            // Draw connections
            this.connections.forEach(conn => {
                const fromNode = this.nodes[conn.from];
                const toNode = this.nodes[conn.to];
                
                // Recalculer distance
                const dx = toNode.x - fromNode.x;
                const dy = toNode.y - fromNode.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < 300) {
                    const opacity = (1 - distance / 300) * 0.35;
                    
                    // Gradient line
                    const gradient = this.ctx.createLinearGradient(
                        fromNode.x, fromNode.y, 
                        toNode.x, toNode.y
                    );
                    gradient.addColorStop(0, `rgba(${fromNode.color.r}, ${fromNode.color.g}, ${fromNode.color.b}, ${opacity})`);
                    gradient.addColorStop(1, `rgba(${toNode.color.r}, ${toNode.color.g}, ${toNode.color.b}, ${opacity})`);
                    
                    this.ctx.beginPath();
                    this.ctx.strokeStyle = gradient;
                    this.ctx.lineWidth = 1.8;
                    this.ctx.moveTo(fromNode.x, fromNode.y);
                    this.ctx.lineTo(toNode.x, toNode.y);
                    this.ctx.stroke();
                }
            });
            
            // Update et draw pulses (impulsions lumineuses)
            this.pulses = this.pulses.filter(pulse => {
                pulse.progress += pulse.speed;
                
                if (pulse.progress > 1) {
                    return false; // Remove pulse
                }
                
                const fromNode = this.nodes[pulse.connection.from];
                const toNode = this.nodes[pulse.connection.to];
                
                // Position interpolée
                const x = fromNode.x + (toNode.x - fromNode.x) * pulse.progress;
                const y = fromNode.y + (toNode.y - fromNode.y) * pulse.progress;
                
                // Draw pulse
                this.ctx.save();
                
                // Outer glow
                const glowGradient = this.ctx.createRadialGradient(
                    x, y, 0,
                    x, y, pulse.size * 4
                );
                glowGradient.addColorStop(0, `rgba(255, 255, 255, ${pulse.opacity})`);
                glowGradient.addColorStop(0.5, `rgba(${fromNode.color.r}, ${fromNode.color.g}, ${fromNode.color.b}, ${pulse.opacity * 0.5})`);
                glowGradient.addColorStop(1, `rgba(${fromNode.color.r}, ${fromNode.color.g}, ${fromNode.color.b}, 0)`);
                
                this.ctx.beginPath();
                this.ctx.arc(x, y, pulse.size * 4, 0, Math.PI * 2);
                this.ctx.fillStyle = glowGradient;
                this.ctx.fill();
                
                // Core
                this.ctx.beginPath();
                this.ctx.arc(x, y, pulse.size, 0, Math.PI * 2);
                this.ctx.fillStyle = `rgba(255, 255, 255, ${pulse.opacity})`;
                this.ctx.fill();
                
                this.ctx.restore();
                
                return true;
            });
            
            // Ajouter nouveaux pulses aléatoirement
            if (Math.random() < 0.05 && this.pulses.length < 15) {
                if (this.connections.length > 0) {
                    const conn = this.connections[Math.floor(Math.random() * this.connections.length)];
                    this.pulses.push({
                        connection: conn,
                        progress: 0,
                        speed: 0.005 + Math.random() * 0.01,
                        size: 3 + Math.random() * 3,
                        opacity: 0.6 + Math.random() * 0.4
                    });
                }
            }
            
            // Continue animation
            if (!State.isDocumentHidden && State.effectsEnabled && !State.reducedMotion) {
                this.neuralAnimationId = requestAnimationFrame(() => this.animate());
            }
        },
        
        start() {
            if (!this.neuralAnimationId) {
                this.animate();
            }
        },
        
        stop() {
            if (this.neuralAnimationId) {
                cancelAnimationFrame(this.neuralAnimationId);
                this.neuralAnimationId = null;
            }
        }
    };
    
    // ===== PARTICLES SYSTEM DOUBLE (GLOBAL + HERO) =====
    const ParticlesSystem = {
        // Canvas global (plein écran)
        globalCanvas: null,
        globalCtx: null,
        globalParticles: [],
        
        // Canvas hero (clippé au hero, plus intense)
        heroCanvas: null,
        heroCtx: null,
        heroParticles: [],
        
        dpr: 1,
        animationId: null,
        mouseX: 0,
        mouseY: 0,
        mouseActive: false,
        
        init() {
            this.dpr = window.devicePixelRatio || 1;
            
            // Init canvas global
            this.globalCanvas = document.getElementById('particlesCanvasGlobal');
            if (this.globalCanvas) {
                this.globalCtx = this.globalCanvas.getContext('2d');
                this.resizeGlobal();
            }
            
            // Init canvas hero
            this.heroCanvas = document.getElementById('particlesCanvasHero');
            if (this.heroCanvas) {
                this.heroCtx = this.heroCanvas.getContext('2d');
                this.resizeHero();
            }
            
            // Resize listener
            window.addEventListener('resize', () => {
                this.resizeGlobal();
                this.resizeHero();
            }, { passive: true });
            
            // Mouse interaction (hero seulement)
            const heroSection = document.querySelector('.hero-section');
            if (heroSection) {
                heroSection.addEventListener('mousemove', (e) => {
                    const rect = heroSection.getBoundingClientRect();
                    this.mouseX = e.clientX - rect.left;
                    this.mouseY = e.clientY - rect.top;
                }, { passive: true });
                heroSection.addEventListener('mouseenter', () => { this.mouseActive = true; });
                heroSection.addEventListener('mouseleave', () => { this.mouseActive = false; });
            }
            
            if (State.effectsEnabled && !State.reducedMotion) {
                this.animate();
            }
        },
        
        resizeGlobal() {
            if (!this.globalCanvas) return;
            
            const width = window.innerWidth;
            const height = window.innerHeight;
            
            this.globalCanvas.width = width * this.dpr;
            this.globalCanvas.height = height * this.dpr;
            this.globalCtx.scale(this.dpr, this.dpr);
            
            this.globalCanvas.style.width = width + 'px';
            this.globalCanvas.style.height = height + 'px';
            
            // Créer particules globales (densité augmentée)
            const count = State.isMobile ? 60 : 120;
            this.globalParticles = [];
            
            for (let i = 0; i < count; i++) {
                const color = CONFIG.particles.colors[Math.floor(Math.random() * CONFIG.particles.colors.length)];
                this.globalParticles.push({
                    x: Math.random() * width,
                    y: Math.random() * height,
                    vx: (Math.random() - 0.5) * 0.8,
                    vy: (Math.random() - 0.5) * 0.8,
                    size: 5 + Math.random() * 7,
                    opacity: 0.4 + Math.random() * 0.5,
                    color: color,
                    pulsePhase: Math.random() * Math.PI * 2,
                    pulseSpeed: 0.015 + Math.random() * 0.025
                });
            }
        },
        
        resizeHero() {
            if (!this.heroCanvas) return;
            
            const heroSection = document.querySelector('.hero-section');
            if (!heroSection) return;
            
            const rect = heroSection.getBoundingClientRect();
            const width = rect.width;
            const height = rect.height;
            
            this.heroCanvas.width = width * this.dpr;
            this.heroCanvas.height = height * this.dpr;
            this.heroCtx.scale(this.dpr, this.dpr);
            
            this.heroCanvas.style.width = width + 'px';
            this.heroCanvas.style.height = height + 'px';
            
            // Créer particules hero (haute densité)
            const count = State.isMobile ? 50 : 100;
            this.heroParticles = [];
            
            for (let i = 0; i < count; i++) {
                const color = CONFIG.particles.colors[Math.floor(Math.random() * CONFIG.particles.colors.length)];
                this.heroParticles.push({
                    x: Math.random() * width,
                    y: Math.random() * height,
                    vx: (Math.random() - 0.5) * CONFIG.particles.speed,
                    vy: (Math.random() - 0.5) * CONFIG.particles.speed,
                    size: CONFIG.particles.size.min + Math.random() * (CONFIG.particles.size.max - CONFIG.particles.size.min),
                    opacity: CONFIG.particles.opacity.min + Math.random() * (CONFIG.particles.opacity.max - CONFIG.particles.opacity.min),
                    color: color,
                    pulsePhase: Math.random() * Math.PI * 2,
                    pulseSpeed: 0.02 + Math.random() * 0.03
                });
            }
        },
        
        drawParticle(ctx, particle, currentSize) {
            ctx.save();
            
            // Outer glow
            const gradient = ctx.createRadialGradient(
                particle.x, particle.y, 0,
                particle.x, particle.y, currentSize * 3
            );
            gradient.addColorStop(0, `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, ${particle.opacity})`);
            gradient.addColorStop(0.3, `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, ${particle.opacity * 0.5})`);
            gradient.addColorStop(1, `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, 0)`);
            
            ctx.beginPath();
            ctx.arc(particle.x, particle.y, currentSize * 3, 0, Math.PI * 2);
            ctx.fillStyle = gradient;
            ctx.fill();
            
            // Core particle
            ctx.beginPath();
            ctx.arc(particle.x, particle.y, currentSize, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, ${particle.opacity})`;
            ctx.fill();
            
            // Inner highlight
            ctx.beginPath();
            ctx.arc(particle.x - currentSize * 0.2, particle.y - currentSize * 0.2, currentSize * 0.3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${particle.opacity * 0.6})`;
            ctx.fill();
            
            ctx.restore();
        },
        
        drawConnections(ctx, particles, maxDistance, lineWidth, opacityFactor) {
            particles.forEach((p1, i) => {
                particles.slice(i + 1).forEach(p2 => {
                    const dx = p1.x - p2.x;
                    const dy = p1.y - p2.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    
                    if (distance < maxDistance) {
                        const opacity = (1 - distance / maxDistance) * opacityFactor;
                        
                        const gradient = ctx.createLinearGradient(p1.x, p1.y, p2.x, p2.y);
                        gradient.addColorStop(0, `rgba(${p1.color.r}, ${p1.color.g}, ${p1.color.b}, ${opacity})`);
                        gradient.addColorStop(1, `rgba(${p2.color.r}, ${p2.color.g}, ${p2.color.b}, ${opacity})`);
                        
                        ctx.beginPath();
                        ctx.strokeStyle = gradient;
                        ctx.lineWidth = lineWidth;
                        ctx.moveTo(p1.x, p1.y);
                        ctx.lineTo(p2.x, p2.y);
                        ctx.stroke();
                    }
                });
            });
        },
        
        animate() {
            // Draw global canvas
            if (this.globalCanvas && this.globalCtx) {
                const w = window.innerWidth;
                const h = window.innerHeight;
                
                this.globalCtx.clearRect(0, 0, w, h);
                
                this.globalParticles.forEach(p => {
                    p.pulsePhase += p.pulseSpeed;
                    const pulseFactor = 0.85 + Math.sin(p.pulsePhase) * 0.15;
                    const currentSize = p.size * pulseFactor;
                    
                    p.x += p.vx;
                    p.y += p.vy;
                    
                    if (p.x < 0 || p.x > w) { p.vx *= -1; p.x = Math.max(0, Math.min(p.x, w)); }
                    if (p.y < 0 || p.y > h) { p.vy *= -1; p.y = Math.max(0, Math.min(p.y, h)); }
                    
                    this.drawParticle(this.globalCtx, p, currentSize);
                });
                
                this.drawConnections(this.globalCtx, this.globalParticles, 200, 1.5, 0.25);
            }
            
            // Draw hero canvas
            if (this.heroCanvas && this.heroCtx) {
                const heroSection = document.querySelector('.hero-section');
                if (heroSection) {
                    const rect = heroSection.getBoundingClientRect();
                    const w = rect.width;
                    const h = rect.height;
                    
                    this.heroCtx.clearRect(0, 0, w, h);
                    
                    this.heroParticles.forEach(p => {
                        p.pulsePhase += p.pulseSpeed;
                        const pulseFactor = 0.85 + Math.sin(p.pulsePhase) * 0.15;
                        const currentSize = p.size * pulseFactor;
                        
                        // Mouse attraction
                        if (this.mouseActive && !State.isMobile) {
                            const dx = this.mouseX - p.x;
                            const dy = this.mouseY - p.y;
                            const distance = Math.sqrt(dx * dx + dy * dy);
                            
                            if (distance < 150) {
                                const force = (150 - distance) / 150 * 0.5;
                                p.vx += (dx / distance) * force * 0.1;
                                p.vy += (dy / distance) * force * 0.1;
                            }
                        }
                        
                        p.x += p.vx;
                        p.y += p.vy;
                        
                        if (p.x < 0 || p.x > w) { p.vx *= -1; p.x = Math.max(0, Math.min(p.x, w)); }
                        if (p.y < 0 || p.y > h) { p.vy *= -1; p.y = Math.max(0, Math.min(p.y, h)); }
                        
                        this.drawParticle(this.heroCtx, p, currentSize);
                    });
                    
                    this.drawConnections(this.heroCtx, this.heroParticles, CONFIG.particles.connectionDistance, CONFIG.particles.connectionWidth, CONFIG.particles.connectionOpacity);
                }
            }
            
            // Continue animation
            if (!State.isDocumentHidden && State.effectsEnabled && !State.reducedMotion) {
                this.animationId = requestAnimationFrame(() => this.animate());
            }
        },
        
        start() {
            if (!this.animationId) {
                this.animate();
            }
        },
        
        stop() {
            if (this.animationId) {
                cancelAnimationFrame(this.animationId);
                this.animationId = null;
            }
        }
    };
    
    // ===== PARALLAX SYSTEM (conservé) =====
    const ParallaxSystem = {
        layers: null,
        lastScrollY: 0,
        animationFrameId: null,
        
        init() {
            this.layers = {
                layer1: document.getElementById('parallax-layer-1'),
                layer2: document.getElementById('parallax-layer-2'),
                layer3: document.getElementById('parallax-layer-3')
            };
            
            if (!this.layers.layer1) return;
            
            window.addEventListener('scroll', () => this.onScroll(), { passive: true });
            this.update(0);
        },
        
        onScroll() {
            if (!State.effectsEnabled || State.reducedMotion) return;
            
            this.lastScrollY = window.pageYOffset;
            
            if (!this.animationFrameId) {
                this.animationFrameId = requestAnimationFrame(() => this.animate());
            }
        },
        
        animate() {
            this.update(this.lastScrollY);
            this.animationFrameId = null;
        },
        
        update(scrollY) {
            if (!this.layers.layer1) return;
            
            const maxOffset = State.isMobile ? 
                CONFIG.parallax.maxOffsetMobile : 
                CONFIG.parallax.maxOffset;
            
            const offset1 = clamp(scrollY * CONFIG.parallax.layer1, -maxOffset, maxOffset);
            const offset2 = clamp(scrollY * CONFIG.parallax.layer2, -maxOffset, maxOffset);
            const offset3 = clamp(scrollY * CONFIG.parallax.layer3, -maxOffset, maxOffset);
            
            this.layers.layer1.style.transform = `translateY(${offset1}px)`;
            this.layers.layer2.style.transform = `translateY(${offset2}px)`;
            this.layers.layer3.style.transform = `translateY(${offset3}px)`;
        },
        
        stop() {
            if (this.animationFrameId) {
                cancelAnimationFrame(this.animationFrameId);
                this.animationFrameId = null;
            }
        }
    };
    
    // ===== EFFECTS TOGGLE =====
    const EffectsToggle = {
        button: null,
        
        init() {
            this.createButton();
            this.setupListeners();
        },
        
        createButton() {
            this.button = document.createElement('button');
            this.button.className = 'effects-toggle';
            this.button.setAttribute('aria-label', 'Toggle visual effects');
            this.button.innerHTML = '<i class="bi bi-stars"></i>';
            
            if (State.effectsEnabled) {
                this.button.classList.add('active');
            }
            
            document.body.appendChild(this.button);
        },
        
        setupListeners() {
            this.button.addEventListener('click', () => this.toggle());
        },
        
        toggle() {
            State.effectsEnabled = !State.effectsEnabled;
            saveEffectsPreference(State.effectsEnabled);
            
            if (State.effectsEnabled) {
                this.button.classList.add('active');
                NeuralNetworkSystem.start();
                ParticlesSystem.start();
            } else {
                this.button.classList.remove('active');
                NeuralNetworkSystem.stop();
                ParticlesSystem.stop();
            }
        }
    };
    
    // ===== FORM VALIDATION (UX conservée) =====
    const FormValidation = {
        init() {
            const uploadForm = document.getElementById('uploadForm');
            const uploadBtn = document.getElementById('uploadBtn');
            
            if (uploadForm && uploadBtn) {
                // Essayer plusieurs sélecteurs pour trouver les champs
                const nameInput = uploadForm.querySelector('[name="name"]') || 
                                 uploadForm.querySelector('#id_name') ||
                                 uploadForm.querySelector('input[type="text"]');
                                 
                const fileInput = uploadForm.querySelector('[name="file"]') || 
                                 uploadForm.querySelector('#id_file') ||
                                 uploadForm.querySelector('input[type="file"]');
                
                console.log('🔍 Form elements found:', {
                    nameInput: nameInput ? 'Yes' : 'No',
                    fileInput: fileInput ? 'Yes' : 'No'
                });
                
                if (!nameInput || !fileInput) {
                    console.error('❌ Form inputs not found!');
                    return;
                }
                
                const checkValidity = () => {
                    const isValid = nameInput.value.trim() !== '' && fileInput.files.length > 0;
                    uploadBtn.disabled = !isValid;
                    console.log('✅ Form validation:', {
                        name: nameInput.value.trim(),
                        fileCount: fileInput.files.length,
                        isValid: isValid
                    });
                };
                
                nameInput.addEventListener('input', checkValidity);
                fileInput.addEventListener('change', checkValidity);
                
                // Vérifier immédiatement au chargement
                checkValidity();
                
                uploadForm.addEventListener('submit', () => {
                    uploadBtn.disabled = true;
                    uploadBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Upload en cours...';
                });
            } else {
                console.error('❌ Upload form or button not found!');
            }
            
            const selectForm = document.getElementById('selectForm');
            if (selectForm) {
                selectForm.addEventListener('submit', (e) => {
                    const btn = selectForm.querySelector('button[type="submit"]');
                    btn.disabled = true;
                    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Chargement...';
                });
            }
        }
    };
    
    // ===== SMOOTH SCROLL =====
    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                const href = this.getAttribute('href');
                if (href === '#') return;
                
                const target = document.querySelector(href);
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });
    }
    
    // ===== DOCUMENT VISIBILITY =====
    function handleVisibilityChange() {
        State.isDocumentHidden = document.hidden;
        
        if (State.isDocumentHidden) {
            NeuralNetworkSystem.stop();
            ParticlesSystem.stop();
            ParallaxSystem.stop();
        } else if (State.effectsEnabled && !State.reducedMotion) {
            NeuralNetworkSystem.start();
            ParticlesSystem.start();
        }
    }
    
    // ===== INITIALIZATION =====
    function init() {
        // Detect device & motion preferences
        State.isMobile = isMobileDevice();
        State.reducedMotion = checkReducedMotion();
        State.effectsEnabled = loadEffectsPreference();
        
        // Initialize systems
        ParallaxSystem.init();
        NeuralNetworkSystem.init();
        ParticlesSystem.init();
        TypewriterSystem.init();
        EffectsToggle.init();
        FormValidation.init();
        initSmoothScroll();
        
        // Document visibility
        document.addEventListener('visibilitychange', handleVisibilityChange);
        
        // Resize handler (pas nécessaire pour canvas, géré dans ParticlesSystem.resize)
        
        // Respect reduced motion
        if (State.reducedMotion) {
            State.effectsEnabled = false;
            NeuralNetworkSystem.stop();
            ParticlesSystem.stop();
        }
        
        console.log('✨ Neural Network + Particles Ultra-Intense System initialized');
    }
    
    // Start when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})();
