"""
omega_google_workspace.py — Google Workspace export adapter for Omega OS.

Prepares report/document exports to Google Docs, Sheets, and Drive.
Returns structured not_configured responses when credentials are absent —
never crashes regardless of environment.

When GOOGLE_WORKSPACE_ENABLED=true and credentials are present:
  - Requires: google-auth, google-auth-oauthlib, google-api-python-client
  - Token refresh via GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET + GOOGLE_REFRESH_TOKEN

Usage:
    from omega_google_workspace import is_google_workspace_configured, export_report_bundle
    status = get_google_workspace_status()
    result = export_report_bundle(report_id="abc123", formats=["doc", "sheet"])
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

# ── Credential env vars ───────────────────────────────────────────────────────
_REQUIRED_VARS = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN",
)
_PLACEHOLDER_FRAGMENTS = ("YOUR_", "your_", "apps.googleusercontent.com.YOUR")

# Scopes required for Docs + Sheets + Drive file creation
_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


# ── Detection ─────────────────────────────────────────────────────────────────

def is_google_workspace_configured() -> bool:
    """
    Return True when:
      - GOOGLE_WORKSPACE_ENABLED=true
      - All required credentials are present and non-placeholder
    """
    enabled = os.getenv("GOOGLE_WORKSPACE_ENABLED", "false").strip().lower()
    if enabled not in ("true", "1", "yes"):
        return False
    for var in _REQUIRED_VARS:
        val = os.getenv(var, "").strip()
        if not val:
            return False
        for frag in _PLACEHOLDER_FRAGMENTS:
            if frag in val:
                return False
    return True


def get_google_workspace_status() -> dict[str, Any]:
    """
    Return a structured status dict describing credential availability.

    Fields:
        configured: bool
        enabled: bool (reflects GOOGLE_WORKSPACE_ENABLED env var)
        missing_vars: list of required env vars that are absent or placeholder
        available_operations: list of enabled operations
        message: human-readable summary
    """
    enabled_raw = os.getenv("GOOGLE_WORKSPACE_ENABLED", "false").strip().lower()
    enabled = enabled_raw in ("true", "1", "yes")

    missing: list[str] = []
    for var in _REQUIRED_VARS:
        val = os.getenv(var, "").strip()
        if not val:
            missing.append(var)
            continue
        for frag in _PLACEHOLDER_FRAGMENTS:
            if frag in val:
                missing.append(var)
                break

    configured = enabled and not missing

    ops: list[str] = []
    if configured:
        ops = ["create_report_doc", "create_research_sheet", "export_report_bundle"]

    msg = (
        "Google Workspace integration active."
        if configured
        else (
            "Google Workspace not enabled. Set GOOGLE_WORKSPACE_ENABLED=true and configure credentials in .env."
            if not enabled
            else f"Google Workspace enabled but missing credentials: {', '.join(missing)}"
        )
    )

    return {
        "configured":            configured,
        "enabled":               enabled,
        "missing_vars":          missing,
        "available_operations":  ops,
        "message":               msg,
        "scopes":                _SCOPES if configured else [],
        "folder_id":             os.getenv("GOOGLE_DRIVE_REPORTS_FOLDER_ID", ""),
    }


# ── Internal credential builder ───────────────────────────────────────────────

def _build_credentials():
    """
    Build a google.oauth2.credentials.Credentials object from env vars.
    Returns None when credentials are unavailable or google-auth is not installed.
    """
    if not is_google_workspace_configured():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as _GRequest

        creds = Credentials(
            token=None,
            refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN", ""),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            scopes=_SCOPES,
        )
        creds.refresh(_GRequest())
        return creds
    except ImportError:
        log.warning("omega_google_workspace: google-auth not installed — run: pip install google-auth google-auth-oauthlib google-api-python-client")
        return None
    except Exception as exc:
        log.warning("omega_google_workspace: credential build failed — %s", exc)
        return None


def _not_configured_response(operation: str, **extra: Any) -> dict[str, Any]:
    """Return a structured not_configured response for any operation."""
    return {
        "success":           False,
        "status":            "not_configured",
        "operation":         operation,
        "message":           "Google Workspace credentials not configured. Set GOOGLE_WORKSPACE_ENABLED=true and add credentials to .env.",
        "configured":        False,
        **extra,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def create_report_doc(
    title: str,
    markdown_content: str,
    folder_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a Google Doc from report content.

    Args:
        title: Document title
        markdown_content: Report content (Markdown; converted to plain text for Docs API)
        folder_id: Google Drive folder ID (defaults to GOOGLE_DRIVE_REPORTS_FOLDER_ID)

    Returns dict with:
        success: bool
        status: "created" | "not_configured" | "error"
        doc_id: str | None
        doc_url: str | None
        title: str
    """
    if not is_google_workspace_configured():
        return _not_configured_response("create_report_doc", title=title, doc_id=None, doc_url=None)

    target_folder = folder_id or os.getenv("GOOGLE_DRIVE_REPORTS_FOLDER_ID", "")

    try:
        from googleapiclient.discovery import build as _gbuild

        creds = _build_credentials()
        if not creds:
            return _not_configured_response("create_report_doc", title=title, doc_id=None, doc_url=None)

        docs_service = _gbuild("docs", "v1", credentials=creds)
        drive_service = _gbuild("drive", "v3", credentials=creds)

        # Create empty document
        doc = docs_service.documents().create(body={"title": title}).execute()
        doc_id = doc.get("documentId")

        # Insert content as plain text (Markdown → plain text)
        plain_text = markdown_content.replace("**", "").replace("*", "").replace("#", "")
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [{
                    "insertText": {
                        "location": {"index": 1},
                        "text": plain_text,
                    }
                }]
            },
        ).execute()

        # Move to target folder if specified
        if target_folder:
            drive_service.files().update(
                fileId=doc_id,
                addParents=target_folder,
                removeParents="root",
                fields="id, parents",
            ).execute()

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        log.info("omega_google_workspace: created doc %s — %s", doc_id, title)
        return {
            "success":  True,
            "status":   "created",
            "operation": "create_report_doc",
            "doc_id":   doc_id,
            "doc_url":  doc_url,
            "title":    title,
            "folder_id": target_folder or None,
        }
    except Exception as exc:
        log.warning("omega_google_workspace: create_report_doc failed — %s", exc)
        return {
            "success":   False,
            "status":    "error",
            "operation": "create_report_doc",
            "error":     str(exc)[:200],
            "title":     title,
            "doc_id":    None,
            "doc_url":   None,
        }


