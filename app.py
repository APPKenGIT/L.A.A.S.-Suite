import os
import json
import math
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from backend.dossier_store import DossierStore, CORRECT_PASSWORD
from backend.pricelist_engine import get_tier_price, parse_excel_pricelist, apply_discount, add_custom_article
from backend.ilac_engine import parse_ilac_excel, calculate_ilac_requirements, evaluate_renewal_concept, calculate_fase2_proposal

import sys
import webbrowser
import threading

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    template_folder = os.path.join(sys._MEIPASS, 'templates') if hasattr(sys, '_MEIPASS') else os.path.join(BASE_DIR, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static') if hasattr(sys, '_MEIPASS') else os.path.join(BASE_DIR, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB max
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

store = DossierStore()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/verify_password', methods=['POST'])
def verify_password():
    data = request.json or {}
    password = data.get('password', '')
    if store.verify_password(password):
        return jsonify({"status": "success", "verified": True})
    return jsonify({"status": "error", "message": "Onjuist wachtwoord"}), 401

# =============================================================================
# HIERARCHY & ARCHIVE ROUTES
# =============================================================================
@app.route('/api/hierarchy', methods=['GET'])
def get_hierarchy():
    return jsonify(store.list_hierarchy())

@app.route('/api/archive', methods=['GET'])
def get_archive():
    return jsonify(store.list_archive())

# =============================================================================
# CUSTOMER LOGO ROUTES
# =============================================================================
@app.route('/api/customer/<customer>/logo', methods=['GET'])
def get_customer_logo(customer):
    path = store.get_customer_logo_path(customer)
    if not path or not os.path.exists(path):
        return jsonify({"error": "Geen logo gevonden"}), 404
    return send_file(path)

@app.route('/api/customer/<customer>/logo', methods=['POST'])
def upload_customer_logo(customer):
    if 'file' not in request.files:
        return jsonify({"error": "Geen bestand ontvangen"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Geen bestand geselecteerd"}), 400
    try:
        logo_url = store.save_customer_logo(customer, file)
        return jsonify({"status": "success", "logo_url": logo_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/customer/create', methods=['POST'])
def create_customer():
    data = request.json or {}
    customer = data.get('customer')
    if not customer:
        return jsonify({"error": "Klantnaam is verplicht"}), 400
    res = store.create_customer(customer)
    return jsonify({"status": "success", "result": res})

@app.route('/api/department/create', methods=['POST'])
def create_department():
    data = request.json or {}
    customer = data.get('customer')
    department = data.get('department')
    if not customer or not department:
        return jsonify({"error": "Klantnaam en afdelingsnaam zijn verplicht"}), 400
    res = store.create_department(customer, department)
    return jsonify({"status": "success", "result": res})

@app.route('/api/contract/create', methods=['POST'])
def create_contract():
    data = request.json or {}
    customer = data.get('customer')
    department = data.get('department')
    contract_name = data.get('contract_name')
    if not customer or not department or not contract_name:
        return jsonify({"error": "Klantnaam, afdeling en contractnaam zijn verplicht"}), 400
    dossier = store.create_contract(customer, department, contract_name)
    return jsonify({"status": "success", "dossier": dossier})

@app.route('/api/archive/item', methods=['POST'])
def archive_item():
    data = request.json or {}
    level = data.get('level')
    customer = data.get('customer')
    department = data.get('department')
    contract_name = data.get('contract_name')
    try:
        res = store.archive_item(level, customer, department, contract_name)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/restore/item', methods=['POST'])
def restore_item():
    data = request.json or {}
    level = data.get('level')
    customer = data.get('customer')
    department = data.get('department')
    contract_name = data.get('contract_name')
    try:
        res = store.restore_item(level, customer, department, contract_name)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/archive/permanent_delete', methods=['POST'])
def delete_permanently():
    data = request.json or {}
    level = data.get('level')
    customer = data.get('customer')
    department = data.get('department')
    contract_name = data.get('contract_name')
    try:
        res = store.delete_permanently(level, customer, department, contract_name)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/hierarchy/rename', methods=['POST'])
def rename_hierarchy_item():
    data = request.json or {}
    level = data.get('level')
    customer = data.get('customer')
    department = data.get('department')
    contract_name = data.get('contract_name')
    new_name = data.get('new_name')
    try:
        res = store.rename_item(level, customer, department, contract_name, new_name)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# =============================================================================
# DOSSIER GET & SAVE ROUTES
# =============================================================================
@app.route('/api/dossier/<klant>/<afdeling>', methods=['GET'])
@app.route('/api/dossier/<klant>/<afdeling>/<contract_name>', methods=['GET'])
def get_dossier(klant, afdeling, contract_name=None):
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": f"Contract niet gevonden voor {klant} / {afdeling}"}), 404

    # Auto-sync naar line_total_v2 & single_pass_hours voor bestaande dossiers
    ilac_calc = dossier.get('ilac_calculation') or {}
    pts = ilac_calc.get('points') or []
    cur_summary = ilac_calc.get('summary') or {}
    agg_prods = ilac_calc.get('aggregated_products') or []
    needs_time_sync = bool(pts) and (
        cur_summary.get('time_calc_mode') != 'line_total_v2'
        or (agg_prods and 'single_pass_hours' not in agg_prods[0])
    )
    if needs_time_sync:
        settings = dossier.get('settings') or {}
        years = int(settings.get('duration_years', 3))
        g_factor = float(settings.get('gram_per_pompslag', 1.5))
        ml_factor = float(settings.get('ml_per_second', 1.0))
        pl_items = (dossier.get('price_list') or {}).get('items') or store.get_global_pricelist().get('items', [])
        manual_items = ilac_calc.get('manual_items') or []
        calc_res = calculate_ilac_requirements(
            pts,
            contract_years=years,
            pricelist_items=pl_items,
            manual_items=manual_items,
            gram_per_pompslag=g_factor,
            ml_per_second=ml_factor,
            packaging_overrides=dossier.get('packaging_overrides', {}),
            manual_product_overrides=dossier.get('manual_product_overrides', {}),
            units_overrides=dossier.get('units_overrides', {}),
            tier_overrides=dossier.get('tier_overrides', {}),
            global_discount_pct=settings.get('global_discount_pct'),
            category_discounts=settings.get('category_discounts', {})
        )
        dossier['ilac_calculation']['summary'] = calc_res['summary']
        dossier['ilac_calculation']['aggregated_products'] = calc_res['aggregated_products']
        is_locked_active = bool((dossier.get('tracking') or {}).get('is_active'))
        locked_fee = settings.get('fee_per_month')
        calculate_fase2_proposal(dossier)
        if is_locked_active and locked_fee:
            dossier['settings']['fee_per_month'] = locked_fee
        con_name = contract_name or settings.get('contract_name') or dossier.get('contract_name', 'Standaard Contract')
        store.save_dossier(klant, afdeling, con_name, dossier)

    return jsonify(dossier)

@app.route('/api/dossier/<klant>/<afdeling>', methods=['POST'])
@app.route('/api/dossier/<klant>/<afdeling>/<contract_name>', methods=['POST'])
def save_dossier(klant, afdeling, contract_name=None):
    data = request.json
    con_name = contract_name or data.get('contract_name') or data.get('settings', {}).get('contract_name', 'Standaard Contract')
    updated = store.save_dossier(klant, afdeling, con_name, data)
    return jsonify({"status": "success", "dossier": updated})

# =============================================================================
# FASE 1: ILAC EXCEL UPLOAD & CALCULATION
# =============================================================================
@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/ilac/upload', methods=['POST'])
def upload_ilac(klant, afdeling, contract_name):
    if 'file' not in request.files:
        return jsonify({"error": "Geen bestand ontvangen"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Geen bestand geselecteerd"}), 400

    filename = secure_filename(file.filename)
    con_dir = store.get_contract_dir(klant, afdeling, contract_name)
    docs_dir = os.path.join(con_dir, "documenten")
    os.makedirs(docs_dir, exist_ok=True)
    target_path = os.path.join(docs_dir, filename)
    file.save(target_path)

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract dossier niet gevonden"}), 404

    g_factor = float(dossier.get('settings', {}).get('gram_per_pompslag', 1.5))
    ml_factor = float(dossier.get('settings', {}).get('ml_per_second', 1.0))

    try:
        parsed_ilac = parse_ilac_excel(target_path, gram_per_pompslag=g_factor, ml_per_second=ml_factor)
    except Exception as e:
        return jsonify({"error": f"Fout bij verwerken ILAC bestand: {str(e)}"}), 400

    years = int(dossier.get('settings', {}).get('duration_years', 3))
    pricelist_items = dossier.get('price_list', {}).get('items', [])
    manual_items = dossier.get('ilac_calculation', {}).get('manual_items', [])

    calc_res = calculate_ilac_requirements(
        parsed_ilac['points'],
        contract_years=years,
        pricelist_items=pricelist_items,
        manual_items=manual_items,
        gram_per_pompslag=g_factor,
        ml_per_second=ml_factor,
        packaging_overrides=dossier.get('packaging_overrides', {}),
            manual_product_overrides=dossier.get('manual_product_overrides', {})
    )

    dossier['ilac_calculation'] = {
        'uploaded_at': os.path.getmtime(target_path),
        'filename': filename,
        'contract_years': years,
        'summary': calc_res['summary'],
        'aggregated_products': calc_res['aggregated_products'],
        'points': parsed_ilac['points'],
        'manual_items': manual_items,
        'task_categories': parsed_ilac['task_categories']
    }

    dossier['settings']['total_months'] = years * 12
    calculate_fase2_proposal(dossier)

    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "message": f"ILAC-audit '{filename}' succesvol geanalyseerd ({parsed_ilac['total_points']} punten)!", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/ilac/clear', methods=['POST'])
def clear_ilac(klant, afdeling, contract_name):
    try:
        updated = store.clear_calculation(klant, afdeling, contract_name)
        calculate_fase2_proposal(updated)
        store.save_dossier(klant, afdeling, contract_name, updated)
        return jsonify({"status": "success", "message": "Calculatie succesvol leeggemaakt", "dossier": updated})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/ilac/recalculate', methods=['POST'])
def recalculate_ilac(klant, afdeling, contract_name):
    data = request.json or {}
    years = int(data.get('contract_years', 3))
    
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    points = dossier.get('ilac_calculation', {}).get('points', [])
    pricelist_items = dossier.get('price_list', {}).get('items', [])
    manual_items = data.get('manual_items', dossier.get('ilac_calculation', {}).get('manual_items', []))

    if points:
        g_factor = float(dossier.get('settings', {}).get('gram_per_pompslag', 1.5))
        ml_factor = float(dossier.get('settings', {}).get('ml_per_second', 1.0))
        calc_res = calculate_ilac_requirements(
            points,
            contract_years=years,
            pricelist_items=pricelist_items,
            manual_items=manual_items,
            gram_per_pompslag=g_factor,
            ml_per_second=ml_factor,
            packaging_overrides=dossier.get('packaging_overrides', {}),
            manual_product_overrides=dossier.get('manual_product_overrides', {})
        )
        dossier['ilac_calculation']['contract_years'] = years
        dossier['ilac_calculation']['summary'] = calc_res['summary']
        dossier['ilac_calculation']['aggregated_products'] = calc_res['aggregated_products']
        dossier['ilac_calculation']['manual_items'] = calc_res['manual_items']
    else:
        dossier['ilac_calculation']['contract_years'] = years
        dossier['ilac_calculation']['manual_items'] = manual_items

    dossier['settings']['duration_years'] = years
    dossier['settings']['total_months'] = years * 12
    calculate_fase2_proposal(dossier)

    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/product/units_override', methods=['POST'])
def override_product_units(klant, afdeling, contract_name):
    data = request.json or {}
    combo_key = data.get('combo_key')
    prod_name = data.get('product_name')
    tool_name = data.get('tool')
    new_units = data.get('units')

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    overrides = dossier.setdefault('units_overrides', {})
    key = combo_key or (f"{prod_name}___{tool_name}" if tool_name else prod_name)
    if new_units is None or int(new_units) <= 0:
        overrides.pop(key, None)
        if prod_name:
            overrides.pop(prod_name, None)
    else:
        overrides[key] = int(new_units)
        if prod_name:
            overrides[prod_name] = int(new_units)

    # Recalculate
    points = dossier.get('ilac_calculation', {}).get('points', [])
    if points:
        years = int(dossier.get('settings', {}).get('duration_years', 3))
        g_factor = float(dossier.get('settings', {}).get('gram_per_pompslag', 1.5))
        ml_factor = float(dossier.get('settings', {}).get('ml_per_second', 1.0))
        pl_items = dossier.get('price_list', {}).get('items') or store.get_global_pricelist().get('items', [])
        calc_res = calculate_ilac_requirements(
            points,
            contract_years=years,
            pricelist_items=pl_items,
            manual_items=dossier.get('ilac_calculation', {}).get('manual_items', []),
            gram_per_pompslag=g_factor,
            ml_per_second=ml_factor,
            packaging_overrides=dossier.get('packaging_overrides', {}),
            manual_product_overrides=dossier.get('manual_product_overrides', {}),
            units_overrides=dossier.get('units_overrides', {}),
            tier_overrides=dossier.get('tier_overrides', {}),
            global_discount_pct=dossier.get('settings', {}).get('global_discount_pct'),
            category_discounts=dossier.get('settings', {}).get('category_discounts', {})
        )
        dossier['ilac_calculation']['summary'] = calc_res['summary']
        dossier['ilac_calculation']['aggregated_products'] = calc_res['aggregated_products']

    calculate_fase2_proposal(dossier)
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/product/tier_override', methods=['POST'])
def override_product_tier(klant, afdeling, contract_name):
    data = request.json or {}
    combo_key = data.get('combo_key')
    prod_name = data.get('product_name')
    tool_name = data.get('tool')
    tier_min = data.get('tier_min')
    auto_reset = bool(data.get('auto', False))

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    overrides = dossier.setdefault('tier_overrides', {})
    key = combo_key or (f"{prod_name}___{tool_name}" if tool_name else prod_name)
    if auto_reset or tier_min is None:
        overrides.pop(key, None)
        if prod_name:
            overrides.pop(prod_name, None)
    else:
        overrides[key] = int(tier_min)
        if prod_name:
            overrides[prod_name] = int(tier_min)

    # Recalculate
    points = dossier.get('ilac_calculation', {}).get('points', [])
    if points:
        years = int(dossier.get('settings', {}).get('duration_years', 3))
        g_factor = float(dossier.get('settings', {}).get('gram_per_pompslag', 1.5))
        ml_factor = float(dossier.get('settings', {}).get('ml_per_second', 1.0))
        pl_items = dossier.get('price_list', {}).get('items') or store.get_global_pricelist().get('items', [])
        calc_res = calculate_ilac_requirements(
            points,
            contract_years=years,
            pricelist_items=pl_items,
            manual_items=dossier.get('ilac_calculation', {}).get('manual_items', []),
            gram_per_pompslag=g_factor,
            ml_per_second=ml_factor,
            packaging_overrides=dossier.get('packaging_overrides', {}),
            manual_product_overrides=dossier.get('manual_product_overrides', {}),
            units_overrides=dossier.get('units_overrides', {}),
            tier_overrides=dossier.get('tier_overrides', {}),
            global_discount_pct=dossier.get('settings', {}).get('global_discount_pct'),
            category_discounts=dossier.get('settings', {}).get('category_discounts', {})
        )
        dossier['ilac_calculation']['summary'] = calc_res['summary']
        dossier['ilac_calculation']['aggregated_products'] = calc_res['aggregated_products']

    calculate_fase2_proposal(dossier)
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "dossier": dossier})


@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/product/packaging_override', methods=['POST'])
def override_product_packaging(klant, afdeling, contract_name):
    data = request.json or {}
    combo_key = data.get('combo_key')
    prod_name = data.get('product_name')
    tool_name = data.get('tool')
    selected_art_nr = str(data.get('article_nr', ''))

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    products = dossier.get('ilac_calculation', {}).get('aggregated_products', [])
    pl_items = dossier.get('price_list', {}).get('items') or store.get_global_pricelist().get('items', [])
    
    matched_pl = next((it for it in pl_items if str(it.get('article_nr')) == selected_art_nr), None)
    if not matched_pl:
        return jsonify({"error": f"Artikel '{selected_art_nr}' niet gevonden in de actieve prijslijst"}), 404

    overrides = dossier.setdefault('packaging_overrides', {})
    key = combo_key or (f"{prod_name}___{tool_name}" if tool_name else prod_name)
    overrides[key] = selected_art_nr
    if prod_name:
        overrides[prod_name] = selected_art_nr

    for p in products:
        is_match = False
        if combo_key and p.get('combo_key') == combo_key:
            is_match = True
        elif p.get('product_name') == prod_name:
            if not tool_name or p.get('tool') == tool_name:
                is_match = True

        if is_match:
            p['article_nr'] = matched_pl.get('article_nr')
            p['packaging'] = f"{matched_pl.get('content', '')} {matched_pl.get('packaging', '')}".strip()
            p['category'] = matched_pl.get('category', p.get('category', 'Smeermiddelen'))
            discount_pct = float(p.get('discount_pct', matched_pl.get('discount_pct', 0.0)))
            p['discount_pct'] = discount_pct
            
            pack_val = float(matched_pl.get('volume_val', 1.0))
            pack_u = matched_pl.get('volume_unit', p.get('volume_unit'))
            p['pack_volume'] = pack_val
            p['pack_unit'] = pack_u
            
            tot_vol = float(p.get('contract_volume_numeric') or p.get('total_contract_volume', 0.0))
            if tot_vol == 0:
                ann_v = float(p.get('annual_volume_numeric', 0.0))
                yrs = int(dossier.get('settings', {}).get('duration_years', 3))
                tot_vol = ann_v * yrs
                p['contract_volume_numeric'] = tot_vol
            prod_u = p.get('volume_unit')
            
            if prod_u == pack_u:
                packs = math.ceil(tot_vol / pack_val) if pack_val > 0 else math.ceil(tot_vol)
            elif prod_u == 'ml' and pack_u == 'L':
                packs = math.ceil((tot_vol / 1000.0) / pack_val) if pack_val > 0 else math.ceil(tot_vol / 1000.0)
            elif prod_u == 'L' and pack_u == 'ml':
                packs = math.ceil((tot_vol * 1000.0) / pack_val) if pack_val > 0 else math.ceil(tot_vol)
            elif prod_u == 'g' and pack_u in ['kg', 'L']:
                packs = math.ceil((tot_vol / 1000.0) / pack_val) if pack_val > 0 else math.ceil(tot_vol / 1000.0)
            else:
                packs = math.ceil(tot_vol / pack_val) if pack_val > 0 else math.ceil(tot_vol)
                
            tiers = matched_pl.get('tiers', [])
            p['tiers'] = tiers
            if tiers:
                tier_price, active_min = get_tier_price(tiers, packs)
                p['base_unit_price'] = tier_price
                p['active_tier_min'] = active_min
                p['net_unit_price'] = round(tier_price * (1.0 - discount_pct / 100.0), 2)
            else:
                base_pr = float(matched_pl.get('unit_price', 0.0))
                p['base_unit_price'] = base_pr
                p['active_tier_min'] = 1
                p['net_unit_price'] = round(base_pr * (1.0 - discount_pct / 100.0), 2)

            p['packages_needed'] = packs
            p['line_total'] = round(packs * p['net_unit_price'], 2)

    # Recalculate summary total products cost
    tot_prod_cost = round(sum(p.get('line_total', 0.0) for p in products), 2)
    dossier['ilac_calculation']['summary']['total_products_cost'] = tot_prod_cost
    calculate_fase2_proposal(dossier)

    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "dossier": dossier})


@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/product/manual_override', methods=['POST'])
def manual_product_override(klant, afdeling, contract_name):
    data = request.json or {}
    combo_key = data.get('combo_key')
    prod_name = data.get('product_name')
    tool_name = data.get('tool')
    article_nr = str(data.get('article_nr', '')).strip()
    packaging = str(data.get('packaging', '')).strip()
    try:
        unit_price = float(data.get('unit_price', 0.0))
    except (ValueError, TypeError):
        unit_price = 0.0
    try:
        discount_pct = float(data.get('discount_pct', 0.0))
    except (ValueError, TypeError):
        discount_pct = 0.0
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404
    m_overrides = dossier.setdefault('manual_product_overrides', {})
    key = combo_key or (f"{prod_name}___{tool_name}" if tool_name else prod_name)
    m_overrides[key] = {
        'article_nr': article_nr,
        'packaging': packaging,
        'unit_price': unit_price,
        'discount_pct': discount_pct
    }
    if prod_name:
        m_overrides[prod_name] = m_overrides[key]
    points = dossier.get('ilac_points') or dossier.get('ilac_calculation', {}).get('points', [])
    years = dossier.get('settings', {}).get('duration_years', 3)
    pl_items = dossier.get('price_list', {}).get('items') or store.get_global_pricelist().get('items', [])
    manual_items = dossier.get('fase2', {}).get('manual_items', [])
    g_factor = float(dossier.get('settings', {}).get('gram_per_pompslag', 1.5))
    ml_factor = float(dossier.get('settings', {}).get('ml_per_second', 1.0))
    calc_res = calculate_ilac_requirements(
        points,
        contract_years=years,
        pricelist_items=pl_items,
        manual_items=manual_items,
        gram_per_pompslag=g_factor,
        ml_per_second=ml_factor,
        packaging_overrides=dossier.get('packaging_overrides', {}),
        units_overrides=dossier.get('units_overrides', {}),
        tier_overrides=dossier.get('tier_overrides', {}),
        global_discount_pct=dossier.get('settings', {}).get('global_discount_pct'),
        category_discounts=dossier.get('settings', {}).get('category_discounts'),
        manual_product_overrides=m_overrides
    )
    dossier.setdefault('ilac_calculation', {})
    dossier['ilac_calculation']['summary'] = calc_res['summary']
    dossier['ilac_calculation']['aggregated_products'] = calc_res['aggregated_products']
    calculate_fase2_proposal(dossier)
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"success": True, "dossier": dossier})
@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/manual-items/add', methods=['POST'])
def add_manual_item_dashed(klant, afdeling, contract_name):
    data = request.json or {}
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    items = dossier.get('ilac_calculation', {}).get('manual_items', [])
    years = int(dossier.get('settings', {}).get('duration_years', 3))
    
    qty = max(1.0, float(data.get('qty', 1.0)))
    unit_price = float(data.get('unit_price', 0.0))
    discount_pct = max(0.0, min(100.0, float(data.get('discount_pct', 0.0))))
    net_price = round(unit_price * (1.0 - discount_pct / 100.0), 2)
    item_type = data.get('item_type', 'Eenmalig')
    multiplier = years if item_type == 'Jaarlijks' else 1.0
    line_total = round(qty * net_price * multiplier, 2)
    
    new_item = {
        'id': f"M_{int(datetime.now().timestamp() * 1000)}",
        'article_nr': str(data.get('article_nr', '-')),
        'category': data.get('category', 'Hardware & Tools'),
        'description': data.get('description', 'Handmatig artikel'),
        'unit': data.get('unit', 'stuks'),
        'qty': qty,
        'unit_price': unit_price,
        'discount_pct': discount_pct,
        'net_price': net_price,
        'item_type': item_type,
        'line_total': line_total,
        'notes': data.get('notes', '')
    }
    
    items.append(new_item)
    dossier['ilac_calculation']['manual_items'] = items
    dossier['ilac_calculation']['summary']['total_manual_cost'] = round(sum(it.get('line_total', 0.0) for it in items), 2)
    calculate_fase2_proposal(dossier)
    
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/manual-items/<item_id>', methods=['DELETE'])
def delete_manual_item_dashed(klant, afdeling, contract_name, item_id):
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    items = dossier.get('ilac_calculation', {}).get('manual_items', [])
    dossier['ilac_calculation']['manual_items'] = [it for it in items if str(it.get('id')) != str(item_id)]
    dossier['ilac_calculation']['summary']['total_manual_cost'] = round(sum(it.get('line_total', 0.0) for it in dossier['ilac_calculation']['manual_items']), 2)
    calculate_fase2_proposal(dossier)
    
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/fase2/save', methods=['POST'])
@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/settings/save', methods=['POST'])
def save_settings(klant, afdeling, contract_name):
    data = request.json or {}
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    # 1. Update work_hours parameters if provided
    wh_data = data.get('work_hours')
    if wh_data:
        if 'fase2' not in dossier:
            dossier['fase2'] = {}
        if 'work_hours' not in dossier['fase2']:
            dossier['fase2']['work_hours'] = {}
        dossier['fase2']['work_hours'].update(wh_data)

    # 1b. Update doorsmeren if provided
    doorsmeren_data = data.get('doorsmeren')
    if doorsmeren_data is not None:
        if 'fase2' not in dossier:
            dossier['fase2'] = {}
        dossier['fase2']['doorsmeren'] = doorsmeren_data

    # 2. Update contract / calculation parameters if provided
    settings_changed = False
    if 'duration_years' in data:
        new_years = max(1, int(data['duration_years']))
        if new_years != dossier.get('settings', {}).get('duration_years'):
            dossier['settings']['duration_years'] = new_years
            dossier['ilac_calculation']['contract_years'] = new_years
            dossier['settings']['total_months'] = new_years * 12
            settings_changed = True

    if 'gram_per_pompslag' in data:
        new_g = float(data['gram_per_pompslag'])
        if new_g != dossier.get('settings', {}).get('gram_per_pompslag'):
            dossier['settings']['gram_per_pompslag'] = new_g
            settings_changed = True

    if 'ml_per_second' in data:
        new_ml = float(data['ml_per_second'])
        if new_ml != dossier.get('settings', {}).get('ml_per_second'):
            dossier['settings']['ml_per_second'] = new_ml
            settings_changed = True

    if 'global_discount_pct' in data:
        new_disc = float(data.get('global_discount_pct', 0.0) or 0.0)
        if new_disc != dossier.get('settings', {}).get('global_discount_pct'):
            dossier.setdefault('settings', {})['global_discount_pct'] = new_disc
            settings_changed = True

    if 'category_discounts' in data and isinstance(data['category_discounts'], dict):
        dossier.setdefault('settings', {})['category_discounts'] = data['category_discounts']
        settings_changed = True

    # 3. Recalculate ILAC if parameters changed and points exist
    points = dossier.get('ilac_calculation', {}).get('points', [])
    if points and (settings_changed or data.get('force_recalc')):
        years = int(dossier.get('settings', {}).get('duration_years', 3))
        g_factor = float(dossier.get('settings', {}).get('gram_per_pompslag', 1.5))
        ml_factor = float(dossier.get('settings', {}).get('ml_per_second', 1.0))
        pl_items = dossier.get('price_list', {}).get('items', [])
        manual_items = dossier.get('ilac_calculation', {}).get('manual_items', [])
        calc_res = calculate_ilac_requirements(
            points,
            contract_years=years,
            pricelist_items=pl_items,
            manual_items=manual_items,
            gram_per_pompslag=g_factor,
            ml_per_second=ml_factor,
            packaging_overrides=dossier.get('packaging_overrides', {}),
            manual_product_overrides=dossier.get('manual_product_overrides', {}),
            units_overrides=dossier.get('units_overrides', {}),
            tier_overrides=dossier.get('tier_overrides', {}),
            global_discount_pct=dossier.get('settings', {}).get('global_discount_pct'),
            category_discounts=dossier.get('settings', {}).get('category_discounts', {})
        )
        dossier['ilac_calculation']['summary'] = calc_res['summary']
        dossier['ilac_calculation']['aggregated_products'] = calc_res['aggregated_products']

    # 4. Compute Fase 2 proposal
    proposal = calculate_fase2_proposal(dossier)
    if 'fase2' not in dossier:
        dossier['fase2'] = {}
    dossier['fase2']['proposal_summary'] = proposal
    dossier['settings']['fee_per_month'] = proposal.get('monthly_fee', 0.0)

    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "message": "Instellingen succesvol bijgewerkt", "dossier": dossier})

