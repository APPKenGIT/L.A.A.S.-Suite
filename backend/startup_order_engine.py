import os
import math
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from backend.ilac_engine import parse_ilac_volume

def calculate_startup_order(dossier, months=3, include_hardware=True):
    """
    Calculates the required start-up order based on the contract's ILAC calculation
    and Phase 2 data for a configurable period of X months.

    Calculation rules:
    - Recurring tasks (smeren, controle, inspectie): scaled to (months / 12.0) of annual volume.
    - One-off tasks (doorsmeren, initiële vulling, initial cleanings): 100% of volume is included.
    - Quantities are rounded UP to full packs / units (ceil).
    - If include_hardware=True, items from Fase 2 material groups (guns, pumps, cans) are added.
    """
    if not dossier:
        return {"items": [], "summary": {}}

    months = max(1, min(36, int(months)))
    fraction = months / 12.0

    ilac_calc = dossier.get('ilac_calculation', {})
    pricelist = dossier.get('price_list', {}).get('items', [])
    settings = dossier.get('settings', {})
    gram_per_pompslag = float(settings.get('gram_per_pompslag', 1.5))
    ml_per_second = float(settings.get('ml_per_second', 1.0))
    duration_years = int(settings.get('duration_years', 3))
    contract_days = duration_years * 365.25

    points = ilac_calc.get('points', [])
    agg_prods = ilac_calc.get('aggregated_products', [])
    global_discount_pct = float(settings.get('global_discount_pct', 0.0))

    # 1. Collect one-off volumes (doorsmeren, initiële opstart) and recurring annual volumes per combo_key
    one_off_by_combo = {}
    recurring_by_combo = {}

    if points:
        for pt in points:
            prod = (pt.get('product_name') or '').strip()
            tool = (pt.get('tool') or 'Manueel').strip()
            count = int(pt.get('point_count', 1))
            remark = (pt.get('short_remark') or '').lower()

            if not prod or prod.lower() in ['niet van toepassing', 'none', '-']:
                continue

            vol_raw = pt.get('volume_raw', '')
            if vol_raw:
                vol_std, std_unit, _ = parse_ilac_volume(vol_raw, gram_per_pompslag=gram_per_pompslag, ml_per_second=ml_per_second)
            else:
                vol_std = pt.get('volume_numeric', 0.0)
                std_unit = pt.get('volume_unit', 'unit')

            combo_key = f"{prod}___{tool}"
            one_off_by_combo.setdefault(combo_key, 0.0)
            recurring_by_combo.setdefault(combo_key, 0.0)

            for t in pt.get('tasks', []):
                tname = t.get('task_name', '')
                interval_d = t.get('interval_days', 365.0)
                freq = t.get('annual_frequency', 1.0)

                is_doorsmeren = any(k in tname.lower() or k in remark for k in ['doorsmeer', 'initiëel', 'initieel', 'opstart', 'inbedrijf'])
                is_one_off = is_doorsmeren or ((interval_d >= contract_days - 0.5) if duration_years > 1 else (interval_d > 365.5))
                is_reservoir_check = ('bijvullen' in tname.lower() or 'top-up' in remark or 'indien nodig' in remark) and interval_d <= 14 and vol_std >= 1.0 and std_unit == 'L'

                if is_reservoir_check:
                    recurring_by_combo[combo_key] += (count * max(0.5, vol_std * 0.15))
                elif is_one_off:
                    one_off_by_combo[combo_key] += (count * vol_std)
                else:
                    recurring_by_combo[combo_key] += (count * vol_std * freq)

    startup_items = []

    # 2. Build startup items from aggregated products to guarantee consistency with calculation
    if agg_prods:
        for idx, p in enumerate(agg_prods, 1):
            art_nr = p.get('article_nr', '-')
            if art_nr == '-':
                continue

            prod_name = p.get('product_name', '')
            tool = p.get('tool', 'Manueel')
            combo_key = p.get('combo_key', f"{prod_name}___{tool}")
            cat = p.get('category', 'Smeermiddelen')
            pack_desc = p.get('packaging', 'stuks')
            ann_vol = float(p.get('annual_volume_numeric', 0.0) or 0.0)
            prod_unit = p.get('volume_unit', 'g')

            # Fetch one-off volume if present in points
            one_off_amt = one_off_by_combo.get(combo_key, 0.0)
            # Startup needed volume: fraction of recurring + 100% of one-off
            startup_vol = (ann_vol * fraction) + one_off_amt

            cand = p.get('candidate_packagings', [])
            matched_cand = next((c for c in cand if str(c.get('article_nr')) == str(art_nr)), None)
            if matched_cand:
                pack_val = float(matched_cand.get('volume_val') or 1.0)
                pack_u = matched_cand.get('volume_unit') or prod_unit
            else:
                pack_val = 1.0
                pack_u = prod_unit

            packs_needed = 0
            if startup_vol > 0:
                if prod_unit == pack_u:
                    packs_needed = math.ceil(startup_vol / pack_val) if pack_val > 0 else math.ceil(startup_vol)
                elif prod_unit == 'ml' and pack_u == 'L':
                    packs_needed = math.ceil((startup_vol / 1000.0) / pack_val) if pack_val > 0 else math.ceil(startup_vol / 1000.0)
                elif prod_unit == 'L' and pack_u == 'ml':
                    packs_needed = math.ceil((startup_vol * 1000.0) / pack_val) if pack_val > 0 else math.ceil(startup_vol)
                elif prod_unit == 'g' and pack_u in ['kg', 'L']:
                    packs_needed = math.ceil((startup_vol / 1000.0) / pack_val) if pack_val > 0 else math.ceil(startup_vol / 1000.0)
                else:
                    packs_needed = math.ceil(startup_vol / pack_val) if pack_val > 0 else math.ceil(startup_vol)

            packs_needed = max(1, packs_needed)
            net_p = float(p.get('net_unit_price', 0.0))
            base_p = float(p.get('base_unit_price', net_p))
            disc_pct = float(p.get('discount_pct', 0.0))
            line_tot = round(packs_needed * net_p, 2)
            purch_unit = round(net_p * 0.55, 2)
            tot_purch = round(packs_needed * purch_unit, 2)

            startup_items.append({
                'id': f"item_{len(startup_items)+1}",
                'item_type': 'consumable',
                'article_nr': art_nr,
                'product_name': prod_name,
                'description': f"{prod_name} - {pack_desc}".strip(),
                'tool': tool,
                'category': cat,
                'packaging': pack_desc,
                'pack_volume': pack_val,
                'pack_unit': pack_u,
                'needed_volume_raw': round(startup_vol, 2),
                'volume_unit': prod_unit,
                'one_off_volume': round(one_off_amt, 2),
                'recurring_volume': round(ann_vol * fraction, 2),
                'qty': packs_needed,
                'suggested_qty': packs_needed,
                'base_unit_price': base_p,
                'discount_pct': disc_pct,
                'net_unit_price': net_p,
                'line_total': line_tot,
                'purchase_unit': purch_unit,
                'total_purchase': tot_purch,
                'margin': round(line_tot - tot_purch, 2)
            })

    # 3. Add Hardware & Tools from Fase 2 if requested
    if include_hardware:
        fase2 = dossier.get('fase2', {})
        mat_groups = fase2.get('material_groups', [])
        for grp in mat_groups:
            for m in grp.get('materials', []):
                qty = int(m.get('qty', 1))
                if qty <= 0:
                    continue
                price = float(m.get('unit_price', 0.0))
                disc = float(m.get('discount_pct', global_discount_pct))
                net_p = round(price * (1.0 - max(0.0, min(100.0, disc)) / 100.0), 2)
                line_tot = round(qty * net_p, 2)
                purch_unit = float(m.get('purchase_unit') or (net_p * 0.6))
                tot_purch = round(qty * purch_unit, 2)

                startup_items.append({
                    'id': f"hw_{len(startup_items)+1}",
                    'item_type': 'hardware',
                    'article_nr': str(m.get('article_nr', '')),
                    'product_name': m.get('description', 'Hardware/Tool'),
                    'description': m.get('description', 'Hardware/Tool'),
                    'tool': 'Hardware & Tools',
                    'category': m.get('category', 'Hardware & Tools'),
                    'packaging': m.get('unit', 'Stuks'),
                    'pack_volume': 1.0,
                    'pack_unit': 'Stuks',
                    'needed_volume_raw': qty,
                    'volume_unit': 'Stuks',
                    'one_off_volume': qty,
                    'recurring_volume': 0.0,
                    'qty': qty,
                    'suggested_qty': qty,
                    'base_unit_price': price,
                    'discount_pct': disc,
                    'net_unit_price': net_p,
                    'line_total': line_tot,
                    'purchase_unit': purch_unit,
                    'total_purchase': tot_purch,
                    'margin': round(line_tot - tot_purch, 2)
                })

    tot_sales = round(sum(it['line_total'] for it in startup_items), 2)
    tot_purchase = round(sum(it['total_purchase'] for it in startup_items), 2)
    tot_units = sum(it['qty'] for it in startup_items)
    tot_consumables = sum(it['qty'] for it in startup_items if it.get('item_type') == 'consumable')
    tot_hardware = sum(it['qty'] for it in startup_items if it.get('item_type') == 'hardware')

    summary = {
        'months': months,
        'include_hardware': include_hardware,
        'total_items_count': len(startup_items),
        'total_units': tot_units,
        'consumables_units': tot_consumables,
        'hardware_units': tot_hardware,
        'total_sales_value': tot_sales,
        'total_purchase_cost': tot_purchase,
        'total_margin': round(tot_sales - tot_purchase, 2)
    }

    return {
        'summary': summary,
        'items': startup_items,
        'customer': dossier.get('customer', ''),
        'department': dossier.get('department', ''),
        'contract_name': dossier.get('contract_name', ''),
        'calculated_at': datetime.now().isoformat()
    }


