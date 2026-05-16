# skill: report_export

## name
report_export

## description
Export a completed report to PDF, PPTX, XLSX, or standalone HTML.

## when_to_use
- User asks "export this", "give me the PDF", "download as Excel"
- POST /export/* route is triggered
- A completed company_report or document is ready for export

## when_not_to_use
- No completed report exists to export
- User wants inline analysis, not a file

## inputs_required
- Completed report content (final_report or document)
- Target format (pdf, pptx, xlsx, html)
- Optional: filename override

## steps
1. Receive completed report and target format
2. Route to correct builder: pdf_render, build_deck, or build_workbook
3. Save output to atlas_vault/03-Outputs/
4. Return download path or file response

## outputs
- renderer_type: document
- Format: file download (binary or HTML string)
- Saved to: atlas_vault/03-Outputs/
- Includes: as-of timestamp in filename

## safety_rules
- Do not include API keys or secrets in exported files
- Label all data with as-of timestamps
- Exported files go to atlas_vault/03-Outputs/ only (not arbitrary paths)

## quality_checks
- File saved to atlas_vault/03-Outputs/
- As-of timestamp in filename
- No API keys in exported file
- File is non-empty

## examples
Input: Completed BlackRock company report + format=pdf
Output: PDF saved to atlas_vault/03-Outputs/blackrock_report_20260515.pdf

## repair_strategy
If PDF render fails (WeasyPrint/GTK error), fall back to HTML export and notify user.

## related_files
- omega_os/skills/company_report/skill.md
- omega_os/skills/document_generator/skill.md
- atlas_export/pdf_render.py
