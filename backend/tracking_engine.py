"""
L.A.A.S. Suite - Project Opvolgings & P&L Engine
Conforms to P&L LaaS Umicore.xlsx business logic:
- Tracking of invoiced fee vs. consumed value
- Product deliveries (within FEE vs outside FEE)
- Partner execution hours and travel days
- Interflon PM internal hours
- Partner regie hours (with contractual 15% markup)
- Dynamic invoicing schedule (1, 2, or 3 years)
- Extra generated orders outside FEE (commercial upsell)
"""

import os
import openpyxl
from datetime import datetime

def format_date_str(val):
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d')
    if val:
        return str(val)[:10]
    return datetime.now().strftime('%Y-%m-%d')

def parse_umicore_pnl_excel(excel_path):
    """
    Parses P&L LaaS Umicore.xlsx and extracts rich historical data
    for project tracking.
    """
    if not os.path.exists(excel_path):
        return None

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    
    # 1. Invoicing Schedule from '07 FEE per maand'
    invoicing_schedule = []
    if '07 FEE per maand' in wb.sheetnames:
        ws_fee = wb['07 FEE per maand']
        for r in range(5, min(41, ws_fee.max_row + 1)):
            month_name = ws_fee.cell(r, 1).value
            year = ws_fee.cell(r, 2).value
            fee_val = ws_fee.cell(r, 3).value
            invoiced_str = str(ws_fee.cell(r, 11).value or '').strip().lower()
            if month_name and year:
                is_inv = invoiced_str in ['ja', 'true', '1', 'yes']
                invoicing_schedule.append({
                    'index': len(invoicing_schedule) + 1,
                    'month_name': str(month_name),
                    'year': int(year),
                    'fee': float(fee_val or 10949.36),
                    'is_invoiced': is_inv,
                    'invoice_ref': f"INV-2026-{len(invoicing_schedule)+1:02d}" if is_inv else "",
                    'invoice_date': f"2026-{len(invoicing_schedule)+1:02d}-01" if is_inv else ""
                })

    # 2. Deliveries from '08 Leveringen'
    deliveries = []
    out_of_fee_orders = []
    if '08 Leveringen' in wb.sheetnames:
        ws_deliv = wb['08 Leveringen']
        for r in range(5, ws_deliv.max_row + 1):
            date_val = ws_deliv.cell(r, 1).value
            if not date_val:
                continue
            bon_so = str(ws_deliv.cell(r, 2).value or '').strip()
            year = int(ws_deliv.cell(r, 3).value or 1)
            in_fee_val = str(ws_deliv.cell(r, 4).value or '').strip()
            # checkmark or 'ja' means in fee, 'x' or 'nee' means out of fee
            in_fee = in_fee_val not in ['x', 'X', 'Nee', 'nee', 'false', '0']
            prod_pack = str(ws_deliv.cell(r, 5).value or '').strip()
            qty = float(ws_deliv.cell(r, 6).value or 1)
            content = float(ws_deliv.cell(r, 7).value or 0)
            unit = str(ws_deliv.cell(r, 8).value or 'stuks').strip()
            total_vol = float(ws_deliv.cell(r, 9).value or (qty * content))
            purchase_unit = float(ws_deliv.cell(r, 10).value or 0)
            sales_unit = float(ws_deliv.cell(r, 11).value or 0)
            tot_purchase = float(ws_deliv.cell(r, 12).value or (qty * purchase_unit))
            tot_sales = float(ws_deliv.cell(r, 13).value or (qty * sales_unit))
            margin = float(ws_deliv.cell(r, 14).value or (tot_sales - tot_purchase))

            item_dict = {
                'id': f"deliv_{r}",
                'date': format_date_str(date_val),
                'bon_so': bon_so,
                'year': year,
                'in_fee': in_fee,
                'product_pack': prod_pack,
                'qty': qty,
                'content_per_pack': content,
                'unit': unit,
                'total_volume': round(total_vol, 2),
                'purchase_unit': round(purchase_unit, 2),
                'sales_unit': round(sales_unit, 2),
                'total_purchase': round(tot_purchase, 2),
                'total_sales': round(tot_sales, 2),
                'margin': round(margin, 2)
            }
            deliveries.append(item_dict)

            # If out of fee, also add to out_of_fee_orders (commercial upsell)
            if not in_fee:
                out_of_fee_orders.append({
                    'id': f"oof_{r}",
                    'date': format_date_str(date_val),
                    'order_nr': bon_so,
                    'client_ref': "Reguliere bestelling buiten fee",
                    'description': prod_pack,
                    'qty': qty,
                    'unit': unit,
                    'sales_amount': round(tot_sales, 2),
                    'purchase_amount': round(tot_purchase, 2),
                    'margin': round(margin, 2),
                    'reason': "Directe bestelling klant gegenereerd via L.A.A.S. opvolging"
                })

    # 3. Regular Partner Execution Hours from '05 Werkuren'
    partner_regular_hours = []
    if '05 Werkuren' in wb.sheetnames:
        ws_wh = wb['05 Werkuren']
        for r in range(13, ws_wh.max_row + 1):
            date_val = ws_wh.cell(r, 1).value
            if not date_val:
                continue
            year = int(ws_wh.cell(r, 2).value or 1)
            hours = float(ws_wh.cell(r, 3).value or 0)
            travel_days = float(ws_wh.cell(r, 4).value or 0)
            cost_hours = float(ws_wh.cell(r, 5).value or (hours * 67.02))
            cost_travel = float(ws_wh.cell(r, 6).value or (travel_days * 133.0))
            tot_cost = cost_hours + cost_travel

            partner_regular_hours.append({
                'id': f"ptnr_{r}",
                'date': format_date_str(date_val),
                'technician': "Partner Technieker",
                'year': year,
                'hours': hours,
                'travel_days': travel_days,
                'hours_cost': round(cost_hours, 2),
                'travel_cost': round(cost_travel, 2),
                'total_cost': round(tot_cost, 2),
                'description': "Regulier periodiek smeertechnisch onderhoud"
            })

    # 4. Interflon PM Hours from '05A Werkuren Interflon'
    interflon_pm_hours = []
    if '05A Werkuren Interflon' in wb.sheetnames:
        ws_pm = wb['05A Werkuren Interflon']
        for r in range(16, ws_pm.max_row + 1):
            date_val = ws_pm.cell(r, 1).value
            if not date_val:
                continue
            year = int(ws_pm.cell(r, 2).value or 1)
            consultant = str(ws_pm.cell(r, 3).value or 'KDM').strip()
            hours = float(ws_pm.cell(r, 4).value or 0)
            travel_days = float(ws_pm.cell(r, 5).value or 0)
            cost_rate = float(ws_pm.cell(r, 6).value or 70.0)
            sales_rate = float(ws_pm.cell(r, 7).value or 110.0)
            cost_hours = float(ws_pm.cell(r, 8).value or (hours * cost_rate))
            cost_travel = float(ws_pm.cell(r, 9).value or (travel_days * 70.0))
            tot_cost = cost_hours + cost_travel
            tot_sales = round(hours * sales_rate, 2)

            interflon_pm_hours.append({
                'id': f"pm_{r}",
                'date': format_date_str(date_val),
                'consultant': consultant,
                'year': year,
                'hours': hours,
                'travel_days': travel_days,
                'cost_rate': cost_rate,
                'sales_rate': sales_rate,
                'total_cost': round(tot_cost, 2),
                'sales_value': tot_sales,
                'description': "Project Management, inspectie & auditborging"
            })

    # 5. Partner Regie Hours from '06 Regie'
    partner_regie_hours = []
    if '06 Regie' in wb.sheetnames:
        ws_reg = wb['06 Regie']
        for r in range(13, ws_reg.max_row + 1):
            date_val = ws_reg.cell(r, 1).value
            if not date_val:
                continue
            year = int(ws_reg.cell(r, 2).value or 1)
            so_af = str(ws_reg.cell(r, 3).value or '').strip()
            hours = float(ws_reg.cell(r, 4).value or 0)
            travel_days = float(ws_reg.cell(r, 5).value or 0)
            cost_hours = float(ws_reg.cell(r, 6).value or (hours * 67.02))
            cost_travel = float(ws_reg.cell(r, 7).value or (travel_days * 118.96))
            sales_hours = float(ws_reg.cell(r, 8).value or (cost_hours * 1.15))
            sales_travel = float(ws_reg.cell(r, 9).value or (cost_travel * 1.15))
            tot_cost = float(ws_reg.cell(r, 10).value or (cost_hours + cost_travel))
            tot_sales = float(ws_reg.cell(r, 11).value or (sales_hours + sales_travel))
            markup = float(ws_reg.cell(r, 12).value or (tot_sales - tot_cost))

            partner_regie_hours.append({
                'id': f"reg_{r}",
                'date': format_date_str(date_val),
                'so_af': so_af,
                'technician': "Partner Technieker (Regie)",
                'year': year,
                'hours': hours,
                'travel_days': travel_days,
                'total_cost': round(tot_cost, 2),
                'total_sales': round(tot_sales, 2),
                'markup_value': round(markup, 2),
                'markup_pct': 15.0,
                'description': "Extra regie-werkzaamheden buiten vaste fee"
            })

    # 6. Products Overview / Planned vs Delivered from '11 Productoverzicht'
    products_comparison = []
    if '11 Productoverzicht' in wb.sheetnames:
        ws11 = wb['11 Productoverzicht']
        for r in range(6, ws11.max_row + 1):
            name = ws11.cell(r, 1).value
            if not name or str(name).strip().startswith('Totaal'):
                break
            cat = str(ws11.cell(r, 2).value or 'Interflon smeermiddelen').strip()
            j1_val = round(float(ws11.cell(r, 3).value or 0), 2)
            total_val = round(float(ws11.cell(r, 4).value or 0), 2)
            deliv_val = round(float(ws11.cell(r, 5).value or 0), 2)
            in_fee_val = round(float(ws11.cell(r, 6).value or 0), 2)
            extra_val = round(float(ws11.cell(r, 7).value or 0), 2)
            plan_val = round(float(ws11.cell(r, 8).value or total_val), 2)
            diff_val = round(float(ws11.cell(r, 9).value or (total_val - deliv_val)), 2)
            raw_pct = ws11.cell(r, 10).value
            pct = round(float(raw_pct) * 100, 1) if (raw_pct is not None and float(raw_pct) <= 5.0) else round(float(raw_pct or 0), 1)
            status = str(ws11.cell(r, 11).value or ('Op plan' if pct >= 75 else '<75% geleverd')).strip()

            j2_val = round((total_val - j1_val) / 2, 2) if total_val > j1_val else 0.0
            j3_val = round((total_val - j1_val) / 2, 2) if total_val > j1_val else 0.0

            products_comparison.append({
                'id': f"prod_{r}",
                'product': str(name).strip(),
                'category': cat,
                'j1_val': j1_val,
                'j2_val': j2_val,
                'j3_val': j3_val,
                'total_val': total_val,
                'deliv_val': deliv_val,
                'deliv_j1': deliv_val,
                'deliv_j2': 0.0,
                'deliv_j3': 0.0,
                'in_fee_val': in_fee_val,
                'extra_val': extra_val,
                'diff_val': diff_val,
                'pct': pct,
                'status': status
            })

    return {
        'invoicing_schedule': invoicing_schedule,
        'deliveries': deliveries,
        'partner_regular_hours': partner_regular_hours,
        'interflon_pm_hours': interflon_pm_hours,
        'partner_regie_hours': partner_regie_hours,
        'out_of_fee_orders': out_of_fee_orders,
        'products_comparison': products_comparison
    }

