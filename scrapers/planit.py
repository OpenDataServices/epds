import requests
import datetime
import json
import time
import click
import os
import subprocess
import shutil
import csv
import glob
from hashlib import sha1
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


@click.group()
def cli():
    pass

@click.command()
@click.option('--skipdownload', default=False, is_flag=True)
@click.option('--days', default=15*360)
def full_scrape(skipdownload, days):
    date = datetime.date.today()
    os.makedirs('_planit_output/full', exist_ok=True)

    if not skipdownload:
        download(date, int(days), 'full')

    transform_to_csv()

    sql = f'''
    \copy planit_load(key, file, data, load_date, hash, name) FROM _planit_output/full/all.csv with CSV

    INSERT INTO planit(load_id, name, data, latest_change_date, geom, geog) 
    SELECT 
       id, 
       name,
       data, 
       load_date, 
       ST_MakePoint((data ->> 'location_x')::float, (data ->> 'location_y')::float),
       ST_MakePoint((data ->> 'location_x')::float, (data ->> 'location_y')::float)
    FROM 
       planit_load
    ON CONFLICT DO NOTHING;

    REFRESH MATERIALIZED VIEW CONCURRENTLY near_ibas;
    REFRESH MATERIALIZED VIEW CONCURRENTLY near_rspb_reserves;
    REFRESH MATERIALIZED VIEW CONCURRENTLY planit_key_fields;

    UPDATE planit_load SET new=true, processed=true;
       
    '''
    run_sql(sql)


@click.command()
@click.option('--days', default=180)
def update_scrape(days):
    date = datetime.date.today()
    os.makedirs(f'_planit_output/{str(date)}', exist_ok=True)
    download(date, int(days), str(date))
    transform_to_csv(str(date))

    sql = f'''
    BEGIN;
    CREATE TEMPORARY TABLE planit_load_tmp(key INT, file TEXT, data JSONB, load_date DATE, hash TEXT, name TEXT);
    CREATE INDEX planit_load_tmp_name on planit_load_tmp(name);

    \copy planit_load_tmp(key, file, data, load_date, hash, name) FROM _planit_output/{str(date)}/all.csv with CSV;

    INSERT INTO planit_load(key, file, data, load_date, hash, name, new, changed) 
    SELECT 
      planit_load_tmp.*, CASE WHEN planit.name is null THEN true ELSE false END, CASE WHEN planit.name is null THEN false ELSE true END
    FROM  
      planit_load_tmp
    LEFT JOIN planit USING (name)
    ON CONFLICT DO NOTHING;

    DROP TABLE planit_load_tmp;

    INSERT INTO planit(name, load_id, data, latest_change_date, geom, geog) 
    SELECT 
       name,
       id, 
       data, 
       load_date,
       ST_MakePoint((data ->> 'location_x')::float, (data ->> 'location_y')::float),
       ST_MakePoint((data ->> 'location_x')::float, (data ->> 'location_y')::float)
    FROM 
       planit_load pl
    WHERE
       load_date = '{str(date)}'
    ON CONFLICT (name) DO UPDATE
       set load_id=excluded.load_id, data=excluded.data, latest_change_date=excluded.latest_change_date;

    REFRESH MATERIALIZED VIEW CONCURRENTLY near_ibas;
    REFRESH MATERIALIZED VIEW CONCURRENTLY near_rspb_reserves;
    REFRESH MATERIALIZED VIEW CONCURRENTLY planit_key_fields;
    
    COMMIT
       
    '''
    run_sql(sql)

EMAIL_TEMPLATE = '''
<p>Dear {name}</p>

<p>Here are the list of tree related planning requests found near RSBP reserves or IBAs in Wales:</p>

{matches}
    '''

MATCH_TEMPLATE = '''
<hr>
<b>Name:</b> {name} <br>
<b>Description:</b> {description} <br>
<b>Near:</b> {near} <br>
<b>Address:</b> {address} <br>
<b>Planit URL:</b> {url} <br>
<b>Source URL:</b> {source_url} <br>
<b>Lat Long:</b> {location_x} {location_y}<br>
'''

sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))

