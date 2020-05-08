import optparse

import pandas
import camelot

import geopy
import geopy.extra.rate_limiter

import folium

from flask import Flask

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
    default="out.csv",
)

options, remainder = parser.parse_args()

headers_pdf = ['Nom', 'Prenom', 'Adresse', 'Tel']

tables = camelot.read_pdf(options.in_filename, pages='all')

assembled_table = pandas.DataFrame()  #columns=headers_pdf)
for table in tables[1:]:
    print(table.parsing_report)
    tmp = pandas.DataFrame(table.df)
    if assembled_table.size == 0:  # we are dealing with the very first table
        tmp.drop(tmp.head(1).index, inplace=True)  # remove column titles
    tmp.columns = headers_pdf
    assembled_table = pandas.concat([assembled_table, tmp])

assembled_table = assembled_table.replace('\n', '', regex=True)
assembled_table['Ville'] = "Lyon"

assembled_table.loc[:, 'Nom'] = assembled_table['Nom'].apply(
    lambda x: repr(bytes(x, encoding="utf-16le"))[2:-1])
assembled_table.loc[:, 'Prenom'] = assembled_table['Prenom'].apply(
    lambda x: repr(bytes(x, encoding="utf-16le"))[2:-1])

print(assembled_table)

assembled_table.to_csv(options.out_filename)

geolocator = geopy.geocoders.Nominatim(user_agent="assmat-prepare")

geocode = geopy.extra.rate_limiter.RateLimiter(geolocator.geocode,
                                               min_delay_seconds=.1)

df = assembled_table.copy()
df['location'] = df.apply(
    lambda row: geocode("{} {}".format(row["Adresse"], row["Ville"])), axis=1)
df['point'] = df['location'].apply(lambda loc: tuple(loc.point)
                                   if loc else None)

df.to_csv("{}_geocode.csv".format(options.out_filename[:-4]))

popup_template = ("<b>{Nom:s} {Prenom!s}</b></br>" "{Tel}")


def add_marker(row, map, icon):
    if row["point"]:
        folium.Marker([row["point"][0], row["point"][1]],
                      popup=popup_template.format(**row),
                      icon=icon).add_to(map)


app = Flask(__name__)


@app.route('/')
def index():
    start_lat = 45.7434134
    start_lng = 4.8509982
    folium_map = folium.Map(location=[start_lat, start_lng],
                            zoom_start=15,
                            control_scale=True)

    icon = None
    df.apply(add_marker, axis=1, args=(
        folium_map,
        icon,
    ))
    return folium_map._repr_html_()


if __name__ == '__main__':
    app.run(debug=True)
