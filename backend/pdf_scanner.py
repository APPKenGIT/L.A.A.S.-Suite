import re
import os
from pypdf import PdfReader
from datetime import datetime

def analyze_delivery_pdf(pdf_path, dossier):
    """
    Extracts delivery/order items from PDF documents (leverbonnen, orderbevestigingen, pakbonnen)
    and matches them against the dossier's article master and budget items.
    Allows pre-booking review and manual adjustments.
    """
    text = ""
    raw_lines = []
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
                for line in t.split('\n'):
                    if line.strip():
                        raw_lines.append(line.strip())
    except Exception as e:
        return {"error": f"Fout bij lezen van PDF: {str(e)}"}

    # 1. Search for Bon / Order number
    bon_number = ""
    # Check "Order # S05076" or similar
    order_num_match = re.search(r'Order\s*#\s*[:\s]*([A-Za-z0-9\-_]+)', text, re.IGNORECASE)
    if order_num_match:
        bon_number = order_num_match.group(1).strip()
    else:
        so_match = re.search(r'\b(S0[0-9]{3,7})\b', text, re.IGNORECASE)
        if so_match:
            bon_number = so_match.group(1).strip()
        else:
            lb_match = re.search(r'\b(LB[-0-9A-Z]{4,12})\b', text, re.IGNORECASE)
            if lb_match:
                bon_number = lb_match.group(1).strip()
            else:
                m = re.search(r'(?:Pakbon|Leverbon|Sales\s*Order|Order)\s*[:#\s/]+([A-Za-z0-9\-_]+)', text, re.IGNORECASE)
                if m and len(m.group(1).strip()) > 2 and m.group(1).strip().lower() not in ['sales', 'order', 'bon', 'leverbon']:
                    bon_number = m.group(1).strip()

    if not bon_number:
        bon_number = f"DOC-{datetime.now().strftime('%Y%m%d-%H%M')}"

    # 2. Search for Date
    date_val = datetime.now().strftime('%Y-%m-%d')
    # Check Leveringsdatum or Orderdatum
    deliv_date_match = re.search(r'(?:Leveringsdatum|Levering|Datum|Orderdatum)\s*[:\s]*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})', text, re.IGNORECASE)
    if deliv_date_match:
        raw_d = deliv_date_match.group(1).replace('/', '-').replace('.', '-')
        try:
            parts = raw_d.split('-')
            date_val = f"{parts[2]}-{int(parts[1]):02d}-{int(parts[0]):02d}"
        except Exception:
            pass
    else:
        date_patterns = [
            r'\b(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})\b',
            r'\b(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})\b'
        ]
        for pattern in date_patterns:
            m = re.search(pattern, text)
            if m:
                raw_d = m.group(1).replace('/', '-').replace('.', '-')
                try:
                    parts = raw_d.split('-')
                    if len(parts[0]) == 4:
                        date_val = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                    else:
                        date_val = f"{parts[2]}-{int(parts[1]):02d}-{int(parts[0]):02d}"
                    break
                except Exception:
                    pass

    # 3. Match articles
    articles_catalog = dossier.get('articles', [])
    budget_items = {b.get('product', '').lower(): b for b in dossier.get('budget_items', [])}
    deliveries = dossier.get('deliveries', [])

    delivered_totals = {}
    for d in deliveries:
        p_name = d.get('product_pack', '').lower()
        delivered_totals[p_name] = delivered_totals.get(p_name, 0) + float(d.get('quantity', 0))

    proposals = []
    matched_codes = set()

    # Step 3A: Search for structured bracketed codes: [4401] Servicepack ...
    # This matches Interflon ERP order format perfectly!
    for idx, line in enumerate(raw_lines):
        # Look for [code]
        bracket_match = re.search(r'\[(\d{3,6})\]\s*([^|\n\r]+)', line)
        if bracket_match:
            # Check if this line is a surcharge line (e.g. contains '| aantal')
            if '|' in line and 'aantal' in line.lower():
                continue

            code = bracket_match.group(1).strip()
            desc = bracket_match.group(2).strip()

            # Find matching article in catalog by code
            matched_art = None
            for art in articles_catalog:
                if str(art.get('article_code', '')).strip() == code or f"art. {code}" in art.get('dropdown_name', ''):
                    matched_art = art
                    break

            if not matched_art:
                # Try matching by name
                for art in articles_catalog:
                    if desc.lower() in art.get('dropdown_name', '').lower():
                        matched_art = art
                        break

            # Try to get quantity from the next 1-3 lines
            detected_qty = 1.0
            found_qty = False
            for offset in range(1, min(4, len(raw_lines) - idx)):
                next_l = raw_lines[idx + offset].strip()
                # Check for "4,00" or "4"
                q_match = re.match(r'^(\d+(?:[,\.]\d+)?)$', next_l)
                if q_match:
                    try:
                        detected_qty = float(q_match.group(1).replace(',', '.'))
                        found_qty = True
                        break
                    except Exception:
                        pass
                if 'stuk' in next_l.lower():
                    # Might be "4,00 Stuk(s)"
                    qm2 = re.search(r'(\d+(?:[,\.]\d+)?)', next_l)
                    if qm2:
                        detected_qty = float(qm2.group(1).replace(',', '.'))
                        found_qty = True
                        break

            product_name = matched_art.get('dropdown_name', f"[{code}] {desc}") if matched_art else f"[{code}] {desc}"
            category = matched_art.get('category', 'Smeermiddelen') if matched_art else 'Smeermiddelen'
            unit = matched_art.get('unit', 'Stuks') if matched_art else 'Stuks'
            pack_content = float(matched_art.get('content_per_pack', 1) if matched_art else 1)
            cost_price = float(matched_art.get('cost_price', 0) if matched_art else 0)
            sales_price = float(matched_art.get('sales_price', 0) if matched_art else 0)

            # If order has a price, check subsequent lines for price
            if sales_price == 0:
                for offset in range(1, min(6, len(raw_lines) - idx)):
                    price_line = raw_lines[idx + offset].strip()
                    pm = re.match(r'^(\d{1,4}[,\.]\d{2})$', price_line)
                    if pm and float(pm.group(1).replace(',', '.')) > 0:
                        sales_price = float(pm.group(1).replace(',', '.'))
                        break

            # Check budget item
            base_low = product_name.split('|')[0].strip().lower()
            b_match = None
            for b_name, b_data in budget_items.items():
                if b_name in base_low or base_low in b_name or desc.lower() in b_name or b_name in desc.lower():
                    b_match = b_data
                    break

            budget_y1 = float(b_match.get('y1_packs', 0) if b_match else 0)
            already_del = delivered_totals.get(product_name.lower(), 0)
            balance_before = max(0, budget_y1 - already_del)
            balance_after = balance_before - detected_qty

            status = "Gedekt door budget"
            if budget_y1 > 0 and balance_after < 0:
                status = f"Overschrijding ({abs(balance_after):.1f} extra)"
            elif budget_y1 == 0:
                status = "Buiten voorcalculatie"

            tot_cost = round(detected_qty * cost_price, 2)
            tot_sales = round(detected_qty * sales_price, 2)
            margin_eur = round(tot_sales - tot_cost, 2)
            margin_pct = round((margin_eur / tot_sales * 100) if tot_sales > 0 else 0, 1)

            matched_codes.add(code)
            proposals.append({
                'id': f"prop_{len(proposals)+1}",
                'product_pack': product_name,
                'article': code,
                'category': category,
                'unit': unit,
                'pack_content': pack_content,
                'quantity': detected_qty,
                'cost_per_pack': cost_price,
                'sales_per_pack': sales_price,
                'total_cost': tot_cost,
                'total_sales': tot_sales,
                'margin_eur': margin_eur,
                'margin_pct': margin_pct,
                'in_fee': 'Ja',
                'budget_y1': budget_y1,
                'already_delivered': already_del,
                'balance_before': balance_before,
                'balance_after': balance_after,
                'status': status
            })

    # Step 3B: If no bracketed codes found, perform text name / code search (standard packing slips)
    if not proposals:
        matched_articles = set()
        for art in articles_catalog:
            art_name = art.get('dropdown_name', '')
            base_name = art_name.split('|')[0].strip() if '|' in art_name else art_name
            short_name = art.get('dashboard_name', '') or base_name
            art_code = str(art.get('article_code', '')).strip()

            base_low = base_name.lower()
            short_low = short_name.lower() if len(short_name) > 3 else ''
            code_low = art_code.lower() if len(art_code) >= 3 else ''

            found_in_text = False
            detected_qty = 1.0

            for line in raw_lines:
                line_low = line.lower()
                code_match = bool(code_low and (f"art. {code_low}" in line_low or f" {code_low} " in f" {line_low} "))
                name_match = (base_low in line_low) or (short_low and short_low in line_low)

                if code_match or name_match:
                    found_in_text = True
                    qty_match = re.search(r'(\d+(?:[,\.]\d+)?)\s*(?:x|stuks|bussen|kokers|stk|ltr|l|kg)?\s+', line_low)
                    if not qty_match:
                        qty_match = re.search(r'(?:(?:aantal|qty|stuks)[:\s]*)?(\d+(?:[,\.]\d+)?)\s*(?:x|\*)', line_low)
                    if not qty_match:
                        qty_match = re.search(r'\b(\d{1,4})\b', line)

                    if qty_match:
                        try:
                            q_str = qty_match.group(1).replace(',', '.')
                            val = float(q_str)
                            if 0 < val < 5000:
                                detected_qty = val
                        except Exception:
                            pass
                    break

            if found_in_text and art_name not in matched_articles:
                matched_articles.add(art_name)

                b_match = None
                for b_name, b_data in budget_items.items():
                    if b_name in base_low or base_low in b_name:
                        b_match = b_data
                        break

                budget_y1 = float(b_match.get('y1_packs', 0) if b_match else 0)
                already_del = delivered_totals.get(art_name.lower(), 0)
                balance_before = max(0, budget_y1 - already_del)
                balance_after = balance_before - detected_qty

                status = "Gedekt door budget"
                if budget_y1 > 0 and balance_after < 0:
                    status = f"Overschrijding ({abs(balance_after):.1f} extra)"
                elif budget_y1 == 0:
                    status = "Buiten voorcalculatie"

                cost_per_pack = float(art.get('cost_price', 0))
                sales_per_pack = float(art.get('sales_price', 0))
                tot_cost = round(detected_qty * cost_per_pack, 2)
                tot_sales = round(detected_qty * sales_per_pack, 2)
                margin_eur = round(tot_sales - tot_cost, 2)
                margin_pct = round((margin_eur / tot_sales * 100) if tot_sales > 0 else 0, 1)

                proposals.append({
                    'id': f"prop_{len(proposals)+1}",
                    'product_pack': art_name,
                    'article': art.get('article_code', ''),
                    'category': art.get('category', ''),
                    'unit': art.get('unit', 'Stuks'),
                    'pack_content': art.get('content_per_pack', 1),
                    'quantity': detected_qty,
                    'cost_per_pack': cost_per_pack,
                    'sales_per_pack': sales_per_pack,
                    'total_cost': tot_cost,
                    'total_sales': tot_sales,
                    'margin_eur': margin_eur,
                    'margin_pct': margin_pct,
                    'in_fee': art.get('in_fee_default', 'Ja'),
                    'budget_y1': budget_y1,
                    'already_delivered': already_del,
                    'balance_before': balance_before,
                    'balance_after': balance_after,
                    'status': status
                })

    return {
        'bon_so': bon_number,
        'date': date_val,
        'proposals': proposals,
        'raw_lines_count': len(raw_lines),
        'summary': f"{len(proposals)} artikelen automatisch herkend op document {bon_number}"
    }
