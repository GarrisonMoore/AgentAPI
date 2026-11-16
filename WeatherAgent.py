import os
from asyncio import selector_events
from zoneinfo import available_timezones

import questionary
# === STEPS TO INSTALL ===

# 1. Install google-genai:
#       pip install google-genai

# 2. Install requests for Open-Meteo API:
#       pip install requests

#3. Install questionary for the TUI:
#       pip install questionary rich

# 4. Get a Gemini API key:
#       https://aistudio.google.com/api-keys

from google import genai
from google.genai import types
import requests
from google.genai.errors import APIError


def clear_console():
  os.system('cls' if os.name == 'nt' else 'clear')

def get_current_weather(city: str) -> dict:
    """
    Fetches current weather for a given city name.
    """

    print(f"[Tool Executing] Fetching weather data for: {city}")

    # Convert city name to lat / long using Open-Meteo geocoding API
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_res = requests.get(geo_url, params={"name": city, "count": 1}, timeout=10).json()

    # error if cant find the city
    if not geo_res.get("results"):
        return f"Error: Could not find coordinates for {city}"

    # assign location, lat, long,
    location = geo_res["results"][0]
    lat = location["latitude"]
    long = location["longitude"]
    resolved_name = f"{location['name']}, {location.get('admin1', '')}, {location.get('country', '')})"

    # fetch weather using coordinates
    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_params = {
        "latitude": lat,
        "longitude": long,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph"
    }
    weather_res = requests.get(weather_url, params=weather_params, timeout=10).json()

    return {
        "resolved_location": resolved_name,
        "current_weather": weather_res.get("current", {}),
        "units": weather_res.get("current_units", {})
    }

def start_chat(chat):
    print("\nChat initialized. Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()

        # quit condition
        if user_input.lower() in ["exit", "quit"]:
            break

        # no input condition
        if not user_input:
            continue

        try:
            # try to send the user input message
            print("\nWaiting for Gemini...")
            response = chat.send_message(user_input)
            print(f"\nAgent : {response.text}")
        except Exception as e:
            print(f"\nAPI Error {e}\n")

def select_model(client, current_model=None):
    """
    Fetches available chat models from Google and lets the user pick one.
    """
    available_models = []

    # loop through all available models returned by the API
    for m in client.models.list():
        # check if model supports text chat
        if "generateContent" in (m.supported_actions or []):
            clean_name = m.name.replace("models/", "")
            available_models.append(clean_name)

    if current_model:
        available_models.append("<- Back")

    # create the submenu for model selection
    choice = questionary.select(
        "Model Selection:",
        choices = available_models,
        # if current model is in the list then use it, else assign None
        default=current_model if current_model in available_models else None
    ).ask()

    if choice in ["<- Back", None]:
        return current_model

    return choice

def create_chat(client, model_name):
    """
    Creates a session with  the chosen model and weather tool
    """
    # clients.chats.create automatically manages convo history, agent prompts, and tool calling
    return client.chats.create(
        # Using the free flash lite model
        model="gemini-3.5-flash-lite",
        # generate instructions for the model
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are a helpful weather and general assistant. When a user asks about "
                "the weather, use the get_current_weather tool to fetch live data, then "
                "summarize the conditions (including WMO weather codes) in plain, conversational language."
            ),
            tools=[get_current_weather]
        )
    )

def setup():
    """
    Runs initial setup of the Gemini API.
    """
    clear_console()

    print("Welcome to the Weather Agent."
          "\n* This program only works with Gemini cloud API keys. Get one here:"
          "\n   https://aistudio.google.com/api-keys\n")

    while True:
        gem_api_key = input("Enter your Gemini API key: ").strip()
        client = genai.Client(api_key=gem_api_key)

        try:
            clear_console()
            print("Checking API key...")
            selected_model = select_model(client)
            print("Connection Successful.")
            return client, selected_model

        except APIError:
            print("Key invalid, try again")

def main():
    # call the setup function
    client, current_model = setup()
    chat = create_chat(client, current_model)

    # TUI menu
    while True:

        model_selection_label = f"Select Model (Current: {current_model}"

        choice = questionary.select(
            "\nMain Menu",
            choices = ["Start New Chat",
                       "Setup",
                       model_selection_label,
                       "Quit"
                    ]
        ).ask()

        if choice == "Start New Chat":
            start_chat(chat)

        elif choice == "Setup":
            setup()

        elif choice == model_selection_label:
            new_model = select_model(client, current_model)
            current_model = new_model
            chat = create_chat(client, current_model)

        elif choice in ["Quit", None]:
            print("Exiting.")
            break

if __name__ == "__main__":
    main()