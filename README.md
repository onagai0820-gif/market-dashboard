# マーケットボード

世界の主要株価指数・ボラティリティ指数・金利・為替・商品・暗号資産・米国主要銘柄の相場と、
マーケット関連ニュースを1ページにまとめた静的ダッシュボードです。

- サイト本体: `docs/`（HTML / CSS / JavaScript のみ。ビルド不要）
- データ生成: `scripts/build_data.py`（Python 標準ライブラリのみ。外部依存なし）
- 自動更新: GitHub Actions が定期実行し、`docs/data/*.json` を更新してコミットします

## 情報源

価格データは公的機関ないし正規ベンダーが公開しているAPIのみを使います。
非公式の内部エンドポイントは使いません。

| 分野 | 情報源 | 備考 |
| --- | --- | --- |
| 株価指数・金利・ボラティリティ・商品・暗号資産 | [FRED](https://fred.stlouisfed.org/)（米セントルイス連銀） | 要APIキー（無料） |
| 為替 | [ECB](https://www.ecb.europa.eu/) 参照相場（[Frankfurter](https://frankfurter.dev/) 経由） | キー不要 |
| 米国個別株・金 | [Twelve Data](https://twelvedata.com/) | 要APIキー（無料枠は毎分8リクエスト） |
| ニュース | Bloomberg / WSJ / FT / CNBC / MarketWatch / NHK / 東洋経済 / 日本銀行 のRSS | キー不要 |

いずれも**日次の確定値**であり、リアルタイムの取引価格ではありません。
各指標には取得元とデータ基準日を表示しています。

### 掲載していないもの

無料の範囲で正確な値が得られないため、次は掲載していません。

- TOPIX・DAX・FTSE 100・ハンセン指数・KOSPI … Twelve Data の無料枠が指数に対応しない
- 日本の個別株 … JPXのデータは有料プランでのみ提供される
- 銀（XAG/USD）… 同上

なお Twelve Data で `DAX` という銘柄コードは無料枠でも応答が返りますが、
中身はNASDAQ上場の別銘柄（約47ドル）であり、ドイツのDAX指数（約26,000pt）ではありません。
銘柄コードの一致だけを信用せず、通貨・取引所・値の桁を検証してください。

## ローカルでの動かし方

```bash
# APIキーを環境変数に入れる（.env は .gitignore 済み）
export FRED_API_KEY=...        # https://fredaccount.stlouisfed.org/apikeys
export TWELVE_DATA_KEY=...     # https://twelvedata.com/account/api-keys

# データを取得（2分ほど。Twelve Data のレート制限に合わせて間隔を空けます）
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

- `GROUPS` … 表示する指標。`(取得元, 取得元でのID, 表示名, 補足, 単位)` の形式
  - 取得元は `fred` / `ecb` / `td` のいずれか
  - 単位は `pt`（指数）、`%`（利回り・スプレッド）、通貨コードのいずれか
- `ECB_CURRENCIES` … 為替で取得する通貨。ここに足すと通貨ペアを組めます
- `NEWS_FEEDS` … ニュースの配信元。`tier` は情報源の格付け
  （`primary` = 中央銀行等の一次情報 / `wire` = 金融専門メディア / `general` = 総合媒体）
- `MARKET_KEYWORDS` … 総合媒体の記事を市場関連に絞り込むための語

新しい銘柄を足したら、**必ず実際の値を確認してください**。
銘柄コードが通っても別の銘柄が返ることがあります。

## GitHub Actions の設定

リポジトリの Settings → Secrets and variables → Actions に次を登録します。

- `FRED_API_KEY`
- `TWELVE_DATA_KEY`

## 免責

掲載する価格は提供元から自動取得した遅延データであり、正確性・完全性・即時性を保証しません。
投資判断はご自身の責任で、取引所や証券会社の一次情報を確認のうえ行ってください。
本サイトは投資勧誘を目的としたものではありません。
