#!/usr/bin/env python3
"""
AUTONOMOUS GMAIL → NOTION SYNC
Real-time job email tracking for 500+ applications
Syncs job application emails from Gmail to Notion automatically.
"""

import os
import sys
import time
import json
import base64
import schedule
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Google API Libraries
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- CONFIGURATION (Load from environment variables) ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# Scopes for Gmail API
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Search query to find job application, rejection, and interview emails
GMAIL_SEARCH_QUERY = 'subject:(application OR "thank you for applying" OR "received your application" OR "applying to" OR "unfortunate" OR "rejected" OR "moving forward" OR "interview" OR "interviews" OR "next steps") -subject:("Security code" OR "Verification code" OR "Your code" OR "one-time password" OR "OTP")'

class JobSyncAutomation:
    def __init__(self):
        self.notion_headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        self.creds = self.get_gmail_creds()
        self.gmail_service = build('gmail', 'v1', credentials=self.creds)

    def get_gmail_creds(self):
        """Manages Gmail OAuth2 credentials with Env Var support for Railway"""
        creds = None
        
        # 1. Try loading Token from Environment Variable (Railway)
        env_token = os.getenv("GMAIL_TOKEN")
        if env_token:
            print("🔑 Loading Gmail Token from environment variable...")
            token_data = json.loads(env_token)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        # 2. Fallback to local token.json
        elif os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # 3. Try loading Credentials from Environment Variable
                env_creds = os.getenv("GMAIL_CREDENTIALS")
                if env_creds:
                    print("🔑 Loading Gmail Credentials from environment variable...")
                    creds_data = json.loads(env_creds)
                    flow = InstalledAppFlow.from_client_config(creds_data, SCOPES)
                    creds = flow.run_local_server(port=0)
                # 4. Fallback to local credentials.json
                elif os.path.exists('credentials.json'):
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                else:
                    print("\n❌ ERROR: No Gmail credentials found (env or file)!")
                    exit(1)
            
            # Save the credentials for next time (locally)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        
        return creds

    def fetch_emails(self, count=500) -> List[Dict]:
        """Fetch emails matching the search query, up to a specific count"""
        try:
            results = self.gmail_service.users().messages().list(
                userId='me', q=GMAIL_SEARCH_QUERY, maxResults=min(count, 500)
            ).execute()
            
            messages = results.get('messages', [])
            job_data = []

            print(f"🔍 Found {len(messages)} matching emails in Gmail. Starting extraction...")

            for i, msg in enumerate(messages):
                if i % 10 == 0 and i > 0:
                    print(f"  ...processed {i} emails")
                
                details = self.get_message_details(msg['id'])
                if details:
                    job_data.append(details)
            
            return job_data

        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

    def get_message_details(self, msg_id: str) -> Optional[Dict]:
        """Extract details from a specific Gmail message"""
        try:
            message = self.gmail_service.users().messages().get(
                userId='me', id=msg_id, format='full'
            ).execute()

            headers = message.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown Sender")
            date_raw = next((h['value'] for h in headers if h['name'].lower() == 'date'), None)
            
            # Basic parsing of company and title from subject
            # (Very simple logic, can be improved with AI/regex)
            company = "Unknown Company"
            title = subject
            
            if " at " in subject:
                parts = subject.split(" at ")
                company = parts[-1].strip()
            elif " - " in sender:
                company = sender.split(" - ")[-1].strip()
            else:
                # Try to extract company from sender email domain
                if "<" in sender:
                    email_domain = sender.split("<")[-1].replace(">", "").split("@")[-1].lower()
                    # Filter out common generic domains
                    generic_domains = ["gmail.com", "outlook.com", "yahoo.com", "icloud.com", "me.com", "mail.com"]
                    if email_domain not in generic_domains:
                        company = email_domain.split(".")[0].capitalize()
                    else:
                        company = "Referral/Direct"

            # Date formatting for Notion
            try:
                # Simple fallback date if parsing fails
                received_date = datetime.now().isoformat()
                if date_raw:
                    # Clean the date string (remove timezone names in parentheses)
                    clean_date = date_raw.split(' (')[0]
                    # Fri, 07 Feb 2025 15:30:10 +0000
                    parsed_date = datetime.strptime(clean_date[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                    received_date = parsed_date.isoformat()
            except Exception:
                received_date = datetime.now().isoformat()

            snippet = message.get('snippet', '').lower()
            link = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}"

            # Advanced Status Detection
            status = "Applied"
            next_action = "Check status"
            
            # Rejection detection
            rejection_keywords = ["unfortunate", "not moving forward", "rejected", "another candidate", "position filled", "not be moving", "thank you for your interest but"]
            if any(kw in subject.lower() or kw in snippet for kw in rejection_keywords):
                status = "Rejected"
                next_action = "Archived"
            
            # Interview discovery
            interview_keywords = ["interview", "interviews", "meet with", "next steps", "chat with", "scheduling", "availability"]
            if any(kw in subject.lower() or kw in snippet for kw in interview_keywords) and status != "Rejected":
                status = "Interview Round 1"
                next_action = "Schedule/Prepare for interview"

            return {
                "title": title,
                "company": company,
                "email_from": sender,
                "subject": subject,
                "date_received": received_date,
                "email_preview": snippet,
                "email_link": link,
                "status": status,
                "next_action": next_action,
                "action_date": (datetime.now() + timedelta(days=7)).isoformat()
            }

        except Exception as e:
            print(f"Error parsing message {msg_id}: {e}")
            return None

    def add_to_notion(self, job: Dict) -> bool:
        """Add job to Notion database if it doesn't already exist"""
        
        # Check for duplicates (Search by Subject)
        query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
        query_payload = {
            "filter": {
                "property": "Subject",
                "rich_text": {"equals": job['subject']}
            }
        }
        
        check_res = requests.post(query_url, headers=self.notion_headers, json=query_payload)
        if check_res.status_code == 200 and len(check_res.json().get('results', [])) > 0:
            # Skip if already exists
            return False

        # Create new page
        url = "https://api.notion.com/v1/pages"
        payload = {
            "parent": {"database_id": DATABASE_ID},
            "properties": {
                "Title": {"title": [{"text": {"content": job['title']}}]},
                "Company": {"rich_text": [{"text": {"content": job['company']}}]},
                "Email From": {"rich_text": [{"text": {"content": job['email_from']}}]},
                "Subject": {"rich_text": [{"text": {"content": job['subject']}}]},
                "Date Received": {"date": {"start": job['date_received']}},
                "Email Preview": {"rich_text": [{"text": {"content": job['email_preview'][:2000]}}]},
                "Email Link": {"url": job['email_link']},
                "Status": {"select": {"name": job['status']}},
                "Next Action": {"rich_text": [{"text": {"content": job['next_action']}}]},
                "Action Date": {"date": {"start": job['action_date']}}
            }
        }

        try:
            response = requests.post(url, headers=self.notion_headers, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Error adding {job['company']}: {str(e)}")
            return False

    def sync_cycle(self, count=500):
        """The main sync logic to be run on schedule"""
        print(f"\n⏱️  Sync started: {datetime.now().strftime('%H:%M:%S')}")
        jobs = self.fetch_emails(count=count)
        
        added_count = 0
        for job in jobs:
            if self.add_to_notion(job):
                print(f"✅ Synced: {job['company']} - {job['title']}")
                added_count += 1
                time.sleep(0.5) # Rate limiting for Notion API
        
        if added_count == 0:
            print("  (No new job emails found)")
        else:
            print(f"✨ Successfully added {added_count} new entries.")

def main():
    print("\n" + "="*80)
    print("🚀 GMAIL → NOTION JOB TRACKER ACTIVE")
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    try:
        automator = JobSyncAutomation()
        
        # Initial deep sync (fetch up to 500 historical emails)
        print("📥 Running initial deep sync for historical data...")
        automator.sync_cycle(count=500)

        # Subsequent periodic syncs (fetch last 50 only for speed)
        schedule.every(2).minutes.do(automator.sync_cycle, count=50)

        print("\n📋 Monitoring Active:")
        print("  - Searching Gmail for job application keywords")
        print("  - Syncing new unique emails to Notion")
        print("  - Running historical recovery + 2min live checks\n")

        while True:
            schedule.run_pending()
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n👋 Automation stopped by user.")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        sys.stdout.flush()
        # Sleep before exiting to avoid aggressive restart loops
        time.sleep(10)
        sys.exit(1)

if __name__ == "__main__":
    # Ensure logs are flushed immediately
    sys.stdout.reconfigure(line_buffering=True)
    main()