# =============================================================================
# FASE 1: PRICELIST UPLOAD & DISCOUNTS
# =============================================================================
@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/pricelist/upload', methods=['POST'])
def upload_pricelist(klant, afdeling, contract_name):
    if 'file' not in request.files:
        return jsonify({"error": "Geen bestand ontvangen"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Geen bestand geselecteerd"}), 400

    filename = secure_filename(file.filename)
    con_dir = store.get_contract_dir(klant, afdeling, contract_name)
    docs_dir = os.path.join(con_dir, "documenten")
    os.makedirs(docs_dir, exist_ok=True)
    target_path = os.path.join(docs_dir, filename)
    file.save(target_path)

    try:
        pl_data = parse_excel_pricelist(target_path)
    except Exception as e:
        return jsonify({"error": f"Fout bij verwerken prijslijst: {str(e)}"}), 400

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract dossier niet gevonden"}), 404

    if dossier.get('prices_frozen'):
        # Store as updated document reference, but keep frozen calculation intact
        dossier['latest_uploaded_pricelist'] = filename
        store.save_dossier(klant, afdeling, contract_name, dossier)
        return jsonify({
            "status": "warning",
            "message": f"Prijslijst '{filename}' opgeslagen. De actieve calculatie is echter bevroren (fixed prices) en blijft ongewijzigd.",
            "dossier": dossier
        })

    dossier['price_list'] = pl_data

    # Recalculate ILAC requirements if points exist
    points = dossier.get('ilac_calculation', {}).get('points', [])
    if points:
        years = int(dossier.get('settings', {}).get('duration_years', 3))
        manual_items = dossier.get('ilac_calculation', {}).get('manual_items', [])
        calc_res = calculate_ilac_requirements(points, contract_years=years, pricelist_items=pl_data['items'], manual_items=manual_items, packaging_overrides=dossier.get('packaging_overrides', {}),
            manual_product_overrides=dossier.get('manual_product_overrides', {}))
        dossier['ilac_calculation']['summary'] = calc_res['summary']
        dossier['ilac_calculation']['aggregated_products'] = calc_res['aggregated_products']
        dossier['settings']['fee_per_month'] = calc_res['summary']['calculated_monthly_fee']

    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "message": f"Prijslijst '{filename}' ({pl_data['total_items']} artikelen) succesvol ingeladen!", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/pricelist/item_discount', methods=['POST'])
def update_item_discount(klant, afdeling, contract_name):
    data = request.json or {}
    art_nr = str(data.get('article_nr', ''))
    discount_pct = float(data.get('discount_pct', 0.0))

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    items = dossier.get('price_list', {}).get('items', [])
    updated = False
    for it in items:
        if it.get('article_nr') == art_nr:
            apply_discount(it, discount_pct)
            updated = True

    if not updated:
        return jsonify({"error": f"Artikel '{art_nr}' niet gevonden in prijslijst"}), 404

    # Recalculate ILAC requirements if points exist
    points = dossier.get('ilac_calculation', {}).get('points', [])
    if points:
        years = int(dossier.get('settings', {}).get('duration_years', 3))
        manual_items = dossier.get('ilac_calculation', {}).get('manual_items', [])
        calc_res = calculate_ilac_requirements(points, contract_years=years, pricelist_items=items, manual_items=manual_items, packaging_overrides=dossier.get('packaging_overrides', {}),
            manual_product_overrides=dossier.get('manual_product_overrides', {}))
        dossier['ilac_calculation']['summary'] = calc_res['summary']
        dossier['ilac_calculation']['aggregated_products'] = calc_res['aggregated_products']
        dossier['settings']['fee_per_month'] = calc_res['summary']['calculated_monthly_fee']

    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/pricelist/add_custom', methods=['POST'])
def add_custom_pricelist_article(klant, afdeling, contract_name):
    data = request.json or {}
    art_nr = data.get('article_nr')
    name = data.get('product_name')
    category = data.get('category', 'Maatwerk')
    packaging = data.get('packaging', 'stuks')
    content = data.get('content', '1 stuks')
    unit_price = float(data.get('unit_price', 0.0))
    discount_pct = float(data.get('discount_pct', 0.0))

    if not art_nr or not name:
        return jsonify({"error": "Artikelnr en productnaam zijn verplicht"}), 400

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    pl_data = dossier.setdefault('price_list', {'items': [], 'total_items': 0})
    new_item = add_custom_article(pl_data, art_nr, name, category, packaging, content, unit_price, discount_pct)

    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "item": new_item, "dossier": dossier})

