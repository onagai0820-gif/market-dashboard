#!/usr/bin/env python3
"""市場データとニュースを取得して docs/data/*.json を生成する。

依存ライブラリなし（Python 3.9+ の標準ライブラリのみ）。
"""

import gzip
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from symbols import ECB_CURRENCIES, GROUPS, MARKET_KEYWORDS, NEWS_FEEDS

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
JST = timezone(timedelta(hours=9))

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
# Twelve Data の無料枠は毎分8リクエストまで。余裕をみて8秒ごとに1件とする。
REQUEST_INTERVAL = float(os.environ.get("REQUEST_INTERVAL", "8"))
_last_request_at = 0.0

_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)


def http_get(url, timeout=25, headers=None, throttle=False):
    global _last_request_at
    if throttle:
        wait = REQUEST_INTERVAL - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()

    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "ja,en;q=0.8",
        "Accept-Encoding": "gzip",
        **(headers or {}),
    })
    with _opener.open(req, timeout=timeout) as res:
        raw = res.read()
        if res.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw


# --------------------------------------------------------------------------
# 市場データ
#
# 取得元は3つ。いずれも提供元が公開しているAPIで、非公式の内部エンドポイントは使わない。
#   FRED : 米セントルイス連銀。株価指数・金利・ボラティリティ・商品・暗号資産
#   ECB  : 欧州中央銀行の参照相場（Frankfurter経由）。為替
#   Twelve Data : 個別株・海外指数・貴金属。上2つに日次系列がないものだけ
# --------------------------------------------------------------------------

FRED_API_KEY = os.environ.get("FRED_API_KEY", "").strip()
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "").strip()

HISTORY_DAYS = 400  # 1年分の営業日を確保するため、暦日では多めに取る


def observation_window():
    end = datetime.now(timezone.utc).date()
    return end - timedelta(days=HISTORY_DAYS), end


def round_sig(value, digits=4):
    if value is None:
        return None
    magnitude = abs(value)
    if magnitude >= 1000:
        return round(value, 1)
    if magnitude >= 10:
        return round(value, 2)
    if magnitude >= 1:
        return round(value, 3)
    return round(value, max(digits, 6))


def make_quote(key, name, subtitle, unit, source, dates, values):
    """日付と終値の並びから、画面が使う1銘柄分のデータを組み立てる。"""
    if not values:
        raise ValueError("観測値がありません")

    hist_t = [
        int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        for d in dates
    ]
    hist_c = [round_sig(v) for v in values]

    price = hist_c[-1]
    prev_close = hist_c[-2] if len(hist_c) >= 2 else None
    change = change_pct = None
    if prev_close is not None:
        change = price - prev_close
        if prev_close != 0:
            change_pct = change / prev_close * 100

    # 52週の高安は「直近N件」では数えられない。暗号資産のように土日も値が付く系列と、
    # 週次でしか出ない系列とでは1年あたりの件数が違うため、日付で区切る。
    year_ago = (
        datetime.strptime(dates[-1], "%Y-%m-%d") - timedelta(days=365)
    ).strftime("%Y-%m-%d")
    window = [c for d, c in zip(dates, hist_c) if d >= year_ago] or hist_c

    return {
        "symbol": key,
        "name": name,
        "subtitle": subtitle,
        "unit": unit,
        "source": source,
        "price": price,
        "prev_close": prev_close,
        "change": round_sig(change),
        "change_pct": round(change_pct, 2) if change_pct is not None else None,
        "w52_high": max(window),
        "w52_low": min(window),
        "as_of": dates[-1],
        "history": {"t": hist_t, "c": hist_c},
        "stale": False,
    }


# ------------------------------------------------------------------ FRED

def fetch_fred(series_id):
    """FREDの観測値を取得する。欠測は "." で返るため取り除く。"""
    if not FRED_API_KEY:
        raise RuntimeError("FRED_API_KEY が設定されていません")
    start, end = observation_window()
    query = urllib.parse.urlencode({
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
    })
    payload = json.loads(http_get(f"https://api.stlouisfed.org/fred/series/observations?{query}"))

    dates, values = [], []
    for obs in payload.get("observations", []):
        if obs["value"] in (".", ""):
            continue
        dates.append(obs["date"])
        values.append(float(obs["value"]))
    return dates, values


