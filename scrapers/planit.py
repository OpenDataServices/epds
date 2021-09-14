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


@click.group()
def cli():
    pass

@click.command()
@click.option('--download/--no-download', default=True)
def full_scrape(download):
    date = datetime.date.today()
    os.makedirs('_planit_output/full', exist_ok=True)

    if download:
        download(date, 150)

    transform_to_csv()

    sql = f'''
    \copy planit_load(key, file, data, load_date, hash, uid) FROM _planit_output/full/all.csv with CSV

    INSERT INTO planit(load_id, uid, data, latest_change_date, geom, geog) 
    SELECT 
       id, 
       uid,
       data, 
       load_date, 
       ST_MakePoint((data ->> 'location_x')::float, (data ->> 'location_y')::float),
       ST_MakePoint((data ->> 'location_x')::float, (data ->> 'location_y')::float)
    FROM 
       planit_load;

    REFRESH MATERIALIZED VIEW CONCURRENTLY near_ibas;
    REFRESH MATERIALIZED VIEW CONCURRENTLY near_rspb_reserves;

    UPDATE planit_load SET new=true, processed=true;
       
    '''
    run_sql(sql)


@click.command()
def update_scrape():
    date = datetime.date.today()
    os.makedirs(f'_planit_output/{str(date)}', exist_ok=True)
    download(date, 3)
    transform_to_csv(str(date))

    sql = f'''
    BEGIN;
    CREATE TEMPORARY TABLE planit_load_tmp(key INT, file TEXT, data JSONB, load_date DATE, hash TEXT, uid TEXT);
    CREATE INDEX planit_load_tmp_uid on planit_load_tmp(uid);

    \copy planit_load_tmp(key, file, data, load_date, hash, uid) FROM _planit_output/{str(date)}/all.csv with CSV;

    INSERT INTO planit_load(key, file, data, load_date, hash, uid, new, changed) 
    SELECT 
      planit_load_tmp.*, CASE WHEN planit.uid is null THEN true ELSE false END, CASE WHEN planit.uid is null THEN false ELSE true END
    FROM  
      planit_load_tmp
    LEFT JOIN planit USING (uid)
    ON CONFLICT DO NOTHING;

    DROP TABLE planit_load_tmp;

    INSERT INTO planit(load_id, data, latest_change_date, geom, geog) 
    SELECT 
       id, 
       data, 
       load_date,
       ST_MakePoint((data ->> 'location_x')::float, (data ->> 'location_y')::float),
       ST_MakePoint((data ->> 'location_x')::float, (data ->> 'location_y')::float)
    FROM 
       planit_load pl
    WHERE
       load_date = '{str(date)}'
    ON CONFLICT (uid) DO UPDATE
       set load_id=excluded.load_id, data=excluded.data, latest_change_date=excluded.latest_change_date;

    REFRESH MATERIALIZED VIEW CONCURRENTLY near_ibas;
    REFRESH MATERIALIZED VIEW CONCURRENTLY near_rspb_reserves;
    
    COMMIT
       
    '''
    run_sql(sql)


@click.command()
def clean():
    run_sql('DROP MATERIALIZED VIEW IF EXISTS near_ibas')
    run_sql('DROP MATERIALIZED VIEW IF EXISTS near_rspb_reserves')
    run_sql('DROP TABLE IF EXISTS planit')
    run_sql('DROP TABLE IF EXISTS planit_load')
    shutil.rmtree('_planit_output')

@click.command()
def setup():
    os.makedirs('_planit_output/full', exist_ok=True)
    run_sql('''
       CREATE TABLE IF NOT EXISTS planit_load(id SERIAL,
                                              key INT,
                                              file TEXT,
                                              data JSONB,
                                              load_date DATE,
                                              hash TEXT,
                                              uid TEXT,
                                              new bool DEFAULT FALSE,
                                              changed bool DEFAULT FALSE,
                                              processed bool DEFAULT FALSE);

       CREATE UNIQUE INDEX planit_load_hash_idx ON planit_load(hash);
       CREATE INDEX planit_load_uid_idx ON planit_load(uid);

       CREATE TABLE IF NOT EXISTS planit(id serial, 
                                         uid TEXT, 
                                         load_id bigint, 
                                         data jsonb, 
                                         latest_change_date date);

                                              
       SELECT AddGeometryColumn ('public','planit','geom',4326,'POINT',2);
       ALTER TABLE planit ADD COLUMN geog GEOGRAPHY;

       CREATE UNIQUE INDEX planit_uid ON planit(uid);

       CREATE INDEX planit_planit_load_id ON planit(load_id);

       CREATE MATERIALIZED VIEW near_ibas AS
            SELECT distinct(id) from planit, ibas WHERE ST_DWithin(ibas.geog, planit.geog, 500, false);

       CREATE UNIQUE INDEX near_ibas_planit_id ON near_ibas(id);

       CREATE MATERIALIZED VIEW near_rspb_reserves AS
            SELECT distinct(id) from planit, rspb_reserves WHERE ST_DWithin(rspb_reserves.geog, planit.geog, 500, false);

       CREATE UNIQUE INDEX near_rspb_reserves_id ON near_rspb_reserves(id);
    ''')


cli.add_command(full_scrape)
cli.add_command(update_scrape)
cli.add_command(clean)
cli.add_command(setup)

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


def download(today, days):
    for days in range(0, days):
        date = str(today - datetime.timedelta(days=days))
        download_day(date, 'full')


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
                    writer.writerow([i, f, original_json_dump, str(datetime.date.today()), str(sha1(json.dumps(item).encode()).hexdigest()), item['uid']])
                    i += 1


if __name__ == '__main__':
    cli()
