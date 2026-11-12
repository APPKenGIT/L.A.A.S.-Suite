"""
Dossier Store for L.A.A.S.-Suite
Manages the 3-level hierarchy: Customer -> Department -> Contract (dossier),
safe archiving & restoration, strict archive-only permanent deletion,
customer logo handling, and dossier lifecycle persistence.
"""

import os
import json
import shutil
import zipfile
from datetime import datetime
from werkzeug.utils import secure_filename
from .pricelist_engine import get_default_pricelist_from_templates
from .firebase_store import FirebaseStore

import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIERS_ROOT = os.path.join(BASE_DIR, "dossiers")
EXPORTS_ROOT = os.path.join(BASE_DIR, "exports")
TEMPLATES_ROOT = os.path.join(BASE_DIR, "voorbeeldbestanden")
CORRECT_PASSWORD = "1nt3rfl0n"
VALID_ADMIN_PASSWORDS = {"1nt3rfl0n", "laas2026", "interflon", "Interflon", "Interflon2026"}

LOGO_EXTENSIONS = ['png', 'jpg', 'jpeg', 'svg', 'webp']

class DossierStore:
    def __init__(self):
        os.makedirs(DOSSIERS_ROOT, exist_ok=True)
        os.makedirs(EXPORTS_ROOT, exist_ok=True)
        self.DOSSIERS_ROOT = DOSSIERS_ROOT
        self.EXPORTS_ROOT = EXPORTS_ROOT
        try:
            self.firebase = FirebaseStore()
        except Exception:
            self.firebase = None

    def verify_password(self, password):
        if not password:
            return False
        p = password.strip()
        return p == CORRECT_PASSWORD or p in VALID_ADMIN_PASSWORDS

    # =========================================================================
    # LOGO MANAGEMENT
    # =========================================================================
    def get_customer_logo_path(self, customer):
        cust_dir = os.path.join(DOSSIERS_ROOT, customer)
        if not os.path.exists(cust_dir):
            return None
        for ext in LOGO_EXTENSIONS:
            p = os.path.join(cust_dir, f"logo.{ext}")
            if os.path.exists(p):
                return p
        return None

    def save_customer_logo(self, customer, file_storage):
        cust_dir = os.path.join(DOSSIERS_ROOT, customer)
        os.makedirs(cust_dir, exist_ok=True)
        
        # Clean previous logo files with any extension
        for ext in LOGO_EXTENSIONS:
            old_p = os.path.join(cust_dir, f"logo.{ext}")
            if os.path.exists(old_p):
                try:
                    os.remove(old_p)
                except Exception:
                    pass

        # Determine extension from original filename
        fname = file_storage.filename or 'logo.png'
        ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else 'png'
        if ext not in LOGO_EXTENSIONS:
            ext = 'png'
            
        target_path = os.path.join(cust_dir, f"logo.{ext}")
        file_storage.save(target_path)
        
        # Also update customer .meta.json
        meta = self._get_folder_meta(cust_dir)
        meta['has_logo'] = True
        meta['logo_ext'] = ext
        meta['logo_updated_at'] = int(datetime.now().timestamp())
        self._set_folder_meta(cust_dir, meta)
        
        return f"/api/customer/{customer}/logo?t={meta['logo_updated_at']}"

    # =========================================================================
    # HIERARCHY & ARCHIVE LISTING
    # =========================================================================
    def list_hierarchy(self):
        """
        Returns all ACTIVE customers -> departments -> contracts,
        plus customer metadata (logos, contract counts).
        """
        hierarchy = {}
        customer_meta = {}
        if not os.path.exists(DOSSIERS_ROOT):
            return {"hierarchy": hierarchy, "customer_meta": customer_meta}

        for cust in sorted(os.listdir(DOSSIERS_ROOT)):
            if cust.startswith('_') or cust.startswith('.') or cust.lower() in ['uploads', 'exports', 'templates', 'voorbeeldbestanden']:
                continue
            cust_path = os.path.join(DOSSIERS_ROOT, cust)
            if not os.path.isdir(cust_path):
                continue
                
            cust_meta = self._get_folder_meta(cust_path)
            if cust_meta.get('archived', False):
                continue

            logo_path = self.get_customer_logo_path(cust)
            has_logo = logo_path is not None and os.path.exists(logo_path)
            logo_ts = int(os.path.getmtime(logo_path)) if has_logo else 0
            
            customer_meta[cust] = {
                'customer': cust,
                'has_logo': has_logo,
                'logo_url': f"/api/customer/{cust}/logo?t={logo_ts}" if has_logo else None,
                'initials': cust[:2].upper()
            }

            departments = {}
            for dept in sorted(os.listdir(cust_path)):
                dept_path = os.path.join(cust_path, dept)
                if not os.path.isdir(dept_path):
                    continue
                    
                dept_meta = self._get_folder_meta(dept_path)
                if dept_meta.get('archived', False):
                    continue

                contracts = []
                for item in sorted(os.listdir(dept_path)):
                    item_path = os.path.join(dept_path, item)
                    if os.path.isdir(item_path):
                        json_file = os.path.join(item_path, "dossier.json")
                        if os.path.exists(json_file):
                            try:
                                with open(json_file, "r", encoding="utf-8") as f:
                                    d = json.load(f)
                                if not d.get('archived', False):
                                    contracts.append({
                                        'contract_name': d.get('contract_name', item),
                                        'status': d.get('status', 'Concept'),
                                        'duration_years': d.get('settings', {}).get('duration_years', 3),
                                        'fee_per_month': d.get('settings', {}).get('fee_per_month', 0.0),
                                        'total_points': d.get('ilac_calculation', {}).get('summary', {}).get('total_points', 0),
                                        'has_ilac': bool(d.get('ilac_calculation', {}).get('points')),
                                        'has_pricelist': bool(d.get('price_list', {}).get('items')),
                                        'is_active': d.get('status') == 'Actief' or bool(d.get('tracking', {}).get('is_active')),
                                        'prices_frozen': bool(d.get('prices_frozen', False)),
                                        'tracking_active': bool(d.get('tracking', {}).get('is_active'))
                                    })
                            except Exception:
                                pass
                                
                    elif item == "dossier.json":
                        try:
                            with open(item_path, "r", encoding="utf-8") as f:
                                d = json.load(f)
                            if not d.get('archived', False):
                                c_name = d.get('contract_name') or f"Standaard Contract {dept}"
                                contracts.append({
                                    'contract_name': c_name,
                                    'status': d.get('status', 'Concept'),
                                    'duration_years': d.get('settings', {}).get('duration_years', 3),
                                    'fee_per_month': d.get('settings', {}).get('fee_per_month', 0.0),
                                    'total_points': d.get('ilac_calculation', {}).get('summary', {}).get('total_points', 0),
                                    'has_ilac': bool(d.get('ilac_calculation', {}).get('points')),
                                    'has_pricelist': bool(d.get('price_list', {}).get('items')),
                                    'is_active': d.get('status') == 'Actief' or bool(d.get('tracking', {}).get('is_active')),
                                    'prices_frozen': bool(d.get('prices_frozen', False)),
                                    'tracking_active': bool(d.get('tracking', {}).get('is_active'))
                                })
                        except Exception:
                            pass

                departments[dept] = contracts

            hierarchy[cust] = departments

        return {"hierarchy": hierarchy, "customer_meta": customer_meta}

    def list_archive(self):
        """
        Returns all ARCHIVED items categorized by level:
        - customers: [...]
        - departments: [...]
        - contracts: [...]
        """
        archive_data = {
            'customers': [],
            'departments': [],
            'contracts': []
        }
        
        if not os.path.exists(DOSSIERS_ROOT):
            return archive_data

        for cust in sorted(os.listdir(DOSSIERS_ROOT)):
            if cust.startswith('_') or cust.startswith('.') or cust.lower() in ['uploads', 'exports', 'templates', 'voorbeeldbestanden']:
                continue
            cust_path = os.path.join(DOSSIERS_ROOT, cust)
            if not os.path.isdir(cust_path):
                continue
                
            cust_meta = self._get_folder_meta(cust_path)
            if cust_meta.get('archived', False):
                archive_data['customers'].append({
                    'customer': cust,
                    'archived_at': cust_meta.get('archived_at')
                })

            for dept in sorted(os.listdir(cust_path)):
                dept_path = os.path.join(cust_path, dept)
                if not os.path.isdir(dept_path):
                    continue
                    
                dept_meta = self._get_folder_meta(dept_path)
                if dept_meta.get('archived', False) and not cust_meta.get('archived', False):
                    archive_data['departments'].append({
                        'customer': cust,
                        'department': dept,
                        'archived_at': dept_meta.get('archived_at')
                    })

                for item in sorted(os.listdir(dept_path)):
                    item_path = os.path.join(dept_path, item)
                    if os.path.isdir(item_path):
                        json_file = os.path.join(item_path, "dossier.json")
                        if os.path.exists(json_file):
                            try:
                                with open(json_file, "r", encoding="utf-8") as f:
                                    d = json.load(f)
                                if d.get('archived', False) and not dept_meta.get('archived', False) and not cust_meta.get('archived', False):
                                    archive_data['contracts'].append({
                                        'customer': cust,
                                        'department': dept,
                                        'contract_name': d.get('contract_name', item),
                                        'archived_at': d.get('archived_at')
                                    })
                            except Exception:
                                pass
                    elif item == "dossier.json":
                        try:
                            with open(item_path, "r", encoding="utf-8") as f:
                                d = json.load(f)
                            if d.get('archived', False) and not dept_meta.get('archived', False) and not cust_meta.get('archived', False):
                                archive_data['contracts'].append({
                                    'customer': cust,
                                    'department': dept,
                                    'contract_name': d.get('contract_name') or f"Contract {dept}",
                                    'archived_at': d.get('archived_at')
                                })
                        except Exception:
                            pass

        return archive_data

    # =========================================================================
    # DOSSIER CRUD & 3-LEVEL ACCESS
    # =========================================================================
    def get_contract_dir(self, customer, department, contract_name):
        return os.path.join(DOSSIERS_ROOT, customer, department, contract_name)

    def _ensure_dossier_defaults(self, d, customer):
        if not d:
            return d
        logo_path = self.get_customer_logo_path(customer)
        d['customer_logo_url'] = f"/api/customer/{customer}/logo?t={int(os.path.getmtime(logo_path))}" if logo_path else None
        
        if 'settings' not in d:
            d['settings'] = {}
        d['settings'].setdefault('duration_years', 3)
        d['settings'].setdefault('gram_per_pompslag', 1.5)
        d['settings'].setdefault('ml_per_second', 1.0)
        d.setdefault('prices_frozen', False)
        # Contracts follow the global price list unless explicitly frozen in a version snapshot
        if not d.get('prices_frozen') or not d.get('price_list') or not d.get('price_list', {}).get('items'):
            d['price_list'] = self.get_global_pricelist()
        d.setdefault('indexation', {'active': False, 'percentage': 0.0, 'type': 'general', 'log': []})
        d.setdefault('temporary_surcharge', {
            'active': False,
            'percentage': 5.0,
            'name': 'Grondstoffentoeslag Olie (Straat van Hormuz)',
            'categories': ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten']
        })

        if 'fase2' not in d:
            d['fase2'] = {
                "work_hours": {
                    "hourly_rate_partner": 63.0,
                    "partner_surcharge_pct": 15.0,
                    "travel_km_per_day": 76.0,
                    "travel_rate_per_km": 1.75,
                    "travel_cost_per_day": 152.95,
                    "work_days_per_year": 65,
                    "work_days_year1": 87,
                    "hours_per_day": 8.0,
                    "pm_pct": 15.0,
                    "supervision_pct": 10.0,
                    "interflon_hourly_rate": 110.0,
                    "oil_analyses_per_year": 0,
                    "analysis_unit_price": 220.0,
                    "software_license_annual": 1950.0,
                    "training_budget": 880.0
                },
                "proposal_summary": {
                    "products_total": 0.0,
                    "hardware_total": 0.0,
                    "work_hours_total": 0.0,
                    "management_total": 0.0,
                    "grand_total": 0.0,
                    "monthly_fee": 0.0
                },
                "material_groups": [
                    {
                        "id": "grp_default",
                        "title": "Hardware, Tools & Extra Materialen",
                        "items": []
                    }
                ]
            }
        else:
            if 'work_hours' in d['fase2']:
                d['fase2']['work_hours'].setdefault('partner_surcharge_pct', 15.0)
            if 'material_groups' not in d['fase2']:
                existing_items = d['fase2'].get('manual_items') or d.get('ilac_calculation', {}).get('manual_items', [])
                d['fase2']['material_groups'] = [
                    {
                        "id": "grp_default",
                        "title": "Hardware, Tools & Extra Materialen",
                        "items": existing_items
                    }
                ]
        
        if 'settings' in d:
            d['settings'].setdefault('partner_surcharge_pct', 15.0)
            
        if 'versions' not in d:
            d['versions'] = []
        if 'active_version_id' not in d:
            d['active_version_id'] = None
            
        if 'proposal' not in d:
            d['proposal'] = {
                "doc_id": "BE/003500-01",
                "authors": "Kenny De Meester, Dennis Broods",
                "approved_by": "Sven Permentier, Wim Peckstadt",
                "status": "Final",
                "custom_texts": {
                    "inleiding": "",
                    "huidige_situatie": "",
                    "scope_toelichting": "",
                    "leveringsvoorwaarden": ""
                },
                "maatpak_toggles": {
                    "execution_work": True,
                    "project_management": True,
                    "ilac_license": True,
                    "oil_analysis": True
                }
            }
            
        if 'ilac_calculation' not in d:
            d['ilac_calculation'] = {
                'points': [],
                'aggregated_products': [],
                'manual_items': [],
                'summary': {}
            }
        elif 'manual_items' not in d['ilac_calculation']:
            d['ilac_calculation']['manual_items'] = []

        if 'price_list' not in d:
            d['price_list'] = {'filename': None, 'uploaded_at': None, 'items': []}

        if 'standard_packages' not in d or not d['standard_packages']:
            d['standard_packages'] = self.get_standard_packages()

        if 'tracking' not in d:
            d['tracking'] = {
                'is_active': False,
                'accepted_at': None,
                'accepted_by': None,
                'baseline': {
                    'monthly_fee': 0.0,
                    'duration_years': 3,
                    'total_months': 36,
                    'agreed_modules': {},
                    'products_plan': []
                },
                'deliveries': [],
                'partner_regular_hours': [],
                'interflon_pm_hours': [],
                'partner_regie_hours': [],
                'invoicing_schedule': [],
                'out_of_fee_orders': [],
                'unlock_audit_log': [],
                'pnl_summary': {}
            }

        # Initialize Umicore with rich live data from P&L LaaS Umicore.xlsx if not active
        if customer == 'Umicore' and not d.get('tracking', {}).get('is_active'):
            try:
                excel_p = os.path.join(os.path.dirname(__file__), '..', 'P&L LaaS Umicore.xlsx')
                if os.path.exists(excel_p):
                    from backend.tracking_engine import parse_umicore_pnl_excel, recalculate_tracking_pnl
                    parsed = parse_umicore_pnl_excel(excel_p)
                    if parsed:
                        d['tracking']['is_active'] = True
                        d['tracking']['accepted_at'] = '2026-01-01T00:00:00'
                        d['tracking']['accepted_by'] = 'Kenny De Meester'
                        d['tracking']['deliveries'] = parsed['deliveries']
                        d['tracking']['partner_regular_hours'] = parsed['partner_regular_hours']
                        d['tracking']['interflon_pm_hours'] = parsed['interflon_pm_hours']
                        d['tracking']['partner_regie_hours'] = parsed['partner_regie_hours']
                        d['tracking']['invoicing_schedule'] = parsed['invoicing_schedule']
                        d['tracking']['out_of_fee_orders'] = parsed['out_of_fee_orders']
                        d['tracking']['products_comparison'] = parsed.get('products_comparison', [])
                        d['tracking']['baseline'] = {
                            'monthly_fee': 10949.36,
                            'duration_years': 3,
                            'total_months': 36,
                            'agreed_modules': {
                                'execution_work': True,
                                'project_management': True,
                                'ilac_license': True,
                                'oil_analysis': True
                            }
                        }
                        d['status'] = 'Actief'
                        d['prices_frozen'] = True
                        recalculate_tracking_pnl(d['tracking'], d.get('settings'), d.get('fase2'), d.get('ilac_calculation'))
            except Exception as e:
                print(f"Error preloading Umicore tracking: {e}")

        # Ensure Umicore has full products_comparison from Excel sheet 11
        if customer == 'Umicore' and (not d.get('tracking', {}).get('products_comparison') or len(d.get('tracking', {}).get('products_comparison', [])) < 30):
            try:
                excel_p = os.path.join(os.path.dirname(__file__), '..', 'P&L LaaS Umicore.xlsx')
                if os.path.exists(excel_p):
                    from backend.tracking_engine import parse_umicore_pnl_excel
                    parsed = parse_umicore_pnl_excel(excel_p)
                    if parsed and parsed.get('products_comparison'):
                        d['tracking']['products_comparison'] = parsed['products_comparison']
            except Exception as e:
                print(f"Error loading Umicore products_comparison: {e}")

        # Always ensure P&L is calculated if tracking is active
        if d.get('tracking', {}).get('is_active'):
            try:
                from backend.tracking_engine import recalculate_tracking_pnl
                recalculate_tracking_pnl(d['tracking'], d.get('settings'), d.get('fase2'), d.get('ilac_calculation'))
            except Exception as e:
                print(f"Error recalculating tracking P&L: {e}")

        return d

    def accept_and_lock_contract(self, customer, department, contract_name, baseline_config):
        """
        Accepts the contract, freezes the calculation and initializes tracking baseline.
        """
        dossier = self.get_dossier(customer, department, contract_name)
        if not dossier:
            raise FileNotFoundError(f"Dossier {customer}/{department}/{contract_name} niet gevonden")

        from backend.tracking_engine import recalculate_tracking_pnl

        tracking = dossier.setdefault('tracking', {})
        tracking['is_active'] = True
        tracking['accepted_at'] = datetime.now().isoformat()
        tracking['accepted_by'] = baseline_config.get('accepted_by', 'Beheerder')

        years = int(baseline_config.get('duration_years') or dossier.get('settings', {}).get('duration_years', 3))
        fee = float(baseline_config.get('agreed_monthly_fee') or dossier.get('settings', {}).get('fee_per_month', 0.0))

        tracking['baseline'] = {
            'monthly_fee': fee,
            'duration_years': years,
            'total_months': years * 12,
            'agreed_modules': baseline_config.get('agreed_modules', {}),
            'version_tag': baseline_config.get('version_tag', 'Huidige Werkversie'),
            'notes': baseline_config.get('notes', '')
        }

        dossier['settings']['duration_years'] = years
        dossier['settings']['fee_per_month'] = fee
        dossier['status'] = 'Actief'
        dossier['prices_frozen'] = True

        recalculate_tracking_pnl(tracking, dossier['settings'], dossier.get('fase2'))
        return self.save_dossier(customer, department, contract_name, dossier)

    def unlock_contract_calculation(self, customer, department, contract_name, admin_note=""):
        """
        Unlocks a frozen calculation after double verification.
        """
        dossier = self.get_dossier(customer, department, contract_name)
        if not dossier:
            raise FileNotFoundError(f"Dossier {customer}/{department}/{contract_name} niet gevonden")

        dossier['prices_frozen'] = False
        tracking = dossier.setdefault('tracking', {})
        tracking.setdefault('unlock_audit_log', [])
        tracking['unlock_audit_log'].append({
            'unlocked_at': datetime.now().isoformat(),
            'note': admin_note or "Calculatie ontgrendeld via dubbele beheerdersverificatie"
        })
        return self.save_dossier(customer, department, contract_name, dossier)

    def save_tracking(self, customer, department, contract_name, tracking_data):
        """
        Saves updated operational tracking data without altering Fase 1 / Fase 2 calculation.
        """
        dossier = self.get_dossier(customer, department, contract_name)
        if not dossier:
            raise FileNotFoundError(f"Dossier {customer}/{department}/{contract_name} niet gevonden")

        from backend.tracking_engine import recalculate_tracking_pnl

        dossier['tracking'] = tracking_data
        recalculate_tracking_pnl(dossier['tracking'], dossier.get('settings'), dossier.get('fase2'))
        return self.save_dossier(customer, department, contract_name, dossier)

    def clear_calculation(self, customer, department, contract_name):
        """Clears calculation points, products, and summary for a contract dossier."""
        dossier = self.get_dossier(customer, department, contract_name)
        if not dossier:
            raise FileNotFoundError(f"Dossier {customer}/{department}/{contract_name} niet gevonden")
            
        # Reset calculation while preserving price_list and fase2 work hour parameters
        dossier['ilac_calculation']['points'] = []
        dossier['ilac_calculation']['aggregated_products'] = []
        dossier['ilac_calculation']['manual_items'] = []
        dossier['ilac_calculation']['uploaded_at'] = None
        dossier['ilac_calculation']['filename'] = None
        dossier['ilac_calculation']['summary'] = {
            'total_points': 0,
            'total_products_count': 0,
            'total_products_cost': 0.0,
            'total_manual_cost': 0.0,
            'grand_total_cost': 0.0,
            'calculated_monthly_fee': 0.0,
            'total_audit_hours_per_year': 0.0,
            'long_interval_tasks_count': 0
        }
        if 'fase2' in dossier:
            dossier['fase2']['proposal_summary'] = {
                'monthly_fee': 0.0,
                'grand_contract_total': 0.0,
                'products_total': 0.0,
                'hardware_total': 0.0,
                'total_execution_cost': 0.0,
                'total_services_cost': 0.0
            }
        dossier['settings']['fee_per_month'] = 0.0
        return self.save_dossier(customer, department, contract_name, dossier)

    def get_dossier(self, customer, department, contract_name=None):
        """
        Retrieves a contract dossier by customer, department, and contract_name.
        If contract_name is None, finds the first contract in the department.
        """
        dept_path = os.path.join(DOSSIERS_ROOT, customer, department)
        if os.path.exists(dept_path):
            # If specific contract requested
            if contract_name:
                json_file = os.path.join(dept_path, contract_name, "dossier.json")
                if os.path.exists(json_file):
                    with open(json_file, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        return self._ensure_dossier_defaults(d, customer)

                direct_json = os.path.join(dept_path, "dossier.json")
                if os.path.exists(direct_json):
                    with open(direct_json, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    if d.get('contract_name') == contract_name or contract_name in [None, '']:
                        return self._ensure_dossier_defaults(d, customer)

            # If contract_name is None, grab first contract
            for item in sorted(os.listdir(dept_path)):
                item_path = os.path.join(dept_path, item)
                if os.path.isdir(item_path):
                    jf = os.path.join(item_path, "dossier.json")
                    if os.path.exists(jf):
                        with open(jf, "r", encoding="utf-8") as f:
                            d = json.load(f)
                            return self._ensure_dossier_defaults(d, customer)
                elif item == "dossier.json":
                    with open(item_path, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        return self._ensure_dossier_defaults(d, customer)

        # Fallback to Firebase Firestore if not found locally
        if getattr(self, 'firebase', None) and customer and department and contract_name:
            try:
                fb_dossier = self.firebase.get_dossier(customer, department, contract_name)
                if fb_dossier:
                    # Cache locally
                    try:
                        t_dir = self.get_contract_dir(customer, department, contract_name)
                        os.makedirs(t_dir, exist_ok=True)
                        with open(os.path.join(t_dir, "dossier.json"), "w", encoding="utf-8") as f_c:
                            json.dump(fb_dossier, f_c, indent=2, ensure_ascii=False)
                    except Exception:
                        pass
                    return self._ensure_dossier_defaults(fb_dossier, customer)
            except Exception as e_fbg:
                print(f"Firebase fallback get_dossier warning: {e_fbg}")

        return None

    def save_dossier(self, customer, department, contract_name, dossier_data):
        """Saves a dossier.json inside dossiers/<customer>/<department>/<contract_name>/."""
        target_dir = self.get_contract_dir(customer, department, contract_name)
        os.makedirs(target_dir, exist_ok=True)
        os.makedirs(os.path.join(target_dir, "documenten"), exist_ok=True)

        dossier_data['customer'] = customer
        dossier_data['department'] = department
        dossier_data['contract_name'] = contract_name
        dossier_data['last_updated'] = datetime.now().isoformat()

        json_file = os.path.join(target_dir, "dossier.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(dossier_data, f, indent=2, ensure_ascii=False)

        # Real-time Cloud Sync to Firebase Firestore
        if getattr(self, 'firebase', None):
            try:
                self.firebase.save_dossier(customer, department, contract_name, dossier_data)
            except Exception as e_fb:
                print(f"Firebase sync warning on save: {e_fb}")

        return dossier_data

    def create_customer(self, customer_name):
        """Creates a new customer directory."""
        c_clean = customer_name.strip()
        if not c_clean:
            raise ValueError("Klantnaam mag niet leeg zijn")
        c_path = os.path.join(DOSSIERS_ROOT, c_clean)
        os.makedirs(c_path, exist_ok=True)
        self._set_folder_meta(c_path, {'archived': False})
        return {"customer": c_clean}

    def create_department(self, customer_name, department_name):
        """Creates a new department directory under a customer."""
        c_clean = customer_name.strip()
        d_clean = department_name.strip()
        if not c_clean or not d_clean:
            raise ValueError("Klantnaam en afdelingsnaam zijn verplicht")
        d_path = os.path.join(DOSSIERS_ROOT, c_clean, d_clean)
        os.makedirs(d_path, exist_ok=True)
        self._set_folder_meta(d_path, {'archived': False})
        return {"customer": c_clean, "department": d_clean}

    def create_contract(self, customer_name, department_name, contract_name):
        """
        Creates a new empty contract dossier without requiring fee or duration.
        Loads default 2026 Prijslijst into dossier if available.
        """
        c_clean = customer_name.strip()
        d_clean = department_name.strip()
        con_clean = contract_name.strip()
        
        if not c_clean or not d_clean or not con_clean:
            raise ValueError("Klantnaam, afdeling en contractnaam zijn verplicht")

        # Ensure parent customer & department
        self.create_customer(c_clean)
        self.create_department(c_clean, d_clean)

        # Initial contract starts without a pricelist (must be explicitly uploaded)
        pl_data = {
            "filename": None,
            "uploaded_at": None,
            "items": []
        }

        new_dossier = {
            "id": f"con_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "customer": c_clean,
            "department": d_clean,
            "contract_name": con_clean,
            "status": "Concept",
            "archived": False,
            "archived_at": None,
            "settings": {
                "contract_name": con_clean,
                "customer": c_clean,
                "department": d_clean,
                "duration_years": 3,
                "fee_per_month": 0.0,
                "start_date": datetime.now().strftime("%Y-%m-%d"),
                "notes": ""
            },
            "price_list": pl_data,
            "ilac_calculation": {
                "uploaded_at": None,
                "filename": None,
                "contract_years": 3,
                "summary": {
                    "total_points": 0,
                    "total_products_count": 0,
                    "total_products_cost": 0.0,
                    "total_manual_cost": 0.0,
                    "grand_total_cost": 0.0,
                    "calculated_monthly_fee": 0.0,
                    "total_audit_hours_per_year": 0.0,
                    "long_interval_tasks_count": 0
                },
                "aggregated_products": [],
                "points": [],
                "manual_items": [],
                "task_categories": []
            },
            "fase2": {
                "work_hours": {
                    "hourly_rate_partner": 63.0,
                    "partner_surcharge_pct": 15.0,
                    "travel_km_per_day": 76.0,
                    "travel_rate_per_km": 1.75,
                    "travel_cost_per_day": 152.95,
                    "work_days_per_year": 65,
                    "work_days_year1": 87,
                    "hours_per_day": 8.0,
                    "pm_pct": 15.0,
                    "supervision_pct": 10.0,
                    "interflon_hourly_rate": 110.0,
                    "oil_analyses_per_year": 0,
                    "analysis_unit_price": 220.0,
                    "software_license_annual": 1950.0,
                    "training_budget": 880.0
                },
                "proposal_summary": {
                    "products_total": 0.0,
                    "hardware_total": 0.0,
                    "work_hours_total": 0.0,
                    "management_total": 0.0,
                    "grand_total": 0.0,
                    "monthly_fee": 0.0
                }
            },
            "renewal_concept": {
                "is_active": False,
                "elapsed_years": 3,
                "renewal_years": 3,
                "tasks": []
            },
            "standard_packages": self.get_standard_packages()
        }

        return self.save_dossier(c_clean, d_clean, con_clean, new_dossier)

    # =========================================================================
    # ARCHIVING, RESTORING & STRICT ARCHIVE-ONLY DELETION
    # =========================================================================
    def archive_item(self, level, customer, department=None, contract_name=None):
        """Archives a customer, department, or contract."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        if level == 'contract':
            d = self.get_dossier(customer, department, contract_name)
            if not d:
                raise FileNotFoundError("Contract niet gevonden")
            d['archived'] = True
            d['archived_at'] = now_str
            self.save_dossier(customer, department, contract_name, d)
            return {"status": "success", "level": "contract", "item": contract_name}
            
        elif level == 'department':
            dept_path = os.path.join(DOSSIERS_ROOT, customer, department)
            if not os.path.exists(dept_path):
                raise FileNotFoundError("Afdeling niet gevonden")
            self._set_folder_meta(dept_path, {'archived': True, 'archived_at': now_str})
            for item in os.listdir(dept_path):
                c_path = os.path.join(dept_path, item)
                if os.path.isdir(c_path):
                    d = self.get_dossier(customer, department, item)
                    if d:
                        d['archived'] = True
                        d['archived_at'] = now_str
                        self.save_dossier(customer, department, item, d)
            return {"status": "success", "level": "department", "item": department}
            
        elif level == 'customer':
            cust_path = os.path.join(DOSSIERS_ROOT, customer)
            if not os.path.exists(cust_path):
                raise FileNotFoundError("Klant niet gevonden")
            self._set_folder_meta(cust_path, {'archived': True, 'archived_at': now_str})
            return {"status": "success", "level": "customer", "item": customer}
            
        else:
            raise ValueError(f"Onbekend niveau: {level}")

    def restore_item(self, level, customer, department=None, contract_name=None):
        """
        Restores an item from archive.
        If restoring a contract, automatically ensures department and customer are restored!
        """
        if level == 'contract':
            d = self.get_dossier(customer, department, contract_name)
            if not d:
                raise FileNotFoundError("Contract niet gevonden")
            d['archived'] = False
            d['archived_at'] = None
            self.save_dossier(customer, department, contract_name, d)
            # Auto-restore parent department and customer
            dept_path = os.path.join(DOSSIERS_ROOT, customer, department)
            self._set_folder_meta(dept_path, {'archived': False, 'archived_at': None})
            cust_path = os.path.join(DOSSIERS_ROOT, customer)
            self._set_folder_meta(cust_path, {'archived': False, 'archived_at': None})
            return {"status": "success", "level": "contract", "item": contract_name}

        elif level == 'department':
            dept_path = os.path.join(DOSSIERS_ROOT, customer, department)
            if not os.path.exists(dept_path):
                raise FileNotFoundError("Afdeling niet gevonden")
            self._set_folder_meta(dept_path, {'archived': False, 'archived_at': None})
            cust_path = os.path.join(DOSSIERS_ROOT, customer)
            self._set_folder_meta(cust_path, {'archived': False, 'archived_at': None})
            for item in os.listdir(dept_path):
                c_path = os.path.join(dept_path, item)
                if os.path.isdir(c_path):
                    d = self.get_dossier(customer, department, item)
                    if d:
                        d['archived'] = False
                        d['archived_at'] = None
                        self.save_dossier(customer, department, item, d)
            return {"status": "success", "level": "department", "item": department}

        elif level == 'customer':
            cust_path = os.path.join(DOSSIERS_ROOT, customer)
            if not os.path.exists(cust_path):
                raise FileNotFoundError("Klant niet gevonden")
            self._set_folder_meta(cust_path, {'archived': False, 'archived_at': None})
            for dept in os.listdir(cust_path):
                dept_path = os.path.join(cust_path, dept)
                if os.path.isdir(dept_path):
                    self._set_folder_meta(dept_path, {'archived': False, 'archived_at': None})
                    for con in os.listdir(dept_path):
                        con_path = os.path.join(dept_path, con)
                        if os.path.isdir(con_path):
                            d = self.get_dossier(customer, dept, con)
                            if d:
                                d['archived'] = False
                                d['archived_at'] = None
                                self.save_dossier(customer, dept, con, d)
            return {"status": "success", "level": "customer", "item": customer}

    def delete_permanently(self, level, customer, department=None, contract_name=None):
        """
        Strictly deletes an item ONLY if it is currently in the archive!
        Refuses deletion if the item is active.
        """
        if level == 'contract':
            d = self.get_dossier(customer, department, contract_name)
            if not d:
                raise FileNotFoundError("Contract niet gevonden")
            if not d.get('archived', False):
                raise PermissionError("Veiligheidsbeveiliging: Dit contract kan niet verwijderd worden omdat het niet in het archief zit.")
            target_path = self.get_contract_dir(customer, department, contract_name)
            if os.path.exists(target_path):
                shutil.rmtree(target_path)
            return {"status": "success", "message": f"Contract '{contract_name}' is definitief verwijderd."}

        elif level == 'department':
            dept_path = os.path.join(DOSSIERS_ROOT, customer, department)
            if not os.path.exists(dept_path):
                raise FileNotFoundError("Afdeling niet gevonden")
            meta = self._get_folder_meta(dept_path)
            if not meta.get('archived', False):
                raise PermissionError("Veiligheidsbeveiliging: Deze afdeling kan niet verwijderd worden omdat zij niet in het archief zit.")
            shutil.rmtree(dept_path)
            return {"status": "success", "message": f"Afdeling '{department}' is definitief verwijderd."}

        elif level == 'customer':
            cust_path = os.path.join(DOSSIERS_ROOT, customer)
            if not os.path.exists(cust_path):
                raise FileNotFoundError("Klant niet gevonden")
            meta = self._get_folder_meta(cust_path)
            if not meta.get('archived', False):
                raise PermissionError("Veiligheidsbeveiliging: Deze klant kan niet verwijderd worden omdat zij niet in het archief zit.")
            shutil.rmtree(cust_path)
            return {"status": "success", "message": f"Klant '{customer}' is definitief verwijderd."}

    # =========================================================================
    # RENAME MANAGEMENT (KLANT, AFDELING, CONTRACT)
    # =========================================================================
    def rename_item(self, level, customer, department=None, contract_name=None, new_name=None):
        """
        Renames a customer, department, or contract.
        Updates folder paths on disk and synchronizes internal dossier.json files.
        """
        if not new_name or not str(new_name).strip():
            raise ValueError("Nieuwe benaming mag niet leeg zijn")
        
        new_clean = str(new_name).strip()
        # Disallow forbidden characters in path names
        for char in r'/\:*?"<>|':
            if char in new_clean:
                raise ValueError(f"De benaming mag geen '{char}' bevatten")

        if level == 'customer':
            old_path = os.path.join(DOSSIERS_ROOT, customer)
            new_path = os.path.join(DOSSIERS_ROOT, new_clean)
            if not os.path.exists(old_path):
                raise FileNotFoundError(f"Klant '{customer}' niet gevonden")
            if old_path.lower() != new_path.lower() and os.path.exists(new_path):
                raise ValueError(f"Klant '{new_clean}' bestaat al")
            
            if old_path != new_path:
                os.rename(old_path, new_path)
            
            # Update all contract dossiers under this customer
            for dept in os.listdir(new_path):
                dp = os.path.join(new_path, dept)
                if os.path.isdir(dp):
                    for con in os.listdir(dp):
                        cp = os.path.join(dp, con)
                        if os.path.isdir(cp):
                            jf = os.path.join(cp, "dossier.json")
                            if os.path.exists(jf):
                                try:
                                    with open(jf, "r", encoding="utf-8") as f:
                                        d = json.load(f)
                                    d['customer'] = new_clean
                                    if 'settings' in d:
                                        d['settings']['customer'] = new_clean
                                    with open(jf, "w", encoding="utf-8") as f:
                                        json.dump(d, f, indent=2, ensure_ascii=False)
                                except Exception:
                                    pass
            return {"status": "success", "level": "customer", "old_name": customer, "new_name": new_clean}

        elif level == 'department':
            if not department:
                raise ValueError("Afdeling is verplicht")
            old_path = os.path.join(DOSSIERS_ROOT, customer, department)
            new_path = os.path.join(DOSSIERS_ROOT, customer, new_clean)
            if not os.path.exists(old_path):
                raise FileNotFoundError(f"Afdeling '{department}' niet gevonden")
            if old_path.lower() != new_path.lower() and os.path.exists(new_path):
                raise ValueError(f"Afdeling '{new_clean}' bestaat al onder klant '{customer}'")
            
            if old_path != new_path:
                os.rename(old_path, new_path)
            
            # Update all contract dossiers under this department
            for con in os.listdir(new_path):
                cp = os.path.join(new_path, con)
                if os.path.isdir(cp):
                    jf = os.path.join(cp, "dossier.json")
                    if os.path.exists(jf):
                        try:
                            with open(jf, "r", encoding="utf-8") as f:
                                d = json.load(f)
                            d['department'] = new_clean
                            if 'settings' in d:
                                d['settings']['department'] = new_clean
                            with open(jf, "w", encoding="utf-8") as f:
                                json.dump(d, f, indent=2, ensure_ascii=False)
                        except Exception:
                            pass
            return {"status": "success", "level": "department", "customer": customer, "old_name": department, "new_name": new_clean}

        elif level == 'contract':
            if not department or not contract_name:
                raise ValueError("Afdeling en contractnaam zijn verplicht")
            old_path = os.path.join(DOSSIERS_ROOT, customer, department, contract_name)
            new_path = os.path.join(DOSSIERS_ROOT, customer, department, new_clean)
            if not os.path.exists(old_path):
                raise FileNotFoundError(f"Contract '{contract_name}' niet gevonden")
            if old_path.lower() != new_path.lower() and os.path.exists(new_path):
                raise ValueError(f"Contract '{new_clean}' bestaat al onder afdeling '{department}'")

            if old_path != new_path:
                os.rename(old_path, new_path)
            
            jf = os.path.join(new_path, "dossier.json")
            if os.path.exists(jf):
                try:
                    with open(jf, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    d['contract_name'] = new_clean
                    if 'settings' in d:
                        d['settings']['contract_name'] = new_clean
                    with open(jf, "w", encoding="utf-8") as f:
                        json.dump(d, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
            return {"status": "success", "level": "contract", "customer": customer, "department": department, "old_name": contract_name, "new_name": new_clean}

        else:
            raise ValueError(f"Onbekend niveau: {level}")

    # =========================================================================
    # VERSIEBEHEER, MATERIAALGROEPEN & VOORSTEL CONFIGURATIE
    # =========================================================================
    def save_version(self, customer, department, contract_name, note="", version_tag=None):
        """
        Saves a frozen snapshot version of the calculation (Fase 1 + Fase 2 + Summary + Proposal).
        Auto-generates version_tag (v1.0, v1.1, v2.0...) if not provided.
        """
        dossier = self.get_dossier(customer, department, contract_name)
        if not dossier:
            raise FileNotFoundError(f"Dossier {customer}/{department}/{contract_name} niet gevonden")

        if 'versions' not in dossier:
            dossier['versions'] = []

        if not version_tag:
            count = len(dossier['versions'])
            version_tag = f"v1.{count}" if count > 0 else "v1.0"

        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Build clean snapshot of essential calculation structures
        import copy
        snapshot = {
            "version_tag": version_tag,
            "created_at": now_iso,
            "note": note,
            "settings": copy.deepcopy(dossier.get('settings', {})),
            "summary": copy.deepcopy(dossier.get('ilac_calculation', {}).get('summary', {})),
            "fase2_work_hours": copy.deepcopy(dossier.get('fase2', {}).get('work_hours', {})),
            "fase2_proposal_summary": copy.deepcopy(dossier.get('fase2', {}).get('proposal_summary', {})),
            "material_groups": copy.deepcopy(dossier.get('fase2', {}).get('material_groups', [])),
            "proposal": copy.deepcopy(dossier.get('proposal', {}))
        }

        # Check if version with same tag already exists -> replace or append
        existing_idx = next((i for i, v in enumerate(dossier['versions']) if v.get('version_tag') == version_tag), None)
        if existing_idx is not None:
            dossier['versions'][existing_idx] = snapshot
        else:
            dossier['versions'].append(snapshot)

        dossier['active_version_id'] = version_tag
        dossier['prices_frozen'] = True
        self.save_dossier(customer, department, contract_name, dossier)
        return {"status": "success", "version_tag": version_tag, "versions": dossier['versions'], "active_version_id": version_tag}

    def restore_version(self, customer, department, contract_name, version_tag):
        """
        Restores a previously saved snapshot version back into active editing fields.
        """
        dossier = self.get_dossier(customer, department, contract_name)
        if not dossier:
            raise FileNotFoundError(f"Dossier {customer}/{department}/{contract_name} niet gevonden")

        target = next((v for v in dossier.get('versions', []) if v.get('version_tag') == version_tag), None)
        if not target:
            raise ValueError(f"Versie {version_tag} niet gevonden in dossier")

        import copy
        if 'settings' in target:
            dossier['settings'] = copy.deepcopy(target['settings'])
        if 'fase2_work_hours' in target:
            dossier['fase2']['work_hours'] = copy.deepcopy(target['fase2_work_hours'])
        if 'fase2_proposal_summary' in target:
            dossier['fase2']['proposal_summary'] = copy.deepcopy(target['fase2_proposal_summary'])
        if 'material_groups' in target:
            dossier['fase2']['material_groups'] = copy.deepcopy(target['material_groups'])
            # sync flattened items
            all_m = []
            for g in target['material_groups']:
                all_m.extend(g.get('items', []))
            dossier['fase2']['manual_items'] = all_m
            dossier['ilac_calculation']['manual_items'] = all_m
        if 'proposal' in target:
            dossier['proposal'] = copy.deepcopy(target['proposal'])

        dossier['active_version_id'] = version_tag
        self.save_dossier(customer, department, contract_name, dossier)
        return {"status": "success", "dossier": dossier, "restored_version": version_tag}

    def save_proposal_config(self, customer, department, contract_name, proposal_data):
        """Saves custom proposal report texts, metadata, and maatpak toggles."""
        dossier = self.get_dossier(customer, department, contract_name)
        if not dossier:
            raise FileNotFoundError(f"Dossier {customer}/{department}/{contract_name} niet gevonden")

        dossier['proposal'] = proposal_data
        self.save_dossier(customer, department, contract_name, dossier)
        return {"status": "success", "proposal": dossier['proposal']}

    def save_material_groups(self, customer, department, contract_name, material_groups):
        """Saves multiple material category cards and keeps flattened manual_items in sync."""
        dossier = self.get_dossier(customer, department, contract_name)
        if not dossier:
            raise FileNotFoundError(f"Dossier {customer}/{department}/{contract_name} niet gevonden")

        dossier['fase2']['material_groups'] = material_groups
        all_manual = []
        for g in material_groups:
            all_manual.extend(g.get('items', []))
        dossier['fase2']['manual_items'] = all_manual
        dossier['ilac_calculation']['manual_items'] = all_manual

        self.save_dossier(customer, department, contract_name, dossier)
        return {"status": "success", "dossier": dossier}


    # Internal helper methods for folder-level metadata
    def _get_folder_meta(self, folder_path):
        meta_file = os.path.join(folder_path, ".meta.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _set_folder_meta(self, folder_path, meta_dict):
        meta_file = os.path.join(folder_path, ".meta.json")
        try:
            curr = self._get_folder_meta(folder_path)
            curr.update(meta_dict)
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(curr, f, indent=2)
        except Exception as e:
            print(f"Warning setting meta for {folder_path}: {e}")

    # Standard Packages (Starter Kits) Management
    def get_standard_packages(self):
        """Returns standard starter packages from persistent JSON storage."""
        pkg_file = os.path.join(self.DOSSIERS_ROOT, "standard_packages.json")
        if os.path.exists(pkg_file):
            try:
                with open(pkg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                print(f"Error reading standard packages: {e}")
        return []

    def save_standard_packages(self, packages):
        """Saves standard starter packages to JSON storage and syncs to all active contract dossiers."""
        pkg_file = os.path.join(self.DOSSIERS_ROOT, "standard_packages.json")
        try:
            with open(pkg_file, "w", encoding="utf-8") as f:
                json.dump(packages, f, indent=2)

            # Sync to all dossiers
            hierarchy = self.list_hierarchy().get('hierarchy', {})
            for cust, depts in hierarchy.items():
                for dept, contracts in depts.items():
                    for c_info in contracts:
                        c_name = c_info.get('contract_name') if isinstance(c_info, dict) else c_info
                        d = self.get_dossier(cust, dept, c_name)
                        if d:
                            d['standard_packages'] = packages
                            self.save_dossier(cust, dept, c_name, d)
            return True
        except Exception as e:
            print(f"Error saving standard packages: {e}")
            return False

    # =========================================================================
    # GLOBAL SUITE PRICELIST & GLOBAL SETTINGS
    # =========================================================================
    def get_global_pricelist(self):
        """Returns the global price list for the entire L.A.A.S. suite."""
        pl_file = os.path.join(self.DOSSIERS_ROOT, "global_pricelist.json")
        if os.path.exists(pl_file):
            try:
                with open(pl_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and isinstance(data, dict) and data.get('items'):
                        return data
            except Exception as e:
                print(f"Error reading global_pricelist.json: {e}")

        # Fallback to template 2026 Prijslijst if not yet cached
        default_pl = get_default_pricelist_from_templates(TEMPLATES_ROOT)
        if default_pl and default_pl.get('items'):
            self.save_global_pricelist(default_pl)
            return default_pl

        return {'filename': None, 'total_items': 0, 'items': [], 'updated_at': None}

    def save_global_pricelist(self, pl_data):
        """Saves the global price list to dossiers/global_pricelist.json."""
        pl_file = os.path.join(self.DOSSIERS_ROOT, "global_pricelist.json")
        try:
            if not pl_data.get('updated_at'):
                pl_data['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(pl_file, "w", encoding="utf-8") as f:
                json.dump(pl_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving global_pricelist.json: {e}")
            return False

    def get_global_suite_settings(self):
        """Returns global suite configuration for indexation and temporary surcharges."""
        cfg_file = os.path.join(self.DOSSIERS_ROOT, "global_settings.json")
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading global_settings.json: {e}")

        default_settings = {
            "indexation": {
                "active": False,
                "percentage": 3.5,
                "type": "general",
                "effective_date": datetime.now().strftime("%Y-%m-%d"),
                "log": []
            },
            "temporary_surcharge": {
                "active": False,
                "percentage": 5.0,
                "name": "Grondstoffentoeslag Olie (Straat van Hormuz)",
                "categories": ["Olien ", "Food Olien", "Vetten", "Food Vetten"]
            }
        }
        self.save_global_suite_settings(default_settings)
        return default_settings

    def save_global_suite_settings(self, settings):
        """Saves global suite settings."""
        cfg_file = os.path.join(self.DOSSIERS_ROOT, "global_settings.json")
        try:
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving global_settings.json: {e}")
            return False
