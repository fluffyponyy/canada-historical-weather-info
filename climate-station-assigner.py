import json
import pandas as pd
from osgeo import ogr, osr
import math
from owslib.ogcapi.features import Features
from datetime import date

buffer = 7 #km radius for weather stations 

# ESPG code of the preferred projection to create the buffer
# NAD83 / Statistics Canada Lambert
projection = 3347

latitude_to_km = 110.574 #1deg latitude in km
longitude_to_km = 111.320 #*cos(latitude), 1 deg long in km

start_date = date(2000, 1, 1)
end_date = date(2020, 8, 31)
time_ = f"{start_date}/{end_date}"

#1st: find all stations located within a town; 5x5 bounding box
#(convert from lat/long distance to km)
#2nd: when a city is selected, for each station it is attached to, create a new .csv that stores id of city, and calculates daily average temperature recorded for a given day and a given date range

def km_to_deg(lat, km_lat, km_lon):
    deg_lat = km_lat / 111.0
    deg_lon = km_lon / (111.320 * math.cos(math.radians(lat)))
    return deg_lat, deg_lon

cities = pd.read_csv("simplemaps_canadacities_basic/canadacities.csv")
print(cities.head())
for index, city in cities.iterrows():
    city_lat = city['lat']
    city_long = city['lng']
    province = city["province_id"]


    deg_lat, deg_lon = km_to_deg(city_lat, buffer, buffer)
    bbox = [
        city_long - deg_lon,
        city_lat - deg_lat,
        city_long + deg_lon,
        city_lat + deg_lat,
    ]

    oafeat = Features("https://api.weather.gc.ca/")
    station_data = oafeat.collection_items(
        "climate-stations", bbox=bbox
    )

    # Verification of the retrieved data
    if "features" in station_data:
        station_data = json.dumps(station_data, indent=4)
        # for station in station_data["features"]:
        #     props = station["properties"]
        #     identifier = props["CLIMATE_IDENTIFIER"]
        #     print(identifier)
    else:
        raise ValueError(
            "No hydrometric stations were found. Please verify the coordinates."
        )
    
    # List of stations located inside the buffer zone

    # Accessing the hydrometric stations layer
    driver = ogr.GetDriverByName("GeoJSON")
    data_source = driver.Open(station_data, 0)
    layer = data_source.GetLayer()

    # Identification of the input spatial reference system (SRS)
    SRS_input = layer.GetSpatialRef()
    SR = osr.SpatialReference(str(SRS_input))
    epsg = SR.GetAuthorityCode(None)
    SRS_input.ImportFromEPSG(int(epsg))

    # Definition of the SRS used to project data
    SRS_projected = osr.SpatialReference()
    SRS_projected.ImportFromEPSG(projection)

# Transformation from input SRS to the prefered projection
    transform = osr.CoordinateTransformation(SRS_input, SRS_projected)

    # Creation of a buffer to select stations
    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint(city_long, city_lat)
    point.Transform(transform)
    point_buffer = point.Buffer(10 * 1000)  # The value must be in meters

    # Selection of the stations in the buffer zone
    stations = []
    identifiers = []

    for feature in layer:
        geom = feature.GetGeometryRef().Clone()
        geom.Transform(transform)
        if geom.Intersects(point_buffer):
            if(feature.PROV_STATE_TERR_CODE == province):
                stations.append(feature.STATION_NAME)
                identifiers.append(feature.CLIMATE_IDENTIFIER)

    if 'station_names' not in cities.columns:
        cities['station_names'] = None
    if 'station_ids' not in cities.columns:
        cities['station_ids'] = None
    
    cities.at[index, 'station_names'] = stations
    cities.at[index, 'station_ids'] = identifiers

    # Raising an error if no station were found
    if not stations:
        print (
            f"There are no climate stations within {buffer} km"
            + " of the chosen coordinates. Skipping"
        ) 
        continue
    
    cities.to_csv("canadacities_new.csv", sep='\t', encoding='utf-8', index=False, header=True)