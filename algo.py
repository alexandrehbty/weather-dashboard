"""
Gestion adaptative des timeouts réseau basée sur les algorithmes de Jacobson et Karn (RFC 6298).

Conçu pour une exécution multi-threadée en mémoire (ex. Gunicorn --workers 1 --threads 4)
sans dépendance externe (pas de Redis requis).
"""

from __future__ import annotations

import math
import threading
import time
from typing import Callable, Dict


class PortfolioBrain:
    """Calcule dynamiquement un timeout de lecture HTTP à partir des latences observées."""

    # Bornes du RTO (Retransmission Timeout) en secondes
    TIMEOUT_MIN: float = 1.0
    TIMEOUT_MAX: float = 10.0
    DEFAULT_TIMEOUT: float = 3.0

    # Paramètres RFC 6298 (Jacobson/Karels)
    ALPHA: float = 0.125
    BETA: float = 0.25
    K: float = 4.0

    # État initial et bornes de la variance
    INITIAL_RTTVAR: float = 0.5
    RTTVAR_MAX: float = 2.5
    FAILURE_RTTVAR_STEP: float = 0.5

    # Seuil d'inactivité (secondes) déclenchant le Soft Decay (Cold Start)
    MEMORY_TTL: float = 600.0
    SOFT_DECAY_MIN_RTTVAR: float = 1.0

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._lock = threading.Lock()
        self._clock = clock

        self.srtt: float = self.DEFAULT_TIMEOUT
        self.rttvar: float = self.INITIAL_RTTVAR
        self.current_timeout: float = self._calc_timeout_unsafe()
        self.last_request_time: float = self._clock()

    def _calc_timeout_unsafe(self) -> float:
        """Calcule le RTO selon RFC 6298 (SRTT + K * RTTVAR). Doit être appelé sous verrou."""
        rto = self.srtt + (self.K * self.rttvar)
        return max(self.TIMEOUT_MIN, min(self.TIMEOUT_MAX, rto))

    def get_timeout(self) -> float:
        """Retourne le timeout à appliquer avant une requête et gère le Soft Decay après inactivité."""
        with self._lock:
            now = self._clock()
            time_since_last = now - self.last_request_time

            if time_since_last > self.MEMORY_TTL:
                # Élargit prudemment la variance au réveil sans effacer l'historique SRTT
                self.rttvar = min(
                    self.RTTVAR_MAX,
                    max(self.rttvar * 2.0, self.SOFT_DECAY_MIN_RTTVAR),
                )
                self.current_timeout = self._calc_timeout_unsafe()
                self.last_request_time = now

            return self.current_timeout

    def update(self, observed_latency: float, success: bool) -> None:
        """Met à jour l'état de l'algorithme après un appel réseau.

        Args:
            observed_latency: Durée de la requête en secondes (ignorée si success=False).
            success: True si le serveur distant a répondu, False en cas de timeout ou d'erreur réseau.
        """
        with self._lock:
            self.last_request_time = self._clock()

            if not success:
                # Règle de Karn : on ignore la latence et on applique un backoff exponentiel
                self.current_timeout = min(self.TIMEOUT_MAX, self.current_timeout * 2.0)
                self.rttvar = min(self.RTTVAR_MAX, self.rttvar + self.FAILURE_RTTVAR_STEP)
                return

            if not isinstance(observed_latency, (int, float)) or not math.isfinite(observed_latency):
                return

            latency = max(0.0, float(observed_latency))

            # Mise à jour RFC 6298 (RTTVAR calculé avant l'actualisation de SRTT)
            diff = latency - self.srtt
            self.rttvar = min(
                self.RTTVAR_MAX,
                self.rttvar + self.BETA * (abs(diff) - self.rttvar),
            )
            self.srtt = self.srtt + self.ALPHA * diff
            self.current_timeout = self._calc_timeout_unsafe()

    def get_stats(self) -> Dict[str, float]:
        """Expose les métriques internes pour l'observabilité (/algo/stats)."""
        with self._lock:
            idle_sec = max(0.0, self._clock() - self.last_request_time)
            return {
                "srtt": round(self.srtt, 3),
                "rttvar": round(self.rttvar, 3),
                "timeout": round(self.current_timeout, 3),
                "idle_sec": round(idle_sec, 1),
            }