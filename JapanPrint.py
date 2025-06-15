# Japan Print - Display Machida weather on LCD and terminal
"""
Display the forecast for Machida City using the WeatherAPI service.
This script prints the weather information to both the terminal and
an ST7735 LCD. If your display driver and font support Japanese glyphs
(e.g. fonts from the Noto Sans CJK family), the weather text will be
shown in Japanese.

Installing Japanese fonts on Raspberry Pi OS / Debian:
    sudo apt-get update
    sudo apt-get install fonts-noto-cjk

After installing, configure your ST7735 driver to use a font file that
includes Japanese glyphs or render the text on the terminal where the
font is available.
"""

import network
import urequests
import ntptime
import time
from machine import Pin, SPI
from st7735 import TFT
from font import FONT8x8

# Wi-Fi credentials
SSID = "aterm-4b854e-a"
PASSWORD = "29a167324e3d9"

# WeatherAPI settings
API_KEY = "151a73f432ff4c5da0743413251406"
LOCATION = "Machida"

# Setup SPI LCD (ST7735)
spi = SPI(1, baudrate=20_000_000, polarity=0, phase=0,
          sck=Pin(10), mosi=Pin(11), miso=Pin(8))
tft = TFT(spi, 8, 12, 9)
tft.initg()
tft.rotation(1)
tft.fill(tft.BLACK)

# Optional romanization map when Japanese glyphs are unavailable
jp_to_romaji = {
    "曇": "Kumori",
    "雨": "Ame",
    "晴": "Hare",
    "のち": "nochi",
    "一時": "ichiji",
    "時々": "tokidoki",
}


def convert_to_romaji(text: str) -> str:
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
    except Exception:
        print("NTP sync failed")


def get_forecast():
    url = (
        f"https://api.weatherapi.com/v1/forecast.json?key={API_KEY}&"
        f"q={LOCATION}&days=1&lang=ja"
    )
    try:
        res = urequests.get(url)
        if res.status_code == 200:
            data = res.json()
            weather = data["forecast"]["forecastday"][0]["day"]["condition"]["text"]
            pop = str(
                data["forecast"]["forecastday"][0]["day"].get("daily_chance_of_rain", "?")
            )
            update = data.get("current", {}).get("last_updated", "")
            return weather, pop, update
        print("HTTP error", res.status_code)
    except Exception as exc:
        print("Fetch error", exc)
    return "--", "--", ""


def display_weather(weather: str, pop: str, timestamp: str):
    tft.fill(tft.BLACK)
    tft.text((2, 2), "町田市", tft.CYAN, FONT8x8)
    tft.text((2, 12), f"更新: {timestamp}", tft.CYAN, FONT8x8)
    try:
        tft.text((2, 26), weather, tft.WHITE, FONT8x8)
    except Exception:
        tft.text((2, 26), convert_to_romaji(weather), tft.WHITE, FONT8x8)
    tft.text((2, 38), f"降水確率: {pop}%", tft.WHITE, FONT8x8)

    print("町田市", timestamp)
    print(weather)
    print("降水確率", pop + "%")


if __name__ == "__main__":
    connect_wifi()
    sync_time()
    while True:
        w, p, ts = get_forecast()
        if ts:
            ts = ts[11:16]
        else:
            t = time.localtime(time.time() + 9 * 3600)
            ts = f"{t[3]:02}:{t[4]:02}"
        display_weather(w, p, ts)
        time.sleep(900)
