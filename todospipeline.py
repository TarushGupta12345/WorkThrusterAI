import os
import json
import time
import threading
from langchain_openai import ChatOpenAI
import emailGetter

os.environ["OPENAI_API_KEY"] = "YOUR_API_KEY_HERE"

llm = ChatOpenAI(model="gpt-4o-mini")

EMAILS_JSON = "emails.json"     # <-- NEW: where we store the generated TODOs
MESSAGES_JSON = "messages.json"  # existing file from emailGetter

def process_email_for_todos(email: dict, llm: ChatOpenAI) -> list:
    """
    Given an email dictionary, use a langchain prompt to generate a list of TODOs.
    This example assumes the email dictionary has keys 'subject' and 'body'.
    """
    email_text = f"Subject: {email.get('subject', '')}\nBody: {email.get('body', '')}"
    system_prompt = (
        "You are an assistant trained to create actionable TODOs based on email content. "
        "Generate a list of clear, concise, and actionable items based solely on the content below. "
        "Separate each TODO with exactly three forward slashes (///) with no extra commentary."
    )
    prompt = [
        ("system", system_prompt),
        ("human", f"Email content:\n{email_text}")
    ]
    response = llm.invoke(prompt).content
    todos = [t.strip() for t in response.split("///") if t.strip()]
    return todos

def poll_and_generate_todos(poll_interval: int = 60):
    """
    Continuously polls for new emails from messages.json (written by emailGetter).
    For each unprocessed email (identified by its 'id'), uses langchain to generate TODOs,
    then saves them in emails.json keyed by email ID.
    """

    print("Todo pipeline started, polling for new emails...")

    # 1) Load existing todos from emails.json (if it exists)
    if os.path.exists(EMAILS_JSON):
        try:
            with open(EMAILS_JSON, "r") as f:
                all_todos = json.load(f)
        except Exception as e:
            print("Error reading emails.json:", e)
            all_todos = {}
    else:
        all_todos = {}

    # 2) Create a set of email IDs we've already processed
    processed_ids = set(all_todos.keys())

    while True:
        print("\nReloading messages.json for new emails...")
        # 3) Load email threads from messages.json
        if os.path.exists(MESSAGES_JSON):
            try:
                with open(MESSAGES_JSON, "r") as f:
                    data = json.load(f)
            except Exception as e:
                print("Error reading messages.json:", e)
                data = {}
        else:
            data = {}

        # data should be a dict: {thread_id: [email_dict, email_dict, ...], ...}
        # 4) For each email, check if we've processed it. If not, generate todos and save them.
        for thread_id, emails in data.items():
            for email in emails:
                email_id = email.get("id")
                if email_id and email_id not in processed_ids:
                    print(f"\nGenerating TODOs for email {email_id}...")
                    todos = process_email_for_todos(email, llm)
                    print(f"Todos for email {email_id}:")
                    for idx, todo in enumerate(todos, start=1):
                        print(f"  {idx}. {todo}")

                    # 5) Store the generated todos in all_todos, keyed by email_id
                    all_todos[email_id] = todos
                    processed_ids.add(email_id)

        # 6) Write all_todos back to emails.json so we persist our results
        with open(EMAILS_JSON, "w") as f:
            json.dump(all_todos, f, indent=2)

        print("Waiting for new emails...")
        time.sleep(poll_interval)

def run_todo_pipeline():
    poll_and_generate_todos()

