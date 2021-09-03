import requests
import datetime
import json
import time


def do_scrape(date, page=1):
    url = f'https://www.planit.org.uk/api/applics/json?start_date={date}&end_date={date}&pg_sz=3000&page={page}'
    response = requests.get(url)

    if response.status_code == 400:
        time.sleep(30)
        response = requests.get(url)

    json_response = response.json()

    with open(f'output/{date}-p{page}.json', 'w+') as outputfile:
        json.dump(json_response, outputfile)

    time.sleep(20)

    return json_response['total']


for days in range(0, 365*15):
    date = str(datetime.date.today() - datetime.timedelta(days=days))

    total = do_scrape(date)

    if total > 3000:
        do_scrape(date, 2)

    if total > 6000:
        do_scrape(date, 3)

    if total > 9000:
        do_scrape(date, 4)

    if total > 12000:
        do_scrape(date, 5)

    if total > 15000:
        raise Exception('can not handle 15000 a day')

    



