import bs4
import datetime as dt
import gspread as gs
import os
import pandas as pd
import re
import requests as rq


def brno_part_budget():

    # Import data from API
    response = rq.get('https://services6.arcgis.com/fUWVlHWZNxUvTUh8/arcgis/rest/services/ProjektyPARO/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=json')
    data = response.json()
    proj_data = [i['attributes'] for i in data['features']]
    api_data = pd.DataFrame(proj_data)

    # Scrape web page (property IDs and votes data)
    pids_data = []
    votes_data = []

    this_year = dt.date.today().year

    for year in range(2017, this_year):
        page_res = rq.get(f'https://damenavas.brno.cz/vysledky-hlasovani/?y={str(year)}')
        soup = bs4.BeautifulSoup(page_res.content, 'html.parser')

        for projects in soup.find_all('div', attrs={re.compile('col-xs-12 vap-project-name')}):
            pids = int(re.compile(r'id=(\d{1,})').findall(str(projects.a))[0])
            pids_data.append(pids)

        for votes in soup.find_all('span', attrs={'class':'vap-project-balance-number'}):
            votes = int(votes.text.replace(' ', ''))
            votes_data.append(votes)

    wp_data = pd.DataFrame(list(zip(pids_data, votes_data)), columns=['properties_id','votes'])

    # Join data together and clean
    full_data = api_data.join(wp_data.set_index('properties_id'), on='properties_id')
    full_data = full_data.fillna('').sort_values('properties_id')

    # Clean district names and add column with their shorted version
    full_data['properties_district'] = full_data['properties_district'].apply(lambda x: 'Brno' if x in ('Brno', ' - ') else x.replace(' - ', '-').replace('A', 'a'))
    full_data.insert(7, 'properties_district_short', full_data['properties_district'].apply(lambda x: 'Brno' if x == 'Brno' else x.split('-')[1]))

    # Push to GSheet
    gc = gs.service_account_from_dict(os.environ['GOOGLE_CREDENTIALS'])
    sh = gc.open_by_key(os.environ['GOOGLE_SPREADSHEET_ID'])
    ws = sh.get_worksheet(0)
    ws.update([full_data.columns.values.tolist()] + full_data.values.tolist())

    # Return message if successful
    return print('Data successfully updated.')


if __name__ == '__main__':
    brno_part_budget()
