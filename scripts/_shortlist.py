import csv
import sys

rows = list(csv.DictReader(open('docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv', encoding='utf-8')))
ids = set(sys.argv[1:])
for r in rows:
    if r['Master ID'] not in ids:
        continue
    print('=' * 70)
    print('{mid} | {pri} | {av} | {name}'.format(
        mid=r['Master ID'], pri=r['Priority'],
        av=r['Community availability'], name=r['Exact source feature name']))
    for field in ('Description', 'Dependencies', 'Remaining work',
                  'Final acceptance criteria', 'Licensing constraint'):
        print('  {0}: {1}'.format(field, r[field]))
