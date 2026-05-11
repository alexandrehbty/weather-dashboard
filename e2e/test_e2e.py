import pytest
from playwright.sync_api import Page, expect

# L'URL de ton serveur Flask local
BASE_URL = "http://127.0.0.1:5000"

def test_recherche_ville_succes(page: Page):
    """
    Scénario : Un utilisateur recherche 'Marseille' et voit les résultats.
    """
    # 1. Navigation vers l'app
    page.goto(BASE_URL)
    
    # 2. Interaction avec le formulaire
    page.fill("#city-input", "Marseille")
    page.click("#search-btn")
    
    # 3. Vérification des résultats (DOM réel)
    # On attend que le titre de la ville s'affiche dans la zone de résultat
    expect(page.locator(".weather-info h3")).to_contain_text("Marseille", timeout=5000)
    
    # On vérifie que la température est affichée (symbole °C présent)
    expect(page.locator("text=Température")).to_be_visible()
    expect(page.locator(".weather-card span")).to_contain_text("°C")

def test_autocompletion_ux(page: Page):
    """
    Scénario : Vérifie que les suggestions apparaissent lors de la frappe.
    """
    page.goto(BASE_URL)
    
    # On tape 'Par' (déclenche le debounce de 300ms dans ton script.js)
    page.fill("#city-input", "Par")
    
    # On attend un peu que l'API Geocoding réponde
    page.wait_for_timeout(1000)
    
    # On vérifie que le datalist contient des suggestions
    # Playwright peut compter les éléments <option> dans le datalist
    options_count = page.locator("#city-suggestions option").count()
    assert options_count > 0, "L'autocomplétion n'a renvoyé aucun résultat"

def test_erreur_ville_introuvable(page: Page):
    """
    Scénario : L'utilisateur tape une ville inexistante et voit un message d'erreur.
    """
    page.goto(BASE_URL)
    
    page.fill("#city-input", "VilleQuiNexistePas123")
    page.click("#search-btn")
    
    # On vérifie que le message d'erreur stylisé (en rouge) apparaît
    error_p = page.locator("#weather-result p")
    expect(error_p).to_contain_text("Ville introuvable")
    
    # Vérification du style (couleur danger définie dans ton CSS)
    # Optionnel, mais montre la puissance du E2E
    color = error_p.evaluate("el => getComputedStyle(el).color")
    assert "rgb(255, 107, 107)" in color  # Correspond à ton --danger (#ff6b6b)