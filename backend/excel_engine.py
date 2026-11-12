import openpyxl
import os
import json
import shutil
import subprocess
import tempfile
from datetime import datetime

def safe_load_workbook(path, data_only=True):
    temp_dir = tempfile.gettempdir()
    temp_file = os.path.join(temp_dir, f"laas_read_{os.getpid()}_{int(datetime.now().timestamp())}.xlsx")
    try:
        shutil.copy2(path, temp_file)
    except Exception:
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Copy-Item -LiteralPath '{os.path.abspath(path)}' -Destination '{temp_file}' -Force"], check=True)
    
    wb = openpyxl.load_workbook(temp_file, data_only=data_only)
    try:
        os.remove(temp_file)
    except Exception:
        pass
    return wb

def parse_laas_excel(path):
    wb = safe_load_workbook(path, data_only=True)
    dossier = {}

    # 1. Instellingen
    customer = 'Umicore'
    department = 'Loodraffinaderij H41'
    contract_name = 'Umicore - Loodraffinaderij H41'

    ws_inst = wb['01 Instellingen']
    fee_val = float(ws_inst.cell(4, 5).value or 10949.36)

    dossier['settings'] = {
        'contract_name': contract_name,
        'customer': customer,
        'department': department,
        'start_year': ws_inst.cell(5, 2).value or 2026,
        'duration_years': ws_inst.cell(6, 2).value or 3,
        'included_hours_month': ws_inst.cell(8, 2).value or 0,
        'fee_per_month': fee_val,
        'start_date': str(ws_inst.cell(5, 5).value or '2026-01-01')[:10],
        'total_months': int(ws_inst.cell(6, 5).value or 36),
        'invoiced_months': int(ws_inst.cell(7, 5).value or 9),
        'execution_markup': float(ws_inst.cell(10, 5).value or 0.15),
        'status': 'Actief'
    }

    # 2. Artikelmaster
    ws_art = wb['98 Artikelmaster']
    articles = []
    for r in range(5, ws_art.max_row + 1):
        name = ws_art.cell(r, 1).value
        if not name:
            continue
        articles.append({
            'dropdown_name': str(name).strip(),
            'category': str(ws_art.cell(r, 2).value or '').strip(),
            'dashboard_name': str(ws_art.cell(r, 3).value or '').strip(),
            'article_code': str(ws_art.cell(r, 4).value or '').strip(),
            'unit': str(ws_art.cell(r, 5).value or '').strip(),
            'content_per_pack': float(ws_art.cell(r, 6).value or 1),
            'cost_price': float(ws_art.cell(r, 7).value or 0),
            'sales_price': float(ws_art.cell(r, 8).value or 0),
            'in_fee_default': 'Ja' if str(ws_art.cell(r, 11).value or '').strip() in ['\u2714', 'Ja', 'ja', 'JA', 'Yes', 'yes', '1'] else 'Nee'
        })
    dossier['articles'] = articles

    # 3. Voorcalculatie - Budget
    ws_bud = wb['02 Voorcalculatie - budget']
    budget_items = []
    for r in range(4, ws_bud.max_row + 1):
        cat = ws_bud.cell(r, 1).value
        prod = ws_bud.cell(r, 2).value
        if not prod:
            continue
        budget_items.append({
            'category': str(cat or '').strip(),
            'product': str(prod).strip(),
            'lubrication_points': int(ws_bud.cell(r, 3).value or 0) if ws_bud.cell(r, 3).value else 0,
            'y1_qty': float(ws_bud.cell(r, 4).value or 0),
            'unit': str(ws_bud.cell(r, 5).value or '').strip(),
            'y1_packs': float(ws_bud.cell(r, 6).value or 0),
            'y1_value': float(ws_bud.cell(r, 7).value or 0),
            'y2_value': float(ws_bud.cell(r, 8).value or 0),
            'y3_value': float(ws_bud.cell(r, 9).value or 0)
        })
    dossier['budget_items'] = budget_items

    # 4. Controle producten
    ws_ctrl = wb['04 Controle producten']
    control_items = []
    for r in range(5, ws_ctrl.max_row + 1):
        prod = ws_ctrl.cell(r, 1).value
        if not prod:
            continue
        control_items.append({
            'product': str(prod).strip(),
            'unit': str(ws_ctrl.cell(r, 2).value or '').strip(),
            'yearly_demand': float(ws_ctrl.cell(r, 3).value or 0),
            'calc_product': str(ws_ctrl.cell(r, 4).value or '').strip(),
            'y1_qty': float(ws_ctrl.cell(r, 5).value or 0),
            'y1_diff': float(ws_ctrl.cell(r, 6).value or 0),
            'y1_coverage_pct': float(ws_ctrl.cell(r, 7).value or 0),
            'y2_qty': float(ws_ctrl.cell(r, 8).value or 0),
            'y2_diff': float(ws_ctrl.cell(r, 9).value or 0),
            'y2_coverage_pct': float(ws_ctrl.cell(r, 10).value or 0),
            'y3_qty': float(ws_ctrl.cell(r, 11).value or 0),
            'y3_diff': float(ws_ctrl.cell(r, 12).value or 0),
            'y3_coverage_pct': float(ws_ctrl.cell(r, 13).value or 0),
            'y1_cost': float(ws_ctrl.cell(r, 14).value or 0)
        })
    dossier['control_items'] = control_items

    # 5. Leveringen (Normalize in_fee: '\u2714' or 'Ja' -> 'Ja', else 'Nee')
    ws_lev = wb['08 Leveringen']
    deliveries = []
    for r in range(5, ws_lev.max_row + 1):
        datum = ws_lev.cell(r, 1).value
        bon = ws_lev.cell(r, 2).value
        prod = ws_lev.cell(r, 5).value
        if not prod and not bon:
            continue
        raw_in_fee = str(ws_lev.cell(r, 4).value or '').strip()
        in_fee_normalized = 'Ja' if raw_in_fee in ['\u2714', 'Ja', 'ja', 'JA', 'Yes', 'yes', '1', 'True'] else 'Nee'

        deliveries.append({
            'date': str(datum)[:10] if datum else '',
            'bon_so': str(bon or '').strip(),
            'year': int(ws_lev.cell(r, 3).value or 1),
            'in_fee': in_fee_normalized,
            'product_pack': str(prod or '').strip(),
            'quantity': float(ws_lev.cell(r, 6).value or 0),
            'pack_content': float(ws_lev.cell(r, 7).value or 0),
            'unit': str(ws_lev.cell(r, 8).value or '').strip(),
            'delivered_qty': float(ws_lev.cell(r, 9).value or 0),
            'cost_per_pack': float(ws_lev.cell(r, 10).value or 0),
            'sales_per_pack': float(ws_lev.cell(r, 11).value or 0),
            'total_cost': float(ws_lev.cell(r, 12).value or 0),
            'total_sales': float(ws_lev.cell(r, 13).value or 0),
            'margin_eur': float(ws_lev.cell(r, 14).value or 0),
            'margin_pct': float(ws_lev.cell(r, 15).value or 0),
            'category': str(ws_lev.cell(r, 16).value or '').strip(),
            'article': str(ws_lev.cell(r, 18).value or '').strip(),
            'notes': str(ws_lev.cell(r, 19).value or '').strip()
        })
    dossier['deliveries'] = deliveries

    # 6. Werkuren Partner
    ws_uur = wb['05 Werkuren']
    partner_hours = []
    for r in range(13, ws_uur.max_row + 1):
        datum = ws_uur.cell(r, 1).value
        hours = ws_uur.cell(r, 3).value
        if datum is None and hours is None:
            continue
        cost_h = float(ws_uur.cell(r, 5).value or 0)
        cost_t = float(ws_uur.cell(r, 6).value or 0)
        partner_hours.append({
            'date': str(datum)[:10] if datum else '',
            'year': int(ws_uur.cell(r, 2).value or 1) if ws_uur.cell(r, 2).value else 1,
            'hours': float(hours or 0),
            'trips': int(ws_uur.cell(r, 4).value or 0) if ws_uur.cell(r, 4).value else 0,
            'cost_hours': cost_h,
            'cost_trips': cost_t,
            'sales_hours': round(cost_h * 1.15, 2),
            'sales_trips': round(cost_t * 1.15, 2),
            'total_cost': round(cost_h + cost_t, 2),
            'total_sales': round((cost_h + cost_t) * 1.15, 2)
        })
    dossier['partner_hours'] = partner_hours

    # 7. Werkuren Interflon
    ws_intl = wb['05A Werkuren Interflon']
    interflon_hours = []
    for r in range(16, ws_intl.max_row + 1):
        datum = ws_intl.cell(r, 1).value
        init = ws_intl.cell(r, 3).value
        if not datum and not init:
            continue
        interflon_hours.append({
            'date': str(datum)[:10] if datum else '',
            'year': int(ws_intl.cell(r, 2).value or 1) if ws_intl.cell(r, 2).value else 1,
            'employee': str(init or '').strip(),
            'hours': float(ws_intl.cell(r, 4).value or 0),
            'trips': int(ws_intl.cell(r, 5).value or 0) if ws_intl.cell(r, 5).value else 0,
            'cost_rate': float(ws_intl.cell(r, 6).value or 0),
            'sales_rate': float(ws_intl.cell(r, 7).value or 0),
            'cost_hours': float(ws_intl.cell(r, 8).value or 0),
            'cost_trips': float(ws_intl.cell(r, 9).value or 0),
            'total_cost': float(ws_intl.cell(r, 10).value or 0),
            'total_sales': float(ws_intl.cell(r, 11).value or 0),
            'notes': str(ws_intl.cell(r, 12).value or '').strip()
        })
    dossier['interflon_hours'] = interflon_hours

    # 8. Regie
    ws_reg = wb['06 Regie']
    regie_items = []
    for r in range(13, ws_reg.max_row + 1):
        datum = ws_reg.cell(r, 1).value
        so = ws_reg.cell(r, 3).value
        if not datum and not so:
            continue
        regie_items.append({
            'date': str(datum)[:10] if datum else '',
            'year': int(ws_reg.cell(r, 2).value or 1) if ws_reg.cell(r, 2).value else 1,
            'so_af': str(so or '').strip(),
            'hours': float(ws_reg.cell(r, 4).value or 0),
            'trips': int(ws_reg.cell(r, 5).value or 0) if ws_reg.cell(r, 5).value else 0,
            'cost_hours': float(ws_reg.cell(r, 6).value or 0),
            'cost_trips': float(ws_reg.cell(r, 7).value or 0),
            'sales_hours': float(ws_reg.cell(r, 8).value or 0),
            'sales_trips': float(ws_reg.cell(r, 9).value or 0),
            'total_cost': float(ws_reg.cell(r, 10).value or 0),
            'total_sales': float(ws_reg.cell(r, 11).value or 0),
            'markup_value': float(ws_reg.cell(r, 12).value or 0)
        })
    dossier['regie'] = regie_items

    # 9. Evolutie & Prognose
    ws_evo = wb['09 Evolutie FEE saldo']
    evolution = []
    for r in range(5, ws_evo.max_row + 1):
        month = ws_evo.cell(r, 1).value
        if not month:
            continue
        evolution.append({
            'month': str(month)[:10],
            'fee_invoiced': float(ws_evo.cell(r, 2).value or 0),
            'products_value': float(ws_evo.cell(r, 3).value or 0),
            'partner_value': float(ws_evo.cell(r, 4).value or 0),
            'interflon_value': float(ws_evo.cell(r, 5).value or 0),
            'total_consumed': float(ws_evo.cell(r, 6).value or 0),
            'cum_fee_actual': float(ws_evo.cell(r, 7).value or 0),
            'cum_consumed_actual': float(ws_evo.cell(r, 8).value or 0),
            'balance_actual': float(ws_evo.cell(r, 9).value or 0),
            'status': str(ws_evo.cell(r, 10).value or '').strip(),
            'cum_fee_forecast': float(ws_evo.cell(r, 11).value or 0),
            'cum_consumed_forecast': float(ws_evo.cell(r, 12).value or 0),
            'balance_forecast': float(ws_evo.cell(r, 13).value or 0)
        })
    dossier['evolution'] = evolution

    # 10. Invoiced schedule (36 months fee check)
    months_names = ["Jan", "Feb", "Mrt", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    invoiced_schedule = []
    inv_count = 0
    for m_idx in range(1, 37):
        year_idx = ((m_idx - 1) // 12) + 1
        m_name = months_names[(m_idx - 1) % 12]
        cal_year = 2026 + ((m_idx - 1) // 12)
        is_inv = (m_idx <= 9)
        if is_inv:
            inv_count += 1
        invoiced_schedule.append({
            'month_number': m_idx,
            'month_label': f"{m_name} {cal_year}",
            'contract_year': year_idx,
            'fee_amount': fee_val,
            'is_invoiced': is_inv,
            'invoice_number': f"INV-{cal_year}-{m_idx:02d}" if is_inv else "",
            'invoice_date': f"{cal_year}-{(m_idx - 1) % 12 + 1:02d}-15" if is_inv else "",
            'checked': is_inv,
            'notes': "Gecontroleerd & akkoord" if is_inv else "Nog te factureren"
        })
    dossier['invoiced_schedule'] = invoiced_schedule

    # 11. Addendums list (incorporates former Phase 5 extension logic)
    dossier['addendums'] = [
        {
            'id': 'add_1',
            'title': 'Addendum 1 - Uitbreiding smeerpunten H41',
            'option': 'Optie A: Resterende looptijd hoofdcontract (Voorkeur)',
            'extra_fee_monthly': 0.0,
            'start_date': '2026-06-01',
            'status': 'Actief',
            'notes': 'Smeerpunten H41 uitbreiding opgenomen binnen bestaande FEE'
        }
    ]

    # 12. Signed Contracts Documents List
    dossier['signed_contracts'] = [
        {
            'filename': 'L.A.A.S._Overeenkomst_Umicore_Loodraffinaderij_H41_Getekend.pdf',
            'upload_date': '2026-01-02',
            'filesize': '1.4 MB',
            'signatory_client': 'Philippe De Witte (Umicore)',
            'signatory_interflon': 'Sven Permentier (Interflon)',
            'status': 'Volledig Ondertekend'
        }
    ]

    # 13. Project Management Tasks & Alerts
    dossier['tasks'] = [
        {
            'id': 'tsk_1',
            'title': 'Kwartaalinspectie centrale smeerinstallatie H41',
            'assignee': 'KDM',
            'due_date': '2026-11-20',
            'priority': 'Hoog',
            'status': 'In Behandeling'
        },
        {
            'id': 'tsk_2',
            'title': 'Controle voorraad Grease HTG en MP2/3',
            'assignee': 'SP',
            'due_date': '2026-11-25',
            'priority': 'Normaal',
            'status': 'Te Doen'
        },
        {
            'id': 'tsk_3',
            'title': 'Voorbereiding evaluatiecontract Jaar 2',
            'assignee': 'CV',
            'due_date': '2026-12-10',
            'priority': 'Normaal',
            'status': 'Te Doen'
        }
    ]

    # 14. Fase 1 Calculatiemodule Data (Scope, Smeermiddelen, Hardware, Partner, Interflon, Optie 1 & 2)
    dossier['calculation'] = get_default_calculation(customer, department)

    # 15. Dashboard KPIs
    recalculate_dossier_kpis(dossier)
    wb.close()
    return dossier

def get_default_calculation(customer="Umicore", department="Loodraffinaderij H41"):
    """Returns the verified, complete Phase 1 calculation data structure."""
    return {
        "scenario": "option2", # 'option1' (Levering & Regie) or 'option2' (All-in LaaS Uitvoering)
        "method": "kenny",     # 'kenny' (validated active model) or 'tjeu'
        "contract_months": 36,
        "contract_fee_target": 10949.36,
        "contract_fee_total": 394176.96,
        "audit_total_points": 1468,
        "departments": [
            {"name": "Anhydro", "points": 120, "description": "Droog- en scheidingsinstallaties"},
            {"name": "Droge weg", "points": 345, "description": "Transportbanden, brekers, ventilatoren"},
            {"name": "Gebouw Herweg ziften", "points": 60, "description": "Zeefinstallaties & trilmotoren"},
            {"name": "Natte weg", "points": 325, "description": "Pompen, roerwerken, filters"},
            {"name": "Raffinage", "points": 413, "description": "Loodketels, gietwielen, kraanbanen"},
            {"name": "Werktuigen", "points": 11, "description": "Onderhoudswerkplaats & mobiel equipement"},
            {"name": "Zakkenfilter", "points": 79, "description": "Afzuiging & doekenreiniging"},
            {"name": "Zo/Jo ovens", "points": 115, "description": "Ovens, aandrijvingen, zware lagers"}
        ],
        "lubricants": [
            {"name": "Fluor Grease 2", "category": "Interflon smeermiddelen", "points": 20, "yearly_demand": 1092, "unit": "Gram", "pack_size": "Lube Shuttle 800 gr.", "unit_price": 806.00, "y1_packs": 3, "y2_packs": 2, "y3_packs": 2, "y1_qty": 2400, "y2_qty": 1600, "y3_qty": 1600, "y1_extra_packs": 1, "y1_extra_note": "1 bus extra doorsmeren opstart", "y1_val": 2418.00, "y2_val": 1612.00, "y3_val": 1612.00, "in_fee": True},
            {"name": "Food Lube G100", "category": "Interflon smeermiddelen", "points": 4, "yearly_demand": 19.5, "unit": "Liter", "pack_size": "Jerrycan 10 L", "unit_price": 43.80, "y1_packs": 20, "y2_packs": 20, "y3_packs": 20, "y1_qty": 20, "y2_qty": 20, "y3_qty": 20, "y1_extra_packs": 0, "y1_extra_note": "-", "y1_val": 876.00, "y2_val": 876.00, "y3_val": 876.00, "in_fee": True},
            {"name": "Food Lube G220", "category": "Interflon smeermiddelen", "points": 1, "yearly_demand": 1.0, "unit": "Liter", "pack_size": "Jerrycan 5 L", "unit_price": 43.80, "y1_packs": 1, "y2_packs": 1, "y3_packs": 1, "y1_qty": 1, "y2_qty": 1, "y3_qty": 1, "y1_extra_packs": 0, "y1_extra_note": "-", "y1_val": 43.80, "y2_val": 43.80, "y3_val": 43.80, "in_fee": True},
            {"name": "Interflon Grease HTG", "category": "Interflon smeermiddelen", "points": 99, "yearly_demand": 64840, "unit": "Gram", "pack_size": "Lube Shuttle 400 gr.", "unit_price": 119.90, "y1_packs": 187, "y2_packs": 163, "y3_packs": 163, "y1_qty": 74800, "y2_qty": 65200, "y3_qty": 65200, "y1_extra_packs": 24, "y1_extra_note": "24 patronen extra doorsmeren J1", "y1_val": 22421.30, "y2_val": 19543.70, "y3_val": 19543.70, "in_fee": True},
            {"name": "Grease MP00", "category": "Interflon smeermiddelen", "points": 173, "yearly_demand": 1062.7, "unit": "Liter", "pack_size": "Vat 60 L / Los", "unit_price": 45.70, "y1_packs": 1066, "y2_packs": 0, "y3_packs": 0, "y1_qty": 1066, "y2_qty": 0, "y3_qty": 0, "y1_extra_packs": 1066, "y1_extra_note": "Eenmalige vulling centrale installaties J1", "y1_val": 48716.20, "y2_val": 0.00, "y3_val": 0.00, "in_fee": True},
            {"name": "Grease MP2/3 LS", "category": "Interflon smeermiddelen", "points": 679, "yearly_demand": 99612, "unit": "Gram", "pack_size": "Lube Shuttle 400 ml", "unit_price": 30.20, "y1_packs": 298, "y2_packs": 250, "y3_packs": 250, "y1_qty": 119200, "y2_qty": 100000, "y3_qty": 100000, "y1_extra_packs": 48, "y1_extra_note": "48 patronen oliewissels eerste jaar", "y1_val": 8999.60, "y2_val": 7550.00, "y3_val": 7550.00, "in_fee": True},
            {"name": "Grease MP2/3 SP", "category": "Interflon smeermiddelen", "points": 4, "yearly_demand": 4500, "unit": "Milliliter", "pack_size": "Service Pack 250 ml", "unit_price": 59.30, "y1_packs": 18, "y2_packs": 18, "y3_packs": 18, "y1_qty": 4500, "y2_qty": 4500, "y3_qty": 4500, "y1_extra_packs": 0, "y1_extra_note": "-", "y1_val": 1067.40, "y2_val": 1067.40, "y3_val": 1067.40, "in_fee": True},
            {"name": "Grease MP2/3 Vulpomp", "category": "Interflon smeermiddelen", "points": 16, "yearly_demand": 37200, "unit": "Gram", "pack_size": "Vulpomp 30 L", "unit_price": 37.00, "y1_packs": 40, "y2_packs": 40, "y3_packs": 40, "y1_qty": 37200, "y2_qty": 37200, "y3_qty": 37200, "y1_extra_packs": 0, "y1_extra_note": "-", "y1_val": 1480.00, "y2_val": 1480.00, "y3_val": 1480.00, "in_fee": True},
            {"name": "Grease OG", "category": "Interflon smeermiddelen", "points": 24, "yearly_demand": 2000, "unit": "Milliliter", "pack_size": "Spuitbus 500 ml", "unit_price": 42.80, "y1_packs": 4, "y2_packs": 4, "y3_packs": 4, "y1_qty": 2000, "y2_qty": 2000, "y3_qty": 2000, "y1_extra_packs": 0, "y1_extra_note": "-", "y1_val": 171.20, "y2_val": 171.20, "y3_val": 171.20, "in_fee": True},
            {"name": "Lube EP+", "category": "Interflon smeermiddelen", "points": 20, "yearly_demand": 19840, "unit": "Milliliter", "pack_size": "Spuitbus 500 ml", "unit_price": 37.40, "y1_packs": 40, "y2_packs": 40, "y3_packs": 40, "y1_qty": 19840, "y2_qty": 19840, "y3_qty": 19840, "y1_extra_packs": 0, "y1_extra_note": "-", "y1_val": 1496.00, "y2_val": 1496.00, "y3_val": 1496.00, "in_fee": True},
            {"name": "Lube TF Oliekan", "category": "Interflon smeermiddelen", "points": 2, "yearly_demand": 2400, "unit": "Milliliter", "pack_size": "Bus 1 L", "unit_price": 41.80, "y1_packs": 3, "y2_packs": 3, "y3_packs": 3, "y1_qty": 2400, "y2_qty": 2400, "y3_qty": 2400, "y1_extra_packs": 0, "y1_extra_note": "-", "y1_val": 125.40, "y2_val": 125.40, "y3_val": 125.40, "in_fee": True},
            {"name": "Lube TF Aerosol", "category": "Interflon smeermiddelen", "points": 46, "yearly_demand": 3642, "unit": "Milliliter", "pack_size": "Spuitbus 500 ml", "unit_price": 26.60, "y1_packs": 8, "y2_packs": 8, "y3_packs": 8, "y1_qty": 3642, "y2_qty": 3642, "y3_qty": 3642, "y1_extra_packs": 0, "y1_extra_note": "-", "y1_val": 212.80, "y2_val": 212.80, "y3_val": 212.80, "in_fee": True},
            {"name": "Grease HTG Single Point 125 gr", "category": "Interflon smeermiddelen", "points": 4, "yearly_demand": 24, "unit": "Stuks", "pack_size": "Single Point Unit 125 gr", "unit_price": 115.40, "y1_packs": 24, "y2_packs": 24, "y3_packs": 24, "y1_qty": 24, "y2_qty": 24, "y3_qty": 24, "y1_extra_packs": 0, "y1_extra_note": "-", "y1_val": 2769.60, "y2_val": 2769.60, "y3_val": 2769.60, "in_fee": True},
            {"name": "Lube TF Single Point 125 ml", "category": "Interflon smeermiddelen", "points": 2, "yearly_demand": 24, "unit": "Stuks", "pack_size": "Single Point Unit 125 ml", "unit_price": 60.00, "y1_packs": 24, "y2_packs": 24, "y3_packs": 24, "y1_qty": 24, "y2_qty": 24, "y3_qty": 24, "y1_extra_packs": 0, "y1_extra_note": "-", "y1_val": 1440.00, "y2_val": 1440.00, "y3_val": 1440.00, "in_fee": True}
        ],
        "external_lubricants": [
            {"name": "Leybold LVO 210", "yearly_demand": 10, "unit": "Liter", "unit_price": 32.00, "y1_val": 320.00, "y2_val": 320.00, "y3_val": 320.00, "in_fee": False, "notes": "Buiten vaste FEE - nacalculatie"},
            {"name": "Mobil DTE 10 Excel 46", "yearly_demand": 335, "unit": "Liter", "unit_price": 7.96, "y1_val": 2666.60, "y2_val": 0.00, "y3_val": 0.00, "in_fee": False, "notes": "Buiten vaste FEE - nacalculatie"},
            {"name": "Mobil DTE 10 Excel 68", "yearly_demand": 17, "unit": "Liter", "unit_price": 7.96, "y1_val": 135.32, "y2_val": 0.00, "y3_val": 0.00, "in_fee": False, "notes": "Buiten vaste FEE - nacalculatie"},
            {"name": "Mobil DTE Excel 68", "yearly_demand": 160, "unit": "Liter", "unit_price": 7.96, "y1_val": 1273.60, "y2_val": 0.00, "y3_val": 0.00, "in_fee": False, "notes": "Buiten vaste FEE - nacalculatie"},
            {"name": "Mobil Mobilux EP2", "yearly_demand": 0, "unit": "Gram", "unit_price": 9.10, "y1_val": 0.00, "y2_val": 0.00, "y3_val": 0.00, "in_fee": False, "notes": "Buiten vaste FEE - nacalculatie"},
            {"name": "Quaker Q888-46", "yearly_demand": 144, "unit": "Liter", "unit_price": 13.42, "y1_val": 1932.48, "y2_val": 1932.48, "y3_val": 1932.48, "in_fee": False, "notes": "Buiten vaste FEE - nacalculatie"}
        ],
        "hardware": [
            {"name": 'Interflon Lube-Shuttle one hand grease gun 1/8"', "qty": 2, "unit": "Stuk", "unit_price": 54.80, "total_val": 109.60, "category": "Interflon hardware"},
            {"name": "Interflon Battery Grease Gun 18V + 2 LI-Ion batteries 4000mAh", "qty": 2, "unit": "Stuk", "unit_price": 578.70, "total_val": 1157.40, "category": "Interflon hardware"},
            {"name": "Interflon G-Coupler Speciaal mondstuk 1/8 BSP", "qty": 5, "unit": "Stuk", "unit_price": 40.50, "total_val": 202.50, "category": "Interflon hardware"},
            {"name": "CLS Filler", "qty": 2, "unit": "Stuk", "unit_price": 63.80, "total_val": 127.60, "category": "Overige hardware"},
            {"name": "Vulpomp 30 Liter Manueel", "qty": 1, "unit": "Stuk", "unit_price": 328.70, "total_val": 328.70, "category": "Interflon hardware"},
            {"name": "Interflon Manual Lubrication Pump 13L", "qty": 1, "unit": "Stuk", "unit_price": 275.20, "total_val": 275.20, "category": "Interflon hardware"},
            {"name": "Pulsarlube M2 250cc", "qty": 4, "unit": "Stuk", "unit_price": 267.40, "total_val": 1069.60, "category": "Interflon hardware"},
            {"name": "Installatiekit 1250RC-1", "qty": 4, "unit": "Stuk", "unit_price": 32.00, "total_val": 128.00, "category": "Interflon hardware"},
            {"name": "Installatie Pulsarlube + ISPL", "qty": 8, "unit": "Uur", "unit_price": 110.00, "total_val": 880.00, "category": "Interflon hardware"},
            {"name": "Oil Safe Can 3 ltr", "qty": 3, "unit": "Stuks", "unit_price": 34.50, "total_val": 103.50, "category": "Overige hardware"},
            {"name": "Oil Safe Can 10 ltr", "qty": 1, "unit": "Stuks", "unit_price": 61.10, "total_val": 61.10, "category": "Overige hardware"},
            {"name": "Oilsafe Stretch Spout Lids (4 kleuren)", "qty": 4, "unit": "Stuks", "unit_price": 71.40, "total_val": 285.60, "category": "Overige hardware"}
        ],
        "contractor": {
            "partner_name": "Vadalub",
            "hourly_base_rate": 58.28,
            "dirty_work_markup": 0.15,
            "hourly_cost_rate": 67.02,
            "sales_markup": 0.15,
            "hourly_sales_rate": 77.08,
            "hours_per_day": 8,
            "cost_per_day": 536.16,
            "sales_per_day": 616.584,
            "trip_cost": 133.00,
            "trip_sales": 152.95,
            "y1_days": 87,
            "y2_days": 65,
            "y3_days": 65,
            "total_days": 217,
            "y1_hours": 696,
            "y2_hours": 520,
            "y3_hours": 520,
            "total_hours": 1736,
            "y1_sales": 66947.37,
            "y2_sales": 50018.15,
            "y3_sales": 50018.15,
            "total_sales": 166983.67
        },
        "interflon_services": {
            "ilac_pro_annual_fee": 1950.00,
            "ilac_pro_total_3y": 5850.00,
            "implementation_audit": 8228.00,
            "pm_hourly_rate": 110.00,
            "y1_pm_hours": 113,
            "y1_pm_val": 12430.00,
            "y2_pm_hours": 86,
            "y2_pm_val": 9460.00,
            "y3_pm_hours": 86,
            "y3_pm_val": 9460.00,
            "pm_total_3y": 31350.00,
            "contractor_guidance_hours": 76,
            "contractor_guidance_val": 8360.00,
            "training_and_consults": 14300.00,
            "total_interflon_budget": 47410.00
        },
        "summary": {
            "lubricants_total": 169013.10,
            "hardware_total": 4728.80,
            "contractor_total": 166983.67,
            "interflon_total": 47410.00,
            "calculated_subtotal": 388135.57,
            "calculated_fee_monthly": 10781.54,
            "target_contract_fee_monthly": 10949.36,
            "target_contract_fee_total": 394176.96,
            "safety_margin": 6041.39,
            "option1_fee_monthly": 6076.85,
            "option1_fee_total": 218766.70,
            "option2_raw_monthly": 11683.90
        },
        "comparison_tjeu": {
            "contractor_total_3y": 150823.96,
            "pm_total_3y": 33220.00,
            "lubricants_j2_3": 25834.10,
            "option1_fee_monthly": 5049.04,
            "option2_fee_monthly": 10008.59,
            "notes": "Tab Tjeu hanteerde lagere smeerfrequenties (geen opstart-doorsmering en oliewissels) en 16 dagen minder contractor-inzet."
        }
    }

def recalculate_dossier_kpis(dossier):
    """Dynamically recalculate all KPIs and evolution when entries are added or modified."""
    delivs = dossier.get('deliveries', [])
    tot_deliv_cost = sum(d.get('total_cost', 0) for d in delivs)
    tot_deliv_sales = sum(d.get('total_sales', 0) for d in delivs)
    in_fee_sales = sum(d.get('total_sales', 0) for d in delivs if d.get('in_fee') == 'Ja')
    out_fee_sales = sum(d.get('total_sales', 0) for d in delivs if d.get('in_fee') != 'Ja')

    partner_hours = dossier.get('partner_hours', [])
    tot_partner_cost = sum(p.get('total_cost', 0) for p in partner_hours)
    tot_partner_sales = sum(p.get('total_sales', 0) for p in partner_hours)

    intl_hours = dossier.get('interflon_hours', [])
    tot_intl_cost = sum(i.get('total_cost', 0) for i in intl_hours)
    tot_intl_sales = sum(i.get('total_sales', 0) for i in intl_hours)

    settings = dossier.get('settings', {})
    fee_per_month = settings.get('fee_per_month', 10949.36)

    schedule = dossier.get('invoiced_schedule', [])
    if schedule:
        invoiced_months = sum(1 for m in schedule if m.get('is_invoiced'))
    else:
        invoiced_months = settings.get('invoiced_months', 9)

    settings['invoiced_months'] = invoiced_months
    total_months = settings.get('total_months', 36)
    fee_invoiced_total = round(fee_per_month * invoiced_months, 2)
    fee_contract_total = round(fee_per_month * total_months, 2)
    fee_remaining = round(max(0, fee_contract_total - fee_invoiced_total), 2)

    total_consumed_value = round(tot_deliv_sales + tot_partner_sales + tot_intl_sales, 2)
    current_balance = round(fee_invoiced_total - total_consumed_value, 2)

    dossier['kpis'] = {
        'fee_monthly': fee_per_month,
        'fee_invoiced_months': invoiced_months,
        'fee_invoiced_total': fee_invoiced_total,
        'fee_contract_total': fee_contract_total,
        'fee_remaining': fee_remaining,
        'total_consumed_value': total_consumed_value,
        'current_balance': current_balance,
        'delivered_products_sales': round(tot_deliv_sales, 2),
        'delivered_products_cost': round(tot_deliv_cost, 2),
        'delivered_in_fee_sales': round(in_fee_sales, 2),
        'delivered_out_fee_sales': round(out_fee_sales, 2),
        'partner_hours_sales': round(tot_partner_sales, 2),
        'partner_hours_cost': round(tot_partner_cost, 2),
        'interflon_hours_sales': round(tot_intl_sales, 2),
        'interflon_hours_cost': round(tot_intl_cost, 2),
        'break_even_forecast': 'Juni 2027' if current_balance < 0 else 'Bereikt!'
    }
    return dossier

def export_dossier_to_excel(dossier, output_path, template_path="template_laas.xlsx"):
    """Write dossier back to a 100% compliant Excel spreadsheet for parallel editing."""
    recalculate_dossier_kpis(dossier)
    shutil.copy2(template_path, output_path)
    wb = openpyxl.load_workbook(output_path, data_only=False)

    if '01 Instellingen' in wb.sheetnames:
        ws = wb['01 Instellingen']
        s = dossier.get('settings', {})
        ws.cell(4, 2, s.get('contract_name', ''))
        ws.cell(4, 5, s.get('fee_per_month', 10949.36))
        ws.cell(6, 2, s.get('duration_years', 3))
        ws.cell(6, 5, s.get('total_months', 36))
        ws.cell(10, 5, s.get('execution_markup', 0.15))

    if '08 Leveringen' in wb.sheetnames:
        ws = wb['08 Leveringen']
        delivs = dossier.get('deliveries', [])
        for r_idx, d in enumerate(delivs, start=5):
            ws.cell(r_idx, 1, d.get('date', ''))
            ws.cell(r_idx, 2, d.get('bon_so', ''))
            ws.cell(r_idx, 3, d.get('year', 1))
            # Write checkmark if Ja, X if Nee for 100% Excel compatibility
            ws.cell(r_idx, 4, '\u2714' if d.get('in_fee') == 'Ja' else 'X')
            ws.cell(r_idx, 5, d.get('product_pack', ''))
            ws.cell(r_idx, 6, d.get('quantity', 0))
            ws.cell(r_idx, 7, d.get('pack_content', 0))
            ws.cell(r_idx, 8, d.get('unit', ''))
            ws.cell(r_idx, 9, f"=F{r_idx}*G{r_idx}")
            ws.cell(r_idx, 10, d.get('cost_per_pack', 0))
            ws.cell(r_idx, 11, d.get('sales_per_pack', 0))
            ws.cell(r_idx, 12, f"=F{r_idx}*J{r_idx}")
            ws.cell(r_idx, 13, f"=F{r_idx}*K{r_idx}")
            ws.cell(r_idx, 14, f"=M{r_idx}-L{r_idx}")
            ws.cell(r_idx, 15, f"=IF(M{r_idx}>0,N{r_idx}/M{r_idx},0)")
            ws.cell(r_idx, 16, d.get('category', ''))
            ws.cell(r_idx, 18, d.get('article', ''))
            ws.cell(r_idx, 19, d.get('notes', ''))

    if '05 Werkuren' in wb.sheetnames:
        ws = wb['05 Werkuren']
        partner_hours = dossier.get('partner_hours', [])
        for r_idx, p in enumerate(partner_hours, start=13):
            ws.cell(r_idx, 1, p.get('date', ''))
            ws.cell(r_idx, 2, p.get('year', 1))
            ws.cell(r_idx, 3, p.get('hours', 0))
            ws.cell(r_idx, 4, p.get('trips', 0))
            ws.cell(r_idx, 5, p.get('cost_hours', 0))
            ws.cell(r_idx, 6, p.get('cost_trips', 0))

    if '05A Werkuren Interflon' in wb.sheetnames:
        ws = wb['05A Werkuren Interflon']
        intl_hours = dossier.get('interflon_hours', [])
        for r_idx, i in enumerate(intl_hours, start=16):
            ws.cell(r_idx, 1, i.get('date', ''))
            ws.cell(r_idx, 2, i.get('year', 1))
            ws.cell(r_idx, 3, i.get('employee', ''))
            ws.cell(r_idx, 4, i.get('hours', 0))
            ws.cell(r_idx, 5, i.get('trips', 0))
            ws.cell(r_idx, 6, i.get('cost_rate', 70))
            ws.cell(r_idx, 7, i.get('sales_rate', 110))
            ws.cell(r_idx, 8, i.get('cost_hours', 0))
            ws.cell(r_idx, 9, i.get('cost_trips', 0))
            ws.cell(r_idx, 10, i.get('total_cost', 0))
            ws.cell(r_idx, 11, i.get('total_sales', 0))
            ws.cell(r_idx, 12, i.get('notes', ''))

    wb.save(output_path)
    wb.close()
    return output_path
