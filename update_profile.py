#!/usr/bin/env python3
"""Update profile.html - replace export and add workout report download"""
import sys

filepath = r'C:\Users\Rekha\OneDrive\Desktop\Second_year\frontend\html\profile.html'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the export section using the known text
idx = content.find('Export my data')
if idx < 0:
    print('ERROR: Export section not found')
    sys.exit(1)

# Find the start of the div containing this button
div_start = content.rfind('<!-- Export', 0, idx)
if div_start < 0:
    div_start = content.rfind('<div class="bg-surface-container-lowest rounded-3xl p-6 shadow-sm">', 0, idx)
    if div_start < 0:
        print('ERROR: Could not find export div start')
        sys.exit(1)

# Find the end of the export section (the hr after it)
hr_start = content.find('<div class="h-px bg-surface-container-high my-6"></div>', idx)
if hr_start < 0:
    print('ERROR: Could not find hr after export')
    sys.exit(1)

# Find the end of the hr div
hr_end = content.find('></div>', hr_start) + len('></div>')

old_section = content[div_start:hr_end]

new_section = '''<!-- Export workout data -->
          <div class="bg-surface-container-lowest rounded-3xl p-6 shadow-sm">
            <h3 class="text-base font-bold text-on-surface mb-1">Workout Data</h3>
            <p class="text-sm text-on-surface-variant mb-4">Download your workout history and performance reports.</p>
            <button onclick="App.exportWorkoutReport()"
              class="flex items-center gap-2 px-6 py-2.5 rounded-full bg-primary hover:bg-primary-container text-on-primary text-sm font-bold transition-all">
              <span class="material-symbols-outlined text-[18px]">download</span>Export Workout History
            </button>
          </div>
          <div class="h-px bg-surface-container-high my-6"></div>'''

content = content.replace(old_section, new_section)
print('SUCCESS: Replaced export section')

# Now replace the exportData function with exportWorkoutReport
old_js = '''      async function exportData() {
        try {
          const res = await fetch("/api/data/export", { credentials: "same-origin" });
          if (!res.ok) throw new Error((await res.json().catch(() => ({}))).message || res.statusText);
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = "poseai-data.json";
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
        } catch (err) {
          alert("Export failed: " + err.message);
        }
      }'''

new_js = '''      async function exportWorkoutReport() {
        try {
          const res = await window.api.get("/api/analysis");
          const data = res.data || {};
          if (!data || data.hasData === false) {
            alert("No workout history found. Complete a workout first.");
            return;
          }
          if (data.id) {
            window.location.href = "/api/workouts/" + data.id + "/report/download";
          } else {
            alert("Could not find workout data for export.");
          }
        } catch (err) {
          alert("Export failed: " + err.message);
        }
      }'''

if old_js in content:
    content = content.replace(old_js, new_js)
    print('SUCCESS: Replaced exportData with exportWorkoutReport')
else:
    print('WARNING: exportData function not found - searching...')
    idx2 = content.find('async function exportData')
    if idx2 >= 0:
        print(f'Found at {idx2}')
        print(content[idx2:idx2+400])

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done - profile.html updated')



""" satyam@gmail.com and password """