import json
import os

def analyze_keywords():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(BASE_DIR, 'law_etc/판례정보_농지연금_농지관련_정제.json')
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} does not exist!")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        precedents = json.load(f)
        
    print(f"Total precedents to analyze: {len(precedents)}")
    
    categories = {
        "양도소득세 및 세금 분쟁": ["양도소득세", "취득세", "증여세", "상속세", "세금", "과세", "세액", "감면"],
        "농지법 위반 및 불법 전용": ["농지법위반", "불법전용", "무단전용", "전용허가", "형질변경", "잡석", "원상회복"],
        "농지보전부담금 분쟁": ["농지보전부담금", "부담금", "감면처분", "부과처분취소"],
        "기반시설 목적외사용 분쟁": ["목적외", "구거", "농로", "저수지", "사용료", "용수", "배수"],
        "농지처분의무 및 자경 분쟁": ["처분의무", "처분명령", "자경", "농지처분", "경작", "소유자격"]
    }
    
    cat_counts = {cat: 0 for cat in categories}
    uncategorized = 0
    
    for prec in precedents:
        text = (prec.get("제목", "") + " " + prec.get("판시사항", "") + " " + prec.get("참조조문", "")).lower()
        
        matched = False
        for cat, keywords in categories.items():
            if any(kw.lower() in text for kw in keywords):
                cat_counts[cat] += 1
                matched = True
                
        if not matched:
            uncategorized += 1
            
    print("\n--- 분석 결과 ---")
    for cat, count in cat_counts.items():
        ratio = (count / len(precedents)) * 100
        print(f"{cat}: {count} 건 ({ratio:.2f}%)")
        
    print(f"기타 분쟁: {uncategorized} 건 ({uncategorized/len(precedents)*100:.2f}%)")
    
if __name__ == '__main__':
    analyze_keywords()
