import json
import math
from functools import lru_cache
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CITY_COORDS = {
    "Delhi": (28.6139, 77.2090), "New Delhi": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777), "Bengaluru": (12.9716, 77.5946),
    "Bangalore": (12.9716, 77.5946), "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707), "Kolkata": (22.5726, 88.3639),
    "Pune": (18.5204, 73.8567), "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7872), "Lucknow": (26.8467, 80.9462),
    "Kanpur": (26.4499, 80.3319), "Nagpur": (21.1458, 79.0882),
    "Indore": (22.7196, 75.8577), "Bhopal": (23.2599, 77.4126),
    "Visakhapatnam": (17.6868, 83.2185), "Patna": (25.5941, 85.1376),
    "Vadodara": (22.3072, 73.1812), "Surat": (21.1702, 72.8311),
    "Noida": (28.5355, 77.3910), "Gurgaon": (28.4595, 77.0266),
    "Gurugram": (28.4595, 77.0266), "Chandigarh": (30.7333, 76.7794),
    "Coimbatore": (11.0168, 76.9558), "Kochi": (9.9312, 76.2673),
    "Agra": (27.1767, 78.0081), "Varanasi": (25.3176, 82.9739),
    "Meerut": (28.9845, 77.7064), "Raipur": (21.2514, 81.6296),
    "Ranchi": (23.3441, 85.3096), "Guwahati": (26.1445, 91.7362),
    "Jodhpur": (26.2389, 73.0243), "Amritsar": (31.6340, 74.8723),
    "Faridabad": (28.4089, 77.3178), "Bhubaneswar": (20.2961, 85.8245),
    "Bokaro": (23.6693, 86.1511), "Allahabad": (25.4358, 81.8463),
    "Prayagraj": (25.4358, 81.8463), "Mathura": (27.4924, 77.6737),
    "Bareilly": (28.3670, 79.4304), "Aligarh": (27.8974, 78.0880),
    "Moradabad": (28.8386, 78.7733), "Saharanpur": (29.9680, 77.5460),
    "Gorakhpur": (26.7606, 83.3732), "Firozabad": (27.1591, 78.3957),
    "Jhansi": (25.4484, 78.5685), "Ghaziabad": (28.6692, 77.4538),
    "Ludhiana": (30.9010, 75.8573), "Jalandhar": (31.3260, 75.5762),
    "Dehradun": (30.3165, 78.0322), "Haridwar": (29.9457, 78.1642),
    "Rishikesh": (30.0869, 78.2676), "Shimla": (31.1048, 77.1732),
    "Bathinda": (30.2110, 74.9455), "Unknown": (20.5937, 78.9629),
}

CITY_ALIASES = {
    "bubanesar": "Bhubaneswar",
    "bubaneswar": "Bhubaneswar",
    "bhubaneshwar": "Bhubaneswar",
    "bhubaneswar": "Bhubaneswar",
}


def normalize_location(value: str | None) -> str:
    """Return the best known city name from a city or free-form location."""
    text = " ".join((value or "").replace(",", " ").split()).strip()
    if not text:
        return "Unknown"
    lowered = text.casefold()
    for alias, city in CITY_ALIASES.items():
        if alias in lowered:
            return city
    for city in sorted(CITY_COORDS, key=len, reverse=True):
        if city.casefold() in lowered:
            return city
    return text


def get_city_coordinates(city: str):
    return CITY_COORDS.get(normalize_location(city))


def get_case_map_location(
    city: str | None,
    last_seen: str | None,
    address: str | None,
    latitude: float | None = None,
    longitude: float | None = None,
):
    """Resolve a case location while retaining the most specific text for display."""
    location_text = " / ".join(value.strip() for value in (last_seen, address) if value)
    if latitude is not None and longitude is not None:
        return (latitude, longitude), location_text or city or "Unknown"
    candidates = (last_seen, address, city)
    for candidate in candidates:
        coordinates = get_city_coordinates(candidate or "")
        if coordinates:
            return coordinates, location_text or candidate or "Unknown"
    return get_city_coordinates("Unknown"), location_text or city or "Unknown"


def separate_overlapping_coordinate(coords, seen_coordinates: dict):
    """Keep cases at the same city visible while preserving their exact tooltip."""
    key = (round(coords[0], 5), round(coords[1], 5))
    occurrence = seen_coordinates.get(key, 0)
    seen_coordinates[key] = occurrence + 1
    if occurrence == 0:
        return coords
    ring_position = occurrence - 1
    ring_size = 6
    ring = ring_position // ring_size + 1
    position = ring_position % ring_size
    angle = 2 * math.pi * position / ring_size
    offset = 0.12 * ring
    return coords[0] + offset * math.sin(angle), coords[1] + offset * math.cos(angle)


def resolve_case_map_coordinate(
    city: str | None,
    last_seen: str | None,
    address: str | None,
    latitude: float | None = None,
    longitude: float | None = None,
):
    """Return a finite coordinate for every case, using geocoding before city fallback."""
    if (
        latitude is not None
        and longitude is not None
        and math.isfinite(float(latitude))
        and math.isfinite(float(longitude))
    ):
        return float(latitude), float(longitude)
    return geocode_location(city, last_seen, address)


@lru_cache(maxsize=256)
def geocode_location(city: str | None, last_seen: str | None, address: str | None):
    """Best-effort address geocoding with a short timeout and city fallback."""
    query = ", ".join(value.strip() for value in (address, last_seen, city, "India") if value)
    if query:
        try:
            request = Request(
                "https://nominatim.openstreetmap.org/search?"
                + urlencode({"q": query, "format": "json", "limit": 1}),
                headers={"User-Agent": "missing-person-map/1.0"},
            )
            with urlopen(request, timeout=2) as response:
                results = json.load(response)
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    return get_case_map_location(city, last_seen, address)[0]