#!/usr/bin/env python3
"""市場データとニュースを取得して docs/data/*.json を生成する。

依存ライブラリなし（Python 3.9+ の標準ライブラリのみ）。
"""

import gzip
import http.cookiejar
import json
import os
import random
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

from symbols import GROUPS, MARKET_KEYWORDS, NEWS_FEEDS

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
JST = timezone(timedelta(hours=9))

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
CHART_HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]

# Yahoo Finance は短時間に多数のリクエストを送ると 429 を返し、しばらく解除されない。
# 1件ずつ間隔を空けて取得する。
REQUEST_INTERVAL = float(os.environ.get("REQUEST_INTERVAL", "1.5"))
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
# --------------------------------------------------------------------------

def fetch_chart(symbol, attempts=3):
    """Yahoo Finance のチャートAPIから1年分の日足とメタ情報を取得する。"""
    path = urllib.parse.quote(symbol, safe="")
    last_err = None
    for i in range(attempts):
        host = CHART_HOSTS[i % len(CHART_HOSTS)]
        url = (
            f"https://{host}/v8/finance/chart/{path}"
            "?interval=1d&range=1y&includePrePost=false"
        )
        try:
            payload = json.loads(http_get(url, throttle=True))
            result = (payload.get("chart") or {}).get("result")
            if not result:
                raise ValueError(f"empty result: {(payload.get('chart') or {}).get('error')}")
            return result[0]
        except urllib.error.HTTPError as err:
            last_err = err
            if err.code == 429:
                time.sleep(20 * (i + 1) + random.random() * 5)
            elif err.code == 404:
                break
            else:
                time.sleep(2 * (i + 1))
        except Exception as err:  # noqa: BLE001 - 失敗理由は問わず再試行する
            last_err = err
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{symbol}: {last_err}")


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


def build_quote(symbol, display_name, subtitle):
    raw = fetch_chart(symbol)
    meta = raw.get("meta") or {}
    timestamps = raw.get("timestamp") or []
    closes = (((raw.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []

    # {"t":…,"c":…} の配列よりキーの繰り返しがない並列配列のほうが転送量が小さい。
    hist_t, hist_c = [], []
    for timestamp, close in zip(timestamps, closes):
        if close is not None:
            hist_t.append(timestamp)
            hist_c.append(round_sig(close))

    price = meta.get("regularMarketPrice")
    if price is None and hist_c:
        price = hist_c[-1]

    # meta の chartPreviousClose は「取得期間の開始前の終値」なので、range=1y だと
    # 1年前の値になってしまう。前日比には使えない。日足の最後から2番目を前日終値とする。
    prev_close = meta.get("previousClose")
    if prev_close is None and len(hist_c) >= 2:
        prev_close = hist_c[-2]

    change = change_pct = None
    if price is not None and prev_close:
        change = price - prev_close
        change_pct = change / prev_close * 100

    return {
        "symbol": symbol,
        "name": display_name,
        "subtitle": subtitle,
        "currency": meta.get("currency"),
        "exchange": meta.get("fullExchangeName"),
        "market_state": raw.get("meta", {}).get("marketState"),
        "price": round_sig(price),
        "prev_close": round_sig(prev_close),
        "change": round_sig(change),
        "change_pct": round(change_pct, 2) if change_pct is not None else None,
        "day_high": round_sig(meta.get("regularMarketDayHigh")),
        "day_low": round_sig(meta.get("regularMarketDayLow")),
        "w52_high": round_sig(meta.get("fiftyTwoWeekHigh")),
        "w52_low": round_sig(meta.get("fiftyTwoWeekLow")),
        "market_time": meta.get("regularMarketTime"),
        "timezone": meta.get("exchangeTimezoneName"),
        "history": {"t": hist_t, "c": hist_c},
        "stale": False,
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

    jobs = [
        (symbol, name, subtitle)
        for group in GROUPS
        for symbol, name, subtitle in group["items"]
    ]

    results = {}
    pending = jobs
    for attempt in (1, 2):
        failed = []
        for symbol, name, subtitle in pending:
            try:
                results[symbol] = build_quote(symbol, name, subtitle)
            except Exception as err:  # noqa: BLE001
                failed.append((symbol, name, subtitle))
                print(f"  ! {symbol}: {err}", file=sys.stderr)
        pending = failed
        if not pending or attempt == 2:
            break
        print(f"  {len(pending)}件を再取得します（60秒待機）", file=sys.stderr)
        time.sleep(60)

    failures = []
    for symbol, _, _ in pending:
        failures.append(symbol)
        stale = prev_index.get(symbol)
        if stale:
            results[symbol] = {**stale, "stale": True}

    groups = []
    for group in GROUPS:
        items = [results[s] for s, _, _ in group["items"] if s in results]
        if items:
            groups.append({
                "id": group["id"],
                "name": group["name"],
                "note": group["note"],
                "items": items,
            })

    total = len(jobs)
    fetched = total - len(failures)
    print(f"markets: {fetched}/{total} 件取得", file=sys.stderr)
    if fetched == 0:
        raise SystemExit("市場データを1件も取得できなかったため中断します")

    payload = {
        "updated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "source": "Yahoo Finance",
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
    root = ET.fromstring(xml_bytes)
    entries = (
        root.findall(".//item")
        + root.findall(".//rss:item", NS)
        + root.findall(".//atom:entry", NS)
    )
    articles = []
    for entry in entries:
        title = clean_text(find_text(entry, "title", "rss:title", "atom:title"), 160)
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


def is_market_related(article):
    # 要約には媒体名や定型句が混ざるため、判定は見出しだけを対象にする。
    return any(keyword in article["title"] for keyword in MARKET_KEYWORDS)


def build_news():
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    collected = []
    for name, url, lang, focused in NEWS_FEEDS:
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
            collected.append({**article, "source": name, "lang": lang})
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
