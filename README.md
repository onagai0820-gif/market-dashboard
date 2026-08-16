# マーケットボード

世界の主要株価指数・VIX指数・為替・コモディティ・主要銘柄の株価と、マーケット関連ニュースを
1ページにまとめた静的ダッシュボードです。

- サイト本体: `docs/`（HTML / CSS / JavaScript のみ。ビルド不要）
- データ生成: `scripts/build_data.py`（Python 標準ライブラリのみ）
- 自動更新: GitHub Actions が定期実行し、`docs/data/*.json` を更新してコミットします

## ローカルでの動かし方

```bash
# データを取得（6〜8分ほどかかります）
python3 scripts/build_data.py

# 市場データだけ / ニュースだけ更新したいとき
python3 scripts/build_data.py markets
python3 scripts/build_data.py news

# ローカルサーバーで確認
python3 -m http.server 8000 --directory docs
# → http://localhost:8000
```

## 掲載内容を変える

`scripts/symbols.py` を編集します。

- `GROUPS` … 表示する指数・銘柄。`(シンボル, 表示名, 補足)` の形式で、
  シンボルは Yahoo Finance の表記に従います（例: `^GSPC`、`7203.T`、`USDJPY=X`）
- `NEWS_FEEDS` … ニュースの配信元 RSS。`(表示名, URL, 言語, 専門メディアか)`
- `MARKET_KEYWORDS` … 総合メディアの記事を市場関連に絞り込む見出しキーワード

## データ取得についての注意

Yahoo Finance は短時間に多数のリクエストを送ると `429 Too Many Requests` を返し、
しばらく解除されません。そのため 1 銘柄ずつ `REQUEST_INTERVAL` 秒（既定 1.5 秒、
CI では 2.0 秒）の間隔を空けて逐次取得しています。**この間隔は縮めないでください。**

取得に失敗した銘柄は前回の値を残したうえで、サイト上に「更新待ち」と表示します。

## 免責

掲載データは情報提供のみを目的としており、正確性・完全性・即時性を保証しません。
投資判断はご自身の責任で、一次情報を確認のうえ行ってください。
