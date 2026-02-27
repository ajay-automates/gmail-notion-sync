<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=24,30,35&height=170&section=header&text=Gmail%20→%20Notion%20Sync&fontSize=48&fontAlignY=35&animation=twinkling&fontColor=ffffff&desc=Autonomous%20Email-to-Notion%20Pipeline%20%7C%20Zero%20Manual%20Effort&descAlignY=55&descSize=18" width="100%" />

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](.)
[![Gmail API](https://img.shields.io/badge/Gmail-API-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](.)
[![Notion API](https://img.shields.io/badge/Notion-API-000000?style=for-the-badge&logo=notion&logoColor=white)](.)
[![Railway](https://img.shields.io/badge/Railway-Deployed-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](.)

**Automatically sync Gmail emails to Notion databases. Set it and forget it.**

</div>

---

## Why This Exists

Manually copying email content into Notion for tracking, logging, or organizing is tedious. This script runs autonomously — it watches your Gmail inbox, extracts relevant emails, and creates structured Notion database entries automatically.

Deploy once on Railway. Never think about it again.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   Gmail-Notion Sync Pipeline                  │
│                                                               │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│   │   Gmail API   │───→│   Processor  │───→│  Notion API  │  │
│   │  (fetch new   │    │  (extract &  │    │  (create DB  │  │
│   │   emails)     │    │   transform) │    │   entries)   │  │
│   └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                               │
│   ┌──────────────────────────────────────────────────────┐   │
│   │  Runs continuously on Railway with Procfile worker   │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## How It Works

| Step | What Happens | Technology |
|------|-------------|------------|
| **1** | Connect to Gmail via OAuth/API credentials | Gmail API |
| **2** | Fetch new unprocessed emails on schedule | Python polling |
| **3** | Extract subject, sender, body, and metadata | Email parser |
| **4** | Transform into structured Notion properties | Data mapper |
| **5** | Create entries in your Notion database | Notion API |
| **6** | Mark emails as processed to avoid duplicates | State tracking |

---

## Quick Start

```bash
git clone https://github.com/ajay-automates/gmail-notion-sync.git
cd gmail-notion-sync
pip install -r requirements.txt

# Configure your credentials
export GMAIL_CREDENTIALS=your-credentials
export NOTION_API_KEY=your-notion-key
export NOTION_DATABASE_ID=your-db-id

python autonomous-gmail-notion-final.py
```

### Deploy on Railway

1. Connect this repo to Railway
2. Set environment variables for Gmail and Notion credentials
3. Railway auto-detects the Procfile worker
4. Runs continuously in the background

---

## Project Structure

```
gmail-notion-sync/
├── autonomous-gmail-notion-final.py   # Main sync pipeline
├── requirements.txt                    # Python dependencies
└── Procfile                           # Railway worker config
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single-file architecture** | Simple to deploy, easy to debug |
| **Procfile worker** | Runs continuously on Railway without cron complexity |
| **Duplicate prevention** | Tracks processed emails to avoid re-syncing |
| **Autonomous operation** | No manual triggers needed after deployment |

---

## Tech Stack

`Python` `Gmail API` `Notion API` `Railway` `OAuth2`

---

## Related Projects

| Project | Description |
|---------|-------------|
| [Social Media Automator](https://github.com/ajay-automates/social-media-automator) | Automated LinkedIn posting with scheduling |
| [Brain Dump Agent](https://github.com/ajay-automates/brain-dump-agent) | Turn scattered thoughts into action steps with Claude |
| [Multi-Orchestration System](https://github.com/ajay-automates/multi-orchestration-system) | Real-time multi-project monitoring |

---

<div align="center">

**Built by [Ajay Kumar Reddy Nelavetla](https://github.com/ajay-automates)** · February 2026

*Automate the boring stuff. Focus on what matters.*

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=24,30,35&height=100&section=footer" width="100%" />

</div>
