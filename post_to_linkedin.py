# linkedin posting with scheduling

# import sys
# import os
# import json
# import logging
# import time
# import requests
# from requests.adapters import HTTPAdapter
# from urllib3.util.retry import Retry
# import pandas as pd
# from io import BytesIO
# from datetime import datetime, timedelta
# import shutil
# import pytz

# # Setup logging with explicit path
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
#     sys.exit(1)

# # Check required modules
# try:
#     import requests
#     import pandas
# except ImportError as e:
#     logger.error(f"Missing required module: {e}")
#     sys.exit(1)

# # Initialize requests session with retries
# session = requests.Session()
# retries = Retry(
#     total=config.get("LINKEDIN_RETRIES", 3),
#     backoff_factor=config.get("LINKEDIN_RETRY_DELAY", 2),
#     status_forcelist=[429, 500, 502, 503, 504],
#     allowed_methods=["GET", "POST"]
# )
# session.mount("https://", HTTPAdapter(max_retries=retries))

# def get_linkedin_user_id(access_token):
#     """Fetch LinkedIn user ID using the /rest/me API."""
#     if not access_token:
#         logger.error("LinkedIn access token is empty.")
#         return None
#     url = "https://api.linkedin.com/rest/me"
#     headers = {
#         "Authorization": f"Bearer {access_token}",
#         "Content-Type": "application/json",
#         "X-Restli-Protocol-Version": "2.0.0",
#         "LinkedIn-Version": "202306"
#     }
#     logger.debug(f"Sending GET request to {url}, Token (masked): {access_token[:10]}...")
#     try:
#         response = session.get(url, headers=headers, timeout=10)
#         response.raise_for_status()
#         user_data = response.json()
#         user_id = user_data.get("id")
#         if not user_id:
#             logger.error("No 'id' found in LinkedIn /rest/me response.")
#             return None
#         logger.info(f"Fetched LinkedIn user ID: {user_id}")
#         return user_id
#     except requests.exceptions.HTTPError as e:
#         logger.error(f"HTTP error fetching LinkedIn user ID: {e}, Status: {response.status_code}, Response: {response.text}")
#         return None
#     except Exception as e:
#         logger.error(f"Error fetching LinkedIn user ID: {e}")
#         return None

# def post_to_linkedin(post_text, access_token, user_id):
#     """Post content to LinkedIn using the /rest/posts API."""
#     if not user_id:
#         logger.error("Cannot post to LinkedIn: Invalid user ID.")
#         return False
#     url = "https://api.linkedin.com/rest/posts"
#     headers = {
#         "Authorization": f"Bearer {access_token}",
#         "Content-Type": "application/json",
#         "X-Restli-Protocol-Version": "2.0.0",
#         "LinkedIn-Version": "202306"
#     }
#     payload = {
#         "author": f"urn:li:person:{user_id}",
#         "commentary": post_text,
#         "visibility": "PUBLIC",
#         "distribution": {
#             "feedDistribution": "MAIN_FEED",
#             "targetEntities": [],
#             "thirdPartyDistributionChannels": []
#         },
#         "lifecycleState": "PUBLISHED",
#         "isReshareDisabledByAuthor": False
#     }
#     logger.debug(f"Sending POST request to {url}, payload: {json.dumps(payload, indent=2)}, Token (masked): {access_token[:10]}...")
#     try:
#         response = session.post(url, headers=headers, json=payload, timeout=10)
#         response.raise_for_status()
#         logger.info(f"Successfully posted to LinkedIn: {post_text[:50]}...")
#         return True
#     except requests.exceptions.HTTPError as e:
#         logger.error(f"HTTP error posting to LinkedIn: {e}, Status: {response.status_code}, Response: {response.text}")
#         if response.status_code == 429:
#             logger.warning("Rate limit exceeded. Waiting before retry.")
#             time.sleep(60)  # Wait 1 minute before retrying
#             response = session.post(url, headers=headers, json=payload, timeout=10)
#             response.raise_for_status()
#             logger.info(f"Retried and successfully posted: {post_text[:50]}...")
#             return True
#         return False
#     except Exception as e:
#         logger.error(f"Error posting to LinkedIn: {e}")
#         return False

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
#     """Save scheduled posts to schedule.json."""
#     schedule_file = os.path.join(os.getcwd(), config["SCHEDULE_FILE"])
#     try:
#         with open(schedule_file, "w") as f:
#             json.dump(scheduled_posts, f, indent=2)
#         logger.info(f"Saved {len(scheduled_posts)} scheduled posts to {schedule_file}")
#     except Exception as e:
#         logger.error(f"Error saving schedule.json at {schedule_file}: {e}")

