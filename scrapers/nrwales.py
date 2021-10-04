import click
import dataset
import datetime
import requests

from bs4 import BeautifulSoup


FELLING_LICENSE_REGISTER_URL = "https://naturalresources.wales/permits-and-permissions/tree-felling-and-other-regulations/forestry-public-register/felling-licence-register/?lang=en"

@click.group()
def cli():
    pass


@click.command()
def full_scrape():
    scrape_felling_licenses()


cli.add_command(full_scrape)


def scrape_felling_licenses():
    """
    Reference, Applicant, Site Name, Grid reference, Nearest town, Local Authority, Number of trees to be felled, Hectare, End date for comments
    """
    response = requests.get(FELLING_LICENSE_REGISTER_URL)
    if response.ok:
        soup = BeautifulSoup(response.content, 'html.parser')
        last_updated_date = datetime.datetime.strptime(soup.find(id="gmtLastUpdated")["value"], "%Y-%m-%dT%H:%M:%SZ")
        last_updated = last_updated_date.strftime("%Y-%m-%d %H:%M:%S")

        registry = soup.find('table')
        data = []
        for row in registry.find_all('tr'):
            if len(row.find_all('td')) > 0:
                values = [td.text for td in row.find_all('td')]
                values.append(last_updated)
                data.append(values)


        mapped = map(normalise, data)
        print(list(mapped))


def insert_data(rows):
    db = dataset.connect()
    # planit_load(key, file, data, load_date, hash, name)
    # planit(load_id, name, data, latest_change_date, geom, geog)
    # planit_key_fields
    table = db["tmp_nrwales_load"]


def convert_gridref_to_coords(gridref):
    pass


def normalise(row):
    """
    Maps the scraped table headings onto planit data structure.

    0 Reference
    1 Applicant
    2 Site Name
    3 Grid reference
    4 Nearest town
    5 Local Authority
    6 Number of trees to be felled
    7 Hectare
    8 End date for comments
    9 Last updated date (added by scraper, not in source table)
    """
    mapped = {}
    mapped["other_fields"] = {}
    mapped["uid"] = row[0]
    mapped["reference"] = row[0]
    mapped["other_fields"]["applicant_name"] = row[1]
    mapped["address"] = "%s, %s" % (row[2], row[4])
    mapped["location"] = row[3] # TODO - convert to coords
    mapped["area_name"] = row[5]
    mapped["description"] = "%s trees to be felled over %s hectares" % (row[6], row[7])

    consulted_date = datetime.datetime.strptime(row[8], "%d/%m/%Y")
    mapped["consulted_date"] = consulted_date.strftime("%Y-%m-%d")

    mapped["last_changed"] = row[9]
    mapped["app_type"] = "Trees"
    mapped["url"] = FELLING_LICENSE_REGISTER_URL
    mapped["last_scraped"] = datetime.date.today().strftime("%Y-%m-%d")

    return mapped

if __name__ == '__main__':
    cli()