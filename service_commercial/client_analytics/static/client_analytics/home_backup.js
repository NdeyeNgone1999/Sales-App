// ==========================================
// HOME.JS - Premium Effects System
// Parallax + Particles + Accessibility
// ==========================================

(function() {
    'use strict';
    
    // ===== CONFIGURATION =====
    const CONFIG = {
        particles: {
            count: 60,
            countMobile: 30,
            speed: 0.6,
            size: { min: 4, max: 10 },
            opacity: { min: 0.4, max: 0.9 },
            connectionDistance: 180,
            connectionOpacity: 0.25,
            colors: [
                { r: 240, g: 147, b: 251 }, // Rose
                { r: 102, g: 126, b: 234 }, // Bleu violet
                { r: 79, g: 172, b: 254 },  // Bleu clair
                { r: 0, g: 242, b: 254 },   // Cyan
                { r: 255, g: 255, b: 255 }  // Blanc
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
    
    // ===== STATE MANAGEMENT =====
    const State = {
        effectsEnabled: true,
        reducedMotion: false,
        isMobile: false,
        animationFrameId: null,
        particlesAnimationId: null,
        isDocumentHidden: false
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
        // Default: ON if no reduced motion, OFF otherwise
        return !State.reducedMotion;
    }
    
    function saveEffectsPreference(enabled) {
        localStorage.setItem('analytics_effects_enabled', enabled.toString());
    }
    
    // ===== PARALLAX SYSTEM =====
    const ParallaxSystem = {
        layers: null,
        lastScrollY: 0,
        
        init() {
            this.layers = {
                layer1: document.getElementById('parallax-layer-1'),
                layer2: document.getElementById('parallax-layer-2'),
                layer3: document.getElementById('parallax-layer-3')
            };
            
            if (!this.layers.layer1) return;
            
            // Use passive listener
            window.addEventListener('scroll', () => this.onScroll(), { passive: true });
            
            // Initial position
            this.update(0);
        },
        
        onScroll() {
            if (!State.effectsEnabled || State.reducedMotion) return;
            
            this.lastScrollY = window.pageYOffset;
            
            if (!State.animationFrameId) {
                State.animationFrameId = requestAnimationFrame(() => this.animate());
            }
        },
        
        animate() {
            this.update(this.lastScrollY);
            State.animationFrameId = null;
        },
        
        update(scrollY) {
            if (!this.layers.layer1) return;
            
            const maxOffset = State.isMobile ? 
                CONFIG.parallax.maxOffsetMobile : 
                CONFIG.parallax.maxOffset;
            
            const offset1 = clamp(scrollY * CONFIG.parallax.layer1, 0, maxOffset);
            const offset2 = clamp(scrollY * CONFIG.parallax.layer2, 0, maxOffset);
            const offset3 = clamp(scrollY * CONFIG.parallax.layer3, 0, maxOffset);
            
            if (this.layers.layer1) {
                this.layers.layer1.style.transform = `translateY(${offset1}px)`;
            }
            if (this.layers.layer2) {
                this.layers.layer2.style.transform = `translateY(${offset2}px)`;
            }
            if (this.layers.layer3) {
                this.layers.layer3.style.transform = `translateY(${offset3}px)`;
            }
        },
        
        reset() {
            if (this.layers.layer1) this.layers.layer1.style.transform = 'translateY(0)';
            if (this.layers.layer2) this.layers.layer2.style.transform = 'translateY(0)';
            if (this.layers.layer3) this.layers.layer3.style.transform = 'translateY(0)';
        }
    };
    
    // ===== PARTICLES SYSTEM =====
    const ParticlesSystem = {
        canvas: null,
        ctx: null,
        particles: [],
        dpr: 1,
        
        init() {
            this.canvas = document.getElementById('heroParticles');
            if (!this.canvas) return;
            
            this.ctx = this.canvas.getContext('2d');
            this.dpr = window.devicePixelRatio || 1;
            
            this.resize();
            this.createParticles();
            
            window.addEventListener('resize', () => this.resize());
            
            if (State.effectsEnabled && !State.reducedMotion) {
                this.animate();
            }
        },
        
        resize() {
            if (!this.canvas) return;
            
            // Force canvas to match parent dimensions
            const parent = this.canvas.parentElement;
            const width = parent.offsetWidth;
            const height = parent.offsetHeight;
            
            this.canvas.width = width * this.dpr;
            this.canvas.height = height * this.dpr;
            this.ctx.scale(this.dpr, this.dpr);
            
            this.canvas.style.width = width + 'px';
            this.canvas.style.height = height + 'px';
            
            // Recreate particles on resize
            this.createParticles();
        },
        
        createParticles() {
            if (!this.canvas) return;
            
            const count = State.isMobile ? 
                CONFIG.particles.countMobile : 
                CONFIG.particles.count;
            
            this.particles = [];
            
            for (let i = 0; i < count; i++) {
                const color = CONFIG.particles.colors[Math.floor(Math.random() * CONFIG.particles.colors.length)];
                this.particles.push({
                    x: Math.random() * (this.canvas.width / this.dpr),
                    y: Math.random() * (this.canvas.height / this.dpr),
                    vx: (Math.random() - 0.5) * CONFIG.particles.speed,
                    vy: (Math.random() - 0.5) * CONFIG.particles.speed,
                    size: CONFIG.particles.size.min + 
                          Math.random() * (CONFIG.particles.size.max - CONFIG.particles.size.min),
                    opacity: CONFIG.particles.opacity.min + 
                            Math.random() * (CONFIG.particles.opacity.max - CONFIG.particles.opacity.min),
                    color: color,
                    pulsePhase: Math.random() * Math.PI * 2,
                    pulseSpeed: 0.02 + Math.random() * 0.03
                });
            }
        },
        
        animate() {
            if (!this.canvas || !this.ctx) return;
            
            this.ctx.clearRect(0, 0, this.canvas.width / this.dpr, this.canvas.height / this.dpr);
            
            // Update and draw particles
            this.particles.forEach(particle => {
                // Move
                particle.x += particle.vx;
                particle.y += particle.vy;
                
                // Bounce off edges
                if (particle.x < 0 || particle.x > this.canvas.width / this.dpr) {
                    particle.vx *= -1;
                }
                if (particle.y < 0 || particle.y > this.canvas.height / this.dpr) {
                    particle.vy *= -1;
                }
                
                // Update pulse
                particle.pulsePhase += particle.pulseSpeed;
                const pulseFactor = 0.8 + Math.sin(particle.pulsePhase) * 0.2;
                const currentSize = particle.size * pulseFactor;
                
                // Draw particle with glow effect
                this.ctx.save();
                
                // Outer glow
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
                
                // Core particle
                this.ctx.beginPath();
                this.ctx.arc(particle.x, particle.y, currentSize, 0, Math.PI * 2);
                this.ctx.fillStyle = `rgba(${particle.color.r}, ${particle.color.g}, ${particle.color.b}, ${particle.opacity})`;
                this.ctx.fill();
                
                this.ctx.restore();
            });
            
            // Draw connections (optional, very subtle)
            if (!State.isMobile) {
                this.particles.forEach((p1, i) => {
                    this.particles.slice(i + 1).forEach(p2 => {
                        const dx = p1.x - p2.x;
                        const dy = p1.y - p2.y;
                        const distance = Math.sqrt(dx * dx + dy * dy);
                        
                        if (distance < CONFIG.particles.connectionDistance) {
                            const opacity = (1 - distance / CONFIG.particles.connectionDistance) * 
                                          CONFIG.particles.connectionOpacity;
                            this.ctx.beginPath();
                            this.ctx.strokeStyle = `rgba(255, 255, 255, ${opacity})`;
                            this.ctx.lineWidth = 0.5;
                            this.ctx.moveTo(p1.x, p1.y);
                            this.ctx.lineTo(p2.x, p2.y);
                            this.ctx.stroke();
                        }
                    });
                });
            }
            
            // Continue animation if not paused
            if (!State.isDocumentHidden && State.effectsEnabled && !State.reducedMotion) {
                State.particlesAnimationId = requestAnimationFrame(() => this.animate());
            }
        },
        
        start() {
            if (!State.particlesAnimationId) {
                this.animate();
            }
        },
        
        stop() {
            if (State.particlesAnimationId) {
                cancelAnimationFrame(State.particlesAnimationId);
                State.particlesAnimationId = null;
            }
            if (this.ctx && this.canvas) {
                this.ctx.clearRect(0, 0, this.canvas.width / this.dpr, this.canvas.height / this.dpr);
            }
        }
    };
    
    // ===== EFFECTS TOGGLE =====
    const EffectsToggle = {
        button: null,
        
        init() {
            this.createButton();
            this.updateButtonState();
        },
        
        createButton() {
            const button = document.createElement('button');
            button.id = 'effectsToggle';
            button.className = 'effects-toggle';
            button.setAttribute('aria-label', 'Activer/désactiver les effets visuels');
            button.innerHTML = `
                <i class="bi bi-stars"></i>
                <span class="effects-toggle-text">Effets</span>
            `;
            
            button.addEventListener('click', () => this.toggle());
            
            document.body.appendChild(button);
            this.button = button;
        },
        
        updateButtonState() {
            if (!this.button) return;
            
            if (State.effectsEnabled) {
                this.button.classList.add('active');
                this.button.setAttribute('aria-pressed', 'true');
            } else {
                this.button.classList.remove('active');
                this.button.setAttribute('aria-pressed', 'false');
            }
        },
        
        toggle() {
            State.effectsEnabled = !State.effectsEnabled;
            saveEffectsPreference(State.effectsEnabled);
            this.updateButtonState();
            
            if (State.effectsEnabled && !State.reducedMotion) {
                ParticlesSystem.start();
            } else {
                ParticlesSystem.stop();
                ParallaxSystem.reset();
            }
        }
    };
    
    // ===== FORM VALIDATION & LOADING STATES =====
    function initFormEnhancements() {
        // Upload form validation
        const uploadForm = document.getElementById('uploadForm');
        const uploadBtn = document.getElementById('uploadBtn');
        const nameInput = document.querySelector('input[name="name"]');
        const fileInput = document.querySelector('input[name="file"]');
        
        function checkUploadForm() {
            const hasName = nameInput && nameInput.value.trim() !== '';
            const hasFile = fileInput && fileInput.files.length > 0;
            if (uploadBtn) {
                uploadBtn.disabled = !(hasName && hasFile);
            }
        }
        
        if (nameInput) nameInput.addEventListener('input', checkUploadForm);
        if (fileInput) fileInput.addEventListener('change', checkUploadForm);
        
        // Upload form submit
        if (uploadForm) {
            uploadForm.addEventListener('submit', function() {
                if (uploadBtn) {
                    uploadBtn.disabled = true;
                    uploadBtn.classList.add('btn-loading');
                    uploadBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Upload en cours...';
                }
            });
        }
        
        // Select form submit
        const selectForm = document.getElementById('selectForm');
        const selectBtn = document.getElementById('selectBtn');
        
        if (selectForm && selectBtn) {
            selectForm.addEventListener('submit', function() {
                selectBtn.disabled = true;
                selectBtn.classList.add('btn-loading');
                selectBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Chargement...';
            });
        }
    }
    
    // ===== SMOOTH SCROLL =====
    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }
    
    // ===== DOCUMENT VISIBILITY =====
    function handleVisibilityChange() {
        if (document.hidden) {
            State.isDocumentHidden = true;
            ParticlesSystem.stop();
        } else {
            State.isDocumentHidden = false;
            if (State.effectsEnabled && !State.reducedMotion) {
                ParticlesSystem.start();
            }
        }
    }
    
    // ===== INITIALIZATION =====
    function init() {
        // Check device and motion preferences
        State.isMobile = isMobileDevice();
        State.reducedMotion = checkReducedMotion();
        State.effectsEnabled = loadEffectsPreference();
        
        // If reduced motion is preferred, force disable effects
        if (State.reducedMotion) {
            State.effectsEnabled = false;
        }
        
        // Initialize systems
        ParallaxSystem.init();
        ParticlesSystem.init();
        EffectsToggle.init();
        initFormEnhancements();
        initSmoothScroll();
        
        // Listen for visibility changes
        document.addEventListener('visibilitychange', handleVisibilityChange);
        
        // Listen for motion preference changes
        window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
            State.reducedMotion = e.matches;
            if (State.reducedMotion) {
                State.effectsEnabled = false;
                ParticlesSystem.stop();
                ParallaxSystem.reset();
                EffectsToggle.updateButtonState();
            }
        });
    }
    
    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})();
