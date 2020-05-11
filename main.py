import optparse
import hashlib
import pickle
import pathlib

from threading import Lock

import pandas
import camelot

import geopy
import geopy.distance
import geopy.extra.rate_limiter

import folium

import app

GEOCODE_CACHE_FILE = "geocode_cache.csv"

CAMELOT_LOCK = Lock()

### Geocoding utilities


def hasher(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def pull_cache(geocode_cache_file=GEOCODE_CACHE_FILE):
    try:
        with open(geocode_cache_file, "rb") as f:
            return pickle.load(f)
    except:
        print("no cache found for geocodes")
        return {}


def save_cache(geocode_cache, geocode_cache_file=GEOCODE_CACHE_FILE):
    with open(geocode_cache_file, 'wb') as f:  # Just use 'w' mode in 3.x
        pickle.dump(geocode_cache, f)


def fetch_geocode(address, provider_geocode, cache=None):
    """Fetch geocode from address. Will build a cache by default to respect the
    providers servers.

    """
    hash_address = hasher(address + provider_geocode.func.__qualname__)
    if cache and hash_address in cache:
        return cache.get(hash_address)
    else:
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


## Data processing


def prepare_data_from_pdf(pdf_filename):
    """Prepare data into a Dataframe from a pdf file

    """
    headers_pdf = ['Nom', 'Prenom', 'Adresse', 'Tel']

    with CAMELOT_LOCK:
        tables = camelot.read_pdf(pdf_filename, pages='all')

    assembled_table = pandas.DataFrame(columns=headers_pdf)
    if len(tables) < 2:
        raise ValueError(
            "Le document est illisible (scanné ?) ou ne contient pas 2 tableaux sur sa première page"
        )
    elif tables[1].shape[1] != 4:
        raise ValueError(
            "{} colonnes trouvées. Il ne devrait y en avoir 4 exactement :</br> Attendu {}"
            .format(tables[1].shape[1],
                    ["Nom", "Prenom", "Adresse", "Telephone 1"]))
    else:
        # assemble tables from different pages as one.
        #assembled_table = pandas.DataFrame()
        for table in tables[1:]:
            tmp = pandas.DataFrame(table.df)
            if assembled_table.size == 0:  # we are dealing with the very first table
                tmp.drop(tmp.head(1).index,
                         inplace=True)  # remove column titles
            tmp.columns = headers_pdf
            assembled_table = pandas.concat([assembled_table, tmp])

    assembled_table['Email'] = ""
    assembled_table['Misc'] = ""

    return assembled_table


def enrich_data(assembled_table, cache=None, csv_filename=None):

    # clean up unnecessary line returns in addresses
    assembled_table = assembled_table.replace('\n', '', regex=True)
    # add utility city column
    assembled_table['Ville'] = "Lyon"

    # save pdf data to csv
    if csv_filename:
        assembled_table.to_csv(csv_filename)

    try:
        # add a location column with geocodes
        assembled_table['location'] = add_geocode_to_dataset(
            assembled_table,
            geopy.geocoders.Nominatim(user_agent="assmat-prepare"), cache)

        assembled_table['locationarcgis'] = add_geocode_to_dataset(
            assembled_table, geopy.geocoders.ArcGIS(), cache=cache)
    except Exception as e:
        raise RuntimeError(
            "Erreur dans la géocodification des adresses : Les fournisseurs sont peut-être indisponibles"
        ) from e

    # save again with geocodes
    if csv_filename:
        assembled_table.to_csv("{}_geocode.csv".format(csv_filename[:-4]))

    try:
        # fix encoding for web visualisation
        for field in ["Nom", "Prenom", "Adresse", "Misc"]:
            assembled_table["w" + field] = assembled_table[field].apply(
                lambda x: repr(bytes(x, encoding="utf-16le"))[2:-1])
    except:
        raise RuntimeError("Erreur dans les adresses reçus")

    try:
        d = geopy.distance.distance

        # distance between argis and nominatim data
        assembled_table['diff'] = assembled_table.apply(
            lambda row: d(row['location'], row['locationarcgis']), axis=1)
        # > 50m
        assembled_table['dif50'] = assembled_table.apply(
            lambda row: d(row['location'], row['locationarcgis']) > .05,
            axis=1)
        # > 100m
        assembled_table['dif100'] = assembled_table.apply(
            lambda row: d(row['location'], row['locationarcgis']) > .1, axis=1)
        # > 500m
        assembled_table['dif500'] = assembled_table.apply(
            lambda row: d(row['location'], row['locationarcgis']) > .5, axis=1)
        # distance of nominatim geocode \to the center of Lyon [Jean Mace]
        assembled_table['tocentern'] = assembled_table.apply(
            lambda row: d(row['location'], (45.7452567, 4.8416748, 0)), axis=1)
        # distance of ArcGIS geocode \to the center of Lyon [Jean Mace]
        assembled_table['tocentera'] = assembled_table.apply(
            lambda row: d(row['locationarcgis'], (45.7452567, 4.8416748, 0)),
            axis=1)
    except:
        raise RuntimeError(
            "Les traitements complémentaires n'ont pu être effectués")

    return assembled_table


## Map visualisation
import legend

POPUP_TEMPLATE = ("<b>{wNom:s} {wPrenom!s}</b></br>"
                  "{wAdresse}</br>"
                  "<p><nobr>{Tel}</nobr></br><nobr>{Email}</nobr></p>"
                  "<p>{Misc}<p>")


def add_marker(row, fmap, icon, popup_template=POPUP_TEMPLATE):
    """Callback function adding a marker to a folium map
    row: pandas.Series
         Dataframe row should contains a `location` field as a tuple of (lat, long)
    fmap: folium.map
         Will add markers to this map
    icon:
    popup_template: string template

    """
    location_field = "locationarcgis"
    icon = folium.map.Icon(
        color='orange' if row["dif50"] or row["tocentera"] > 20
        or row["tocentern"] > 20 else 'blue',
        icon='user')
    if row[location_field]:
        folium.Marker([row[location_field][0], row[location_field][1]],
                      popup=popup_template.format(**row),
                      icon=icon).add_to(fmap)


def create_map(data):
    start_lat = 45.7452567
    start_lng = 4.8416748
    folium_map = folium.Map(location=[start_lat, start_lng],
                            zoom_start=14,
                            control_scale=True)

    icon = None
    data.apply(add_marker, axis=1, args=(
        folium_map,
        icon,
    ))

    folium_map = legend.add_categorical_legend(folium_map,
                                               "Positionnement",
                                               colors=['#59c7f9', 'orange'],
                                               labels=['correct', 'incertain'])

    return folium_map


import grandlyon

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option(
        '-i',
        '--input',
        dest="in_filename",
        default=None,
    )

    parser.add_option(
        '-o',
        '--output',
        dest="out_filename",
        default=None,
    )

    parser.add_option("-s", "--save", dest="save_map", default=None)

    options, remainder = parser.parse_args()

    if options.in_filename:  # we are in commandline mode

        data = None
        if pathlib.Path(options.in_filename) == ".pdf":
            dataN = prepare_data_from_pdf(options.in_filename)
            dataN = enrich_data(dataN, geocode_cache, csv_filename=None)
            #dataS = prepare_data_from_pdf(
            #    "/tmp/Copie de edition ass mat au 06-03-2020 (SUD)-.pdf",
            #    geocode_cache, options.out_filename)
            #data = pandas.concat([dataS, dataN])
            data = dataN
        elif pathlib.Path(options.in_filename) in [".html", "htm"]:
            data = grandlyon.prepare_data_from_html(options.in_filename)

        geocode_cache = pull_cache()
        data = enrich_data(data,
                           geocode_cache,
                           csv_filename=options.out_filename)

        #    data.loc[DATA['location'].isnull()] = add_geocode_to_dataset(
        #        data.loc[DATA['location'].isnull()],
        #        geopy.geocoders.ArcGIS(),
        #        use_cache=False)

        #data.to_csv("/tmp/compare_geolocators.csv")
        save_cache(geocode_cache)

        print(data)
        print(data.shape)
        print(data.loc[data['location'].isnull()
                       & data['locationarcgis'].isnull()])

        if options.save_map:
            create_map(data).save(options.save_map)

    else:
        app.socketio.run(app.app, host="0.0.0.0")
