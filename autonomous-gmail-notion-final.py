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
import schedule
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional

# Google API Libraries
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- CONFIGURATION (Load from environment variables) ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# Scopes for Gmail API
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Search query to find job application, rejection, and interview emails
GMAIL_SEARCH_QUERY = 'subject:(application OR "thank you for applying" OR "received your application" OR "applying to" OR "unfortunate" OR "rejected" OR "moving forward" OR "interview" OR "interviews" OR "next steps" OR "submission" OR "applied" OR "interest" OR "registration" OR "acknowledgment" OR "receipt") -subject:("Security code" OR "Verification code" OR "Your code" OR "one-time password" OR "OTP")'

class JobSyncAutomation:
    def __init__(self):
        self.notion_headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": "2025-09-03"
        }
        self.creds = self.get_gmail_creds()
        self.gmail_service = build('gmail', 'v1', credentials=self.creds)
        
        # Get user email to create direct Gmail links
        profile = self.gmail_service.users().getProfile(userId='me').execute()
        self.user_email = profile.get('emailAddress')
        print(f"📧 Authenticated as: {self.user_email}")
        
        self._initialize_notion_source()

    def _initialize_notion_source(self):
        """Verify the Notion database is accessible"""
        try:
            url = f"https://api.notion.com/v1/databases/{DATABASE_ID}"
            res = requests.get(url, headers=self.notion_headers, timeout=10)
            if res.status_code == 200:
                print(f"✅ Notion database connected.")
            else:
                print(f"⚠️ Notion database check failed ({res.status_code}): {res.text[:500]}")
            sys.stdout.flush()
        except Exception as e:
            print(f"⚠️ Notion connectivity check exception: {str(e)}")

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
            company = "Unknown Company"
            title = subject

            # Smart parsing logic
            if " at " in subject:
                company = subject.split(" at ")[-1].strip()
            elif " to " in subject:
                company = subject.split(" to ")[-1].strip()
            elif " in " in subject:
                company = subject.split(" in ")[-1].strip()
            elif " - " in sender:
                company = sender.split(" - ")[-1].strip()
            else:
                # Try to extract company from sender email domain
                if "<" in sender:
                    email_domain = sender.split("<")[-1].replace(">", "").split("@")[-1].lower()
                    # Filter out common generic domains
                    generic_domains = ["gmail.com", "outlook.com", "yahoo.com", "icloud.com", "me.com", "mail.com", "notifications.greenhouse.io", "ashbyhq.com", "lever.co"]
                    if email_domain not in generic_domains and "." in email_domain:
                        company = email_domain.split(".")[0].capitalize()
                    else:
                        company = "Referral/Direct"
            
            # Clean up company name (remove punctuation at end)
            company = company.rstrip("!.,")

            # Date formatting for Notion
            received_date = datetime.now().isoformat()
            if date_raw:
                # Remove timezone name in parentheses, e.g. "(UTC)"
                clean_date = date_raw.split(' (')[0].strip()
                for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S"]:
                    try:
                        parsed_date = datetime.strptime(clean_date, fmt)
                        received_date = parsed_date.isoformat()
                        break
                    except ValueError:
                        continue

            snippet = message.get('snippet', '').lower()
            # Use the specific user email in the link to ensure it opens in the correct account
            link = f"https://mail.google.com/mail/u/{self.user_email}/#inbox/{msg_id}"

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
        """Add job to Notion or update existing entry (deduplicates by Subject)"""

        query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
            
        query_payload = {
            "filter": {
                "property": "Subject",
                "rich_text": {"equals": job['subject']}
            }
        }
        
        try:
            check_res = requests.post(query_url, headers=self.notion_headers, json=query_payload, timeout=10)
            if check_res.status_code != 200:
                print(f"  ❌ Notion Query Error ({check_res.status_code}): {check_res.text}")
                # Query failed - fall through to CREATE to avoid silently dropping the email.
                # This may rarely cause a duplicate, but is better than losing data.
                results = []
            else:
                results = check_res.json().get('results', [])
            
            # Prepare properties
            properties = {
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

            if len(results) > 0:
                # UPDATE existing page
                page_id = results[0]['id']
                current_props = results[0].get('properties', {})
                current_status = current_props.get('Status', {}).get('select', {}).get('name')
                current_link = current_props.get('Email Link', {}).get('url', '')
                
                # Update if status changed OR if the link is in the old "/u/0/" format
                link_outdated = "/u/0/" in current_link and self.user_email not in current_link
                
                if current_status != job['status'] or link_outdated:
                    update_url = f"https://api.notion.com/v1/pages/{page_id}"
                    update_payload = {
                        "properties": {
                            "Status": {"select": {"name": job['status']}},
                            "Next Action": {"rich_text": [{"text": {"content": job['next_action']}}]},
                            "Email Preview": {"rich_text": [{"text": {"content": job['email_preview'][:2000]}}]},
                            "Email Link": {"url": job['email_link']}
                        }
                    }
                    patch_res = requests.patch(update_url, headers=self.notion_headers, json=update_payload, timeout=10)
                    if patch_res.status_code != 200:
                        print(f"  ❌ Notion Update Error ({patch_res.status_code}): {patch_res.text}")
                    elif link_outdated:
                        print(f"  🔗 Fixed Link: {job['company']}")
                    else:
                        print(f"  🔄 Updated Status: {job['company']}")
                return False

            # CREATE new page
            url = "https://api.notion.com/v1/pages"
            payload = {
                "parent": {"database_id": DATABASE_ID},
                "properties": properties
            }

            response = requests.post(url, headers=self.notion_headers, json=payload, timeout=10)
            if response.status_code == 200:
                return True
            else:
                print(f"  ❌ Notion Create Error ({response.status_code}): {response.text}")
                return False
            
        except Exception as e:
            print(f"  ❌ Exception for {job['company']}: {str(e)}")
            return False

    def sync_one_by_one(self, count=2000):
        """Fetch and sync emails one by one to save memory and handle large batches"""
        print(f"\n⏱️  Sync started: {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            messages = []
            next_page_token = None
            
            print(f"🔍 Searching Gmail for up to {count} matching emails...")
            
            while len(messages) < count:
                max_results = min(count - len(messages), 500)
                results = self.gmail_service.users().messages().list(
                    userId='me', 
                    q=GMAIL_SEARCH_QUERY, 
                    maxResults=max_results,
                    pageToken=next_page_token
                ).execute()
                
                batch = results.get('messages', [])
                if not batch:
                    break
                    
                messages.extend(batch)
                next_page_token = results.get('nextPageToken')
                if not next_page_token:
                    break

            print(f"📝 Found {len(messages)} potential emails. Starting one-by-one sync...")
            
            added_count = 0
            for i, msg in enumerate(messages):
                if i % 25 == 0 and i > 0:
                    print(f"  ...processed {i}/{len(messages)} emails")
                    sys.stdout.flush()
                
                # Fetch details for just ONE message
                job = self.get_message_details(msg['id'])
                if job:
                    # Sync to Notion immediately
                    if self.add_to_notion(job):
                        print(f"✅ Synced: {job['company']} - {job['title']}")
                        added_count += 1
                    time.sleep(0.5)  # Rate limit every processed email, not just new ones

                # The 'job' variable is overwritten in next iteration, allowing GC
            
            if added_count == 0:
                print("  (No new job emails found)")
            else:
                print(f"✨ Successfully added {added_count} new entries.")

        except Exception as e:
            print(f"❌ Critical Sync Error: {str(e)}")

    def sync_cycle(self, count=2000):
        """Wrapper for the new one-by-one sync logic"""
        self.sync_one_by_one(count=count)

def main():
    print("\n" + "="*80)
    print("🚀 GMAIL → NOTION JOB TRACKER ACTIVE")
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    try:
        automator = JobSyncAutomation()
        
        # Initial Mega sync (fetch up to 2000 historical emails)
        print("📥 Running initial MEGA sync for widespread historical data...")
        automator.sync_cycle(count=2000)

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
