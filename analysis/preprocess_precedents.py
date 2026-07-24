import pandas as pd
import json
import os

def preprocess_precedents():
    # Define absolute paths for security and reliability
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    xls_path = os.path.join(BASE_DIR, 'law_etc/판례정보_농지연금_농지관련.xls')
    output_json = os.path.join(BASE_DIR, 'law_etc/판례정보_농지연금_농지관련_정제.json')
    output_xlsx = os.path.join(BASE_DIR, 'law_etc/판례정보_농지연금_농지관련_정제.xlsx')
    streamlit_json = os.path.join(BASE_DIR, 'app_build_streamlit/data/precedents.json')
    
    print(f"Reading raw precedents XLS from: {xls_path}")
    if not os.path.exists(xls_path):
        print(f"Error: {xls_path} does not exist!")
        return

    # Load file
    df = pd.read_excel(xls_path)
    
    # 1. Forward-fill empty '번호', '사건번호', '제목' to bundle multi-row items together
    # Create groups based on '번호' being non-null
    df['group_id'] = df['번호'].ffill()
    
    # In case the first row starts without '번호' but is part of the first precedent
    df['group_id'] = df['group_id'].fillna(1)
    
    grouped = df.groupby('group_id')
    final_records = []
    
    for gid, group in grouped:
        # Obtain non-null single values (usually the first row has them, but we use first non-null just in case)
        num_val = group['번호'].dropna().first_valid_index()
        num = int(group.loc[num_val, '번호']) if num_val is not None else int(gid)
        
        title_idx = group['제목'].dropna().first_valid_index()
        title = str(group.loc[title_idx, '제목']).strip() if title_idx is not None else ""
        
        case_idx = group['사건번호'].dropna().first_valid_index()
        case_num = str(group.loc[case_idx, '사건번호']).strip() if case_idx is not None else ""
        
        date_idx = group['선고일자'].dropna().first_valid_index()
        date_str = str(group.loc[date_idx, '선고일자']).strip() if date_idx is not None else ""
        
        # Collect and merge unique legal references (참조조문) and article numbers (조문번호)
        laws = []
        for law in group['참조조문'].dropna():
            # split by comma just in case
            for part in str(law).split(','):
                part_stripped = part.strip()
                if part_stripped and part_stripped not in laws:
                    laws.append(part_stripped)
                    
        articles = []
        for art in group['조문번호'].dropna():
            for part in str(art).split(','):
                part_stripped = part.strip()
                if part_stripped and part_stripped not in articles:
                    articles.append(part_stripped)
                    
        # Merge multi-line case highlights / judgments (판시사항)
        highlights = []
        for hl in group['판시사항'].dropna():
            hl_stripped = str(hl).strip()
            if hl_stripped and hl_stripped not in highlights:
                highlights.append(hl_stripped)
        
        judgment_text = "\n\n".join(highlights).strip()
        
        final_rec = {
            "번호": num,
            "제목": title,
            "사건번호": case_num,
            "선고일자": date_str,
            "참조조문": ", ".join(laws),
            "조문번호": ", ".join(articles),
            "판시사항": judgment_text
        }
        final_records.append(final_rec)
        
    print(f"Processed {len(final_records)} unique precedent records.")
    
    # Save to JSON in law_etc/
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(final_records, f, ensure_ascii=False, indent=2)
    print(f"Saved cleaned JSON to: {output_json}")
    
    # Save to JSON in app_build_streamlit/data/ for chatbot usage
    os.makedirs(os.path.dirname(streamlit_json), exist_ok=True)
    with open(streamlit_json, 'w', encoding='utf-8') as f:
        json.dump(final_records, f, ensure_ascii=False, indent=2)
    print(f"Saved Streamlit copy of JSON to: {streamlit_json}")
    
    # Save to Excel (.xlsx) in law_etc/
    df_clean = pd.DataFrame(final_records)
    df_clean.to_excel(output_xlsx, index=False)
    print(f"Saved cleaned Excel (.xlsx) to: {output_xlsx}")

if __name__ == '__main__':
    preprocess_precedents()
