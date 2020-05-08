import optparse

import pandas
import camelot

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

assembled_table = pandas.DataFrame(columns=headers_pdf)
for table in tables[1:]:
    print(table.parsing_report)
    tmp = pandas.DataFrame(table.df)
    tmp.columns = headers_pdf
    assembled_table = pandas.concat([assembled_table, tmp])

assembled_table = assembled_table.replace('\n', '', regex=True)
assembled_table['Ville'] = "Lyon"

print(assembled_table)

assembled_table.to_csv(options.out_filename)
