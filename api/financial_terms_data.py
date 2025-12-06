# Bilingual Financial Terms Data (Chart of Accounts)
# Format: List of Dicts {"id": "", "name": "", "category": "", "definition": ""}

FINANCIAL_TERMS_DATA = [
    # Assets (1)
    {"id": "1", "name": "資產 Assets", "category": "Assets", "definition": "指商業透過交易或其他事項所獲得之經濟資源，能以貨幣衡量並預期未來能提供經濟效益者。 (Economic resources controlled by an entity...)"},
    {"id": "11-12", "name": "流動資產 Current Assets", "category": "Assets", "definition": "指現金、短期投資及其他預期能於一年內變現或耗用之資產。"},
    
    # Cash
    {"id": "111", "name": "現金及約當現金 Cash and Cash Equivalents", "category": "Assets", "definition": "包括庫存現金、銀行存款及週轉金、零用金..."},
    {"id": "1111", "name": "庫存現金 Cash on Hand", "category": "Assets", "definition": "Consists of cash on hand..."},
    {"id": "1113", "name": "銀行存款 Cash in Banks", "category": "Assets", "definition": ""},
    {"id": "1117", "name": "約當現金 Cash Equivalents", "category": "Assets", "definition": ""},
    
    # Short-term Investment
    {"id": "112", "name": "短期投資 Short-term Investments", "category": "Assets", "definition": "指短期性之投資..."},
    {"id": "1121", "name": "公平價值變動列入損益之金融資產 Financial Assets at Fair Value through Income Statement", "category": "Assets", "definition": ""},
    {"id": "1122", "name": "備供出售金融資產 Available-for-sale Financial Assets", "category": "Assets", "definition": ""},
    
    # Receivables
    {"id": "113", "name": "應收票據 Notes Receivable", "category": "Assets", "definition": "商業應收之各種票據..."},
    {"id": "114", "name": "應收帳款 Accounts Receivable", "category": "Assets", "definition": "凡因出售產品、商品或提供勞務等而發生之債權..."},
    {"id": "1141", "name": "應收帳款 Accounts Receivable", "category": "Assets", "definition": ""},
    {"id": "1149", "name": "備抵呆帳－應收帳款 Allowance for Uncollectible Accounts", "category": "Assets", "definition": ""},
    
    # Inventories
    {"id": "121-122", "name": "存貨 Inventories", "category": "Assets", "definition": "指備供正常營業出售之商品..."},
    {"id": "1211", "name": "商品存貨 Merchandise Inventory", "category": "Assets", "definition": ""},
    {"id": "1221", "name": "製成品 Finished Goods", "category": "Assets", "definition": ""},
    
    # Prepayments
    {"id": "125", "name": "預付費用 Prepaid Expenses", "category": "Assets", "definition": "預付薪資、租金、保險費..."},
    {"id": "126", "name": "預付款項 Prepayments", "category": "Assets", "definition": "預為支付之各項成本或費用..."},
    
    # Fixed Assets
    {"id": "14-15", "name": "固定資產 Property, Plant, and Equipment", "category": "Assets", "definition": "供營業上使用，非以出售為目的..."},
    {"id": "141", "name": "土地 Land", "category": "Assets", "definition": ""},
    {"id": "143", "name": "房屋及建築 Buildings", "category": "Assets", "definition": ""},
    {"id": "144", "name": "機器及設備 Machinery and Equipment", "category": "Assets", "definition": ""},
    {"id": "1448", "name": "累計折舊－機器及設備 Accumulated Depreciation - Machinery", "category": "Assets", "definition": ""},
    
    # Intangible Assets
    {"id": "17", "name": "無形資產 Intangible Assets", "category": "Assets", "definition": "無實體存在而具經濟價值之資產..."},
    {"id": "171", "name": "商標權 Trademarks", "category": "Assets", "definition": ""},
    {"id": "172", "name": "專利權 Patents", "category": "Assets", "definition": ""},
    {"id": "176", "name": "商譽 Goodwill", "category": "Assets", "definition": ""},
    
    # Liabilities (2)
    {"id": "2", "name": "負債 Liabilities", "category": "Liabilities", "definition": "由於過去之交易...所產生之經濟義務..."},
    {"id": "21-22", "name": "流動負債 Current Liabilities", "category": "Liabilities", "definition": "預期於一年內償付之債務..."},
    {"id": "211", "name": "短期借款 Short-term Debt", "category": "Liabilities", "definition": ""},
    {"id": "213", "name": "應付票據 Notes Payable", "category": "Liabilities", "definition": ""},
    {"id": "214", "name": "應付帳款 Accounts Payable", "category": "Liabilities", "definition": ""},
    {"id": "216", "name": "應付所得稅 Income Tax Payable", "category": "Liabilities", "definition": ""},
    {"id": "217", "name": "應付費用 Accrued Expenses", "category": "Liabilities", "definition": "已發生而尚未支付之各項費用..."},
    {"id": "226", "name": "預收款項 Unearned Revenue", "category": "Liabilities", "definition": ""},
    
    # Long-term Liabilities
    {"id": "23", "name": "長期負債 Long-term Liabilities", "category": "Liabilities", "definition": "到期日在一年以上之債務..."},
    {"id": "231", "name": "應付公司債 Bonds Payable", "category": "Liabilities", "definition": ""},
    {"id": "232", "name": "長期借款 Long-term Debt", "category": "Liabilities", "definition": ""},
    
    # Equity (3)
    {"id": "3", "name": "業主權益 Owners' Equity", "category": "Equity", "definition": "資產減除負債後之餘額..."},
    {"id": "31", "name": "資本(股本) Capital", "category": "Equity", "definition": ""},
    {"id": "3111", "name": "普通股股本 Common Stock", "category": "Equity", "definition": ""},
    {"id": "32", "name": "資本公積 Capital Surplus", "category": "Equity", "definition": "非由營業結果所產生之權益..."},
    {"id": "33", "name": "保留盈餘 Retained Earnings", "category": "Equity", "definition": "由營業結果所產生之權益..."},
    
    # Revenue (4)
    {"id": "4", "name": "營業收入 Operating Revenue", "category": "Revenue", "definition": "本期內經常營業活動獲得之收入..."},
    {"id": "41", "name": "銷貨收入 Sales Revenue", "category": "Revenue", "definition": ""},
    {"id": "417", "name": "銷貨退回 Sales Return", "category": "Revenue", "definition": ""},
    {"id": "419", "name": "銷貨折讓 Sales Allowances", "category": "Revenue", "definition": ""},
    
    # Costs (5)
    {"id": "5", "name": "營業成本 Operating Costs", "category": "Expenses", "definition": "本期內因銷售商品...應負擔之成本..."},
    {"id": "51", "name": "銷貨成本 Cost of Goods Sold", "category": "Expenses", "definition": ""},
    
    # Expenses (6)
    {"id": "6", "name": "營業費用 Operating Expenses", "category": "Expenses", "definition": "本期內銷售商品...所應負擔之費用..."},
    {"id": "61", "name": "推銷費用 Selling Expenses", "category": "Expenses", "definition": ""},
    {"id": "62", "name": "管理費用 Administrative Expenses", "category": "Expenses", "definition": ""},
    {"id": "63", "name": "研發費用 R&D Expenses", "category": "Expenses", "definition": ""},
    
    # Other Income/Expenses (7)
    {"id": "71", "name": "利息收入 Interest Income", "category": "Revenue", "definition": ""},
    {"id": "75", "name": "利息費用 Interest Expense", "category": "Expenses", "definition": ""},
    
    # Income Tax (8)
    {"id": "8", "name": "所得稅費用 Income Tax Expense", "category": "Expenses", "definition": ""},

    # --- General Glossary (A-Z) ---
    {"id": "glossary_averaging_down", "name": "攤平/補倉 Averaging Down", "category": "Glossary", "definition": "Buying more of a security at a lower price to lower the average cost."},
    {"id": "glossary_adp", "name": "ADP就業人口 ADP National Employment Report", "category": "Macroeconomics", "definition": ""},
    {"id": "glossary_aud", "name": "澳元 AUD", "category": "Forex", "definition": "Australian Dollar"},
    {"id": "glossary_ask", "name": "買價 Ask", "category": "Trading", "definition": "The price a seller is willing to accept for a security."},
    {"id": "glossary_alt_inv", "name": "另類投資 Alternative Investment", "category": "Investment", "definition": ""},
    {"id": "glossary_adr_ratio", "name": "漲跌比率 ADR (Advance-Decline Ratio)", "category": "Technical Analysis", "definition": ""},
    {"id": "glossary_bid", "name": "賣價 Bid", "category": "Trading", "definition": "The price a buyer is willing to pay for a security."},
    {"id": "glossary_bottom_fishing", "name": "抄底 Bottom Fishing", "category": "Trading", "definition": "Investing in assets that have declined in price."},
    {"id": "glossary_bar_chart", "name": "柱狀圖 Bar Chart", "category": "Technical Analysis", "definition": ""},
    {"id": "glossary_bretton_woods", "name": "布雷頓森林體系 Bretton Woods System", "category": "Economics", "definition": ""},
    {"id": "glossary_black_swan", "name": "黑天鵝事件 Black Swan Event", "category": "Risk Management", "definition": "Unpredictable event with severe consequences."},
    {"id": "glossary_boj", "name": "日本央行會議 BOJ Meeting", "category": "Central Banks", "definition": "Bank of Japan"},
    {"id": "glossary_business_cycle", "name": "景氣循環 Business Cycle", "category": "Economics", "definition": ""},
    {"id": "glossary_bdi", "name": "波羅的海乾散貨指數 Baltic Dry Index", "category": "Indices", "definition": ""},
    {"id": "glossary_boe", "name": "英格蘭銀行 BOE", "category": "Central Banks", "definition": "Bank of England"},
    {"id": "glossary_cpi", "name": "消費者物價指數 CPI", "category": "Macroeconomics", "definition": "Consumer Price Index"},
    {"id": "glossary_cfd", "name": "差價合約 CFD", "category": "Derivatives", "definition": "Contract for Difference"},
    {"id": "glossary_cta", "name": "商品投資顧問 Commodity Trading Advisor (CTA)", "category": "Investment", "definition": ""},
    {"id": "glossary_cftc", "name": "美國商品期貨交易委員會 CFTC", "category": "Regulation", "definition": ""},
    {"id": "glossary_chf", "name": "瑞士法郎 CHF", "category": "Forex", "definition": "Swiss Franc"},
    {"id": "glossary_currency_basket", "name": "一籃子貨幣 Currency Basket", "category": "Forex", "definition": ""},
    {"id": "glossary_cad", "name": "加元 CAD", "category": "Forex", "definition": "Canadian Dollar"},
    {"id": "glossary_cnh", "name": "離岸人民幣 CNH", "category": "Forex", "definition": "Offshore Chinese Yuan"},
    {"id": "glossary_czk", "name": "捷克克朗 CZK", "category": "Forex", "definition": "Czech Koruna"},
    {"id": "glossary_cme", "name": "芝商所 CME Group", "category": "Exchanges", "definition": ""},
    {"id": "glossary_compound_interest", "name": "複利 Compound Interest", "category": "Finance", "definition": ""},
    {"id": "glossary_chip_analysis", "name": "籌碼面分析 Chip Analysis", "category": "Analysis", "definition": ""},
    {"id": "glossary_market_cap_index", "name": "市值加權指數 Capitalization-weighted Index", "category": "Indices", "definition": ""},
    {"id": "glossary_commodities", "name": "大宗商品 Commodities", "category": "Commodities", "definition": ""},
    {"id": "glossary_circuit_breaker", "name": "熔斷機制 Circuit Breaker", "category": "Regulation", "definition": ""},
    {"id": "glossary_credit_rating", "name": "信用評級機構 Credit Rating Agencies", "category": "Agencies", "definition": ""},
    {"id": "glossary_deflation", "name": "通貨緊縮 Deflation", "category": "Macroeconomics", "definition": ""},
    {"id": "glossary_dovish", "name": "鴿派 Dovish", "category": "Central Banks", "definition": "Favoring low interest rates."},
    {"id": "glossary_dow_theory", "name": "道氏理論 Dow Theory", "category": "Technical Analysis", "definition": ""},
    {"id": "glossary_divergence", "name": "背離 Divergence", "category": "Technical Analysis", "definition": ""},
    {"id": "glossary_day_trading", "name": "當日沖銷 Day Trading", "category": "Trading", "definition": ""},
    {"id": "glossary_dca", "name": "美元成本平均法 DCA", "category": "Investment", "definition": "Dollar Cost Averaging"},
    {"id": "glossary_dividend_payout", "name": "配息率 Dividend Payout Ratio", "category": "Fundamental Analysis", "definition": ""},
    {"id": "glossary_entry", "name": "開倉/進場 Entry", "category": "Trading", "definition": ""},
    {"id": "glossary_exit", "name": "平倉/出場 Exit", "category": "Trading", "definition": ""},
    {"id": "glossary_eps", "name": "每股盈餘 EPS", "category": "Fundamental Analysis", "definition": "Earnings Per Share"},
    {"id": "glossary_eur", "name": "歐元 EUR", "category": "Forex", "definition": "Euro"},
    {"id": "glossary_emerging_markets", "name": "新興市場 Emerging Markets", "category": "Markets", "definition": ""},
    {"id": "glossary_ex_dividend", "name": "除息日 Ex-Dividend Date", "category": "Corporate Actions", "definition": ""},
    {"id": "glossary_fed", "name": "聯準會 Fed", "category": "Central Banks", "definition": "Federal Reserve"},
    {"id": "glossary_financing_cost", "name": "隔夜利息 Financing Cost", "category": "Trading", "definition": ""},
    {"id": "glossary_forex_reserves", "name": "外匯儲備 Foreign Exchange Reserves", "category": "Macroeconomics", "definition": ""},
    {"id": "glossary_futures", "name": "期貨交易 Futures Trading", "category": "Derivatives", "definition": ""},
    {"id": "glossary_financing", "name": "融資 Financing", "category": "Finance", "definition": ""},
    {"id": "glossary_geopolitical_risk", "name": "地緣政治風險 Geopolitical Risk", "category": "Risk Management", "definition": ""},
    {"id": "glossary_gdp", "name": "國內生產總值 GDP", "category": "Macroeconomics", "definition": "Gross Domestic Product"},
    {"id": "glossary_gbp", "name": "英鎊 GBP", "category": "Forex", "definition": "British Pound"},
    {"id": "glossary_gnp", "name": "國民生產毛額 GNP", "category": "Macroeconomics", "definition": "Gross National Product"},
    {"id": "glossary_gotobi", "name": "五十日 GOTOBI", "category": "Trading", "definition": "Japanese market term for 5th, 10th, etc. days."},
    {"id": "glossary_g20", "name": "二十國集團 G20", "category": "Organizations", "definition": ""},
    {"id": "glossary_g7", "name": "七大工業國 G7", "category": "Organizations", "definition": ""},
    {"id": "glossary_hawks", "name": "鷹派 Hawks", "category": "Central Banks", "definition": "Favoring high interest rates to fight inflation."},
    {"id": "glossary_interbank", "name": "銀行間市場 Interbank Market", "category": "Finance", "definition": ""},
    {"id": "glossary_inflation", "name": "通貨膨脹 Inflation", "category": "Macroeconomics", "definition": ""},
    {"id": "glossary_insider_trading", "name": "內線交易 Insider Trading", "category": "Regulation", "definition": ""},
    {"id": "glossary_ism", "name": "ISM製造業景氣指數 ISM Manufacturing Index", "category": "Macroeconomics", "definition": ""},
    {"id": "glossary_irr", "name": "內部報酬率 IRR", "category": "Finance", "definition": "Internal Rate of Return"},
    {"id": "glossary_ipo", "name": "首次公開募股 IPO", "category": "Corporate Actions", "definition": "Initial Public Offering"},
    {"id": "glossary_imf", "name": "國際貨幣基金組織 IMF", "category": "Organizations", "definition": ""},
    {"id": "glossary_jpy", "name": "日圓 JPY", "category": "Forex", "definition": "Japanese Yen"},
    {"id": "glossary_london_fixing", "name": "倫敦定盤價 London Fixing", "category": "Forex", "definition": ""},
    {"id": "glossary_lehman", "name": "雷曼兄弟事件 Lehman Brothers Incident", "category": "History", "definition": ""},
    {"id": "glossary_limit_up", "name": "漲停 Limit Up", "category": "Trading", "definition": ""},
    {"id": "glossary_limit_down", "name": "跌停 Limit Down", "category": "Trading", "definition": ""},
    {"id": "glossary_liquidation", "name": "爆倉 Liquidation", "category": "Trading", "definition": "Forced closing of positions due to insufficient margin."},
    {"id": "glossary_mxn", "name": "墨西哥披索 MXN", "category": "Forex", "definition": "Mexican Peso"},
    {"id": "glossary_monetary_policy", "name": "貨幣政策 Monetary Policy", "category": "Central Banks", "definition": ""},
    {"id": "glossary_matthew_effect", "name": "馬太效應 Matthew Effect", "category": "Economics", "definition": "The rich get richer."},
    {"id": "glossary_market_cap", "name": "市值 Market Capitalization", "category": "Fundamental Analysis", "definition": ""},
    {"id": "glossary_murphy_law", "name": "墨菲定律 Murphy’s Law", "category": "General", "definition": ""},
    {"id": "glossary_max_drawdown", "name": "最大回撤 Maximum Drawdown", "category": "Risk Management", "definition": ""},
    {"id": "glossary_nfp", "name": "美國非農就業人數 NFP", "category": "Macroeconomics", "definition": "Non-Farm Payrolls"},
    {"id": "glossary_nzd", "name": "紐元 NZD", "category": "Forex", "definition": "New Zealand Dollar"},
    {"id": "glossary_nok", "name": "挪威克朗 NOK", "category": "Forex", "definition": "Norwegian Krone"},
    {"id": "glossary_nasdaq", "name": "納斯達克 Nasdaq", "category": "Indices", "definition": ""},
    {"id": "glossary_neckline", "name": "頸線 Neckline", "category": "Technical Analysis", "definition": ""},
    {"id": "glossary_otc", "name": "場外交易 OTC", "category": "Trading", "definition": "Over-The-Counter"},
    {"id": "glossary_omo", "name": "公開市場操作 Open Market Operations", "category": "Central Banks", "definition": ""},
    {"id": "glossary_oscillators", "name": "震盪類指標 Oscillators", "category": "Technical Analysis", "definition": ""},
    {"id": "glossary_oecd", "name": "經濟合作暨發展組織 OECD", "category": "Organizations", "definition": ""},
    {"id": "glossary_plaza_accord", "name": "廣場協議 Plaza Accord", "category": "History", "definition": ""},
    {"id": "glossary_per", "name": "本益比 PER", "category": "Fundamental Analysis", "definition": "Price-to-Earnings Ratio"},
    {"id": "glossary_pln", "name": "波蘭茲羅提 PLN", "category": "Forex", "definition": "Polish Zloty"},
    {"id": "glossary_ponzi", "name": "龐氏騙局 Ponzi Scheme", "category": "Risk Management", "definition": ""},
    {"id": "glossary_policy_rate", "name": "政策利率 Policy Interest Rate", "category": "Central Banks", "definition": ""},
    {"id": "glossary_pullback", "name": "回調/回檔 Pullback", "category": "Technical Analysis", "definition": ""},
    {"id": "glossary_position", "name": "倉位/頭寸 Position", "category": "Trading", "definition": ""},
    {"id": "glossary_pbr", "name": "股價淨值比 PBR", "category": "Fundamental Analysis", "definition": "Price-to-Book Ratio"},
    {"id": "glossary_qe", "name": "量化寬鬆 QE", "category": "Central Banks", "definition": "Quantitative Easing"},
    {"id": "glossary_qt", "name": "量化緊縮 QT", "category": "Central Banks", "definition": "Quantitative Tightening"},
    {"id": "glossary_roe", "name": "股東權益報酬率 ROE", "category": "Fundamental Analysis", "definition": "Return on Equity"},
    {"id": "glossary_rule_72", "name": "72法則 Rule of 72", "category": "Finance", "definition": ""},
    {"id": "glossary_rebalance", "name": "再平衡 Rebalance", "category": "Portfolio Management", "definition": ""},
    {"id": "glossary_rba", "name": "澳洲儲備銀行 RBA", "category": "Central Banks", "definition": "Reserve Bank of Australia"},
    {"id": "glossary_rbnz", "name": "紐西蘭儲備銀行 RBNZ", "category": "Central Banks", "definition": "Reserve Bank of New Zealand"},
    {"id": "glossary_sgd", "name": "新加坡元 SGD", "category": "Forex", "definition": "Singapore Dollar"},
    {"id": "glossary_slippage", "name": "滑點 Slippage", "category": "Trading", "definition": ""},
    {"id": "glossary_stop_loss", "name": "停損/止損 Stop Loss", "category": "Trading", "definition": ""},
    {"id": "glossary_sharpe", "name": "夏普比率 Sharpe Ratio", "category": "Risk Management", "definition": ""},
    {"id": "glossary_sortino", "name": "索提諾比率 Sortino Ratio", "category": "Risk Management", "definition": ""},
    {"id": "glossary_thb", "name": "泰銖 THB", "category": "Forex", "definition": "Thai Baht"},
    {"id": "glossary_try", "name": "土耳其里拉 TRY", "category": "Forex", "definition": "Turkish Lira"},
    {"id": "glossary_tenbagger", "name": "十倍股 Tenbagger", "category": "Investment", "definition": ""},
    {"id": "glossary_usd", "name": "美元 USD", "category": "Forex", "definition": "United States Dollar"},
    {"id": "glossary_volatility", "name": "波動率 Volatility", "category": "Risk Management", "definition": ""},
    {"id": "glossary_washout", "name": "洗盤 Washout", "category": "Trading", "definition": ""},
    {"id": "glossary_zar", "name": "南非蘭特 ZAR", "category": "Forex", "definition": "South African Rand"},
    {"id": "glossary_zero_sum", "name": "零和遊戲 Zero-sum Game", "category": "Game Theory", "definition": ""},

    # --- Categorized Definitions (Batch 3) ---
    # 1. General Market
    {"id": "gen_capital_market", "name": "資本市場 Capital Market", "category": "General Market", "definition": "是指證券融資和經營一年以上中長期資金借貸的金融市場。"},
    {"id": "gen_stock", "name": "股票 Stock", "category": "General Market", "definition": "股份有限公司在籌集資本時向出資人發行的股份憑證..."},
    {"id": "gen_bond", "name": "債券 Bond", "category": "General Market", "definition": "政府、金融機構、工商企業等機構直接向社會借債籌措資金時，向投資者發行的憑證..."},
    {"id": "gen_convertible", "name": "可轉換證券 Convertible Securities", "category": "General Market", "definition": "持有人有權將其轉換成為另一種不同性質的證券..."},
    {"id": "gen_warrant", "name": "權證 Warrant", "category": "Derivatives", "definition": "指標的證券發行人或其以外的第三人發行的，約定持有人在規定期間內有權按約定價格購買或出售標的證券..."},
    {"id": "gen_fund", "name": "證券投資基金 Fund", "category": "Funds", "definition": "一種利益共享、風險共擔的集合證券投資方式..."},
    {"id": "gen_ipo", "name": "首次公開募股 IPO", "category": "Primary Market", "definition": "Initial Public Offering，指某公司首次向社會公眾公開招股。"},
    {"id": "gen_blue_chip", "name": "藍籌股 Blue Chip", "category": "Stocks", "definition": "資本雄厚、股本和市值較大、信譽優良的上市公司發行的股票。"},
    {"id": "gen_st_stock", "name": "ST股票 Special Treatment", "category": "Stocks", "definition": "因經營虧損或其他異常情況，證監會提醒股民注意特別處理的股票。"},
    
    # 2. Technical Analysis
    {"id": "tech_k_line", "name": "K線 K-Line/Candlestick", "category": "Technical Analysis", "definition": "又稱為日本線，由影線和實體組成，記錄股票一天的價格變動。"},
    {"id": "tech_trend", "name": "趨勢 Trend", "category": "Technical Analysis", "definition": "股票價格市場運動的方向 (上升、下降、水平)。"},
    {"id": "tech_support", "name": "支撐線 Support Line", "category": "Technical Analysis", "definition": "股價跌到某個價位附近停止下跌甚至回升的價位。"},
    {"id": "tech_resistance", "name": "壓力線 Resistance Line", "category": "Technical Analysis", "definition": "股價上漲到某個價位附近停止上漲甚至回落的價位。"},
    {"id": "tech_gap", "name": "跳空缺口 Gap", "category": "Technical Analysis", "definition": "相鄰兩根K線間沒有發生交易的空白區域。"},
    {"id": "tech_divergence", "name": "背離 Divergence", "category": "Technical Analysis", "definition": "股價創新低/高，但指標未跟隨創新低/高。"},
    
    # 3. Trading Terms
    {"id": "trade_bull", "name": "多頭 Bull", "category": "Trading", "definition": "預期未來價格上漲，先買後賣。"},
    {"id": "trade_bear", "name": "空頭 Bear", "category": "Trading", "definition": "預期未來行情下跌，先賣後買。"},
    {"id": "trade_limit_up", "name": "漲停板 Limit Up", "category": "Trading", "definition": "交易當天股價的最高限度。"},
    {"id": "trade_limit_down", "name": "跌停板 Limit Down", "category": "Trading", "definition": "交易當天股價的最低限度。"},
    {"id": "trade_turnover", "name": "換手率 Turnover Rate", "category": "Trading", "definition": "一定時間內市場中股票轉手買賣的頻率。"},
    {"id": "trade_volume_ratio", "name": "量比 Volume Ratio", "category": "Trading", "definition": "當日總成交手數與近期平均成交手數的比值。"},
    
    # 4. Financial Analysis
    {"id": "fin_pe", "name": "市盈率 P/E Ratio", "category": "Fundamental Analysis", "definition": "股票市價與其每股收益的比值。"},
    {"id": "fin_pb", "name": "市淨率 P/B Ratio", "category": "Fundamental Analysis", "definition": "股票市價與每股淨資產的比值。"},
    
    # 5. Macroeconomics
    {"id": "macro_monetary_policy", "name": "貨幣政策 Monetary Policy", "category": "Macroeconomics", "definition": "央行調節貨幣供給和利率以影響宏觀經濟的方針。"},
    {"id": "macro_fiscal_policy", "name": "財政政策 Fiscal Policy", "category": "Macroeconomics", "definition": "國家通過財政支出與稅收政策來調節總需求。"},
    {"id": "macro_inflation", "name": "通貨膨脹 Inflation", "category": "Macroeconomics", "definition": "流通中貨幣量超過實際需要量引起的貨幣貶值、物價上漲。"},
    {"id": "macro_cpi", "name": "消費者物價指數 CPI", "category": "Macroeconomics", "definition": "反映與居民生活有關的商品及勞務價格變動指標。"},
    {"id": "macro_ppi", "name": "生產者物價指數 PPI", "category": "Macroeconomics", "definition": "衡量工業企業產品出廠價格變動趨勢和程度的指數。"},
    
    # 6. Funds
    {"id": "fund_etf", "name": "交易所交易基金 ETF", "category": "Funds", "definition": "可以在交易所上市交易的基金，代表一攬子股票組合。"},
    {"id": "fund_nav", "name": "基金單位淨值 NAV", "category": "Funds", "definition": "基金總資產價值扣除費用後除以單位總數。"}
]