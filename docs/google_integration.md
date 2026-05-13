# Google Integration Setup Guide

This guide walks through enabling the Google Docs and Google Sheets integration
so the Storage Agent can automatically save reports to your Google Drive.

---

## Prerequisites

- A Google account
- A Google Cloud project (free tier is sufficient)

---

## Step 1: Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Click the project dropdown at the top → **New Project**.
3. Name it (e.g., `research-agent`) → **Create**.

---

## Step 2: Enable Required APIs

In your new project:

1. Navigate to **APIs & Services → Library**.
2. Search for and enable each of:
   - **Google Docs API**
   - **Google Sheets API**
   - **Google Drive API**

---

## Step 3: Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services → Credentials**.
2. Click **Create Credentials → OAuth 2.0 Client ID**.
3. If prompted to configure the OAuth consent screen:
   - User Type: **External**
   - App name: `Research Agent`
   - Add your email as a test user
   - Scopes: add `.../auth/documents`, `.../auth/spreadsheets`, `.../auth/drive.file`
4. Application type: **Desktop App**
5. Click **Create** → **Download JSON**.
6. Rename the downloaded file to `credentials.json`.
7. Place it in the **project root** (same level as `.env`).

---

## Step 4: First-Run Authentication

On the first pipeline run with Google integration enabled:

```bash
python -c "from agents.storage_agent import _get_google_credentials; _get_google_credentials()"
```

A browser window opens asking you to sign in to Google and grant the requested permissions.
After approval, `token.json` is saved in the project root. Future runs are fully automatic.

> **Note:** If using Docker, you'll need to run this step on the host machine first,
> then mount the generated `token.json` into the container.

---

## Step 5: Configure Drive Folder (Optional)

To save reports into a specific Google Drive folder instead of the root:

1. Open Google Drive in your browser.
2. Navigate to (or create) the target folder.
3. The folder ID is the last part of the URL:
   ```
   https://drive.google.com/drive/folders/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                           This is your GOOGLE_DRIVE_FOLDER_ID
   ```
4. Add to `.env`:
   ```
   GOOGLE_DRIVE_FOLDER_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
   ```

---

## What Gets Saved

### Google Docs
- One document per research run.
- Named: `{Report Title}` (e.g., `Latest AI Tools for Healthcare Diagnosis`).
- Content: full Markdown report inserted as plain text.
- Stored in the configured Drive folder (or root).

### Google Sheets
- A single spreadsheet named **Research Agent Log** is created on first run.
- Each research run appends one row with:

| Column | Content |
|---|---|
| Timestamp | Date of the research run |
| Query | Original research query |
| Title | Report title |
| Sources | Number of sources analysed |
| Word Count | Report word count |
| Google Doc URL | Link to the generated Doc |
| Top Source | Highest-credibility URL used |
| Top Source Score | Credibility score (0–1) |

---

## Troubleshooting

**`credentials.json` not found**
→ Ensure the file is in the project root, not a subdirectory.

**`invalid_grant` error**
→ Delete `token.json` and re-run the first-run authentication step.

**`Access Not Configured`**
→ The relevant API (Docs/Sheets/Drive) is not enabled in your Cloud project. Re-check Step 2.

**Running in Docker and auth doesn't work**
→ Run authentication on the host, then bind-mount `token.json`:
```yaml
volumes:
  - ./token.json:/app/token.json
```