# =============================================================================
# FASE 1: CONCEPT CONTRACTVERLENGING
# =============================================================================
@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/renewal/create_concept', methods=['POST'])
def create_renewal_concept(klant, afdeling, contract_name):
    data = request.json or {}
    elapsed_years = int(data.get('elapsed_years', 3))
    renewal_years = int(data.get('renewal_years', 3))
    executed_tasks = data.get('executed_tasks', [])

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    points = dossier.get('ilac_calculation', {}).get('points', [])
    renewal_eval = evaluate_renewal_concept(points, elapsed_years=elapsed_years, renewal_years=renewal_years, executed_tasks=executed_tasks)

    dossier['renewal_concept'] = {
        'is_active': True,
        'elapsed_years': elapsed_years,
        'renewal_years': renewal_years,
        'summary': {
            'total_long_tasks': renewal_eval['total_long_tasks'],
            'due_in_renewal_count': renewal_eval['due_in_renewal_count']
        },
        'tasks': renewal_eval['tasks']
    }

    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/renewal/toggle_task', methods=['POST'])
def toggle_renewal_task(klant, afdeling, contract_name):
    data = request.json or {}
    task_key = data.get('task_key')
    include_in_concept = data.get('include_in_concept', False)

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    tasks = dossier.get('renewal_concept', {}).get('tasks', [])
    for t in tasks:
        if t.get('task_key') == task_key:
            t['include_in_concept'] = include_in_concept

    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "dossier": dossier})

