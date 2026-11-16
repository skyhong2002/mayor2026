"""Official, city-scoped identity joins for mayoral comparisons."""
from __future__ import annotations
import csv
from pathlib import Path
from elections.model import COUNTIES, COUNTY_NAME

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def race_roster(city: str) -> list[dict]:
    name = COUNTY_NAME[city]
    registered = [r for r in read_rows(ROOT / 'data/elections/2026/registered.csv')
                  if r['category'] in ('municipal-mayor', 'county-mayor') and r['district'] == name]
    numbered = {r['name']: r for r in read_rows(ROOT / 'data/elections/2026/candidates.csv')
                if r['category'] in ('municipal-mayor', 'county-mayor') and r['county'] == city}
    tracked = {r['name']: r for r in read_rows(ROOT / 'data/sources/candidates.csv') if r['city'] == city}
    result = []
    for r in registered:
        ballot, known = numbered.get(r['name']), tracked.get(r['name'])
        # Exact name and city join only. Untracked IDs derive from an official record.
        import hashlib
        official = ballot['id'] if ballot else city + '-registered-' + hashlib.sha256(r['name'].encode()).hexdigest()[:12]
        result.append({'id': known['candidate_id'] if known else official, 'name': r['name'],
                       'number': int(ballot['number']) if ballot else None, 'party': r['party'],
                       'officialId': official, 'rosterSource': r['source'], 'sourceTracked': bool(known)})
    if not result:
        raise ValueError('No official mayoral roster: ' + city)
    return sorted(result, key=lambda c: (c['number'] is None, c['number'] or 0, c['name']))


def validate_race(data: dict) -> None:
    city = data['race']['id']
    expected = {c['id']: c for c in race_roster(city)}
    actual = data['candidates']
    if len(actual) != len(expected) or {c['id'] for c in actual} != set(expected):
        raise ValueError('Comparison must include the complete official race roster: ' + city)
    if data['race']['name'] != COUNTY_NAME[city]:
        raise ValueError('Race label mismatch')
    for c in actual:
        if any(c.get(k) != expected[c['id']][k] for k in ('name', 'number', 'party', 'officialId')):
            raise ValueError('Comparison candidate identity differs from official roster')
