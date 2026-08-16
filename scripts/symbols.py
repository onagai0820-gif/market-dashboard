"""掲載する指標の定義。ここを編集すればサイトの掲載内容が変わる。

各項目は取得元を明示する。
  fred : セントルイス連銀 FRED（公式統計。株価指数・金利・ボラティリティ・商品・暗号資産）
  ecb  : 欧州中央銀行の参照相場（為替。日次で更新される）
  td   : Twelve Data（個別株・海外指数・貴金属。FREDに日次系列がないもののみ）

FREDの為替系列（DEXJPUS 等）は週次更新で9日ほど遅れるため為替には使わない。
"""

# (取得元, 取得元でのID, 表示名, 補足, 単位)
# 単位は表示の整形に使う。"pt"=指数、"%"=率、それ以外は通貨コード。
GROUPS = [
    {
        "id": "indices",
        "name": "主要株価指数",
        "note": "各国の代表的な株価指数（終値ベース）",
        "items": [
            ("fred", "SP500", "S&P 500", "米国", "pt"),
            ("fred", "NASDAQCOM", "NASDAQ総合", "米国", "pt"),
            ("fred", "NASDAQ100", "NASDAQ 100", "米国", "pt"),
            ("fred", "DJIA", "NYダウ", "米国", "pt"),
            ("fred", "NIKKEI225", "日経平均株価", "日本", "pt"),
        ],
    },
    {
        "id": "volatility",
        "name": "ボラティリティ指数",
        "note": "市場が織り込む先行き変動率。相場の警戒度を示す",
        "items": [
            ("fred", "VIXCLS", "VIX指数", "S&P500の変動率", "pt"),
            ("fred", "VXNCLS", "VXN指数", "NASDAQ100の変動率", "pt"),
            ("fred", "VXDCLS", "VXD指数", "NYダウの変動率", "pt"),
            ("fred", "OVXCLS", "OVX指数", "原油の変動率", "pt"),
            ("fred", "GVZCLS", "GVZ指数", "金の変動率", "pt"),
        ],
    },
    {
        "id": "rates",
        "name": "金利・信用",
        "note": "米国の金利水準と信用スプレッド",
        "items": [
            ("fred", "DGS2", "米2年債利回り", "政策金利の織り込み", "%"),
            ("fred", "DGS10", "米10年債利回り", "長期金利の代表", "%"),
            ("fred", "DGS30", "米30年債利回り", "超長期", "%"),
            ("fred", "DTB3", "米3ヶ月TB", "短期金利", "%"),
            ("fred", "T10Y2Y", "10年-2年スプレッド", "マイナスは景気後退の予兆", "%"),
            ("fred", "T10YIE", "期待インフレ率", "10年・BEI", "%"),
            ("fred", "BAMLH0A0HYM2", "ハイイールド社債スプレッド", "信用不安の目安", "%"),
            ("fred", "DFF", "FF金利", "米政策金利（実効）", "%"),
            ("fred", "MORTGAGE30US", "米住宅ローン30年", "週次", "%"),
        ],
    },
    {
        "id": "fx",
        "name": "為替",
        "note": "欧州中央銀行が公表する参照相場",
        "items": [
            ("ecb", "USD/JPY", "ドル円", "USD/JPY", "JPY"),
            ("ecb", "EUR/JPY", "ユーロ円", "EUR/JPY", "JPY"),
            ("ecb", "GBP/JPY", "ポンド円", "GBP/JPY", "JPY"),
            ("ecb", "AUD/JPY", "豪ドル円", "AUD/JPY", "JPY"),
            ("ecb", "CNY/JPY", "人民元円", "CNY/JPY", "JPY"),
            ("ecb", "EUR/USD", "ユーロドル", "EUR/USD", "USD"),
            ("ecb", "GBP/USD", "ポンドドル", "GBP/USD", "USD"),
        ],
    },
    {
        "id": "commodities",
        "name": "商品",
        "note": "エネルギーと貴金属",
        "items": [
            ("fred", "DCOILWTICO", "WTI原油", "米国産原油・バレル", "USD"),
            ("fred", "DCOILBRENTEU", "ブレント原油", "北海産原油・バレル", "USD"),
            ("fred", "DHHNGSP", "天然ガス", "ヘンリーハブ", "USD"),
            ("td", "XAU/USD", "金", "トロイオンス", "USD"),
        ],
    },
    {
        "id": "crypto",
        "name": "暗号資産",
        "note": "Coinbase の終値（FRED経由）",
        "items": [
            ("fred", "CBBTCUSD", "ビットコイン", "BTC/USD", "USD"),
            ("fred", "CBETHUSD", "イーサリアム", "ETH/USD", "USD"),
        ],
    },
    {
        "id": "us_stocks",
        "name": "米国の主要銘柄",
        "note": "時価総額上位を中心に",
        "items": [
            ("td", "AAPL", "アップル", "AAPL", "USD"),
            ("td", "MSFT", "マイクロソフト", "MSFT", "USD"),
            ("td", "NVDA", "エヌビディア", "NVDA", "USD"),
            ("td", "GOOGL", "アルファベット", "GOOGL", "USD"),
            ("td", "AMZN", "アマゾン", "AMZN", "USD"),
            ("td", "META", "メタ", "META", "USD"),
            ("td", "TSLA", "テスラ", "TSLA", "USD"),
            ("td", "AVGO", "ブロードコム", "AVGO", "USD"),
            ("td", "JPM", "JPモルガン", "JPM", "USD"),
            ("td", "LLY", "イーライリリー", "LLY", "USD"),
        ],
    },
]