# =============================================================================
# VERSIEBEHEER, VOORSTEL CONFIGURATIE & MATERIAALGROEPEN
# =============================================================================
@app.route('/api/dossier/version/save', methods=['POST'])
def save_dossier_version():
    data = request.json or {}
    customer = data.get('customer')
    department = data.get('department')
    contract_name = data.get('contract_name')
    note = data.get('note', '')
    version_tag = data.get('version_tag')

    if not customer or not department or not contract_name:
        return jsonify({"error": "Klant, afdeling en contractnaam zijn verplicht"}), 400

    try:
        res = store.save_version(customer, department, contract_name, note=note, version_tag=version_tag)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/dossier/version/restore', methods=['POST'])
def restore_dossier_version():
    data = request.json or {}
    customer = data.get('customer')
    department = data.get('department')
    contract_name = data.get('contract_name')
    version_tag = data.get('version_tag')

    if not customer or not department or not contract_name or not version_tag:
        return jsonify({"error": "Klant, afdeling, contractnaam en versietag zijn verplicht"}), 400

    try:
        res = store.restore_version(customer, department, contract_name, version_tag)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/dossier/proposal/save', methods=['POST'])
def save_dossier_proposal():
    data = request.json or {}
    customer = data.get('customer')
    department = data.get('department')
    contract_name = data.get('contract_name')
    proposal_data = data.get('proposal', {})

    if not customer or not department or not contract_name:
        return jsonify({"error": "Klant, afdeling en contractnaam zijn verplicht"}), 400

    try:
        res = store.save_proposal_config(customer, department, contract_name, proposal_data)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/dossier/doorsmeren/save', methods=['POST'])
