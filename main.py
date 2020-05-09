import optparse
import hashlib
import pickle

from threading import Lock

import pandas
import camelot

import geopy
import geopy.extra.rate_limiter

import folium

import app

GEOCODE_CACHE_FILE = "geocode_cache.csv"

CAMELOT_LOCK = Lock()


def hasher(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def pull_cache():
    try:
        with open(GEOCODE_CACHE_FILE, "rb") as f:
            return pickle.load(f)
    except:
        print("no cache found for geocodes")
        return {}


def save_cache(geocode_cache):
    with open(GEOCODE_CACHE_FILE, 'wb') as f:  # Just use 'w' mode in 3.x
        pickle.dump(geocode_cache, f)


def fetch_geocode(address, provider_geocode, cache={}):
    """Fetch geocode from address. Will build a cache by default to respect the
    providers servers.

    """
    hash_address = hasher(address)
    if cache and hash_address in cache:
        return cache.get(hash_address)
    else:
        print("fetching {}".format(address))
        point = None
        location = provider_geocode(address)
        if location:
            point = tuple(location.point)
        cache[hash_address] = point
        return point


def add_geocode_to_dataset(dataset, provider, cache=None):
    geocode = geopy.extra.rate_limiter.RateLimiter(provider.geocode,
                                                   min_delay_seconds=.1)

    return dataset.apply(lambda row: fetch_geocode(
        "{} {}".format(row["Adresse"], row["Ville"]), geocode, cache),
                         axis=1)


def prepare_data_from_pdf(pdf_filename, cache=None, csv_filename=None):
    """

    """
    headers_pdf = ['Nom', 'Prenom', 'Adresse', 'Tel']

    with CAMELOT_LOCK:
        tables = camelot.read_pdf(pdf_filename, pages='all')

    # assemble tables from different pages as one.
    assembled_table = pandas.DataFrame()
    for table in tables[1:]:
        tmp = pandas.DataFrame(table.df)
        if assembled_table.size == 0:  # we are dealing with the very first table
            tmp.drop(tmp.head(1).index, inplace=True)  # remove column titles
        tmp.columns = headers_pdf
        assembled_table = pandas.concat([assembled_table, tmp])

    # clean up unnecessary line returns in addresses
    assembled_table = assembled_table.replace('\n', '', regex=True)
    # add utility city column
    assembled_table['Ville'] = "Lyon"

    # save pdf data to csv
    if csv_filename:
        assembled_table.to_csv(csv_filename)

    # add a location column with geocodes
    assembled_table['location'] = add_geocode_to_dataset(
        assembled_table,
        geopy.geocoders.Nominatim(user_agent="assmat-prepare"), cache)

    # save again with geocodes
    if csv_filename:
        assembled_table.to_csv("{}_geocode.csv".format(csv_filename[:-4]))

    # fix encoding for web visualisation
    for field in ["Nom", "Prenom", "Adresse"]:
        assembled_table["w" + field] = assembled_table[field].apply(
            lambda x: repr(bytes(x, encoding="utf-16le"))[2:-1])

    return assembled_table


POPUP_TEMPLATE = ("<b>{wNom:s} {wPrenom!s}</b></br>"
                  "{wAdresse}</br>"
                  "<p><nobr>{Tel}</nobr></p>")


def add_marker(row, fmap, icon, popup_template=POPUP_TEMPLATE):
    """Callback function adding a marker to a folium map
    row: pandas.Series
         Dataframe row should contains a `location` field as a tuple of (lat, long)
    fmap: folium.map
         Will add markers to this map
    icon:
    popup_template: string template

    """
    if row["location"]:
        folium.Marker([row["location"][0], row["location"][1]],
                      popup=popup_template.format(**row),
                      icon=icon).add_to(fmap)


def create_map(data):
    start_lat = 45.7452567
    start_lng = 4.8416748
    folium_map = folium.Map(location=[start_lat, start_lng],
                            zoom_start=15,
                            control_scale=True)

    icon = None
    data.apply(add_marker, axis=1, args=(
        folium_map,
        icon,
    ))

    return folium_map


parser = optparse.OptionParser()
parser.add_option(
    '-i',
    '--input',
    dest="in_filename",
    default="default.pdf",
)

parser.add_option(
    '-o',
    '--output',
    dest="out_filename",
    default=None,
)

parser.add_option("-s", "--save", dest="save_map", default=None)

if __name__ == '__main__':
    options, remainder = parser.parse_args()

    geocode_cache = pull_cache()

    if options.save_map:  # we are in commandline mode
        data = prepare_data_from_pdf(options.in_filename, options.out_filename)
        save_cache(geocode_cache)

        #    data.loc[DATA['location'].isnull()] = add_geocode_to_dataset(
        #        data.loc[DATA['location'].isnull()],
        #        geopy.geocoders.ArcGIS(),
        #        use_cache=False)

        #data['locationarcgis'] = add_geocode_to_dataset(data,
        #                                                geopy.geocoders.ArcGIS(),
        #                                                use_cache=False)
        #data.to_csv("/tmp/compare_geolocators.csv")

        create_map(data).save(options.save_map)
    else:
        app.socketio.run(app.app, debug=True, host="0.0.0.0")
