// =============================================================================

// FIREBASE CLOUD ADAPTER (Voor GitHub Pages & Online Samenwerking)

// =============================================================================

const firebaseConfig = {

  apiKey: "AIzaSyCTqBxLUg-_3jw66C4aujjTL3LD2XHdYVg",

  authDomain: "laas-suite.firebaseapp.com",

  databaseURL: "https://laas-suite-default-rtdb.europe-west1.firebasedatabase.app",

  projectId: "laas-suite",

  storageBucket: "laas-suite.firebasestorage.app",

  messagingSenderId: "850325086691",

  appId: "1:850325086691:web:0ccc569dfdd1c19e1700d6"

};

let db = null;

if (typeof firebase !== 'undefined') {

  try {

    if (!firebase.apps.length) {

      firebase.initializeApp(firebaseConfig);

    }

    db = firebase.firestore();

    console.log("Firebase Cloud Firestore successfully connected!");

  } catch (err) {

    console.error("Firebase init error:", err);

  }

}

const isCloudMode = !window.location.port || window.location.hostname.includes('github.io') || window.location.protocol === 'file:';

const { createApp, ref, computed, onMounted } = Vue;

const app = createApp({

  setup() {

    // =========================================================================

    // STATE: PORTAL, HIERARCHY, SEARCH & ARCHIVE

    // =========================================================================

    const currentView = ref('clients_portal'); // 'clients_portal' or 'calculation_phase1'

    const activePortalTab = ref('active'); // 'active' or 'archive'

    const hierarchy = ref({});

    const customerMeta = ref({});

    const archiveData = ref({ customers: [], departments: [], contracts: [] });

    const toastMessage = ref('');

    // Collapsible & Search

    const portalSearchQuery = ref('');

    const expandedCustomers = ref({}); // customerName: bool (default collapsed)

    // Selected contract context

    const selectedCustomer = ref('');

    const selectedDepartment = ref('');

    const selectedContract = ref('');

    const dossier = ref(null);

    const loadingDossier = ref(false);

    // Active Phase: 'phase1' (Audit & Productcalculatie) or 'phase2' (Contractvoorstel & Werkuren)

    const activePhase = ref('phase1');

    // Security

    const isUnlocked = ref(false);

    const showPasswordModal = ref(false);

    const inputPassword = ref('');

    const passwordError = ref(false);

    // Modals for Creation (3 Levels, NO fee, NO preset years)

    const showCreateCustomerModal = ref(false);

    const newCustomerName = ref('');

    const showCreateDeptModal = ref(false);

    const newDeptCustomer = ref('');

    const newDeptName = ref('');

    const showCreateContractModal = ref(false);

    const newContractCustomer = ref('');

    const newContractDept = ref('');

    const newContractName = ref('');

    // Rename Modal (Customer, Department, Contract)

    const showRenameModal = ref(false);

    const renameTarget = ref({ level: '', customer: '', department: '', contract_name: '', current_name: '', new_name: '' });

    const renamingItem = ref(false);

    const renameError = ref('');

    // Archive / Permanent Delete Confirmation Modal

    const showDeleteConfirmModal = ref(false);

    const deleteTarget = ref({ level: '', customer: '', department: '', contract_name: '' });

    const deletingItem = ref(false);

    // Clear calculation modal

    const showClearCalcModal = ref(false);

    const clearingCalc = ref(false);

    // =========================================================================

    // STATE: FASE 1 & FASE 2

    // =========================================================================

    const activeFase1Tab = ref('aggregated'); // 'aggregated', 'points', 'pricelist', 'renewal'

    const calcYears = ref(3);

    const uploadingILAC = ref(false);

    const uploadingPriceList = ref(false);

    const uploadingLogo = ref(false);

    const savingCalc = ref(false);

    // Filters for points and pricelist

    const pointsSearch = ref('');

    const pointsDeptFilter = ref('all');

    const priceSearch = ref('');

    const priceCategoryFilter = ref('all');

    // Dynamische Materiaalgroepen in Fase 2

    const activeMaterialGroupId = ref('grp_default');

    // Versiebeheer (Fase 2 Afronding & Fase 3)

    const showVersionModal = ref(false);

    const versionForm = ref({ tag: '', note: '' });

    const savingVersion = ref(false);

    const selectedProposalVersion = ref('current');

    // Fase 3: Voorstel & Waardepropositie Modals & State

    const editSectionModal = ref({

      show: false,

      key: '',

      title: '',

      content: '',

      isLegal: false

    });

    const showMetadataModal = ref(false);

    // Custom Pricelist Articles

    const showAddCustomArticleModal = ref(false);

    const customArticleForm = ref({

      article_nr: '',

      product_name: '',

      category: 'Maatwerk',

      packaging: 'stuks',

      content: '1 stuks',

      unit_price: 0.0,

      discount_pct: 0.0

    });

    // Material Modal in Fase 2 (Hardware, Tools, Manual items)

    const showAddMaterialModal = ref(false);

    const materialMode = ref('pricelist'); // 'pricelist' or 'custom'

    const materialPricelistSearch = ref('');

    const selectedPricelistItem = ref(null);

    const materialForm = ref({

      article_nr: '',

      description: '',

      category: 'Hardware & Tools',

      unit: 'stuks',

      qty: 1,

      unit_price: 0.0,

      discount_pct: 0.0,

      item_type: 'Eenmalig',

      notes: ''

    });

    // Fase 2 Work Hours Form

    const workHoursForm = ref({

      hourly_rate_partner: 63.0,

      partner_surcharge_pct: 15.0,

      travel_km_per_day: 76.0,

      travel_rate_per_km: 1.75,

      travel_cost_per_day: 152.95,

      work_days_year1: 87,

      work_days_per_year: 65,

      hours_per_day: 8.0,

      pm_pct: 15.0,

      supervision_pct: 10.0,

      interflon_hourly_rate: 110.0,

      oil_analyses_per_year: 0,

      analysis_unit_price: 220.0,

      software_license_annual: 1950.0,

      training_budget: 880.0

    });

    const savingWorkHours = ref(false);

    // Renewal Concept (preserved)

    const renewalForm = ref({

      elapsed_years: 3,

      renewal_years: 3,

      executed_tasks: []

    });

    const generatingRenewal = ref(false);

    // =========================================================================

    // TOAST HELPER & FORMATTERS

    // =========================================================================

    const showToast = (msg, duration = 3000) => {

      toastMessage.value = msg;

      setTimeout(() => {

        toastMessage.value = '';

      }, duration);

    };

    const formatCurrency = (num) => formatNum(num);

    const formatNum = (num) => {

      if (num === undefined || num === null || isNaN(num)) return '0,00';

      return Number(num).toLocaleString('nl-BE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    };

    // =========================================================================

    // API CALLS: HIERARCHY & ARCHIVE

    // =========================================================================

    const fetchHierarchy = async () => {

      if (isCloudMode && db) {

        try {

          const snapshot = await db.collection('dossiers').get();

          const newHierarchy = {};

          const newMeta = {};

          snapshot.forEach((doc) => {

            const fields = doc.data();

            const cust = fields.customer;

            const dept = fields.department;

            const con = fields.contract_name;

            if (!cust || !dept || !con) return;

            newMeta[cust] = {

              customer: cust,

              has_logo: false,

              logo_url: null,

              initials: cust.substring(0, 2).toUpperCase()

            };

            if (!newHierarchy[cust]) newHierarchy[cust] = {};

            if (!newHierarchy[cust][dept]) newHierarchy[cust][dept] = [];

            newHierarchy[cust][dept].push({

              contract_name: con,

              status: fields.status || 'Concept',

              is_active: (fields.status === 'Actief'),

              duration_years: parseInt(fields.duration_years || 3, 10),

              total_points: parseInt(fields.total_points || 0, 10),

              has_ilac: parseInt(fields.total_points || 0, 10) > 0,

              has_pricelist: true,

              fee_per_month: 0.0,

              tracking_active: (fields.status === 'Actief')

            });

          });

          hierarchy.value = newHierarchy;

          customerMeta.value = newMeta;

          return;

        } catch (err) {

          console.error("Cloud fetchHierarchy error:", err);

        }

      }

      try {

        const res = await fetch('/api/hierarchy');

        if (res.ok) {

          const data = await res.json();

          if (data.hierarchy !== undefined) {

            hierarchy.value = data.hierarchy;

            customerMeta.value = data.customer_meta || {};

          } else {

            hierarchy.value = data;

            customerMeta.value = {};

          }

        }

      } catch (err) {

        console.error('Fout bij ophalen hiërarchie:', err);

      }

    };

    const fetchArchive = async () => {

      try {

        const res = await fetch('/api/archive');

        if (res.ok) {

          archiveData.value = await res.json();

        }

      } catch (err) {

        console.error('Fout bij ophalen archief:', err);

      }

    };

    // =========================================================================

    // EXPAND / COLLAPSE ALL CUSTOMERS

    // =========================================================================

    const toggleCustomerExpand = (customer) => {

      expandedCustomers.value[customer] = !expandedCustomers.value[customer];

    };

    const isCustomerExpanded = (customer) => {

      return !!expandedCustomers.value[customer];

    };

    const expandAllCustomers = () => {

      const all = {};

      Object.keys(hierarchy.value).forEach(k => {

        all[k] = true;

      });

      expandedCustomers.value = all;

    };

    const collapseAllCustomers = () => {

      expandedCustomers.value = {};

    };

    // Filtered customers based on search

    const filteredCustomersList = computed(() => {

      const q = portalSearchQuery.value.trim().toLowerCase();

      const custs = Object.keys(hierarchy.value);

      if (!q) return custs;

      return custs.filter(c => {

        if (c.toLowerCase().includes(q)) return true;

        const depts = hierarchy.value[c] || {};

        for (const [deptName, contracts] of Object.entries(depts)) {

          if (deptName.toLowerCase().includes(q)) return true;

          if (contracts && contracts.some(con => con.contract_name.toLowerCase().includes(q))) {

            return true;

          }

        }

        return false;

      });

    });

    const getCustomerContractCount = (customer) => {

      const depts = hierarchy.value[customer] || {};

      let total = 0;

      for (const list of Object.values(depts)) {

        if (Array.isArray(list)) total += list.length;

      }

      return total;

    };

    // Customer Logo Upload

    const uploadCustomerLogo = async (customer, event) => {

      const file = event.target.files[0];

      if (!file) return;

      const formData = new FormData();

      formData.append('file', file);

      uploadingLogo.value = true;

      try {

        const res = await fetch(`/api/customer/${encodeURIComponent(customer)}/logo`, {

          method: 'POST',

          body: formData

        });

        const data = await res.json();

        if (res.ok) {

          showToast(`Logo voor ${customer} succesvol opgeslagen!`);

          if (customerMeta.value[customer]) {

            customerMeta.value[customer].has_logo = true;

            customerMeta.value[customer].logo_url = data.logo_url;

          }

          if (dossier.value && dossier.value.customer === customer) {

            dossier.value.customer_logo_url = data.logo_url;

          }

          await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

        } else {

          alert(data.error || 'Fout bij uploaden logo');

        }

      } catch (err) {

        alert('Netwerkfout bij uploaden logo');

      } finally {

        uploadingLogo.value = false;

        event.target.value = '';

      }

    };

    // Password unlock

    const unlockSystem = async () => {

      passwordError.value = false;

      if (isCloudMode) {

        const val = (inputPassword.value || '').trim();

        const valid = ['1nt3rfl0n', 'laas2026', 'interflon', 'Interflon', 'Interflon2026'];

        if (valid.includes(val)) {

          isUnlocked.value = true;

          showPasswordModal.value = false;

          inputPassword.value = '';

          showToast('Beheerdersmodus ontgrendeld');

          return;

        } else {

          passwordError.value = true;

          return;

        }

      }

      try {

        const res = await fetch('/api/verify_password', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ password: inputPassword.value })

        });

        if (res.ok) {

          isUnlocked.value = true;

          showPasswordModal.value = false;

          inputPassword.value = '';

          showToast('Beheerdersmodus ontgrendeld');

        } else {

          passwordError.value = true;

        }

      } catch (err) {

        passwordError.value = true;

      }

    };

    const lockSystem = () => {

      isUnlocked.value = false;

      showToast('Beheerdersmodus vergrendeld');

    };

    // Creation helpers

    const openCreateCustomer = () => {

      newCustomerName.value = '';

      showCreateCustomerModal.value = true;

    };

    const submitCreateCustomer = async () => {

      if (!newCustomerName.value.trim()) return;

      try {

        const res = await fetch('/api/customer/create', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ customer: newCustomerName.value.trim() })

        });

        if (res.ok) {

          showToast(`Klant '${newCustomerName.value.trim()}' succesvol aangemaakt!`);

          showCreateCustomerModal.value = false;

          await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

        } else {

          const err = await res.json();

          alert(err.error || 'Fout bij aanmaken klant');

        }

      } catch (e) {

        alert('Netwerkfout bij aanmaken klant');

      }

    };

    const openCreateDept = (customer = '') => {

      newDeptCustomer.value = customer || Object.keys(hierarchy.value)[0] || '';

      newDeptName.value = '';

      showCreateDeptModal.value = true;

    };

    const submitCreateDept = async () => {

      if (!newDeptCustomer.value || !newDeptName.value.trim()) return;

      try {

        const res = await fetch('/api/department/create', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ customer: newDeptCustomer.value, department: newDeptName.value.trim() })

        });

        if (res.ok) {

          showToast(`Afdeling '${newDeptName.value.trim()}' aangemaakt onder ${newDeptCustomer.value}!`);

          showCreateDeptModal.value = false;

          await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

        } else {

          const err = await res.json();

          alert(err.error || 'Fout bij aanmaken afdeling');

        }

      } catch (e) {

        alert('Netwerkfout bij aanmaken afdeling');

      }

    };

    const openCreateContract = (customer = '', department = '') => {

      newContractCustomer.value = customer || Object.keys(hierarchy.value)[0] || '';

      const depts = Object.keys(hierarchy.value[newContractCustomer.value] || {});

      newContractDept.value = department || depts[0] || '';

      newContractName.value = '';

      showCreateContractModal.value = true;

    };

    const submitCreateContract = async () => {

      if (!newContractCustomer.value || !newContractDept.value || !newContractName.value.trim()) {

        alert('Gelieve alle velden in te vullen.');

        return;

      }

      try {

        const res = await fetch('/api/contract/create', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            customer: newContractCustomer.value,

            department: newContractDept.value,

            contract_name: newContractName.value.trim()

          })

        });

        if (res.ok) {

          showToast(`Contract '${newContractName.value.trim()}' succesvol aangemaakt!`);

          showCreateContractModal.value = false;

          await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

          // Open the new contract

          await openContract(newContractCustomer.value, newContractDept.value, newContractName.value.trim());

        } else {

          const err = await res.json();

          alert(err.error || 'Fout bij aanmaken contract');

        }

      } catch (e) {

        alert('Netwerkfout bij aanmaken contract');

      }

    };

    // Archive & Delete

    const archiveContract = async (customer, department, contract_name) => {

      if (!confirm(`Contract '${contract_name}' archiveren?`)) return;

      try {

        const res = await fetch('/api/archive/item', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ level: 'contract', customer, department, contract_name })

        });

        if (res.ok) {

          showToast(`Contract '${contract_name}' verplaatst naar Archief.`);

          await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

          await fetchArchive();

        }

      } catch (e) {

        alert('Fout bij archiveren contract');

      }

    };

    const archiveDepartment = async (customer, department) => {

      if (!confirm(`Afdeling '${department}' en alle onderliggende contracten archiveren?`)) return;

      try {

        const res = await fetch('/api/archive/item', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ level: 'department', customer, department })

        });

        if (res.ok) {

          showToast(`Afdeling '${department}' verplaatst naar Archief.`);

          await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

          await fetchArchive();

        }

      } catch (e) {

        alert('Fout bij archiveren afdeling');

      }

    };

    const archiveCustomer = async (customer) => {

      if (!confirm(`Klant '${customer}' en alle onderliggende afdelingen archiveren?`)) return;

      try {

        const res = await fetch('/api/archive/item', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ level: 'customer', customer })

        });

        if (res.ok) {

          showToast(`Klant '${customer}' verplaatst naar Archief.`);

          await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

          await fetchArchive();

        }

      } catch (e) {

        alert('Fout bij archiveren klant');

      }

    };

    const restoreArchivedItem = async (level, customer, department = null, contract_name = null) => {

      try {

        const res = await fetch('/api/restore/item', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ level, customer, department, contract_name })

        });

        if (res.ok) {

          showToast(`${level.toUpperCase()} succesvol hersteld naar actieve lijst!`);

          await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

          await fetchArchive();

        }

      } catch (e) {

        alert('Fout bij herstellen uit archief');

      }

    };

    const confirmPermanentDelete = (level, customer, department = null, contract_name = null) => {

      if (!isUnlocked.value) {

        showPasswordModal.value = true;

        showToast('Beheerderswachtwoord vereist om items definitief te wissen');

        return;

      }

      deleteTarget.value = { level, customer, department, contract_name };

      showDeleteConfirmModal.value = true;

    };

    const executePermanentDelete = async () => {

      deletingItem.value = true;

      try {

        const res = await fetch('/api/archive/permanent_delete', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(deleteTarget.value)

        });

        if (res.ok) {

          showToast(`Definitief verwijderd van schijf.`);

          showDeleteConfirmModal.value = false;

          await fetchArchive();

        } else {

          const err = await res.json();

          alert(err.error || 'Fout bij definitief verwijderen');

        }

      } catch (e) {

        alert('Netwerkfout bij definitief verwijderen');

      } finally {

        deletingItem.value = false;

      }

    };

    // =========================================================================

    // RENAME CUSTOMER, DEPARTMENT, CONTRACT (BEHEERDERSMODUS + DUBBELE CHECK)

    // =========================================================================

    const openRenameModal = (level, customer, department = null, contract_name = null) => {

      if (!isUnlocked.value) {

        showPasswordModal.value = true;

        showToast('Beheerderswachtwoord vereist om benamingen aan te passen');

        return;

      }

      let currentName = '';

      if (level === 'customer') currentName = customer;

      else if (level === 'department') currentName = department;

      else if (level === 'contract') currentName = contract_name;

      renameError.value = '';

      renameTarget.value = {

        level,

        customer,

        department: department || '',

        contract_name: contract_name || '',

        current_name: currentName,

        new_name: currentName

      };

      showRenameModal.value = true;

    };

    const executeRename = async () => {

      const target = renameTarget.value;

      const trimmedNew = (target.new_name || '').trim();

      if (!trimmedNew) {

        renameError.value = 'Naam mag niet leeg zijn.';

        return;

      }

      if (trimmedNew === target.current_name) {

        renameError.value = 'De nieuwe naam is hetzelfde als de huidige naam.';

        return;

      }

      renamingItem.value = true;

      renameError.value = '';

      try {

        const res = await fetch('/api/hierarchy/rename', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            level: target.level,

            customer: target.customer,

            department: target.department || null,

            contract_name: target.contract_name || null,

            new_name: trimmedNew

          })

        });

        const data = await res.json();

        if (res.ok) {

          showToast(`${target.level.toUpperCase()} succesvol hernoemd naar '${trimmedNew}'!`);

          showRenameModal.value = false;

          // If current open dossier was affected, update context

          if (dossier.value) {

            if (target.level === 'customer' && selectedCustomer.value === target.customer) {

              selectedCustomer.value = trimmedNew;

              dossier.value.customer = trimmedNew;

              if (dossier.value.settings) dossier.value.settings.customer = trimmedNew;

            } else if (target.level === 'department' && selectedCustomer.value === target.customer && selectedDepartment.value === target.department) {

              selectedDepartment.value = trimmedNew;

              dossier.value.department = trimmedNew;

              if (dossier.value.settings) dossier.value.settings.department = trimmedNew;

            } else if (target.level === 'contract' && selectedCustomer.value === target.customer && selectedDepartment.value === target.department && selectedContract.value === target.contract_name) {

              selectedContract.value = trimmedNew;

              dossier.value.contract_name = trimmedNew;

              if (dossier.value.settings) dossier.value.settings.contract_name = trimmedNew;

            }

          }

          await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

        } else {

          renameError.value = data.error || 'Fout bij hernoemen.';

        }

      } catch (e) {

        renameError.value = 'Netwerkfout bij hernoemen.';

      } finally {

        renamingItem.value = false;

      }

    };

    // =========================================================================

    // =========================================================================

    // OPEN CONTRACT DOSSIER & SYNC

    // =========================================================================

    const openContract = async (customer, department, contract_name) => {

      selectedCustomer.value = customer;

      selectedDepartment.value = department;

      selectedContract.value = contract_name;

      loadingDossier.value = true;

      if (isCloudMode && db) {

        try {

          const docId = `${customer}__${department}__${contract_name}`.replace(/[\/\s]/g, '_');

          const doc = await db.collection('dossiers').doc(docId).get();

          if (doc.exists) {

            const data = doc.data();

            let dJson = {};

            if (data.dossier_json) {

              dJson = JSON.parse(data.dossier_json);

            } else {

              dJson = data;

            }

            try {

              const ptsDoc = await db.collection('dossier_points').doc(docId).get();

              if (ptsDoc.exists) {

                const ptsData = ptsDoc.data();

                dJson.ilac_calculation = dJson.ilac_calculation || {};

                dJson.ilac_calculation.points = JSON.parse(ptsData.points_json || '[]');

              }

            } catch (e) {}

            dossier.value = dJson;

            calcYears.value = dJson.settings?.duration_years || 3;

            activePhase.value = 'phase1';

            activeFase1Tab.value = 'aggregated';

            if (dJson.fase2 && dJson.fase2.work_hours) {

              workHoursForm.value = { ...workHoursForm.value, ...dJson.fase2.work_hours };

            }

            currentView.value = 'calculation_phase1';

            loadingDossier.value = false;

            return;

          }

        } catch (err) {

          console.error("Cloud openContract error:", err);

        }

      }

      try {

        const res = await fetch(`/api/dossier/${encodeURIComponent(customer)}/${encodeURIComponent(department)}/${encodeURIComponent(contract_name)}`);

        if (res.ok) {

          const data = await res.json();

          dossier.value = data;

          calcYears.value = data.settings?.duration_years || 3;

          activePhase.value = 'phase1';

          activeFase1Tab.value = 'aggregated';

          // Sync Fase 2 Work Hours

          if (data.fase2 && data.fase2.work_hours) {

            workHoursForm.value = { ...workHoursForm.value, ...data.fase2.work_hours };

          }

          currentView.value = 'calculation_phase1';

        } else {

          alert('Kon dossier niet laden.');

        }

      } catch (err) {

        alert('Fout bij ophalen van contractdossier.');

      } finally {

        loadingDossier.value = false;

      }

    };

    const backToPortal = async () => {

      currentView.value = 'clients_portal';

      dossier.value = null;

      activePhase.value = 'phase1';

      await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

    };

    // =========================================================================

    // PRICE LIST STATE: UPLOAD VS RENEW

    // =========================================================================

    const hasPriceList = computed(() => {

      return !!(dossier.value && dossier.value.price_list && Array.isArray(dossier.value.price_list.items) && dossier.value.price_list.items.length > 0);

    });

    const priceListBtnText = computed(() => {

      return hasPriceList.value ? 'Prijslijst vernieuwen' : 'Prijslijst uploaden';

    });

    const onPriceListFileChange = async (event) => {

      const file = event.target.files[0];

      if (!file || !dossier.value) return;

      const formData = new FormData();

      formData.append('file', file);

      uploadingPriceList.value = true;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/pricelist/upload`, {

          method: 'POST',

          body: formData

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showToast(data.message || 'Prijslijst succesvol verwerkt!');

        } else {

          alert(data.error || 'Fout bij inlezen prijslijst');

        }

      } catch (err) {

        alert('Netwerkfout bij uploaden prijslijst');

      } finally {

        uploadingPriceList.value = false;

        event.target.value = '';

      }

    };

    // =========================================================================

    // ILAC-AUDIT UPLOAD & CLEAR CALCULATION

    // =========================================================================

    const onILACFileChange = async (event) => {

      const file = event.target.files[0];

      if (!file || !dossier.value) return;

      const formData = new FormData();

      formData.append('file', file);

      uploadingILAC.value = true;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/ilac/upload`, {

          method: 'POST',

          body: formData

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showToast(data.message || 'ILAC-audit succesvol geanalyseerd!');

        } else {

          alert(data.error || 'Fout bij analyseren ILAC bestand');

        }

      } catch (err) {

        alert('Netwerkfout bij analyseren ILAC bestand');

      } finally {

        uploadingILAC.value = false;

        event.target.value = '';

      }

    };

    const confirmClearCalculation = async () => {

      if (!dossier.value) return;

      clearingCalc.value = true;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/ilac/clear`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' }

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showClearCalcModal.value = false;

          showToast('Calculatie en audit succesvol leeggemaakt!');

        } else {

          alert(data.error || 'Fout bij leegmaken calculatie');

        }

      } catch (e) {

        alert('Netwerkfout bij leegmaken calculatie');

      } finally {

        clearingCalc.value = false;

      }

    };

    const changeContractYears = async (years) => {

      if (!dossier.value || calcYears.value === years) return;

      calcYears.value = years;

      savingCalc.value = true;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/ilac/recalculate`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ contract_years: years })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          if (data.dossier.fase2 && data.dossier.fase2.work_hours) {

            workHoursForm.value = { ...workHoursForm.value, ...data.dossier.fase2.work_hours };

          }

          showToast(`Calculatie realtime herberekend voor ${years} jaar!`);

        }

      } catch (err) {

        console.error('Fout bij herberekenen looptijd:', err);

      } finally {

        savingCalc.value = false;

      }

    };

    const overrideProductPackaging = async (prodOrName, articleNr) => {

      if (!dossier.value) return;

      let comboKey = null;

      let prodName = prodOrName;

      let toolName = null;

      if (typeof prodOrName === 'object' && prodOrName !== null) {

        comboKey = prodOrName.combo_key || null;

        prodName = prodOrName.product_name;

        toolName = prodOrName.tool || null;

      }

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/product/packaging_override`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            combo_key: comboKey,

            product_name: prodName,

            tool: toolName,

            article_nr: articleNr

          })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showToast(`Verpakking voor ${prodName} bijgewerkt!`);

        } else {

          alert(data.error || 'Fout bij aanpassen verpakking');

        }

      } catch (e) {

        alert('Netwerkfout bij aanpassen verpakking');

      }

    };

    const updateItemDiscount = async (artNr, discountPct) => {

      if (!dossier.value) return;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/pricelist/item_discount`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ article_nr: artNr, discount_pct: discountPct })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showToast(`Korting (${discountPct}%) toegepast op artikel ${artNr}!`);

        }

      } catch (err) {

        console.error('Fout bij bijwerken korting:', err);

      }

    };

    // =========================================================================

    // FASE 2: MANUAL MATERIALS & HARDWARE

    // =========================================================================

    const filteredPriceListForMaterial = computed(() => {

      const q = materialPricelistSearch.value.trim().toLowerCase();

      const items = (dossier.value && dossier.value.price_list && dossier.value.price_list.items) || [];

      if (!q) return items.slice(0, 40);

      return items.filter(it => {

        return (it.article_nr && it.article_nr.toLowerCase().includes(q)) ||

               (it.product_name && it.product_name.toLowerCase().includes(q)) ||

               (it.description && it.description.toLowerCase().includes(q)) ||

               (it.category && it.category.toLowerCase().includes(q));

      }).slice(0, 40);

    });

    // =========================================================================

    // CALCULATION & CONTRACT SETTINGS (TANDWIELICOONTJE)

    // =========================================================================

    const showCalcSettingsModal = ref(false);

    const savingCalcSettings = ref(false);

    const calcSettingsTab = ref('partner'); // 'partner', 'management', 'services', 'conversion'

    // Standard categories for category discounts

    const standardCategoriesList = ref([

      'Oliën',

      'Food Oliën',

      'Vetten',

      'Food Vetten',

      'Reinigers',

      'Hardware & Tools',

      'Hulpmaterialen',

      'Automatic lubrication',

      'Diensten'

    ]);

    // Vergeet-mij-niet Tools Checklist State

    const toolChecklist = ref({});

    const filteredDetectedTools = computed(() => {

      if (!detectedTools.value || !detectedTools.value.length) return [];

      return detectedTools.value.filter(t => {

        const n = (t.tool_name || '').toLowerCase();

        return !n.includes('spuitbus') && !n.includes('aerosol') && !n.includes('spray');

      });

    });

    const completedToolsCount = computed(() => {

      return filteredDetectedTools.value.filter(t => toolChecklist.value[t.tool_name]).length;

    });

    // Manual Units Override & Full-Box Rounding

    const updatingUnits = ref(false);

    const updateProductUnits = async (prod, unitsVal) => {

      if (!currentContract.value || !prod) return;

      const val = parseInt(unitsVal);

      if (isNaN(val) || val < 1) {

        showToast('Vul een geldig aantal units in (minimaal 1)');

        return;

      }

      try {

        updatingUnits.value = true;

        const res = await fetch(`/api/contract/${currentKlant.value}/${currentAfdeling.value}/${currentContract.value}/product/units_override`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            combo_key: prod.combo_key,

            product_name: prod.product_name,

            tool: prod.tool,

            units: val

          })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showToast(`Aantal units aangepast naar ${val}`);

        } else {

          showToast(data.error || 'Fout bij aanpassen units');

        }

      } catch (e) {

        showToast('Netwerkfout bij aanpassen units');

      } finally {

        updatingUnits.value = false;

      }

    };

    const roundProductUnits = (prod, boxSize, direction) => {

      const currentUnits = parseInt(prod.packages_needed || prod.packs_needed) || 1;

      let newUnits = currentUnits;

      if (direction === 'up') {

        newUnits = Math.ceil(currentUnits / boxSize) * boxSize;

        if (newUnits <= currentUnits) newUnits += boxSize;

      } else {

        newUnits = Math.floor(currentUnits / boxSize) * boxSize;

        if (newUnits >= currentUnits) newUnits -= boxSize;

        if (newUnits < 1) newUnits = 1;

      }

      updateProductUnits(prod, newUnits);

    };

    const resetProductUnits = async (prod) => {

      if (!currentContract.value || !prod) return;

      try {

        updatingUnits.value = true;

        const res = await fetch(`/api/contract/${currentKlant.value}/${currentAfdeling.value}/${currentContract.value}/product/units_override`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            combo_key: prod.combo_key,

            product_name: prod.product_name,

            tool: prod.tool,

            units: null

          })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showToast('Automatisch berekende hoeveelheid hersteld');

        } else {

          showToast(data.error || 'Fout bij herstellen units');

        }

      } catch (e) {

        showToast('Netwerkfout bij herstellen units');

      } finally {

        updatingUnits.value = false;

      }

    };

    // Manual Staffel Tier Override

    const applyManualTier = async (item, minQty) => {

      if (!currentContract.value || !item) return;

      try {

        const res = await fetch(`/api/contract/${currentKlant.value}/${currentAfdeling.value}/${currentContract.value}/product/tier_override`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            combo_key: item.combo_key,

            product_name: item.product_name,

            tool: item.tool,

            tier_min: minQty

          })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          if (selectedStaffelItem.value) {

            selectedStaffelItem.value.active_tier_min = minQty;

            selectedStaffelItem.value.is_manual_tier = true;

          }

          showToast(`Staffeltrap ${minQty}+ succesvol toegepast`);

        } else {

          showToast(data.error || 'Fout bij instellen staffeltrap');

        }

      } catch (e) {

        showToast('Netwerkfout bij instellen staffeltrap');

      }

    };

    const resetManualTier = async (item) => {

      if (!currentContract.value || !item) return;

      try {

        const res = await fetch(`/api/contract/${currentKlant.value}/${currentAfdeling.value}/${currentContract.value}/product/tier_override`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            combo_key: item.combo_key,

            product_name: item.product_name,

            tool: item.tool,

            auto: true

          })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          if (selectedStaffelItem.value) {

            selectedStaffelItem.value.is_manual_tier = false;

          }

          showToast('Automatische staffel hersteld');

        } else {

          showToast(data.error || 'Fout bij herstellen staffel');

        }

      } catch (e) {

        showToast('Netwerkfout bij herstellen staffel');

      }

    };

    const calcSettingsForm = ref({

      duration_years: 3,

      gram_per_pompslag: 1.5,

      ml_per_second: 1.0,

      global_discount_pct: 0.0,

      category_discounts: {},

      work_hours: {

        work_days_year1: 87,

        work_days_per_year: 65,

        hours_per_day: 8.0,

        hourly_rate_partner: 63.0,

        partner_surcharge_pct: 15.0,

        travel_cost_per_day: 152.95,

        travel_km_per_day: 76.0,

        travel_rate_per_km: 1.75,

        pm_pct: 15.0,

        supervision_pct: 10.0,

        interflon_hourly_rate: 110.0,

        oil_analyses_per_year: 0,

        analysis_unit_price: 220.0,

        software_license_annual: 1950.0,

        training_budget: 880.0

      }

    });

    const openCalcSettingsModal = () => {

      if (!isUnlocked.value) {

        showPasswordModal.value = true;

        showToast('Beheerderswachtwoord vereist om calculatie-instellingen te openen');

        return;

      }

      if (!dossier.value) return;

      const s = dossier.value.settings || {};

      const wh = (dossier.value.fase2 && dossier.value.fase2.work_hours) || {};

      calcSettingsForm.value = {

        duration_years: s.duration_years || 3,

        gram_per_pompslag: s.gram_per_pompslag !== undefined ? s.gram_per_pompslag : 1.5,

        ml_per_second: s.ml_per_second !== undefined ? s.ml_per_second : 1.0,

        global_discount_pct: s.global_discount_pct !== undefined ? s.global_discount_pct : 0.0,

        category_discounts: { ...(s.category_discounts || {}) },

        work_hours: {

          work_days_year1: wh.work_days_year1 !== undefined ? wh.work_days_year1 : 87,

          work_days_per_year: wh.work_days_per_year !== undefined ? wh.work_days_per_year : 65,

          hours_per_day: wh.hours_per_day !== undefined ? wh.hours_per_day : 8.0,

          hourly_rate_partner: wh.hourly_rate_partner !== undefined ? wh.hourly_rate_partner : 63.0,

          partner_surcharge_pct: wh.partner_surcharge_pct !== undefined ? wh.partner_surcharge_pct : 15.0,

          travel_cost_per_day: wh.travel_cost_per_day !== undefined ? wh.travel_cost_per_day : 152.95,

          travel_km_per_day: wh.travel_km_per_day !== undefined ? wh.travel_km_per_day : 76.0,

          travel_rate_per_km: wh.travel_rate_per_km !== undefined ? wh.travel_rate_per_km : 1.75,

          pm_pct: wh.pm_pct !== undefined ? wh.pm_pct : 15.0,

          supervision_pct: wh.supervision_pct !== undefined ? wh.supervision_pct : 10.0,

          interflon_hourly_rate: wh.interflon_hourly_rate !== undefined ? wh.interflon_hourly_rate : 110.0,

          oil_analyses_per_year: wh.oil_analyses_per_year !== undefined ? wh.oil_analyses_per_year : 0,

          analysis_unit_price: wh.analysis_unit_price !== undefined ? wh.analysis_unit_price : 220.0,

          software_license_annual: (wh.software_license_annual && parseFloat(wh.software_license_annual) > 0) ? parseFloat(wh.software_license_annual) : 1950.0,

          training_budget: wh.training_budget !== undefined ? wh.training_budget : 880.0

        }

      };

      showCalcSettingsModal.value = true;

    };

    const updateTravelFromKm = () => {

      const km = parseFloat(calcSettingsForm.value.work_hours.travel_km_per_day) || 0;

      const rate = parseFloat(calcSettingsForm.value.work_hours.travel_rate_per_km) || 0;

      calcSettingsForm.value.work_hours.travel_cost_per_day = Math.round(km * rate * 100) / 100;

    };

    const resetCalcSettingsToDefaults = () => {

      if (!confirm('Standaard benchmark parameters (Kenny Umicore calculatiemodel) herstellen?')) return;

      calcSettingsForm.value = {

        duration_years: 3,

        gram_per_pompslag: 1.5,

        ml_per_second: 1.0,

        work_hours: {

          work_days_year1: 87,

          work_days_per_year: 65,

          hours_per_day: 8.0,

          hourly_rate_partner: 63.0,

          partner_surcharge_pct: 15.0,

          travel_cost_per_day: 152.95,

          travel_km_per_day: 76.0,

          travel_rate_per_km: 1.75,

          pm_pct: 15.0,

          supervision_pct: 10.0,

          interflon_hourly_rate: 110.0,

          oil_analyses_per_year: 0,

          analysis_unit_price: 220.0,

          software_license_annual: 1950.0,

          training_budget: 880.0

        }

      };

    };

    const settingsPreview = computed(() => {

      const wh = calcSettingsForm.value.work_hours || {};

      const years = parseInt(calcYears.value) || 3;

      const y1 = parseFloat(dossier.value?.fase2?.work_hours?.work_days_year1 || 0);

      const yOther = parseFloat(dossier.value?.fase2?.work_hours?.work_days_per_year || 0);

      const totalDays = y1 + (yOther * Math.max(0, years - 1));

      const hoursPerDay = parseFloat(wh.hours_per_day) || 8;

      const totalPartnerHours = totalDays * hoursPerDay;

      const partnerRate = (parseFloat(wh.hourly_rate_partner) || 0) * (1.0 + (parseFloat(wh.partner_surcharge_pct) || 0) / 100.0);

      const partnerCost = totalPartnerHours * partnerRate;

      const travelCost = totalDays * (parseFloat(wh.travel_cost_per_day) || 0);

      const executionTotal = partnerCost + travelCost;

      const interflonRate = parseFloat(wh.interflon_hourly_rate) || 110;

      const pmHours = totalPartnerHours * ((parseFloat(wh.pm_pct) || 0) / 100.0);

      const supHours = totalPartnerHours * ((parseFloat(wh.supervision_pct) || 0) / 100.0);

      const mgmtCost = (pmHours + supHours) * interflonRate;

      const analysesCost = (parseFloat(wh.oil_analyses_per_year) || 0) * (parseFloat(wh.analysis_unit_price) || 0) * years;

      const softwareCost = (parseFloat(wh.software_license_annual) || 0) * years;

      const trainingCost = parseFloat(wh.training_budget) || 0;

      const servicesTotal = mgmtCost + analysesCost + softwareCost + trainingCost;

      return {

        totalDays,

        totalPartnerHours,

        executionTotal,

        pmHours,

        supHours,

        mgmtCost,

        servicesTotal

      };

    });

    const saveCalcSettings = async () => {

      if (!dossier.value) return;

      if (!isUnlocked.value) {

        showPasswordModal.value = true;

        showToast('Beheerderswachtwoord vereist om instellingen op te slaan');

        return;

      }

      savingCalcSettings.value = true;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/settings/save`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(calcSettingsForm.value)

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          calcYears.value = data.dossier.settings?.duration_years || 3;

          if (data.dossier.fase2 && data.dossier.fase2.work_hours) {

            workHoursForm.value = { ...workHoursForm.value, ...data.dossier.fase2.work_hours };

          }

          showCalcSettingsModal.value = false;

          showToast('Calculatie- en tariefparameters succesvol bijgewerkt!');

        } else {

          alert(data.error || 'Fout bij opslaan instellingen');

        }

      } catch (e) {

        alert('Netwerkfout bij opslaan instellingen');

      } finally {

        savingCalcSettings.value = false;

      }

    };

    // =========================================================================

    // FASE 2: SAVE WORK HOURS

    // =========================================================================

    const saveFase2WorkHours = async () => {

      if (!dossier.value) return;

      savingWorkHours.value = true;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/fase2/save`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ work_hours: workHoursForm.value })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showToast('Werkuren en contractvoorstel succesvol opgeslagen!');

        } else {

          alert(data.error || 'Fout bij opslaan werkuren');

        }

      } catch (e) {

        alert('Netwerkfout bij opslaan werkuren');

      } finally {

        savingWorkHours.value = false;

      }

    };

    // Active version snapshot for Fase 3 version selection

    const activeVersionSnapshot = computed(() => {

      if (!dossier.value || !selectedProposalVersion.value || selectedProposalVersion.value === 'current') {

        return null;

      }

      return (dossier.value.versions || []).find(v => v.version_tag === selectedProposalVersion.value) || null;

    });

    // Live computed proposal summary in frontend (dynamically switches when version snapshot selected)

    const proposalSummary = computed(() => {

      if (activeVersionSnapshot.value) {

        return activeVersionSnapshot.value.fase2_proposal_summary || activeVersionSnapshot.value.summary || {};

      }

      if (!dossier.value) {

        return {

          products_total: 0,

          hardware_total: 0,

          total_execution_cost: 0,

          partner_hours_cost: 0,

          travel_total_cost: 0,

          total_services_cost: 0,

          management_cost: 0,

          grand_contract_total: 0,

          monthly_fee: 0

        };

      }

      return (dossier.value.fase2 && dossier.value.fase2.proposal_summary) || {};

    });

    const proposalMaterialGroups = computed(() => {

      if (activeVersionSnapshot.value && activeVersionSnapshot.value.material_groups) {

        return activeVersionSnapshot.value.material_groups;

      }

      return materialGroups.value;

    });

    // =========================================================================

    // DYNAMISCHE CATEGORIEEN & MATERIAALGROEPEN (FASE 2)

    // =========================================================================

    const availableMaterialCategories = computed(() => {

      const cats = new Set();

      (priceListItems.value || []).forEach(item => {

        if (item && item.category && String(item.category).trim()) {

          cats.add(String(item.category).trim());

        }

      });

      const core = [

        'Hardware & Tools',

        'Interflon hardware',

        'Hulpmaterialen onderdelen',

        'Smeerapparatuur',

        'Single Point Lubricators / Pulsarlube',

        'Tools - Opslag - Kleurcodering',

        'Voorraadbeheer - Inrichting',

        'Olieanalyse',

        'Diensten & Software',

        'Maatwerk'

      ];

      core.forEach(c => cats.add(c));

      return Array.from(cats).sort();

    });

    const materialGroups = computed({

      get: () => {

        if (!dossier.value) return [];

        if (!dossier.value.fase2) dossier.value.fase2 = {};

        if (!dossier.value.fase2.material_groups || dossier.value.fase2.material_groups.length === 0) {

          const initItems = dossier.value.ilac_calculation?.manual_items || [];

          dossier.value.fase2.material_groups = [

            {

              id: 'grp_default',

              title: 'Hardware, Tools & Extra Materialen',

              items: initItems

            }

          ];

        }

        return dossier.value.fase2.material_groups;

      },

      set: (val) => {

        if (dossier.value && dossier.value.fase2) {

          dossier.value.fase2.material_groups = val;

        }

      }

    });

    const saveMaterialGroupsToBackend = async () => {

      if (!dossier.value) return;

      try {

        const res = await fetch('/api/dossier/material_groups/save', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            customer: selectedCustomer.value,

            department: selectedDepartment.value,

            contract_name: selectedContract.value,

            material_groups: materialGroups.value

          })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

        }

      } catch (e) {

        console.error('Fout bij synchroniseren materiaalgroepen:', e);

      }

    };

    const addMaterialGroup = async () => {

      const title = prompt('Voer benaming in voor de nieuwe materiaalgroep / categoriekaart:', 'Tools - Opslag - Kleurcodering');

      if (!title || !title.trim()) return;

      const newGrp = {

        id: 'grp_' + Date.now(),

        title: title.trim(),

        items: []

      };

      materialGroups.value.push(newGrp);

      await saveMaterialGroupsToBackend();

      showToast(`Materiaalgroep '${title.trim()}' toegevoegd!`);

    };

    const renameMaterialGroup = async (group) => {

      const newTitle = prompt('Nieuwe benaming voor deze categoriekaart:', group.title);

      if (!newTitle || !newTitle.trim() || newTitle.trim() === group.title) return;

      group.title = newTitle.trim();

      await saveMaterialGroupsToBackend();

      showToast('Benaming categoriekaart bijgewerkt!');

    };

    const deleteMaterialGroup = async (grpIdx) => {

      const grp = materialGroups.value[grpIdx];

      if (!grp) return;

      if (grp.items && grp.items.length > 0) {

        if (!confirm(`Weet u zeker dat u de kaart '${grp.title}' inclusief ${grp.items.length} artikel(en) wilt verwijderen?`)) return;

      }

      materialGroups.value.splice(grpIdx, 1);

      await saveMaterialGroupsToBackend();

      showToast(`Materiaalgroep verwijderd.`);

    };

    // Open material modal specifically for a targeted group

    const openAddMaterialModal = (targetGroupId = null) => {

      activeMaterialGroupId.value = targetGroupId || materialGroups.value[0]?.id || 'grp_default';

      materialMode.value = hasPriceList.value ? 'pricelist' : 'custom';

      materialPricelistSearch.value = '';

      selectedPricelistItem.value = null;

      materialForm.value = {

        article_nr: '',

        description: '',

        category: 'Hardware & Tools',

        unit: 'stuks',

        qty: 1,

        unit_price: 0.0,

        discount_pct: 0.0,

        item_type: 'Eenmalig',

        notes: ''

      };

      showAddMaterialModal.value = true;

    };

    const selectPriceListItemForMaterial = (item) => {

      selectedPricelistItem.value = item;

      materialForm.value.article_nr = item.article_nr || '-';

      materialForm.value.description = item.description || item.product_name;

      materialForm.value.category = (item.category && String(item.category).trim()) || 'Hardware & Tools';

      materialForm.value.unit = item.packaging || 'stuks';

      materialForm.value.unit_price = item.unit_price || 0.0;

      materialForm.value.discount_pct = item.discount_pct || 0.0;

    };

    const submitManualMaterial = async () => {

      if (!materialForm.value.description.trim()) {

        alert('Gelieve een omschrijving op te geven.');

        return;

      }

      const qty = parseFloat(materialForm.value.qty) || 1;

      const unitPrice = parseFloat(materialForm.value.unit_price) || 0.0;

      const discountPct = parseFloat(materialForm.value.discount_pct) || 0.0;

      const netPrice = Math.round(unitPrice * (1.0 - discountPct / 100.0) * 100) / 100;

      const lineTotal = Math.round(netPrice * qty * 100) / 100;

      const newItem = {

        id: 'mat_' + Date.now(),

        article_nr: materialForm.value.article_nr || '-',

        description: materialForm.value.description.trim(),

        category: materialForm.value.category || 'Hardware & Tools',

        unit: materialForm.value.unit || 'stuks',

        qty: qty,

        unit_price: unitPrice,

        discount_pct: discountPct,

        net_price: netPrice,

        line_total: lineTotal,

        item_type: materialForm.value.item_type || 'Eenmalig',

        notes: materialForm.value.notes || ''

      };

      // Find target group

      let targetGrp = materialGroups.value.find(g => g.id === activeMaterialGroupId.value);

      if (!targetGrp && materialGroups.value.length > 0) {

        targetGrp = materialGroups.value[0];

      }

      if (targetGrp) {

        if (!targetGrp.items) targetGrp.items = [];

        targetGrp.items.push(newItem);

      }

      await saveMaterialGroupsToBackend();

      showAddMaterialModal.value = false;

      showToast(`Artikel '${newItem.description}' toegevoegd aan '${targetGrp?.title || 'contract'}'!`);

    };

    const deleteManualMaterial = async (groupId, itemId) => {

      const grp = materialGroups.value.find(g => g.id === groupId);

      if (!grp || !grp.items) return;

      const idx = grp.items.findIndex(it => it.id === itemId);

      if (idx !== -1) {

        grp.items.splice(idx, 1);

        await saveMaterialGroupsToBackend();

        showToast('Artikel verwijderd.');

      }

    };

    // =========================================================================

    // STANDAARD PAKKETTEN (STARTER KITS) & TOOLS CHECKLIST & TOESLAGEN LOGIC

    // =========================================================================

    const standardPackages = ref([]);

    const loadingPackages = ref(false);

    const showApplyPackageModal = ref(false);

    const selectedPackageId = ref('pkg_basic');

    const packageInsertMode = ref('new_card'); // 'new_card' or 'existing_card'

    const packageTargetGroup = ref('');

    const applyingPackage = ref(false);

    // Standaardpakketten aanmaken & artikelbeheer

    const showNewPackageModal = ref(false);

    const newPackageForm = ref({ name: '', description: '' });

    const activePackageIdForNewItem = ref(null);

    const newItemForm = ref({

      mode: 'pricelist',

      selectedArticleNr: '',

      article_nr: '',

      name: '',

      category: 'Hulpmaterialen',

      packaging: 'stuks',

      unit_price: 0,

      qty: 1,

      item_type: 'Eenmalig'

    });

    const editingPackageId = ref(null);

    const editingPackageName = ref('');

    const editingPackageDescription = ref('');

    const startEditingPackage = (pkg) => {

      editingPackageId.value = pkg.id;

      editingPackageName.value = pkg.name || '';

      editingPackageDescription.value = pkg.description || '';

    };

    const cancelEditingPackage = () => {

      editingPackageId.value = null;

      editingPackageName.value = '';

      editingPackageDescription.value = '';

    };

    const savePackageInfo = async (pkgId) => {

      const pkg = standardPackages.value.find(p => p.id === pkgId);

      if (!pkg) return;

      const newName = editingPackageName.value.trim();

      if (!newName) {

        alert("Vul a.u.b. een pakketnaam in");

        return;

      }

      pkg.name = newName;

      pkg.description = editingPackageDescription.value.trim();

      await saveAllStandardPackages();

      editingPackageId.value = null;

      showToast(`Pakketnaam gewijzigd naar '${newName}'!`);

    };

    const createStandardPackage = async () => {

      const name = newPackageForm.value.name.trim();

      if (!name) {

        alert("Vul a.u.b. een pakketnaam in");

        return;

      }

      const newPkg = {

        id: `pkg_${Date.now()}`,

        name: name,

        description: newPackageForm.value.description.trim(),

        items: []

      };

      standardPackages.value.push(newPkg);

      await saveAllStandardPackages();

      newPackageForm.value = { name: '', description: '' };

      showNewPackageModal.value = false;

      showToast(`Pakket '${newPkg.name}' succesvol aangemaakt!`);

    };

    const deleteStandardPackage = async (pkgId) => {

      const pkg = standardPackages.value.find(p => p.id === pkgId);

      const pkgName = pkg ? pkg.name : pkgId;

      if (!confirm(`Weet u zeker dat u het pakket '${pkgName}' wilt verwijderen?`)) return;

      standardPackages.value = standardPackages.value.filter(p => p.id !== pkgId);

      await saveAllStandardPackages();

      showToast(`Pakket '${pkgName}' verwijderd!`);

    };

    const onPricelistArticleSelect = () => {

      const artNr = newItemForm.value.selectedArticleNr;

      const allItems = priceListItems.value || [];

      const it = allItems.find(item => String(item.article_nr) === String(artNr));

      if (it) {

        newItemForm.value.article_nr = it.article_nr || '-';

        newItemForm.value.name = it.description || it.product_name || it.name || '';

        newItemForm.value.category = it.category || 'Hulpmaterialen';

        newItemForm.value.packaging = it.packaging || 'stuks';

        newItemForm.value.unit_price = Number(it.unit_price !== undefined ? it.unit_price : (it.price !== undefined ? it.price : it.net_price)) || 0;

      }

    };

    const addItemToPackage = async (pkgId) => {

      const pkg = standardPackages.value.find(p => p.id === pkgId);

      if (!pkg) return;

      const artName = newItemForm.value.name.trim();

      if (!artName) {

        alert("Vul a.u.b. een artikelnaam in");

        return;

      }

      if (!pkg.items) pkg.items = [];

      pkg.items.push({

        article_nr: newItemForm.value.article_nr || '-',

        name: artName,

        category: newItemForm.value.category || 'Hulpmaterialen',

        packaging: newItemForm.value.packaging || 'stuks',

        unit_price: Number(newItemForm.value.unit_price) || 0,

        qty: Number(newItemForm.value.qty) || 1,

        item_type: newItemForm.value.item_type || 'Eenmalig',

        is_custom: newItemForm.value.mode === 'manual'

      });

      await saveAllStandardPackages();

      activePackageIdForNewItem.value = null;

      newItemForm.value = {

        mode: 'pricelist',

        selectedArticleNr: '',

        article_nr: '',

        name: '',

        category: 'Hulpmaterialen',

        packaging: 'stuks',

        unit_price: 0,

        qty: 1,

        item_type: 'Eenmalig'

      };

      showToast(`Artikel toegevoegd aan pakket '${pkg.name}'!`);

    };

    const removeItemFromPackage = async (pkgId, itemIdx) => {

      const pkg = standardPackages.value.find(p => p.id === pkgId);

      if (!pkg || !pkg.items) return;

      pkg.items.splice(itemIdx, 1);

      await saveAllStandardPackages();

      showToast("Artikel verwijderd uit pakket!");

    };

    const saveAllStandardPackages = async () => {

      try {

        const res = await fetch('/api/settings/standard-packages', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ packages: standardPackages.value })

        });

        const data = await res.json();

        if (res.ok && data.status === 'success') {

          standardPackages.value = data.packages;

        }

      } catch (e) {

        console.error('Fout bij opslaan van standaardpakketten:', e);

      }

    };

    const fetchStandardPackages = async () => {

      try {

        loadingPackages.value = true;

        const res = await fetch('/api/settings/standard-packages');

        const data = await res.json();

        if (res.ok) {

          standardPackages.value = data.packages || [];

        }

      } catch (e) {

        console.error('Fout bij ophalen standaardpakketten:', e);

      } finally {

        loadingPackages.value = false;

      }

    };

    const openApplyPackageModal = async () => {

      await fetchStandardPackages();

      if (standardPackages.value.length > 0) {

        selectedPackageId.value = standardPackages.value[0].id;

      }

      packageInsertMode.value = 'new_card';

      packageTargetGroup.value = materialGroups.value[0]?.name || 'Hardware, Tools & Extra Materialen';

      showApplyPackageModal.value = true;

    };

    const submitApplyPackage = async () => {

      if (!dossier.value || !selectedPackageId.value) return;

      try {

        applyingPackage.value = true;

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/package/apply`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            package_id: selectedPackageId.value,

            as_new_card: packageInsertMode.value === 'new_card',

            target_group_name: packageTargetGroup.value

          })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          if (data.dossier?.fase2?.material_groups) {

            materialGroups.value = data.dossier.fase2.material_groups;

          }

          showApplyPackageModal.value = false;

          showToast(data.message || 'Standaard pakket succesvol toegevoegd aan contract!');

        } else {

          alert(data.error || 'Fout bij toepassen pakket');

        }

      } catch (e) {

        alert('Netwerkfout bij toepassen pakket');

      } finally {

        applyingPackage.value = false;

      }

    };

    // Tools Checklist uit Audit

    const detectedTools = computed(() => {

      return dossier.value?.ilac_calculation?.summary?.detected_tools || [];

    });

    const addingTool = ref({});

    const toolTargetCardMap = ref({});

    const addToolToContractCard = async (toolItem, targetCardName = null) => {

      if (!dossier.value) return;

      const targetCard = targetCardName || toolTargetCardMap.value[toolItem.tool_name] || materialGroups.value[0]?.name || 'Hardware, Tools & Extra Materialen';

      const artNr = toolItem.selected_article_nr || toolItem.suggested_items?.[0]?.article_nr || '';

      try {

        addingTool.value[toolItem.tool_name] = true;

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/tools/add_to_card`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            tool_name: toolItem.tool_name,

            article_nr: artNr,

            target_group_name: targetCard,

            qty: toolItem.recommended_qty || 1

          })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          if (data.dossier?.fase2?.material_groups) {

            materialGroups.value = data.dossier.fase2.material_groups;

          }

          toolItem.status = 'added';

          showToast(`Artikel voor '${toolItem.tool_name}' toegevoegd aan '${targetCard}'!`);

        } else {

          alert(data.error || 'Fout bij toevoegen artikel voor tool');

        }

      } catch (e) {

        alert('Netwerkfout bij toevoegen tool');

      } finally {

        addingTool.value[toolItem.tool_name] = false;

      }

    };

    // Indexation & Surcharge Management

    const availableIndexCategories = [

      'Olien ',

      'Food Olien',

      'Vetten',

      'Food Vetten',

      'Reinigers',

      'Hardware & Tools',

      'Hulpmaterialen',

      'Automatic lubrication',

      'STO Partner Uitvoering',

      'PM & Regie'

    ];

    const indexationForm = ref({

      active: false,

      percentage: 3.5,

      type: 'general',

      categories: ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten', 'Reinigers'],

      effective_date: new Date().toISOString().split('T')[0],

      note: ''

    });

    const toggleIndexCategory = (cat) => {

      if (!Array.isArray(indexationForm.value.categories)) {

        indexationForm.value.categories = [];

      }

      const idx = indexationForm.value.categories.indexOf(cat);

      if (idx >= 0) {

        indexationForm.value.categories.splice(idx, 1);

      } else {

        indexationForm.value.categories.push(cat);

      }

    };

    const selectAllIndexCategories = () => {

      indexationForm.value.categories = [...availableIndexCategories];

    };

    const selectProductsIndexCategories = () => {

      indexationForm.value.categories = ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten', 'Reinigers'];

    };

    const selectLaborIndexCategories = () => {

      indexationForm.value.categories = ['STO Partner Uitvoering'];

    };

    const toggleSuiteIndexCategory = (cat) => {

      if (!suiteSettings.value.indexation) return;

      if (!Array.isArray(suiteSettings.value.indexation.categories)) {

        suiteSettings.value.indexation.categories = [];

      }

      const idx = suiteSettings.value.indexation.categories.indexOf(cat);

      if (idx >= 0) {

        suiteSettings.value.indexation.categories.splice(idx, 1);

      } else {

        suiteSettings.value.indexation.categories.push(cat);

      }

    };

    const selectAllSuiteIndexCategories = () => {

      if (!suiteSettings.value.indexation) return;

      suiteSettings.value.indexation.categories = [...availableIndexCategories];

    };

    const selectProductsSuiteIndexCategories = () => {

      if (!suiteSettings.value.indexation) return;

      suiteSettings.value.indexation.categories = ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten', 'Reinigers'];

    };

    const toggleSuiteSurchargeCategory = (cat) => {

      if (!suiteSettings.value.temporary_surcharge) {

        suiteSettings.value.temporary_surcharge = {

          active: false,

          percentage: 5.0,

          name: 'Grondstoffentoeslag Olie (Straat van Hormuz)',

          categories: []

        };

      }

      if (!Array.isArray(suiteSettings.value.temporary_surcharge.categories)) {

        suiteSettings.value.temporary_surcharge.categories = [];

      }

      const idx = suiteSettings.value.temporary_surcharge.categories.indexOf(cat);

      if (idx >= 0) {

        suiteSettings.value.temporary_surcharge.categories.splice(idx, 1);

      } else {

        suiteSettings.value.temporary_surcharge.categories.push(cat);

      }

    };

    const selectOilGreaseSuiteSurchargeCategories = () => {

      if (!suiteSettings.value.temporary_surcharge) return;

      suiteSettings.value.temporary_surcharge.categories = ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten'];

    };

    const selectAllSuiteSurchargeCategories = () => {

      if (!suiteSettings.value.temporary_surcharge) return;

      suiteSettings.value.temporary_surcharge.categories = [...availableIndexCategories];

    };

    const clearSuiteSurchargeCategories = () => {

      if (!suiteSettings.value.temporary_surcharge) return;

      suiteSettings.value.temporary_surcharge.categories = [];

    };

    const surchargeForm = ref({

      active: false,

      percentage: 5.0,

      name: 'Grondstoffentoeslag Olie (Straat van Hormuz)',

      categories: ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten']

    });

    const initContractSettingsForms = () => {

      if (!dossier.value) return;

      const idx = dossier.value.indexation || {};

      indexationForm.value = {

        active: !!idx.active,

        percentage: idx.percentage !== undefined ? idx.percentage : 3.5,

        type: idx.type || 'general',

        categories: Array.isArray(idx.categories) && idx.categories.length > 0

          ? [...idx.categories]

          : ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten', 'Reinigers'],

        effective_date: new Date().toISOString().split('T')[0],

        note: ''

      };

      const sur = dossier.value.temporary_surcharge || {};

      surchargeForm.value = {

        active: !!sur.active,

        percentage: sur.percentage !== undefined ? sur.percentage : 5.0,

        name: sur.name || 'Grondstoffentoeslag Olie (Straat van Hormuz)',

        categories: sur.categories || ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten']

      };

    };

    const previewCompoundedFee = computed(() => {

      const cur = Number(proposalSummary.value.base_monthly_fee || proposalSummary.value.monthly_fee || 0);

      const pct = Number(indexationForm.value.percentage) || 0;

      if (!indexationForm.value.active || pct === 0) return cur;

      return Math.round(cur * (1.0 + pct / 100.0) * 100) / 100;

    });

    const submitIndexationUpdate = async () => {

      if (!dossier.value) return;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/indexation`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(indexationForm.value)

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          initContractSettingsForms();

          showToast('Indexatie succesvol doorgerekend op laatste fee en gelogd!');

        } else {

          alert(data.error || 'Fout bij opslaan indexatie');

        }

      } catch (e) {

        alert('Netwerkfout bij opslaan indexatie');

      }

    };

    const deleteIndexationEntry = async (entryId) => {

      if (!confirm("Weet u zeker dat u deze indexatiemutatie wilt verwijderen? De fee wordt automatisch herberekend uit de overgebleven mutaties.")) return;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/indexation/delete`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ entry_id: entryId })

        });

        const data = await res.json();

        if (res.ok && data.status === 'success') {

          dossier.value = data.dossier;

          initContractSettingsForms();

          showToast('Indexering verwijderd en fee succesvol herberekend!');

        } else {

          alert(data.error || 'Kon indexatiemutatie niet verwijderen');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij verwijderen indexatiemutatie');

      }

    };

    const submitSurchargeUpdate = async () => {

      if (!dossier.value) return;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/surcharge`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(surchargeForm.value)

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showToast('Tijdelijke grondstoffentoeslag bijgewerkt!');

        } else {

          alert(data.error || 'Fout bij opslaan toeslag');

        }

      } catch (e) {

        alert('Netwerkfout bij opslaan toeslag');

      }

    };

    // Helper for tool badges

    const getToolBadgeColor = (tool) => {

      if (!tool) return 'bg-slate-100 text-slate-700 border-slate-200';

      const t = tool.toLowerCase();

      if (t.includes('accugreaser') || t.includes('vetpistool')) return 'bg-sky-50 text-sky-700 border-sky-200';

      if (t.includes('vulpomp') || t.includes('cls')) return 'bg-amber-50 text-amber-700 border-amber-200';

      if (t.includes('spuitbus') || t.includes('spray')) return 'bg-purple-50 text-purple-700 border-purple-200';

      if (t.includes('single point') || t.includes('service pack') || t.includes('spl')) return 'bg-emerald-50 text-emerald-700 border-emerald-200';

      if (t.includes('oliekan')) return 'bg-indigo-50 text-indigo-700 border-indigo-200';

      if (t.includes('staalname')) return 'bg-teal-50 text-teal-700 border-teal-200';

      return 'bg-slate-100 text-slate-700 border-slate-200';

    };

    // =========================================================================

    // VERSIEBEHEER (FASE 2 AFRONDEN & FASE 3 SELECTIE)

    // =========================================================================

    const openSaveVersionModal = () => {

      const versions = dossier.value?.versions || [];

      const nextTag = `v1.${versions.length}`;

      versionForm.value = {

        tag: nextTag,

        note: ''

      };

      showVersionModal.value = true;

    };

    const submitSaveVersion = async () => {

      if (!dossier.value) return;

      savingVersion.value = true;

      try {

        const res = await fetch('/api/dossier/version/save', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            customer: selectedCustomer.value,

            department: selectedDepartment.value,

            contract_name: selectedContract.value,

            note: versionForm.value.note.trim(),

            version_tag: versionForm.value.tag.trim()

          })

        });

        const data = await res.json();

        if (res.ok) {

          if (dossier.value) {

            dossier.value.versions = data.versions;

            dossier.value.active_version_id = data.active_version_id;

          }

          showToast(`Versie ${data.version_tag} succesvol vastgelegd!`);

          showVersionModal.value = false;

          activePhase.value = 'phase3';

        } else {

          alert(data.error || 'Fout bij opslaan versie');

        }

      } catch (e) {

        alert('Netwerkfout bij opslaan versie');

      } finally {

        savingVersion.value = false;

      }

    };

    const restoreVersionToActive = async (versionTag) => {

      if (!confirm(`Weet u zeker dat u versie '${versionTag}' wilt herstellen als actieve werkversie? Huidige niet-opgeslagen wijzigingen in Fase 2 worden overschreven.`)) return;

      try {

        const res = await fetch('/api/dossier/version/restore', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            customer: selectedCustomer.value,

            department: selectedDepartment.value,

            contract_name: selectedContract.value,

            version_tag: versionTag

          })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          selectedProposalVersion.value = 'current';

          showToast(`Versie ${versionTag} succesvol hersteld!`);

        } else {

          alert(data.error || 'Fout bij herstellen versie');

        }

      } catch (e) {

        alert('Netwerkfout bij herstellen versie');

      }

    };

    // =========================================================================

    // FASE 3: VOORSTEL & WAARDEPROPOSITIE (RAPPORTAGE P. 20 - 30)

    // =========================================================================

    const proposalData = computed(() => {

      if (activeVersionSnapshot.value && activeVersionSnapshot.value.proposal) {

        return activeVersionSnapshot.value.proposal;

      }

      if (!dossier.value) return {};

      if (!dossier.value.proposal) {

        dossier.value.proposal = {

          client_ref: 'Marc Hellemans - Philippe de Witte',

          doc_id: 'BE/003500-01',

          authors: 'Kenny De Meester, Dennis Broods',

          approved_by: 'Sven Permentier, Wim Peckstadt',

          status: 'Final',

          version_date: new Date().toLocaleDateString('nl-BE', { day: 'numeric', month: 'long', year: 'numeric' }),

          total_pages: '6 (incl. titelpagina + bijlages)',

          custom_texts: {

            inleiding: 'Gedegen smeertechnisch onderhoud (STO) staat aan de basis van een betrouwbare industrie/productielocatie. Tot 40% van een onderhoudsbudget gaat op aan activiteiten die smeergerelateerd zijn. Denk hierbij aan schades, maar ook het vroegtijdig gepland vervangen van machineonderdelen. Doelstellingen:\n1. Verbeteren en stabiliseren van de technische beschikbaarheid\n2. Reduceren smeergerelateerde schades (kosten uren - spares)\n3. Optimaliseren van smeertechnisch onderhoud (kosten uren - lubricants)',

            huidige_situatie: 'Het smeertechnisch onderhoud wordt reeds langere tijd uitgevoerd, maar er is behoefte aan verhoogde controle, transparantie en een geoptimaliseerd smeerplan. Interflon stelt een geborgde aanpak voor met MicPol®-technologie en onderbrenging in ILAC Pro.',

            waardepropositie: 'De detailopname van het smeeronderhoud toont een aanzienlijk besparingspotentieel aan, gerealiseerd door de inzet van Interflon MicPol®-technologie in combinatie met een geoptimaliseerde onderhoudsaanpak. Ten opzichte van het aangeboden voorstel bedraagt de directe besparing circa 32% per jaar.',

            leveringsvoorwaarden: '1. Deze offerte is 30 dagen geldig na uitgifte.\n2. Alle vermelde prijzen zijn in euro\'s en exclusief BTW.\n3. Prijzen zijn inclusief reistijd en -kosten, maar exclusief verblijfskosten, met uitzondering van de arbeidstarieven voor uitvoer STO.\n4. Prijsindexering arbeid conform tarievenlijst servicepartner éénmaal per kalenderjaar op basis van de Agoria formule in relatie tot PC 111.02.\n5. Prijsindexering Interflon-services en -producten vindt éénmaal per kalenderjaar plaats.\n6. Betaling: op fixed basis, met uitzondering van de uitvoering van het smeeronderhoud welke op regiebasis wordt doorbelast.'

          },

          client_address: 'Adolf Greinerstraat 14, 2660 Antwerpen, België',

          company_number: 'BE 0401.574.852',

          invoice_email: 'facturatie@klant.com',

          maatpak_toggles: {

            execution_work: true,

            project_management: true,

            ilac_license: true,

            oil_analysis: true

          }

        };

      }

      return dossier.value.proposal;

    });

    const maatpakToggles = computed({

      get: () => {

        if (!dossier.value?.proposal) return {};

        if (!dossier.value.proposal.maatpak_toggles) {

          dossier.value.proposal.maatpak_toggles = {

            execution_work: true,

            project_management: true,

            ilac_license: true,

            oil_analysis: true

          };

        }

        return dossier.value.proposal.maatpak_toggles;

      },

      set: (v) => {

        if (dossier.value?.proposal) dossier.value.proposal.maatpak_toggles = v;

      }

    });

    const isGroupToggled = (groupId) => {

      if (maatpakToggles.value[groupId] === undefined) {

        maatpakToggles.value[groupId] = true;

      }

      return !!maatpakToggles.value[groupId];

    };

    const toggleMaatpakModule = (key) => {

      maatpakToggles.value[key] = !maatpakToggles.value[key];

    };

    const maatpakTweeluik = computed(() => {

      const summary = proposalSummary.value;

      const wh = (activeVersionSnapshot.value?.fase2_work_hours) || (dossier.value?.fase2?.work_hours) || {};

      const years = (activeVersionSnapshot.value?.settings?.duration_years) || calcYears.value || 3;

      const totalMonths = years * 12;

      const surchActive = Boolean(summary.surcharge_active);

      const surchTotal = surchActive ? (parseFloat(summary.surcharge_total) || 0) : 0;

      const surchMonthly = surchActive ? (parseFloat(summary.surcharge_monthly) || 0) : 0;

      const allInMonthly = summary.total_monthly_fee || summary.monthly_fee || 0;

      const allInBaseMonthly = summary.base_monthly_fee || (surchActive ? Math.max(0, allInMonthly - surchMonthly) : allInMonthly);

      const allInGrandTotal = summary.grand_contract_total || 0;

      let chosenGrandTotal = 0;

      chosenGrandTotal += (summary.products_total || 0);

      (proposalMaterialGroups.value || []).forEach(grp => {

        if (isGroupToggled(grp.id)) {

          (grp.items || []).forEach(it => {

            const qty = parseFloat(it.qty) || 1;

            const net = parseFloat(it.net_price) || 0;

            const isAnnual = it.item_type === 'Jaarlijks';

            chosenGrandTotal += (qty * net * (isAnnual ? years : 1));

          });

        }

      });

      if (maatpakToggles.value.execution_work) {

        chosenGrandTotal += (summary.total_execution_cost || 0);

      }

      if (maatpakToggles.value.project_management) {

        chosenGrandTotal += (summary.management_cost || 0);

      }

      if (maatpakToggles.value.ilac_license) {

        const licAnnual = parseFloat(wh.software_license_annual) || 1950.0;

        chosenGrandTotal += (licAnnual * years);

      }

      if (maatpakToggles.value.oil_analysis) {

        const analysesYr = parseFloat(wh.oil_analyses_per_year) || 0;

        const unitPrice = parseFloat(wh.analysis_unit_price) || 220.0;

        chosenGrandTotal += (analysesYr * unitPrice * years);

      }

      chosenGrandTotal += parseFloat(wh.training_budget || 0);

      // Tijdelijke toeslag toevoegen aan gekozen scenario (toeslag op smeermiddelen)

      chosenGrandTotal += surchTotal;

      const chosenMonthly = totalMonths > 0 ? (chosenGrandTotal / totalMonths) : 0;

      const chosenBaseMonthly = Math.max(0, chosenMonthly - surchMonthly);

      const clientBaselineAnnual = Math.round((chosenMonthly * 12) * 1.462);

      const interflonAnnual = Math.round(chosenMonthly * 12);

      const savingEuro = clientBaselineAnnual - interflonAnnual;

      const savingPct = clientBaselineAnnual > 0 ? Math.round((savingEuro / clientBaselineAnnual) * 100) : 32;

      return {

        allInMonthly: Math.round(allInMonthly * 100) / 100,

        allInBaseMonthly: Math.round(allInBaseMonthly * 100) / 100,

        allInGrandTotal: Math.round(allInGrandTotal * 100) / 100,

        chosenMonthly: Math.round(chosenMonthly * 100) / 100,

        chosenBaseMonthly: Math.round(chosenBaseMonthly * 100) / 100,

        chosenGrandTotal: Math.round(chosenGrandTotal * 100) / 100,

        surchMonthly: Math.round(surchMonthly * 100) / 100,

        surchTotal: Math.round(surchTotal * 100) / 100,

        clientBaselineAnnual,

        interflonAnnual,

        savingEuro,

        savingPct

      };

    });

    const scopeByLocation = computed(() => {

      const map = {};

      (ilacPoints.value || []).forEach(p => {

        const loc = p.location || p.system_name || p.sub_department || p.department || 'Afdeling Scope';

        map[loc] = (map[loc] || 0) + 1;

      });

      return Object.entries(map).map(([location, count]) => ({ location, count }));

    });

    const openEditSectionModal = (key, title, isLegal = false) => {

      if (isLegal && !isUnlocked.value) {

        showPasswordModal.value = true;

        showToast('Beheerderswachtwoord vereist om juridische voorwaarden aan te passen');

        return;

      }

      const texts = proposalData.value.custom_texts || {};

      editSectionModal.value = {

        show: true,

        key,

        title,

        content: texts[key] || '',

        isLegal

      };

    };

    const saveSectionContent = async () => {

      if (!proposalData.value.custom_texts) proposalData.value.custom_texts = {};

      proposalData.value.custom_texts[editSectionModal.value.key] = editSectionModal.value.content;

      editSectionModal.value.show = false;

      await saveProposalConfig();

    };

    const saveProposalConfig = async () => {

      if (!dossier.value) return;

      try {

        const res = await fetch('/api/dossier/proposal/save', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            customer: selectedCustomer.value,

            department: selectedDepartment.value,

            contract_name: selectedContract.value,

            proposal: dossier.value.proposal

          })

        });

        if (res.ok) {

          showToast('Voorstelinstellingen opgeslagen!');

        }

      } catch (e) {

        console.error('Fout bij opslaan voorstelinstellingen:', e);

      }

    };

    const printProposal = () => {

      window.print();

    };

    // Custom article modal in pricelist

    const submitCustomArticle = async () => {

      if (!customArticleForm.value.article_nr || !customArticleForm.value.product_name) {

        alert('Artikelnr en productnaam zijn verplicht.');

        return;

      }

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/pricelist/add_custom`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(customArticleForm.value)

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showAddCustomArticleModal.value = false;

          showToast(`Maatwerkartikel ${customArticleForm.value.article_nr} toegevoegd aan prijslijst!`);

        }

      } catch (err) {

        alert('Fout bij toevoegen maatwerkartikel');

      }

    };

    // Filtered lists

    const ilacPoints = computed(() => (dossier.value?.ilac_calculation?.points) || []);

    const globalPriceList = ref({ items: [], total_items: 0, filename: null, uploaded_at: null });

    const uploadingGlobalPriceList = ref(false);

    const fetchGlobalPriceList = async () => {

      try {

        const res = await fetch('/api/settings/global-pricelist');

        const data = await res.json();

        if (res.ok && data.pricelist) {

          globalPriceList.value = data.pricelist;

        }

      } catch (err) {

        console.error('Fout bij ophalen van globale prijslijst:', err);

      }

    };

    const globalPlFileInput = ref(null);

    const triggerGlobalPriceListUpload = () => {

      if (!isUnlocked.value) {

        showPasswordModal.value = true;

        showToast('Beheerderswachtwoord vereist om de globale prijslijst te uploaden');

        return;

      }

      if (globalPlFileInput.value) {

        globalPlFileInput.value.click();

      }

    };

    const onGlobalPriceListFileChange = async (event) => {

      if (!isUnlocked.value) {

        showPasswordModal.value = true;

        showToast('Beheerderswachtwoord vereist om de globale prijslijst te uploaden');

        if (event.target) event.target.value = '';

        return;

      }

      const file = event.target.files && event.target.files[0];

      if (!file) return;

      const formData = new FormData();

      formData.append('file', file);

      try {

        uploadingGlobalPriceList.value = true;

        const res = await fetch('/api/settings/global-pricelist/upload', {

          method: 'POST',

          body: formData

        });

        const data = await res.json();

        if (res.ok && data.status === 'success') {

          globalPriceList.value = data.pricelist;

          showToast(data.message || 'Globale prijslijst geactiveerd!');

          if (selectedCustomer.value && selectedDepartment.value && selectedContract.value) {

            await openContract(selectedCustomer.value, selectedDepartment.value, selectedContract.value);

          }

        } else {

          alert(data.error || 'Fout bij uploaden van globale prijslijst');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij uploaden globale prijslijst');

      } finally {

        uploadingGlobalPriceList.value = false;

        event.target.value = '';

      }

    };

    const priceListItems = computed(() => {

      if (globalPriceList.value?.items && globalPriceList.value.items.length > 0) {

        return globalPriceList.value.items;

      }

      return (dossier.value?.price_list?.items) || [];

    });

    // Staffel Modal State

    const showStaffelModal = ref(false);

    const selectedStaffelItem = ref(null);

    const openStaffelModal = (item) => {

      if (!item) return;

      selectedStaffelItem.value = item;

      showStaffelModal.value = true;

    };

    const closeStaffelModal = () => {

      showStaffelModal.value = false;

      selectedStaffelItem.value = null;

    };

    // Global Pricelist Filtering & Pagination

    const globalPlSearch = ref('');

    const globalPlCategory = ref('');

    const globalPlPage = ref(1);

    const globalPlPerPage = ref(50);

    const globalPriceListCategories = computed(() => {

      const cats = new Set();

      (priceListItems.value || []).forEach(it => {

        if (it.category && String(it.category).trim()) {

          cats.add(String(it.category).trim());

        }

      });

      return Array.from(cats).sort();

    });

    const filteredGlobalPriceList = computed(() => {

      let list = priceListItems.value || [];

      const cat = globalPlCategory.value.trim().toLowerCase();

      if (cat) {

        list = list.filter(it => (it.category || '').toLowerCase() === cat);

      }

      const q = globalPlSearch.value.trim().toLowerCase();

      if (q) {

        list = list.filter(it => {

          const art = String(it.article_nr || '').toLowerCase();

          const name = String(it.description || it.product_name || '').toLowerCase();

          const pkg = String(it.packaging || it.content || '').toLowerCase();

          const category = String(it.category || '').toLowerCase();

          return art.includes(q) || name.includes(q) || pkg.includes(q) || category.includes(q);

        });

      }

      return list;

    });

    const totalGlobalPlPages = computed(() => {

      return Math.max(1, Math.ceil(filteredGlobalPriceList.value.length / globalPlPerPage.value));

    });

    const paginatedGlobalPriceList = computed(() => {

      const start = (globalPlPage.value - 1) * globalPlPerPage.value;

      return filteredGlobalPriceList.value.slice(start, start + globalPlPerPage.value);

    });

    const setGlobalPlPage = (newPage) => {

      if (newPage >= 1 && newPage <= totalGlobalPlPages.value) {

        globalPlPage.value = newPage;

      }

    };

    const aggregatedProducts = computed(() => (dossier.value?.ilac_calculation?.aggregated_products) || []);

    const manualItems = computed(() => (dossier.value?.ilac_calculation?.manual_items) || []);

    const calculationSummary = computed(() => (dossier.value?.ilac_calculation?.summary) || {});

    const uniqueDepartments = computed(() => {

      const depts = new Set();

      ilacPoints.value.forEach(p => {

        if (p.department) depts.add(p.department);

      });

      return Array.from(depts);

    });

    const filteredILACPoints = computed(() => {

      let list = ilacPoints.value;

      if (pointsDeptFilter.value !== 'all') {

        list = list.filter(p => p.department === pointsDeptFilter.value);

      }

      if (pointsSearch.value.trim()) {

        const q = pointsSearch.value.trim().toLowerCase();

        list = list.filter(p => {

          return (p.machine && p.machine.toLowerCase().includes(q)) ||

                 (p.machine_part && p.machine_part.toLowerCase().includes(q)) ||

                 (p.maintenance_part && p.maintenance_part.toLowerCase().includes(q)) ||

                 (p.product_name && p.product_name.toLowerCase().includes(q)) ||

                 (p.location && p.location.toLowerCase().includes(q));

        });

      }

      return list;

    });

    const uniquePriceCategories = computed(() => {

      const cats = new Set();

      priceListItems.value.forEach(item => {

        if (item.category) cats.add(item.category);

      });

      return Array.from(cats);

    });

    const filteredPriceListItems = computed(() => {

      let list = priceListItems.value;

      if (priceCategoryFilter.value !== 'all') {

        list = list.filter(p => p.category === priceCategoryFilter.value);

      }

      if (priceSearch.value.trim()) {

        const q = priceSearch.value.trim().toLowerCase();

        list = list.filter(p => {

          return (p.product_name && p.product_name.toLowerCase().includes(q)) ||

                 (p.article_nr && p.article_nr.toLowerCase().includes(q)) ||

                 (p.description && p.description.toLowerCase().includes(q));

        });

      }

      return list;

    });

    // Renewal Concept methods

    const renewalTasks = computed(() => (dossier.value?.renewal_concept?.tasks) || []);

    const generateRenewalConcept = async () => {

      if (!dossier.value) return;

      generatingRenewal.value = true;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/renewal/create_concept`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(renewalForm.value)

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

          showToast('Concept contractverlenging gegenereerd!');

        }

      } catch (err) {

        alert('Fout bij genereren verlengingsconcept');

      } finally {

        generatingRenewal.value = false;

      }

    };

    const toggleRenewalTask = async (taskKey, includeInConcept) => {

      if (!dossier.value) return;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(selectedCustomer.value)}/${encodeURIComponent(selectedDepartment.value)}/${encodeURIComponent(selectedContract.value)}/renewal/toggle_task`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ task_key: taskKey, include_in_concept: includeInConcept })

        });

        const data = await res.json();

        if (res.ok) {

          dossier.value = data.dossier;

        }

      } catch (err) {

        console.error('Fout bij toggle taak:', err);

      }

    };

    // =========================================================================

    // LIFECYCLE

    // =========================================================================

        // =========================================================================

    // SUITE-WIDE GLOBAL SETTINGS MODAL

    // =========================================================================

    const showSuiteSettingsModal = ref(false);

    const suiteSettingsTab = ref('pricelist'); // 'pricelist', 'packages', 'indexation', 'surcharge'

    const suiteSettings = ref({

      indexation: { active: false, percentage: 3.5, type: 'general', categories: ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten', 'Reinigers'], effective_date: '', note: '', log: [] },

      temporary_surcharge: { active: false, percentage: 5.0, name: 'Grondstoffentoeslag Olie (Straat van Hormuz)', categories: ['Olien ', 'Food Olien', 'Vetten', 'Food Vetten'] }

    });

    const savingSuiteSettings = ref(false);

    const fetchSuiteSettings = async () => {

      try {

        const res = await fetch('/api/settings/suite');

        const data = await res.json();

        if (res.ok && data.settings) {

          suiteSettings.value = data.settings;

        }

      } catch (e) {

        console.error('Fout bij ophalen suite-instellingen:', e);

      }

    };

    const openSuiteSettingsModal = async (initialTab = 'pricelist') => {

      suiteSettingsTab.value = initialTab;

      await Promise.all([

        fetchGlobalPriceList(),

        fetchStandardPackages(),

        fetchSuiteSettings()

      ]);

      showSuiteSettingsModal.value = true;

    };

    const deleteSuiteIndexationEntry = (idx) => {

      if (!confirm("Weet u zeker dat u deze globale indexatiemutatie uit de suite-historie wilt verwijderen?")) return;

      if (suiteSettings.value?.indexation?.log && suiteSettings.value.indexation.log[idx] !== undefined) {

        suiteSettings.value.indexation.log.splice(idx, 1);

        saveSuiteSettings();

      }

    };

    const saveSuiteSettings = async () => {

      try {

        savingSuiteSettings.value = true;

        // Append to suite indexation log if newly indexed

        if (suiteSettings.value?.indexation?.active && Number(suiteSettings.value.indexation.percentage) > 0) {

          const logEntry = {

            id: 'suite_idx_' + Date.now(),

            timestamp: new Date().toLocaleString('nl-NL'),

            effective_date: suiteSettings.value.indexation.effective_date || new Date().toISOString().split('T')[0],

            percentage: Number(suiteSettings.value.indexation.percentage),

            type: suiteSettings.value.indexation.type || 'general',

            categories: suiteSettings.value.indexation.categories || [],

            note: suiteSettings.value.indexation.note || 'Suite-brede indexering'

          };

          if (!Array.isArray(suiteSettings.value.indexation.log)) {

            suiteSettings.value.indexation.log = [];

          }

          suiteSettings.value.indexation.log.unshift(logEntry);

        }

        const res = await fetch('/api/settings/suite', {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({ settings: suiteSettings.value, apply_to_all_contracts: true })

        });

        const data = await res.json();

        if (res.ok) {

          showToast('Suite-instellingen opgeslagen en gesynchroniseerd!');

          showSuiteSettingsModal.value = false;

          if (selectedCustomer.value && selectedDepartment.value && selectedContract.value) {

            await openContract(selectedCustomer.value, selectedDepartment.value, selectedContract.value);

          }

        } else {

          alert(data.error || 'Fout bij opslaan suite-instellingen');

        }

      } catch (e) {

        alert('Netwerkfout bij opslaan suite-instellingen');

      } finally {

        savingSuiteSettings.value = false;

      }

    };

    // =========================================================================

    // PROJECT OPVOLGING & P&L TRACKING DASHBOARD STATE & METHODS

    // =========================================================================

    const activeTrackingTab = ref('cockpit');

    const selectedComparisonYear = ref('all');

    const productsComparisonSearch = ref('');

    const productsComparisonStatusFilter = ref('all');

    const activeHoursSubtab = ref('partner_regular');

    const trackingCustomer = ref('');

    const trackingDepartment = ref('');

    const trackingContract = ref('');

    const trackingData = ref(null);

    const trackingPnl = ref(null);

    const loadingTracking = ref(false);

    // Modals

    const showAcceptContractModal = ref(false);

    const acceptingContract = ref(false);

    const acceptForm = ref({

      customer: '',

      department: '',

      contract_name: '',

      version_tag: 'Huidige Werkversie',

      duration_years: 3,

      signed_date: new Date().toISOString().substring(0, 10),

      start_date: new Date().toISOString().substring(0, 10),

      agreed_monthly_fee: 0,

      agreed_modules: {

        execution_work: true,

        project_management: true,

        ilac_license: true,

        oil_analysis: true

      },

      notes: ''

    });

    const showUnlockCalcModal = ref(false);

    const unlockingCalc = ref(false);

    const unlockPassword = ref('');

    const unlockAgreed = ref(false);

    const unlockNote = ref('');

    const unlockTarget = ref({ customer: '', department: '', contract_name: '' });

    const showAddDeliveryModal = ref(false);

    const savingDelivery = ref(false);

    const newDeliveryForm = ref({

      date: new Date().toISOString().substring(0, 10),

      bon_so: '',

      product_pack: '',

      qty: 1,

      content_per_pack: 1,

      purchase_unit: 0,

      sales_unit: 0,

      year: 1,

      in_fee: true

    });

    const showAddHoursModal = ref(false);

    const savingHours = ref(false);

    const newHoursForm = ref({

      category: 'partner_regular',

      date: new Date().toISOString().substring(0, 10),

      year: 1,

      technician: '',

      consultant: '',

      so_af: '',

      hours: 8,

      travel_days: 1,

      description: ''

    });

    const showAddOutOfFeeModal = ref(false);

    const savingOutOfFee = ref(false);

    const newOutOfFeeForm = ref({

      date: new Date().toISOString().substring(0, 10),

      order_nr: '',

      client_ref: '',

      description: '',

      sales_amount: 0,

      purchase_amount: 0,

      reason: ''

    });

    // =========================================================================

    // VOORZIEN VS GELEVERD (PRODUCTEN VERGELIJKING) COMPUTEDS

    // =========================================================================

    const productsComparisonCards = computed(() => {

      const prods = (trackingData.value && trackingData.value.products_comparison) || [];

      const yr = selectedComparisonYear.value;

      const q = productsComparisonSearch.value.trim().toLowerCase();

      const statusFilter = productsComparisonStatusFilter.value;

      return prods.map(item => {

        let plan = 0;

        let deliv = 0;

        if (yr === '1') {

          plan = Number(item.j1_val) || 0;

          deliv = Number(item.deliv_j1 !== undefined ? item.deliv_j1 : item.deliv_val) || 0;

        } else if (yr === '2') {

          plan = Number(item.j2_val) || 0;

          deliv = Number(item.deliv_j2) || 0;

        } else if (yr === '3') {

          plan = Number(item.j3_val) || 0;

          deliv = Number(item.deliv_j3) || 0;

        } else {

          plan = Number(item.total_val) || 0;

          deliv = Number(item.deliv_val) || 0;

        }

        const inFee = Number(item.in_fee_val) || 0;

        const extra = Number(item.extra_val) || 0;

        const diff = Math.round((plan - deliv) * 100) / 100;

        const pct = plan > 0 ? Math.round((deliv / plan) * 1000) / 10 : (deliv > 0 ? 100 : 0);

        let statusText = '';

        let statusKey = '';

        let statusBadgeClass = '';

        if (deliv === 0 && plan > 0) {

          statusText = 'Nog niet geleverd';

          statusKey = 'not_delivered';

          statusBadgeClass = 'bg-slate-100 text-slate-600 border border-slate-200';

        } else if (pct > 105) {

          statusText = `Oververbruik (+${Math.round(pct - 100)}%)`;

          statusKey = 'alert';

          statusBadgeClass = 'bg-rose-100 text-rose-800 border border-rose-300 font-bold';

        } else if (pct >= 75) {

          statusText = `Op plan (${Math.round(pct)}%)`;

          statusKey = 'on_plan';

          statusBadgeClass = 'bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold';

        } else {

          statusText = `<75% geleverd (${Math.round(pct)}%)`;

          statusKey = 'in_progress';

          statusBadgeClass = 'bg-sky-100 text-sky-800 border border-sky-300 font-semibold';

        }

        return {

          ...item,

          planVal: plan,

          delivVal: deliv,

          inFeeVal: inFee,

          extraVal: extra,

          diffVal: diff,

          pct: pct,

          statusText: statusText,

          statusKey: statusKey,

          statusBadgeClass: statusBadgeClass

        };

      }).filter(card => {

        if (q) {

          const matchName = (card.product || '').toLowerCase().includes(q);

          const matchCat = (card.category || '').toLowerCase().includes(q);

          if (!matchName && !matchCat) return false;

        }

        if (statusFilter !== 'all') {

          if (card.statusKey !== statusFilter) return false;

        }

        return true;

      });

    });

    const comparisonTotals = computed(() => {

      const cards = productsComparisonCards.value;

      const totalPlan = cards.reduce((sum, c) => sum + (c.planVal || 0), 0);

      const totalDeliv = cards.reduce((sum, c) => sum + (c.delivVal || 0), 0);

      const diff = Math.round((totalPlan - totalDeliv) * 100) / 100;

      const pct = totalPlan > 0 ? Math.round((totalDeliv / totalPlan) * 100) : 0;

      const overAlerts = cards.filter(c => c.statusKey === 'alert').length;

      return {

        planned: totalPlan,

        delivered: totalDeliv,

        diff: diff,

        pct: pct,

        overAlerts: overAlerts,

        totalItems: cards.length

      };

    });

    // Navigation to Project Opvolging

    const openProjectTracking = async (customer, department, contract_name) => {

      trackingCustomer.value = customer;

      trackingDepartment.value = department;

      trackingContract.value = contract_name;

      loadingTracking.value = true;

      if (isCloudMode && db) {

        try {

          const docId = `${customer}__${department}__${contract_name}`.replace(/[\/\s]/g, '_');

          const doc = await db.collection('dossiers').doc(docId).get();

          if (doc.exists) {

            const data = doc.data();

            let dJson = data.dossier_json ? JSON.parse(data.dossier_json) : data;

            trackingData.value = dJson.tracking || {};

            trackingPnl.value = (dJson.tracking && dJson.tracking.pnl_summary) || {};

            activeTrackingTab.value = 'cockpit';

            currentView.value = 'project_tracking';

            loadingTracking.value = false;

            return;

          }

        } catch (err) {

          console.error("Cloud openProjectTracking error:", err);

        }

      }

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(customer)}/${encodeURIComponent(department)}/${encodeURIComponent(contract_name)}/tracking`);

        if (res.ok) {

          const data = await res.json();

          trackingData.value = data.tracking || {};

          trackingPnl.value = data.pnl || (data.tracking && data.tracking.pnl_summary) || {};

          activeTrackingTab.value = 'cockpit';

          currentView.value = 'project_tracking';

        } else {

          alert('Kon opvolgingsgegevens niet ophalen.');

        }

      } catch (err) {

        console.error(err);

        alert('Fout bij ophalen projectopvolging.');

      } finally {

        loadingTracking.value = false;

      }

    };

    const refreshTracking = async () => {

      if (!trackingCustomer.value || !trackingDepartment.value || !trackingContract.value) return;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(trackingCustomer.value)}/${encodeURIComponent(trackingDepartment.value)}/${encodeURIComponent(trackingContract.value)}/tracking`);

        if (res.ok) {

          const data = await res.json();

          trackingData.value = data.tracking || {};

          trackingPnl.value = data.pnl || (data.tracking && data.tracking.pnl_summary) || {};

        }

      } catch (e) {

        console.error('Fout bij vernieuwen tracking:', e);

      }

    };

    // Contract Accepteren & Bevriezen

    const openAcceptContractModal = (customer, department, contract_name, contractObj = null) => {

      acceptForm.value.customer = customer;

      acceptForm.value.department = department;

      acceptForm.value.contract_name = contract_name;

      acceptForm.value.version_tag = 'Huidige Werkversie';

      acceptForm.value.duration_years = (contractObj && contractObj.duration_years) || 3;

      acceptForm.value.agreed_monthly_fee = (contractObj && (contractObj.monthly_fee || contractObj.calculated_fee)) || 0;

      acceptForm.value.signed_date = new Date().toISOString().substring(0, 10);

      acceptForm.value.start_date = new Date().toISOString().substring(0, 10);

      acceptForm.value.notes = '';

      acceptForm.value.agreed_modules = {

        execution_work: true,

        project_management: true,

        ilac_license: true,

        oil_analysis: true

      };

      showAcceptContractModal.value = true;

    };

    const submitAcceptContract = async () => {
      acceptingContract.value = true;
      if (isCloudMode && db) {
        try {
          const docId = `${acceptForm.value.customer}__${acceptForm.value.department}__${acceptForm.value.contract_name}`.replace(/[\/\s]/g, '_');
          const docRef = db.collection('dossiers').doc(docId);
          const doc = await docRef.get();
          if (doc.exists) {
            const data = doc.data();
            let dJson = data.dossier_json ? JSON.parse(data.dossier_json) : data;
            dJson.status = 'Actief';
            dJson.prices_frozen = true;
            dJson.tracking = dJson.tracking || {};
            dJson.tracking.is_active = true;
            dJson.tracking.accepted_at = new Date().toISOString();
            dJson.tracking.start_date = acceptForm.value.start_date;
            dJson.tracking.duration_years = acceptForm.value.duration_years || 3;
            await docRef.update({
              status: 'Actief',
              prices_frozen: true,
              dossier_json: JSON.stringify(dJson)
            });
          }
          showAcceptContractModal.value = false;
          showToast('Contract geaccepteerd! Calculatie is bevroren en opvolging geactiveerd.', 'success');
          await fetchHierarchy();
          await openProjectTracking(acceptForm.value.customer, acceptForm.value.department, acceptForm.value.contract_name);
          return;
        } catch (err) {
          console.error("Cloud accept error:", err);
          alert('Fout bij accepteren: ' + err.message);
        } finally {
          acceptingContract.value = false;
        }
        return;
      }
      try {
        const res = await fetch(`/api/contract/${encodeURIComponent(acceptForm.value.customer)}/${encodeURIComponent(acceptForm.value.department)}/${encodeURIComponent(acceptForm.value.contract_name)}/accept`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(acceptForm.value)

        });

        const result = await res.json();

        if (res.ok) {

          showAcceptContractModal.value = false;

          showToast('Contract geaccepteerd! Calculatie is bevroren en opvolging geactiveerd.', 'success');

          await fetchHierarchy();

          await openProjectTracking(acceptForm.value.customer, acceptForm.value.department, acceptForm.value.contract_name);

        } else {

          alert(result.error || 'Fout bij accepteren van contract');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij accepteren van contract');

      } finally {

        acceptingContract.value = false;

      }

    };

    // Klikken op contractkaart: als bevroren, vraag dubbele verificatie

    const handleOpenLockedContract = (customer, department, contract_name, con) => {

      if (con && (con.prices_frozen || con.status === 'Actief')) {

        unlockTarget.value = { customer, department, contract_name };

        unlockPassword.value = '';

        unlockAgreed.value = false;

        unlockNote.value = '';

        showUnlockCalcModal.value = true;

      } else {

        openContract(customer, department, contract_name);

      }

    };

    const submitUnlockCalculation = async () => {

      if (!unlockAgreed.value) {

        alert('U dient het vakje aan te vinken om te bevestigen dat u de calculatie wilt ontgrendelen.');

        return;

      }

      if (!unlockPassword.value) {

        alert('Voer het beheerderswachtwoord in.');

        return;

      }

      unlockingCalc.value = true;

      if (isCloudMode) {

        const val = (unlockPassword.value || '').trim();

        const valid = ['1nt3rfl0n', 'laas2026', 'interflon', 'Interflon', 'Interflon2026'];

        if (!valid.includes(val)) {

          alert('Onjuist beheerderswachtwoord.');

          unlockingCalc.value = false;

          return;

        }

        try {

          const docId = `${unlockTarget.value.customer}__${unlockTarget.value.department}__${unlockTarget.value.contract_name}`.replace(/[\/\s]/g, '_');

          if (db) {

            const docRef = db.collection('dossiers').doc(docId);

            const doc = await docRef.get();

            if (doc.exists) {

              const data = doc.data();

              let dJson = data.dossier_json ? JSON.parse(data.dossier_json) : data;

              dJson.prices_frozen = false;

              dJson.unlock_log = dJson.unlock_log || [];

              dJson.unlock_log.push({

                date: new Date().toISOString(),

                note: unlockNote.value

              });

              await docRef.update({

                prices_frozen: false,

                dossier_json: JSON.stringify(dJson)

              });

            }

          }

          showUnlockCalcModal.value = false;

          showToast('Calculatie ontgrendeld met beheerdersrecht.', 'success');

          await openContract(unlockTarget.value.customer, unlockTarget.value.department, unlockTarget.value.contract_name);

        } catch (err) {

          console.error("Cloud unlock error:", err);

          alert('Fout bij ontgrendelen: ' + err.message);

        } finally {

          unlockingCalc.value = false;

        }

        return;

      }

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(unlockTarget.value.customer)}/${encodeURIComponent(unlockTarget.value.department)}/${encodeURIComponent(unlockTarget.value.contract_name)}/unlock-calculation`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            password: unlockPassword.value,

            agreed_warning: unlockAgreed.value,

            note: unlockNote.value

          })

        });

        const result = await res.json();

        if (res.ok) {

          showUnlockCalcModal.value = false;

          showToast('Calculatie ontgrendeld met beheerdersrecht.', 'success');

          await fetchHierarchy();

          await openContract(unlockTarget.value.customer, unlockTarget.value.department, unlockTarget.value.contract_name);

        } else {

          alert(result.error || 'Onjuist wachtwoord of fout bij ontgrendelen.');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij ontgrendelen calculatie.');

      } finally {

        unlockingCalc.value = false;

      }

    };

    // Leveringen Toevoegen & Verwijderen

    const openAddDeliveryModal = () => {

      newDeliveryForm.value = {

        date: new Date().toISOString().substring(0, 10),

        bon_so: '',

        product_pack: '',

        qty: 1,

        content_per_pack: 1,

        purchase_unit: 0,

        sales_unit: 0,

        year: 1,

        in_fee: true

      };

      showAddDeliveryModal.value = true;

    };

    const submitAddDelivery = async () => {

      if (!newDeliveryForm.value.product_pack) {

        alert('Vul omschrijving/product in');

        return;

      }

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(trackingCustomer.value)}/${encodeURIComponent(trackingDepartment.value)}/${encodeURIComponent(trackingContract.value)}/tracking/delivery`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(newDeliveryForm.value)

        });

        const result = await res.json();

        if (res.ok) {

          trackingData.value = result.tracking;

          trackingPnl.value = result.pnl || (result.tracking && result.tracking.pnl_summary) || {};

          showAddDeliveryModal.value = false;

          showToast('Levering toegevoegd!', 'success');

        } else {

          alert(result.error || 'Fout bij toevoegen levering');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij toevoegen levering');

      }

    };

    const deleteDelivery = async (itemId) => {

      if (!confirm('Weet u zeker dat u deze levering wilt verwijderen?')) return;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(trackingCustomer.value)}/${encodeURIComponent(trackingDepartment.value)}/${encodeURIComponent(trackingContract.value)}/tracking/delivery/${encodeURIComponent(itemId)}`, {

          method: 'DELETE'

        });

        const result = await res.json();

        if (res.ok) {

          trackingData.value = result.tracking;

          trackingPnl.value = result.pnl || (result.tracking && result.tracking.pnl_summary) || {};

          showToast('Levering verwijderd.', 'info');

        } else {

          alert(result.error || 'Fout bij verwijderen levering');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij verwijderen levering');

      }

    };

    // Uren Registratie (PM, Partner, Regie)

    const openAddHoursModal = (cat = 'partner_regular') => {

      newHoursForm.value = {

        category: cat || activeHoursSubtab.value || 'partner_regular',

        date: new Date().toISOString().substring(0, 10),

        year: 1,

        technician: '',

        consultant: '',

        so_af: '',

        hours: 8,

        travel_days: 1,

        description: ''

      };

      showAddHoursModal.value = true;

    };

    const submitAddHours = async () => {

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(trackingCustomer.value)}/${encodeURIComponent(trackingDepartment.value)}/${encodeURIComponent(trackingContract.value)}/tracking/hours`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(newHoursForm.value)

        });

        const result = await res.json();

        if (res.ok) {

          trackingData.value = result.tracking;

          trackingPnl.value = result.pnl || (result.tracking && result.tracking.pnl_summary) || {};

          showAddHoursModal.value = false;

          showToast('Uren geregistreerd!', 'success');

        } else {

          alert(result.error || 'Fout bij opslaan uren');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij opslaan uren');

      }

    };

    const deleteHours = async (category, itemId) => {

      if (!confirm('Weet u zeker dat u deze urenregistratie wilt verwijderen?')) return;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(trackingCustomer.value)}/${encodeURIComponent(trackingDepartment.value)}/${encodeURIComponent(trackingContract.value)}/tracking/hours/${encodeURIComponent(category)}/${encodeURIComponent(itemId)}`, {

          method: 'DELETE'

        });

        const result = await res.json();

        if (res.ok) {

          trackingData.value = result.tracking;

          trackingPnl.value = result.pnl || (result.tracking && result.tracking.pnl_summary) || {};

          showToast('Urenregel verwijderd.', 'info');

        } else {

          alert(result.error || 'Fout bij verwijderen urenregel');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij verwijderen urenregel');

      }

    };

    // Facturatie Maand Toggle

    const toggleInvoiceMonth = async (monthIndex, currentInvoiced) => {

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(trackingCustomer.value)}/${encodeURIComponent(trackingDepartment.value)}/${encodeURIComponent(trackingContract.value)}/tracking/invoicing/toggle`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            month_index: monthIndex,

            invoiced: !currentInvoiced

          })

        });

        const result = await res.json();

        if (res.ok) {

          trackingData.value = result.tracking;

          trackingPnl.value = result.pnl || (result.tracking && result.tracking.pnl_summary) || {};

          showToast(`Maand ${monthIndex + 1} status bijgewerkt!`, 'success');

        } else {

          alert(result.error || 'Fout bij wijzigen facturatiestatus');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij aanpassen facturatie');

      }

    };

    // Extra Orders Buiten Fee

    const openAddOutOfFeeModal = () => {

      newOutOfFeeForm.value = {

        date: new Date().toISOString().substring(0, 10),

        order_nr: '',

        client_ref: '',

        description: '',

        sales_amount: 0,

        purchase_amount: 0,

        reason: ''

      };

      showAddOutOfFeeModal.value = true;

    };

    const submitAddOutOfFeeOrder = async () => {

      if (!newOutOfFeeForm.value.order_nr || !newOutOfFeeForm.value.description) {

        alert('Vul ordernummer en omschrijving in.');

        return;

      }

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(trackingCustomer.value)}/${encodeURIComponent(trackingDepartment.value)}/${encodeURIComponent(trackingContract.value)}/tracking/out-of-fee`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(newOutOfFeeForm.value)

        });

        const result = await res.json();

        if (res.ok) {

          trackingData.value = result.tracking;

          trackingPnl.value = result.pnl || (result.tracking && result.tracking.pnl_summary) || {};

          showAddOutOfFeeModal.value = false;

          showToast('Extra bestelling buiten fee toegevoegd!', 'success');

        } else {

          alert(result.error || 'Fout bij opslaan order buiten fee');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij opslaan order buiten fee');

      }

    };

    const deleteOutOfFeeOrder = async (itemId) => {

      if (!confirm('Weet u zeker dat u deze order buiten fee wilt verwijderen?')) return;

      try {

        const res = await fetch(`/api/contract/${encodeURIComponent(trackingCustomer.value)}/${encodeURIComponent(trackingDepartment.value)}/${encodeURIComponent(trackingContract.value)}/tracking/out-of-fee/${encodeURIComponent(itemId)}`, {

          method: 'DELETE'

        });

        const result = await res.json();

        if (res.ok) {

          trackingData.value = result.tracking;

          trackingPnl.value = result.pnl || (result.tracking && result.tracking.pnl_summary) || {};

          showToast('Order buiten fee verwijderd.', 'info');

        } else {

          alert(result.error || 'Fout bij verwijderen order');

        }

      } catch (e) {

        console.error(e);

        alert('Netwerkfout bij verwijderen order');

      }

    };

    // Excel Export van Tracking

    const exportTrackingExcel = () => {

      if (!trackingCustomer.value || !trackingDepartment.value || !trackingContract.value) return;

      window.location.href = `/api/contract/${encodeURIComponent(trackingCustomer.value)}/${encodeURIComponent(trackingDepartment.value)}/${encodeURIComponent(trackingContract.value)}/tracking/export/excel`;

    };

    // =========================================================================

    // START-UP ORDER MODULE STATE & LOGIC

    // =========================================================================

    const showStartupOrderModal = ref(false);

    const startupOrderLoading = ref(false);

    const startupOrderContract = ref({ customer: '', department: '', contract_name: '', is_active: false });

    const startupOrderMonths = ref(3);

    const startupOrderIncludeHardware = ref(true);

    const startupOrderItems = ref([]);

    const showAddStartupItemModal = ref(false);

    const newStartupItemForm = ref({

      product: '',

      article_nr: '',

      category: 'Smeermiddelen',

      packaging: '1 x 400 ml aerosol',

      qty: 1,

      net_unit_price: 0,

      purchase_unit: 0,

      item_type: 'Handmatig'

    });

    const startupOrderSummary = computed(() => {

      let totalItems = startupOrderItems.value.length;

      let totalUnits = 0;

      let totalSales = 0;

      let totalPurchase = 0;

      for (const it of startupOrderItems.value) {

        const q = parseFloat(it.qty) || 0;

        const s = parseFloat(it.net_unit_price) || 0;

        const p = parseFloat(it.purchase_unit) || 0;

        totalUnits += q;

        totalSales += q * s;

        totalPurchase += q * p;

      }

      const marginEur = totalSales - totalPurchase;

      const marginPct = totalSales > 0 ? (marginEur / totalSales) * 100 : 0;

      return {

        total_items: totalItems,

        total_units: Math.round(totalUnits),

        total_sales: Math.round(totalSales * 100) / 100,

        total_purchase: Math.round(totalPurchase * 100) / 100,

        margin_eur: Math.round(marginEur * 100) / 100,

        margin_pct: Math.round(marginPct * 10) / 10

      };

    });

    const openStartupOrderModal = async (customer, department, contract_name, contractObj = null) => {

      startupOrderContract.value = {

        customer,

        department,

        contract_name,

        is_active: !!(contractObj && (contractObj.is_active || contractObj.status === 'Actief'))

      };

      startupOrderMonths.value = 3;

      startupOrderIncludeHardware.value = true;

      showStartupOrderModal.value = true;

      await fetchStartupOrder();

    };

    const fetchStartupOrder = async () => {
      if (!startupOrderContract.value.customer || !startupOrderContract.value.contract_name) return;
      startupOrderLoading.value = true;
      if (isCloudMode && db) {
        try {
          const docId = `${startupOrderContract.value.customer}__${startupOrderContract.value.department}__${startupOrderContract.value.contract_name}`.replace(/[\/\s]/g, '_');
          const doc = await db.collection('dossiers').doc(docId);
          const doc = await docRef.get();
          if (doc.exists) {
            const data = doc.data();
            const dJson = data.dossier_json ? JSON.parse(data.dossier_json) : data;
            const ilac = dJson.ilac_calculation || {};
            const agg = ilac.aggregated_products || [];
            const fraction = (startupOrderMonths.value || 3) / 12.0;

            const items = [];
            for (const p of agg) {
              const qtyYear = p.units_needed || 1;
              const stoQty = Math.max(1, Math.ceil(qtyYear * fraction));
              const price = parseFloat(p.net_unit_price || p.price_per_unit || 0);
              const cost = parseFloat(p.cost_price || 0);
              items.push({
                item_type: p.category && p.category.toLowerCase().includes('cleaner') ? 'Reiniger' : 'Smeermiddel',
                article_nr: p.article_nr || '',
                product: p.product || p.article_name || '',
                description: p.article_name || p.product || '',
                category: p.category || 'Smeermiddelen',
                packaging: p.packaging || '',
                required_volume_formatted: p.required_volume_formatted || '-',
                qty: stoQty,
                net_unit_price: price,
                purchase_unit: cost,
                total_sales: Math.round(stoQty * price * 100) / 100,
                total_purchase: Math.round(stoQty * cost * 100) / 100,
                notes: 'Berekend op basis van ILAC'
              });
            }
            startupOrderItems.value = items;
            startupOrderLoading.value = false;
            return;
          }
        } catch (err) {
          console.error("Cloud startup order fetch error:", err);
        }
      }
      try {

        const cust = encodeURIComponent(startupOrderContract.value.customer);

        const dept = encodeURIComponent(startupOrderContract.value.department);

        const con = encodeURIComponent(startupOrderContract.value.contract_name);

        const res = await fetch(`/api/contract/${cust}/${dept}/${con}/startup-order?months=${startupOrderMonths.value}&include_hardware=${startupOrderIncludeHardware.value}`);

        if (res.ok) {

          const data = await res.json();

          startupOrderItems.value = (data.order && data.order.items) ? data.order.items : [];

        } else {

          alert('Kon start-up order niet ophalen van contract.');

        }

      } catch (err) {

        console.error('Fout bij ophalen start-up order:', err);

        alert('Fout bij berekenen van start-up order.');

      } finally {

        startupOrderLoading.value = false;

      }

    };

    const updateStartupOrderMonths = async (m) => {

      startupOrderMonths.value = m;

      await fetchStartupOrder();

    };

    const removeStartupOrderItem = (idx) => {

      startupOrderItems.value.splice(idx, 1);

    };

    const openAddStartupItemModal = () => {

      newStartupItemForm.value = {

        product: '',

        article_nr: '',

        category: 'Smeermiddelen',

        packaging: '1 x eenheid',

        qty: 1,

        net_unit_price: 0,

        purchase_unit: 0,

        item_type: 'Handmatig'

      };

      showAddStartupItemModal.value = true;

    };

    const submitAddStartupItem = () => {

      if (!newStartupItemForm.value.product) {

        alert('Vul a.u.b. een productnaam of omschrijving in.');

        return;

      }

      const qty = parseInt(newStartupItemForm.value.qty, 10) || 1;

      const net_unit_price = parseFloat(newStartupItemForm.value.net_unit_price) || 0;

      const purchase_unit = parseFloat(newStartupItemForm.value.purchase_unit) || 0;

      startupOrderItems.value.push({

        item_type: newStartupItemForm.value.item_type || 'Handmatig',

        article_nr: newStartupItemForm.value.article_nr || '',

        product: newStartupItemForm.value.product,

        description: newStartupItemForm.value.product,

        category: newStartupItemForm.value.category || 'Overig',

        packaging: newStartupItemForm.value.packaging || '1 x eenheid',

        required_volume_formatted: '-',

        qty: qty,

        net_unit_price: net_unit_price,

        purchase_unit: purchase_unit,

        total_sales: Math.round(qty * net_unit_price * 100) / 100,

        total_purchase: Math.round(qty * purchase_unit * 100) / 100,

        notes: 'Handmatig toegevoegd'

      });

      showAddStartupItemModal.value = false;

    };

    const exportStartupOrderExcel = async () => {

      if (!startupOrderContract.value.customer || !startupOrderContract.value.contract_name) return;

      try {

        const cust = encodeURIComponent(startupOrderContract.value.customer);

        const dept = encodeURIComponent(startupOrderContract.value.department);

        const con = encodeURIComponent(startupOrderContract.value.contract_name);

        const payload = {

          customer: startupOrderContract.value.customer,

          department: startupOrderContract.value.department,

          contract_name: startupOrderContract.value.contract_name,

          months: startupOrderMonths.value,

          include_hardware: startupOrderIncludeHardware.value,

          items: startupOrderItems.value,

          summary: startupOrderSummary.value

        };

        const res = await fetch(`/api/contract/${cust}/${dept}/${con}/startup-order/export/excel`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(payload)

        });

        if (res.ok) {

          const blob = await res.blob();

          const url = window.URL.createObjectURL(blob);

          const a = document.createElement('a');

          a.href = url;

          a.download = `Startup_Order_${startupOrderContract.value.customer}_${startupOrderContract.value.contract_name}.xlsx`.replace(/\s+/g, '_');

          document.body.appendChild(a);

          a.click();

          a.remove();

          window.URL.revokeObjectURL(url);

        } else {

          alert('Fout bij exporteren naar Excel.');

        }

      } catch (err) {

        console.error('Fout bij exporteren Excel:', err);

        alert('Fout bij exporteren naar Excel.');

      }

    };

    const exportStartupOrderPdf = async () => {

      if (!startupOrderContract.value.customer || !startupOrderContract.value.contract_name) return;

      try {

        const cust = encodeURIComponent(startupOrderContract.value.customer);

        const dept = encodeURIComponent(startupOrderContract.value.department);

        const con = encodeURIComponent(startupOrderContract.value.contract_name);

        const payload = {

          customer: startupOrderContract.value.customer,

          department: startupOrderContract.value.department,

          contract_name: startupOrderContract.value.contract_name,

          months: startupOrderMonths.value,

          include_hardware: startupOrderIncludeHardware.value,

          items: startupOrderItems.value,

          summary: startupOrderSummary.value

        };

        const res = await fetch(`/api/contract/${cust}/${dept}/${con}/startup-order/export/pdf`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify(payload)

        });

        if (res.ok) {

          const blob = await res.blob();

          const url = window.URL.createObjectURL(blob);

          const a = document.createElement('a');

          a.href = url;

          a.download = `Startup_Order_${startupOrderContract.value.customer}_${startupOrderContract.value.contract_name}.pdf`.replace(/\s+/g, '_');

          document.body.appendChild(a);

          a.click();

          a.remove();

          window.URL.revokeObjectURL(url);

        } else {

          alert('Fout bij exporteren naar PDF.');

        }

      } catch (err) {

        console.error('Fout bij exporteren PDF:', err);

        alert('Fout bij exporteren naar PDF.');

      }

    };

    const applyStartupOrderToDeliveries = async () => {

      if (!startupOrderContract.value.customer || !startupOrderContract.value.contract_name) return;

      if (!confirm(`Wilt u deze ${startupOrderItems.value.length} start-up order artikelen registreren als initiële levering in het Dashboard?`)) {

        return;

      }

      try {

        const cust = encodeURIComponent(startupOrderContract.value.customer);

        const dept = encodeURIComponent(startupOrderContract.value.department);

        const con = encodeURIComponent(startupOrderContract.value.contract_name);

        const res = await fetch(`/api/contract/${cust}/${dept}/${con}/startup-order/apply-to-deliveries`, {

          method: 'POST',

          headers: { 'Content-Type': 'application/json' },

          body: JSON.stringify({

            items: startupOrderItems.value,

            months: startupOrderMonths.value

          })

        });

        if (res.ok) {

          const data = await res.json();

          alert(`${data.added_count} artikelen succesvol overgenomen als levering in het Dashboard!`);

          showStartupOrderModal.value = false;

          if (currentView.value === 'project_tracking' && trackingContract.value === startupOrderContract.value.contract_name) {

            await refreshTracking();

          }

        } else {

          alert('Fout bij overnemen naar leveringen in Dashboard.');

        }

      } catch (err) {

        console.error('Fout bij applyStartupOrderToDeliveries:', err);

        alert('Fout bij overnemen naar leveringen.');

      }

    };

    onMounted(async () => {

      await fetchHierarchy();

      await fetchGlobalPriceList();

      await fetchStandardPackages();

      await fetchSuiteSettings();

      await fetchArchive();

    });

    return {

      // Project Opvolging & P&L Tracking

      activeTrackingTab,

      selectedComparisonYear,

      productsComparisonSearch,

      productsComparisonStatusFilter,

      productsComparisonCards,

      comparisonTotals,

      activeHoursSubtab,

      trackingCustomer,

      trackingDepartment,

      trackingContract,

      trackingData,

      trackingPnl,

      loadingTracking,

      openProjectTracking,

      refreshTracking,

      handleOpenLockedContract,

      showAcceptContractModal,

      acceptingContract,

      acceptForm,

      openAcceptContractModal,

      submitAcceptContract,

      showUnlockCalcModal,

      unlockingCalc,

      unlockPassword,

      unlockAgreed,

      unlockNote,

      unlockTarget,

      submitUnlockCalculation,

      showAddDeliveryModal,

      newDeliveryForm,

      openAddDeliveryModal,

      submitAddDelivery,

      deleteDelivery,

      showAddHoursModal,

      newHoursForm,

      openAddHoursModal,

      submitAddHours,

      deleteHours,

      toggleInvoiceMonth,

      showAddOutOfFeeModal,

      newOutOfFeeForm,

      openAddOutOfFeeModal,

      submitAddOutOfFeeOrder,

      deleteOutOfFeeOrder,

      exportTrackingExcel,

      // Start-up Order Module

      showStartupOrderModal,

      startupOrderLoading,

      startupOrderContract,

      startupOrderMonths,

      startupOrderIncludeHardware,

      startupOrderItems,

      startupOrderSummary,

      showAddStartupItemModal,

      newStartupItemForm,

      openStartupOrderModal,

      fetchStartupOrder,

      updateStartupOrderMonths,

      removeStartupOrderItem,

      openAddStartupItemModal,

      submitAddStartupItem,

      exportStartupOrderExcel,

      exportStartupOrderPdf,

      applyStartupOrderToDeliveries,

      // Portal & Hierarchy

      currentView,

      activePortalTab,

      hierarchy,

      customerMeta,

      archiveData,

      toastMessage,

      portalSearchQuery,

      expandedCustomers,

      filteredCustomersList,

      getCustomerContractCount,

      toggleCustomerExpand,

      isCustomerExpanded,

      expandAllCustomers,

      collapseAllCustomers,

      uploadCustomerLogo,

      uploadingLogo,

      // Selected Contract & Phase Navigation

      selectedCustomer,

      selectedDepartment,

      selectedContract,

      dossier,

      loadingDossier,

      activePhase,

      openContract,

      backToPortal,

      formatNum,

      formatCurrency,

      // Security

      isUnlocked,

      showPasswordModal,

      inputPassword,

      passwordError,

      unlockSystem,

      lockSystem,

      // Creation Modals

      showCreateCustomerModal,

      newCustomerName,

      openCreateCustomer,

      submitCreateCustomer,

      showCreateDeptModal,

      newDeptCustomer,

      newDeptName,

      openCreateDept,

      submitCreateDept,

      showCreateContractModal,

      newContractCustomer,

      newContractDept,

      newContractName,

      openCreateContract,

      submitCreateContract,

      // Archive & Delete

      archiveContract,

      archiveDepartment,

      archiveCustomer,

      restoreArchivedItem,

      showDeleteConfirmModal,

      deleteTarget,

      deletingItem,

      confirmPermanentDelete,

      executePermanentDelete,

      // Clear Calculation

      showClearCalcModal,

      clearingCalc,

      confirmClearCalculation,

      // Rename

      showRenameModal,

      renameTarget,

      renamingItem,

      renameError,

      openRenameModal,

      executeRename,

      // Fase 1 State & Controls

      activeFase1Tab,

      calcYears,

      uploadingILAC,

      uploadingPriceList,

      savingCalc,

      hasPriceList,

      priceListBtnText,

      onILACFileChange,

      changeContractYears,

      onPriceListFileChange,

      overrideProductPackaging,

      updateItemDiscount,

      // Filters

      pointsSearch,

      pointsDeptFilter,

      filteredILACPoints,

      uniqueDepartments,

      priceSearch,

      priceCategoryFilter,

      filteredPriceListItems,

      uniquePriceCategories,

      // Aggregates & Summary

      ilacPoints,

      priceListItems,

      aggregatedProducts,

      manualItems,

      calculationSummary,

      // Custom Articles (Pricelist)

      showAddCustomArticleModal,

      customArticleForm,

      submitCustomArticle,

      // Fase 2: Materials & Hardware (Meervoudige Categoriekaarten)

      materialGroups,

      activeMaterialGroupId,

      availableMaterialCategories,

      addMaterialGroup,

      renameMaterialGroup,

      deleteMaterialGroup,

      showAddMaterialModal,

      // Versiebeheer & Fase 3

      showVersionModal,

      versionForm,

      savingVersion,

      selectedProposalVersion,

      openSaveVersionModal,

      submitSaveVersion,

      restoreVersionToActive,

      // Fase 3: Voorstel & Waardepropositie

      proposalData,

      maatpakToggles,

      isGroupToggled,

      toggleMaatpakModule,

      maatpakTweeluik,

      scopeByLocation,

      editSectionModal,

      showMetadataModal,

      openEditSectionModal,

      saveSectionContent,

      saveProposalConfig,

      // Standaard Pakketten & Tools Checklist & Toeslagen

      // Globale Prijslijst & Suite Instellingen

      globalPriceList,

      uploadingGlobalPriceList,

      fetchGlobalPriceList,

      globalPlFileInput,

      triggerGlobalPriceListUpload,

      onGlobalPriceListFileChange,

      showSuiteSettingsModal,

      suiteSettingsTab,

      suiteSettings,

      showStaffelModal,

      selectedStaffelItem,

      openStaffelModal,

      closeStaffelModal,

      globalPlSearch,

      globalPlCategory,

      globalPlPage,

      globalPlPerPage,

      globalPriceListCategories,

      filteredGlobalPriceList,

      paginatedGlobalPriceList,

      totalGlobalPlPages,

      setGlobalPlPage,

      availableIndexCategories,

      toggleIndexCategory,

      selectAllIndexCategories,

      selectProductsIndexCategories,

      selectLaborIndexCategories,

      toggleSuiteIndexCategory,

      selectAllSuiteIndexCategories,

      selectProductsSuiteIndexCategories,

      deleteSuiteIndexationEntry,

      toggleSuiteSurchargeCategory,

      selectOilGreaseSuiteSurchargeCategories,

      selectAllSuiteSurchargeCategories,

      clearSuiteSurchargeCategories,

      savingSuiteSettings,

      openSuiteSettingsModal,

      saveSuiteSettings,

      standardPackages,

      loadingPackages,

      editingPackageId,

      editingPackageName,

      editingPackageDescription,

      startEditingPackage,

      cancelEditingPackage,

      savePackageInfo,

      showNewPackageModal,

      newPackageForm,

      activePackageIdForNewItem,

      newItemForm,

      createStandardPackage,

      deleteStandardPackage,

      onPricelistArticleSelect,

      addItemToPackage,

      removeItemFromPackage,

      saveAllStandardPackages,

      previewCompoundedFee,

      deleteIndexationEntry,

      activeVersionSnapshot,

      proposalMaterialGroups,

      showApplyPackageModal,

      selectedPackageId,

      packageInsertMode,

      packageTargetGroup,

      applyingPackage,

      openApplyPackageModal,

      submitApplyPackage,

      fetchStandardPackages,

      detectedTools,

      addingTool,

      toolTargetCardMap,

      addToolToContractCard,

      getToolBadgeColor,

      indexationForm,

      surchargeForm,

      initContractSettingsForms,

      submitIndexationUpdate,

      submitSurchargeUpdate,

      printProposal,

      materialMode,

      materialPricelistSearch,

      selectedPricelistItem,

      materialForm,

      filteredPriceListForMaterial,

      selectPriceListItemForMaterial,

      openAddMaterialModal,

      submitManualMaterial,

      deleteManualMaterial,

      // Fase 2: Work Hours & Proposal

      workHoursForm,

      savingWorkHours,

      saveFase2WorkHours,

      proposalSummary,

      // Calculation Settings Modal (Tandwiel)

      showCalcSettingsModal,

      savingCalcSettings,

      calcSettingsTab,

      calcSettingsForm,

      settingsPreview,

      openCalcSettingsModal,

      updateTravelFromKm,

      resetCalcSettingsToDefaults,

      saveCalcSettings,

      // New features: Categories, Discounts, Manual Units, Staffel & Tool Checklist

      standardCategoriesList,

      toolChecklist,

      filteredDetectedTools,

      completedToolsCount,

      updatingUnits,

      updateProductUnits,

      roundProductUnits,

      resetProductUnits,

      applyManualTier,

      resetManualTier,

      // Renewal Concept

      renewalForm,

      generatingRenewal,

      renewalTasks,

      generateRenewalConcept,

      toggleRenewalTask

    };

  }

});

app.mount('#app');