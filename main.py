import bs4
import datetime as dt
import gspread as gs
import json
import os
import pandas as pd
import re
import requests as rq


def brno_part_budget():

    # Define the range of years to query
    start_year = 2017
    this_year = dt.date.today().year

    # Loop through each year to query all data from API
    all_proj_data = []

    for year in range(start_year, this_year + 1):
        response = rq.get(f'https://services6.arcgis.com/fUWVlHWZNxUvTUh8/arcgis/rest/services/ProjektyPARO/FeatureServer/0/query?where=properties_year={year}&outFields=*&outSR=4326&f=json')
        data = response.json()
        proj_data = [i['attributes'] for i in data['features']]
        all_proj_data.extend(proj_data)

    # Convert the final data into a DataFrame
    api_data = pd.DataFrame(all_proj_data)

    # Scrape web page (property IDs and votes data)
    pids_data = []
    votes_total = []
    votes_number = []
    votes_pos = []
    votes_neg = []
    votes_ppl = []

    for year in range(start_year, this_year + 1):
        page_res = rq.get(f'https://paro.damenavas.cz/vysledky-hlasovani/?y={str(year)}')
        soup = bs4.BeautifulSoup(page_res.content, 'html.parser')

        # Scrape total number of people who voted in given year
        total = soup.find('div', attrs={'class': 'g-stats-number'})
        total = int(total.text.replace(' ', ''))

        # Scrape property ID
        for projects in soup.find_all('div', attrs={re.compile('col-xs-12 vap-project-name')}):
            pids = int(re.compile(r'id=(\d{1,})').findall(str(projects.a))[0])
            pids_data.append(pids)
            votes_total.append(total)  # add total to each project

        # Scrape votes number
        for votes in soup.find_all('span', attrs={'class': 'vap-project-balance-number'}):
            votes = int(votes.text.replace(' ', ''))
            votes_number.append(votes)

        # Scrape votes details
        for details in soup.find_all('span', attrs={'data-toggle': 'tooltip'}):
            details = re.compile(r'Projekt získal (\d+ ?\d*) kladných hlasů od (\d+ ?\d*) hlasujících\. Dále získal (\d+ ?\d*) záporných hlasů\.').findall(str(details))[0]
            details = [int(d.replace(' ', '')) for d in details]
            votes_pos.append(details[0])
            votes_neg.append(details[2])
            votes_ppl.append(details[1])

    wp_data = pd.DataFrame(list(zip(pids_data, votes_number, votes_pos, votes_neg, votes_ppl, votes_total)),
                           columns=['properties_id', 'votes', 'votes_pos', 'votes_neg', 'votes_ppl', 'votes_total'])

    # Join data together and clean
    full_data = api_data.join(wp_data.set_index('properties_id'), on='properties_id')
    full_data = full_data.fillna('').sort_values('properties_id')

    # Clean district names and add column with their shorted version
    full_data['properties_district'] = full_data['properties_district'].apply(lambda x: 'Brno' if x in ('Brno', ' - ') else x.replace(' - ', '-').replace('A', 'a'))
    full_data.insert(7, 'properties_district_short', full_data['properties_district'].apply(lambda x: 'Brno' if x == 'Brno' else x.split('-')[1]))

    # Push to GSheet
    gc = gs.service_account_from_dict(json.loads(os.environ['GOOGLE_CREDENTIALS'], strict=False))
    sh = gc.open_by_key(os.environ['GOOGLE_SPREADSHEET_ID'])
    ws = sh.get_worksheet(0)
    ws.update([full_data.columns.values.tolist()] + full_data.values.tolist())

    # Return message if successful
    return print('Data successfully updated.')


if __name__ == '__main__':
    brno_part_budget()
