import requests
import datetime
import json
import time

for days in range(0, 365*15):
    date = str(datetime.date.today() - datetime.timedelta(days=days))
    url = f'https://www.planit.org.uk/api/applics/json?start_date={date}&end_date={date}&pg_sz=3000'
    response = requests.get(url)

    if response.status_code == 400:
        time.sleep(30)
        response = requests.get(url)

    json_response = response.json()

    if json_response['total'] > 3000:
        print(f'date {date} has greater that 3000 applications') 


    with open(f'output/{date}.json', 'w+') as outputfile:
        json.dump(json_response, outputfile)

    time.sleep(20)
    



