# import os
# import json
# import time
# import subprocess
# import logging
# from datetime import datetime, timedelta
# import pytz
# import portalocker

# # Setup logging
# log_file_path = os.path.join(os.getcwd(), "automation_log.txt")
# logging.basicConfig(
#     filename=log_file_path,
#     level=logging.DEBUG,
#     format="%(asctime)s - %(levelname)s - %(message)s"
# )
# logger = logging.getLogger()

# # Load config
# CONFIG_FILE = os.path.join(os.getcwd(), "config.json")
# try:
#     with open(CONFIG_FILE, "r") as f:
#         config = json.load(f)
# except Exception as e:
#     logger.error(f"Error loading config.json at {CONFIG_FILE}: {e}")
#     exit(1)

# def load_schedule():
#     """Load scheduled posts from schedule.json."""
#     schedule_file = os.path.join(os.getcwd(), config["SCHEDULE_FILE"])
#     try:
#         if os.path.exists(schedule_file):
#             with open(schedule_file, "r") as f:
#                 return json.load(f)
#         logger.warning(f"{schedule_file} not found.")
#         return []
#     except Exception as e:
#         logger.error(f"Error loading schedule.json at {schedule_file}: {e}")
#         return []

# def save_schedule(scheduled_posts):
#     """Save scheduled posts to schedule.json with file locking."""
#     schedule_file = os.path.join(os.getcwd(), config["SCHEDULE_FILE"])
#     try:
#         with open(schedule_file, "w") as f:
#             json.dump(scheduled_posts, f, indent=2)
#         logger.info(f"Saved {len(scheduled_posts)} scheduled posts to {schedule_file}")
#     except Exception as e:
#         logger.error(f"Error saving schedule.json at {schedule_file}: {e}")

# def is_post_locked(post_id):
#     """Check if a post is locked using a file-based lock."""
#     lock_file = os.path.join(os.getcwd(), f"lock_{post_id}.txt")
#     return os.path.exists(lock_file)

# def lock_post(post_id):
#     """Create a lock file for the post."""
#     lock_file = os.path.join(os.getcwd(), f"lock_{post_id}.txt")
#     try:
#         with portalocker.Lock(lock_file, 'w', timeout=1) as f:
#             return True
#     except portalocker.LockException:
#         logger.warning(f"Post {post_id} is already locked, skipping")
#         return False
#     except Exception as e:
#         logger.error(f"Error locking post {post_id}: {e}")
#         return False

# def unlock_post(post_id):
#     """Remove the lock file for the post."""
#     lock_file = os.path.join(os.getcwd(), f"lock_{post_id}.txt")
#     try:
#         if os.path.exists(lock_file):
#             os.remove(lock_file)
#             logger.info(f"Unlocked post {post_id}")
#     except Exception as e:
#         logger.error(f"Error unlocking post {post_id}: {e}")

# def run_batch_file(post_id):
#     """Run the corresponding batch file for a post with locking."""
#     batch_file = os.path.join(os.getcwd(), f"post_{post_id}.bat")
#     if os.path.exists(batch_file):
#         if lock_post(post_id):
#             try:
#                 logger.info(f"Executing batch file {batch_file} for Post_ID: {post_id}")
#                 result = subprocess.run(batch_file, shell=True, capture_output=True, text=True)
#                 if result.returncode == 0:
#                     logger.info(f"Successfully executed batch file for Post_ID: {post_id}")
#                     return True
#                 else:
#                     logger.error(f"Batch file failed for Post_ID {post_id}, Return code: {result.returncode}, Output: {result.stdout}, Error: {result.stderr}")
#                     return False
#             except subprocess.CalledProcessError as e:
#                 logger.error(f"Error executing batch file for Post_ID {post_id}: {e}")
#                 return False
#             except Exception as e:
#                 logger.error(f"Unexpected error running batch file for Post_ID {post_id}: {e}")
#                 return False
#             finally:
#                 unlock_post(post_id)
#         else:
#             logger.warning(f"Post {post_id} is already locked, skipping execution")
#             return False
#     else:
#         logger.error(f"Batch file {batch_file} not found for Post_ID: {post_id}")
#         return False

# def main():
#     """Main loop to monitor and execute scheduled posts."""
#     logger.info("Scheduler started, monitoring schedule.json...")
#     while True:
#         scheduled_posts = load_schedule()
#         now = datetime.now(pytz.UTC)
        
#         for post in scheduled_posts:
#             post_id = post["Post_ID"]
#             if not post.get("Posted") and not is_post_locked(post_id):
#                 scheduled_time = datetime.strptime(post["Scheduled_DateTime"], "%Y-%m-%d %H:%M").replace(tzinfo=pytz.UTC)
#                 time_window = timedelta(minutes=5)
#                 if now >= scheduled_time and now <= scheduled_time + time_window:
#                     logger.info(f"Scheduled time reached for Post_ID: {post_id} at {scheduled_time}")
#                     if run_batch_file(post_id):
#                         post["Posted"] = True
#                         save_schedule(scheduled_posts)
#                     else:
#                         logger.error(f"Failed to post Post_ID: {post_id} after execution")
        
