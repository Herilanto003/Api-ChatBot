"""Outil météo réutilisé depuis le projet `API_WEATHER`.

La fonction `get_information_weather` est conservée telle quelle : elle est
seulement exposée comme outil LangChain via `@tool`.
"""

import json

import requests
from langchain.tools import tool


@tool(
    "get_information_weather",
    description="Return weather information for a valid city",
)
def get_information_weather(city: str) -> str:
    """Retrieve weather data and handle invalid city names."""
    try:
        city = " ".join(city.split())

        if not city:
            return "Erreur : le nom de la ville est vide."

        url = f"https://wttr.in/{city}?format=j1"

        response = requests.get(url, timeout=15)
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            return (
                f"Impossible d'obtenir les données météo pour '{city}'. "
                "Vérifiez le nom de la ville et réessayez."
            )

        # Vérifier que la réponse contient réellement des données météo.
        if not isinstance(data, dict) or not data.get("current_condition"):
            return f"Aucune donnée météo exploitable pour '{city}'. Vérifiez le nom de la ville."

        return json.dumps(data, ensure_ascii=False)

    except requests.RequestException:
        return (
            f"Le service météo est inaccessible pour le moment. "
            f"Impossible de vérifier la ville '{city}'. Réessayez plus tard."
        )
