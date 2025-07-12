import os
import time
import pandas as pd
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, jsonify, request
from flask_cors import CORS
from pytrends.request import TrendReq

app = Flask(__name__)
CORS(app)

cached_trends = []
last_update = None
update_interval = 30 * 24 * 60 * 60  # 30 วัน

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
                        top_df = related[keyword].get("top")
                        rising_df = related[keyword].get("rising")

                        if isinstance(top_df, pd.DataFrame) and not top_df.empty and "query" in top_df.columns:
                            all_trends.update(top_df["query"].head(8).tolist())

                        if isinstance(rising_df, pd.DataFrame) and not rising_df.empty and "query" in rising_df.columns:
                            all_trends.update(rising_df["query"].head(5).tolist())

            except Exception as e:
                print(f"⚠️ Error batch {batch}: {e}")
                continue

        filtered_trends = clean_and_filter_trends(all_trends)
        print(f"✅ ดึงข้อมูลเทรนด์ได้ {len(filtered_trends[:15])} รายการ")
        return filtered_trends[:15]
    except Exception as e:
        print(f"❌ Error fetching trends: {e}")
        return []





def update_trends_cache():
    global cached_trends, last_update
    new_trends = fetch_trending_data()
    if new_trends and len(new_trends) >= 5:
        cached_trends = new_trends[:10]
    else:
        cached_trends = get_fallback_trends()[:10]
    last_update = datetime.now()
    print(f"📊 อัปเดตข้อมูลเทรนด์เรียบร้อยแล้ว ({len(cached_trends)} รายการ)")


def should_update_cache():
    if not cached_trends or last_update is None:
        return True
    elapsed = (datetime.now() - last_update).total_seconds()
    return elapsed > update_interval


def background_update():
    while True:
        try:
            if should_update_cache():
                update_trends_cache()
            time.sleep(3600)
        except Exception as e:
            print(f"❌ Error in background update: {e}")
            time.sleep(3600)


@app.route("/")
def home():
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


def test_pytrends_connection():
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
            print("⚠️ ไม่มีข้อมูล related queries เลย")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")


# เรียกฟังก์ชันตอนเริ่มระบบ
test_pytrends_connection()

# เริ่ม background thread
background_thread = Thread(target=background_update, daemon=True)
background_thread.start()

# รัน Flask app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print("✅ API ready on http://0.0.0.0:" + str(port))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
