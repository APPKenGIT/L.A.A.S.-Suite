"""
Pricelist Engine for L.A.A.S.-Suite
Parses multi-tab Excel price lists (such as 2026 Prijslijst.xlsx)
and manages custom article catalogs, discount percentages, and net prices per dossier.
"""

import openpyxl
import re
import os

def parse_volume_string(content_str):
    """Parse volume and unit from strings like '400 ml', '1 liter', '13 liter', '120 kg'."""
    if not content_str:
        return 1.0, 'unit'
    s = str(content_str).strip().lower()
    
    m_ml = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*ml', s)
    if m_ml:
        return float(m_ml.group(1)) / 1000.0, 'L'
        
    m_l = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:liter|l\b)', s)
    if m_l:
        return float(m_l.group(1)), 'L'
        
    m_g = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*g(?:ram)?', s)
    if m_g:
        return float(m_g.group(1)) / 1000.0, 'kg'
        
    m_kg = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*kg', s)
    if m_kg:
        return float(m_kg.group(1)), 'kg'
        
    m_st = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:stuks?|pcs?|st\b)', s)
    if m_st:
        return float(m_st.group(1)), 'stuks'
        
    return 1.0, 'unit'

def get_tier_price(tiers, quantity):
    """
    Determines the applicable tier unit price based on quantity.
    Returns (effective_unit_price, matched_min_qty).
    """
    if not tiers or not isinstance(tiers, list):
        return None, 1
    sorted_tiers = sorted(tiers, key=lambda x: x.get('min_qty', 1))
    try:
        qty = float(quantity)
    except (ValueError, TypeError):
        qty = 1.0
        
    best_price = sorted_tiers[0].get('unit_price', 0.0)
    best_min = sorted_tiers[0].get('min_qty', 1)
    
    for t in sorted_tiers:
        if qty >= float(t.get('min_qty', 1)):
            best_price = t.get('unit_price', best_price)
            best_min = t.get('min_qty', 1)
            
    return round(float(best_price), 2), best_min

