from threading import Lock
import lxml

import camelot
import pandas

from lxml.html import parse

CAMELOT_LOCK = Lock()

headers_pdf = ['Nom', 'Prenom', 'Adresse', 'Tel', 'Email', 'Misc']


def grab(element, xpath_string):
    try:
        return element.xpath(xpath_string)[0].strip()
    except IndexError:
        return ""


def prepare_data_from_html(filename):
    doc = parse(filename).getroot()

    articles = doc.xpath('//article')

    assembled_table = pandas.DataFrame(columns=headers_pdf)
    for article in articles:
        row = {
            # Nom prenom
            headers_pdf[0]:
            grab(article, '((./div)[1]/div)[2]/h4/text()'),
            # Prenom vide
            headers_pdf[1]:
            "",
            # Adresse
            headers_pdf[2]:
            grab(article, './/address/span[@itemprop="streetAddress"]/text()'),
            # Telephone
            headers_pdf[3]:
            grab(article, './/span[@itemprop="telephone"]/text()'),
            # Email
            headers_pdf[4]:
            grab(article, '(./div)[2]/div/a/text()'),
            # Misc
            headers_pdf[5]:
            ", ".join(article.xpath('(./div)[2]//li/text()')),
        }
        assembled_table = assembled_table.append(row, ignore_index=True)

    return assembled_table


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

    return assembled_table
