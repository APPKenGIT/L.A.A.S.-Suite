import os
import json
import urllib.request
import urllib.error
from datetime import datetime

PROJECT_ID = "laas-suite"
BASE_FIRESTORE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

def _make_doc_id(customer, department, contract_name):
    # Safe doc id without slashes
    safe_c = str(customer).replace('/', '_').replace(' ', '_')
    safe_d = str(department).replace('/', '_').replace(' ', '_')
    safe_n = str(contract_name).replace('/', '_').replace(' ', '_')
    return f"{safe_c}__{safe_d}__{safe_n}"

class FirebaseStore:
    def __init__(self, project_id=PROJECT_ID):
        self.project_id = project_id
        self.base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"

    def get_dossier(self, customer, department, contract_name):
        """Fetches dossier from Firestore. Returns dict or None."""
        doc_id = _make_doc_id(customer, department, contract_name)
        url = f"{self.base_url}/dossiers/{doc_id}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                fields = data.get("fields", {})
                dossier_json_str = fields.get("dossier_json", {}).get("stringValue", "")
                if not dossier_json_str:
                    return None
                dossier = json.loads(dossier_json_str)
                
                # Fetch points companion doc if available
                points_url = f"{self.base_url}/dossier_points/{doc_id}"
                req_pts = urllib.request.Request(points_url, method="GET")
                try:
                    with urllib.request.urlopen(req_pts, timeout=5) as resp_pts:
                        pts_data = json.loads(resp_pts.read().decode('utf-8'))
                        pts_fields = pts_data.get("fields", {})
                        pts_str = pts_fields.get("points_json", {}).get("stringValue", "[]")
                        points = json.loads(pts_str)
                        dossier.setdefault("ilac_calculation", {})["points"] = points
                except Exception as e_pts:
                    # Non-fatal if points doc is missing
                    pass

                return dossier
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            print(f"FirebaseStore.get_dossier HTTP error {e.code}: {e.reason}")
            return None
        except Exception as e:
            print(f"FirebaseStore.get_dossier error: {e}")
            return None

    def save_dossier(self, customer, department, contract_name, dossier_data):
        """Saves dossier to Firestore."""
        doc_id = _make_doc_id(customer, department, contract_name)
        
        # Extract points to keep main doc lean and within Firestore limits
        points = dossier_data.get('ilac_calculation', {}).get('points', [])
        
        main_dossier = dict(dossier_data)
        if 'ilac_points' in main_dossier:
            del main_dossier['ilac_points']
        
        main_dossier_calc = dict(main_dossier.get('ilac_calculation', {}))
        main_dossier_calc['points'] = []
        main_dossier['ilac_calculation'] = main_dossier_calc
        main_json_str = json.dumps(main_dossier)
        
        url_main = f"{self.base_url}/dossiers/{doc_id}"
        payload_main = {
            "fields": {
                "customer": {"stringValue": str(customer)},
                "department": {"stringValue": str(department)},
                "contract_name": {"stringValue": str(contract_name)},
                "status": {"stringValue": str(dossier_data.get("status", "Concept"))},
                "duration_years": {"integerValue": str(dossier_data.get("settings", {}).get("duration_years", 3))},
                "total_points": {"integerValue": str(len(points))},
                "dossier_json": {"stringValue": main_json_str},
                "updated_at": {"stringValue": datetime.now().isoformat()}
            }
        }
        
        req_main = urllib.request.Request(
            url_main,
            data=json.dumps(payload_main).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="PATCH"
        )
        try:
            with urllib.request.urlopen(req_main, timeout=5) as resp:
                pass
        except Exception as e:
            print(f"FirebaseStore.save_dossier main error: {e}")

        # Save points if present
        if points:
            points_json_str = json.dumps(points)
            url_points = f"{self.base_url}/dossier_points/{doc_id}"
            payload_points = {
                "fields": {
                    "points_count": {"integerValue": str(len(points))},
                    "points_json": {"stringValue": points_json_str}
                }
            }
            req_points = urllib.request.Request(
                url_points,
                data=json.dumps(payload_points).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="PATCH"
            )
            try:
                with urllib.request.urlopen(req_points, timeout=8) as resp:
                    pass
            except Exception as e:
                print(f"FirebaseStore.save_dossier points error: {e}")

        return True

    def list_hierarchy(self):
        """Fetches all dossiers from Firestore and builds hierarchy structure."""
        url = f"{self.base_url}/dossiers"
        req = urllib.request.Request(url, method="GET")
        hierarchy = {}
        customer_meta = {}
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                documents = data.get("documents", [])
                for doc in documents:
                    fields = doc.get("fields", {})
                    cust = fields.get("customer", {}).get("stringValue", "")
                    dept = fields.get("department", {}).get("stringValue", "")
                    con = fields.get("contract_name", {}).get("stringValue", "")
                    status = fields.get("status", {}).get("stringValue", "Concept")
                    duration_years = int(fields.get("duration_years", {}).get("integerValue", 3))
                    total_points = int(fields.get("total_points", {}).get("integerValue", 0))

                    if not cust or not dept or not con:
                        continue

                    customer_meta.setdefault(cust, {
                        "customer": cust,
                        "has_logo": False,
                        "initials": cust[:2].upper() if len(cust) >= 2 else cust.upper(),
                        "logo_url": None
                    })

                    hierarchy.setdefault(cust, {}).setdefault(dept, []).append({
                        "contract_name": con,
                        "status": status,
                        "is_active": (status == "Actief"),
                        "duration_years": duration_years,
                        "total_points": total_points,
                        "has_ilac": total_points > 0,
                        "has_pricelist": True,
                        "fee_per_month": 0.0,
                        "tracking_active": (status == "Actief")
                    })
        except Exception as e:
            print(f"FirebaseStore.list_hierarchy error: {e}")

        return {"hierarchy": hierarchy, "customer_meta": customer_meta}

    def get_settings(self, name):
        """Fetches setting JSON from Firestore."""
        url = f"{self.base_url}/settings/{name}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                fields = data.get("fields", {})
                json_str = fields.get("data_json", {}).get("stringValue", "")
                if json_str:
                    return json.loads(json_str)
        except Exception:
            pass
        return None

    def save_settings(self, name, data):
        """Saves setting JSON to Firestore."""
        url = f"{self.base_url}/settings/{name}"
        payload = {
            "fields": {
                "name": {"stringValue": name},
                "data_json": {"stringValue": json.dumps(data)},
                "updated_at": {"stringValue": datetime.now().isoformat()}
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="PATCH"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return True
        except Exception as e:
            print(f"FirebaseStore.save_settings error: {e}")
            return False
