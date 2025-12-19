from datetime import datetime, timedelta, timezone
from config import *
import pytz

def get_weather_condition(precip_amount, cloudiness):
    """天気条件を判定する"""
    if precip_amount > 1.0:
        return "雨強め"
    elif precip_amount > 0.2:
        return "弱い雨"
    elif cloudiness < 20:
        return "晴れ"
    else:
        return "くもり"

def in_time_window(dt):
    h = dt.hour
    # 早朝: 4時以上7時未満、夕方: 16時以上19時未満
    return (
        (EARLY_MORNING[0] <= h < EARLY_MORNING[1])
        or (EVENING[0] <= h < EVENING[1])
    )

def get_date_start(dt):
    """指定日時の当日0時を取得（UTC）"""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

def get_date_end(dt):
    """指定日時の当日23:59:59を取得（UTC）"""
    return dt.replace(hour=23, minute=59, second=59, microsecond=0)

def check_precipitation_today(timeseries, current_dt):
    """当日中（24:00まで）に雨の予報があるかチェック"""
    jst = pytz.timezone('Asia/Tokyo')
    date_start = get_date_start(current_dt)
    date_end = get_date_end(current_dt)
    
    for t in timeseries:
        dt_utc = datetime.fromisoformat(t["time"].replace("Z", "+00:00"))
        dt = dt_utc.astimezone(jst)
        
        # 当日中のみチェック
        if dt < date_start or dt > date_end:
            continue
        
        # 現在時点より未来の予報のみチェック
        if dt <= current_dt:
            continue
        
        precip = 0
        if "next_1_hours" in t["data"]:
            precip = t["data"]["next_1_hours"]["details"].get(
                "precipitation_amount", 0
            )
        elif "next_6_hours" in t["data"]:
            precip = t["data"]["next_6_hours"]["details"].get(
                "precipitation_amount", 0
            )
        
        if precip > MAX_PRECIP_OK:
            return True
    
    return False

def check_high_temp_duration(timeseries, current_dt):
    """当日中に30度以上が3時間以上続くかチェック"""
    jst = pytz.timezone('Asia/Tokyo')
    date_start = get_date_start(current_dt)
    date_end = get_date_end(current_dt)
    
    high_temp_hours = 0
    max_consecutive = 0
    current_consecutive = 0
    
    for t in timeseries:
        dt_utc = datetime.fromisoformat(t["time"].replace("Z", "+00:00"))
        dt = dt_utc.astimezone(jst)
        
        # 当日中のみチェック
        if dt < date_start or dt > date_end:
            continue
        
        # 現在時点より未来の予報のみチェック
        if dt <= current_dt:
            continue
        
        inst = t["data"]["instant"]["details"]
        temp = inst.get("air_temperature", 0)
        
        if temp >= HIGH_TEMP_THRESHOLD:
            high_temp_hours += 1
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    
    return max_consecutive >= HIGH_TEMP_DURATION_HOURS

def check_rain_within_hours(timeseries, current_dt, hours=RAIN_AFTER_HOURS):
    """過去N時間以内に雨があったかチェック"""
    jst = pytz.timezone('Asia/Tokyo')
    time_limit = current_dt - timedelta(hours=hours)
    
    for t in timeseries:
        dt_utc = datetime.fromisoformat(t["time"].replace("Z", "+00:00"))
        dt = dt_utc.astimezone(jst)
        
        # 過去のデータのみチェック
        if dt > current_dt:
            break
        
        # 時間範囲外ならスキップ（タイムスタンプ自体が範囲外）
        if dt < time_limit:
            continue
        
        # next_1_hoursは、dtからdt+1時間の降水量を示す
        # 現在時刻がその期間内にあれば、雨があった可能性がある
        if "next_1_hours" in t["data"]:
            precip = t["data"]["next_1_hours"]["details"].get(
                "precipitation_amount", 0
            )
            # dtから1時間以内に現在時刻が含まれるか、またはその期間が過去6時間内に含まれるか
            period_end = dt + timedelta(hours=1)
            if period_end >= time_limit and dt <= current_dt and precip > MAX_PRECIP_OK:
                return True
    
    return False

def judge(timeseries):
    results = []
    # 日本時間（JST）のタイムゾーンを取得
    jst = pytz.timezone('Asia/Tokyo')

    for i, t in enumerate(timeseries):
        dt_utc = datetime.fromisoformat(t["time"].replace("Z", "+00:00"))
        # UTC時刻をJST（日本時間）に変換
        dt = dt_utc.astimezone(jst)
        
        # 散布可能時間帯かどうかを判定
        is_spray_time = in_time_window(dt)
        
        # すべての時間帯のデータを返す（散布可能時間帯外も含む）
        # 表示対象の時間帯のみに限定（4-7時、8-15時、16-19時、20-23時）
        if not ((4 <= dt.hour <= 7) or (8 <= dt.hour <= 15) or (16 <= dt.hour <= 19) or (20 <= dt.hour <= 23)):
            continue

        inst = t["data"]["instant"]["details"]
        wind = inst.get("wind_speed", 0)
        temp = inst.get("air_temperature", 0)
        cloudiness = inst.get("cloud_area_fraction", 0)  # 雲量（0-100%）

        precip = 0
        if "next_1_hours" in t["data"]:
            precip = t["data"]["next_1_hours"]["details"].get(
                "precipitation_amount", 0
            )
        
        # 天気条件を計算
        condition = get_weather_condition(precip, cloudiness)

        status = "GREEN"
        reason = []
        recommendations = []
        warnings = []

        # すべての時間帯で基本的な判定ロジックを適用
        # 風速チェック
        if wind > MAX_WIND_OK:
            status = "RED"
            reason.append("風が強い")
        elif is_spray_time and wind < MAX_WIND_FOLIAR:
            # 葉面散布肥料の推奨は散布可能時間帯のみ
            recommendations.append("葉面散布肥料に適した風速です（0.5m/s未満）")

        # 降雨リスクチェック
        if precip > MAX_PRECIP_OK:
            status = "RED"
            reason.append("降雨リスク")

        # 気温チェック
        if temp < MIN_TEMP or temp > MAX_TEMP:
            status = "YELLOW"
            reason.append("気温注意")

        # 1. 当日中の降雨予報チェック
        if check_precipitation_today(timeseries, dt):
            warnings.append("⚠️ 当日中に雨の予報があります。農薬・葉面散布肥料が流亡する可能性があるため注意してください。")

        # 4. 30度以上3時間以上続く場合の注意
        if check_high_temp_duration(timeseries, dt):
            warnings.append("⚠️ 日中30度以上が3時間以上続く予報です。肥料やけ・農薬やけの注意が必要です。")

        # 5. 雨の後6時間の殺虫剤散布適時
        if check_rain_within_hours(timeseries, dt, RAIN_AFTER_HOURS):
            recommendations.append("🌧️ 雨の後6時間以内です。殺虫剤散布に適したタイミングです。")

        results.append({
            "time": dt.isoformat(),
            "wind": wind,
            "temp": temp,
            "precip": precip,
            "cloudiness": cloudiness,
            "condition": condition,
            "status": status,
            "reason": reason,
            "recommendations": recommendations,
            "warnings": warnings,
            "is_spray_time": is_spray_time  # 散布可能時間帯かどうかのフラグ
        })

    return results