@click.command()
@click.option('--date', default=str(datetime.date.today()))
def generate_emails(date):
    csv_output_path = f'_planit_output/{str(date)}/wales-trees-near-ibas-rspb-reserves.csv'

    sql = f'''\copy (
        SELECT pkf.*, 'RSPB Reserve' as near
        FROM planit p
        JOIN planit_load pl on p.load_id = pl.id
        JOIN planit_key_fields pkf on pkf.id = p.id
        JOIN near_rspb_reserves nr on nr.id = p.id
        WHERE load_date = '{str(date)}' and new=true and (app_type = 'Trees' or description ilike '%tree%') and area_name in ('Bridgend','Glamorgan','Cardiff','Caerphilly','Newport','Brecon Beacons','Pembroke Coast','Torfaen','Monmouthshire','Snowdonia','Merthyr Tydfil','Rhondda','Denbighshire','Flintshire','Wrexham','Ceredigion','Pembrokeshire','Carmarthenshire','Swansea','Neath','Blaenau Gwent','Powys','Anglesey','Gwynedd','Conwy')

        UNION

        SELECT pkf.*, 'IBA'
        FROM planit p
        JOIN planit_load pl on p.load_id = pl.id
        JOIN planit_key_fields pkf on pkf.id = p.id
        JOIN near_ibas nr on nr.id = p.id
        WHERE load_date = '{str(date)}' and new=true and (app_type = 'Trees' or description ilike '%tree%') and area_name in ('Bridgend','Glamorgan','Cardiff','Caerphilly','Newport','Brecon Beacons','Pembroke Coast','Torfaen','Monmouthshire','Snowdonia','Merthyr Tydfil','Rhondda','Denbighshire','Flintshire','Wrexham','Ceredigion','Pembrokeshire','Carmarthenshire','Swansea','Neath','Blaenau Gwent','Powys','Anglesey','Gwynedd','Conwy')
        ) TO '{csv_output_path}' with CSV HEADER
    '''

    run_sql(sql.replace('\n',''))

    with open(csv_output_path) as matches_f, open('email_recievers.csv') as recievers_f:
        recievers_reader = csv.DictReader(recievers_f)
        matches_reader = csv.DictReader(matches_f)
        all_matches = list(matches_reader)
        if not all_matches:
            ## no matches do not send any emails
            return

        matches = f"".join([MATCH_TEMPLATE.format(**match) for match in all_matches])

        for reciever in csv.DictReader(recievers_f):
            email_text = EMAIL_TEMPLATE.format(name=reciever['name'], matches=matches)


            message = Mail(
                from_email='code+epds@opendataservices.coop',
                to_emails=reciever['email'],
                subject=f'New Tree planning request near IBA or RSPB Reserve - {date}',
                html_content=email_text)

            response = sg.send(message)
            print(f'Sent email to {reciever["name"]} <{reciever["email"]}>')

            print(response.status_code,
                  response.body, 
                  response.headers)


@click.command()
def clean():
    run_sql('DROP MATERIALIZED VIEW IF EXISTS near_ibas')
    run_sql('DROP MATERIALIZED VIEW IF EXISTS near_rspb_reserves')
    run_sql('DROP MATERIALIZED VIEW IF EXISTS planit_key_fields')
    run_sql('DROP TABLE IF EXISTS planit')
    run_sql('DROP TABLE IF EXISTS planit_load')
    shutil.rmtree('_planit_output')

