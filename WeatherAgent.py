"""
By Garrison Moore - 11/19/2026

Resources:
* https://open-meteo.com/en/docs
* https://pypi.org/project/google-genai/
* Google Gemini (Helper)

This program is a harness for Gemini studio API. Uses the LLM to convert basic weather data from Open-Meteo into natural language.

APIs used :
* Google Gemini aistudio API
* Open-Meteo Geocoding API
* Open-Meteo forecast API

 === STEPS TO INSTALL ===

1. 1. Install required packages:
      pip install google-genai requests questionary rich

2. Get a Gemini Studio API key:
      https://aistudio.google.com/api-keys

3. Run this file in a terminal and follow the setup prompt:
      python WeatherAgent_11.py
"""
from datetime import datetime
from google import genai
from google.genai import types
from google.genai.errors import APIError
from rich.console import Console
from rich.markdown import Markdown
from Utils import Tools
import requests
import questionary

# Global for Markdown compatible console
console = Console()

def get_current_weather(city: str, days: int = 7) -> dict:
    """
    Fetches (days) weather forecast for a given city string name.
    """
    # cap maximum days to 16 for open-meteo
    days = max(1, min(days, 16))

    print(f"[Tool Executing] Calling Open-Meteo API\n"
          f"Fetching {days} day forecast for: {city}")
    try:
        # Convert city name to lat / long using Open-Meteo geocoding API
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        # use requests to call the geocoding API
        geo_res = requests.get(geo_url, params={"name": city, "count": 1}, timeout=10)
        geo_res.raise_for_status()
        geo_data = geo_res.json()

        # Fallback if cant find the state, search by city alone
        if not geo_data.get("results") and "," in city:
            plain_city = city.split(",")[0].strip()
            geo_res = requests.get(geo_url, params={"name": plain_city, "count": 1}, timeout=10)
            geo_res.raise_for_status()
            geo_data = geo_res.json()

        if not geo_data.get("results"):
            return {"status": "not_found", "message": f"Could not find coordinates for {city}"}

        # assign final results returned from Open-Meteo
        location = geo_data["results"][0]
        resolved_name = f"{location['name']}, {location.get('admin1', '')}, {location.get('country', '')}"

        # final translated coordinates
        lat = location["latitude"]
        long = location["longitude"]

        # fetch weather from forecast API using the coordinates
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": lat,
            "longitude": long,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "auto",
            "forecast_days": days,
        }
        # use requests to call the forecast API
        weather_res = requests.get(weather_url, params=weather_params, timeout=10)
        # raise_for_status raises an HTTP error if one occurs
        weather_res.raise_for_status()
        # assign the json results as a new variable
        weather_data = weather_res.json()

        # return the weather data
        return {
            "resolved_location": resolved_name,
            "current_weather": weather_data.get("current", {}),
            "current_units": weather_data.get("current_units", {}),
            "daily_weather": weather_data.get("daily", {}),
            "daily_units": weather_data.get("daily_units", {})
        }

    except requests.RequestException as e:
        return {"status": "service_unavailable", "message": f"Weather API request failed {e}"}

def setup():
    """
    Runs initial setup of the Gemini API.
    """
    Tools.clear_terminal()

    # Welcome screen
    print(f"{Tools.BLUE}🌥{Tools.RESET} Welcome to the Weather Agent {Tools.BLUE}🌦{Tools.RESET}"
          "\n* This program only works with Gemini studio API keys. Get one here:"
          "\n   https://aistudio.google.com/api-keys\n")

    # Loop to let the user enter an API key and validates the key by probing the model list endpoint
    while True:
        gem_api_key = input(f"{Tools.CYAN}Enter your Gemini API key: {Tools.RESET}").strip()
        client = genai.Client(api_key=gem_api_key)

        try:
            Tools.clear_terminal()
            print("Checking API key...")

            # probe the model list API endpoint by calling the select_model() function
            selected_model = select_model(client)
            print("Connection Successful.")

            # return the authenticated client and selected model
            return client, selected_model

        except APIError:
            print(f"{Tools.RED}Key invalid, try again{Tools.RESET}")

