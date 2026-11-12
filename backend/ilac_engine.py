"""
ILAC Engine for L.A.A.S.-Suite
Parses ILAC Excel exports, dynamically identifies tasks and intervals,
calculates product requirements over custom N-year contracts with Product x Tool verification,
applies automatic volume tier (staffel) pricing, and calculates Phase 2 & 3 contract proposals.
"""

import openpyxl
import re
import math
import os
from backend.pricelist_engine import get_tier_price

def parse_ilac_volume(vol_str, gram_per_pompslag=1.5, ml_per_second=1.0):
    """
    Parses volume strings like:
      - '3 Pompslagen' -> 4.5 g (standard grease gun stroke is 1.5 g)
      - '5 Seconden'   -> 5.0 ml (standard aerosol discharge is 1.0 ml/sec)
      - '400.0 Gram'   -> 400.0 g
      - '10.0 Milliliter' -> 10.0 ml
      - '0.5 Liter'    -> 0.5 L
      - '1 Stuks'      -> 1 stuks
      - '0 Niet van toepassing' -> 0.0 nvt
    Returns (numeric_value, standard_unit, display_str).
    Units: 'g', 'ml', 'L', 'stuks', 'nvt', 'unit'.
    """
    if not vol_str:
        return 0.0, 'unit', '0'
    s = str(vol_str).strip()
    s_low = s.lower()
    
    # Check for 'Niet van toepassing' / 0
    if 'niet van toepassing' in s_low or s in ['0', '0.0', 'none', '-']:
        return 0.0, 'nvt', 'N.v.t.'
        
    m = re.match(r'([0-9]+(?:\.[0-9]+)?)\s*(.*)', s)
    if not m:
        return 0.0, 'unit', s
        
    val = float(m.group(1))
    unit_raw = m.group(2).strip().lower()
    
    # 1. Pompslagen (Grease gun strokes) -> gram_per_pompslag g per stroke
    if any(p in unit_raw for p in ['pompslag', 'pompslagen', 'slag', 'slagen']):
        factor = float(gram_per_pompslag) if gram_per_pompslag else 1.5
        g_val = round(val * factor, 2)
        return g_val, 'g', f"{val:.0f} slagen ({g_val:.1f} g)"
        
    # 2. Seconden (Aerosol spray time) -> ml_per_second ml per second
    elif any(sec in unit_raw for sec in ['seconde', 'seconden', 'sec']):
        factor = float(ml_per_second) if ml_per_second else 1.0
        ml_val = round(val * factor, 2)
        return ml_val, 'ml', f"{val:.0f} sec ({ml_val:.1f} ml)"
        
    # 3. Milliliter
    elif 'milliliter' in unit_raw or unit_raw == 'ml':
        return val, 'ml', f"{val:.1f} ml"
        
    # 4. Gram
    elif 'gram' in unit_raw or unit_raw in ['g', 'gr']:
        return val, 'g', f"{val:.1f} g"
        
    # 5. Liter
    elif 'liter' in unit_raw or unit_raw == 'l':
        return val, 'L', f"{val:.2f} L"
        
    # 6. Kilogram
    elif 'kilogram' in unit_raw or unit_raw == 'kg':
        return val * 1000.0, 'g', f"{val:.1f} kg"
        
    # 7. Stuks
    elif 'stuk' in unit_raw or 'pcs' in unit_raw:
        return val, 'stuks', f"{int(val)} stuks"
        
    else:
        return val, 'unit', s

def parse_interval_to_days(interval_val, unit_of_time='D'):
    """Converts task interval to number of days."""
    try:
        val = float(interval_val)
    except (ValueError, TypeError):
        return None
        
    if val <= 0:
        return None
        
    u = str(unit_of_time).strip().upper() if unit_of_time else 'D'
    if u == 'W':
        return val * 7.0
    elif u == 'M':
        return val * (365.0 / 12.0)
    elif u == 'Y':
        return val * 365.0
    else: # Default Days ('D')
        return val