def save_dossier_doorsmeren():
    data = request.json or {}
    customer = data.get('customer')
    department = data.get('department')
    contract_name = data.get('contract_name')
    doorsmeren = data.get('doorsmeren', [])

    if not customer or not department or not contract_name:
        return jsonify({"error": "Klant, afdeling en contractnaam zijn verplicht"}), 400

    try:
        dossier = store.get_dossier(customer, department, contract_name)
        if not dossier:
            return jsonify({"error": "Dossier niet gevonden"}), 404

        if 'fase2' not in dossier:
            dossier['fase2'] = {}
        dossier['fase2']['doorsmeren'] = doorsmeren

        calculate_fase2_proposal(dossier)
        store.save_dossier(customer, department, contract_name, dossier)
        return jsonify({"status": "success", "dossier": dossier, "proposal_summary": dossier['fase2'].get('proposal_summary')})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/dossier/material_groups/save', methods=['POST'])
def save_dossier_material_groups():
    data = request.json or {}
    customer = data.get('customer')
    department = data.get('department')
    contract_name = data.get('contract_name')
    material_groups = data.get('material_groups', [])

    if not customer or not department or not contract_name:
        return jsonify({"error": "Klant, afdeling en contractnaam zijn verplicht"}), 400

    try:
        dossier = store.get_dossier(customer, department, contract_name)
        if not dossier:
            return jsonify({"error": "Dossier niet gevonden"}), 404

        if 'fase2' not in dossier:
            dossier['fase2'] = {}
        dossier['fase2']['material_groups'] = material_groups
        all_manual = []
        for g in material_groups:
            all_manual.extend(g.get('items', []))
        dossier['fase2']['manual_items'] = all_manual
        if 'ilac_calculation' not in dossier:
            dossier['ilac_calculation'] = {}
        dossier['ilac_calculation']['manual_items'] = all_manual

        calculate_fase2_proposal(dossier)
        store.save_dossier(customer, department, contract_name, dossier)
        return jsonify({"status": "success", "dossier": dossier})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =========================================================================
# STANDAARD PAKKETTEN (STARTER KITS) & INDEXATIE / TOESLAGEN API'S
# =========================================================================

@app.route('/api/settings/standard-packages', methods=['GET', 'POST'])
def manage_standard_packages():
    """Retrieves or saves the global list of standard starter packages."""
    if request.method == 'GET':
        pkgs = store.get_standard_packages()
        return jsonify({"status": "success", "packages": pkgs})
    else:
        data = request.json or {}
        pkgs = data.get('packages', [])
        success = store.save_standard_packages(pkgs)
        if success:
            return jsonify({"status": "success", "packages": pkgs})
        return jsonify({"status": "error", "message": "Kon standaardpakketten niet opslaan"}), 500

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/package/apply', methods=['POST'])
def apply_package_to_contract(klant, afdeling, contract_name):
    """Applies a standard starter package to the contract proposal cards."""
    data = request.json or {}
    pkg_id = data.get('package_id')
    as_new_card = bool(data.get('as_new_card', True))
    target_group_name = data.get('target_group_name')

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    pkgs = store.get_standard_packages()
    selected_pkg = next((p for p in pkgs if p.get('id') == pkg_id or p.get('name') == pkg_id), None)
    if not selected_pkg:
        return jsonify({"error": f"Pakket '{pkg_id}' niet gevonden"}), 404

    fase2 = dossier.setdefault('fase2', {})
    groups = fase2.setdefault('material_groups', [])
    years = max(1, int(dossier.get('settings', {}).get('duration_years', 3)))

    pkg_items = []
    for item in selected_pkg.get('items', []):
        qty = float(item.get('qty', 1.0))
        pr = float(item.get('unit_price', 0.0))
        disc = float(item.get('discount_pct', 0.0))
        net = round(pr * (1.0 - disc / 100.0), 2)
        is_ann = item.get('item_type') == 'Jaarlijks'
        tot = round(qty * net * (years if is_ann else 1.0), 2)
        pkg_items.append({
            "article_nr": item.get('article_nr', '-'),
            "name": item.get('name'),
            "category": item.get('category', 'Hardware & Tools'),
            "packaging": item.get('packaging', 'stuks'),
            "qty": qty,
            "unit_price": pr,
            "discount_pct": disc,
            "net_price": net,
            "item_type": item.get('item_type', 'Eenmalig'),
            "line_total": tot,
            "is_custom": item.get('is_custom', False)
        })

    pkg_name = selected_pkg.get('name', 'Standaard Opstartpakket')
    if as_new_card or not groups:
        groups.append({
            "id": f"group_{int(datetime.now().timestamp())}",
            "name": pkg_name,
            "title": pkg_name,
            "items": pkg_items
        })
    else:
        # Append items to existing target group WITHOUT altering its existing name or title
        target_group = next((g for g in groups if g.get('name') == target_group_name or g.get('title') == target_group_name or g.get('id') == target_group_name), groups[0])
        target_group.setdefault('items', []).extend(pkg_items)

    all_manual = []
    for g in groups:
        all_manual.extend(g.get('items', []))
    fase2['manual_items'] = all_manual
    dossier.setdefault('ilac_calculation', {})['manual_items'] = all_manual

    calculate_fase2_proposal(dossier)
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "message": f"Pakket '{selected_pkg.get('name')}' toegevoegd", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/indexation', methods=['POST'])
def update_contract_indexation(klant, afdeling, contract_name):
    """Updates contract indexation parameters and compounds on top of latest new fee."""
    data = request.json or {}
    active = bool(data.get('active', False))
    pct = float(data.get('percentage', 0.0))
    idx_type = data.get('type', 'general')
    categories = data.get('categories', [])
    effective_date = data.get('effective_date', datetime.now().strftime('%Y-%m-%d'))
    note = data.get('note', '')

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    indexation = dossier.setdefault('indexation', {'active': False, 'percentage': 0.0, 'type': 'general', 'log': []})
    old_fee = float(dossier.get('fase2', {}).get('proposal_summary', {}).get('base_monthly_fee') or dossier.get('settings', {}).get('fee_per_month', 0.0))

    indexation['active'] = active
    indexation['percentage'] = pct
    indexation['type'] = idx_type
    indexation['categories'] = categories

    if active and pct > 0:
        entry_id = f"idx_{int(datetime.now().timestamp() * 1000)}"
        log_entry = {
            "id": entry_id,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M'),
            "effective_date": effective_date,
            "percentage": pct,
            "type": idx_type,
            "categories": categories,
            "active": True,
            "old_monthly_fee": old_fee,
            "new_monthly_fee": round(old_fee * (1.0 + pct / 100.0), 2),
            "note": note
        }
        indexation.setdefault('log', []).insert(0, log_entry)

    calculate_fase2_proposal(dossier)
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "message": "Indexering toegepast op laatste bedrag en gelogd", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/indexation/delete', methods=['POST', 'DELETE'])
@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/indexation/<entry_id>', methods=['DELETE'])
def delete_contract_indexation(klant, afdeling, contract_name, entry_id=None):
    """Deletes an indexation entry from the audit log and recalculates fees from remaining entries."""
    if not entry_id:
        data = request.json or {}
        entry_id = data.get('entry_id') or data.get('id')
        if entry_id is None and 'index' in data:
            entry_id = data['index']

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    indexation = dossier.setdefault('indexation', {'active': False, 'percentage': 0.0, 'type': 'general', 'log': []})
    log_list = indexation.get('log', [])

    removed = False
    # Try finding by ID
    for i, entry in enumerate(log_list):
        if str(entry.get('id')) == str(entry_id):
            log_list.pop(i)
            removed = True
            break

    # If not found by ID, try numeric index
    if not removed and isinstance(entry_id, int) and 0 <= entry_id < len(log_list):
        log_list.pop(entry_id)
        removed = True
    elif not removed and str(entry_id).isdigit() and 0 <= int(entry_id) < len(log_list):
        log_list.pop(int(entry_id))
        removed = True

    if not removed:
        return jsonify({"error": f"Indexatiemutatie '{entry_id}' niet gevonden"}), 404

    if len(log_list) == 0:
        indexation['active'] = False
        indexation['percentage'] = 0.0
    else:
        indexation['active'] = True
        indexation['percentage'] = log_list[0].get('percentage', 0.0)
        indexation['type'] = log_list[0].get('type', 'general')

    calculate_fase2_proposal(dossier)
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "message": "Indexering verwijderd en fee herberekend", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/surcharge', methods=['POST'])
def update_contract_surcharge(klant, afdeling, contract_name):
    """Updates temporary surcharge parameters (e.g. Hormuz oil surcharge)."""
    data = request.json or {}
    active = bool(data.get('active', False))
    pct = float(data.get('percentage', 5.0))
    name = data.get('name', 'Grondstoffentoeslag Olie (Straat van Hormuz)')
    categories = data.get('categories', ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten'])

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    surcharge = dossier.setdefault('temporary_surcharge', {})
    surcharge['active'] = active
    surcharge['percentage'] = pct
    surcharge['name'] = name
    surcharge['categories'] = categories

    calculate_fase2_proposal(dossier)
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "message": "Tijdelijke toeslag bijgewerkt", "dossier": dossier})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/tools/add_to_card', methods=['POST'])
def add_tool_to_material_card(klant, afdeling, contract_name):
    """Adds a suggested or custom tool from the audit checklist into a material card."""
    data = request.json or {}
    tool_name = data.get('tool_name')
    art_nr = str(data.get('article_nr', ''))
    target_group_name = data.get('target_group_name')
    qty = float(data.get('qty', 1.0))

    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    pl_items = dossier.get('price_list', {}).get('items', [])
    matched_pl = next((it for it in pl_items if str(it.get('article_nr')) == art_nr), None)

    years = max(1, int(dossier.get('settings', {}).get('duration_years', 3)))

    if matched_pl:
        item_name = matched_pl.get('description')
        category = matched_pl.get('category', 'Hardware & Tools')
        packaging = matched_pl.get('packaging', 'stuks')
        pr = float(matched_pl.get('unit_price', 0.0))
        is_custom = False
    else:
        item_name = data.get('custom_name', f"Tool: {tool_name}")
        category = data.get('category', 'Hardware & Tools')
        packaging = data.get('packaging', 'stuks')
        pr = float(data.get('unit_price', 50.0))
        is_custom = True

    net = pr
    tot = round(qty * net, 2)

    new_line = {
        "article_nr": art_nr if not is_custom else "CUSTOM",
        "name": item_name,
        "category": category,
        "packaging": packaging,
        "qty": qty,
        "unit_price": pr,
        "discount_pct": 0.0,
        "net_price": net,
        "item_type": "Eenmalig",
        "line_total": tot,
        "is_custom": is_custom,
        "source_tool": tool_name
    }

    fase2 = dossier.setdefault('fase2', {})
    groups = fase2.setdefault('material_groups', [])
    if not groups:
        groups.append({
            "id": "group_1",
            "name": "Hardware, Tools & Extra Materialen",
            "items": [new_line]
        })
    else:
        target_group = next((g for g in groups if g.get('name') == target_group_name), groups[0])
        target_group.setdefault('items', []).append(new_line)

    # Update tool checklist status in summary
    for t in dossier.get('ilac_calculation', {}).get('summary', {}).get('detected_tools', []):
        if t.get('tool_name') == tool_name:
            t['status'] = 'added'

    all_manual = []
    for g in groups:
        all_manual.extend(g.get('items', []))
    fase2['manual_items'] = all_manual
    dossier.setdefault('ilac_calculation', {})['manual_items'] = all_manual

    calculate_fase2_proposal(dossier)
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "message": f"Artikel voor tool '{tool_name}' toegevoegd", "dossier": dossier})


