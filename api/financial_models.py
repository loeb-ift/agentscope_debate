from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime, DECIMAL, BigInteger, Time, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from api.database import Base

class Company(Base):
    """
    公司實體 (Company Entity)。
    
    **使用時機 (When to use):**
    - 當需要儲存或查詢公司的基本資料 (如統編、成立日期、產業分類) 時。
    - 當需要建立公司與其他實體 (如子公司、發行證券) 的關聯時。
    - 用於 `internal.search_company` 或 `internal.get_company_details` 工具的後端資料源。
    
    **使用方式 (How to use):**
    - `company_id` 是唯一識別碼，通常使用股票代碼 (Ticker) 或 TEJ ID。
    - 透過 `industry_sector` 與 `industry_group` 進行產業鏈分析。
    - 關聯 `Security` 表以查詢該公司發行的股票或債券。
    """
    __tablename__ = 'companies'

    company_id = Column(String(50), primary_key=True)
    company_name = Column(String(200), nullable=False)
    company_name_en = Column(String(200))
    company_name_local = Column(String(200))
    short_name = Column(String(100))
    former_names = Column(JSON)  # JSON list

    # Legal
    legal_entity_identifier = Column(String(20), unique=True)
    tax_id = Column(String(50))
    registration_number = Column(String(50))
    incorporation_date = Column(Date)
    legal_form = Column(String(50))

    # Classification
    industry_sector = Column(String(100))
    industry_group = Column(String(100))
    sub_industry = Column(String(100))
    gics_code = Column(String(20))
    sic_code = Column(String(20))

    # Scale
    market_cap = Column(DECIMAL(20, 2))
    market_cap_currency = Column(String(3))
    employee_count = Column(Integer)
    revenue_annual = Column(DECIMAL(20, 2))
    revenue_currency = Column(String(3))
    fiscal_year_end = Column(String(5))

    # Listing
    is_public = Column(Boolean, default=False)
    listing_status = Column(String(20))
    primary_exchange = Column(String(50))
    secondary_exchanges = Column(JSON)
    ipo_date = Column(Date)
    delisting_date = Column(Date)

    # Ticker
    ticker_symbol = Column(String(20))
    isin = Column(String(12))
    cusip = Column(String(9))
    sedol = Column(String(7))
    bloomberg_ticker = Column(String(50))
    reuters_ric = Column(String(50))

    # Geo
    country_of_incorporation = Column(String(2))
    country_of_domicile = Column(String(2))
    headquarters_country = Column(String(2))
    headquarters_city = Column(String(100))
    headquarters_address = Column(Text)
    registered_address = Column(Text)

    # Contact
    website_url = Column(String(255))
    investor_relations_url = Column(String(255))
    phone = Column(String(50))
    email = Column(String(100))

    # Relationships
    parent_company_id = Column(String(50), ForeignKey('companies.company_id'))
    ultimate_parent_id = Column(String(50))
    subsidiary_of = Column(JSON)

    # Ratings & Risk
    sp_rating = Column(String(10))
    moody_rating = Column(String(10))
    fitch_rating = Column(String(10))
    rating_outlook = Column(String(20))
    rating_date = Column(Date)
    
    bankruptcy_risk_score = Column(DECIMAL(5, 2))
    esg_score = Column(DECIMAL(5, 2))
    controversy_score = Column(DECIMAL(5, 2))

    # System
    status = Column(String(20), default='active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Security(Base):
    """
    證券實體 (Security Entity)。
    
    **使用時機 (When to use):**
    - 當需要區分同一家公司發行的不同金融商品 (如普通股、特別股、公司債) 時。
    - 儲存具體的交易代碼 (Ticker)、ISIN 碼與交易所資訊。
    - 用於 `internal.get_security_details` 工具，提供精確的證券規格。
    
    **使用方式 (How to use):**
    - 透過 `issuer_company_id` 連結回發行公司 (`Company`)。
    - `security_type` 區分商品類型 (Stock, Bond, ETF)。
    - `primary_exchange` 指定主要交易場所。
    """
    __tablename__ = 'securities'

    security_id = Column(String(50), primary_key=True)
    security_name = Column(String(200), nullable=False)
    security_type = Column(String(50), nullable=False) # Stock, Bond, etc.
    
    issuer_company_id = Column(String(50), ForeignKey('companies.company_id'))
    issuer_name = Column(String(200))
    
    ticker = Column(String(20))
    isin = Column(String(12), unique=True)
    cusip = Column(String(9))
    
    asset_class = Column(String(50))
    sub_asset_class = Column(String(50))
    security_subtype = Column(String(50))
    
    primary_exchange = Column(String(50))
    trading_currency = Column(String(3))
    listing_date = Column(Date)
    maturity_date = Column(Date)
    
    # Stock specific
    share_class = Column(String(10))
    shares_outstanding = Column(BigInteger)
    float_shares = Column(BigInteger)
    
    # Market Data
    last_price = Column(DECIMAL(20, 4))
    last_price_date = Column(Date)
    daily_volume = Column(BigInteger)
    market_cap = Column(DECIMAL(20, 2))
    
    # System
    status = Column(String(20), default='active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class FinancialInstitution(Base):
    """
    金融機構實體 (Financial Institution)。
    
    **使用時機:**
    - 當需要標識銀行、券商、保險公司等特殊金融法人時。
    - 用於儲存 SWIFT Code 或 LEI Code 等金融專用識別碼。
    """
    __tablename__ = 'financial_institutions'
    
    institution_id = Column(String(50), primary_key=True)
    company_id = Column(String(50), ForeignKey('companies.company_id'))
    institution_type = Column(String(50), nullable=False)
    swift_code = Column(String(11))
    lei_code = Column(String(20))
    
    status = Column(String(20), default='active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Exchange(Base):
    """
    交易所實體 (Exchange)。
    
    **使用時機:**
    - 定義交易場所 (如 TWSE, TPEx, NYSE)。
    - 用於正規化市場代碼，確保跨國交易資料的一致性。
    """
    __tablename__ = 'exchanges'
    
    exchange_id = Column(String(50), primary_key=True)
    exchange_name = Column(String(200), nullable=False)
    exchange_code = Column(String(10), unique=True)
    country = Column(String(2))
    market_type = Column(String(50))
    
    status = Column(String(20), default='active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class KeyPersonnel(Base):
    """
    關鍵人員實體 (Key Personnel)。
    
    **使用時機:**
    - 儲存公司董監事、經理人 (CEO, CFO) 等重要人物資訊。
    - 分析「人」與「公司」的關聯 (如董事長兼任情形)。
    """
    __tablename__ = 'key_personnel'
    
    person_id = Column(String(50), primary_key=True)
    full_name = Column(String(200), nullable=False)
    company_id = Column(String(50), ForeignKey('companies.company_id'))
    position_title = Column(String(100))
    position_type = Column(String(50))
    
    status = Column(String(20), default='active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class FinancialTerm(Base):
    """
    金融術語實體 (Financial Term)。
    
    **使用時機 (Use Cases):**
    1. **消除歧義 (Disambiguation)**: 當辯論雙方對某個指標 (例如 "Free Cash Flow") 的計算方式有分歧時。
    2. **知識增強 (Knowledge Augmentation)**: 初階 Agent (如 Junior Analyst) 遇到不熟悉的財經術語時，查詢標準定義。
    3. **報告標準化 (Standardization)**: 在生成最終投資報告時，確保使用的術語符合機構內部標準 (如 IFRS 定義)。

    **使用流程範例 (Example Workflow):**
    1. **觸發**: 辯論中，反方質疑正方的 "EBITDA" 計算未包含租賃費用。
    2. **查詢**: 正方 Agent 調用 `internal.term.lookup(q="EBITDA")`。
    3. **檢索**: 系統從此表 (`financial_terms`) 檢索標準定義、公式 (Formula) 與備註 (Notes)。
    4. **應用**: Agent 引用檢索到的官方公式回應質疑，確保論點基於共同認知的標準。
    """
    __tablename__ = 'financial_terms'
    
    term_id = Column(String(50), primary_key=True)
    term_name = Column(String(200), nullable=False)
    term_category = Column(String(50))
    definition = Column(Text)
    meta = Column(JSON)  # optional: {aliases, tags, lang, version, formula, notes}
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class CorporateRelationship(Base):
    """
    企業關聯實體 (Corporate Relationship)。
    
    **使用時機:**
    - 定義公司間的非層級關係 (如供應商、客戶、策略合作夥伴)。
    - 補足 `Company` 表中層級關係 (Parent/Subsidiary) 以外的商業網絡。
    """
    __tablename__ = 'corporate_relationships'
    
    relationship_id = Column(String(50), primary_key=True)
    company_id_1 = Column(String(50), ForeignKey('companies.company_id'), nullable=False)
    company_id_2 = Column(String(50), ForeignKey('companies.company_id'), nullable=False)
    relationship_type = Column(String(50), nullable=False)
    description = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())