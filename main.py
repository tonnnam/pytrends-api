import os
import json
import time
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, jsonify, request
from flask_cors import CORS
from pytrends.request import TrendReq

app = Flask(__name__)
CORS(app)

cached_trends = []
last_update = None
update_interval = 30 * 24 * 60 * 60

BUSINESS_KEYWORDS = [
    'ธุรกิจ', 'ลงทุน', 'ขายของออนไลน์', 'ร้านค้า', 'ธุรกิจออนไลน์',
    'แฟรนไชส์', 'สตาร์ทอัพ', 'ขายของ', 'ร้านอาหาร', 'บริการ',
    'คาเฟ่', 'เบเกอรี่', 'ความงาม', 'แฟชั่น', 'คอร์สออนไลน์'
]

BUSINESS_FILTER_KEYWORDS_SET = set(k.lower() for k in [
    'ธุรกิจ', 'ร้าน', 'ขาย', 'บริการ', 'คาเฟ่', 'กาแฟ', 'อาหาร',
    'เบเกอรี่', 'ความงาม', 'แฟชั่น', 'คอร์ส', 'ออนไลน์', 'แฟรนไชส์',
    'ลงทุน', 'เปิด', 'ทำ', 'สร้าง', 'เริ่มต้น', 'ขยาย', 'พัฒนา',
    'ตลาด', 'ลูกค้า', 'ผลิต', 'จำหน่าย', 'กิจการ', 'รายได้'
])

EXCLUDED_KEYWORDS_SET = set(k.lower() for k in [
    'ข่าว', 'การเมือง', 'กีฬา', 'ดารา', 'ซีรี่ย์', 'หนัง',
    'เกม', 'อนิเมะ', 'มิวสิค', 'ท่องเที่ยว', 'สุขภาพ',
    'โรคระบาด', 'สงคราม', 'อุบัติเหตุ'
])

def is_business_related(query):
    query_lower = query.lower()
    if any(excluded in query_lower for excluded in EXCLUDED_KEYWORDS_SET):
        return False
    return any(keyword in query_lower for keyword in BUSINESS_FILTER_KEYWORDS_SET)

def clean_and_filter_trends(trends_data):
    cleaned_trends = {
        trend.strip().title()
        for trend in trends_data
        if is_business_related(trend.strip()) and len(trend.strip()) > 3
    }
    return list(cleaned_trends)

def fetch_trending_data():
    try:
        print("🔄 กำลังดึงข้อมูลเทรนด์ใหม่...")
        pytrends = TrendReq(hl='th-TH', tz=360)
        all_trends = set()

        for i in range(0, len(BUSINESS_KEYWORDS), 3):
            batch = BUSINESS_KEYWORDS[i:i+3]
            time.sleep(2)
            try:
                pytrends.build_payload(batch, geo='TH', timeframe='now 7-d')
                related = pytrends.related_queries()
                for keyword in batch:
                    if keyword in related:
                        if related[keyword].get('top') is not None:
                            all_trends.update(related[keyword]['top']['query'][:8])
                        if related[keyword].get('rising') is not None:
                            all_trends.update(related[keyword]['rising']['query'][:5])
            except Exception as e:
                print(f"⚠️ Error batch {batch}: {e}")
                continue

        filtered_trends = clean_and_filter_trends(all_trends)
        print(f"✅ ดึงข้อมูลเทรนด์ได้ {len(filtered_trends[:15])} รายการ")
        return filtered_trends[:15]
    except Exception as e:
        print(f"❌ Error fetching trends: {e}")
        return []

def get_fallback_trends():
    return [
        "แฟรนไชส์กาแฟสด", "ธุรกิจออนไลน์", "ธุรกิจอสังหาริมทรัพย์", "เปิดร้านเบเกอรี่", "อาหารสุขภาพ",
        "เครื่องสำอางเกาหลี", "บริการเดลิเวอรี่", "เสื้อผ้าแฟชั่น", "คอร์สออนไลน์", "ขายของใน TikTok"
    ]

# Additional functions omitted for brevity, assumed to remain unchanged from original
