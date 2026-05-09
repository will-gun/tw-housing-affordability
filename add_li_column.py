import os
import sys
import time

import googlemaps
import pandas as pd

from config import API_KEY

INPUT_CSV = 'collected_housing_prices_2026Q1.csv'
OUTPUT_CSV = 'collected_housing_prices_2026Q1_with_li.csv'
REFERENCE_CSV = '111_165-9.csv'
SLEEP_SECONDS = 0.1

gmaps = googlemaps.Client(key=API_KEY)

# 讀取參考檔案並建立村里查詢表
reference_df = pd.read_csv(REFERENCE_CSV, encoding='utf-8-sig')
# 清理列名（移除BOM和空白字符）
reference_df.columns = reference_df.columns.str.replace('\ufeff', '').str.strip()
# 建立 (縣市別, 村里) -> True 的映射表
reference_villages = set(
    zip(reference_df['縣市別'], reference_df['村里'])
)


def match_village(county_city, village_name):
    """檢查村里是否在參考檔案中"""
    if not village_name or pd.isna(village_name):
        return False
    
    # 精確匹配
    if (county_city, village_name) in reference_villages:
        return True
    
    # 嘗試部分匹配（針對英文或其他可能的格式差異）
    for ref_county, ref_village in reference_villages:
        if ref_county == county_city and ref_village.lower() in village_name.lower():
            return True
        if ref_county == county_city and village_name.lower() in ref_village.lower():
            return True
    
    return False


def extract_li_from_components(components, debug=False):
    exact_li = None
    fallback_li = None
    fallback_types = []

    for comp in components:
        long_name = comp.get('long_name', '')
        if '里' in long_name or '村' in long_name:
            if debug:
                print(f"  [DEBUG] 找到包含里或村的: {long_name}")
            return long_name, comp.get('types', [])

    for comp in components:
        kinds = comp.get('types', [])
        if any(t in kinds for t in ('administrative_area_level_4', 'administrative_area_level_3', 'sublocality', 'neighborhood')):
            long_name = comp.get('long_name', '')
            if not fallback_li:
                fallback_li = long_name
                fallback_types = kinds
            if debug:
                print(f"  [DEBUG] 找到sublocality/neighborhood/level_3/level_4: {long_name} (types: {kinds})")
    return fallback_li, fallback_types


def get_li_from_address(address, debug=False):
    try:
        geocode_result = gmaps.geocode(address, language='zh-TW')
        if not geocode_result:
            if debug:
                print(f"  [DEBUG] 地址 '{address}' 無結果")
            return None

        components = geocode_result[0].get('address_components', [])
        location = geocode_result[0].get('geometry', {}).get('location')
        if debug:
            print(f"  [DEBUG] 地址 '{address}' 的所有組件:")
            for i, comp in enumerate(components):
                long_name = comp.get('long_name', '')
                types = comp.get('types', [])
                print(f"    [{i}] {long_name} (types: {types})")

        li, types = extract_li_from_components(components, debug=debug)
        if li:
            if '里' in li or '村' in li:
                return li

            if debug:
                print(f"  [DEBUG] 正向地理編碼候選值: {li}，可能不是正式里/村名，改用反向地理編碼檢查")

        if not location:
            if debug:
                print(f"  [DEBUG] 無法從正向地理編碼結果取得經緯度，無法執行反向地理編碼")
            return li

        reverse_result = gmaps.reverse_geocode((location['lat'], location['lng']), language='zh-TW')
        if not reverse_result:
            if debug:
                print(f"  [DEBUG] 反向地理編碼無結果")
            return li

        if debug:
            print(f"  [DEBUG] 反向地理編碼結果數量: {len(reverse_result)}")

        for j, result in enumerate(reverse_result):
            rev_components = result.get('address_components', [])
            if debug:
                print(f"  [DEBUG] 反向地理編碼 result[{j}] 的組件:")
                for k, comp in enumerate(rev_components):
                    long_name = comp.get('long_name', '')
                    types = comp.get('types', [])
                    print(f"    [{k}] {long_name} (types: {types})")

            reverse_li, _ = extract_li_from_components(rev_components, debug=debug)
            if reverse_li:
                if debug:
                    print(f"  [DEBUG] 反向地理編碼找到可能的里/村: {reverse_li}")
                return reverse_li

        if debug:
            print(f"  [DEBUG] 反向地理編碼也未找到合適的里或村資訊")
        return li
    except Exception as e:
        message = str(e)
        if any(code in message for code in ('OVER_QUERY_LIMIT', 'RESOURCE_EXHAUSTED', 'dailyLimitExceeded', 'rateLimitExceeded')):
            raise RuntimeError(f'API limit reached or rate limit exceeded: {message}')
        raise


def is_filled(value):
    if pd.isna(value):
        return False
    if isinstance(value, str) and value.strip() == '':
        return False
    return True


if os.path.exists(OUTPUT_CSV):
    df = pd.read_csv(OUTPUT_CSV, encoding='utf-8')
    if '里或村' not in df.columns:
        df['里或村'] = None
    # 確保欄位類型是 object (字符串)
    df['里或村'] = df['里或村'].astype('object')
else:
    df = pd.read_csv(INPUT_CSV, encoding='utf-8')
    if '里或村' not in df.columns:
        df['里或村'] = None
    # 確保欄位類型是 object (字符串)
    df['里或村'] = df['里或村'].astype('object')

if df['里或村'].apply(is_filled).all():
    print("OK: '里或村' 欄位已經全部填滿。")
    sys.exit(0)

# 調試模式：對前5筆未填滿的紀錄進行調試
debug_count = 0
for index, row in df.iterrows():
    if is_filled(row.get('里或村')):
        continue

    full_address = f"{row.get('土地位置建物門牌', '')}"
    
    # 前5筆記錄啟用調試
    debug = debug_count < 5
    if debug:
        print(f"[記錄 {index}]")
    
    try:
        li = get_li_from_address(full_address, debug=debug)
    except RuntimeError as e:
        print(str(e))
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
        print(f"已保存進度到 {OUTPUT_CSV}，請稍後再繼續執行。")
        sys.exit(1)
    except Exception as e:
        print(f"Error geocoding {full_address}: {e}")
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
        print(f"未知錯誤，已保存進度到 {OUTPUT_CSV}。")
        sys.exit(1)

    # 檢查是否在參考檔案中有 match
    county_city = row.get('縣市', '')
    district = row.get('鄉鎮市區', '')
    full_county = f"{county_city}{district}"
    if li and match_village(full_county, li):
        df.at[index, '里或村'] = li
        if debug:
            print(f"  [DEBUG] ✓ 匹配成功: {li}")
    elif li:
        # 無法匹配時填入 "X" 並繼續處理
        df.at[index, '里或村'] = "X"
        if debug:
            print(f"  [DEBUG] ✗ 未能在參考檔案中匹配: {li} (縣市區: {full_county}) - 填入 X")
        print(f"⚠️  第 {index + 2} 行無法匹配村里 '{li}'，已填入 'X'")
    elif debug:
        print(f"  [DEBUG] 未取得村里資訊")
    
    # 每處理 100 行就保存一次進度
    if (index + 1) % 100 == 0:
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
        print(f"💾 已處理 {index + 1} 行，已保存進度到 {OUTPUT_CSV}")
    
    debug_count += 1
    time.sleep(SLEEP_SECONDS)

# Save result
df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
print(f"Done! 已將 '里或村' 欄位寫入 {OUTPUT_CSV}")
