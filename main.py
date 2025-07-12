import os
import json
import time
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, jsonify, request
from flask_cors import CORS
from pytrends.request import TrendReq
import random

app = Flask(__name__)
CORS(app)

# Global variables สำหรับเก็บข้อมูลและ cache
cached_trends = []
last_update = None
update_interval = 30 * 24 * 60 * 60  # 30 วัน (วินาที)

# คำค้นหาหลักสำหรับดึงเทรนด์ธุรกิจ
BUSINESS_KEYWORDS = [
    'ธุรกิจ', 'ลงทุน', 'ขายของออนไลน์', 'ร้านค้า', 'ธุรกิจออนไลน์',
    'แฟรนไชส์', 'สตาร์ทอัพ', 'ขายของ', 'ร้านอาหาร', 'บริการ',
    'คาเฟ่', 'เบเกอรี่', 'ความงาม', 'แฟชั่น', 'คอร์สออนไลน์'
]

# คำที่ใช้กรองข้อมูลที่ไม่เกี่ยวกับธุรกิจ
BUSINESS_FILTER_KEYWORDS = [
    'ธุรกิจ', 'ร้าน', 'ขาย', 'บริการ', 'คาเฟ่', 'กาแฟ', 'อาหาร',
    'เบเกอรี่', 'ความงาม', 'แฟชั่น', 'คอร์ส', 'ออนไลน์', 'แฟรนไชส์',
    'ลงทุน', 'เปิด', 'ทำ', 'สร้าง', 'เริ่มต้น', 'ขยาย', 'พัฒนา',
    'ตลาด', 'ลูกค้า', 'ผลิต', 'จำหน่าย', 'กิจการ', 'รายได้'
]

def is_business_related(query):
    """ตรวจสอบว่าคำค้นหาเกี่ยวกับธุรกิจหรือไม่"""
    query_lower = query.lower()
    
    # ตรวจสอบคำสำคัญที่เกี่ยวกับธุรกิจ
    for keyword in BUSINESS_FILTER_KEYWORDS:
        if keyword in query_lower:
            return True
    
    # กรองคำที่ไม่เกี่ยวกับธุรกิจ
    excluded_keywords = [
        'ข่าว', 'การเมือง', 'กีฬา', 'ดารา', 'ซีรี่ย์', 'หนัง',
        'เกม', 'อนิเมะ', 'มิวสิค', 'ท่องเที่ยว', 'สุขภาพ',
        'โรคระบาด', 'สงคราม', 'อุบัติเหตุ'
    ]
    
    for excluded in excluded_keywords:
        if excluded in query_lower:
            return False
    
    return True

def clean_and_filter_trends(trends_data):
    """ทำความสะอาดและกรองข้อมูลเทรนด์"""
    cleaned_trends = set()
    
    for trend in trends_data:
        # ลบช่องว่างและทำให้เป็นตัวพิมพ์ใหญ่ที่ต้นคำ
        clean_trend = trend.strip().title()
        
        # ตรวจสอบว่าเกี่ยวกับธุรกิจหรือไม่
        if is_business_related(clean_trend) and len(clean_trend) > 3:
            cleaned_trends.add(clean_trend)
    
    return list(cleaned_trends)

def fetch_trending_data():
    """ดึงข้อมูลเทรนด์จาก Google Trends"""
    try:
        print("🔄 กำลังดึงข้อมูลเทรนด์ใหม่...")
        pytrends = TrendReq(hl='th-TH', tz=360)
        
        all_trends = set()
        
        # ดึงข้อมูลจากหลาย ๆ กลุ่มคำค้นหา
        for i in range(0, len(BUSINESS_KEYWORDS), 3):
            batch = BUSINESS_KEYWORDS[i:i+3]
            
            try:
                # เพิ่มการหน่วงเวลาเพื่อหลีกเลี่ยง rate limit
                time.sleep(2)
                
                pytrends.build_payload(batch, geo='TH', timeframe='now 7-d')
                related = pytrends.related_queries()
                
                for keyword in batch:
                    if keyword in related:
                        # ดึง top queries
                        if related[keyword]['top'] is not None:
                            top_queries = related[keyword]['top']['query'].tolist()
                            all_trends.update(top_queries[:8])
                        
                        # ดึง rising queries
                        if related[keyword]['rising'] is not None:
                            rising_queries = related[keyword]['rising']['query'].tolist()
                            all_trends.update(rising_queries[:5])
                            
            except Exception as e:
                print(f"⚠️ Error processing batch {batch}: {str(e)}")
                continue
        
        # กรองและทำความสะอาดข้อมูล
        filtered_trends = clean_and_filter_trends(all_trends)
        
        # เรียงลำดับและเลือก 15 อันดับแรก (เผื่อไว้บ้าง)
        top_trends = filtered_trends[:15]
        
        print(f"✅ ดึงข้อมูลเทรนด์ได้ {len(top_trends)} รายการ")
        return top_trends
        
    except Exception as e:
        print(f"❌ Error fetching trends: {str(e)}")
        return []

def get_fallback_trends():
    """ข้อมูลสำรองเมื่อไม่สามารถดึงจาก API ได้"""
    return [
        "แฟรนไชส์กาแฟสด",
        "ธุรกิจออนไลน์",
        "ธุรกิจอสังหาริมทรัพย์",
        "เปิดร้านเบเกอรี่",
        "อาหารสุขภาพ",
        "เครื่องสำอางเกาหลี",
        "บริการเดลิเวอรี่",
        "เสื้อผ้าแฟชั่น",
        "คอร์สออนไลน์",
        "ขายของใน TikTok",
        "ธุรกิจขนม",
        "ร้านดอกไม้",
        "บริการทำความสะอาด",
        "อาหารเสริม",
        "ธุรกิจน้ำดื่ม"
    ]

