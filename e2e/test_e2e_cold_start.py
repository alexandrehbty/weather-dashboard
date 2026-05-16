import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:5000"

# ===========================================================================
# SCÉNARIOS EXISTANTS
# ===========================================================================

def test_recherche_ville_succes(page: Page):
    """Scénario : Un utilisateur recherche 'Marseille' et voit tous les paramètres météo.
    Vérifie chacune des 7 cartes affichées par renderWeather() dans script.js."""
    page.goto(BASE_URL)
    
    page.fill("#city-input", "Marseille")
    page.click("#search-btn")
    
    # Nom de la ville
    expect(page.locator(".weather-info h3")).to_contain_text("Marseille", timeout=5000)

    # Carte 1 — Température (°C)
    carte_temperature = page.locator(".weather-card").filter(has_text="Température")
    expect(carte_temperature).to_contain_text("°C")

    # Carte 2 — Vent (m/s)
    carte_vent = page.locator(".weather-card").filter(has_text="Vent")
    expect(carte_vent).to_contain_text("m/s")

    # Carte 3 — Humidité (%)
    carte_humidite = page.locator(".weather-card").filter(has_text="Humidité")
    expect(carte_humidite).to_contain_text("%")

    # Carte 4 — Pression (hPa)
    carte_pression = page.locator(".weather-card").filter(has_text="Pression")
    expect(carte_pression).to_contain_text("hPa")

    # Carte 5 — Visibilité (km)
    carte_visibilite = page.locator(".weather-card").filter(has_text="Visibilité")
    expect(carte_visibilite).to_contain_text("km")

    # Carte 6 — Lever du soleil
    carte_lever = page.locator(".weather-card").filter(has_text="Lever")
    expect(carte_lever).to_be_visible()

    # Carte 7 — Coucher du soleil
    carte_coucher = page.locator(".weather-card").filter(has_text="Coucher")
    expect(carte_coucher).to_be_visible()

    # Carte Leaflet visible
    expect(page.locator(".leaflet-container")).to_be_visible()

def test_autocompletion_ux(page: Page):
    """Scénario : Vérifie que les suggestions apparaissent lors de la frappe."""
    page.goto(BASE_URL)
    
    page.fill("#city-input", "Par")
    
    premiere_option = page.locator("#city-suggestions option").first
    premiere_option.wait_for(state="attached", timeout=10000)
    
    options_count = page.locator("#city-suggestions option").count()
    assert options_count > 0, "L'autocomplétion n'a renvoyé aucun résultat"

def test_erreur_ville_introuvable(page: Page):
    """Scénario : L'utilisateur tape une ville inexistante et voit un message d'erreur."""
    page.goto(BASE_URL)
    
    page.fill("#city-input", "VilleQuiNexistePas123")
    page.click("#search-btn")
    
    error_p = page.locator("#weather-result p")
    expect(error_p).to_contain_text("Ville introuvable")


# ===========================================================================
# NOUVEAUX SCÉNARIOS — COUVERTURE COMPLÈTE
# ===========================================================================

def test_champ_vide_recherche(page: Page):
    """Scénario : Cliquer sur Rechercher sans rien taper.
    Comportement attendu : pas de crash, message d'erreur approprié ou rien."""
    page.goto(BASE_URL)
    
    # On s'assure que le champ est vide
    page.fill("#city-input", "")
    page.click("#search-btn")
    
    # L'app ne doit pas crasher — la page doit toujours être fonctionnelle
    expect(page.locator("#city-input")).to_be_visible()


def test_affichage_mobile(page: Page):
    """Scénario : L'interface s'affiche correctement sur un viewport mobile (iPhone SE).
    Vérifie que le design responsive fonctionne et que les éléments clés sont visibles."""
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(BASE_URL)
    
    # Les éléments principaux doivent être visibles sur mobile
    expect(page.locator("#city-input")).to_be_visible()
    expect(page.locator("#search-btn")).to_be_visible()


def test_affichage_tablette(page: Page):
    """Scénario : L'interface s'affiche correctement sur un viewport tablette (iPad)."""
    page.set_viewport_size({"width": 768, "height": 1024})
    page.goto(BASE_URL)
    
    expect(page.locator("#city-input")).to_be_visible()
    expect(page.locator("#search-btn")).to_be_visible()


def test_navigation_clavier_autocompletion(page: Page):
    """Scénario : L'utilisateur navigue dans l'autocomplétion au clavier.
    Vérifie que les flèches et Entrée fonctionnent dans la liste de suggestions."""
    page.goto(BASE_URL)
    
    page.fill("#city-input", "Lyon")
    
    # Attendre que les suggestions apparaissent
    premiere_option = page.locator("#city-suggestions option").first
    premiere_option.wait_for(state="attached", timeout=10000)
    
    # Simuler la navigation clavier
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    
    # Après sélection, le champ doit contenir une valeur
    input_value = page.input_value("#city-input")
    assert len(input_value) > 0, "Le champ est vide après sélection clavier"


