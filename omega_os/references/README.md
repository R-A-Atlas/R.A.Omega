# References

External references, templates, and guides that inform skill execution.

## Subfolders

- **api_docs/** — API documentation snippets for connected services
- **report_templates/** — HTML/PDF/Excel/PowerPoint report templates
- **ui_design/** — UI component specs, color palettes, layout guides
- **prompt_templates/** — Reusable prompt fragments for synthesis and analysis

## How to Use

Reference files are loaded by omega_os_loader at Level 3 — only when a skill explicitly
needs them. They are not included in every prompt.

Example: The company_report skill loads references/report_templates/company_report.md
only when generating a structured company report.
