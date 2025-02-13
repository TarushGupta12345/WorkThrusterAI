import threading
import time
import emailGetter
import todospipeline

def run_email_getter():
    emailGetter.poll_emails(poll_interval=60)

def run_todo_pipeline():
    todospipeline.run_todo_pipeline()

if __name__ == '__main__':
    email_thread = threading.Thread(target=run_email_getter, daemon=True)
    pipeline_thread = threading.Thread(target=run_todo_pipeline, daemon=True)

    email_thread.start()
    pipeline_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutdown signal received. Exiting...")


