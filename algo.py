import time
import threading

class PortfolioBrain:
    """
    Cerveau de gestion des timeouts réseau (Algorithme Jacobson/TCP).
    
    CONTEXTE DE DÉPLOIEMENT :
    -------------------------
    - Plateforme : Render Cloud (Free Tier)
    - Contrainte : 512 Mo RAM max
    - Architecture : Stateless (pas de Redis) -> État stocké en mémoire instance.
    - Concurrence : Thread-Safe (Optimisé pour Gunicorn avec Workers threadés).
    """

    # --- Constantes de Configuration (Optimisées Free Tier) ---
    
    # Plancher de sécurité (1.0s) :
    # Sur un Cloud mutualisé (Free Tier), le CPU peut être throttlé.
    # On laisse une marge d'1s pour ne pas confondre "lenteur CPU" et "panne réseau".
    TIMEOUT_MIN = 1.0
    
    # Plafond UX (10.0s) :
    # Si Render met plus de 10s, l'utilisateur est déjà parti.
    # Autant couper la connexion pour libérer le thread Gunicorn.
    TIMEOUT_MAX = 10.0
    
    DEFAULT_TIMEOUT = 3.0
    
    # Gestion du "Cold Start" (Démarrage à froid) :
    # Les instances Free Tier s'endorment après inactivité.
    # Après 10 min (600s), on considère que le contexte réseau a changé.
    MEMORY_TTL = 600  

    def __init__(self):
        # 🔒 LOCK (THREAD SAFETY) : CRITIQUE SUR 512 Mo RAM
        # Pour économiser la RAM, on utilise des Threads plutôt que des Processus multiples.
        # Ce verrou empêche deux requêtes simultanées de corrompre les calculs de latence.
        self._lock = threading.Lock()

        # --- État initial (Algorithme de Jacobson) ---
        
        # SRTT (Smoothed Round Trip Time) : La "Moyenne"
        # Initialisé à 3s pour être tolérant au démarrage (Cold Start de l'API externe)
        self.srtt = self.DEFAULT_TIMEOUT
        
        # RTTVAR (Round Trip Time Variation) : L' "Incertitude"
        # Initialisé à 0.5s. Plus c'est haut, plus on prend de marge.
        self.rttvar = 0.5
        
        # Le timeout actuel calculé (Ready to use)
        self.current_timeout = self._calc_timeout_unsafe()
        
        self.last_request_time = time.time()

    def _calc_timeout_unsafe(self):
        """
        Calcul pur du RTO (Retransmission Timeout).
        [Interne] Doit toujours être appelé sous Lock.
        """
        # Formule TCP standard (RFC 6298) : Moyenne + 4 * Variation
        # Pourquoi 4 ? Pour couvrir 99.9% des cas statistiques et éviter les faux positifs.
        rto = self.srtt + (4 * self.rttvar)
        
        # Bornage de sécurité (Clamp)
        return max(self.TIMEOUT_MIN, min(self.TIMEOUT_MAX, rto))

    def get_timeout(self):
        """
        Appelé AVANT une requête pour savoir combien de temps attendre.
        Gère intelligemment les réveils de l'instance (Soft Decay).
        """
        with self._lock:
            # 1. Vérification de l'inactivité (Instance endormie ?)
            time_since_last = time.time() - self.last_request_time
            
            if time_since_last > self.MEMORY_TTL:
                # --- STRATÉGIE "SOFT DECAY" ---
                # L'instance se réveille ou n'a pas servi depuis longtemps.
                # On ne reset pas tout (pour garder l'historique), mais on double l'incertitude.
                # Cela élargit le timeout par prudence pour la première requête.
                self.rttvar = max(self.rttvar * 2, 1.0)
                
                # Recalcul immédiat avec cette nouvelle prudence
                self.current_timeout = self._calc_timeout_unsafe()
                
                # On "touche" le timestamp pour ne pas répéter l'opération
                self.last_request_time = time.time()

            return self.current_timeout

    def update(self, observed_latency, success: bool):
        """
        Appelé APRÈS une requête pour nourrir l'algorithme.
        C'est ici que l'apprentissage a lieu.
        
        :param observed_latency: Temps mis par la requête (en secondes)
        :param success: True si le réseau a répondu, False si Timeout/Erreur.
        """
        with self._lock:
            self.last_request_time = time.time()

            if not success:
                # --- PUNITION (Algorithme de Karn) ---
                # Le réseau est instable ou l'API est down.
                # On ignore cette mesure (car faussée) et on double le timeout (Backoff).
                # Cela évite de marteler une API qui souffre déjà (Bonne pratique Cloud).
                self.current_timeout = min(self.TIMEOUT_MAX, self.current_timeout * 2)
                
                # On augmente l'incertitude pour les prochains coups
                self.rttvar += 0.5
            
            else:
                # --- RÉCOMPENSE (Algorithme de Jacobson) ---
                # Tout va bien, on affine le modèle mathématique.
                
                # 1. L'Erreur (Différence entre notre prédiction et la réalité)
                diff = observed_latency - self.srtt
                
                # 2. Mise à jour de la Moyenne (Alpha = 0.125)
                # On lisse doucement (12.5% de poids à la nouvelle mesure)
                self.srtt = self.srtt + (0.125 * diff)
                
                # 3. Mise à jour de la Variance (Beta = 0.25)
                # Si la latence est stable, rttvar diminue -> timeout plus court et réactif.
                # Si la latence fait le yoyo, rttvar augmente -> timeout plus large et sûr.
                self.rttvar = self.rttvar + (0.25 * (abs(diff) - self.rttvar))
                
                # 4. Mise à jour finale
                self.current_timeout = self._calc_timeout_unsafe()

    def get_stats(self):
        """
        Observabilité légère (Pas d'agent Datadog/NewRelic pour économiser la RAM).
        Permet de vérifier la santé du système via des logs simples.
        """
        with self._lock:
            return {
                "srtt": round(self.srtt, 3),            # Latence moyenne estimée
                "rttvar": round(self.rttvar, 3),        # Instabilité du réseau
                "timeout": round(self.current_timeout, 3), # Timeout appliqué
                "idle_sec": round(time.time() - self.last_request_time, 1) # Temps depuis dernier appel
            }