import csv
import sys

rows = list(csv.DictReader(open('docs/FEATURE_PARITY/MASTER_FEATURE_MATRIX.csv', encoding='utf-8')))
sources = sys.argv[1:]
for src in sources:
    print('=' * 24, src)
    for r in rows:
        if r['Source project'] == src and r['Current status'] == 'NOT_IMPLEMENTED':
            print('{mid:8s} {pri:3s} | {name}'.format(
                mid=r['Master ID'], pri=r['Priority'],
                name=r['Exact source feature name'][:66]))
