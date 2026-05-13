"""
agents/storage_agent.py
-----------------------
Storage Agent

Responsibilities:
  1. Save the full Markdown report to a local file.
  2. Upload the report to Google Docs (formatted).
  3. Append a summary row to a Google Sheets tracker.

Google Auth:
  - Requires credentials.json (OAuth 2.0 Desktop App) downloaded from
    Google Cloud Console with Drive and Sheets APIs enabled.
  - On first run, opens a browser for OAuth consent. Subsequent runs use
    the cached token.json.
  - Set GOOGLE_DRIVE_FOLDER_ID env var to save into a specific folder.

Local fallback:
  - If Google credentials are missing, the report is saved to data/ only.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Google API scopes
_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


# ── Google Auth Helper ────────────────────────────────────────────────────────

def _get_google_credentials():
    """
    Return valid Google OAuth2 credentials, refreshing or re-authorising as needed.
    Returns None if credentials.json is absent (Google integration disabled).
    """
    creds_file = Path(settings.GOOGLE_CREDENTIALS_FILE)
    token_file = Path(settings.GOOGLE_TOKEN_FILE)

    if not creds_file.exists():
        logger.warning("google_credentials_missing", path=str(creds_file))
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None

        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), _SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_file), _SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Cache token
            token_file.write_text(creds.to_json())

        return creds

    except Exception as exc:
        logger.error("google_auth_error", error=str(exc))
        return None


# ── Google Docs ───────────────────────────────────────────────────────────────

async def _create_google_doc(
    title: str,
    markdown_content: str,
    creds,
) -> Optional[str]:
    """
    Create a Google Doc from Markdown content.
    Returns the document URL or None on failure.

    Note: Google Docs API does not natively render Markdown.
    We insert the Markdown as plain text with basic heading formatting
    using batchUpdate requests.
    """
    try:
        from googleapiclient.discovery import build

        docs_service = build("docs", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        # 1. Create the document
        doc = docs_service.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

        # 2. Insert content as plain text
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": 1},
                            "text": markdown_content,
                        }
                    }
                ]
            },
        ).execute()

        # 3. Move to target folder if specified
        if settings.GOOGLE_DRIVE_FOLDER_ID:
            drive_service.files().update(
                fileId=doc_id,
                addParents=settings.GOOGLE_DRIVE_FOLDER_ID,
                removeParents="root",
                fields="id, parents",
            ).execute()

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        logger.info("google_doc_created", url=doc_url)
        return doc_url

    except Exception as exc:
        logger.error("google_doc_error", error=str(exc))
        return None


# ── Google Sheets ─────────────────────────────────────────────────────────────

_SHEET_NAME = "Research Agent Log"

async def _append_to_google_sheet(
    metadata: dict[str, Any],
    scored_sources: list[dict[str, Any]],
    doc_url: Optional[str],
    creds,
) -> Optional[str]:
    """
    Append a summary row to the research log Google Sheet.
    Creates the sheet if it doesn't exist in the target folder.
    Returns the sheet URL or None on failure.
    """
    try:
        from googleapiclient.discovery import build

        sheets_service = build("sheets", "v4", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        # Search for existing sheet in the folder
        query = f"name='{_SHEET_NAME}' and mimeType='application/vnd.google-apps.spreadsheet'"
        if settings.GOOGLE_DRIVE_FOLDER_ID:
            query += f" and '{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents"

        results = drive_service.files().list(q=query, fields="files(id,name)").execute()
        files = results.get("files", [])

        if files:
            sheet_id = files[0]["id"]
        else:
            # Create new sheet
            spreadsheet_body = {
                "properties": {"title": _SHEET_NAME},
                "sheets": [{"properties": {"title": "Research Log"}}],
            }
            sheet = sheets_service.spreadsheets().create(
                body=spreadsheet_body
            ).execute()
            sheet_id = sheet["spreadsheetId"]

            # Add header row
            headers = [
                [
                    "Timestamp", "Query", "Title", "Sources",
                    "Word Count", "Google Doc URL",
                    "Top Source", "Top Source Score",
                ]
            ]
            sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range="Research Log!A1",
                valueInputOption="RAW",
                body={"values": headers},
            ).execute()

            # Move to folder
            if settings.GOOGLE_DRIVE_FOLDER_ID:
                drive_service.files().update(
                    fileId=sheet_id,
                    addParents=settings.GOOGLE_DRIVE_FOLDER_ID,
                    removeParents="root",
                ).execute()

        # Prepare data row
        top_source = scored_sources[0] if scored_sources else {}
        row = [
            [
                metadata.get("date", ""),
                metadata.get("query", ""),
                metadata.get("title", ""),
                metadata.get("num_sources", 0),
                metadata.get("word_count", 0),
                doc_url or "N/A",
                top_source.get("url", ""),
                top_source.get("credibility_score", 0),
            ]
        ]

        sheets_service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Research Log!A1",
            valueInputOption="RAW",
            body={"values": row},
        ).execute()

        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        logger.info("google_sheet_updated", url=sheet_url)
        return sheet_url

    except Exception as exc:
        logger.error("google_sheet_error", error=str(exc))
        return None


# ── Local Storage ─────────────────────────────────────────────────────────────

def _save_local(
    title: str,
    report_markdown: str,
    metadata: dict[str, Any],
) -> str:
    """Save report and metadata as local files. Returns the report file path."""
    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Filename from title + timestamp
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in "_ " else "_" for c in title)[:50]
    safe_title = safe_title.strip().replace(" ", "_")
    base_name = f"{ts}_{safe_title}"

    # Save Markdown report
    md_path = data_dir / f"{base_name}.md"
    md_path.write_text(report_markdown, encoding="utf-8")

    # Save metadata as JSON
    meta_path = data_dir / f"{base_name}_meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    logger.info("local_save_complete", path=str(md_path))
    return str(md_path)


# ── Storage Agent ─────────────────────────────────────────────────────────────

class StorageAgent:
    """
    Agent 7 — Storage

    Saves the research report locally and optionally to Google Docs/Sheets.
    """

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Parameters
        ----------
        state : dict
            Full ResearchState.

        Returns
        -------
        dict with keys:
          - local_file_path : str
          - google_doc_url : Optional[str]
          - google_sheet_url : Optional[str]
        """
        report_markdown = state.get("report_markdown", "")
        metadata = state.get("report_metadata", {})
        scored_sources = state.get("scored_sources", [])
        title = metadata.get("title", "Research Report")

        logger.info("storage_agent_start", title=title)

        # 1. Always save locally
        local_path = _save_local(title, report_markdown, metadata)

        # 2. Attempt Google integration
        creds = _get_google_credentials()
        doc_url = None
        sheet_url = None

        if creds:
            doc_url = await _create_google_doc(title, report_markdown, creds)
            sheet_url = await _append_to_google_sheet(
                metadata, scored_sources, doc_url, creds
            )
        else:
            logger.info("google_integration_skipped_no_credentials")

        return {
            "local_file_path": local_path,
            "google_doc_url": doc_url,
            "google_sheet_url": sheet_url,
        }
