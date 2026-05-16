# skill: document_generator

## name
document_generator

## description
Generate a structured document — PDF, PPTX, XLSX, or formatted text report — on demand.

## when_to_use
- User explicitly requests a PDF, report document, presentation, or spreadsheet
- output_mode is "document"
- User says "make a report", "give me a PDF", "create a document"

## when_not_to_use
- User wants analysis inline in chat (use company_report or general_chat)
- User wants an interactive HTML dashboard (use dashboard_generator)

## inputs_required
- Subject or topic for the document
- Optional: format preference (PDF, PPTX, XLSX)
- Optional: sections to include

## steps
1. Confirm output_mode is document and user explicitly requested a file
2. Gather or generate content (may call company_report internally)
3. Build document structure: cover page, sections, data tables
4. Export via atlas_export/ builder (pdf_render, build_deck, or build_workbook)
5. Save to atlas_vault/03-Outputs/ and return download link

## outputs
- renderer_type: document
- Format: structured document ready for export (PDF/PPTX/XLSX)
- Tone: formal, professional
- Saved to: atlas_vault/03-Outputs/

## safety_rules
- Do not include raw API keys or credentials in any document
- Label all data sources at the end of the document
- Generated documents must include a timestamp and data-as-of date

## quality_checks
- Document file was created and path returned
- Cover page and timestamp present
- Data sources labeled
- No API keys or secrets in output

## examples
Input: "Make a PDF report on Microsoft"
Output: PDF file saved to atlas_vault/03-Outputs/microsoft_report_20260515.pdf

## repair_strategy
If PDF render fails (WeasyPrint/GTK error), fall back to HTML export and notify user.
If document is missing required sections, append them before export.

## related_files
- omega_os/skills/company_report/skill.md
- omega_os/skills/report_export/skill.md
- atlas_export/pdf_render.py
