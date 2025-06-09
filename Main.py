import network
import urequests
import ntptime
import time
from machine import Pin, SPI
from st7735 import TFT
from font import FONT8x8

ICON_SCALE = 1.3

def scale(val):
    """Scale helper for icon dimensions."""
    return int(val * ICON_SCALE)


def draw_sunny(cx, cy):
    col = weather_color("晴")
    r = scale(12)
    tft.fillcircle((cx, cy), r, col)
    for dx, dy in [
        (0, -1), (0, 1), (-1, 0), (1, 0),
        (1, 1), (-1, -1), (1, -1), (-1, 1)
    ]:
        tft.line((cx + dx * scale(14), cy + dy * scale(14)),
                 (cx + dx * scale(20), cy + dy * scale(20)), col)

def draw_cloudy(cx, cy):
    col = weather_color("曇")
    tft.fillcircle((cx - scale(6), cy + scale(2)), scale(10), col)
    tft.fillcircle((cx + scale(6), cy + scale(2)), scale(10), col)
    tft.fillcircle((cx, cy - scale(2)), scale(12), col)

def draw_rainy(cx, cy):
    draw_cloudy(cx, cy - scale(4))
    rain_col = weather_color("雨")
    for dx in (-6, 0, 6):
        tft.line((cx + scale(dx), cy + scale(6)),
                 (cx + scale(dx), cy + scale(12)), rain_col)

def draw_weather_icon(weather, cx, cy):
    if "晴" in weather:
        draw_sunny(cx, cy)
    elif "曇" in weather:
        draw_cloudy(cx, cy)
    elif "雨" in weather:
        draw_rainy(cx, cy)
    else:
        tft.fillcircle((cx, cy), scale(12), weather_color(weather))
        tft.text((cx - scale(12), cy - scale(8)),
                 convert_to_romaji(weather)[:4], tft.BLACK, FONT8x8)

# Wi-Fi設定
SSID = "aterm-4b854e-a"
PASSWORD = "29a167324e3d9"

# SPIと液晶初期化
spi = SPI(1, baudrate=20000000, polarity=0, phase=0,
          sck=Pin(10), mosi=Pin(11), miso=Pin(8))
dc, reset, cs = 8, 12, 9
tft = TFT(spi, dc, reset, cs)
tft.initg()
tft.rotation(1)
tft.fill(tft.BLACK)

# 天気→色変換
def weather_color(w):
    if "晴" in w:
        return tft.color(255, 180, 0)  # オレンジ
    elif "曇" in w:
        return tft.color(120, 120, 120)  # グレー
    elif "雨" in w:
        return tft.color(70, 180, 255)  # 水色
    else:
        return tft.WHITE

# ローマ字変換（日本語→ローマ字表示用, 必要なら追加）
jp_to_romaji = {
    "曇": "Kumori",
    "雨": "Ame",
    "晴": "Hare",
    "のち": "nochi",
    "一時": "ichiji",
    "時々": "tokidoki"
}

def convert_to_romaji(text):
    for jp, ro in jp_to_romaji.items():
        text = text.replace(jp, ro)
    return text

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            time.sleep(1)
    return wlan

def sync_time():
    try:
        ntptime.settime()
    except:
        print("NTP sync failed.")

def get_forecast():
    try:
        res = urequests.get("https://www.jma.go.jp/bosai/forecast/data/forecast/130000.json")
        if res.status_code == 200:
            data = res.json()
            weather = data[0]["timeSeries"][0]["areas"][0]["weathers"][0]
            rain = data[0]["timeSeries"][1]["areas"][0]["pops"][0]
            forecast_time = data[0].get("reportDatetime", "")
            return weather, rain, forecast_time
        else:
            return "HTTP error", "?", ""
    except Exception as e:
        print(e)
        return "Fetch error", "?", ""

def text_double(pos, message, color):
    """Render text at double size. Attempts to use scale parameter if available
    and falls back to simple pixel doubling."""
    try:
        # Some drivers support an additional scale argument
        tft.text(pos, message, color, FONT8x8, 2)
    except TypeError:
        x, y = pos
        for dy in (0, 1):
            for dx in (0, 1):
                tft.text((x + dx, y + dy), message, color, FONT8x8)

def draw_weather_transition(prev_weather, curr_weather, curr_pop, timestamp):
    tft.fill(tft.BLACK)
    base_y = 80
    r = 32
    left_x, right_x = 32, 128

    # 画面上部1行目に更新時刻を表示
    tft.text((4, 8), "Update: {}".format(timestamp), tft.CYAN, FONT8x8)

    # 天気ピクトグラム (15%上に移動)
    icon_y = int(base_y * 0.85)
    draw_weather_icon(prev_weather, left_x, icon_y)
    draw_weather_icon(curr_weather, right_x, icon_y)

    # 太く短い矢印
    arrow_y = base_y
    arrow_start = left_x + r + 2
    arrow_end = right_x - r - 2
    for i in range(-1, 2):
        tft.line((arrow_start, arrow_y+i), (arrow_end, arrow_y+i), tft.WHITE)
    tft.line((arrow_end, arrow_y), (arrow_end-10, arrow_y-7), tft.WHITE)
    tft.line((arrow_end, arrow_y), (arrow_end-10, arrow_y+7), tft.WHITE)

    # 矢印の下に降水確率を2倍サイズで表示
    pop_text = "POP: {}%".format(curr_pop)
    text_width = len(pop_text) * 16  # approximate width of double-sized text
    pop_x = (arrow_start + arrow_end - text_width) // 2
    text_double((pop_x, arrow_y + 10), pop_text, tft.CYAN)

# --- メイン処理 ---

connect_wifi()
sync_time()

last_weather = 0
weather_buf = ["--", "--"]
pop_buf = "--"
timestamp = "--:--"
prev_draw = ("", "", "", "")  # 前回表示した内容

while True:
    now = time.time()
    if now - last_weather > 1800 or weather_buf[1] == "--":  # 30分ごと更新
        prev = weather_buf[1]
        curr, curr_pop, ftime = get_forecast()
        weather_buf = [prev, curr]
        pop_buf = curr_pop
        if ftime:
            timestamp = ftime[11:16]
        else:
            t = time.localtime(time.time() + 9*3600)
            timestamp = "{:02}:{:02}".format(t[3], t[4])
        last_weather = now

    # フリッカー防止：内容が変わった時だけ描画
    draw_tuple = (weather_buf[0], weather_buf[1], pop_buf, timestamp)
    if draw_tuple != prev_draw:
        draw_weather_transition(*draw_tuple)
        prev_draw = draw_tuple

    time.sleep(1)