def generate_startup_order_excel(order_data, output_path):
    """
    Generates a clean, professional Excel workbook for the Start-up Order.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Start-up Order"

    BORDER_COLOR = "CBD5E1"
    font_title = Font(name="Calibri", size=16, bold=True, color="0F172A")
    font_subtitle = Font(name="Calibri", size=10, bold=False, color="64748B")
    font_section = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_header = Font(name="Calibri", size=10, bold=True, color="0F172A")
    font_data = Font(name="Calibri", size=10, bold=False, color="1E293B")
    font_data_bold = Font(name="Calibri", size=10, bold=True, color="0F172A")
    font_mono = Font(name="Consolas", size=10, bold=False, color="1E293B")
    font_mono_bold = Font(name="Consolas", size=10, bold=True, color="0F172A")

    fill_section = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    fill_header = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    fill_alt = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_total = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color=BORDER_COLOR),
        right=Side(style='thin', color=BORDER_COLOR),
        top=Side(style='thin', color=BORDER_COLOR),
        bottom=Side(style='thin', color=BORDER_COLOR)
    )

    cust = order_data.get('customer', 'Klant')
    dept = order_data.get('department', 'Afdeling')
    con_name = order_data.get('contract_name', 'Contract')
    summary = order_data.get('summary', {})
    months = summary.get('months', 3)
    order_date = datetime.now().strftime('%d-%m-%Y %H:%M')

    ws['A1'] = "INTERFLON L.A.A.S. - START-UP ORDER / BESTELBON"
    ws['A1'].font = font_title
    ws['A2'] = f"Klant: {cust} | Afdeling: {dept} | Contract: {con_name} | Besteldatum: {order_date}"
    ws['A2'].font = font_subtitle
    ws['A3'] = f"Bufferperiode: {months} Maanden opstartvoorraad (inclusief 100% eenmalige taken & doorsmeren)"
    ws['A3'].font = Font(name="Calibri", size=10, bold=True, color="059669")

    # KPI Summary block
    ws['A5'] = "Type"
    ws['B5'] = "Aantal Artikelen"
    ws['C5'] = "Totaal Units"
    ws['D5'] = "Totale Verkoopwaarde (€)"
    ws['E5'] = "Totale Inkoopkost (€)"
    for col in ['A', 'B', 'C', 'D', 'E']:
        c = ws[f'{col}5']
        c.font = font_section
        c.fill = fill_section
        c.alignment = Alignment(horizontal='center' if col != 'A' else 'left')

    consumables = [it for it in order_data.get('items', []) if it.get('item_type') == 'consumable']
    hardware = [it for it in order_data.get('items', []) if it.get('item_type') == 'hardware']

    ws['A6'] = "Smeermiddelen & Reinigers"
    ws['B6'] = len(consumables)
    ws['C6'] = sum(it.get('qty', 0) for it in consumables)
    ws['D6'] = round(sum(it.get('line_total', 0.0) for it in consumables), 2)
    ws['E6'] = round(sum(it.get('total_purchase', 0.0) for it in consumables), 2)

    ws['A7'] = "Hardware, Pompen & Tools"
    ws['B7'] = len(hardware)
    ws['C7'] = sum(it.get('qty', 0) for it in hardware)
    ws['D7'] = round(sum(it.get('line_total', 0.0) for it in hardware), 2)
    ws['E7'] = round(sum(it.get('total_purchase', 0.0) for it in hardware), 2)

    ws['A8'] = "TOTAAL START-UP ORDER"
    ws['B8'] = summary.get('total_items_count', len(order_data.get('items', [])))
    ws['C8'] = summary.get('total_units', sum(it.get('qty', 0) for it in order_data.get('items', [])))
    ws['D8'] = summary.get('total_sales_value', round(sum(it.get('line_total', 0.0) for it in order_data.get('items', [])), 2))
    ws['E8'] = summary.get('total_purchase_cost', round(sum(it.get('total_purchase', 0.0) for it in order_data.get('items', [])), 2))

    for r in [6, 7, 8]:
        for c in range(1, 6):
            cell = ws.cell(r, c)
            cell.border = thin_border
            if r == 8:
                cell.font = font_data_bold
                cell.fill = fill_total
            else:
                cell.font = font_data
            if c in [2, 3]:
                cell.alignment = Alignment(horizontal='center')
            elif c in [4, 5]:
                cell.alignment = Alignment(horizontal='right')
                cell.number_format = '€ #,##0.00'

    # Items Table
    headers = [
        "Nr", "Art. Nr", "Omschrijving / Product", "Categorie", "Verpakking / Eenheid",
        "Tool / Toepassing", "Aantal Units", "Netto Prijs / St (excl)", "Totaal Bedrag (€)"
    ]
    start_row = 11
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(start_row, col_idx, h)
        cell.font = font_header
        cell.fill = fill_header
        cell.border = thin_border
        if col_idx in [1, 2, 7]:
            cell.alignment = Alignment(horizontal='center')
        elif col_idx in [8, 9]:
            cell.alignment = Alignment(horizontal='right')
        else:
            cell.alignment = Alignment(horizontal='left')

    cur_row = start_row + 1
    for idx, item in enumerate(order_data.get('items', []), 1):
        row_cells = [
            ws.cell(cur_row, 1, idx),
            ws.cell(cur_row, 2, item.get('article_nr', '')),
            ws.cell(cur_row, 3, item.get('description') or item.get('product_name', '')),
            ws.cell(cur_row, 4, item.get('category', '')),
            ws.cell(cur_row, 5, item.get('packaging', 'stuks')),
            ws.cell(cur_row, 6, item.get('tool', '')),
            ws.cell(cur_row, 7, item.get('qty', 1)),
            ws.cell(cur_row, 8, item.get('net_unit_price', 0.0)),
            ws.cell(cur_row, 9, item.get('line_total', 0.0))
        ]

        is_alt = (idx % 2 == 0)
        for c_idx, cell in enumerate(row_cells, 1):
            cell.border = thin_border
            cell.font = font_data
            if is_alt:
                cell.fill = fill_alt

            if c_idx in [1, 2]:
                cell.alignment = Alignment(horizontal='center')
                cell.font = font_mono
            elif c_idx == 7:
                cell.alignment = Alignment(horizontal='center')
                cell.font = font_data_bold
            elif c_idx in [8, 9]:
                cell.alignment = Alignment(horizontal='right')
                cell.font = font_mono_bold if c_idx == 9 else font_mono
                cell.number_format = '€ #,##0.00'

        cur_row += 1

    # Total Row
    tot_cell_label = ws.cell(cur_row, 6, "TOTAAL EXCL. BTW:")
    tot_cell_label.font = font_data_bold
    tot_cell_label.alignment = Alignment(horizontal='right')

    tot_units_val = sum(it.get('qty', 0) for it in order_data.get('items', []))
    tot_units_cell = ws.cell(cur_row, 7, tot_units_val)
    tot_units_cell.font = font_data_bold
    tot_units_cell.alignment = Alignment(horizontal='center')
    tot_units_cell.fill = fill_total
    tot_units_cell.border = thin_border

    tot_sales_val = round(sum(it.get('line_total', 0.0) for it in order_data.get('items', [])), 2)
    tot_val_cell = ws.cell(cur_row, 9, tot_sales_val)
    tot_val_cell.font = Font(name="Consolas", size=11, bold=True, color="047857")
    tot_val_cell.alignment = Alignment(horizontal='right')
    tot_val_cell.fill = fill_total
    tot_val_cell.border = thin_border
    tot_val_cell.number_format = '€ #,##0.00'

    col_widths = {1: 6, 2: 12, 3: 40, 4: 22, 5: 22, 6: 18, 7: 14, 8: 18, 9: 20}
    for col_idx, width in col_widths.items():
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb.save(output_path)
    return output_path


def generate_startup_order_pdf(order_data, output_path):
    """
    Generates a clean, professional PDF document for the Start-up Order via ReportLab.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=30,
        rightMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'OrderTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A')
    )
    subtitle_style = ParagraphStyle(
        'OrderSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569')
    )
    th_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#FFFFFF')
    )
    td_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )
    td_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0F172A')
    )
    td_right = ParagraphStyle(
        'TableCellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=2,
        textColor=colors.HexColor('#1E293B')
    )
    td_right_bold = ParagraphStyle(
        'TableCellRightBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=2,
        textColor=colors.HexColor('#0F172A')
    )

    elements = []

    cust = order_data.get('customer', 'Klant')
    dept = order_data.get('department', 'Afdeling')
    con_name = order_data.get('contract_name', 'Contract')
    summary = order_data.get('summary', {})
    months = summary.get('months', 3)
    order_date = datetime.now().strftime('%d-%m-%Y')

    tot_units_val = sum(it.get('qty', 0) for it in order_data.get('items', []))
    tot_sales_val = round(sum(it.get('line_total', 0.0) for it in order_data.get('items', [])), 2)

    elements.append(Paragraph("INTERFLON L.A.A.S. - START-UP ORDER", title_style))
    elements.append(Paragraph(f"<b>Klant:</b> {cust} &nbsp;|&nbsp; <b>Afdeling:</b> {dept} &nbsp;|&nbsp; <b>Contract:</b> {con_name} &nbsp;|&nbsp; <b>Datum:</b> {order_date}", subtitle_style))
    elements.append(Paragraph(f"<b>Gecalculeerde Bufferperiode:</b> {months} Maanden initiële opstartvoorraad (inclusief 100% eenmalige taken & doorsmeren)", subtitle_style))
    elements.append(Spacer(1, 14))

    # Summary table
    kpi_data = [
        [
            Paragraph("<b>Bufferperiode:</b>", td_style),
            Paragraph(f"{months} Maanden", td_bold),
            Paragraph("<b>Totale Verkoopwaarde:</b>", td_style),
            Paragraph(f"<b>€ {tot_sales_val:,.2f}</b>", td_bold)
        ],
        [
            Paragraph("<b>Totaal Artikelen:</b>", td_style),
            Paragraph(f"{len(order_data.get('items', []))} artikelen", td_bold),
            Paragraph("<b>Totaal Besteleenheden:</b>", td_style),
            Paragraph(f"<b>{tot_units_val} verpakkingen / stuks</b>", td_bold)
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[110, 150, 130, 145])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 16))

    # Items table
    headers = [
        Paragraph("#", th_style),
        Paragraph("Art. Nr", th_style),
        Paragraph("Omschrijving / Product", th_style),
        Paragraph("Categorie", th_style),
        Paragraph("Verpakking", th_style),
        Paragraph("Aantal", th_style),
        Paragraph("Netto St (€)", th_style),
        Paragraph("Totaal (€)", th_style)
    ]
    table_data = [headers]

    for idx, item in enumerate(order_data.get('items', []), 1):
        table_data.append([
            Paragraph(str(idx), td_style),
            Paragraph(str(item.get('article_nr', '-')), td_style),
            Paragraph(str(item.get('description') or item.get('product_name', '')), td_bold),
            Paragraph(str(item.get('category', '')), td_style),
            Paragraph(str(item.get('packaging', 'stuks')), td_style),
            Paragraph(str(item.get('qty', 1)), td_bold),
            Paragraph(f"€ {item.get('net_unit_price', 0.0):,.2f}", td_right),
            Paragraph(f"€ {item.get('line_total', 0.0):,.2f}", td_right_bold)
        ])

    # Total row
    table_data.append([
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph("<b>TOTAAL START-UP ORDER:</b>", td_bold),
        Paragraph("", td_style),
        Paragraph("", td_style),
        Paragraph(f"<b>{tot_units_val}</b>", td_bold),
        Paragraph("", td_style),
        Paragraph(f"<b>€ {tot_sales_val:,.2f}</b>", td_right_bold)
    ])

    items_table = Table(table_data, colWidths=[20, 50, 165, 80, 85, 35, 50, 50])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (1, -1), 'CENTER'),
        ('ALIGN', (5, 0), (5, -1), 'CENTER'),
        ('ALIGN', (6, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ECFDF5')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(items_table)
    elements.append(Spacer(1, 20))

    note_text = Paragraph(
        "<i>Dit Start-up Order voorziet in de initiële opstartlevering inclusief doorsmeren van alle installaties. "
        "Geleverde goederen binnen L.A.A.S. worden afgeboekt conform de periodieke fee-afspraken.</i>",
        subtitle_style
    )
    elements.append(note_text)

    doc.build(elements)
    return output_path