# def main():
#     if len(sys.argv) != 2:
#         logger.error("Usage: python post_to_linkedin.py <Post_ID>")
#         sys.exit(1)
    
#     post_id = sys.argv[1]
#     logger.info(f"Attempting to post Post_ID: {post_id} via Task Scheduler")
    
#     # Log environment details
#     logger.debug(f"Current working directory: {os.getcwd()}")
#     logger.debug(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
#     logger.debug(f"Current user: {os.getlogin()}")
#     logger.debug(f"Command line args: {sys.argv}")
#     logger.debug(f"Python executable: {sys.executable}")
#     logger.debug(f"Script path: {os.path.abspath(__file__)}")
    
#     # Verify Python environment
#     python_exe = config.get("PYTHON_EXECUTABLE", "python")
#     if not shutil.which(python_exe):
#         logger.error(f"Python executable not found: {python_exe}")
#         sys.exit(1)
    
#     # Load schedule
#     scheduled_posts = load_schedule()
#     post = next((p for p in scheduled_posts if p["Post_ID"] == post_id), None)
#     if not post:
#         logger.error(f"Post_ID {post_id} not found in schedule.json")
#         sys.exit(1)
    
#     # Check if already posted or time has passed
#     now = datetime.now(pytz.UTC)
#     scheduled_time = datetime.strptime(post["Scheduled_DateTime"], "%Y-%m-%d %H:%M").replace(tzinfo=pytz.UTC)
#     if post.get("Posted") or now > scheduled_time + timedelta(minutes=5):
#         logger.info(f"Post_ID {post_id} already posted or past scheduled time: {post['Scheduled_DateTime']} UTC")
#         sys.exit(0)
    
#     # Post to LinkedIn
#     access_token = config.get("LINKEDIN_ACCESS_TOKEN")
#     if not access_token:
#         logger.error("LinkedIn access token missing in config.json")
#         sys.exit(1)
    
#     user_id = get_linkedin_user_id(access_token)
#     if user_id:
#         logger.debug(f"Posting content: {post['Output_Text'][:50]}...")
#         success = post_to_linkedin(post["Output_Text"], access_token, user_id)
#         if success:
#             post["Posted"] = True
#             save_schedule(scheduled_posts)
#             try:
#                 output_file = os.path.join(os.getcwd(), "output.xlsx")
#                 if os.path.exists(output_file):
#                     df = pd.read_excel(output_file)
#                     df.loc[df['Post_ID'] == post_id, 'Posted'] = True
#                     output_buffer = BytesIO()
#                     df.to_excel(output_buffer, index=False)
#                     with open(output_file, "wb") as f:
#                         f.write(output_buffer.getvalue())
#                     logger.info(f"Updated output.xlsx for Post_ID {post_id}")
#                 else:
#                     logger.error(f"output.xlsx not found at {output_file}")
#             except Exception as e:
#                 logger.error(f"Error updating output.xlsx for Post_ID {post_id}: {e}")
#             logger.info(f"Successfully posted Post_ID {post_id}")
#         else:
#             logger.error(f"Failed to post Post_ID {post_id} after retries")
#             sys.exit(1)
#     else:
#         logger.error(f"Failed to fetch user ID for Post_ID {post_id}")
#         sys.exit(1)

