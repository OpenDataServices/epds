# EPDS

## Development Guide

Postgis required, docker option below on how to install this easily.

### With docker-compose

To execute things in the data `getter` container, run:

```bash
sudo docker-compose up -d
sudo docker-compose exec getter /bin/bash
```

Inside the `getter` container you can then use `psql` or run the python scripts, eg:

```bash
psql postgresql://epds:epds@db/epds
```

```bash
python scrapers/planit.py
```

See *Loading data* below for more.

### Without docker-compose

This will create a local postgres instance binding to 5432 port on the local computer with user, database and password all `epds`

```bash
sudo docker run --name epds-postgis -e POSTGRES_USER=epds -e POSTGRES_PASSWORD=epds -d -p 5432:5432 postgis/postgis
```

To connect using local psql client use:

```bash
psql postgresql://epds:epds@localhost:5432/epds
```

The connection string `postgresql://epds:epds@localhost:5432/epds` can be used to connect from other applications.

### Loading data

Use the included SQL to load regional data into the PostGIS store.

```bash
psql postgresql://epds:epds@localhost:5432/epds -f data/local_nature.sql
psql postgresql://epds:epds@localhost:5432/epds -f data/national_nature.sql
psql postgresql://epds:epds@localhost:5432/epds -f data/iba.sql
psql postgresql://epds:epds@localhost:5432/epds -f data/sssi.sql
```

#### Planit data

If you're not using docker-compose, don't forget to create the `output` directory.

```
python scrapers/planit.py
python scrapers/planit_load.py
psql -f scrapers/planit_load.sql
```

### Importing new datasources

#### From shapefile

Install postgis package locally, but no need to run postgres locally, as it includes `shp2pgsql`.

**Put all data in the 4326 SRID**, this is the lat/long system that most point data is in.

Run shp2pgsql using a command like:

```bash
   shp2pgsql -s 27700:4326 data/National_Nature_Reserves_England.shp > data/nationl_nature.sql
```

* `27700` is the SRID code (projection) of the shape file. Need to look at documentation of the data to find that.
* `4326` is the target SRID (**always 4326**)
* `data/National_Nature_Reserves_England.shp` is the shapefile
* `data/nationl_nature.sql` output SQL that can be executed to import the data.

Try and document licence with attrubution in `data/data_licences.txt`





