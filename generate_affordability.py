import json
import csv
from collections import defaultdict
import statistics

# Load the districts JSON
with open('/home/will/housing/taiwan_districts_with_median.json', 'r', encoding='utf-8') as f:
    districts_data = json.load(f)

# Extract salary medians by region
salary_medians = {}
for feature in districts_data['features']:
    props = feature['properties']
    region_key = f"{props['COUNTYNAME']}:{props['TOWNNAME']}:{props['VILLNAME']}"
    salary_medians[region_key] = props.get('MEDIAN', 0)

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

# Build the output data by extending the original GeoJSON
for feature in districts_data['features']:
    props = feature['properties']
    region_key = f"{props['COUNTYNAME']}:{props['TOWNNAME']}:{props['VILLNAME']}"
    salary_median = props.get('MEDIAN', 0)
    housing_median = median_prices.get(region_key, 0)
    if salary_median > 0:
        affordability = housing_median / 1000 / salary_median
    else:
        affordability = 0
    props['housing_median'] = housing_median
    props['affordability'] = affordability

# Save the extended JSON
with open('/home/will/housing/taiwan_districts_with_median_extended.json', 'w', encoding='utf-8') as f:
    json.dump(districts_data, f, ensure_ascii=False, indent=4)

print("Done!")