# ------------------------------------------------------------------- ECB

def fetch_ecb_matrix():
    """ECBの参照相場を1リクエストでまとめて取る。基準通貨はECBに合わせてEUR。"""
    start, end = observation_window()
    symbols = ",".join(ECB_CURRENCIES)
    url = (f"https://api.frankfurter.dev/v1/{start.isoformat()}..{end.isoformat()}"
           f"?base=EUR&symbols={symbols}")
    payload = json.loads(http_get(url))
    return payload.get("rates", {})


def ecb_pair_series(matrix, pair):
    """EUR建ての表から任意の通貨ペアを組み立てる。

    ECBが配るのは EUR→X の値なので、USD/JPY のような組み合わせは
    (EUR→JPY) ÷ (EUR→USD) で求める。
    """
    base, quote = pair.split("/")
    dates, values = [], []
    for date in sorted(matrix):
        row = matrix[date]
        base_rate = 1.0 if base == "EUR" else row.get(base)
        quote_rate = 1.0 if quote == "EUR" else row.get(quote)
        if not base_rate or not quote_rate:
            continue
        dates.append(date)
        values.append(quote_rate / base_rate)
    return dates, values


# ----------------------------------------------------------- Twelve Data

def fetch_twelve_data(symbol):
    """Twelve Data の日足を取得する。無料枠は毎分8リクエストまで。"""
    if not TWELVE_DATA_KEY:
        raise RuntimeError("TWELVE_DATA_KEY が設定されていません")
    query = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": "1day",
        "outputsize": 300,
        "apikey": TWELVE_DATA_KEY,
        "order": "ASC",
    })
    payload = json.loads(http_get(f"https://api.twelvedata.com/time_series?{query}", throttle=True))

    if payload.get("status") == "error":
        raise RuntimeError(payload.get("message", "不明なエラー"))

    dates, values = [], []
    for row in payload.get("values", []):
        close = row.get("close")
        if close in (None, ""):
            continue
        dates.append(row["datetime"][:10])
        values.append(float(close))
    return dates, values


SOURCE_LABEL = {
    "fred": "FRED（セントルイス連銀）",
    "ecb": "ECB（欧州中央銀行）",
    "td": "Twelve Data",
}


