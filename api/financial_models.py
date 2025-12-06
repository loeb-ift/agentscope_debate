from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime, DECIMAL, BigInteger, Time, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from api.database import Base

class Company(Base):
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
    __tablename__ = 'financial_terms'
    
    term_id = Column(String(50), primary_key=True)
    term_name = Column(String(200), nullable=False)
    term_category = Column(String(50))
    definition = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class CorporateRelationship(Base):
    __tablename__ = 'corporate_relationships'
    
    relationship_id = Column(String(50), primary_key=True)
    company_id_1 = Column(String(50), ForeignKey('companies.company_id'), nullable=False)
    company_id_2 = Column(String(50), ForeignKey('companies.company_id'), nullable=False)
    relationship_type = Column(String(50), nullable=False)
    description = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())