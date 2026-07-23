import pandas as pd
import json
import os
import glob

def generate_static_data():
    os.makedirs('app_build_static/data', exist_ok=True)
    os.makedirs('app_build_streamlit/data', exist_ok=True)
    
    # 1. Process VOC QA Data (For Chatbot)
    qa_files = glob.glob('base_data/add_data/고객문의 답변사례*.csv')
    qa_list = []
    if qa_files:
        qa_df = pd.concat([pd.read_csv(f, encoding='cp949', usecols=['제목', '내용']).dropna() for f in qa_files])
        # Take 10 unique QA pairs for the PoC Chatbot
        qa_sample = qa_df.drop_duplicates(subset=['제목']).head(10)
        qa_list = qa_sample.to_dict('records')
    
    with open('app_build_streamlit/data/qa_pairs.json', 'w', encoding='utf-8') as f:
        json.dump(qa_list, f, ensure_ascii=False, indent=2)

    # 2. Process Time-Series Pension Data (2020-2024)
    ts_files = glob.glob('base_data/add_data/가입건수 및 월지급금*.csv')
    ts_data = {}
    for f in ts_files:
        year = f.split('(')[1].split(')')[0]
        try:
            df = pd.read_csv(f, encoding='cp949')
            # Extract sum of 가입건수
            ts_data[year] = int(df['가입건수'].sum())
        except Exception as e:
            pass
            
    # Sort by year
    ts_data = dict(sorted(ts_data.items()))
    
    # 3. Save for Static Dashboard (JS)
    try:
        pension_df = pd.read_csv('base_data/한국농어촌공사_농지연금 가입분석 및 평균 월지급금 현황_20251231.csv', encoding='cp949')
        region_payment = pension_df.groupby('지역(도)')['평균월지급금(천원)'].mean().round(0).to_dict()
    except:
        region_payment = {}
        
    try:
        voc_df = pd.read_csv('base_data/한국농어촌공사_고객의 소리 유형분석_20241231.csv', encoding='cp949')
        for col in ['칭찬', '질의', '불만', '요청']:
            voc_df[col] = pd.to_numeric(voc_df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        voc_summary = {
            '칭찬': int(voc_df['칭찬'].sum()),
            '질의': int(voc_df['질의'].sum()),
            '불만': int(voc_df['불만'].sum()),
            '요청': int(voc_df['요청'].sum())
        }
    except:
        voc_summary = {}

    results = {
        'region_payment': region_payment,
        'time_series_trend': ts_data,
        'voc_summary': voc_summary
    }

    with open('app_build_static/data/results.js', 'w', encoding='utf-8') as f:
        f.write("const resultsData = ")
        json.dump(results, f, ensure_ascii=False, indent=2)
        f.write(";")
        
    print("All data generated successfully.")

if __name__ == '__main__':
    generate_static_data()
