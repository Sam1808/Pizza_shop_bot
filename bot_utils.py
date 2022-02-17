import requests

from geopy import distance


def fetch_coordinates(apikey, address):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lat, lon


def return_distance_key(org):
    return org['distance']


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
        key=return_distance_key
    )
