import json
import csv
from collections import defaultdict
import statistics

def parse_region_key_from_salary_row(row):
    area = row['縣市別'].strip()
    village = row['村里'].strip()
    if not area or not village:
        return None
    # Extract county/city and township/district from the combined field
    import re
    match = re.match(r'^(.+?[市縣])(.+)$', area)
    if not match:
        return None
    county = match.group(1)
    town = match.group(2)
    return f"{county}:{town}:{village}"

# Load salary medians from the original CSV
salary_medians = {}
with open('/home/will/housing/111_165-9.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    if reader.fieldnames:
        reader.fieldnames = [name.strip('\ufeff').strip() for name in reader.fieldnames]
    for row in reader:
        region_key = parse_region_key_from_salary_row(row)
        if not region_key:
            continue
        village_median = row.get('中位數', '').strip()
        if village_median in ('', '合計', '其他'):
            continue
        try:
            salary_medians[region_key] = float(village_median)
        except ValueError:
            continue

# Load the smaller simple GeoJSON and extend it
with open('/home/will/housing/taiwan_districts_simple.json', 'r', encoding='utf-8') as f:
    districts_data = json.load(f)

# Load housing prices CSV and group by region
housing_prices = defaultdict(list)
with open('/home/will/housing/collected_housing_prices_2026Q1_with_li.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        region_key = f"{row['縣市']}:{row['鄉鎮市區']}:{row['里或村']}"
        try:
            price = int(row['總價元'])
            housing_prices[region_key].append(price)
        except ValueError:
            pass  # Skip invalid prices

# Calculate median prices
median_prices = {}
for region, prices in housing_prices.items():
    if prices:
        median_prices[region] = statistics.median(prices)
    else:
        median_prices[region] = 0

# Extend the simple GeoJSON with housing median, salary median and affordability
for feature in districts_data['features']:
    props = feature['properties']
    region_key = f"{props['COUNTYNAME']}:{props['TOWNNAME']}:{props['VILLNAME']}"
    salary_median = props.get('MEDIAN', salary_medians.get(region_key, 0))
    housing_median = median_prices.get(region_key, 0)
    if salary_median > 0:
        affordability = housing_median / 1000 / salary_median
    else:
        affordability = 0
    props['MEDIAN'] = salary_median
    props['housing_median'] = housing_median
    props['affordability'] = affordability

# Save the extended simple GeoJSON
with open('/home/will/housing/taiwan_districts_simple_extended.json', 'w', encoding='utf-8') as f:
    json.dump(districts_data, f, ensure_ascii=False, indent=4)

print("Done!")