#         time.sleep(60)  # Check every minute

# if __name__ == "__main__":
#     main()



import os
import json
import time
import subprocess
import logging
from datetime import datetime, timedelta
import pytz
import portalocker

# Setup logging
log_file_path = os.path.join(os.getcwd(), "automation_log.txt")
logging.basicConfig(
    filename=log_file_path,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()

# Load config
CONFIG_FILE = os.path.join(os.getcwd(), "config.json")
try:
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
except Exception as e:
    logger.error(f"Error loading config.json at {CONFIG_FILE}: {e}")
    exit(1)

def load_schedule():
    """Load scheduled posts from schedule.json."""
    schedule_file = os.path.join(os.getcwd(), config["SCHEDULE_FILE"])
    try:
        if os.path.exists(schedule_file):
            with open(schedule_file, "r") as f:
                return json.load(f)
        logger.warning(f"{schedule_file} not found.")
        return []
    except Exception as e:
        logger.error(f"Error loading schedule.json at {schedule_file}: {e}")
        return []

def save_schedule(scheduled_posts):
    """Save scheduled posts to schedule.json with file locking."""
    schedule_file = os.path.join(os.getcwd(), config["SCHEDULE_FILE"])
    try:
        with open(schedule_file, "w") as f:
            json.dump(scheduled_posts, f, indent=2)
        logger.info(f"Saved {len(scheduled_posts)} scheduled posts to {schedule_file}")
    except Exception as e:
        logger.error(f"Error saving schedule.json at {schedule_file}: {e}")

def is_post_locked(post_id):
    """Check if a post is locked using a file-based lock."""
    lock_file = os.path.join(os.getcwd(), f"lock_{post_id}.txt")
    return os.path.exists(lock_file)

def lock_post(post_id):
    """Create a lock file for the post."""
    lock_file = os.path.join(os.getcwd(), f"lock_{post_id}.txt")
    try:
        with portalocker.Lock(lock_file, 'w', timeout=1) as f:
            return True
    except portalocker.LockException:
        logger.warning(f"Post {post_id} is already locked, skipping")
        return False
    except Exception as e:
        logger.error(f"Error locking post {post_id}: {e}")
        return False

def unlock_post(post_id):
    """Remove the lock file for the post."""
    lock_file = os.path.join(os.getcwd(), f"lock_{post_id}.txt")
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
            logger.info(f"Unlocked post {post_id}")
    except Exception as e:
        logger.error(f"Error unlocking post {post_id}: {e}")

def run_batch_file(post_id):
    """Run the corresponding batch file for a post with locking."""
    batch_file = os.path.join(os.getcwd(), f"post_{post_id}.bat")
    if os.path.exists(batch_file):
        if lock_post(post_id):
            try:
                logger.info(f"Executing batch file {batch_file} for Post_ID: {post_id}")
                result = subprocess.run(batch_file, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"Successfully executed batch file for Post_ID: {post_id}")
                    return True
                else:
                    logger.error(f"Batch file failed for Post_ID {post_id}, Return code: {result.returncode}, Output: {result.stdout}, Error: {result.stderr}")
                    return False
            except subprocess.CalledProcessError as e:
                logger.error(f"Error executing batch file for Post_ID {post_id}: {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error running batch file for Post_ID {post_id}: {e}")
                return False
            finally:
                unlock_post(post_id)
        else:
            logger.warning(f"Post {post_id} is already locked, skipping execution")
            return False
    else:
        logger.error(f"Batch file {batch_file} not found for Post_ID: {post_id}")
        return False

def main():
    """Main loop to monitor and execute scheduled posts at exact times."""
    logger.info("Scheduler started, monitoring schedule.json...")
    while True:
        scheduled_posts = load_schedule()
        now = datetime.now(pytz.UTC)
        
        for post in scheduled_posts:
            post_id = post["Post_ID"]
            if not post.get("Posted") and not is_post_locked(post_id):
                scheduled_time = datetime.strptime(post["Scheduled_DateTime"], "%Y-%m-%d %H:%M").replace(tzinfo=pytz.UTC)
                if now >= scheduled_time and now < scheduled_time + timedelta(minutes=1):  # Trigger within 1-minute window
                    logger.info(f"Scheduled time reached for Post_ID: {post_id} at {scheduled_time}")
                    if run_batch_file(post_id):
                        post["Posted"] = True
                        save_schedule(scheduled_posts)
                    else:
                        logger.error(f"Failed to post Post_ID: {post_id} after execution")
                elif now < scheduled_time:
                    # Calculate time until next check (e.g., check 5 minutes before scheduled time)
                    time_to_wait = (scheduled_time - now).total_seconds() - 300  # 5 minutes early
                    if time_to_wait > 0:
                        time.sleep(min(time_to_wait, 60))  # Wait but cap at 60 seconds
                    else:
                        time.sleep(60)  # Default check interval
        
        time.sleep(60)  # Default check every minute if no future posts are close

if __name__ == "__main__":
    main()