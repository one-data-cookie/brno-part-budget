import datetime as dt
import gspread as gs
import json
import os
import pandas as pd
import requests as rq


def map_status_to_category(status_name):
    normalized = (status_name or '').strip().lower()
    mapping = {
        'dokončený': 'finished',
        'realizovaný': 'finished',
        'v realizaci': 'underconstruction+winner',
        'proveditelný': 'got approval',
        'posuzovaný': 'not public',
        'neproveditelný': 'failed',
        'nerealizovatelný': 'failed',
        'nezískal podporu': 'failed',
        'nevítězný': 'failed',
        'stažen': 'failed',
        'jiný': 'failed',
    }
    return mapping.get(normalized, '')


def map_status_to_legacy_id(status_name):
    normalized = (status_name or '').strip().lower()
    mapping = {
        'proveditelný': 5,
        'neproveditelný': 6,
        'v realizaci': 9,
        'realizovaný': 10,
        'dokončený': 10,
        'stažen': 13,
        'nezískal podporu': 14,
        'nevítězný': 15,
        'nerealizovatelný': 16,
        'jiný': 17,
        'posuzovaný': 18,
    }
    return mapping.get(normalized, '')


def brno_part_budget():

    # Define the range of years to query
    start_year = 2017
    this_year = dt.date.today().year

    # Fetch projects from ArcGIS API (schema changed from properties_* to plain names)
    arcgis_url = 'https://services6.arcgis.com/fUWVlHWZNxUvTUh8/arcgis/rest/services/ProjektyPARO/FeatureServer/0/query'
    all_proj_data = []
    offset = 0
    chunk_size = 1000

    while True:
        params = {
            'where': '1=1',
            'outFields': '*',
            'outSR': 4326,
            'f': 'json',
            'resultOffset': offset,
            'resultRecordCount': chunk_size
        }
        response = rq.get(arcgis_url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        if 'error' in data:
            raise RuntimeError(f"ArcGIS API error: {data['error']}")

        features = data.get('features', [])
        if not features:
            break

        all_proj_data.extend([i.get('attributes', {}) for i in features])

        if len(features) < chunk_size:
            break

        offset += chunk_size

    api_data = pd.DataFrame(all_proj_data)

    if api_data.empty:
        raise RuntimeError('ArcGIS API returned no project data.')

    if 'year' in api_data.columns:
        api_data = api_data[api_data['year'].between(start_year, this_year)]

    # Keep backward compatibility with historical naming used downstream
    rename_map = {
        'id': 'properties_id',
        'name': 'properties_name',
        'proposer': 'properties_proposer',
        'district': 'properties_district',
        'year': 'properties_year',
        'budget': 'properties_budget',
        'detail': 'properties_detail',
        'image': 'properties_image',
    }
    api_data = api_data.rename(columns={k: v for k, v in rename_map.items() if k in api_data.columns})

    if 'latitude' not in api_data.columns and 'properties_latitude' in api_data.columns:
        api_data['latitude'] = api_data['properties_latitude']
    if 'longitude' not in api_data.columns and 'properties_longitude' in api_data.columns:
        api_data['longitude'] = api_data['properties_longitude']

    # Fetch status/category metadata for all projects to preserve legacy schema
    project_list_url = 'https://paro.damenavas.cz/wp-json/iq/v1/project/list'
    first_page = rq.post(project_list_url, json={'page': 1}, timeout=60)
    first_page.raise_for_status()
    first_page_data = first_page.json()
    project_count = int(first_page_data.get('count', 0))
    pages = (project_count + 9) // 10

    project_meta_rows = []
    for page in range(1, pages + 1):
        page_res = rq.post(project_list_url, json={'page': page}, timeout=60)
        page_res.raise_for_status()
        page_data = page_res.json()

        for project in page_data.get('items', []):
            status = project.get('status') or {}
            category = project.get('category') or {}

            status_name = status.get('name', '')
            if status_name == 'dokončený':
                status_name = 'realizovaný'

            category_name = category.get('name', '')
            category_category = map_status_to_category(status_name)
            category_status = ''
            if category_name and category_category:
                category_status = f'{category_name}, {category_category}'

            project_meta_rows.append({
                'properties_id': project.get('id'),
                'properties_status_id': map_status_to_legacy_id(status_name),
                'properties_status_name': status_name,
                'properties_category_name': category_name,
                'category_category': category_category,
                'category_status': category_status,
            })

    project_meta_data = pd.DataFrame(project_meta_rows).drop_duplicates(subset='properties_id', keep='last')

    # Fetch vote results from WP JSON API (page is now JS-rendered)
    year_list_res = rq.post(
        'https://paro.damenavas.cz/wp-json/iq/v1/year-settings/list',
        json={},
        timeout=60
    )
    year_list_res.raise_for_status()
    year_list_data = year_list_res.json()
    year_items = year_list_data.get('items', [])

    year_to_id = {
        item.get('year'): item.get('id')
        for item in year_items
        if item.get('year') is not None and item.get('id') is not None
    }

    vote_rows = []
    vote_url = 'https://paro.damenavas.cz/wp-json/iq/v1/project/vote-results'
    for year in range(start_year, this_year + 1):
        year_id = year_to_id.get(year)
        if year_id is None:
            continue

        vote_res = rq.post(
            vote_url,
            json={'filters': [{'field': 'year_id', 'value': year_id}]},
            timeout=60
        )
        vote_res.raise_for_status()
        vote_data = vote_res.json()

        projects = vote_data.get('projects', [])
        voted_tokens_count = vote_data.get('votedTokensCount', '')

        for project in projects:
            vote = project.get('vote') or {}
            vote_rows.append({
                'properties_id': project.get('id'),
                'votes': vote.get('balance', ''),
                'votes_pos': vote.get('positive', ''),
                'votes_neg': vote.get('negative', ''),
                'votes_ppl': vote.get('uniquePositive', ''),
                'votes_total': voted_tokens_count,
            })

    wp_data = pd.DataFrame(vote_rows, columns=['properties_id', 'votes', 'votes_pos', 'votes_neg', 'votes_ppl', 'votes_total'])

    # Join data together and clean
    full_data = api_data.join(project_meta_data.set_index('properties_id'), on='properties_id')
    full_data = full_data.join(wp_data.set_index('properties_id'), on='properties_id')
    full_data = full_data.fillna('').sort_values('properties_id')

    # Clean district names and add column with their shorted version
    full_data['properties_district'] = full_data['properties_district'].apply(lambda x: 'Brno' if x in ('Brno', ' - ') else x.replace(' - ', '-').replace('A', 'a'))
    full_data.insert(7, 'properties_district_short', full_data['properties_district'].apply(lambda x: 'Brno' if x == 'Brno' else x.split('-')[1]))

    final_columns = [
        'properties_id',
        'properties_name',
        'properties_proposer',
        'properties_status_id',
        'properties_status_name',
        'properties_district',
        'properties_year',
        'properties_district_short',
        'properties_budget',
        'properties_detail',
        'properties_category_name',
        'properties_image',
        'latitude',
        'longitude',
        'category_category',
        'category_status',
        'ObjectId',
        'votes',
        'votes_pos',
        'votes_neg',
        'votes_ppl',
        'votes_total',
    ]

    for column in final_columns:
        if column not in full_data.columns:
            full_data[column] = ''

    full_data = full_data[final_columns]

    # Push to GSheet
    gc = gs.service_account_from_dict(json.loads(os.environ['GOOGLE_CREDENTIALS'], strict=False))
    sh = gc.open_by_key(os.environ['GOOGLE_SPREADSHEET_ID'])
    ws = sh.get_worksheet(0)
    ws.update([full_data.columns.values.tolist()] + full_data.values.tolist())

    # Return message if successful
    return print('Data successfully updated.')


if __name__ == '__main__':
    brno_part_budget()