def load_previous(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - 初回実行時などは前回データが無い
        return None


def build_markets():
    out_path = DATA_DIR / "markets.json"
    previous = load_previous(out_path) or {}
    prev_index = {
        item["symbol"]: item
        for group in previous.get("groups", [])
        for item in group.get("items", [])
    }

    # 為替はまとめて1回だけ取得する。失敗しても他の取得は続ける。
    ecb_matrix = {}
    if any(src == "ecb" for group in GROUPS for src, *_ in group["items"]):
        try:
            ecb_matrix = fetch_ecb_matrix()
            print(f"  ECB: {len(ecb_matrix)}営業日分", file=sys.stderr)
        except Exception as err:  # noqa: BLE001
            print(f"  ! ECB: {err}", file=sys.stderr)

    results, failures = {}, []
    for group in GROUPS:
        for source, series_id, name, subtitle, unit in group["items"]:
            if source == "td" and not TWELVE_DATA_KEY:
                continue  # キー未設定のときは黙って飛ばす（未設定は異常ではない）
            try:
                if source == "fred":
                    dates, values = fetch_fred(series_id)
                elif source == "ecb":
                    dates, values = ecb_pair_series(ecb_matrix, series_id)
                elif source == "td":
                    dates, values = fetch_twelve_data(series_id)
                else:
                    raise ValueError(f"未知の取得元: {source}")

                results[series_id] = make_quote(
                    series_id, name, subtitle, unit, SOURCE_LABEL[source], dates, values
                )
            except Exception as err:  # noqa: BLE001
                failures.append(series_id)
                print(f"  ! {series_id}: {err}", file=sys.stderr)
                stale = prev_index.get(series_id)
                if stale:
                    results[series_id] = {**stale, "stale": True}

    groups = []
    for group in GROUPS:
        items = [results[sid] for _, sid, *_ in group["items"] if sid in results]
        if items:
            groups.append({
                "id": group["id"],
                "name": group["name"],
                "note": group["note"],
                "items": items,
            })

    total = sum(len(group["items"]) for group in GROUPS)
    print(f"markets: {len(results)}/{total} 件", file=sys.stderr)
    if not results:
        raise SystemExit("市場データを1件も取得できなかったため中断します")

    sources = sorted({item["source"] for group in groups for item in group["items"]})
    payload = {
        "updated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "sources": sources,
        "failed": sorted(failures),
        "groups": groups,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return payload


# --------------------------------------------------------------------------
# ニュース
# --------------------------------------------------------------------------

TAG_RE = re.compile(r"<[^>]+>")
NS = {
    "rss": "http://purl.org/rss/1.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
}


def clean_text(value, limit=180):
    if not value:
        return ""
    text = TAG_RE.sub(" ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        return parsedate_to_datetime(value)
    except Exception:  # noqa: BLE001 - RFC822以外の形式は下でISOとして試す
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def find_text(node, *names):
    for name in names:
        found = node.find(name, NS)
        if found is not None:
            if found.text:
                return found.text
            href = found.get("href")
            if href:
                return href
    return None


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)  # noqa: S314 - 取得元は既知のRSSのみ
    entries = (
        root.findall(".//item")
        + root.findall(".//rss:item", NS)
        + root.findall(".//atom:entry", NS)
    )
    articles = []
    for entry in entries:
        title = trim_title(clean_text(find_text(entry, "title", "rss:title", "atom:title"), 200))
        link = find_text(entry, "link", "rss:link", "atom:link")
        if not title or not link:
            continue
        published = parse_date(
            find_text(entry, "pubDate", "dc:date", "atom:updated", "atom:published")
        )
        articles.append({
            "title": title,
            "url": link.strip(),
            "summary": clean_text(
                find_text(entry, "description", "rss:description", "atom:summary")
            ),
            "published": published.astimezone(timezone.utc).isoformat() if published else None,
        })
    return articles


def trim_title(title):
    """見出し末尾に付く媒体名やカテゴリ名（「… | 政治・経済 | 東洋経済」等）を落とす。

    区切りの前後で本文が短くなりすぎる場合は、見出し自体に区切り記号が
    含まれているとみなして手を付けない。
    """
    if not title:
        return title
    for sep in (" | ", " - ", " ｜ ", " – "):
        if sep not in title:
            continue
        head = title.split(sep)[0].strip()
        # 落とした結果が短すぎるなら、区切りは見出しの一部とみなして元に戻す。
        if len(head) >= max(12, len(title) * 0.4):
            title = head
    return title


def is_market_related(article):
    # 要約には媒体名や定型句が混ざるため、判定は見出しだけを対象にする。
    return any(keyword in article["title"] for keyword in MARKET_KEYWORDS)


def build_news():
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    collected = []
    for name, url, lang, focused, tier in NEWS_FEEDS:
        try:
            articles = parse_feed(http_get(url, timeout=25))
        except Exception as err:  # noqa: BLE001
            print(f"  ! feed {name}: {err}", file=sys.stderr)
            continue
        kept = 0
        for article in articles[:30]:
            published = parse_date(article["published"])
            if published and published < cutoff:
                continue
            if not focused and not is_market_related(article):
                continue
            collected.append({**article, "source": name, "lang": lang, "tier": tier})
            kept += 1
            if kept >= 20:
                break
        print(f"  - {name}: {kept}件", file=sys.stderr)

    seen = set()
    unique = []
    for article in collected:
        key = article["url"].split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)

    unique.sort(key=lambda a: a["published"] or "", reverse=True)
    unique = unique[:120]

    out_path = DATA_DIR / "news.json"
    previous = load_previous(out_path)
    if not unique and previous:
        print("news: 取得できなかったため前回分を維持します", file=sys.stderr)
        return previous

    payload = {
        "updated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "articles": unique,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"news: {len(unique)}件", file=sys.stderr)
    return payload


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    targets = sys.argv[1:] or ["markets", "news"]
    if "markets" in targets:
        build_markets()
    if "news" in targets:
        build_news()
    print("完了", file=sys.stderr)


if __name__ == "__main__":
    main()
