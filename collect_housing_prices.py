import pandas as pd
import os

# 定義季度列表
#quarters = ['2025Q2', '2025Q3', '2025Q4', '2026Q1']
quarters = ['2026Q1']

# 基礎路徑
base_path = '/home/will/housing'

# 收集所有資料的列表
all_data = []

for quarter in quarters:
    # manifest.csv 路徑
    manifest_path = os.path.join(base_path, quarter, 'lvr_landcsv', 'manifest.csv')
    
    # 讀取 manifest.csv
    manifest_df = pd.read_csv(manifest_path, encoding='utf-8')
    
    # 過濾出買賣檔案：name 以 _a.csv 結尾的
    buy_files = manifest_df[manifest_df['name'].str.endswith('_a.csv')]['name'].tolist()
    
    for file in buy_files:
        # CSV 檔案路徑
        csv_path = os.path.join(base_path, quarter, 'lvr_landcsv', file)
        
        # 讀取 CSV
        df = pd.read_csv(csv_path, encoding='utf-8')
        
        # 過濾交易標的包含 '房地' 的列
        filtered = df[df['交易標的'].str.contains('房地', na=False)]
        
        # 提取所需欄位
        selected = filtered[['鄉鎮市區', '土地位置建物門牌', '總價元']].copy()
        
        # 添加季度資訊
        selected['季度'] = quarter
        
        # 提取縣市名稱：從 description 中去掉 '不動產買賣'
        county = manifest_df[manifest_df['name'] == file]['description'].str.replace('不動產買賣', '').iloc[0]
        selected['縣市'] = county
        
        # 添加到列表
        all_data.append(selected)

# 合併所有資料
final_df = pd.concat(all_data, ignore_index=True)

# 儲存到新檔案
output_path = os.path.join(base_path, 'collected_housing_prices_2026Q1.csv')
final_df.to_csv(output_path, index=False, encoding='utf-8')

print(f"資料已收集並儲存到 {output_path}")