@click.command()
def setup():
    os.makedirs('_planit_output/full', exist_ok=True)
    run_sql('''
       CREATE TABLE IF NOT EXISTS planit_load(id SERIAL PRIMARY KEY,
                                              key INT,
                                              file TEXT,
                                              data JSONB,
                                              load_date DATE,
                                              hash TEXT,
                                              name TEXT,
                                              new bool DEFAULT FALSE,
                                              changed bool DEFAULT FALSE,
                                              processed bool DEFAULT FALSE);

       CREATE UNIQUE INDEX planit_load_hash_idx ON planit_load(hash);
       CREATE INDEX planit_load_name_idx ON planit_load(name);

       CREATE TABLE IF NOT EXISTS planit(id SERIAL PRIMARY KEY, 
                                         name TEXT, 
                                         load_id bigint, 
                                         data jsonb, 
                                         latest_change_date date);

                                              
       SELECT AddGeometryColumn ('public','planit','geom',4326,'POINT',2);
       ALTER TABLE planit ADD COLUMN geog GEOGRAPHY;

       CREATE UNIQUE INDEX planit_name ON planit(name);

       CREATE INDEX planit_planit_load_id ON planit(load_id);

       CREATE MATERIALIZED VIEW near_ibas AS
            SELECT distinct(id) from planit, ibas WHERE ST_DWithin(ibas.geog, planit.geog, 500, false);

       CREATE UNIQUE INDEX near_ibas_planit_id ON near_ibas(id);

       CREATE MATERIALIZED VIEW near_rspb_reserves AS
            SELECT distinct(id) from planit, rspb_reserves WHERE ST_DWithin(rspb_reserves.geog, planit.geog, 500, false);

       CREATE UNIQUE INDEX near_rspb_reserves_id ON near_rspb_reserves(id);
       
       CREATE MATERIALIZED VIEW planit_key_fields AS
            SELECT
              id,
              data ->> 'address' address,
              data ->> 'altid' altid,
              data ->> 'app_size' app_size,
              data ->> 'app_state' app_state,
              data ->> 'app_type' app_type,
              data ->> 'area_id' area_id,
              data ->> 'area_name' area_name,
              data ->> 'associated_id' associated_id,
              data ->> 'consulted_date' consulted_date,
              data ->> 'decided_date' decided_date,
              data ->> 'description' description,
              data ->> 'docs' docs,
              data ->> 'last_changed' last_changed,
              data ->> 'last_different' last_different,
              data ->> 'last_scraped' last_scraped,
              data ->> 'link' link,
              data -> ' location' -> 'coordinates' location_coordinates,
              data -> 'location' -> 'type' location_type,
              data -> 'location_x' location_x,
              data -> 'location_y' location_y,
              data -> 'name' AS name,
              data -> 'other_fields' -> 'applicant_name' applicant_name,
              data -> 'other_fields' -> 'application_type' application_type,
              data -> 'other_fields' -> 'case_officer' case_officer,
              data -> 'other_fields' -> 'date_received' date_received,
              data -> 'other_fields' -> 'date_validated' date_validated,
              data -> 'other_fields' -> 'decision' decision,
              data -> 'other_fields' -> 'source_url' source_url,
              data ->> 'postcode' postcode,
              data ->> 'reference' reference,
              data ->> 'scraper_name' scraper_name,
              data ->> 'start_date' start_date,
              data ->> 'uid' uid,
              data ->> 'url' url
            from
              planit;

       CREATE UNIQUE INDEX planit_key_fields_id ON planit_key_fields(id);

    ''')


cli.add_command(full_scrape)
cli.add_command(update_scrape)
cli.add_command(clean)
cli.add_command(setup)
cli.add_command(generate_emails)

def run_sql(sql):
    subprocess.run(['psql', os.environ.get('DB_URL', '')], input=sql, text=True, check=True)


def do_scrape(date, path, page=1):
    url = f'https://www.planit.org.uk/api/applics/json?start_date={date}&end_date={date}&pg_sz=3000&page={page}'
    response = requests.get(url)

    if response.status_code == 400:
        time.sleep(30)
        response = requests.get(url)

    json_response = response.json()

    with open(f'_planit_output/{path}/{date}-p{page}.json', 'w+') as outputfile:
        json.dump(json_response, outputfile)

    time.sleep(20)

    return json_response['total']

def download_day(date, path):
    total = do_scrape(date, path)

    if total > 3000:
        do_scrape(date, path, 2)

    if total > 6000:
        do_scrape(date, path, 3)

    if total > 9000:
        do_scrape(date, path, 4)

    if total > 12000:
        do_scrape(date, path, 5)

    if total > 15000:
        raise Exception('can not handle 15000 a day')


def download(today, days, path):
    for days in range(0, days):
        date = str(today - datetime.timedelta(days=days))
        download_day(date, path)


def transform_to_csv(path='full'):
    with open(f'_planit_output/{path}/all.csv', 'w+') as out_csv_file:
        i = 1
        writer = csv.writer(out_csv_file)

        for f in glob.glob(f'_planit_output/{path}/*.json'):
            with open(f) as json_file:
                data = json.load(json_file)
                for item in data['records']:
                    original_json_dump = json.dumps(item)
                    item.pop('last_scraped')
                    writer.writerow([i, f, original_json_dump, str(datetime.date.today()), str(sha1(json.dumps(item).encode()).hexdigest()), item['name']])
                    i += 1


if __name__ == '__main__':
    cli()