def recalculate_tracking_pnl(tracking, contract_settings=None, fase2=None, ilac_calculation=None):
    """
    Computes all P&L KPIs according to P&L LaaS Umicore.xlsx logic:
    - fee_invoiced_total vs. total_consumed_value
    - current_fee_balance (invoiced - consumed)
    - break_even_forecast
    - breakdown by products, execution, PM, and out-of-fee upsell
    """
    if not tracking:
        return {}

    settings = contract_settings or {}
    duration_years = int(settings.get('duration_years', 3))
    total_months = duration_years * 12
    monthly_fee = float(settings.get('fee_per_month', 0.0))
    if monthly_fee <= 0 and fase2:
        monthly_fee = float(fase2.get('proposal_summary', {}).get('monthly_fee', 0.0))

    # Invoicing schedule
    schedule = tracking.get('invoicing_schedule', [])
    if not schedule or len(schedule) != total_months:
        # Generate default schedule if empty or mismatch in duration
        existing_map = {m.get('index'): m for m in schedule}
        month_names = ['Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec']
        new_sched = []
        for idx in range(1, total_months + 1):
            yr = ((idx - 1) // 12) + 1
            m_name = month_names[(idx - 1) % 12]
            prev = existing_map.get(idx)
            is_inv = prev.get('is_invoiced', False) if prev else False
            inv_ref = prev.get('invoice_ref', '') if prev else ""
            inv_date = prev.get('invoice_date', '') if prev else ""
            f_val = prev.get('fee', monthly_fee) if prev else monthly_fee
            new_sched.append({
                'index': idx,
                'month_name': m_name,
                'year': yr,
                'fee': round(float(f_val), 2),
                'is_invoiced': is_inv,
                'invoice_ref': inv_ref,
                'invoice_date': inv_date
            })
        schedule = new_sched
        tracking['invoicing_schedule'] = schedule

    invoiced_months = sum(1 for m in schedule if m.get('is_invoiced'))
    fee_invoiced_total = round(sum(m.get('fee', monthly_fee) for m in schedule if m.get('is_invoiced')), 2)
    fee_contract_total = round(monthly_fee * total_months, 2)
    fee_remaining = round(max(0.0, fee_contract_total - fee_invoiced_total), 2)

    # Deliveries (Products)
    deliveries = tracking.get('deliveries', [])
    deliv_in_fee_sales = round(sum(d.get('total_sales', 0.0) for d in deliveries if d.get('in_fee', True)), 2)
    deliv_in_fee_cost = round(sum(d.get('total_purchase', 0.0) for d in deliveries if d.get('in_fee', True)), 2)
    deliv_out_fee_sales = round(sum(d.get('total_sales', 0.0) for d in deliveries if not d.get('in_fee', True)), 2)
    deliv_out_fee_cost = round(sum(d.get('total_purchase', 0.0) for d in deliveries if not d.get('in_fee', True)), 2)

    # Partner Regular Hours
    partner_hours = tracking.get('partner_regular_hours', [])
    partner_reg_cost = round(sum(p.get('total_cost', 0.0) for p in partner_hours), 2)
    partner_reg_hours_total = round(sum(p.get('hours', 0.0) for p in partner_hours), 1)
    partner_reg_travel_days_total = round(sum(p.get('travel_days', 0.0) for p in partner_hours), 1)

    # Partner Regie Hours
    regie_hours = tracking.get('partner_regie_hours', [])
    regie_cost_total = round(sum(r.get('total_cost', 0.0) for r in regie_hours), 2)
    regie_sales_total = round(sum(r.get('total_sales', 0.0) for r in regie_hours), 2)
    regie_markup_total = round(sum(r.get('markup_value', 0.0) for r in regie_hours), 2)
    regie_hours_count = round(sum(r.get('hours', 0.0) for r in regie_hours), 1)

    # Interflon PM Hours
    pm_hours = tracking.get('interflon_pm_hours', [])
    pm_cost_total = round(sum(m.get('total_cost', 0.0) for m in pm_hours), 2)
    pm_sales_total = round(sum(m.get('sales_value', 0.0) for m in pm_hours), 2)
    pm_hours_count = round(sum(m.get('hours', 0.0) for m in pm_hours), 1)

    # Out-of-fee orders (Commercial upsell generated by L.A.A.S.)
    oof_orders = tracking.get('out_of_fee_orders', [])
    oof_sales_total = round(sum(o.get('sales_amount', 0.0) for o in oof_orders), 2)
    oof_cost_total = round(sum(o.get('purchase_amount', 0.0) for o in oof_orders), 2)
    oof_margin_total = round(sum(o.get('margin', 0.0) for o in oof_orders), 2)

    # Total Consumed Value against the FEE
    # (In-fee delivered products + Partner regular cost + PM sales value)
    total_consumed_value = round(deliv_in_fee_sales + partner_reg_cost + pm_cost_total, 2)
    
    # Current FEE Balance: what customer has been invoiced minus what was delivered/consumed
    current_fee_balance = round(fee_invoiced_total - total_consumed_value, 2)

    # Total Gross Operational Result (including regie margin + out-of-fee margin)
    total_operational_margin = round(current_fee_balance + regie_markup_total + oof_margin_total, 2)

    # Break-even projection
    # If currently negative (startup investment in products/hours in year 1),
    # project when cumulative fees overtake cumulative costs.
    avg_monthly_consumption = (total_consumed_value / invoiced_months) if invoiced_months > 0 else (monthly_fee * 0.7)
    net_monthly_gain = monthly_fee - avg_monthly_consumption

    break_even_forecast = "Bereikt (Positief)"
    if current_fee_balance < 0:
        if net_monthly_gain > 0:
            months_needed = int(abs(current_fee_balance) / net_monthly_gain) + 1
            be_month_idx = min(total_months, invoiced_months + months_needed)
            break_even_forecast = f"Verwacht in Maand {be_month_idx} (ca. {schedule[be_month_idx-1]['month_name']} {schedule[be_month_idx-1]['year']})"
        else:
            break_even_forecast = "Aandacht vereist (Verbruik > Fee)"

    # Products comparison: Planned vs Delivered (Voorzien vs. Geleverd)
    products_comp = tracking.get('products_comparison', [])
    if not products_comp and ilac_calculation and ilac_calculation.get('aggregated_products'):
        agg_prods = ilac_calculation.get('aggregated_products', [])
        new_comp = []
        for idx, item in enumerate(agg_prods):
            p_name = item.get('product_name') or item.get('description', f'Artikel {idx+1}')
            tot_val = round(float(item.get('line_total') or 0.0), 2)
            j1 = round(tot_val / duration_years, 2)
            j2 = round(tot_val / duration_years, 2) if duration_years >= 2 else 0.0
            j3 = round(tot_val / duration_years, 2) if duration_years >= 3 else 0.0
            new_comp.append({
                'id': f"prod_agg_{idx+1}",
                'product': p_name,
                'category': item.get('category', 'Smeermiddelen'),
                'packaging': item.get('packaging', ''),
                'j1_val': j1,
                'j2_val': j2,
                'j3_val': j3,
                'total_val': tot_val,
                'deliv_val': 0.0,
                'deliv_j1': 0.0,
                'deliv_j2': 0.0,
                'deliv_j3': 0.0,
                'in_fee_val': 0.0,
                'extra_val': 0.0,
                'diff_val': tot_val,
                'pct': 0.0,
                'status': 'Nog niet geleverd'
            })
        products_comp = new_comp
        tracking['products_comparison'] = products_comp

    # Ensure deliveries are synchronized into products_comp
    if products_comp and deliveries:
        for p in products_comp:
            p_norm = p['product'].strip().lower()
            # find all matching deliveries
            matches = [d for d in deliveries if p_norm in d.get('product_pack', '').lower() or d.get('product_pack', '').lower() in p_norm]
            if matches:
                tot_d = round(sum(d.get('total_sales', 0.0) for d in matches), 2)
                j1_d = round(sum(d.get('total_sales', 0.0) for d in matches if d.get('year', 1) == 1), 2)
                j2_d = round(sum(d.get('total_sales', 0.0) for d in matches if d.get('year', 1) == 2), 2)
                j3_d = round(sum(d.get('total_sales', 0.0) for d in matches if d.get('year', 1) == 3), 2)
                in_f = round(sum(d.get('total_sales', 0.0) for d in matches if d.get('in_fee', True)), 2)
                out_f = round(sum(d.get('total_sales', 0.0) for d in matches if not d.get('in_fee', True)), 2)
                
                # Keep largest of parsed Excel deliv_val or live deliveries sum
                if tot_d >= p.get('deliv_val', 0.0):
                    p['deliv_val'] = tot_d
                    p['deliv_j1'] = j1_d
                    p['deliv_j2'] = j2_d
                    p['deliv_j3'] = j3_d
                    p['in_fee_val'] = in_f
                    p['extra_val'] = out_f
                    p['diff_val'] = round(p['total_val'] - tot_d, 2)
                    p['pct'] = round((tot_d / p['total_val']) * 100, 1) if p['total_val'] > 0 else 100.0
                    if p['pct'] > 105:
                        p['status'] = f"Boven plan (+{round(p['pct'] - 100, 1)}%)"
                    elif p['pct'] >= 75:
                        p['status'] = "Op plan"
                    elif p['pct'] > 0:
                        p['status'] = "<75% geleverd"
                    else:
                        p['status'] = "Nog niet geleverd"

    tracking['products_comparison'] = products_comp


    pnl_summary = {
        'duration_years': duration_years,
        'total_months': total_months,
        'monthly_fee': monthly_fee,
        'invoiced_months': invoiced_months,
        'fee_invoiced_total': fee_invoiced_total,
        'fee_contract_total': fee_contract_total,
        'fee_remaining': fee_remaining,
        
        # Consumed Breakdown
        'total_consumed_value': total_consumed_value,
        'current_fee_balance': current_fee_balance,
        'break_even_forecast': break_even_forecast,
        
        'products_in_fee_sales': deliv_in_fee_sales,
        'products_in_fee_cost': deliv_in_fee_cost,
        'products_out_fee_sales': deliv_out_fee_sales,
        'products_out_fee_cost': deliv_out_fee_cost,
        
        'partner_reg_cost': partner_reg_cost,
        'partner_reg_hours': partner_reg_hours_total,
        'partner_reg_travel_days': partner_reg_travel_days_total,
        
        'regie_cost': regie_cost_total,
        'regie_sales': regie_sales_total,
        'regie_markup': regie_markup_total,
        'regie_hours': regie_hours_count,
        
        'interflon_pm_cost': pm_cost_total,
        'interflon_pm_sales': pm_sales_total,
        'interflon_pm_hours': pm_hours_count,
        
        # Out of fee commercial impact
        'out_of_fee_sales': oof_sales_total,
        'out_of_fee_cost': oof_cost_total,
        'out_of_fee_margin': oof_margin_total,
        
        'total_operational_margin': total_operational_margin
    }

    tracking['pnl_summary'] = pnl_summary
    return pnl_summary

def export_tracking_to_excel(dossier, output_path):
    """
    Generates a clean, professional multi-tab Excel workbook containing
    the full tracking dashboard & P&L.
    """
    wb = openpyxl.Workbook()
    # Sheet 1: Cockpit & P&L
    ws_kpi = wb.active
    ws_kpi.title = "Cockpit & P&L"
    
    tracking = dossier.get('tracking', {})
    pnl = tracking.get('pnl_summary', {})
    cust = dossier.get('customer', 'Klant')
    dept = dossier.get('department', 'Afdeling')
    con_name = dossier.get('contract_name', 'Contract')
    
    ws_kpi['A1'] = f"L.A.A.S. Project Opvolging & P&L - {cust} ({dept})"
    ws_kpi['A2'] = f"Contract: {con_name} | Looptijd: {pnl.get('duration_years', 3)} Jaar ({pnl.get('total_months', 36)} Maanden)"
    ws_kpi['A4'] = "Financiële Cockpit KPI"
    ws_kpi['B4'] = "Waarde (€)"
    ws_kpi['C4'] = "Toelichting"
    
    rows = [
        ("Vaste Maandelijkse FEE", pnl.get('monthly_fee', 0.0), "Overeengekomen maandelijkse contractfee"),
        ("Gefactureerde Maanden", pnl.get('invoiced_months', 0), f"Tot heden {pnl.get('invoiced_months', 0)} van {pnl.get('total_months', 36)} maanden gefactureerd"),
        ("Reeds Gefactureerde FEE", pnl.get('fee_invoiced_total', 0.0), "Totale gefactureerde omzet"),
        ("Totale Contractwaarde", pnl.get('fee_contract_total', 0.0), "Totale contractwaarde volledige looptijd"),
        ("Nog te Factureren FEE", pnl.get('fee_remaining', 0.0), "Resterend te factureren contractsaldo"),
        ("Totale Opgenomen Waarde", pnl.get('total_consumed_value', 0.0), "Totale waarde van geleverde producten, uren en PM"),
        ("Huidig FEE Saldo", pnl.get('current_fee_balance', 0.0), "FEE gefactureerd minus totale opgenomen waarde"),
        ("Break-Even Status", pnl.get('break_even_forecast', ''), "Verwachte break-even trend"),
        ("Extra Omzet Buiten FEE", pnl.get('out_of_fee_sales', 0.0), "Extra gegenereerde orders dankzij L.A.A.S. werking"),
        ("Gegenereerde Marge Buiten FEE", pnl.get('out_of_fee_margin', 0.0), "Brutomarge op extra orders")
    ]
    
    for idx, (lbl, val, note) in enumerate(rows, start=5):
        ws_kpi.cell(idx, 1, lbl)
        ws_kpi.cell(idx, 2, val)
        ws_kpi.cell(idx, 3, note)

    # Sheet 2: Leveringen
    ws_deliv = wb.create_sheet(title="Producten & Leveringen")
    ws_deliv.append(["Datum", "Bon / SO", "Contractjaar", "In FEE?", "Product / Verpakking", "Aantal", "Geleverde Hoeveelheid", "Eenheid", "Inkoopkost (€)", "Verkoopwaarde (€)", "Marge (€)"])
    for d in tracking.get('deliveries', []):
        ws_deliv.append([
            d.get('date', ''),
            d.get('bon_so', ''),
            d.get('year', 1),
            "Ja" if d.get('in_fee') else "Nee",
            d.get('product_pack', ''),
            d.get('qty', 1),
            d.get('total_volume', 0),
            d.get('unit', 'stuks'),
            d.get('total_purchase', 0.0),
            d.get('total_sales', 0.0),
            d.get('margin', 0.0)
        ])

    # Sheet 3: Urenregistratie
    ws_hrs = wb.create_sheet(title="Urenregistratie")
    ws_hrs.append(["Categorie", "Datum", "Medewerker / SO", "Uren", "Reisdagen", "Kost (€)", "Verkoopwaarde / Facturatie (€)", "Omschrijving"])
    for pm in tracking.get('interflon_pm_hours', []):
        ws_hrs.append(["Interflon PM", pm.get('date', ''), pm.get('consultant', ''), pm.get('hours', 0), pm.get('travel_days', 0), pm.get('total_cost', 0.0), pm.get('sales_value', 0.0), pm.get('description', '')])
    for pt in tracking.get('partner_regular_hours', []):
        ws_hrs.append(["Partner Regulier", pt.get('date', ''), pt.get('technician', ''), pt.get('hours', 0), pt.get('travel_days', 0), pt.get('total_cost', 0.0), "-", pt.get('description', '')])
    for rg in tracking.get('partner_regie_hours', []):
        ws_hrs.append(["Partner Regie (+15%)", rg.get('date', ''), rg.get('so_af', ''), rg.get('hours', 0), rg.get('travel_days', 0), rg.get('total_cost', 0.0), rg.get('total_sales', 0.0), rg.get('description', '')])

    # Sheet 4: Facturatieschema
    ws_inv = wb.create_sheet(title="Facturatieschema")
    ws_inv.append(["Index", "Maand", "Contractjaar", "Vaste FEE (€)", "Gefactureerd?", "Factuurreferentie", "Factuurdatum"])
    for m in tracking.get('invoicing_schedule', []):
        ws_inv.append([
            m.get('index', 1),
            m.get('month_name', ''),
            m.get('year', 1),
            m.get('fee', 0.0),
            "Ja" if m.get('is_invoiced') else "Nee",
            m.get('invoice_ref', ''),
            m.get('invoice_date', '')
        ])

    # Sheet 5: Orders Buiten L.A.A.S.
    ws_oof = wb.create_sheet(title="Extra Orders Buiten FEE")
    ws_oof.append(["Datum", "Order / Bon", "Klant Referentie", "Omschrijving", "Aantal", "Eenheid", "Verkoopwaarde (€)", "Inkoopkost (€)", "Marge (€)", "Aanleiding / Toelichting"])
    for o in tracking.get('out_of_fee_orders', []):
        ws_oof.append([
            o.get('date', ''),
            o.get('order_nr', ''),
            o.get('client_ref', ''),
            o.get('description', ''),
            o.get('qty', 1),
            o.get('unit', 'stuks'),
            o.get('sales_amount', 0.0),
            o.get('purchase_amount', 0.0),
            o.get('margin', 0.0),
            o.get('reason', '')
        ])

    wb.save(output_path)
    return True