def select_model(client, current_model=None):
    """
    Fetches available chat models from Google and lets the user pick one.
    """
    available_models = []

    # filtering only available text generation models
    allowed_prefixes = ("gemini-3.", "gemini-4-", "gemma-4-")
    blocked_tags = ("image", "banana", "omni", "tts", "live", "transcribe")

    # loop through all available models returned by the API
    for model in client.models.list():
        # check if model supports text chat
        if "generateContent" in (model.supported_actions or []):
            clean_name = model.name.replace("models/", "")
            # check if the models name has the allowed prefixes and no blocked tags
            if clean_name.startswith(allowed_prefixes) and not any(tag in clean_name for tag in blocked_tags):
                available_models.append(clean_name)

    # add a back option to the list if we have a model selected already
    if current_model:
        available_models.append("<- Back")

    # create the submenu for model selection
    choice = questionary.select(
        "Model Selection:",
        qmark="",
        choices = available_models,
        # if current model is in the list then use it, else assign None
        default=current_model if current_model in available_models else None
    ).ask()

    if choice in ["<- Back", None]:
        return current_model

    return choice

def start_chat(chat, model_name):
    """
    Initializes chat loop with the chosen model.
    """
    print("\nChat initialized. Type 'exit' to quit.\n")

    # chat loop
    while True:
        user_input = input(f"{Tools.ORANGE}You: {Tools.RESET}").strip()

        if user_input.lower() in ["exit", "quit"]:
            break

        if not user_input:
            continue

        # try to send the user input message and receive response
        try:
            # use the braille "dots" spinner for a loading animation until the LLM responds
            with console.status("Waiting for Gemini...", spinner="dots"):
                response = chat.send_message(user_input)
            print(f"\n{Tools.GREEN}{model_name} :{Tools.RESET}")

            if response.text:
                # print LLM response with markdown formatting
                console.print(Markdown(response.text))
            else:
                print("Model did not return a response.")
            print()

        except Exception as e:
            print(f"\n{Tools.RED}API Error {e}{Tools.RESET}\n")

def create_chat(client, model_name):
    """
    Creates a session with the chosen model and the weather tool.
    Defines the LLM's behavior.
    """
    # get the current date for the LLM so it can reference the forecast accurately.
    today = datetime.now().strftime("%A, %B %d, %Y")

    # clients.chats.create automatically manages convo history, agent prompts, and tool calling
    return client.chats.create(
        # passes the model returned in the select_model() function
        model=model_name,
        # generate instructions for the model
        config=types.GenerateContentConfig(
            system_instruction=(
                f"Today's date is {today}. "
                "You are a helpful weather and general assistant. "
                "Pass the whole city name (with state/country abbreviations) to get_current_weather. "
                "If the tool cannot locate the users destination, print the returned error and explain. "
                "If the tool returns status 'service_unavailable', stop immediately and tell the user the weather service is temporarily unreachable and print the returned error—do not retry. "
                "If anything returns an error, print the returned error and explain to the user what the issue may be. "
                "Summarize the returned data and WMO weather codes in plain, conversational language. "
                "Finally, suggest activities and clothing recommendations based on the weather and location. "
            ),
            # give the LLM the get_current_weather() func as a tool
            tools=[get_current_weather],
            # limit function call to 4 per response
            automatic_function_calling = types.AutomaticFunctionCallingConfig(maximum_remote_calls=4),
        )
    )

def main():
    # assign the setup() authenticated client and selected model
    client, current_model = setup()
    # create chat with authenticated client and selected model
    chat = create_chat(client, current_model)

    # Main TUI menu
    while True:
        Tools.clear_terminal()
        model_selection_label = f"Select Model (Current: {current_model})"

        # Main menu
        choice = questionary.select(
            "Main Menu",
            choices = ["Start New Chat",
                       model_selection_label,
                       "Setup",
                       "Quit"
                    ],
            qmark=""
        ).ask()

        if choice == "Start New Chat":
            Tools.clear_terminal()
            start_chat(chat, current_model)

        elif choice == "Setup":
            Tools.clear_terminal()
            client, current_model = setup()
            chat = create_chat(client, current_model)

        elif choice == model_selection_label:
            Tools.clear_terminal()
            new_model = select_model(client, current_model)
            current_model = new_model
            chat = create_chat(client, current_model)

        elif choice in ["Quit", None]:
            print("Exiting.")
            break

if __name__ == "__main__":
    main()