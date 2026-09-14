import requests

def check_internet_connection(timeout=3):
    """Check whether the weather/API network used by the app is reachable."""
    try:
        requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": 41.0082,
                "longitude": 28.9784,
                "current": "temperature_2m",
                "timezone": "auto",
            },
            timeout=timeout,
        ).raise_for_status()
        return True
    except requests.RequestException:
        return False