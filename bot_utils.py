import requests

from geopy import distance
from funcy import retry


@retry(tries=3, timeout=1)
def fetch_coordinates(apikey, address):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    answer = response.json()
    found_places = answer['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lat, lon


@retry(tries=3, timeout=1)
def get_min_distance(client_position, org_catalog: list):
    for organization in org_catalog:
        org_position = (
            str(organization['pizza_latitude']),
            str(organization['pizza_longitude'])
        )
        organization['distance'] = round(distance.distance(
            client_position, org_position
        ).km, 2)

    return min(
        org_catalog,
        key=lambda org: org['distance']
    )