# if __name__ == "__main__":
#     main()



import sys
import os
import json
import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from io import BytesIO
from datetime import datetime
import pytz

# Set working directory to script location
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Setup logging with explicit path
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
    sys.exit(1)

# Check required modules
try:
    import requests
    import pandas
except ImportError as e:
    logger.error(f"Missing required module: {e}")
    sys.exit(1)

# Initialize requests session with retries
session = requests.Session()
retries = Retry(
    total=config.get("LINKEDIN_RETRIES", 3),
    backoff_factor=config.get("LINKEDIN_RETRY_DELAY", 2),
    status_forcelist=[401, 403, 429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"]
)
session.mount("https://", HTTPAdapter(max_retries=retries))

def get_linkedin_user_id(access_token):
    """Fetch LinkedIn user ID using the /rest/me API."""
    if not access_token:
        logger.error("LinkedIn access token is empty.")
        return None
    url = "https://api.linkedin.com/rest/me"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202306"
    }
    logger.debug(f"Sending GET request to {url}, Token (masked): {access_token[:10]}...")
    try:
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        user_data = response.json()
        user_id = user_data.get("id")
        if not user_id:
            logger.error("No 'id' found in LinkedIn /rest/me response.")
            return None
        logger.info(f"Fetched LinkedIn user ID: {user_id}")
        return user_id
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error fetching LinkedIn user ID: {e}, Status: {response.status_code}, Response: {response.text}")
        return None
    except Exception as e:
        logger.error(f"Error fetching LinkedIn user ID: {e}")
        return None

def register_image_upload(access_token, user_id):
    """Register an image upload with LinkedIn API."""
    url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202306"
    }
    payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": f"urn:li:person:{user_id}",
            "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}]
        }
    }
    logger.debug(f"Registering image upload, payload: {json.dumps(payload, indent=2)}...")
    try:
        response = session.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        upload_url = data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset_urn = data["value"]["asset"]
        media_artifact = data["value"]["mediaArtifact"]
        logger.info(f"Registered image upload, uploadUrl: {upload_url[:50]}..., asset: {asset_urn}")
        return upload_url, asset_urn, media_artifact
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error registering image upload: {e}, Status: {response.status_code}, Response: {response.text}")
        return None, None, None
    except Exception as e:
        logger.error(f"Error registering image upload: {e}")
        return None, None, None

def upload_image(image_url, upload_url, access_token):
    """Upload image binary to LinkedIn using the upload URL."""
    logger.debug(f"Fetching image from {image_url} for upload...")
    try:
        response = session.get(image_url, timeout=10)
        response.raise_for_status()
        headers = {"Authorization": f"Bearer {access_token}"}
        upload_response = session.post(upload_url, headers=headers, data=response.content, timeout=10)
        upload_response.raise_for_status()
        logger.info(f"Successfully uploaded image from {image_url}")
        return True
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error uploading image: {e}, Status: {upload_response.status_code}, Response: {upload_response.text}")
        return False
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        return False

