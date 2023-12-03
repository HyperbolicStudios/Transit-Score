import numpy as np
import pandas as pd
import geopandas as gpd
from geopandas.tools import sjoin

import os
from inspect import getsourcefile
from os.path import abspath
import matplotlib.pyplot as plt

import plotly.express as px
#set active directory to file location
directory = abspath(getsourcefile(lambda:0))
#check if system uses forward or backslashes for writing directories
if(directory.rfind("/") != -1):
    newDirectory = directory[:(directory.rfind("/")+1)]
else:
    newDirectory = directory[:(directory.rfind("\\")+1)]
os.chdir(newDirectory)

def transit_score():

    properties = gpd.read_file("CRD Properties/core muni properties dissolved.geojson")
    #drop all columns except geometry and AddressCombined
    properties = properties[['geometry', 'AddressCombined']]

    properties = properties.to_crs('epsg:26910')

    #check for invalid geometries
    properties = properties[properties.is_valid]

    properties['Trip Count'] = 0

    trips = pd.read_csv("transit data/google_transit/trips.txt")
    stop_times = pd.read_csv("transit data/google_transit/stop_times.txt")
    stops = pd.read_csv("transit data/google_transit/stops.txt")
    routes = pd.read_csv("transit data/google_transit/routes.txt")
    calendar = pd.read_csv("transit data/google_transit/calendar.txt")

    stops = stops[['stop_id', 'stop_lat', 'stop_lon']]
    #add route_id to stop_times
    stop_times = stop_times.merge(trips[['trip_id', 'route_id']], on='trip_id')

    #find the service id that is active on monday
    service_id = calendar[calendar.monday == 1]['service_id'].iloc[0]

    trips = trips[trips.service_id == service_id]
    trips = trips[trips.direction_id == 0]

    #filter out stop_times that are not in the service_id
    stop_times = stop_times[stop_times.trip_id.isin(trips.trip_id)]

    #for route in trips.route_id.unique():
    for route in stop_times.route_id.unique():
        route_stop_times = stop_times[stop_times.route_id == route]
        #summarize the number of trips per stop - create a new column called trip_count and set it to 1
        route_stop_times['Route count'] = 1

        route_stop_times = route_stop_times.groupby('stop_id').sum(numeric_only=True).reset_index()
        route_stop_times = route_stop_times[['stop_id', 'Route count']]
        
        route_stops = stops[stops.stop_id.isin(route_stop_times.stop_id)]
        route_stops = route_stops[['stop_id', 'stop_lat', 'stop_lon']]

        #merge route_stops with route_stop_times to get count - this is the number of trips per stop
        route_stops = route_stops.merge(route_stop_times, on='stop_id')

        #convert to geodataframe
        route_stops = gpd.GeoDataFrame(route_stops, geometry=gpd.points_from_xy(route_stops.stop_lon, route_stops.stop_lat))

        #convert to same crs as properties
        route_stops = route_stops.set_crs("epsg:4326").to_crs('epsg:26910')
        route_stops.geometry = route_stops.geometry.buffer(400)

        joined = sjoin(properties, route_stops, how='left', predicate='intersects')

        #aggregate same properties together, using the max value of count
        joined = joined.groupby('AddressCombined').max(numeric_only=True).reset_index()
        joined = joined[['AddressCombined', 'Route count']]
        #replace nan with 0
        joined = joined.fillna(0)

        #merge joined and properties on AddressCombined
        properties = properties.merge(joined, on='AddressCombined', how='left')
        properties['Trip Count'] += properties['Route count']
        properties = properties.drop(columns=['Route count'])

    properties.to_file("transit_scores.geojson", driver='GeoJSON')

    print("Finished transit score")
    return(properties)


def plot_transit_score():
    properties = gpd.read_file("transit_scores.geojson")
    properties = properties.to_crs("epsg:4326")

    #map with plotly
    fig = px.choropleth_mapbox(properties, geojson=properties.geometry, locations=properties.index, color='Trip Count',
                            color_continuous_scale="Viridis",
                            range_color=(0, 200),
                            mapbox_style="carto-positron",
                            zoom=10, center = {"lat": 48.4284, "lon": -123.3656},
                            opacity=0.5,
                            
                            labels={'Trip Count':'Trip Count'}
                              )
    
    #add title
    fig.update_layout(title_text = 'Daily Transit Departures within a 400m')
    #centre title
    fig.update_layout(title_x=0.5)
    #make the title bigger
    fig.update_layout(title_font_size=24)
    fig.update_traces(marker_line_width=0)

    fig.show()

    #to save as html
    fig.write_html("index.html")

#transit_score()
plot_transit_score()
