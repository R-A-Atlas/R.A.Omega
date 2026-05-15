# Skill: document_generator

## name
document_generator

## description
Generate a professional export document (PDF, Excel, or PowerPoint) from query results or
a structured research request. Uses atlas_export/ builders.

## when_to_use
- User asks "make me a PDF report on [topic]"
- User asks "generate an Excel spreadsheet for [data]"
- User asks "create a PowerPoint deck on [topic]"
- intent == DOCUMENT_GENERATION
- output_mode == document

## inputs_required
- Topic or query (required)
- Format: pdf | excel | pptx (required)
- Optional: specific data to include (e.g., "include options chain")
- Optional: company name or ticker

## steps
1. Confirm output format from query (PDF / Excel / PowerPoint)
2. Route to POST /export/{pdf|pptx|xlsx} with the same body as a /query request
3. Run synthesis via OmegaAgent or FourLoopEngine depending on intent
4. Apply OUTPUT_CONTRACTS["document"] — required sections, no forbidden phrases
5. Build document using the appropriate atlas_export/ builder:
   - pdf_render.py → WeasyPrint or browser print
   - build_workbook.py → openpyxl Excel
   - build_deck.py → python-pptx PowerPoint
6. Save output to atlas_vault/03-Outputs/ with timestamp in filename
7. Return download link or file path to user

## outputs
- Document file saved to atlas_vault/03-Outputs/
- Download link or file path
- Success confirmation with file size and page count

## safety_rules
- Maximum file size: 50MB (reject oversized data requests)
- Never include API keys, session tokens, or internal configs in documents
- Do not include personal financial data unless explicitly requested by the user
- Label all data with source and date — never present cached data as live
- Do not auto-send documents via email without explicit user confirmation

## related_files
- atlas_export/pdf_render.py — PDF builder
- atlas_export/build_deck.py — PowerPoint builder
- atlas_export/build_workbook.py — Excel builder
- api_server.py — POST /export/pdf, POST /export/pptx, POST /export/xlsx
- atlas_vault/03-Outputs/ — output directory
- omega_os/references/report_templates/README.md — document templates

## quality_checks
- [ ] Correct file format generated (pdf / xlsx / pptx)
- [ ] File saved to atlas_vault/03-Outputs/ with timestamp
- [ ] File size under 50MB
- [ ] No API keys or secrets in document
- [ ] Data sources labeled with date
- [ ] output_mode == "document" confirmed before generation
