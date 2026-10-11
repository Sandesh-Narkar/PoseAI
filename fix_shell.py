#!/usr/bin/env python3
"""Fix shell.js dropdown behavior - use line-based approach"""
import sys

filepath = r'C:\Users\Rekha\OneDrive\Desktop\Second_year\frontend\js\shell.js'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and remove the mouseleave/mouseenter handlers
output_lines = []
skip_until_end_brace = False
found_mouseenter_comment = False

for i, line in enumerate(lines):
    # Check if this is the mouseleave section we want to remove
    if '// Keep dropdown open while hovering (reset close timer on enter)' in line:
        found_mouseenter_comment = True
        skip_until_end_brace = True
        continue
    
    if skip_until_end_brace:
        # Skip lines until we find the end of this section
        if line.strip() == '}' and i > 0 and '// If mouse re-enters' in lines[i-1] if i > 0 else False:
            skip_until_end_brace = False
            continue
        if line.strip().startswith('// If mouse re-enters'):
            continue
        if line.strip() == '}':
            # Check if this is the closing brace of the mouseleave handler
            # Look at context
            if i >= 2 and '// Delay close on mouseleave' in lines[i-6] if i >= 6 else False:
                skip_until_end_brace = False
                continue
        continue
    
    output_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

print('SUCCESS: Updated shell.js - removed mouseleave/mouseenter handlers')
