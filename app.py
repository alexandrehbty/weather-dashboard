from flask import Flask, request, jsonify, render_template
import requests
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Obtenez votre clé API à partir du fichier .env
API_KEY = os.getenv("API_KEY")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_weather')
def get_weather():
    city = request.args.get('city')
    if not city:
        return jsonify({"error": "Veuillez fournir un nom de ville."}), 400

    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",
        "lang": "fr"
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        weather_data = {
            "city": data['name'],
            "temperature": data['main']['temp'],
            "description": data['weather'][0]['description'],
            "icon": data['weather'][0]['icon'],
            "feels_like": data['main']['feels_like'],
            "wind_speed": data['wind']['speed'],
            "humidity": data['main']['humidity'],
            "pressure": data['main']['pressure'],
            "visibility": data['visibility'],
            "sunrise": data['sys']['sunrise'],
            "sunset": data['sys']['sunset']
        }
        return jsonify(weather_data)

    except requests.exceptions.HTTPError as errh:
        return jsonify({"error": f"Erreur HTTP: {errh}"}), 404
    except requests.exceptions.RequestException as err:
        return jsonify({"error": f"Erreur de connexion: {err}"}), 500

if __name__ == '__main__':
    app.run(debug=True)