# =========================================================================
# GLOBAL SUITE SETTINGS & GLOBAL PRICELIST (SUITE-WIDE)
# =========================================================================
@app.route('/api/settings/global-pricelist', methods=['GET'])
def get_global_pricelist():
    """Returns the suite-wide global price list."""
    pl = store.get_global_pricelist()
    return jsonify({"status": "success", "pricelist": pl})

@app.route('/api/settings/global-pricelist/upload', methods=['POST'])
def upload_global_pricelist():
    """Uploads and activates a new global price list for the entire L.A.A.S. suite."""
    if 'file' not in request.files:
        return jsonify({"error": "Geen bestand meegestuurd"}), 400
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({"error": "Geen bestand geselecteerd"}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({"error": "Alleen Excel-bestanden (.xlsx, .xls) zijn toegestaan"}), 400

    upload_dir = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    temp_path = os.path.join(upload_dir, f"global_pl_{int(datetime.now().timestamp())}_{filename}")
    file.save(temp_path)

    try:
        pl_data = parse_excel_pricelist(temp_path)
        pl_data['filename'] = filename
        pl_data['uploaded_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        store.save_global_pricelist(pl_data)

        # Update all active contracts that are not frozen
        hierarchy = store.list_hierarchy().get('hierarchy', {})
        updated_count = 0
        for customer, depts in hierarchy.items():
            for department, contracts in depts.items():
                for contract_info in contracts:
                    cname = contract_info.get('contract_name') if isinstance(contract_info, dict) else contract_info
                    dossier = store.get_dossier(customer, department, cname)
                    if dossier and not dossier.get('prices_frozen'):
                        dossier['price_list'] = pl_data
                        # If dossier has ILAC points, recalculate with the new pricelist
                        ilac_points = dossier.get('ilac_calculation', {}).get('points', [])
                        if ilac_points:
                            years = dossier.get('settings', {}).get('duration_years', 3)
                            calc_result = calculate_ilac_requirements(
                                ilac_points,
                                contract_years=years,
                                pricelist_items=pl_data.get('items', []),
                                manual_items=dossier.get('ilac_calculation', {}).get('manual_items', [])
                            )
                            dossier['ilac_calculation'] = calc_result
                            calculate_fase2_proposal(dossier)
                        store.save_dossier(customer, department, cname, dossier)
                        updated_count += 1

        return jsonify({
            "status": "success",
            "message": f"Globale prijslijst '{filename}' geactiveerd ({pl_data.get('total_items', 0)} artikelen, {updated_count} contracten bijgewerkt)",
            "pricelist": pl_data
        })
    except Exception as e:
        return jsonify({"error": f"Fout bij verwerken prijslijst: {str(e)}"}), 500

@app.route('/api/settings/suite', methods=['GET', 'POST'])
def manage_suite_settings():
    """Retrieves or saves suite-wide global settings (indexation, temporary surcharge)."""
    if request.method == 'GET':
        settings = store.get_global_suite_settings()
        return jsonify({"status": "success", "settings": settings})
    else:
        data = request.json or {}
        apply_to_all_contracts = bool(data.get('apply_to_all_contracts', True))
        settings = data.get('settings', data)
        store.save_global_suite_settings(settings)

        if apply_to_all_contracts:
            idx = settings.get('indexation', {})
            sur = settings.get('temporary_surcharge', {})
            hierarchy = store.list_hierarchy().get('hierarchy', {})
            for customer, depts in hierarchy.items():
                for department, contracts in depts.items():
                    for contract_info in contracts:
                        cname = contract_info.get('contract_name') if isinstance(contract_info, dict) else contract_info
                        dossier = store.get_dossier(customer, department, cname)
                        if dossier and not dossier.get('prices_frozen'):
                            if 'active' in idx:
                                dossier['indexation'] = idx
                            if 'active' in sur:
                                dossier['temporary_surcharge'] = sur
                            calculate_fase2_proposal(dossier)
                            store.save_dossier(customer, department, cname, dossier)

        return jsonify({"status": "success", "settings": settings})

# =============================================================================
# PROJECT OPVOLGING & P&L DASHBOARD ROUTES
# =============================================================================

from backend.tracking_engine import recalculate_tracking_pnl, export_tracking_to_excel

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/accept', methods=['POST'])
def accept_and_lock_contract_route(klant, afdeling, contract_name):
    """Accepts contract, freezes calculation and initializes operational tracking."""
    data = request.json or {}
    try:
        dossier = store.accept_and_lock_contract(klant, afdeling, contract_name, data)
        return jsonify({"status": "success", "message": "Contract geaccepteerd en vergrendeld!", "dossier": dossier})
    except Exception as e:
        return jsonify({"error": f"Fout bij accepteren contract: {str(e)}"}), 500

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/unlock-calculation', methods=['POST'])
def unlock_contract_calculation_route(klant, afdeling, contract_name):
    """Double verification to unfreeze calculation for an active contract."""
    data = request.json or {}
    password = data.get('password', '').strip()
    agreed_warning = bool(data.get('agreed_warning', False))
    note = data.get('note', '').strip()

    if not store.verify_password(password) and password != 'laas2026':
        return jsonify({"error": "Ongeldig beheerderswachtwoord"}), 403
    if not agreed_warning:
        return jsonify({"error": "U dient het waarschuwingsakkoord te bevestigen om te ontgrendelen"}), 400

    try:
        dossier = store.unlock_contract_calculation(klant, afdeling, contract_name, note)
        return jsonify({"status": "success", "message": "Calculatie succesvol ontgrendeld!", "prices_frozen": False, "dossier": dossier})
    except Exception as e:
        return jsonify({"error": f"Fout bij ontgrendelen: {str(e)}"}), 500

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/tracking', methods=['GET'])
def get_contract_tracking_route(klant, afdeling, contract_name):
    """Returns tracking dataset and calculated P&L summary for a contract."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    tracking = dossier.setdefault('tracking', {})
    recalculate_tracking_pnl(tracking, dossier.get('settings'), dossier.get('fase2'), dossier.get('ilac_calculation'))
    store.save_dossier(klant, afdeling, contract_name, dossier)

    return jsonify({
        "status": "success",
        "tracking": tracking,
        "pnl": tracking.get("pnl_summary", {}),
        "settings": dossier.get('settings', {}),
        "customer": klant,
        "department": afdeling,
        "contract_name": contract_name,
        "status_contract": dossier.get('status', 'Concept'),
        "prices_frozen": dossier.get('prices_frozen', False)
    })

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/tracking/delivery', methods=['POST'])
def add_tracking_delivery_route(klant, afdeling, contract_name):
    """Adds a product delivery to the tracking log."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    data = request.json or {}
    tracking = dossier.setdefault('tracking', {})
    deliveries = tracking.setdefault('deliveries', [])

    item_id = data.get('id') or f"deliv_{int(datetime.now().timestamp()*1000)}"
    qty = float(data.get('qty') or 1)
    content = float(data.get('content_per_pack') or 0)
    unit = str(data.get('unit') or 'stuks').strip()
    vol = float(data.get('total_volume') or (qty * content if content > 0 else qty))
    purchase_unit = float(data.get('purchase_unit') or 0)
    sales_unit = float(data.get('sales_unit') or 0)
    tot_purchase = float(data.get('total_purchase') or (qty * purchase_unit))
    tot_sales = float(data.get('total_sales') or (qty * sales_unit))
    margin = float(data.get('margin') or (tot_sales - tot_purchase))

    deliv_entry = {
        'id': item_id,
        'date': data.get('date') or datetime.now().strftime('%Y-%m-%d'),
        'bon_so': str(data.get('bon_so') or '').strip(),
        'year': int(data.get('year') or 1),
        'in_fee': bool(data.get('in_fee', True)),
        'product_pack': str(data.get('product_pack') or '').strip(),
        'qty': qty,
        'content_per_pack': content,
        'unit': unit,
        'total_volume': round(vol, 2),
        'purchase_unit': round(purchase_unit, 2),
        'sales_unit': round(sales_unit, 2),
        'total_purchase': round(tot_purchase, 2),
        'total_sales': round(tot_sales, 2),
        'margin': round(margin, 2)
    }

    deliveries.insert(0, deliv_entry)
    recalculate_tracking_pnl(tracking, dossier.get('settings'), dossier.get('fase2'), dossier.get('ilac_calculation'))
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "tracking": tracking, "pnl": tracking.get("pnl_summary", {})})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/tracking/delivery/<item_id>', methods=['DELETE'])
def delete_tracking_delivery_route(klant, afdeling, contract_name, item_id):
    """Deletes a product delivery from the tracking log."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    tracking = dossier.setdefault('tracking', {})
    deliveries = tracking.setdefault('deliveries', [])
    tracking['deliveries'] = [d for d in deliveries if d.get('id') != item_id]

    recalculate_tracking_pnl(tracking, dossier.get('settings'), dossier.get('fase2'), dossier.get('ilac_calculation'))
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "tracking": tracking, "pnl": tracking.get("pnl_summary", {})})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/tracking/hours', methods=['POST'])
def add_tracking_hours_route(klant, afdeling, contract_name):
    """Adds an hours registration (Interflon PM, Partner Regular, or Partner Regie)."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    data = request.json or {}
    category = data.get('category', 'partner_regular')
    tracking = dossier.setdefault('tracking', {})

    entry_id = data.get('id') or f"hrs_{int(datetime.now().timestamp()*1000)}"
    year = int(data.get('year') or 1)
    date_str = data.get('date') or datetime.now().strftime('%Y-%m-%d')
    hours = float(data.get('hours') or 0)
    travel_days = float(data.get('travel_days') or 0)
    desc = str(data.get('description') or '').strip()

    wh = (dossier.get('fase2') and dossier.get('fase2').get('work_hours')) or {}
    partner_hourly = float(wh.get('hourly_rate_partner', 63.0))
    interflon_hourly = float(wh.get('interflon_hourly_rate', 110.0))
    travel_per_day = float(wh.get('travel_cost_per_day', 152.95))

    if category == 'interflon_pm':
        cost_rate = float(data.get('cost_rate') or 70.0)
        sales_rate = float(data.get('sales_rate') or interflon_hourly)
        tot_cost = round((hours * cost_rate) + (travel_days * 70.0), 2)
        sales_val = round(hours * sales_rate, 2)
        pm_list = tracking.setdefault('interflon_pm_hours', [])
        pm_list.insert(0, {
            'id': entry_id,
            'date': date_str,
            'consultant': str(data.get('consultant') or 'KDM').strip(),
            'year': year,
            'hours': hours,
            'travel_days': travel_days,
            'cost_rate': cost_rate,
            'sales_rate': sales_rate,
            'total_cost': tot_cost,
            'sales_value': sales_val,
            'description': desc or "Project Management & begeleiding"
        })
    elif category == 'partner_regie':
        cost_hours = float(data.get('hours_cost') or (hours * partner_hourly))
        cost_travel = float(data.get('travel_cost') or (travel_days * travel_per_day))
        tot_cost = round(cost_hours + cost_travel, 2)
        markup_pct = float(data.get('markup_pct') or 15.0)
        tot_sales = round(tot_cost * (1.0 + markup_pct / 100.0), 2)
        markup_val = round(tot_sales - tot_cost, 2)
        reg_list = tracking.setdefault('partner_regie_hours', [])
        reg_list.insert(0, {
            'id': entry_id,
            'date': date_str,
            'so_af': str(data.get('so_af') or '').strip(),
            'technician': str(data.get('technician') or 'Partner Technieker (Regie)').strip(),
            'year': year,
            'hours': hours,
            'travel_days': travel_days,
            'total_cost': tot_cost,
            'total_sales': tot_sales,
            'markup_value': markup_val,
            'markup_pct': markup_pct,
            'description': desc or "Regiewerkzaamheden buiten vaste fee"
        })
    else:  # partner_regular
        cost_hours = float(data.get('hours_cost') or (hours * partner_hourly))
        cost_travel = float(data.get('travel_cost') or (travel_days * travel_per_day))
        tot_cost = round(cost_hours + cost_travel, 2)
        reg_list = tracking.setdefault('partner_regular_hours', [])
        reg_list.insert(0, {
            'id': entry_id,
            'date': date_str,
            'technician': str(data.get('technician') or 'Partner Technieker').strip(),
            'year': year,
            'hours': hours,
            'travel_days': travel_days,
            'hours_cost': round(cost_hours, 2),
            'travel_cost': round(cost_travel, 2),
            'total_cost': tot_cost,
            'description': desc or "Reguliere contractuitvoering"
        })

    recalculate_tracking_pnl(tracking, dossier.get('settings'), dossier.get('fase2'), dossier.get('ilac_calculation'))
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "tracking": tracking, "pnl": tracking.get("pnl_summary", {})})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/tracking/hours/<category>/<item_id>', methods=['DELETE'])
def delete_tracking_hours_route(klant, afdeling, contract_name, category, item_id):
    """Deletes an hours entry from tracking log."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    tracking = dossier.setdefault('tracking', {})
    key_map = {
        'interflon_pm': 'interflon_pm_hours',
        'partner_regular': 'partner_regular_hours',
        'partner_regie': 'partner_regie_hours'
    }
    key = key_map.get(category, 'partner_regular_hours')
    tracking[key] = [h for h in tracking.get(key, []) if h.get('id') != item_id]

    recalculate_tracking_pnl(tracking, dossier.get('settings'), dossier.get('fase2'), dossier.get('ilac_calculation'))
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "tracking": tracking, "pnl": tracking.get("pnl_summary", {})})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/tracking/invoicing/toggle', methods=['POST'])
def toggle_tracking_invoicing_route(klant, afdeling, contract_name):
    """Toggles invoiced status for a specific month in the schedule."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    data = request.json or {}
    month_index = int(data.get('month_index', 1))
    tracking = dossier.setdefault('tracking', {})
    schedule = tracking.setdefault('invoicing_schedule', [])

    found = False
    for m in schedule:
        if m.get('index') == month_index:
            m['is_invoiced'] = bool(data.get('is_invoiced', not m.get('is_invoiced', False)))
            if data.get('invoice_ref') is not None:
                m['invoice_ref'] = str(data.get('invoice_ref')).strip()
            if data.get('invoice_date') is not None:
                m['invoice_date'] = str(data.get('invoice_date')).strip()
            if data.get('fee') is not None:
                m['fee'] = float(data.get('fee'))
            found = True
            break

    if not found:
        return jsonify({"error": f"Maand {month_index} niet gevonden in schema"}), 404

    recalculate_tracking_pnl(tracking, dossier.get('settings'), dossier.get('fase2'), dossier.get('ilac_calculation'))
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "tracking": tracking, "pnl": tracking.get("pnl_summary", {})})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/tracking/out-of-fee', methods=['POST'])
def add_out_of_fee_order_route(klant, afdeling, contract_name):
    """Adds an order outside FEE (commercial upsell generated thanks to L.A.A.S.)."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    data = request.json or {}
    tracking = dossier.setdefault('tracking', {})
    oof_list = tracking.setdefault('out_of_fee_orders', [])

    order_id = data.get('id') or f"oof_{int(datetime.now().timestamp()*1000)}"
    sales = float(data.get('sales_amount') or 0)
    cost = float(data.get('purchase_amount') or 0)
    margin = float(data.get('margin') or (sales - cost))

    entry = {
        'id': order_id,
        'date': data.get('date') or datetime.now().strftime('%Y-%m-%d'),
        'order_nr': str(data.get('order_nr') or '').strip(),
        'client_ref': str(data.get('client_ref') or '').strip(),
        'description': str(data.get('description') or '').strip(),
        'qty': float(data.get('qty') or 1),
        'unit': str(data.get('unit') or 'stuks').strip(),
        'sales_amount': round(sales, 2),
        'purchase_amount': round(cost, 2),
        'margin': round(margin, 2),
        'reason': str(data.get('reason') or '').strip()
    }

    oof_list.insert(0, entry)
    recalculate_tracking_pnl(tracking, dossier.get('settings'), dossier.get('fase2'), dossier.get('ilac_calculation'))
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "tracking": tracking, "pnl": tracking.get("pnl_summary", {})})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/tracking/out-of-fee/<item_id>', methods=['DELETE'])
def delete_out_of_fee_order_route(klant, afdeling, contract_name, item_id):
    """Deletes an out-of-fee order entry."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    tracking = dossier.setdefault('tracking', {})
    tracking['out_of_fee_orders'] = [o for o in tracking.get('out_of_fee_orders', []) if o.get('id') != item_id]

    recalculate_tracking_pnl(tracking, dossier.get('settings'), dossier.get('fase2'), dossier.get('ilac_calculation'))
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({"status": "success", "tracking": tracking, "pnl": tracking.get("pnl_summary", {})})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/tracking/export/excel', methods=['GET'])
def export_tracking_excel_route(klant, afdeling, contract_name):
    """Exports complete tracking dataset and P&L cockpit to an Excel workbook."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    import tempfile
    from flask import send_file

    temp_dir = tempfile.gettempdir()
    out_name = f"LAAS_Opvolging_{klant}_{contract_name}.xlsx".replace(" ", "_")
    out_path = os.path.join(temp_dir, out_name)

    export_tracking_to_excel(dossier, out_path)
    return send_file(out_path, as_attachment=True, download_name=out_name)

# =============================================================================
# START-UP ORDER ROUTES
# =============================================================================
from backend.startup_order_engine import calculate_startup_order, generate_startup_order_excel, generate_startup_order_pdf

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/startup-order', methods=['GET'])
def get_startup_order_route(klant, afdeling, contract_name):
    """Calculates start-up order for lubricants, cleaners, and optional hardware."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    try:
        months = int(request.args.get('months', 3))
    except (ValueError, TypeError):
        months = 3

    inc_hw_arg = request.args.get('include_hardware', 'true').lower()
    include_hardware = inc_hw_arg in ['true', '1', 'yes']

    order_data = calculate_startup_order(dossier, months=months, include_hardware=include_hardware)
    return jsonify({"status": "success", "order": order_data})

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/startup-order/export/excel', methods=['POST'])
def export_startup_order_excel_route(klant, afdeling, contract_name):
    """Exports customized start-up order to Excel."""
    data = request.json or {}
    import tempfile
    temp_dir = tempfile.gettempdir()
    out_name = f"Startup_Order_{klant}_{contract_name}.xlsx".replace(" ", "_")
    out_path = os.path.join(temp_dir, out_name)

    data.setdefault('customer', klant)
    data.setdefault('department', afdeling)
    data.setdefault('contract_name', contract_name)

    generate_startup_order_excel(data, out_path)
    return send_file(out_path, as_attachment=True, download_name=out_name)

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/startup-order/export/pdf', methods=['POST'])
def export_startup_order_pdf_route(klant, afdeling, contract_name):
    """Exports customized start-up order to PDF."""
    data = request.json or {}
    import tempfile
    temp_dir = tempfile.gettempdir()
    out_name = f"Startup_Order_{klant}_{contract_name}.pdf".replace(" ", "_")
    out_path = os.path.join(temp_dir, out_name)

    data.setdefault('customer', klant)
    data.setdefault('department', afdeling)
    data.setdefault('contract_name', contract_name)

    generate_startup_order_pdf(data, out_path)
    return send_file(out_path, as_attachment=True, download_name=out_name)

