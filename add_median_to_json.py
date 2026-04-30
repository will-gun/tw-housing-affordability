#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path


def normalize_name(text: str) -> str:
    if text is None:
        return ""
    s = text.strip()
    s = s.replace("台", "臺")
    s = s.replace("臺灣", "台灣") if False else s
    s = re.sub(r"\s+", "", s)
    s = s.replace("、", "")
    s = s.replace("．", ".")
    return s


def split_county_town(county_town: str) -> tuple[str, str]:
    county_town = county_town.strip()
    m = re.match(r"^(.*?(市|縣))(.*)$", county_town)
    if m:
        return m.group(1), m.group(3)
    return county_town, ""


def build_key(county: str, town: str, village: str) -> str:
    return "|".join([normalize_name(county), normalize_name(town), normalize_name(village)])


def read_csv_medians(csv_path: Path) -> dict[str, int]:
    medians = {}
    duplicates = set()
    with csv_path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError('CSV 檔案無法讀取欄位名稱。')
        reader.fieldnames = [name.lstrip('\ufeff').strip() for name in reader.fieldnames]
        if '縣市別' not in reader.fieldnames or '村里' not in reader.fieldnames or '中位數' not in reader.fieldnames:
            raise ValueError('CSV 必須包含欄位: 縣市別, 村里, 中位數')
        for row in reader:
            row = {k.lstrip('\ufeff').strip(): v for k, v in row.items()}
            county_town = row.get('縣市別', '')
            village = row.get('村里', '')
            median_raw = row.get('中位數', '')
            if not village or not median_raw:
                continue
            try:
                median_value = int(float(median_raw))
            except ValueError:
                try:
                    median_value = float(median_raw)
                except ValueError:
                    continue
            county, town = split_county_town(county_town)
            key = build_key(county, town, village)
            if key in medians:
                duplicates.add(key)
            medians[key] = median_value
    if duplicates:
        print(f'警告: CSV 中有 {len(duplicates)} 個重複鍵，後面值會覆蓋前面值。')
    return medians


def update_json(json_path: Path, medians: dict[str, int], output_path: Path) -> tuple[int, int, int]:
    with json_path.open(encoding='utf-8') as f:
        data = json.load(f)

    if 'features' not in data or not isinstance(data['features'], list):
        raise ValueError('JSON 不是標準 GeoJSON FeatureCollection，找不到 "features"。')

    matched = 0
    unmatched_json = 0
    for feature in data['features']:
        props = feature.get('properties', {})
        county = props.get('COUNTYNAME', '')
        town = props.get('TOWNNAME', '')
        village = props.get('VILLNAME', '')
        if not village:
            unmatched_json += 1
            continue
        key = build_key(county, town, village)
        if key in medians:
            props['MEDIAN'] = medians[key]
            matched += 1
        else:
            unmatched_json += 1

    output_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return matched, unmatched_json, len(medians)


def main() -> None:
    parser = argparse.ArgumentParser(description='將 CSV 中位數填入 GeoJSON 的村里屬性。')
    parser.add_argument('csv_path', type=Path, help='來源 CSV 檔案路徑')
    parser.add_argument('json_path', type=Path, help='來源 JSON 檔案路徑')
    parser.add_argument('output_path', type=Path, nargs='?', default=Path('taiwan_districts_with_median.json'), help='輸出 JSON 檔案路徑，預設 taiwan_districts_with_median.json')
    args = parser.parse_args()

    medians = read_csv_medians(args.csv_path)
    print(f'已讀取 {len(medians)} 筆 CSV 中位數資料。')
    matched, unmatched_json, total_csv = update_json(args.json_path, medians, args.output_path)
    print(f'更新完成: 匹配到 {matched} 個 JSON feature。')
    print(f'JSON 中未匹配到來源 CSV 的 feature: {unmatched_json}。')
    print(f'輸出檔案: {args.output_path}')


if __name__ == '__main__':
    main()