def post_to_linkedin(post_id):
    """Post content with optional image to LinkedIn using v2/ugcPosts endpoint."""
    logger.info(f"Attempting to post Post_ID: {post_id} via batch script")
    
    # Log environment details
    logger.debug(f"Current working directory: {os.getcwd()}")
    logger.debug(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
    logger.debug(f"Current user: {os.getlogin()}")
    logger.debug(f"Command line args: {sys.argv}")
    logger.debug(f"Python executable: {sys.executable}")
    logger.debug(f"Script path: {os.path.abspath(__file__)}")
    
    # Load schedule
    scheduled_posts = load_schedule()
    post = next((p for p in scheduled_posts if p["Post_ID"] == post_id), None)
    if not post:
        logger.error(f"Post_ID {post_id} not found in schedule.json")
        sys.exit(1)
    
    # Post to LinkedIn with retry
    access_token = config.get("LINKEDIN_ACCESS_TOKEN")
    if not access_token:
        logger.error("LinkedIn access token missing in config.json")
        sys.exit(1)
    
    user_id = get_linkedin_user_id(access_token)
    if user_id:
        logger.debug(f"Posting content: {post['Output_Text'][:50]}...")
        image_url = post.get("image")
        max_attempts = 3
        for attempt in range(max_attempts):
            if image_url:
                upload_url, asset_urn, _ = register_image_upload(access_token, user_id)
                if not upload_url or not asset_urn:
                    logger.error(f"Failed to register image upload on attempt {attempt + 1}/{max_attempts}")
                    continue
                if not upload_image(image_url, upload_url, access_token):
                    logger.error(f"Failed to upload image on attempt {attempt + 1}/{max_attempts}")
                    continue
                media = [{
                    "status": "READY",
                    "media": asset_urn,
                    "title": {"text": "Shared Image"},
                    "description": {"text": "Image attached to post"}
                }]
                share_media_category = "IMAGE"
            else:
                media = []
                share_media_category = None

            url = "https://api.linkedin.com/v2/ugcPosts"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
                "LinkedIn-Version": "202306"
            }
            payload = {
                "author": f"urn:li:person:{user_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": post["Output_Text"]},
                        "shareMediaCategory": share_media_category,
                        "media": media if image_url else []
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
            }
            logger.debug(f"Sending POST request to {url}, payload: {json.dumps(payload, indent=2)}...")
            try:
                response = session.post(url, headers=headers, json=payload, timeout=10)
                response.raise_for_status()
                logger.info(f"Successfully posted to LinkedIn with{'out' if not image_url else ''} image: {post['Output_Text'][:50]}...")
                post["Posted"] = True
                save_schedule(scheduled_posts)
                try:
                    output_file = os.path.join(os.getcwd(), "output.xlsx")
                    if os.path.exists(output_file):
                        df = pd.read_excel(output_file)
                        df.loc[df['Post_ID'] == post_id, 'Posted'] = True
                        output_buffer = BytesIO()
                        df.to_excel(output_buffer, index=False)
                        with open(output_file, "wb") as f:
                            f.write(output_buffer.getvalue())
                        logger.info(f"Updated output.xlsx for Post_ID {post_id}")
                    else:
                        logger.error(f"output.xlsx not found at {output_file}")
                except Exception as e:
                    logger.error(f"Error updating output.xlsx for Post_ID {post_id}: {e}")
                sys.exit(0)  # Success, exit
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error posting to LinkedIn on attempt {attempt + 1}/{max_attempts}: {e}, Status: {response.status_code}, Response: {response.text}")
                if attempt == max_attempts - 1:
                    logger.error(f"Max retries reached for Post_ID {post_id}, posting failed")
                    sys.exit(1)
                time.sleep(5)  # Wait before retry
            except Exception as e:
                logger.error(f"Error posting to LinkedIn on attempt {attempt + 1}/{max_attempts}: {e}")
                if attempt == max_attempts - 1:
                    logger.error(f"Max retries reached for Post_ID {post_id}, posting failed")
                    sys.exit(1)
                time.sleep(5)
    else:
        logger.error(f"Failed to fetch user ID for Post_ID {post_id}")
        sys.exit(1)

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
    """Save scheduled posts to schedule.json."""
    schedule_file = os.path.join(os.getcwd(), config["SCHEDULE_FILE"])
    try:
        with open(schedule_file, "w") as f:
            json.dump(scheduled_posts, f, indent=2)
        logger.info(f"Saved {len(scheduled_posts)} scheduled posts to {schedule_file}")
    except Exception as e:
        logger.error(f"Error saving schedule.json at {schedule_file}: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: python post_to_linkedin.py <Post_ID>")
        sys.exit(1)
    post_to_linkedin(sys.argv[1])