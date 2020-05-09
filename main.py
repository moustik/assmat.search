import os.path

import optparse
import hashlib
import pickle

from threading import Lock

import pandas
import camelot

import geopy
import geopy.extra.rate_limiter

import folium

from flask import Flask, render_template, request, redirect
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit

GEOCODE_CACHE = {}
GEOCODE_CACHE_FILE = "geocode_cache.csv"

CAMELOT_MUTEX = Lock()


def hasher(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def pull_cache():
    try:
        with open(GEOCODE_CACHE_FILE, "rb") as f:
            return pickle.load(f)
    except:
        print("no cache found for geocodes")
        return {}


def save_cache():
    with open(GEOCODE_CACHE_FILE, 'wb') as f:  # Just use 'w' mode in 3.x
        pickle.dump(GEOCODE_CACHE, f)


def fetch_geocode(address, provider_geocode, use_cache=True):
    """Fetch geocode from address. Will build a cache by default to respect the
    providers servers.

    """
    hash_address = hasher(address)
    if use_cache and hash_address in GEOCODE_CACHE:
        return GEOCODE_CACHE.get(hash_address)
    else:
        print("fetching {}".format(address))
        point = None
        location = provider_geocode(address)
        if location:
            point = tuple(location.point)
        GEOCODE_CACHE[hash_address] = point
        return point


def add_geocode_to_dataset(dataset, provider, use_cache=True):
    geocode = geopy.extra.rate_limiter.RateLimiter(provider.geocode,
                                                   min_delay_seconds=.1)

    return dataset.apply(lambda row: fetch_geocode(
        "{} {}".format(row["Adresse"], row["Ville"]), geocode, use_cache),
                         axis=1)


def prepare_data_from_pdf(pdf_filename, csv_filename=None):
    """

    """
    headers_pdf = ['Nom', 'Prenom', 'Adresse', 'Tel']

    with CAMELOT_MUTEX:
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
        geopy.geocoders.Nominatim(user_agent="assmat-prepare"))

    # save again with geocodes
    if csv_filename:
        assembled_table.to_csv("{}_geocode.csv".format(csv_filename[:-4]))

    # fix encoding for web visualisation
    for field in ["Nom", "Prenom", "Adresse"]:
        assembled_table["w" + field] = assembled_table[field].apply(
            lambda x: repr(bytes(x, encoding="utf-16le"))[2:-1])

    save_cache()
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


app = Flask(__name__)
bootstrap = Bootstrap()
bootstrap.init_app(app)
socketio = SocketIO(app)

app.config["IMAGE_UPLOADS"] = "/tmp/uploads"


@socketio.on('client_connected', namespace='/test')
def handle_client_connect_event(json):
    print('received json: {0}'.format(str(json)))


@app.route("/", methods=["GET"])
def upload():
    return render_template("upload.html")


@app.route("/view", methods=["GET", "POST"])
def view_data():
    request.sid = request.form.get("sid", None)
    if request.method == "POST":
        if request.files:
            pdf_file = request.files["pdf"]
            if pdf_file.filename == "":
                print("No filename")
                return redirect(request.url)
            filename = secure_filename("{}.{}.pdf".format(
                pdf_file.filename[:-4], request.sid))

            pdf_filename = os.path.join(app.config["IMAGE_UPLOADS"], filename)
            pdf_file.save(pdf_filename)
            emit('display_message',
                 {'data': "Fichier téléversé, traitement en cours"},
                 namespace='/test')

            GEOCODE_CACHE = pull_cache()
            data = prepare_data_from_pdf(pdf_filename)
            emit('display_message',
                 {'data': "Traitement terminé. La carte arrive"},
                 namespace='/test')

            return create_map(data)._repr_html_()
    return None


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

    GEOCODE_CACHE = pull_cache()

    if options.save_map:  # we are in commandline mode
        data = prepare_data_from_pdf(options.in_filename, options.out_filename)
        save_cache()

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
        socketio.run(app, debug=True)