def parse_excel_pricelist(filepath):
    """
    Parses a multi-tab price list Excel file.
    Captures article details, accurate product descriptions across lubricants & hardware,
    and quantity volume tiers (staffels).
    Returns a dict with metadata and a list of parsed items.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Prijslijst bestand niet gevonden: {filepath}")

    wb = openpyxl.load_workbook(filepath, data_only=True)
    items = []
    
    for sheetname in wb.sheetnames:
        ws = wb[sheetname]
        current_product = sheetname.strip()
        current_item = None
        
        for r in range(1, ws.max_row + 1):
            c1 = ws.cell(row=r, column=1).value
            c2 = ws.cell(row=r, column=2).value
            c3 = ws.cell(row=r, column=3).value
            c4 = ws.cell(row=r, column=4).value
            c5 = ws.cell(row=r, column=5).value
            c6 = ws.cell(row=r, column=6).value
            c7 = ws.cell(row=r, column=7).value
            c8 = ws.cell(row=r, column=8).value
            
            # Check if row is a product title header
            if c1 and isinstance(c1, str) and not c2 and not c3 and not c4:
                txt = c1.strip()
                if txt and not txt.startswith('*') and len(txt) > 2 and 'prijs' not in txt.lower():
                    current_product = txt
                    current_item = None
                    continue
                    
            # Skip column header rows
            if c1 and str(c1).strip().lower() in ['artikelnr', 'artikelnr.', 'art.nr']:
                current_item = None
                continue
                
            art_nr = None
            if c1 is not None:
                try:
                    if isinstance(c1, (int, float)) and c1 > 0:
                        art_nr = str(int(c1))
                    elif isinstance(c1, str) and c1.strip().isdigit():
                        art_nr = c1.strip()
                except Exception:
                    pass
                    
            if art_nr:
                price = None
                for p_cand in [c7, c6, c8, c5]:
                    if isinstance(p_cand, (int, float)) and p_cand > 0:
                        price = round(float(p_cand), 2)
                        break
                        
                qty = 1
                if isinstance(c4, (int, float)) and c4 > 0:
                    qty = int(c4)
                    
                extra_desc = ""
                for desc_cand in [c4, c3]:
                    if isinstance(desc_cand, str) and len(desc_cand.strip()) > 1 and desc_cand.strip() != '*':
                        extra_desc = desc_cand.strip()
                        break

                content = str(c2).strip() if (c2 and c2 != '*') else ''
                packaging = str(c3).strip() if (c3 and c3 != '*' and c3 != extra_desc) else ''
                vol_num, vol_unit = parse_volume_string(content or extra_desc)
                
                if extra_desc and extra_desc.lower() != current_product.lower():
                    full_name = f"{current_product} - {extra_desc}".strip()
                    if content and content not in full_name:
                        full_name += f" ({content})"
                else:
                    full_name = f"{current_product} ({content} {packaging})".strip() if content or packaging else current_product
                    
                if price:
                    current_item = {
                        'article_nr': art_nr,
                        'product_name': current_product,
                        'description': full_name,
                        'category': sheetname.strip(),
                        'content': content,
                        'packaging': packaging or ('spuitbus' if 'spuitbus' in full_name.lower() else 'stuks'),
                        'unit_price': price,
                        'volume_val': vol_num,
                        'volume_unit': vol_unit,
                        'tiers': [{'min_qty': qty, 'unit_price': price}],
                        'discount_pct': 0.0,
                        'net_price': price,
                        'is_custom': False
                    }
                    items.append(current_item)
                else:
                    current_item = None
            elif current_item is not None:
                tier_qty = None
                if isinstance(c4, (int, float)) and c4 > 1:
                    tier_qty = int(c4)
                elif isinstance(c3, (int, float)) and c3 > 1:
                    tier_qty = int(c3)
                    
                tier_price = None
                for p_cand in [c6, c5, c7, c8]:
                    if isinstance(p_cand, (int, float)) and p_cand > 0:
                        tier_price = round(float(p_cand), 2)
                        break
                        
                if tier_qty and tier_price:
                    if not any(t.get('min_qty') == tier_qty for t in current_item.get('tiers', [])):
                        current_item['tiers'].append({'min_qty': tier_qty, 'unit_price': tier_price})
                        current_item['tiers'].sort(key=lambda x: x.get('min_qty', 1))
                        
    return {
        'filename': os.path.basename(filepath),
        'total_items': len(items),
        'items': items
    }

def get_default_pricelist_from_templates(template_dir='voorbeeldbestanden'):
    """Loads default 2026 Prijslijst if present in template directory."""
    default_path = os.path.join(template_dir, "2026 Prijslijst.xlsx")
    if os.path.exists(default_path):
        try:
            return parse_excel_pricelist(default_path)
        except Exception as e:
            print(f"Kon 2026 Prijslijst niet automatisch inladen: {e}")
    return {'filename': None, 'total_items': 0, 'items': []}

def apply_discount(item, discount_pct):
    """Applies a discount percentage and updates net_price."""
    try:
        pct = max(0.0, min(100.0, float(discount_pct)))
    except (ValueError, TypeError):
        pct = 0.0
    item['discount_pct'] = pct
    base = float(item.get('unit_price', 0.0))
    item['net_price'] = round(base * (1.0 - pct / 100.0), 2)
    return item

def add_custom_article(pricelist_data, article_nr, name, category, packaging, content, unit_price, discount_pct=0.0):
    """Adds a custom article to the dossier price list."""
    vol_num, vol_unit = parse_volume_string(content)
    base = round(float(unit_price), 2)
    disc = max(0.0, min(100.0, float(discount_pct)))
    net = round(base * (1.0 - disc / 100.0), 2)
    
    new_item = {
        'article_nr': str(article_nr),
        'product_name': name,
        'description': f"{name} ({content} {packaging})".strip(),
        'category': category or 'Maatwerk / Handmatig',
        'content': content,
        'packaging': packaging,
        'unit_price': base,
        'volume_val': vol_num,
        'volume_unit': vol_unit,
        'tiers': [{'min_qty': 1, 'unit_price': base}],
        'discount_pct': disc,
        'net_price': net,
        'is_custom': True
    }
    
    pricelist_data.setdefault('items', []).append(new_item)
    pricelist_data['total_items'] = len(pricelist_data['items'])
    return new_item
