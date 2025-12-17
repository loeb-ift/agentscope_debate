import json
import os
import re
from bs4 import BeautifulSoup

def normalize_id(text):
    """
    Generate a normalized ID from text.
    e.g., "Capital Market" -> "capital_market"
    """
    # Remove special chars and replace spaces with underscores
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return clean.strip().lower().replace(' ', '_')

def parse_term_title(title_text):
    """
    Parse title like "ADP Non-Farm Employment Change( ADP非農就業人數變化 )"
    Returns (english_name, chinese_name)
    """
    # Pattern to match "English ( Chinese )" or "English( Chinese )"
    # Note: The parenthesis might be full-width or half-width
    match = re.search(r'^(.*?)\s*[\(\（](.*?)[\)\）]$', title_text)
    if match:
        en = match.group(1).strip()
        zh = match.group(2).strip()
        return en, zh
    
    # Fallback: if no parenthesis, assume it's just one name (could be mixed)
    return title_text.strip(), title_text.strip()

def enrich_terms():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, 'temp_glossary.html')
    json_path = os.path.join(base_dir, 'data', 'seeds', 'financial_terms.zh-TW.json')
    
    # 1. Load existing terms
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            existing_terms = data.get('terms', [])
            metadata = data.get('metadata', {})
    else:
        existing_terms = []
        metadata = {
            "lang": "zh-TW",
            "source": "enriched_v1",
            "version": 1,
            "created_at": "2025-12-17"
        }
    
    # Map existing IDs for quick lookup
    existing_ids = {t['id'] for t in existing_terms}
    existing_names = {t['name'] for t in existing_terms} # To avoid exact duplicate names if possible
    
    print(f"Loaded {len(existing_terms)} existing terms.")

    # 2. Parse HTML
    if not os.path.exists(html_path):
        print(f"Error: {html_path} not found.")
        return

    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    # Find all glossary items
    # Structure: <div class="glossary_accordion-item"> ... <span class="glossary_button-text">Title</span> ... <div class="glossary_accordion-body">Definition</div>
    items = soup.find_all('div', class_='glossary_accordion-item')
    print(f"Found {len(items)} items in HTML.")
    
    new_terms_count = 0
    
    for item in items:
        # Extract Title
        title_span = item.find('span', class_='glossary_button-text')
        if not title_span:
            continue
        
        full_title = title_span.get_text().strip()
        en_name, zh_name = parse_term_title(full_title)
        
        # Determine main name and aliases
        # If we have both EN and ZH, prefer ZH as 'name' (since file is zh-TW) and EN as alias + ID source
        if en_name and zh_name and en_name != zh_name:
            main_name = zh_name
            term_id = "glossary_" + normalize_id(en_name) # prefix to avoid collision with standard logic
            aliases = [en_name, full_title]
        else:
            main_name = full_title
            # Try to guess language for ID
            if re.match(r'^[a-zA-Z\s]+$', main_name):
                term_id = "glossary_" + normalize_id(main_name)
            else:
                # Fallback for pure Chinese or mixed without parenthesis
                term_id = "glossary_" + normalize_id(main_name)
                # Cap length
                term_id = term_id[:50]
            aliases = []

        # Extract Definition
        body_div = item.find('div', class_='glossary_accordion-body')
        if body_div:
            # Get text, strip whitespace
            definition = body_div.get_text(separator=' ', strip=True)
        else:
            definition = ""
        
        # Skip if ID or Name exists
        if term_id in existing_ids:
            # print(f"Skipping duplicate ID: {term_id}")
            continue
        
        # Check against existing names (fuzzy check)
        if main_name in existing_names:
            # print(f"Skipping duplicate Name: {main_name}")
            continue

        # Add new term
        new_term = {
            "id": term_id,
            "name": main_name,
            "category": "Forex/Pro Glossary", # Default category for these scraped terms
            "definition": definition,
            "aliases": aliases,
            "tags": ["ForexTime Scraped"],
            "lang": "zh-TW",
            "version": 1
        }
        
        existing_terms.append(new_term)
        existing_ids.add(term_id)
        new_terms_count += 1
    
    print(f"Added {new_terms_count} new terms.")
    
    # 3. Save updated JSON
    # Sort terms by ID for consistency? Or keep order? 
    # Let's keep existing order + new appended
    
    updated_data = {
        "metadata": metadata,
        "terms": existing_terms
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=2)
    
    print(f"Saved updated terms to {json_path}")

if __name__ == "__main__":
    enrich_terms()
