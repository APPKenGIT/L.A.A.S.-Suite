import re

# 1. Update templates/index.html
with open('L.A.A.S.-Suite/templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1a. Fix head & favicon
old_head_start = """<!DOC
{% raw %}

TYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>L.A.A.S. Suite - Lubrication As A Service</title>"""

new_head_start = """<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>L.A.A.S. Suite - Lubrication As A Service</title>
  <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">"""

if old_head_start in html:
    html = html.replace(old_head_start, new_head_start)
else:
    # Handle if slightly different whitespace
    html = re.sub(r'<!DOC\s*{% raw %}\s*TYPE html>\s*<html lang="nl">\s*<head>', '<!DOCTYPE html>\n<html lang="nl">\n<head>\n  <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">', html)

# Ensure {% raw %} is placed right after <div id="app" ...>
if '{% raw %}' not in html[:500]:
    app_div_match = re.search(r'(<div id="app"[^>]*>)', html)
    if app_div_match:
        html = html[:app_div_match.end()] + '\n{% raw %}\n' + html[app_div_match.end():]

# 1b. Change Aantal Paks to Aantal Units in Fase 1 header
old_paks_header = '<th class="py-3 px-3 text-center">Aantal Paks</th>'
new_units_header = '<th class="py-3 px-3 text-center">Aantal Units</th>'
assert old_paks_header in html, "Aantal Paks header not found"
html = html.replace(old_paks_header, new_units_header)

# 1c. Replace Fase 1 Staffel button and Units td in table
old_fase1_cells = """                    <td class="py-3 px-3 text-center">
                      <button 
                        v-if="prod.tiers && prod.tiers.length > 1" 
                        type="button"
                        @click.stop="openStaffelModal(prod)" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 inline-flex items-center gap-1 shadow-2xs transition cursor-pointer" 
                        :title="'Staffeltreden bekijken: ' + prod.tiers.map(t => t.min_qty + '+ stuks @ €' + formatNum(t.unit_price)).join(' | ')"
                      >
                        <svg class="w-3 h-3 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
                        <span>{{ prod.active_tier_min }}+</span>
                      </button>
                      <span v-else class="text-[10px] text-slate-400 font-mono">1</span>
                    </td>
                    <td class="py-3 px-3 text-center font-extrabold text-slate-900">
                      {{ prod.packages_needed || prod.packs_needed }}
                    </td>"""

new_fase1_cells = """                    <td class="py-3 px-3 text-center">
                      <button 
                        v-if="prod.tiers && prod.tiers.length > 1" 
                        type="button"
                        @click.stop="openStaffelModal(prod)" 
                        class="px-2 py-0.5 rounded-md text-[10px] font-bold inline-flex items-center gap-1 shadow-2xs transition cursor-pointer" 
                        :class="prod.is_manual_tier ? 'bg-amber-200 text-amber-900 border border-amber-400 font-black' : 'bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200'"
                        :title="'Staffeltreden bekijken & selecteren (Huidige trap: ' + prod.active_tier_min + '+)'"
                      >
                        <svg class="w-3 h-3 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
                        <span>{{ prod.active_tier_min }}+</span>
                        <span v-if="prod.is_manual_tier" class="text-amber-950 text-[9px] font-black" title="Manueel geselecteerde staffel">★</span>
                      </button>
                      <span v-else class="text-[10px] text-slate-400 font-mono">1</span>
                    </td>
                    <td class="py-3 px-3 text-center">
                      <div class="inline-flex flex-col items-center">
                        <div class="inline-flex items-center gap-1">
                          <button 
                            type="button"
                            @click.stop="roundProductUnits(prod, 12, 'down')" 
                            title="Afronden naar beneden (doos van 12)" 
                            class="w-5 h-5 rounded text-[10px] bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center font-bold transition cursor-pointer"
                          >
                            ▼
                          </button>
                          <input 
                            type="number" 
                            min="1" 
                            step="1" 
                            :value="prod.packages_needed || prod.packs_needed" 
                            @change="updateProductUnits(prod, $event.target.value)" 
                            class="w-16 text-center py-1 rounded-lg border text-xs font-mono font-extrabold transition focus:ring-1 focus:ring-sky-500"
                            :class="prod.is_manual_units ? 'border-amber-400 bg-amber-50 text-amber-900' : 'border-slate-200 bg-white text-slate-900'"
                          >
                          <button 
                            type="button"
                            @click.stop="roundProductUnits(prod, 12, 'up')" 
                            title="Afronden naar boven (doos van 12)" 
                            class="w-5 h-5 rounded text-[10px] bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center font-bold transition cursor-pointer"
                          >
                            ▲
                          </button>
                        </div>
                        <button 
                          v-if="prod.is_manual_units" 
                          type="button"
                          @click.stop="resetProductUnits(prod)" 
                          title="Herstel berekende hoeveelheid" 
                          class="text-[9px] text-amber-700 hover:underline font-semibold mt-0.5 cursor-pointer"
                        >
                          herstel auto
                        </button>
                      </div>
                    </td>"""

assert old_fase1_cells in html, "old_fase1_cells not found in index.html"
html = html.replace(old_fase1_cells, new_fase1_cells)

# 1d. Remove Subtab 3 from Fase 1 (Dossier Prijslijst & Kortingen)
# Remove tab button
old_fase1_btn3 = """          <button 
            @click="activeFase1Tab = 'pricelist'" 
            :class="activeFase1Tab === 'pricelist' ? 'bg-sky-50 text-sky-800 border-sky-300 font-bold' : 'text-slate-500 hover:bg-slate-100 border-transparent font-medium'"
            class="px-4 py-2 rounded-xl text-xs border transition flex items-center gap-1.5"
          >
            <span>Dossier Prijslijst &amp; Kortingen</span>
            <span class="px-2 py-0.5 rounded-full text-[10px] bg-slate-200 text-slate-700 font-semibold">{{ priceListItems.length }}</span>
          </button>"""
assert old_fase1_btn3 in html, "old_fase1_btn3 not found in index.html"
html = html.replace(old_fase1_btn3, "")

# Remove subtab 3 div block
old_fase1_subtab3_regex = r'<!-- SUBTAB 3: DOSSIER PRIJSLIJST & KORTINGEN -->.*?</div>\s*</div>\s*<!-- ========================================================================= -->\s*<!-- FASE 2:'
match_subtab3 = re.search(r'<!-- SUBTAB 3: DOSSIER PRIJSLIJST & KORTINGEN -->.*?(?=<!-- ========================================================================= -->\s*<!-- FASE 2:)', html, re.DOTALL)
assert match_subtab3 is not None, "match_subtab3 not found in index.html"
html = html[:match_subtab3.start()] + html[match_subtab3.end():]

# 1e. In staffelModal, add Selection Column and Reset Auto Button
old_staffel_head = """                <th class="py-2.5 px-3">Staffeltrap</th>
                <th class="py-2.5 px-3 text-center">Minimale Afname</th>
                <th class="py-2.5 px-3 text-right">Stukprijs</th>
                <th class="py-2.5 px-3 text-right">Korting t.o.v. Basis</th>"""

new_staffel_head = """                <th class="py-2.5 px-3">Staffeltrap</th>
                <th class="py-2.5 px-3 text-center">Minimale Afname</th>
                <th class="py-2.5 px-3 text-right">Stukprijs</th>
                <th class="py-2.5 px-3 text-right">Korting t.o.v. Basis</th>
                <th v-if="selectedStaffelItem.combo_key || selectedStaffelItem.product_name" class="py-2.5 px-3 text-center">Selectie</th>"""

assert old_staffel_head in html, "old_staffel_head not found in index.html"
html = html.replace(old_staffel_head, new_staffel_head)

old_staffel_row = """                <td class="py-2 px-3 text-right font-sans">
                  <span v-if="selectedStaffelItem.tiers && selectedStaffelItem.tiers[0] && selectedStaffelItem.tiers[0].unit_price > t.unit_price" class="text-emerald-600 font-bold text-[11px]">
                    -{{ Math.round((1 - t.unit_price / selectedStaffelItem.tiers[0].unit_price) * 100) }}%
                  </span>
                  <span v-else class="text-slate-400 text-[11px]">-</span>
                </td>"""

new_staffel_row = """                <td class="py-2 px-3 text-right font-sans">
                  <span v-if="selectedStaffelItem.tiers && selectedStaffelItem.tiers[0] && selectedStaffelItem.tiers[0].unit_price > t.unit_price" class="text-emerald-600 font-bold text-[11px]">
                    -{{ Math.round((1 - t.unit_price / selectedStaffelItem.tiers[0].unit_price) * 100) }}%
                  </span>
                  <span v-else class="text-slate-400 text-[11px]">-</span>
                </td>
                <td v-if="selectedStaffelItem.combo_key || selectedStaffelItem.product_name" class="py-2 px-3 text-center font-sans">
                  <span v-if="selectedStaffelItem.active_tier_min === t.min_qty" class="px-2.5 py-1 rounded-lg bg-emerald-100 text-emerald-800 font-bold text-[10px] inline-flex items-center gap-1 shadow-2xs">
                    <svg class="w-3 h-3 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                    Actief
                  </span>
                  <button 
                    v-else 
                    type="button" 
                    @click="applyManualTier(selectedStaffelItem, t.min_qty)" 
                    class="px-2.5 py-1 rounded-lg bg-sky-600 hover:bg-sky-700 text-white font-bold text-[10px] transition cursor-pointer shadow-2xs"
                  >
                    Kiezen
                  </button>
                </td>"""

assert old_staffel_row in html, "old_staffel_row not found in index.html"
html = html.replace(old_staffel_row, new_staffel_row)

old_staffel_footer = """        <div class="bg-slate-50 rounded-xl p-3 text-[11px] text-slate-500 flex items-center justify-between">
          <span>💡 Staffelprijzen worden automatisch toegepast op basis van de berekende jaarvolumes.</span>
          <button @click="closeStaffelModal" class="px-4 py-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold transition text-xs cursor-pointer">
            Sluiten
          </button>
        </div>"""

new_staffel_footer = """        <div class="bg-slate-50 rounded-xl p-3 text-[11px] text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>💡 Klik op 'Kiezen' om een specifieke staffeltrap manueel vast te leggen.</span>
          <div class="flex items-center gap-2">
            <button 
              v-if="selectedStaffelItem && selectedStaffelItem.is_manual_tier" 
              type="button" 
              @click="resetManualTier(selectedStaffelItem)" 
              class="px-3 py-1.5 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-900 border border-amber-300 font-bold text-xs transition cursor-pointer"
            >
              Herstel automatische staffel
            </button>
            <button @click="closeStaffelModal" class="px-4 py-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold transition text-xs cursor-pointer">
              Sluiten
            </button>
          </div>
        </div>"""

assert old_staffel_footer in html, "old_staffel_footer not found in index.html"
html = html.replace(old_staffel_footer, new_staffel_footer)

# 1f. Add Tab 4 (Discounts) in calcSettingsModal
old_calc_tabs = """          <button 
            @click="calcSettingsTab = 'services'" 
            :class="calcSettingsTab === 'services' ? 'bg-sky-50 text-sky-800 font-bold border-sky-200' : 'text-slate-500 hover:text-slate-700 border-transparent'"
            class="px-3 py-1.5 rounded-lg text-xs border transition cursor-pointer shrink-0"
          >
            3. Diensten, Software &amp; Conversies
          </button>
        </div>"""

new_calc_tabs = """          <button 
            @click="calcSettingsTab = 'services'" 
            :class="calcSettingsTab === 'services' ? 'bg-sky-50 text-sky-800 font-bold border-sky-200' : 'text-slate-500 hover:text-slate-700 border-transparent'"
            class="px-3 py-1.5 rounded-lg text-xs border transition cursor-pointer shrink-0"
          >
            3. Diensten, Software &amp; Conversies
          </button>
          <button 
            @click="calcSettingsTab = 'discounts'" 
            :class="calcSettingsTab === 'discounts' ? 'bg-sky-50 text-sky-800 font-bold border-sky-200' : 'text-slate-500 hover:text-slate-700 border-transparent'"
            class="px-3 py-1.5 rounded-lg text-xs border transition cursor-pointer shrink-0"
          >
            4. Kortingen (Globaal &amp; Categorie)
          </button>
        </div>"""

assert old_calc_tabs in html, "old_calc_tabs not found in index.html"
html = html.replace(old_calc_tabs, new_calc_tabs)

# Add Tab 4 content before Modal Footer in calcSettingsModal
old_modal_footer = """        <!-- Modal Footer -->
        <div class="flex items-center justify-between pt-4 border-t border-slate-100 shrink-0">"""

new_tab4_content = """          <!-- TAB 4: KORTINGEN (GLOBAAL & CATEGORIE) -->
          <div v-if="calcSettingsTab === 'discounts'" class="space-y-4">
            <div class="bg-sky-50 border border-sky-200 rounded-xl p-3.5 text-xs text-sky-900 space-y-1">
              <span class="font-bold block">💡 Contractkortingen Configureren:</span>
              <p class="text-sky-800 text-[11px] leading-relaxed">
                Stel hier een algemene contractkorting in of specifieke kortingen per artikelcategorie. Een categoriekorting heeft altijd voorrang op de algemene contractkorting. Kortingen worden automatisch doorgerekend in de nettoprijzen van alle audit- en hardwarelijnen.
              </p>
            </div>

            <div class="bg-slate-50 p-3.5 rounded-xl border border-slate-200/80">
              <label class="block text-slate-800 font-bold mb-1">Algemene Contractkorting (%):</label>
              <div class="flex items-center gap-2">
                <input 
                  type="number" 
                  min="0" 
                  max="100" 
                  step="0.5" 
                  v-model.number="calcSettingsForm.global_discount_pct" 
                  placeholder="0.0" 
                  class="w-28 px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-mono text-xs font-bold text-sky-900"
                >
                <span class="text-xs text-slate-500 font-medium">% standaard op alle artikelen (tenzij hieronder overschreven)</span>
              </div>
            </div>

            <div class="space-y-2">
              <label class="block text-slate-800 font-bold text-xs">Specifieke Categoriekortingen (%):</label>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div v-for="cat in standardCategoriesList" :key="cat" class="bg-slate-50 p-2.5 rounded-xl border border-slate-200/80 flex items-center justify-between gap-2">
                  <span class="text-xs font-semibold text-slate-700 truncate">{{ cat }}</span>
                  <div class="flex items-center gap-1 shrink-0">
                    <input 
                      type="number" 
                      min="0" 
                      max="100" 
                      step="0.5" 
                      v-model.number="calcSettingsForm.category_discounts[cat]" 
                      placeholder="-" 
                      class="w-16 px-2 py-1 rounded-lg border border-slate-300 bg-white font-mono text-xs text-right font-bold text-slate-900"
                    >
                    <span class="text-xs text-slate-400 font-bold">%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="flex items-center justify-between pt-4 border-t border-slate-100 shrink-0">"""

# Replace the closing div of Tab Contents + Modal Footer
old_tab_close_and_footer = """          </div>

        </div>

        <!-- Modal Footer -->
        <div class="flex items-center justify-between pt-4 border-t border-slate-100 shrink-0">"""

assert old_tab_close_and_footer in html, "old_tab_close_and_footer not found"
html = html.replace(old_tab_close_and_footer, new_tab4_content)

# 1g. In Fase 2: transform detected tools to subtle right sidebar checklist without aerosols
# Locate the old dark tools banner: lines 1056-1141
old_tools_pattern = re.search(r'<!-- TOOL & EQUIPMENT CHECKLIST UIT DE AUDIT.*?<!-- SECTION 1: MEERVOUDIGE & AANPASBARE MATERIAALGROEPEN \(FASE 2\) -->', html, re.DOTALL)
assert old_tools_pattern is not None, "old_tools_pattern not found in index.html"

# We replace the tools banner and wrap the subsequent Fase 2 sections in a flex row layout
# Locate end of Section 3 synthese
end_synthese_marker = '<!-- ========================================================================= -->\n      <!-- FASE 3: CONTRACTVOORSTEL, COMMERCIËLE BIJLAGEN & EXPORT -->'
assert end_synthese_marker in html, "end_synthese_marker not found"

# Let's see what is inside Fase 2 between old_tools_pattern.start() and end_synthese_marker
fase2_body = html[old_tools_pattern.end():html.find(end_synthese_marker)]

# The new layout has a 2-column flex wrapper:
new_fase2_layout = """<!-- FASE 2 BODY MET RECHTER VERGEET-MIJ-NIET TOOLS CHECKLIST -->
        <div class="flex flex-col lg:flex-row items-start gap-6">
          <!-- MAIN CONTENT (LINKS): MATERIAALGROEPEN, WERKUUR EN SYNTHESE -->
          <div class="flex-1 min-w-0 space-y-6 w-full">
            <!-- SECTION 1: MEERVOUDIGE & AANPASBARE MATERIAALGROEPEN (FASE 2) -->""" + fase2_body + """          </div>

          <!-- SIDEBAR (RECHTS): SUBTIELE VERGEET-MIJ-NIET TOOLS CHECKLIST -->
          <div v-if="filteredDetectedTools.length > 0" class="w-full lg:w-72 xl:w-80 shrink-0 space-y-3 sticky top-4">
            <div class="bg-white rounded-2xl border border-slate-200 p-4 shadow-2xs space-y-3">
              <div class="flex items-center justify-between border-b border-slate-100 pb-2.5">
                <div class="flex items-center gap-2">
                  <div class="w-7 h-7 rounded-lg bg-sky-100 text-sky-700 flex items-center justify-center font-bold">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/></svg>
                  </div>
                  <div>
                    <h4 class="text-xs font-bold text-slate-900">Benodigde Tools</h4>
                    <span class="text-[10px] text-slate-400">Vergeet-mij-niet lijst</span>
                  </div>
                </div>
                <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-mono">
                  {{ completedToolsCount }}/{{ filteredDetectedTools.length }}
                </span>
              </div>

              <p class="text-[11px] text-slate-500 leading-snug">
                Vereist voor de uitvoering van ILAC-instructies. Vink af zodra voorzien:
              </p>

              <div class="divide-y divide-slate-100 text-xs max-h-[460px] overflow-y-auto pr-1">
                <label 
                  v-for="tool in filteredDetectedTools" 
                  :key="tool.tool_name"
                  class="flex items-start gap-2.5 py-2.5 hover:bg-slate-50/80 px-1 rounded-lg cursor-pointer transition select-none"
                >
                  <input 
                    type="checkbox" 
                    v-model="toolChecklist[tool.tool_name]"
                    class="mt-0.5 w-4 h-4 rounded text-sky-600 border-slate-300 focus:ring-sky-500 cursor-pointer"
                  >
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between gap-1">
                      <span 
                        class="font-bold text-xs truncate"
                        :class="toolChecklist[tool.tool_name] ? 'line-through text-slate-400' : 'text-slate-800'"
                      >
                        {{ tool.tool_name }}
                      </span>
                      <span class="text-[10px] text-slate-400 shrink-0 font-mono">
                        {{ tool.point_count }} pt
                      </span>
                    </div>
                    <div v-if="tool.sample_points && tool.sample_points.length > 0" class="text-[10px] text-slate-400 truncate mt-0.5">
                      bv. {{ tool.sample_points[0] }}
                    </div>
                  </div>
                </label>
              </div>

              <div class="bg-slate-50 rounded-xl p-2.5 text-[10px] text-slate-500 border border-slate-100 flex items-center gap-1.5">
                <svg class="w-3.5 h-3.5 text-sky-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                <span>Aerosols / spuitbussen zijn reeds opgenomen in de smeermiddelen.</span>
              </div>
            </div>
          </div>
        </div>
"""

html = html[:old_tools_pattern.start()] + new_fase2_layout + html[html.find(end_synthese_marker):]

with open('L.A.A.S.-Suite/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("templates/index.html updated successfully!")
