import os
import urllib

import pandas as pd
import geopandas as gpd
from geocodio import GeocodioClient
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_TAB = os.getenv("GOOGLE_SHEET_TAB")
GEOCODIO_API_KEY = os.getenv("GEOCODIO_API_KEY")

def sheets_to_df(sheet_id, sheet_tab):

    sheet_name = urllib.parse.quote(sheet_tab)
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

    print(url)

    df = pd.read_csv(url)

    return df

def geocode_rows(df):
    ungeo_df = df.loc[df['center_lng'].isna()]

    if ungeo_df.shape[0] > 0:

        client = GeocodioClient(GEOCODIO_API_KEY)
        ungeo_df['address_or_intersection'] = ungeo_df['address'].combine_first(ungeo_df['intersection'])

        geocode_obj = {}

        for index, row in ungeo_df.iterrows():
            geocode_obj[row['short_title']] = {
                "street": row['address_or_intersection'],
                "city": row['city'],
                "state": "MN"
            }

        geocode_results = client.batch_geocode(geocode_obj)
        # print(geocode_results)

        formatted_results = []

        for index, address in geocode_results.items():
            input_addr = address['input']['formatted_address']
            best_result = address['results'][0]

            formatted_results.append({
                'short_title': index,
                'input_addr': input_addr,
                'geocode_lng': best_result['location']['lng'],
                'geocode_lat': best_result['location']['lat'],
                'accuracy': best_result['accuracy'],
                'accuracy_type': best_result['accuracy_type'],
                'geocode_source': best_result['source'],
            })

        results_df = pd.DataFrame(formatted_results)

        final_df = df.drop(list(df.filter(regex = 'Unnamed')), axis=1).merge(
            results_df,
            how="outer",
            on="short_title"
        )

        # Coalesce lat/lng columns, with priority given to manaully filled out version
        final_df['final_lng'] = final_df['center_lng'].combine_first(final_df['geocode_lng'])
        final_df['final_lat'] = final_df['center_lat'].combine_first(final_df['geocode_lat'])

        final_df.rename(columns={
            'center_lng': 'manual_lng',
            'center_lat': 'manual_lat',
        }, inplace=True)

        return final_df

def export_geojson(df):

    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df.final_lng, df.final_lat)
    )
    df.drop(columns=['final_lng', 'final_lat'], inplace=True)
    # gdf.to_json('exports/cr-points.geojson', drop_id=True)

    os.makedirs('exports', exist_ok=True)
    gdf.to_file('exports/cr-points.geojson', driver="GeoJSON", drop_id=True)

if __name__ == "__main__":
    df = sheets_to_df(GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB)

    # Geocode rows without lat/lng coordinates
    df = geocode_rows(df)

    # Convert to GeoJSON
    geojson = export_geojson(df)
