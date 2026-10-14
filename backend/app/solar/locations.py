"""Location presets. City centres are approximate; solar resource varies slowly over
distance, so a nearby city is accurate enough and avoids storing a home's location."""

from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    name: str
    lat: float
    lon: float


LEBANESE_CITIES = {
    c.name.lower(): c
    for c in (
        City("Beirut", 33.8938, 35.5018),
        City("Tripoli", 34.4367, 35.8497),
        City("Sidon", 33.5571, 35.3729),
        City("Tyre", 33.2705, 35.2038),
        City("Jounieh", 33.9808, 35.6178),
        City("Byblos", 34.1230, 35.6519),
        City("Zahle", 33.8463, 35.9020),
        City("Baalbek", 34.0047, 36.2110),
        City("Nabatieh", 33.3779, 35.4839),
    )
}

# PVGIS-SARAH3 satellite data covers roughly 65°S-65°N.
MIN_LAT, MAX_LAT = -60.0, 65.0
