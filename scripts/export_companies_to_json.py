import sqlite3
import json
from datetime import datetime, date

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)

def export_to_json():
    # Connect to the database
    conn = sqlite3.connect('data/debate.db')
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    cursor = conn.cursor()
    
    # Select all records from the companies table
    # We explicitly select fields to match the target JSON structure and order
    # based on the schema we just inspected and the target file format
    cursor.execute("""
        SELECT 
            company_id,
            company_name,
            short_name,
            industry_sector,
            industry_group,
            sub_industry,
            gics_code,
            is_public,
            listing_status,
            primary_exchange,
            ticker_symbol,
            country_of_incorporation,
            country_of_domicile,
            headquarters_country,
            headquarters_address,
            phone,
            website_url,
            incorporation_date,
            ipo_date
        FROM companies
    """)
    
    rows = cursor.fetchall()
    
    # Convert to list of dictionaries
    companies_list = []
    for row in rows:
        company_dict = dict(row)
        
        # Handle boolean conversion for is_public (sqlite stores as 1/0)
        if company_dict['is_public'] == 1:
            company_dict['is_public'] = True
        elif company_dict['is_public'] == 0:
            company_dict['is_public'] = False
            
        companies_list.append(company_dict)
    
    # Create the final structure
    output_data = {"companies": companies_list}
    
    # Write to JSON file
    output_path = 'data/seeds/companies.zh-TW.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2, default=json_serial)
    
    print(f"Successfully exported {len(companies_list)} companies to {output_path}")
    
    conn.close()

if __name__ == "__main__":
    export_to_json()