def parse_ilac_excel(filepath, gram_per_pompslag=1.5, ml_per_second=1.0):
    """
    Parses an ILAC upload Excel file dynamically.
    Returns metadata and list of points.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"ILAC bestand niet gevonden: {filepath}")

    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    if ws.max_row < 5:
        for sname in wb.sheetnames:
            if wb[sname].max_row >= 5:
                ws = wb[sname]
                break
                
    headers = {}
    for c in range(1, ws.max_column + 1):
        v1 = ws.cell(row=1, column=c).value
        v2 = ws.cell(row=2, column=c).value
        h_name = str(v1).strip() if v1 else (str(v2).strip() if v2 else f"Col_{c}")
        headers[c] = h_name

    col_dept = None
    col_loc = None
    col_machine = None
    col_part = None
    col_maint = None
    col_count = None
    col_tool = None
    col_unit_time = None
    col_prod = None
    col_vol = None
    col_time_mins = None
    col_short_remark = None
    
    task_cols = {}

    for c, h in headers.items():
        hl = h.lower()
        if 'department' in hl or 'afdeling' in hl:
            col_dept = c
        elif hl == 'location' or hl == 'locatie':
            col_loc = c
        elif hl == 'machine':
            col_machine = c
        elif 'machine part' in hl or 'machinedeel' in hl:
            if 'id' not in hl and 'order' not in hl and 'uid' not in hl:
                col_part = c
        elif 'maintenance part' in hl or 'onderhoudspunt' in hl:
            if 'id' not in hl and 'uid' not in hl:
                col_maint = c
        elif hl == 'number' or hl == 'aantal':
            col_count = c
        elif hl == 'tool':
            col_tool = c
        elif 'unit of time' in hl or 'tijdseenheid' in hl:
            col_unit_time = c
        elif hl == 'product':
            col_prod = c
        elif hl == 'volume':
            col_vol = c
        elif 'short remark' in hl or 'korte opmerking' in hl:
            col_short_remark = c
        elif 'time in minutes' in hl or 'tijd in minuten' in hl:
            col_time_mins = c
        elif any(t in hl for t in ['visuele', 'smeren', 'vervangen', 'oliewissel', 'staalname', 'bijvullen', 'reinigen']):
            task_cols[c] = h

    for c in range(18, min(25, ws.max_column + 1)):
        if c not in task_cols:
            h = headers.get(c, f"Taak_{c}")
            if h and 'unit' not in h.lower() and 'color' not in h.lower() and 'print' not in h.lower():
                task_cols[c] = h

    points = []
    start_row = 3 if ws.cell(row=2, column=1).value in ['Afdeling', 'Department', 'Locatie'] else 2

    point_id_counter = 1

    for r in range(start_row, ws.max_row + 1):
        dept_val = ws.cell(row=r, column=col_dept).value if col_dept else ''
        loc_val = ws.cell(row=r, column=col_loc).value if col_loc else ''
        prod_val = ws.cell(row=r, column=col_prod).value if col_prod else ''
        
        if not dept_val and not loc_val and not prod_val:
            continue
            
        machine_val = ws.cell(row=r, column=col_machine).value if col_machine else ''
        part_val = ws.cell(row=r, column=col_part).value if col_part else ''
        maint_val = ws.cell(row=r, column=col_maint).value if col_maint else ''
        
        count_raw = ws.cell(row=r, column=col_count).value if col_count else 1
        try:
            count_val = int(count_raw) if count_raw is not None else 1
        except Exception:
            count_val = 1
            
        tool_val = ws.cell(row=r, column=col_tool).value if col_tool else ''
        time_unit_val = ws.cell(row=r, column=col_unit_time).value if col_unit_time else 'D'
        vol_raw = ws.cell(row=r, column=col_vol).value if col_vol else ''
        remark_raw = ws.cell(row=r, column=col_short_remark).value if col_short_remark else ''
        time_mins_raw = ws.cell(row=r, column=col_time_mins).value if col_time_mins else 0
        try:
            time_mins = float(time_mins_raw) if time_mins_raw else 0.0
        except Exception:
            time_mins = 0.0
            
        vol_num, vol_std_unit, vol_display = parse_ilac_volume(vol_raw, gram_per_pompslag=gram_per_pompslag, ml_per_second=ml_per_second)
        prod_name = str(prod_val).strip() if prod_val else 'Niet van toepassing'
        
        tasks = []
        for tc, tname in task_cols.items():
            t_val = ws.cell(row=r, column=tc).value
            if t_val is not None and str(t_val).strip() != '':
                interval_days = parse_interval_to_days(t_val, time_unit_val)
                if interval_days and interval_days > 0:
                    tasks.append({
                        'task_name': tname,
                        'interval_raw': t_val,
                        'unit_of_time': time_unit_val,
                        'interval_days': round(interval_days, 1),
                        'annual_frequency': round(365.0 / interval_days, 3)
                    })

        points.append({
            'point_id': f"P_{point_id_counter:04d}",
            'row_num': r,
            'department': str(dept_val).strip() if dept_val else '',
            'location': str(loc_val).strip() if loc_val else '',
            'machine': str(machine_val).strip() if machine_val else '',
            'machine_part': str(part_val).strip() if part_val else '',
            'maintenance_part': str(maint_val).strip() if maint_val else '',
            'point_count': count_val,
            'tool': str(tool_val).strip() if tool_val else '',
            'product_name': prod_name,
            'volume_raw': str(vol_raw).strip() if vol_raw else '',
            'volume_numeric': vol_num,
            'volume_unit': vol_std_unit,
            'volume_display': vol_display,
            'short_remark': str(remark_raw).strip() if remark_raw else '',
            'time_in_minutes': time_mins,
            'tasks': tasks
        })
        point_id_counter += 1

    return {
        'filename': os.path.basename(filepath),
        'total_points': len(points),
        'task_categories': list(task_cols.values()),
        'points': points
    }

def normalize_product_name(p):
    """Normalizes product name for exact matching, stripping aerosol markers and suffixes."""
    p_clean = str(p or '').lower().replace('interflon', '').strip()
    is_aero = any(w in p_clean for w in ['(aerosol)', 'aerosol', 'spuitbus'])
    p_base = re.sub(r'[\(\[\{].*?[\)\]\}]', '', p_clean)
    p_base = re.sub(r'\s*-\s*(ls|lube-shuttle|shuttle|service pack|vulpomp)', '', p_base, flags=re.IGNORECASE)
    p_base = ' '.join(p_base.split()).strip()
    return p_base, is_aero

def match_tool_to_pricelist(tool_name, pricelist_items):
    """
    Finds best matching tool / hardware articles from the pricelist for a given tool from the audit.
    """
    if not tool_name or not pricelist_items:
        return []
    
    tl = tool_name.lower().strip()
    matches = []
    preferred_cats = ['Hulpmaterialen', 'Automatic lubrication', 'Interflon hardware', 'Diversen']
    
    if 'accugreaser' in tl or 'vetpistool' in tl:
        keywords = ['lube-shuttle grease gun', 'lube-shuttle tg', 'one hand grease gun', 'grease gun']
    elif 'cls filler' in tl or 'vulpomp' in tl:
        keywords = ['zuig- en vulpomp', 'vulpomp', 'filling set', 'vatpomp']
    elif 'oliestaalname' in tl or 'vetstaalname' in tl or 'staalname' in tl:
        keywords = ['staalnamepompje', 'staalname', 'tube']
    elif 'single point lubricator' in tl or 'spl' in tl:
        keywords = ['single point lubricator', 'filling set', 'bracket', 'terugslagventiel']
    elif 'service pack' in tl:
        keywords = ['servicepack', 'service pack', 'single point lubricator']
    elif 'oliekan' in tl:
        keywords = ['kraan', 'schenkkan', 'jerrycan', 'zuig- en vulpomp']
    elif 'spuitbus' in tl or 'spray' in tl:
        keywords = ['handgreep', 'spuitlans', 'nevelsysteem']
    else:
        keywords = [tl]

    seen_arts = set()
    for it in pricelist_items:
        art = it.get('article_nr')
        if art in seen_arts:
            continue
        desc = (it.get('description') or '').lower()
        cat = it.get('category', '')
        score = 0
        for kw in keywords:
            if kw in desc:
                score += 40
        if cat in preferred_cats:
            score += 10
        if score > 0:
            seen_arts.add(art)
            matches.append((score, it))
            
    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches[:4]]

def find_candidate_packagings(prod_name, pricelist_items, tool_name=None):
    """
    Finds and ranks all candidate packaging items from the pricelist for a specific product.
    Includes all available packaging types for that product line so the user can freely override,
    while ranking the most suitable tool-packaging at the top as recommended default.
    """
    if not pricelist_items or not prod_name:
        return []

    p_clean = str(prod_name).lower().replace('interflon', '').strip()
    base_name, is_aerosol = normalize_product_name(prod_name)
    tool_lower = (tool_name or '').lower()

    wants_aerosol = is_aerosol or any(w in tool_lower for w in ['spuitbus', 'aerosol', 'spray'])
    wants_lube_shuttle = any(w in p_clean for w in ['ls', 'lube-shuttle', 'shuttle']) or 'accugreaser' in tool_lower
    wants_bulk = any(w in tool_lower for w in ['vulpomp', 'cls filler', 'oliekan', 'vatpomp', 'bulk'])
    wants_spl = any(w in tool_lower for w in ['single point lubricator', 'service pack', 'spl'])

    # Helper to clean tokens and identify distinctive product codes (e.g. g100, htg, mp00, mp2/3, fluor)
    def clean_name_tokens(name):
        n = re.sub(r'[\(\[\{].*?[\)\]\}]', '', str(name or '').lower().replace('interflon', ''))
        n = re.sub(r'\s*-\s*(ls|lube-shuttle|shuttle|service pack|vulpomp)', '', n, flags=re.IGNORECASE)
        toks = [w for w in re.split(r'[\s\-_/]+', n) if w and w not in ['the', 'and', 'for', 'de', 'en', 'van']]
        return toks

    p_toks = clean_name_tokens(prod_name)
    generic_words = {'oil', 'grease', 'lube', 'vet', 'olie'}
    dist_toks = [w for w in p_toks if w not in generic_words]
    if not dist_toks:
        dist_toks = p_toks

    # 1. Collect all pricelist items matching this specific product line
    all_packagings = []
    seen_articles = set()

    for it in pricelist_items:
        it_full_name = f"{it.get('description', '')} {it.get('product_name', '')}"
        it_toks = set(clean_name_tokens(it_full_name))
        it_lower = it_full_name.lower()
        art_nr = str(it.get('article_nr', '')).strip()

        is_match = False
        if all(d in it_toks or d in it_lower for d in dist_toks):
            # Oil vs Grease sanity check to prevent cross-matching
            if 'grease' in p_toks and 'oil' in it_toks and 'grease' not in it_toks:
                continue
            if 'oil' in p_toks and 'grease' in it_toks and 'oil' not in it_toks:
                continue
            is_match = True

        if is_match and art_nr and art_nr not in seen_articles:
            seen_articles.add(art_nr)
            all_packagings.append(it)

    # 2. Score and sort candidates so the tool preference ranks first
    def score_packaging(m):
        pkg = (m.get('packaging') or '').lower()
        cnt = (m.get('content') or '').lower()
        desc = (m.get('description') or '').lower()
        it_name = m.get('product_name', '').lower()
        _, it_aero = normalize_product_name(it_name)
        is_it_aerosol = it_aero or 'spuitbus' in pkg or 'aerosol' in pkg or 'spuitbus' in desc

        score = 0
        if wants_lube_shuttle:
            if 'lube-shuttle' in pkg or 'shuttle' in pkg or 'lube-shuttle' in desc:
                score += 100
            elif 'patroon' in pkg or 'patr' in pkg or 'cartridge' in pkg:
                score += 60
        elif wants_bulk:
            if any(w in pkg for w in ['vat', 'emmer', 'jerrycan', 'can', 'drum', 'pail']):
                score += 100
            if any(w in cnt for w in ['13 liter', '16 kg', '20 l', '20 liter', '50 kg', '60 l', '120 kg', '180 kg', '200 l']):
                score += 60
        elif wants_spl:
            if any(w in pkg for w in ['spl', 'service pack', 'cartridge']) or any(w in desc for w in ['servicepack', 'single point lubricator']):
                score += 100
            if any(w in cnt for w in ['60 ml', '125 ml', '250 ml', '15 ml']):
                score += 60
        elif wants_aerosol:
            if is_it_aerosol:
                score += 100

        # General preference bonus if not aerosol wanted and not aerosol item
        if not wants_aerosol and not is_it_aerosol:
            score += 20
        return score

    all_packagings.sort(key=score_packaging, reverse=True)
    return all_packagings

def calculate_ilac_requirements(points, contract_years=3, pricelist_items=None, manual_items=None, 
                                gram_per_pompslag=1.5, ml_per_second=1.0, packaging_overrides=None,
                                units_overrides=None, tier_overrides=None,
                                global_discount_pct=None, category_discounts=None):
    """
    Calculates product requirements, packaging counts, and tiered costs over contract_years.
    Groups points by (Product x Tool) matrix to allow precise packaging attribution.
    Dynamically identifies all tools from the audit for the Fase 2 checklist.
    """
    years = max(1, int(contract_years))
    contract_days = years * 365.0
    
    product_totals = {}
    evaluated_long_tasks = []
    recurring_execution_minutes_per_year = 0.0
    one_off_execution_minutes = 0.0
    recurring_oil_analyses_per_year = 0.0
    one_off_oil_analyses = 0.0
    detected_tools_map = {}

    for pt in points:
        count = pt['point_count']
        mins = pt.get('time_in_minutes', 0.0)
        remark = pt.get('short_remark', '').lower()
        prod = pt['product_name']
        tool = (pt.get('tool') or 'Standaard').strip()

        # Tool audit collection
        if tool and tool.lower() not in ['niet van toepassing', 'none', '-', 'visueel']:
            if tool not in detected_tools_map:
                detected_tools_map[tool] = {
                    'tool_name': tool,
                    'point_count': 0,
                    'sample_points': []
                }
            detected_tools_map[tool]['point_count'] += count
            if len(detected_tools_map[tool]['sample_points']) < 3:
                detected_tools_map[tool]['sample_points'].append(f"{pt['machine']} - {pt['maintenance_part']}")

        # 1. Evaluate tasks for work hours and oil analyses
        for t in pt['tasks']:
            tname = t['task_name']
            interval_d = t['interval_days']
            freq = t['annual_frequency']
            
            is_one_off_task = (interval_d >= contract_days - 0.5) if years > 1 else (interval_d > 365.5)

            if is_one_off_task:
                one_off_execution_minutes += (mins * count)
                if any(w in tname.lower() for w in ['analyse', 'staalname', 'staal', 'bemonstering']):
                    one_off_oil_analyses += count
            else:
                recurring_execution_minutes_per_year += (mins * count * freq)
                if any(w in tname.lower() for w in ['analyse', 'staalname', 'staal', 'bemonstering']):
                    recurring_oil_analyses_per_year += (count * freq)

        # 2. Skip lubricant volume aggregation if not consumable product
        if not prod or prod.lower() in ['niet van toepassing', 'none', '-']:
            continue
            
        vol_raw = pt.get('volume_raw', '')
        if vol_raw:
            vol_std, std_unit, _ = parse_ilac_volume(vol_raw, gram_per_pompslag=gram_per_pompslag, ml_per_second=ml_per_second)
        else:
            vol_std = pt.get('volume_numeric', 0.0)
            std_unit = pt.get('volume_unit', 'unit')
        
        combo_key = f"{prod}___{tool}"
        if combo_key not in product_totals:
            product_totals[combo_key] = {
                'product_name': prod,
                'tool': tool,
                'combo_key': combo_key,
                'points_count': 0,
                'annual_volume': 0.0,
                'volume_unit': std_unit,
                'tasks_summary': {},
                'total_contract_volume': 0.0,
                'long_interval_points': 0
            }
            
        product_totals[combo_key]['points_count'] += count
        
        for t in pt['tasks']:
            tname = t['task_name']
            interval_d = t['interval_days']
            freq = t['annual_frequency']
            is_one_off_task = (interval_d >= contract_days - 0.5) if years > 1 else (interval_d > 365.5)
            
            is_reservoir_check = ('bijvullen' in tname.lower() or 'top-up' in remark or 'indien nodig' in remark) and interval_d <= 14 and vol_std >= 1.0 and std_unit == 'L'
            
            if is_reservoir_check:
                ann_vol = count * max(0.5, vol_std * 0.15)
            elif is_one_off_task:
                product_totals[combo_key]['long_interval_points'] += count
                evaluated_long_tasks.append({
                    'point_id': pt['point_id'],
                    'machine': pt['machine'],
                    'maintenance_part': pt['maintenance_part'],
                    'product_name': prod,
                    'tool': tool,
                    'task_name': tname,
                    'interval_days': interval_d,
                    'interval_years': round(interval_d / 365.0, 1),
                    'contract_years': years,
                    'volume_numeric': vol_std * count,
                    'volume_unit': std_unit,
                    'status': 'Buiten standaard contractduur' if interval_d > contract_days else 'Eenmalig binnen contractduur'
                })
                ann_vol = (count * vol_std) / years
            else:
                ann_vol = count * vol_std * freq
                
            product_totals[combo_key]['annual_volume'] += ann_vol
            product_totals[combo_key]['tasks_summary'][tname] = product_totals[combo_key]['tasks_summary'].get(tname, 0) + count

    # Compute packaging and costs with staffel pricing
    aggregated_list = []
    total_products_cost = 0.0

    for combo_key, pdata in sorted(product_totals.items(), key=lambda x: (x[1]['product_name'], x[1]['tool'])):
        prod_name = pdata['product_name']
        tool_name = pdata['tool']
        tot_vol = round(pdata['annual_volume'] * years, 2)
        pdata['total_contract_volume'] = tot_vol
        pdata['annual_volume'] = round(pdata['annual_volume'], 2)
        prod_unit = pdata['volume_unit']
        
        candidates = find_candidate_packagings(prod_name, pricelist_items, tool_name)
        matched_item = candidates[0] if candidates else None

        # Check for persistent manual packaging override
        if packaging_overrides and isinstance(packaging_overrides, dict):
            override_art = str(packaging_overrides.get(combo_key) or packaging_overrides.get(prod_name) or '')
            if override_art:
                matched_override = next((c for c in pricelist_items if str(c.get('article_nr')) == override_art), None)
                if matched_override:
                    matched_item = matched_override
                    # Make sure matched_item is in candidates list
                    if not any(str(c.get('article_nr')) == override_art for c in candidates):
                        candidates.insert(0, matched_override)
        
        is_aerosol_prod = 'aerosol' in prod_name.lower() or 'spuitbus' in prod_name.lower() or any(w in tool_name.lower() for w in ['spuitbus', 'aerosol', 'spray'])
        
        if prod_unit == 'ml':
            norm_vol = tot_vol / 1000.0
        elif prod_unit == 'g':
            norm_vol = tot_vol / 1000.0
        else:
            norm_vol = tot_vol
            
        if candidates and not is_aerosol_prod:
            for cand in candidates:
                cand_vol = cand.get('volume_val', 1.0)
                if norm_vol > 50 and cand_vol >= 10:
                    matched_item = cand
                    break
                elif norm_vol > 10 and cand_vol >= 4:
                    matched_item = cand
                    break
        elif candidates and is_aerosol_prod:
            spuitbussen = [c for c in candidates if 'spuitbus' in c.get('packaging', '').lower() or 'spuitbus' in c.get('description', '').lower()]
            if spuitbussen:
                matched_item = spuitbussen[0]

        packaging_desc = 'Standaard verpakking'
        unit_net_price = 0.0
        art_nr = '-'
        discount_pct = 0.0
        base_price = 0.0
        pack_val = 1.0
        pack_u = prod_unit
        tiers = []
        active_tier_min = 1
        item_category = 'Smeermiddelen'
        
        if matched_item:
            art_nr = matched_item.get('article_nr', '-')
            packaging_desc = f"{matched_item.get('content', '')} {matched_item.get('packaging', '')}".strip()
            item_category = matched_item.get('category', 'Smeermiddelen')
            discount_pct = float(matched_item.get('discount_pct', 0.0))
            pack_val = float(matched_item.get('volume_val') or 1.0)
            pack_u = matched_item.get('volume_unit') or prod_unit
            tiers = matched_item.get('tiers', [])
            
        # Check category or global discount
        cat_key = (item_category or '').strip().lower()
        matched_cat_discount = None
        if category_discounts and isinstance(category_discounts, dict):
            for c_name, c_val in category_discounts.items():
                if c_val is not None and str(c_val).strip() != '':
                    c_clean = c_name.strip().lower()
                    if c_clean == cat_key:
                        matched_cat_discount = float(c_val)
                        break
                    elif 'olie' in c_clean and 'olie' in cat_key:
                        if ('food' in c_clean) == ('food' in cat_key):
                            matched_cat_discount = float(c_val)
                            break
                    elif 'vet' in c_clean and 'vet' in cat_key:
                        if ('food' in c_clean) == ('food' in cat_key):
                            matched_cat_discount = float(c_val)
                            break
        if matched_cat_discount is not None:
            discount_pct = matched_cat_discount
        elif global_discount_pct is not None and float(global_discount_pct) > 0:
            discount_pct = float(global_discount_pct)

        packs_needed = 0
        if tot_vol > 0:
            if prod_unit == pack_u:
                packs_needed = math.ceil(tot_vol / pack_val) if pack_val > 0 else math.ceil(tot_vol)
            elif prod_unit == 'ml' and pack_u == 'L':
                packs_needed = math.ceil((tot_vol / 1000.0) / pack_val) if pack_val > 0 else math.ceil(tot_vol / 1000.0)
            elif prod_unit == 'L' and pack_u == 'ml':
                packs_needed = math.ceil((tot_vol * 1000.0) / pack_val) if pack_val > 0 else math.ceil(tot_vol)
            elif prod_unit == 'g' and pack_u == 'kg':
                packs_needed = math.ceil((tot_vol / 1000.0) / pack_val) if pack_val > 0 else math.ceil(tot_vol / 1000.0)
            elif prod_unit == 'g' and pack_u == 'L':
                packs_needed = math.ceil((tot_vol / 1000.0) / pack_val) if pack_val > 0 else math.ceil(tot_vol / 1000.0)
            else:
                packs_needed = math.ceil(tot_vol / pack_val) if pack_val > 0 else math.ceil(tot_vol)

        # Check for persistent manual units override
        is_manual_units = False
        if units_overrides and isinstance(units_overrides, dict):
            ov_u = units_overrides.get(combo_key) or units_overrides.get(prod_name)
            if ov_u is not None and int(ov_u) > 0:
                packs_needed = int(ov_u)
                is_manual_units = True

        # Check for persistent manual tier override
        is_manual_tier = False
        if tier_overrides and isinstance(tier_overrides, dict):
            ov_t = tier_overrides.get(combo_key) or tier_overrides.get(prod_name)
            if ov_t is not None and tiers:
                target_min = int(ov_t)
                matching_t = next((t for t in tiers if int(t.get('min_qty', 1)) == target_min), None)
                if matching_t:
                    tier_price = float(matching_t.get('unit_price', 0.0))
                    active_tier_min = target_min
                    base_price = tier_price
                    unit_net_price = round(tier_price * (1.0 - discount_pct / 100.0), 2)
                    is_manual_tier = True

        if not is_manual_tier:
            if tiers:
                tier_price, active_tier_min = get_tier_price(tiers, packs_needed)
                base_price = tier_price
                unit_net_price = round(tier_price * (1.0 - discount_pct / 100.0), 2)
            elif matched_item:
                base_price = float(matched_item.get('unit_price', 0.0))
                unit_net_price = round(base_price * (1.0 - discount_pct / 100.0), 2)
                tiers = [{'min_qty': 1, 'unit_price': base_price}]

        line_total = round(packs_needed * unit_net_price, 2)
        total_products_cost += line_total
        
        if prod_unit == 'ml':
            ann_disp = f"{pdata['annual_volume']:.0f} ml" if pdata['annual_volume'] < 1000 else f"{pdata['annual_volume']/1000.0:.2f} L"
            tot_disp = f"{tot_vol:.0f} ml" if tot_vol < 1000 else f"{tot_vol/1000.0:.2f} L"
        elif prod_unit == 'g':
            ann_disp = f"{pdata['annual_volume']:.0f} g" if pdata['annual_volume'] < 1000 else f"{pdata['annual_volume']/1000.0:.2f} kg"
            tot_disp = f"{tot_vol:.0f} g" if tot_vol < 1000 else f"{tot_vol/1000.0:.2f} kg"
        elif prod_unit == 'L':
            ann_disp = f"{pdata['annual_volume']:.2f} L"
            tot_disp = f"{tot_vol:.2f} L"
        else:
            ann_disp = f"{pdata['annual_volume']:.1f} {prod_unit}"
            tot_disp = f"{tot_vol:.1f} {prod_unit}"

        pack_options = []
        if candidates:
            for c in candidates:
                pack_options.append({
                    'article_nr': c.get('article_nr'),
                    'description': c.get('description'),
                    'packaging': f"{c.get('content', '')} {c.get('packaging', '')}".strip(),
                    'unit_price': c.get('unit_price', 0.0),
                    'net_price': c.get('net_price', 0.0),
                    'volume_val': c.get('volume_val', 1.0),
                    'volume_unit': c.get('volume_unit', prod_unit),
                    'tiers': c.get('tiers', [])
                })

        aggregated_list.append({
            'combo_key': combo_key,
            'product_name': prod_name,
            'tool': tool_name,
            'points_count': pdata['points_count'],
            'annual_volume_display': ann_disp,
            'contract_volume_display': tot_disp,
            'annual_volume_numeric': pdata['annual_volume'],
            'contract_volume_numeric': tot_vol,
            'volume_unit': prod_unit,
            'packaging': packaging_desc,
            'article_nr': art_nr,
            'category': item_category,
            'packages_needed': packs_needed,
            'base_unit_price': base_price,
            'discount_pct': discount_pct,
            'net_unit_price': unit_net_price,
            'line_total': line_total,
            'candidate_packagings': pack_options,
            'tiers': tiers,
            'active_tier_min': active_tier_min,
            'is_manual_units': is_manual_units,
            'is_manual_tier': is_manual_tier,
            'tasks_breakdown': pdata['tasks_summary'],
            'long_interval_points': pdata['long_interval_points']
        })

    # Prepare detected tools checklist with suggestions
    tool_checklist = []
    for tool_name, t_info in sorted(detected_tools_map.items()):
        suggestions = match_tool_to_pricelist(tool_name, pricelist_items)
        tool_checklist.append({
            'tool_name': tool_name,
            'point_count': t_info['point_count'],
            'sample_points': t_info['sample_points'],
            'status': 'pending',
            'suggested_items': [{
                'article_nr': s.get('article_nr'),
                'description': s.get('description'),
                'category': s.get('category'),
                'unit_price': s.get('unit_price', 0.0),
                'packaging': s.get('packaging', 'stuks'),
                'tiers': s.get('tiers', [])
            } for s in suggestions],
            'selected_article_nr': suggestions[0].get('article_nr') if suggestions else None,
            'recommended_qty': max(1, math.ceil(t_info['point_count'] / 50))
        })

    total_manual_cost = 0.0
    processed_manual = []
    if manual_items:
        for m in manual_items:
            qty = float(m.get('qty', 1.0))
            pr = float(m.get('unit_price', 0.0))
            disc = float(m.get('discount_pct', 0.0))
            tiers = m.get('tiers', [])
            
            if tiers:
                tier_pr, active_min = get_tier_price(tiers, qty)
                pr = tier_pr
                m['base_unit_price'] = pr
                m['active_tier_min'] = active_min
                
            net = round(pr * (1.0 - disc / 100.0), 2)
            is_annual = m.get('item_type') == 'Jaarlijks'
            tot = round(qty * net * (years if is_annual else 1.0), 2)
            total_manual_cost += tot
            
            m_copy = dict(m)
            m_copy['net_price'] = net
            m_copy['line_total'] = tot
            processed_manual.append(m_copy)

    total_annual_hours = recurring_execution_minutes_per_year / 60.0
    one_off_hours = one_off_execution_minutes / 60.0
    auto_days_per_year = math.ceil(total_annual_hours / 8.0) if total_annual_hours > 0 else 0
    auto_one_off_days = math.ceil(one_off_hours / 8.0) if one_off_hours > 0 else 0
    auto_days_year1 = auto_days_per_year + auto_one_off_days

    summary = {
        'contract_years': years,
        'total_points': len(points),
        'total_products_cost': round(total_products_cost, 2),
        'total_manual_cost': round(total_manual_cost, 2),
        'grand_total_phase1': round(total_products_cost + total_manual_cost, 2),
        'recurring_execution_minutes_per_year': round(recurring_execution_minutes_per_year, 1),
        'recurring_execution_hours_per_year': round(total_annual_hours, 1),
        'one_off_execution_minutes': round(one_off_execution_minutes, 1),
        'one_off_execution_hours': round(one_off_hours, 1),
        'auto_days_per_year': auto_days_per_year,
        'auto_one_off_days': auto_one_off_days,
        'auto_days_year1': auto_days_year1,
        'auto_oil_analyses_per_year': int(recurring_oil_analyses_per_year),
        'auto_one_off_analyses': int(one_off_oil_analyses),
        'detected_tools': tool_checklist
    }

    return {
        'contract_years': years,
        'summary': summary,
        'aggregated_products': aggregated_list,
        'manual_items': processed_manual,
        'long_interval_tasks': evaluated_long_tasks,
        'detected_tools': tool_checklist
    }

def evaluate_renewal_concept(points, elapsed_years=3, renewal_years=3, executed_tasks=None):
    """
    Evaluates long-interval tasks for a renewal contract concept.
    """
    elapsed_days = float(elapsed_years) * 365.0
    renewal_end_days = (float(elapsed_years) + float(renewal_years)) * 365.0
    executed_set = set(executed_tasks or [])
    
    renewal_tasks = []
    
    for pt in points:
        prod = pt['product_name']
        vol_std = pt['volume_numeric']
        std_unit = pt['volume_unit']
        count = pt['point_count']
        
        for t in pt['tasks']:
            int_days = t['interval_days']
            task_key = f"{pt['point_id']}_{t['task_name']}"
            
            is_long = int_days > elapsed_days
            due_in_renewal = elapsed_days < int_days <= renewal_end_days
            already_done = task_key in executed_set
            
            if is_long:
                action = "Opnemen in verlenging" if (due_in_renewal or not already_done) else "Reeds uitgevoerd in periode 1"
                renewal_tasks.append({
                    'task_key': task_key,
                    'point_id': pt['point_id'],
                    'machine': pt['machine'],
                    'maintenance_part': pt['maintenance_part'],
                    'product_name': prod,
                    'task_name': t['task_name'],
                    'interval_days': int_days,
                    'interval_years': round(int_days / 365.0, 1),
                    'volume_needed': round(vol_std * count, 2),
                    'volume_unit': std_unit,
                    'already_executed': already_done,
                    'due_in_renewal': due_in_renewal,
                    'recommended_action': action,
                    'include_in_concept': (due_in_renewal and not already_done)
                })

    return {
        'elapsed_years': elapsed_years,
        'renewal_years': renewal_years,
        'total_long_tasks': len(renewal_tasks),
        'due_in_renewal_count': len([t for t in renewal_tasks if t['due_in_renewal']]),
        'tasks': renewal_tasks
    }

def calculate_fase2_proposal(dossier):
    """
    Calculates Phase 2 contract proposal based on products, manual items, and work hours.
    Applies P&L-consistent indexation (cost and revenue) and transparent temporary surcharges.
    """
    years = max(1, int(dossier.get('settings', {}).get('duration_years', 3)))
    fase2 = dossier.get('fase2', {})
    wh = fase2.get('work_hours', {})
    
    # 1. Lubricants total
    products_cost = float(dossier.get('ilac_calculation', {}).get('summary', {}).get('total_products_cost', 0.0))
    
    # 2. Hardware & Manual items total (supports multiple material_groups)
    global_disc = dossier.get('settings', {}).get('global_discount_pct')
    cat_discs = dossier.get('settings', {}).get('category_discounts', {})

    if 'material_groups' in fase2 and fase2['material_groups']:
        manual_items = []
        for grp in fase2['material_groups']:
            manual_items.extend(grp.get('items', []))
    else:
        manual_items = dossier.get('ilac_calculation', {}).get('manual_items', [])
    hardware_cost = 0.0
    for m in manual_items:
        qty = float(m.get('qty', 1.0))
        unit_p = float(m.get('unit_price', 0.0))
        m_cat = (m.get('category') or '').strip().lower()
        m_disc = float(m.get('discount_pct', 0.0))
        if cat_discs and isinstance(cat_discs, dict):
            for c_k, c_v in cat_discs.items():
                if c_v is not None and str(c_v).strip() != '' and c_k.strip().lower() == m_cat:
                    m_disc = float(c_v)
                    break
        elif global_disc is not None and float(global_disc) > 0:
            m_disc = float(global_disc)
        m['discount_pct'] = m_disc
        net = round(unit_p * (1.0 - m_disc / 100.0), 2)
        m['net_price'] = net
        is_annual = m.get('item_type') == 'Jaarlijks'
        line_tot = round(qty * net * (years if is_annual else 1.0), 2)
        m['line_total'] = line_tot
        hardware_cost += line_tot
    hardware_cost = round(hardware_cost, 2)
    
    # 3. Work hours parameters
    hourly_rate_partner = float(wh.get('hourly_rate_partner', 63.0))
    surcharge_pct = float(wh.get('partner_surcharge_pct', 15.0))
    partner_billed_rate = round(hourly_rate_partner * (1.0 + surcharge_pct / 100.0), 2)
    wh['partner_billed_rate'] = partner_billed_rate
    
    summary = dossier.get('ilac_calculation', {}).get('summary', {})

    auto_days_yr = summary.get('auto_days_per_year')
    if auto_days_yr is not None and auto_days_yr > 0:
        days_per_year = float(auto_days_yr)
    else:
        days_per_year = float(wh.get('work_days_per_year', 65))

    auto_one_off = summary.get('auto_one_off_days', 0)
    auto_y1 = summary.get('auto_days_year1')
    if auto_y1 is not None and auto_y1 > 0:
        days_y1 = float(auto_y1)
    else:
        days_y1 = float(wh.get('work_days_year1', days_per_year + float(auto_one_off or 0)))

    one_off_days = int(auto_one_off) if auto_one_off is not None else max(0, int(days_y1 - days_per_year))

    auto_analyses = summary.get('auto_oil_analyses_per_year')
    if auto_analyses is not None:
        analyses_per_year = float(auto_analyses)
    else:
        analyses_per_year = float(wh.get('oil_analyses_per_year', 0))

    wh['work_days_year1'] = int(days_y1)
    wh['work_days_per_year'] = int(days_per_year)
    wh['one_off_days'] = int(one_off_days)
    wh['oil_analyses_per_year'] = int(analyses_per_year)

    total_days = days_y1 + (days_per_year * (years - 1)) if years > 1 else days_y1
    hours_per_day = float(wh.get('hours_per_day', 8.0))
    total_partner_hours = total_days * hours_per_day
    partner_hours_cost = round(total_partner_hours * partner_billed_rate, 2)
    
    km = float(wh.get('travel_km_per_day', 76.0))
    km_rate = float(wh.get('travel_rate_per_km', 1.75))
    travel_cost_per_day = round((km * km_rate) * (1.0 + surcharge_pct / 100.0), 2)
    wh['travel_cost_per_day'] = travel_cost_per_day
    total_travel_cost = round(total_days * travel_cost_per_day, 2)
    total_execution_cost = round(partner_hours_cost + total_travel_cost, 2)
    
    # 4. Management & Guidance (Interflon)
    interflon_rate = float(wh.get('interflon_hourly_rate', 110.0))
    pm_pct = float(wh.get('pm_pct', 15.0))
    sup_pct = float(wh.get('supervision_pct', 10.0))
    
    pm_hours = round(total_partner_hours * (pm_pct / 100.0), 1)
    sup_hours = round(total_partner_hours * (sup_pct / 100.0), 1)
    management_cost = round((pm_hours + sup_hours) * interflon_rate, 2)
    
    # 5. Analyses, Software, Training
    analysis_price = float(wh.get('analysis_unit_price', 220.0))
    analyses_cost = round(analyses_per_year * analysis_price * years, 2)
    
    software_annual = float(wh.get('software_license_annual', 1950.0))
    software_cost = round(software_annual * years, 2)
    
    training_cost = float(wh.get('training_budget', 880.0))
    
    total_services_cost = round(management_cost + analyses_cost + software_cost + training_cost, 2)
    
    # Baseline Grand contract total
    grand_contract_total = round(products_cost + hardware_cost + total_execution_cost + total_services_cost, 2)
    total_months = years * 12
    base_monthly_fee = round(grand_contract_total / total_months, 2) if total_months > 0 else 0.0

    # 6. Compound Indexation Calculation (P&L consistent on cost and revenue)
    # Every indexation entry compounds upon the latest new fee in chronological order
    raw_indexation = dossier.get('indexation', {})
    has_explicit_log = 'log' in raw_indexation
    indexation = dossier.setdefault('indexation', {'active': False, 'percentage': 0.0, 'type': 'general', 'log': []})
    log_entries = indexation.get('log', [])

    # Order of application is chronological (oldest to newest).
    # Since UI inserts newest at index 0, chronological order is reversed(log_entries).
    chronological_entries = list(reversed(log_entries)) if log_entries else []

    # Fallback only for legacy contracts where 'log' was never present
    if not has_explicit_log and not chronological_entries and indexation.get('active') and float(indexation.get('percentage', 0.0)) > 0:
        chronological_entries = [{
            'id': 'legacy_entry',
            'percentage': float(indexation.get('percentage', 0.0)),
            'type': indexation.get('type', 'general'),
            'active': True
        }]

    indexed_fee = base_monthly_fee
    running_grand_total = grand_contract_total
    running_products_cost = products_cost
    running_partner_hours_cost = partner_hours_cost
    running_total_execution_cost = total_execution_cost
    running_total_services_cost = total_services_cost

    active_count = 0
    for entry in chronological_entries:
        if not entry.get('active', True):
            continue
        e_pct = float(entry.get('percentage', 0.0))
        e_type = entry.get('type', 'general')
        if e_pct == 0:
            continue

        active_count += 1
        idx_factor = (1.0 + e_pct / 100.0)
        entry['old_monthly_fee'] = round(indexed_fee, 2)

        if e_type == 'general':
            indexed_fee = round(indexed_fee * idx_factor, 2)
            running_grand_total = round(running_grand_total * idx_factor, 2)
            running_products_cost = round(running_products_cost * idx_factor, 2)
            running_partner_hours_cost = round(running_partner_hours_cost * idx_factor, 2)
            running_total_execution_cost = round(running_total_execution_cost * idx_factor, 2)
            running_total_services_cost = round(running_total_services_cost * idx_factor, 2)
        elif e_type == 'products_only':
            extra_prod = round(running_products_cost * (e_pct / 100.0), 2)
            running_grand_total = round(running_grand_total + extra_prod, 2)
            running_products_cost = round(running_products_cost + extra_prod, 2)
            indexed_fee = round(running_grand_total / total_months, 2) if total_months > 0 else 0.0
        elif e_type == 'labor_only':
            extra_labor = round(running_partner_hours_cost * (e_pct / 100.0), 2)
            running_grand_total = round(running_grand_total + extra_labor, 2)
            running_partner_hours_cost = round(running_partner_hours_cost + extra_labor, 2)
            running_total_execution_cost = round(running_total_execution_cost + extra_labor, 2)
            indexed_fee = round(running_grand_total / total_months, 2) if total_months > 0 else 0.0
        elif e_type in ['categories', 'custom_categories']:
            cats = entry.get('categories', [])
            extra_sum = 0.0
            if any(c in cats for c in ['STO Partner Uitvoering', 'Arbeid', 'Uren', 'Partner uren']):
                extra_lab = round(running_partner_hours_cost * (e_pct / 100.0), 2)
                running_partner_hours_cost = round(running_partner_hours_cost + extra_lab, 2)
                running_total_execution_cost = round(running_total_execution_cost + extra_lab, 2)
                extra_sum += extra_lab
            if any(c in cats for c in ['PM & Regie', 'Interflon Diensten', 'Diensten', 'Management']):
                extra_serv = round(running_total_services_cost * (e_pct / 100.0), 2)
                running_total_services_cost = round(running_total_services_cost + extra_serv, 2)
                extra_sum += extra_serv
            prod_cats_known = ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten', 'Reinigers']
            matched_prod_cats = [c for c in cats if c in prod_cats_known]
            if matched_prod_cats:
                agg_prods = dossier.get('ilac_calculation', {}).get('aggregated_products', [])
                cat_prod_cost = sum(float(p.get('total_cost', 0.0)) for p in agg_prods if p.get('category') in matched_prod_cats)
                if cat_prod_cost > 0:
                    extra_p = round(cat_prod_cost * (e_pct / 100.0), 2)
                    running_products_cost = round(running_products_cost + extra_p, 2)
                    extra_sum += extra_p
                elif len(matched_prod_cats) == len(prod_cats_known) or 'Alle Producten' in cats:
                    extra_p = round(running_products_cost * (e_pct / 100.0), 2)
                    running_products_cost = round(running_products_cost + extra_p, 2)
                    extra_sum += extra_p
            hw_cats_known = ['Hardware & Tools', 'Hulpmaterialen', 'Automatic lubrication', 'Hardware', 'Tools']
            matched_hw = [c for c in cats if c in hw_cats_known]
            if matched_hw:
                cat_hw_cost = sum(float(m.get('qty', 1.0)) * float(m.get('net_price', 0.0)) * (years if m.get('item_type') == 'Jaarlijks' else 1.0)
                                  for m in manual_items if m.get('category') in matched_hw)
                if cat_hw_cost > 0:
                    extra_hw = round(cat_hw_cost * (e_pct / 100.0), 2)
                    extra_sum += extra_hw
            running_grand_total = round(running_grand_total + extra_sum, 2)
            indexed_fee = round(running_grand_total / total_months, 2) if total_months > 0 else 0.0

        entry['new_monthly_fee'] = round(indexed_fee, 2)

    grand_contract_total = running_grand_total
    products_cost = running_products_cost
    partner_hours_cost = running_partner_hours_cost
    total_execution_cost = running_total_execution_cost
    total_services_cost = running_total_services_cost

    index_active = active_count > 0 or bool(indexation.get('active', False))
    index_pct = float(indexation.get('percentage', 0.0))
    index_type = indexation.get('type', 'general')

    # 7. Temporary Surcharge (e.g. Hormuz oil surcharge)
    surcharge = dossier.get('temporary_surcharge', {})
    surch_active = bool(surcharge.get('active', False))
    surch_pct = float(surcharge.get('percentage', 5.0)) if surch_active else 0.0
    surch_name = surcharge.get('name', 'Grondstoffentoeslag Olie (Straat van Hormuz)')
    surch_cats = surcharge.get('categories', ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten'])

    surcharge_total = 0.0
    surcharge_monthly = 0.0

    if surch_active and surch_pct > 0:
        agg_prods = dossier.get('ilac_calculation', {}).get('aggregated_products', [])
        applicable_prod_cost = sum(float(p.get('line_total', 0.0)) for p in agg_prods if p.get('category') in surch_cats)
        if applicable_prod_cost == 0:
            applicable_prod_cost = products_cost # fallback
        surcharge_total = round(applicable_prod_cost * (surch_pct / 100.0), 2)
        surcharge_monthly = round(surcharge_total / total_months, 2) if total_months > 0 else 0.0

    final_monthly_fee = round(indexed_fee + surcharge_monthly, 2)

    proposal_summary = {
        'contract_years': years,
        'contract_months': total_months,
        'products_total': products_cost,
        'products_annual': round(products_cost / years, 2),
        'hardware_total': hardware_cost,
        'hardware_annual': round(hardware_cost / years, 2),
        'work_days_year1': int(days_y1),
        'work_days_per_year': int(days_per_year),
        'one_off_days': int(one_off_days),
        'total_work_days': int(total_days),
        'partner_hours': total_partner_hours,
        'partner_hours_cost': partner_hours_cost,
        'travel_days': total_days,
        'travel_total_cost': total_travel_cost,
        'total_execution_cost': total_execution_cost,
        'pm_hours': pm_hours,
        'sup_hours': sup_hours,
        'management_cost': management_cost,
        'analyses_cost': analyses_cost,
        'analyses_per_year': int(analyses_per_year),
        'software_cost': software_cost,
        'training_cost': training_cost,
        'total_services_cost': total_services_cost,
        'grand_contract_total': grand_contract_total,
        # Fee structure
        'base_monthly_fee': indexed_fee,
        'surcharge_monthly': surcharge_monthly,
        'surcharge_total': surcharge_total,
        'total_monthly_fee': final_monthly_fee,
        'monthly_fee': final_monthly_fee, # backward compat
        'surcharge_active': surch_active,
        'surcharge_name': surch_name,
        'surcharge_percentage': surch_pct,
        'indexation_active': index_active,
        'indexation_percentage': index_pct,
        'indexation_type': index_type
    }
    
    fase2['proposal_summary'] = proposal_summary
    dossier['settings']['fee_per_month'] = final_monthly_fee
    return proposal_summary
