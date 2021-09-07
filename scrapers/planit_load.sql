create table planit_load(key int, file text, data jsonb);
\copy planit_load from output/all.csv with CSV
update planit_load set geom = ST_MakePoint((data ->> 'location_x')::float, (data ->> 'location_y')::float);