def create_research_sheet(
    title: str,
    rows: list[list[Any]],
    folder_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a Google Sheet from tabular research data.

    Args:
        title: Spreadsheet title
        rows: List of rows, each row is a list of values (first row = headers)
        folder_id: Google Drive folder ID (defaults to GOOGLE_DRIVE_REPORTS_FOLDER_ID)

    Returns dict with:
        success: bool
        status: "created" | "not_configured" | "error"
        sheet_id: str | None
        sheet_url: str | None
        title: str
        rows_written: int
    """
    if not is_google_workspace_configured():
        return _not_configured_response(
            "create_research_sheet",
            title=title, sheet_id=None, sheet_url=None, rows_written=0,
        )

    target_folder = folder_id or os.getenv("GOOGLE_DRIVE_REPORTS_FOLDER_ID", "")

    try:
        from googleapiclient.discovery import build as _gbuild

        creds = _build_credentials()
        if not creds:
            return _not_configured_response(
                "create_research_sheet",
                title=title, sheet_id=None, sheet_url=None, rows_written=0,
            )

        sheets_service = _gbuild("sheets", "v4", credentials=creds)
        drive_service  = _gbuild("drive", "v3", credentials=creds)

        # Create spreadsheet
        sheet = sheets_service.spreadsheets().create(
            body={"properties": {"title": title}}
        ).execute()
        sheet_id = sheet.get("spreadsheetId")

        # Write rows
        if rows:
            sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="Sheet1!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [[str(c) for c in row] for row in rows]},
            ).execute()

        # Move to target folder
        if target_folder:
            drive_service.files().update(
                fileId=sheet_id,
                addParents=target_folder,
                removeParents="root",
                fields="id, parents",
            ).execute()

        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        log.info("omega_google_workspace: created sheet %s — %s (%d rows)", sheet_id, title, len(rows))
        return {
            "success":      True,
            "status":       "created",
            "operation":    "create_research_sheet",
            "sheet_id":     sheet_id,
            "sheet_url":    sheet_url,
            "title":        title,
            "rows_written": len(rows),
            "folder_id":    target_folder or None,
        }
    except Exception as exc:
        log.warning("omega_google_workspace: create_research_sheet failed — %s", exc)
        return {
            "success":      False,
            "status":       "error",
            "operation":    "create_research_sheet",
            "error":        str(exc)[:200],
            "title":        title,
            "sheet_id":     None,
            "sheet_url":    None,
            "rows_written": 0,
        }


def export_report_bundle(
    report_id: str,
    formats: list[str] | None = None,
) -> dict[str, Any]:
    """
    Export a report as one or more Google Workspace files.

    Loads report metadata from omega_persistence if available.
    Supports formats: "doc" (Google Doc), "sheet" (Google Sheet).

    Args:
        report_id: The report ID (from omega_persistence)
        formats: List of export formats, default ["doc", "sheet"]

    Returns dict with:
        success: bool
        status: "exported" | "not_configured" | "partial" | "error"
        report_id: str
        exports: dict[format_name, export_result]
        configured: bool
    """
    if formats is None:
        formats = ["doc", "sheet"]

    if not is_google_workspace_configured():
        return {
            "success":    False,
            "status":     "not_configured",
            "report_id":  report_id,
            "configured": False,
            "exports":    {},
            "message":    "Google Workspace credentials not configured. Set GOOGLE_WORKSPACE_ENABLED=true and add credentials to .env.",
        }

    # Load report metadata from persistence layer
    report_meta: dict[str, Any] = {}
    try:
        from omega_persistence import get_recent_reports
        recent = get_recent_reports(limit=100)
        for r in recent:
            if r.get("id") == report_id:
                report_meta = r
                break
    except Exception:
        pass  # Persistence unavailable — continue with minimal metadata

    title = report_meta.get("query", f"Report {report_id}")[:120]
    exports: dict[str, Any] = {}
    any_success = False

    if "doc" in formats:
        content = (
            f"# {title}\n\n"
            f"Query: {report_meta.get('query', 'N/A')}\n"
            f"Intent: {report_meta.get('intent', 'N/A')}\n"
            f"Generated: {report_meta.get('saved_at', 'N/A')}\n"
        )
        exports["doc"] = create_report_doc(title=title, markdown_content=content)
        if exports["doc"].get("success"):
            any_success = True

    if "sheet" in formats:
        headers = ["Field", "Value"]
        rows = [
            headers,
            ["Report ID",  report_id],
            ["Query",      report_meta.get("query", "N/A")],
            ["Intent",     report_meta.get("intent", "N/A")],
            ["Output Mode", report_meta.get("output_mode", "N/A")],
            ["Company",    report_meta.get("company") or "N/A"],
            ["Saved At",   report_meta.get("saved_at", "N/A")],
        ]
        exports["sheet"] = create_research_sheet(title=f"{title} — Data", rows=rows)
        if exports["sheet"].get("success"):
            any_success = True

    all_success = all(e.get("success") for e in exports.values())
    status = "exported" if all_success else ("partial" if any_success else "error")

    return {
        "success":    all_success,
        "status":     status,
        "report_id":  report_id,
        "configured": True,
        "exports":    exports,
        "formats_requested": formats,
    }