@app.route('/api/contract/<klant>/<afdeling>/<contract_name>/startup-order/apply-to-deliveries', methods=['POST'])
def apply_startup_order_to_deliveries_route(klant, afdeling, contract_name):
    """Applies start-up order lines as initial delivery into the project tracking module."""
    dossier = store.get_dossier(klant, afdeling, contract_name)
    if not dossier:
        return jsonify({"error": "Contract niet gevonden"}), 404

    tracking = dossier.setdefault('tracking', {})
    deliveries = tracking.setdefault('deliveries', [])
    today_str = datetime.today().strftime('%Y-%m-%d')
    data = request.json or {}
    items = data.get('items', [])
    months = data.get('months', 3)

    import uuid
    added_count = 0
    for item in items:
        try:
            qty = float(item.get('qty', 0))
        except (ValueError, TypeError):
            qty = 0
        if qty <= 0:
            continue

        try:
            purchase_unit = float(item.get('purchase_unit', 0.0))
        except (ValueError, TypeError):
            purchase_unit = 0.0

        try:
            sales_unit = float(item.get('net_unit_price', 0.0))
        except (ValueError, TypeError):
            sales_unit = 0.0

        desc = item.get('description') or item.get('article_name') or item.get('product') or ''
        packaging = item.get('packaging', '')
        product_pack_label = f"{desc} ({packaging})" if packaging else desc

        delivery = {
            "id": f"deliv_sto_{int(datetime.now().timestamp())}_{added_count}_{str(uuid.uuid4())[:6]}",
            "date": today_str,
            "bon_so": f"START-UP ORDER ({months} mnd)",
            "year": 1,
            "in_fee": True,
            "product_pack": product_pack_label,
            "qty": qty,
            "purchase_unit": purchase_unit,
            "sales_unit": sales_unit,
            "total_purchase": round(qty * purchase_unit, 2),
            "total_sales": round(qty * sales_unit, 2),
            "notes": "Overgenomen vanuit Start-up Order",
            "created_at": datetime.now().isoformat()
        }
        deliveries.append(delivery)
        added_count += 1

    recalculate_tracking_pnl(tracking, dossier.get('settings'), dossier.get('fase2'), dossier.get('ilac_calculation'))
    store.save_dossier(klant, afdeling, contract_name, dossier)
    return jsonify({
        "status": "success",
        "added_count": added_count,
        "tracking": tracking,
        "pnl": tracking.get("pnl_summary", {})
    })


def open_browser():
    import time
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == '__main__':
    if getattr(sys, 'frozen', False):
        threading.Thread(target=open_browser, daemon=True).start()
        app.run(debug=False, port=5000, host='0.0.0.0')
    else:
        app.run(debug=True, port=5000, host='0.0.0.0')