# 掲載を見送ったもの（無料で正確な値が得られないため）
#   TOPIX・DAX・FTSE100・ハンセン・KOSPI … Twelve Data の無料枠が指数に対応しない。
#     なお "DAX" は取得できてしまうが、中身はNASDAQ上場の別銘柄（約47ドル）で
#     ドイツのDAX指数（約26,000pt）ではない。銘柄コードの一致だけを信用しないこと。
#   日本の個別株 … JPXのデータは有料プランでのみ提供される。
#   銀(XAG/USD) … 同上。
# 米国上場の国別ETF（EWG/EWU/EWH/EWY）は取得できるが、米ドル建てのETFであり
# 現地指数とは値動きがずれるため、指数の代用としては載せない。

# 為替は ECB が基準にしている EUR 建てを1回だけ取得し、そこから各ペアを組み立てる。
ECB_CURRENCIES = ["USD", "JPY", "GBP", "AUD", "CNY"]

# (表示名, URL, 言語, focused, tier)
# focused=True は市場専門の配信元。False は総合媒体なので MARKET_KEYWORDS で絞り込む。
# tier は情報源の格付けで、並べ替えの優先度と画面上のラベルに使う。
#   "primary"  … 中央銀行など一次情報の発信元
#   "wire"     … 金融専門の報道機関
#   "general"  … 総合メディアの経済面
#
# 検証時点でロイター(401)・日経(404)・時事通信(404)はRSS提供を終了しており取得できない。
# 個人の相場観を載せる媒体（みんかぶ・MONEY PLUS等）は誤情報の温床になるため採用しない。
NEWS_FEEDS = [
    # 一次情報
    ("日本銀行", "https://www.boj.or.jp/rss/whatsnew.xml", "ja", False, "primary"),
    # 金融専門メディア
    ("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss", "en", True, "wire"),
    ("WSJ Markets", "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain", "en", True, "wire"),
    ("Financial Times", "https://www.ft.com/markets?format=rss", "en", True, "wire"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "en", True, "wire"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "en", True, "wire"),
    # 総合メディアの経済面
    ("NHK 経済", "https://www.nhk.or.jp/rss/news/cat5.xml", "ja", False, "general"),
    ("東洋経済オンライン", "https://toyokeizai.net/list/feed/rss", "ja", False, "general"),
    ("Yahoo!ニュース 経済", "https://news.yahoo.co.jp/rss/topics/business.xml", "ja", False, "general"),
    ("Yahoo!ニュース 市況", "https://news.yahoo.co.jp/rss/categories/business.xml", "ja", False, "general"),
]

# 総合メディアの記事を市場関連に絞り込むためのキーワード（見出しに対して判定する）。
# 「経済」のような広すぎる語は、媒体名や定型句に当たってしまうため入れていない。
MARKET_KEYWORDS = [
    "株価", "株式", "個別株", "相場", "市場", "日経平均", "TOPIX", "ダウ", "ナスダック",
    "円安", "円高", "為替", "ドル", "ユーロ", "金利", "利上げ", "利下げ", "日銀", "FRB",
    "インフレ", "物価", "景気", "GDP", "決算", "上場", "投資", "債券", "国債", "原油",
    "金価格", "資産運用", "ファンド", "ETF", "証券", "取引所", "配当", "業績", "増益",
    "減益", "最高値", "急落", "急騰", "反発", "続伸", "続落", "S&P", "先物",
]