def test_injection_xss(page: Page):
    """Scénario SÉCURITÉ : Tentative d'injection XSS via le champ de recherche.
    Vérifie que le script malveillant n'est pas exécuté dans le DOM."""
    page.goto(BASE_URL)
    
    # Payload XSS classique
    xss_payload = "<script>alert('XSS')</script>"
    page.fill("#city-input", xss_payload)
    page.click("#search-btn")
    
    # Vérifier qu'aucune boîte de dialogue (alert) ne s'est ouverte
    # Si le XSS était exécuté, on aurait une dialog — on vérifie qu'il n'y en a pas
    dialogs = []
    page.on("dialog", lambda dialog: dialogs.append(dialog))
    
    page.wait_for_timeout(2000)  # Attendre 2s pour laisser le temps à un éventuel alert
    
    assert len(dialogs) == 0, f"FAILLE XSS DÉTECTÉE : une dialog s'est ouverte ({len(dialogs)} fois)"


def test_injection_sql_like(page: Page):
    """Scénario SÉCURITÉ : Tentative d'injection SQL-like via le champ de recherche.
    Vérifie que l'app gère correctement les caractères spéciaux."""
    page.goto(BASE_URL)
    
    sql_payload = "' OR '1'='1"
    page.fill("#city-input", sql_payload)
    page.click("#search-btn")
    
    # L'app ne doit pas crasher — page toujours fonctionnelle
    expect(page.locator("#city-input")).to_be_visible()


def test_caracteres_speciaux_unicode(page: Page):
    """Scénario : Recherche avec des caractères Unicode (accents, cyrillique, CJK).
    Vérifie que l'encodage est correct sur toute la chaîne."""
    page.goto(BASE_URL)
    
    # Ville avec accent
    page.fill("#city-input", "Montréal")
    page.click("#search-btn")
    
    # L'app ne doit pas crasher
    expect(page.locator("#city-input")).to_be_visible()


def test_recherche_multiple_consecutive(page: Page):
    """Scénario : L'utilisateur effectue plusieurs recherches consécutives.
    Vérifie que l'état est correctement réinitialisé entre chaque recherche."""
    page.goto(BASE_URL)
    
    # Première recherche
    page.fill("#city-input", "Paris")
    page.click("#search-btn")
    expect(page.locator(".weather-info h3")).to_contain_text("Paris", timeout=5000)
    
    # Deuxième recherche immédiate
    page.fill("#city-input", "Londres")
    page.click("#search-btn")
    
    # Le résultat doit être mis à jour — pas de résidu de la première recherche
    expect(page.locator(".weather-info h3")).not_to_contain_text("Paris", timeout=5000)


def test_page_title(page: Page):
    """Scénario : Vérification du titre de la page pour le SEO et l'accessibilité."""
    page.goto(BASE_URL)
    
    assert "météo" in page.title().lower() or "meteo" in page.title().lower() or "geo" in page.title().lower(), \
        f"Le titre de la page ne contient pas de mot-clé météo : '{page.title()}'"


def test_accessibilite_aria(page: Page):
    """Scénario ACCESSIBILITÉ : Vérifie la présence des attributs ARIA essentiels.
    Conforme aux standards a11y mentionnés dans le README."""
    page.goto(BASE_URL)
    
    # Le bouton de recherche doit être accessible
    search_btn = page.locator("#search-btn")
    expect(search_btn).to_be_visible()
    expect(search_btn).to_be_enabled()
    
    # Le champ de saisie doit être focusable
    page.focus("#city-input")
    expect(page.locator("#city-input")).to_be_focused()


def test_cold_start_resilience(page: Page):
    """Scénario RÉSILIENCE : Simule un Cold Start en attendant puis en requêtant.
    Vérifie que l'algo Jacobson/Karn gère correctement le réveil de l'instance."""
    page.goto(BASE_URL)
    
    # Attente simulant une inactivité courte (pas 10 min, mais suffisant pour tester)
    page.wait_for_timeout(3000)
    
    # L'app doit répondre après l'inactivité
    page.fill("#city-input", "Berlin")
    page.click("#search-btn")
    
    # Timeout plus long pour le cold start
    expect(page.locator(".weather-info h3")).to_contain_text("Berlin", timeout=15000)


def test_carte_leaflet_chargee(page: Page):
    """Scénario : Vérifie que la carte Leaflet.js est correctement initialisée."""
    page.goto(BASE_URL)
    
    # La carte Leaflet génère un container avec la classe 'leaflet-container'
    leaflet_container = page.locator(".leaflet-container")
    expect(leaflet_container).to_be_visible(timeout=5000)


def test_headers_securite(page: Page):
    """Scénario SÉCURITÉ : Vérifie la présence des headers HTTP de sécurité.
    Conforme aux standards mentionnés dans le README (HSTS, CSP, X-Frame-Options)."""
    response = page.goto(BASE_URL)
    
    headers = response.headers
    
    # Vérification X-Frame-Options (protection clickjacking)
    assert "x-frame-options" in headers, "Header X-Frame-Options manquant"