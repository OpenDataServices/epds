import json
import csv
import glob

with open('output/all.csv', 'w+') as out_csv_file:
    i = 1
    writer = csv.writer(out_csv_file)

    for f in glob.glob("output/*.json"):
        with open(f) as json_file:
            data = json.load(json_file)
            for item in data['records']:
                writer.writerow([i, f, json.dumps(item)])
                i += 1
