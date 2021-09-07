create table planit_load(key int, file text, data jsonb);
\copy planit_load from output/all.csv with CSV
SELECT AddGeometryColumn ('public','planit_load','geom',4326,'POINT',2);
update planit_load set geom = ST_MakePoint((data ->> 'location_x')::float, (data ->> 'location_y')::float);
