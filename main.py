import requests as rq
import pandas as pd
import gspread as gs
import bs4
import re
import os
  
# Get projects data
proj_res = rq.get('https://gis.brno.cz/ags1/rest/services/Hosted/ProjektyPARO/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=json')
proj_data = [i['attributes'] for i in proj_res.json()['features']]
    
# Scrape voting data
vote_data = []
for year in [2017, 2018, 2019]:
    # Get BS object
    vote_res = rq.get('https://damenavas.brno.cz/vysledky-hlasovani/?y=' + str(year))
    soup = bs4.BeautifulSoup(vote_res.content, 'html.parser')
    
    # Get Property IDs
    pids = soup.find_all('div', attrs={'class': re.compile('col-xs-12 vap-project-name')})
    vote_pids = [int(re.compile(r'\d{1,}').findall(str(i.a))[0]) for i in pids]
    
    # Get votes
    votes = soup.find_all('span', attrs={'class':'vap-project-balance-number'})
    vote_votes = [int(i.text.replace(' ', '')) for i in votes]

    # Put together
    for i, j in zip(vote_pids, vote_votes):
        vote_data.append({"properties_id": i, "properties_vote": j})

# Put into data frames, join, and clean
proj_df = pd.DataFrame(proj_data)
vote_df = pd.DataFrame(vote_data)
df = proj_df.merge(vote_df, how='left', on='properties_id')
df = df.sort_values(by=['objectid'], ignore_index=True).fillna('')

# Open GSheet
gc = gs.service_account(filename=os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
ss = gc.open_by_key(os.environ['GOOGLE_SPREADSHEET_ID'])

# Write data
ss.worksheets()[0].update([df.columns.values.tolist()] + df.values.tolist())
print('Data successfully updated.')