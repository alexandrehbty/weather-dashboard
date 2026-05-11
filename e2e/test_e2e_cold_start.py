import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:5000"

def test_recherche_ville_succes(page: Page):
    """Scénario : Un utilisateur recherche 'Marseille' et voit les résultats."""
    page.goto(BASE_URL)
    
    page.fill("#city-input", "Marseille")
    page.click("#search-btn")
    
    expect(page.locator(".weather-info h3")).to_contain_text("Marseille", timeout=5000)
    
    # CORRECTION : On cible spécifiquement la carte "Température"
    carte_temperature = page.locator(".weather-card").filter(has_text="Température")
    expect(carte_temperature).to_contain_text("°C")

def test_autocompletion_ux(page: Page):
    """Scénario : Vérifie que les suggestions apparaissent lors de la frappe."""
    page.goto(BASE_URL)
    
    page.fill("#city-input", "Par")
    
    # CORRECTION : Attente dynamique (Idéal pour le Cold Start)
    # Le robot attend intelligemment que la première option apparaisse (max 10 secondes)
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