def update_trends_cache():
    """อัปเดตข้อมูลเทรนด์ในแคช"""
    global cached_trends, last_update
    
    # ดึงข้อมูลใหม่
    new_trends = fetch_trending_data()
    
    if new_trends and len(new_trends) >= 5:
        cached_trends = new_trends[:10]  # เก็บ 10 อันดับแรก
    else:
        # ใช้ข้อมูลสำรอง
        fallback = get_fallback_trends()
        cached_trends = fallback[:10]
    
    last_update = datetime.now()
    print(f"📊 อัปเดตข้อมูลเทรนด์เรียบร้อยแล้ว ({len(cached_trends)} รายการ)")

def should_update_cache():
    """ตรวจสอบว่าควรอัปเดตแคชหรือไม่"""
    if not cached_trends or last_update is None:
        return True
    
    time_since_update = (datetime.now() - last_update).total_seconds()
    return time_since_update > update_interval

def background_update():
    """อัปเดตข้อมูลในพื้นหลัง"""
    while True:
        try:
            if should_update_cache():
                update_trends_cache()
            
            # ตรวจสอบทุก 1 ชั่วโมง
            time.sleep(3600)
            
        except Exception as e:
            print(f"❌ Error in background update: {str(e)}")
            time.sleep(3600)

# เริ่มต้นข้อมูลเทรนด์
update_trends_cache()

# เริ่ม background thread สำหรับอัปเดตอัตโนมัติ
background_thread = Thread(target=background_update, daemon=True)
background_thread.start()

@app.route("/")
def home():
    """หน้าแรก - ข้อมูล API"""
    return jsonify({
        "service": "Thai Business Trends API",
        "version": "2.0",
        "description": "API สำหรับดึงข้อมูลธุรกิจยอดนิยมจาก Google Trends",
        "endpoints": {
            "/api/trends": "ดึงข้อมูลธุรกิจยอดนิยม 10 อันดับแรก",
            "/api/trends/fresh": "บังคับอัปเดตข้อมูลใหม่",
            "/api/status": "สถานะการทำงานของระบบ"
        },
        "features": [
            "🔌 Web API พร้อมใช้งาน",
            "📊 ดึงเทรนด์จาก Google Trends",
            "🧹 คัดกรองข้อมูลธุรกิจ",
            "📤 ส่งข้อมูล JSON",
            "🔄 อัปเดตอัตโนมัติทุกเดือน"
        ],
        "status": "running",
        "last_update": last_update.isoformat() if last_update else None,
        "cached_trends_count": len(cached_trends)
    })

@app.route("/api/trends")
def get_trends():
    try:
        if should_update_cache():
            update_trends_cache()

        # ✅ ป้องกัน last_update เป็น None
        last = last_update.isoformat() if isinstance(last_update, datetime) else None
        next_update = (
            (last_update + timedelta(seconds=update_interval)).isoformat()
            if isinstance(last_update, datetime)
            else None
        )

        return jsonify({
            "trends": cached_trends,
            "last_update": last,
            "next_update": next_update,
            "total_count": len(cached_trends)
        })

    except Exception as e:
        return jsonify({
            "error": str(e),
            "fallback_trends": get_fallback_trends()[:10]
        }), 500
        
@app.route("/api/trends/fresh")
def get_fresh_trends():
    """บังคับอัปเดตข้อมูลใหม่"""
    try:
        update_trends_cache()
        
        return jsonify({
            "message": "อัปเดตข้อมูลเทรนด์ใหม่เรียบร้อย",
            "trends": cached_trends,
            "updated_at": last_update.isoformat() if isinstance(last_update, datetime) else None,
            "total_count": len(cached_trends)
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "ไม่สามารถอัปเดตข้อมูลได้"
        }), 500

@app.route("/api/status")
def get_status():
    """สถานะการทำงานของระบบ"""
    uptime_seconds = (datetime.now() - last_update).total_seconds() if last_update else 0
    
    return jsonify({
        "status": "healthy",
        "uptime_seconds": uptime_seconds,
        "last_update": last_update.isoformat() if last_update else None,
        "cached_trends_count": len(cached_trends),
        "update_interval_days": update_interval / (24 * 60 * 60),
        "next_update_in_seconds": max(0, update_interval - uptime_seconds) if last_update else 0,
        "background_thread_alive": background_thread.is_alive()
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": [
            "/",
            "/api/trends",
            "/api/trends/fresh", 
            "/api/status"
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal server error",
        "message": "กรุณาลองใหม่อีกครั้ง"
    }), 500

# 🔍 ทดสอบ pytrends ดึงข้อมูลได้ไหม
def test_pytrends_connection():
    from pytrends.request import TrendReq

    print("🚀 ทดสอบ pytrends...")

    try:
        pytrends = TrendReq(hl='th-TH', tz=360)
        pytrends.build_payload(kw_list=["ธุรกิจ"], geo="TH", timeframe="now 7-d")
        related = pytrends.related_queries()

        if related and "ธุรกิจ" in related:
            print("✅ ดึงข้อมูลสำเร็จ:")
            print("🔸 top:", related["ธุรกิจ"].get("top"))
            print("🔸 rising:", related["ธุรกิจ"].get("rising"))
        else:
            print("⚠️ ไม่มีข้อมูล related queries เลย (อาจถูก block หรือคำค้นไม่แม่น)")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")

# เรียกฟังก์ชันทดสอบ
test_pytrends_connection()

if __name__ == "__main__":
    print("🚀 Starting Thai Business Trends API...")
    print("📊 Initial trends data loaded")
    print("🔄 Background update thread started")
    print("✅ API ready on http://0.0.0.0:8080")
    
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)

# updated for Render deploy
