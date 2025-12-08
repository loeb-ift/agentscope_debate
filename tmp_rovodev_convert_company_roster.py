import csv, json, os, sys
from datetime import datetime

# Input path from argument or default
INPUT_PATH = sys.argv[1] if len(sys.argv) > 1 else "/Users/loeb/Desktop/agentscope_debate/公司實體名冊.txt"
OUTPUT_DIR = os.path.join("data", "seeds")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "companies.zh-TW.json")

# Mapping from Chinese headers to logical keys
HEADER_MAP = {
    "公司代號": "code",
    "公司名稱": "company_name",
    "公司簡稱": "short_name",
    "產業別": "industry_code",
    "住址": "address",
    "總機電話": "phone",
    "成立日期": "incorporation_date",
    "上市日期": "ipo_date",
    "網址": "website",
}

# Helper to parse date in YYYYMMDD -> YYYY-MM-DD

def parse_date(val: str):
    if not val:
        return None
    val = val.strip().replace("/", "").replace("-", "")
    if not val.isdigit() or len(val) != 8:
        return None
    try:
        dt = datetime.strptime(val, "%Y%m%d")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

# Load file and detect delimiter (many values are quoted, comma-separated)

def sniff_dialect(sample):
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=",\t")
        return dialect
    except Exception:
        class D:
            delimiter = ","
            quotechar = '"'
            doublequote = True
            escapechar = None
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL
        return D()

# Read file
if not os.path.exists(INPUT_PATH):
    print(f"Input file not found: {INPUT_PATH}")
    sys.exit(1)

with open(INPUT_PATH, "r", encoding="utf-8") as f:
    sample = f.read(2048)
    f.seek(0)
    dialect = sniff_dialect(sample)
    reader = csv.reader(f, delimiter=dialect.delimiter, quotechar=dialect.quotechar)
    rows = list(reader)

if not rows:
    print("No data rows found")
    sys.exit(1)

# Build header index map
header = [h.strip().strip('\ufeff') for h in rows[0]]
idx = {name: i for i, name in enumerate(header)}

required_headers = list(HEADER_MAP.keys())
missing = [h for h in required_headers if h not in idx]
if missing:
    print(f"Warning: missing headers: {missing}")

companies = []
seen_ids = set()

for r in rows[1:]:
    if not any(r):
        continue
    # Fetch values safely
    def get(h):
        i = idx.get(h)
        if i is None or i >= len(r):
            return ""
        return r[i].strip().strip('"')

    code = get("公司代號")
    name = get("公司名稱")
    short = get("公司簡稱")
    address = get("住址")
    phone = get("總機電話")
    industry = get("產業別")
    url = get("網址")
    inc_date_raw = get("成立日期")
    ipo_date_raw = get("上市日期")

    if not code or not name:
        continue

    # Normalize IDs for TW market
    try:
        code_int = int(code)
        if 1 <= code_int <= 99999:
            ticker_symbol = f"{code}.TW"
            company_id = ticker_symbol
        else:
            ticker_symbol = code
            company_id = code
    except Exception:
        ticker_symbol = code
        company_id = code

    if company_id in seen_ids:
        continue
    seen_ids.add(company_id)

    comp = {
        "company_id": company_id,
        "company_name": name,
        "short_name": short or None,
        "industry_sector": None,  # can be enriched later
        "industry_group": None,
        "sub_industry": None,
        "gics_code": None,
        "is_public": True,
        "listing_status": "listed",
        "primary_exchange": "TWSE",
        "ticker_symbol": ticker_symbol,
        "country_of_incorporation": "TW",
        "country_of_domicile": "TW",
        "headquarters_country": "TW",
        "headquarters_address": address or None,
        "phone": phone or None,
        "website_url": url or None,
        "incorporation_date": parse_date(inc_date_raw),
        "ipo_date": parse_date(ipo_date_raw),
        # leave other optional fields empty
    }
    companies.append(comp)

# Ensure output dir
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(OUTPUT_PATH, "w", encoding="utf-8") as out:
    json.dump({"companies": companies}, out, ensure_ascii=False, indent=2)

print(f"Wrote {len(companies)} companies to {OUTPUT_PATH}")
