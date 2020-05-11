import lxml

import pandas

from lxml.html import parse

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
