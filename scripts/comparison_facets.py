"""Integrity rules for the compact, evidence-linked comparison layer."""
from __future__ import annotations
from collections import Counter
import hashlib
import json


def snapshot_hash(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def facet_id(topic_id: str, questions: list[str]) -> str:
    return topic_id + '-overview-' + hashlib.sha256('\n'.join(sorted(questions)).encode()).hexdigest()[:10]


def validate_facets(compact: dict, data: dict) -> None:
    if compact.get('version') != 1 or compact.get('snapshotHash') != snapshot_hash(data):
        raise ValueError('compact comparison does not match the source snapshot')
    topics = {t['id']: t for t in data['topics']}
    if Counter(t['id'] for t in compact['topics']) != Counter(topics.keys()):
        raise ValueError('compact comparison must retain every topic exactly once')
    claims = {c['id']: c for c in data['claims']}
    seen_ids = set()
    for topic in compact['topics']:
        questions = {q['id']: q for q in topics[topic['id']]['questions']}
        facets = topic['facets']
        limit = 2 if len(questions) < 20 else 4
        if bool(facets) != bool(questions) or len(facets) > limit:
            raise ValueError('each nonempty topic needs one to four comparison facets')
        covered = []
        for facet in facets:
            if facet['id'] in seen_ids or not facet['title'].strip():
                raise ValueError('invalid or duplicate facet')
            seen_ids.add(facet['id'])
            ids = facet['questionIds']
            if not ids or len(set(ids)) != len(ids) or not set(ids) <= questions.keys():
                raise ValueError('facet question references are invalid')
            if facet['id'] != facet_id(topic['id'], ids):
                raise ValueError('facet ID does not match its questions')
            covered.extend(ids)
            expected: dict[str, set] = {}
            for qid in ids:
                for row in questions[qid]['rows']:
                    expected.setdefault(row['candidateId'], set()).update(row['claimIds'])
            if Counter(r['candidateId'] for r in facet['rows']) != Counter(expected.keys()):
                raise ValueError('facet must retain every candidate with evidence')
            for row in facet['rows']:
                if row.get('verified') is not True or not 1 <= len(row['highlights']) <= 3:
                    raise ValueError('facet summary must pass semantic verification')
                for point in row['highlights']:
                    refs = point['claimIds']
                    if not point['text'].strip() or not refs or len(set(refs)) != len(refs) or not set(refs) <= expected[row['candidateId']]:
                        raise ValueError('facet highlights must cite their candidate and questions')
                    if any(claims[ref]['candidateId'] != row['candidateId'] for ref in refs):
                        raise ValueError('facet highlight candidate attribution mismatch')
        if Counter(covered) != Counter(questions.keys()):
            raise ValueError('facet grouping omitted or duplicated questions')
