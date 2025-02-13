import os
import json
import pickle
import base64
import time
from datetime import datetime
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
MESSAGES_FILE = 'messages.json'  # This file will store your grouped threads

def get_email_body(message: dict) -> str:
    def extract_body(payload: dict) -> str:
        if 'parts' in payload:
            for part in payload['parts']:
                result = extract_body(part)
                if result:
                    return result
        else:
            data = payload.get('body', {}).get('data')
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
                except Exception as e:
                    print(f"Error decoding body: {e}")
        return ""
    return extract_body(message.get('payload', {}))

def extract_header(headers: list, header_name: str) -> str:
    for header in headers:
        if header.get('name', '').lower() == header_name.lower():
            return header.get('value', '')
    return ""

def get_email_details(message: dict) -> dict:
    headers = message.get('payload', {}).get('headers', [])

    internal_date = message.get('internalDate')
    dt = datetime.fromtimestamp(int(internal_date) / 1000)
    formatted_date = dt.strftime('%Y-%m-%d %H:%M:%S')
    
    details = {
        'id': message.get('id'),
        'threadId': message.get('threadId'),
        'from': extract_header(headers, 'From'),
        'to': extract_header(headers, 'To'),
        'subject': extract_header(headers, 'Subject'),
        'body': get_email_body(message),
        'dateTime': formatted_date
    }
    return details

def group_emails_by_thread(emails: list) -> dict:
    """
    Groups emails by their threadId.
    
    Args:
        emails (list): A list of email dictionaries, each containing a 'threadId'.
    
    Returns:
        dict: A dictionary mapping each threadId to a list of emails in that thread.
    """
    threads = {}
    for email in emails:
        thread_id = email.get('threadId')
        if thread_id not in threads:
            threads[thread_id] = []
        threads[thread_id].append(email)
    
    # Optionally, sort emails within each thread by internalDate
    for thread in threads.values():
        thread.sort(key=lambda email: int(email.get('internalDate', 0)))
    
    return threads

def load_messages():
    """
    Loads grouped threads from MESSAGES_FILE (messages.json).
    Returns a dictionary where keys are thread IDs and values are lists of emails.
    """
    if os.path.exists(MESSAGES_FILE):
        try:
            data = json.load(open(MESSAGES_FILE, 'r'))
            if isinstance(data, dict):
                return data
            else:
                return {}
        except Exception as e:
            print("Error loading messages:", e)
            return {}
    return {}

def save_messages(grouped_threads: dict):
    """
    Saves grouped threads to MESSAGES_FILE (messages.json).
    
    ### SAVING HERE: The grouped threads are recorded to messages.json in this function.
    """
    with open(MESSAGES_FILE, 'w') as file:
        json.dump(grouped_threads, file, indent=2)
    # End of saving section.

def authenticate_gmail():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print("Error refreshing credentials, re-authenticating.")
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

def collect_messages_by_epoch(after_epoch: int, before_epoch: int, service) -> list:
    query = f'in:inbox after:{after_epoch} before:{before_epoch}'
    try:
        results = service.users().messages().list(userId='me', q=query).execute()
    except HttpError as error:
        print(f"An error occurred: {error}")
        return []
    messages = results.get('messages', [])
    new_messages = []
    for message in messages:
        try:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            details = get_email_details(msg)
            new_messages.append(details)
        except HttpError as error:
            print(f"Error fetching message {message['id']}: {error}")
    return new_messages

def fetch_initial_emails(after_epoch: int, before_epoch: int) -> dict:
    """
    Fetch initial emails from a specified time range if messages.json is empty.
    Returns grouped threads as a dictionary.
    """
    service = authenticate_gmail()
    print(f"Fetching initial emails from {after_epoch} to {before_epoch}...")
    new_messages = collect_messages_by_epoch(after_epoch, before_epoch, service)
    grouped_threads = group_emails_by_thread(new_messages)
    # Save initial grouped threads to messages.json
    save_messages(grouped_threads)  # <-- SAVING HERE: Initial fetch saved.
    return grouped_threads

def update_grouped_threads(existing_threads: dict, new_messages: list) -> dict:
    """
    Merge new_messages (list of emails) into existing_threads (grouped by threadId).
    Returns updated grouped threads.
    """
    # Group the new messages
    new_grouped = group_emails_by_thread(new_messages)
    for thread_id, messages in new_grouped.items():
        if thread_id in existing_threads:
            # Add only messages not already in the thread (check by id)
            existing_ids = {msg['id'] for msg in existing_threads[thread_id]}
            for msg in messages:
                if msg['id'] not in existing_ids:
                    existing_threads[thread_id].append(msg)
            # Optionally sort the thread again
            existing_threads[thread_id].sort(key=lambda email: int(email.get('internalDate', 0)), reverse=True)
        else:
            existing_threads[thread_id] = messages
    return existing_threads

def poll_emails(poll_interval=60):
    service = authenticate_gmail()
    grouped_threads = load_messages()  # Load grouped threads from messages.json
    
    # If there are no messages, do an initial fetch from a specified time range
    if not grouped_threads:
        # For example, fetch emails from one day ago to now (using epoch seconds)
        now = int(time.time())
        one_day_ago = now - 86400  # 86400 seconds in a day
        grouped_threads = fetch_initial_emails(one_day_ago, now)
    
    # Create a set of processed message IDs from the grouped threads
    processed_ids = {msg['id'] for thread in grouped_threads.values() for msg in thread}
    
    last_checked_epoch = int(time.time())
    
    while True:
        current_epoch = int(time.time())
        #print(f"Polling emails from {last_checked_epoch} to {current_epoch}...")
        new_messages = collect_messages_by_epoch(last_checked_epoch, current_epoch, service)
        
        # Filter out already processed messages
        fresh_messages = [msg for msg in new_messages if msg['id'] not in processed_ids]
        if fresh_messages:
            print(f"Found {len(fresh_messages)} new email(s).")
            processed_ids.update(msg['id'] for msg in fresh_messages)
            
            # Update grouped threads with fresh messages
            grouped_threads = update_grouped_threads(grouped_threads, fresh_messages)
            
            # Save updated grouped threads to messages.json
        save_messages(grouped_threads)  
        
        last_checked_epoch = current_epoch
        time.sleep(poll_interval)

if __name__ == "__main__":
    poll_emails(poll_interval=60)
