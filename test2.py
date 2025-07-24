import os
import pandas as pd
import streamlit as st
from groq import Groq
from io import BytesIO
import time
import logging
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import uuid
from datetime import datetime, timedelta
import pytz

# Setup logging first (to ensure logger is available)
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Configuration (use Streamlit secrets with fallback)
DEFAULT_CONFIG = {
    "MAX_DAILY_REQUESTS": 1000,  # RPD limit for free tier
    "REQUESTS_PER_POST": 2,  # 1 for text, ~1 for summarization
    "NUM_VARIATIONS": 3,  # Number of variations for prompt
    "LINKEDIN_RETRIES": 3,  # Number of retries for LinkedIn API calls
    "LINKEDIN_RETRY_DELAY": 2,  # Seconds between retries
}

# Load config and secrets with explicit check
config = DEFAULT_CONFIG.copy()
if hasattr(st, 'secrets') and st.secrets is not None:
    if "GROQ_API_KEY" in st.secrets:
        config["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
        logger.info("GROQ_API_KEY loaded from secrets successfully.")
    else:
        st.error("GROQ_API_KEY not found in Streamlit secrets. Please verify and add it in the 'Manage app' secrets section.")
        st.stop()
    if "LINKEDIN_ACCESS_TOKEN" in st.secrets:
        config["LINKEDIN_ACCESS_TOKEN"] = st.secrets["LINKEDIN_ACCESS_TOKEN"]
        logger.info("LINKEDIN_ACCESS_TOKEN loaded from secrets successfully.")
    else:
        st.error("LINKEDIN_ACCESS_TOKEN not found in Streamlit secrets. Please verify and add it in the 'Manage app' secrets section.")
        st.stop()
else:
    st.error("Streamlit secrets are not available. Ensure secrets are configured in the 'Manage app' section.")
    logger.error("st.secrets is not available.")
    st.stop()

# Initialize Groq client
try:
    client = Groq(api_key=config["GROQ_API_KEY"])
    logger.info("Groq client initialized successfully.")
except KeyError as e:
    st.error("Failed to initialize Groq client due to missing API key. Check secrets configuration.")
    logger.error(f"KeyError initializing Groq client: {e}")
    st.stop()
except Exception as e:
    st.error(f"Error initializing Groq client: {str(e)}. Check logs.")
    logger.error(f"Exception initializing Groq client: {e}")
    st.stop()

# Initialize requests session with retries
session = requests.Session()
retries = Retry(
    total=config["LINKEDIN_RETRIES"],
    backoff_factor=config["LINKEDIN_RETRY_DELAY"],
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"]
)
session.mount("https://", HTTPAdapter(max_retries=retries))

def get_linkedin_user_id(access_token):
    """Fetch LinkedIn user ID using the /rest/me API."""
    if not access_token:
        logger.error("LinkedIn access token is empty.")
        st.error("LinkedIn access token is missing. Please add it to Streamlit secrets.")
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
            st.error("Failed to fetch LinkedIn user ID. No 'id' in API response.")
            return None
        logger.info(f"Fetched LinkedIn user ID: {user_id}")
        return user_id
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error fetching LinkedIn user ID: {e}, Status: {response.status_code}, Response: {response.text}")
        st.error(f"HTTP {response.status_code}: {response.text}. Check logs.")
        return None
    except Exception as e:
        logger.error(f"Error fetching LinkedIn user ID: {e}")
        st.error(f"Failed to fetch LinkedIn user ID: {str(e)}. Check logs.")
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

def post_to_linkedin(post_text, access_token, user_id, image_url=None):
    """Post content with optional image to LinkedIn using v2/ugcPosts."""
    if image_url:
        upload_url, asset_urn, media_artifact = register_image_upload(access_token, user_id)
        if not upload_url or not asset_urn:
            logger.error("Failed to register image upload.")
            return False
        if not upload_image(image_url, upload_url, access_token):
            logger.error("Failed to upload image.")
            return False
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
                "shareCommentary": {"text": post_text},
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
        logger.info(f"Successfully posted to LinkedIn with{'out' if not image_url else''} image: {post_text[:50]}...")
        return True
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error posting to LinkedIn: {e}, Status: {response.status_code}, Response: {response.text}")
        return False
    except Exception as e:
        logger.error(f"Error posting to LinkedIn: {e}")
        return False

def enhance_content(content):
    """Enhance a single piece of content using Groq's meta-llama/llama-4-scout-17b-16e-instruct model."""
    logger.info(f"Enhancing content: {content[:50]}...")
    prompt = f"Paraphrase this content for a professional LinkedIn post, keeping it concise, engaging, and under 100 words:\n{content}"
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            max_tokens=150,
            temperature=0.7
        )
        result = response.choices[0].message.content.strip()
        logger.info(f"Content enhanced successfully. Tokens used: {response.usage.prompt_tokens + response.usage.completion_tokens}")
        return result
    except Exception as e:
        logger.error(f"Error enhancing content: {e}")
        st.error("Failed to enhance content. Check logs.")
        return None

def generate_content(prompt, num_variations):
    """Generate multiple LinkedIn post variations using Groq's meta-llama/llama-4-scout-17b-16e-instruct model."""
    logger.info(f"Generating {num_variations} variations for prompt: {prompt[:50]}...")
    posts = []
    for i in range(num_variations):
        full_prompt = f"Generate a 100-word LinkedIn post based on this prompt, with a professional tone and a call-to-action: {prompt} (Variation {i+1})"
        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": full_prompt}],
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                max_tokens=150,
                temperature=0.8
            )
            posts.append((response.choices[0].message.content.strip(), i + 1))
            logger.info(f"Generated variation {i+1} successfully. Tokens used: {response.usage.prompt_tokens + response.usage.completion_tokens}")
        except Exception as e:
            logger.error(f"Error generating post {i+1}: {e}")
            st.error(f"Failed to generate post variation {i+1}. Check logs.")
            posts.append((None, i + 1))
    return posts

def convert_pd_na_to_none(obj):
    """Convert pd.NA to None for JSON serialization."""
    if isinstance(obj, dict):
        return {k: convert_pd_na_to_none(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_pd_na_to_none(item) for item in obj]
    elif pd.isna(obj):
        return None
    return obj

def process_rows(df, process_type, num_variations):
    """Process rows based on process_type ('content' or 'prompt')."""
    posts = []
    output_rows = []
    request_count = 0
    post_index = 1
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_rows = len(df[df['Type'].str.strip().str.lower().replace('\u00A0', ' ') == process_type]) * (num_variations if process_type == "prompt" else 1)
    
    for idx, row in df.iterrows():
        if request_count >= config["MAX_DAILY_REQUESTS"]:
            logger.warning("Reached daily request limit (1000 RPD).")
            status_text.warning("Reached daily request limit (1000 RPD). Stopping.")
            break
        
        input_type = str(row['Type']).strip().lower().replace('\u00A0', ' ')
        input_text = str(row['Text']).strip()
        image_url = str(row.get('image', '')).strip() if 'image' in df.columns else None
        
        if input_type != process_type:
            continue
        
        if not input_text:
            logger.warning(f"Empty Text at row {idx+1}. Skipping.")
            status_text.warning(f"Empty Text at row {idx+1}. Skipping.")
            continue
        
        if input_type == "content":
            status_text.info(f"Processing content (Row {idx+1}): {input_text[:50]}...")
            enhanced = enhance_content(input_text)
            if enhanced:
                output_rows.append({
                    'Type': input_type,
                    'Text': input_text,
                    'Output_Text': enhanced,
                    'Variation': pd.NA,
                    'Timestamp': time.ctime(),
                    'Posted': False,
                    'Post_ID': str(uuid.uuid4()),
                    'Scheduled_DateTime': pd.NA,
                    'image': image_url
                })
                request_count += config["REQUESTS_PER_POST"]
                posts.append(output_rows[-1])
                post_index += 1
            else:
                logger.warning(f"Failed to enhance content at row {idx+1}.")
                status_text.warning(f"Failed to enhance content at row {idx+1}.")
            time.sleep(1)
        
        elif input_type == "prompt":
            status_text.info(f"Generating posts for prompt (Row {idx+1}): {input_text[:50]}...")
            generated_posts = generate_content(input_text, num_variations)
            for post, variation in generated_posts:
                if post:
                    output_rows.append({
                        'Type': input_type,
                        'Text': input_text,
                        'Output_Text': post,
                        'Variation': variation,
                        'Timestamp': time.ctime(),
                        'Posted': False,
                        'Post_ID': str(uuid.uuid4()),
                        'Scheduled_DateTime': pd.NA,
                        'image': image_url
                    })
                    request_count += config["REQUESTS_PER_POST"]
                    posts.append(output_rows[-1])
                    post_index += 1
                else:
                    logger.warning(f"Failed to generate variation {variation} for prompt at row {idx+1}.")
                    status_text.warning(f"Failed to generate variation {variation} for prompt at row {idx+1}.")
                time.sleep(1)
        
        if total_rows > 0:
            progress_bar.progress(min((post_index - 1) / total_rows, 1.0))
    
    return posts, output_rows

def validate_schedule_datetime(schedule_datetime, test_mode=False):
    """Validate that the scheduled date/time is within LinkedIn's limits."""
    now = datetime.now(pytz.UTC)
    min_time = now + timedelta(minutes=5) if test_mode else now + timedelta(hours=1)
    max_time = now + timedelta(days=90)
    try:
        schedule_dt = datetime.strptime(schedule_datetime, "%Y-%m-%d %H:%M")
        schedule_dt = pytz.UTC.localize(schedule_dt)
        if not (min_time <= schedule_dt <= max_time):
            error_msg = f"Scheduled time must be between {min_time.strftime('%Y-%m-%d %H:%M')} and {max_time.strftime('%Y-%m-%d %H:%M')} UTC."
            logger.warning(f"Invalid schedule datetime: {schedule_datetime}. {error_msg}")
            return False, error_msg
        return True, ""
    except ValueError:
        error_msg = "Invalid date/time format. Use YYYY-MM-DD HH:MM (e.g., 2025-07-15 19:00)."
        logger.warning(f"Invalid schedule datetime format: {schedule_datetime}. {error_msg}")
        return False, error_msg

def generate_schedule_csv(df):
    """Generate a CSV for manual scheduling as a fallback."""
    schedule_rows = df[df['Scheduled_DateTime'].notna()][['Post_ID', 'Output_Text', 'Scheduled_DateTime', 'image']]
    if schedule_rows.empty:
        logger.info("No scheduled posts to generate schedule.csv")
        st.warning("No scheduled posts to generate schedule.csv")
        return None
    schedule_rows = schedule_rows.rename(columns={'Output_Text': 'Text', 'Scheduled_DateTime': 'DateTime'})
    schedule_rows['Link'] = ""
    output_buffer = BytesIO()
    schedule_rows[['DateTime', 'Text', 'image', 'Link', 'Post_ID']].to_csv(output_buffer, index=False)
    logger.info("Generated schedule.csv for download")
    return output_buffer.getvalue()

def main():
    """Streamlit UI for LinkedIn content automation."""
    st.title("LinkedIn Content Automation")
    st.markdown("""
    Upload an Excel file with 'Type' (content or prompt), 'Text', and optional 'image' (URL) columns.
    - 'content': Enhances the provided text into a professional LinkedIn post.
    - 'prompt': Generates multiple post variations based on the prompt.
    Use the buttons below to enhance or generate posts. Edit posts using the 'Edit' button, 
    or post immediately with 'Post to LinkedIn'. Ensure the LinkedIn access token is added to Streamlit secrets.
    Results are downloadable as output.xlsx. Use schedule.csv for manual scheduling in LinkedIn or Hootsuite.
    **Note**: Scheduling is not supported on Streamlit Cloud; use the downloaded CSV for manual scheduling.
    """)

    # Initialize session state
    if 'posts' not in st.session_state:
        st.session_state.posts = []
    if 'editing_post_id' not in st.session_state:
        st.session_state.editing_post_id = None
    if 'edited_text' not in st.session_state:
        st.session_state.edited_text = ""
    if 'scheduling_post_id' not in st.session_state:
        st.session_state.scheduling_post_id = None
    if 'scheduled_datetime' not in st.session_state:
        st.session_state.scheduled_datetime = (datetime.now(pytz.UTC) + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")

    # Debug UI
    st.write(f"**Debug**: Current editing_post_id: {st.session_state.editing_post_id}, scheduling_post_id: {st.session_state.scheduling_post_id}")

    # Config settings
    st.sidebar.header("Settings")
    config["NUM_VARIATIONS"] = st.sidebar.slider("Number of Variations for Prompts", 1, 5, config.get("NUM_VARIATIONS", 3))
    test_mode = st.sidebar.checkbox("Enable Test Mode (Min 5 mins from now)", value=False)

    # File uploader
    uploaded_file = st.file_uploader("Upload input.xlsx", type=["xlsx"])
    
    if uploaded_file:
        # Read Excel
        try:
            df = pd.read_excel(uploaded_file)
            st.session_state.df = df
            st.write("**Input Data Preview**")
            st.dataframe(df)
            logger.info(f"Successfully read uploaded Excel with {len(df)} rows.")
        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            st.error(f"Error reading Excel file. Ensure it has 'Type' and 'Text' columns. Check logs.")
            return
        
        if not {'Type', 'Text'}.issubset(df.columns):
            logger.error("Excel file missing required columns: 'Type' and 'Text'.")
            st.error("Excel file must contain 'Type' and 'Text' columns.")
            return
        
        # Initialize output columns
        for col in ['Output_Text', 'Variation', 'Timestamp', 'Posted', 'Post_ID', 'Scheduled_DateTime', 'image']:
            if col not in df.columns:
                df[col] = pd.NA
        df['Post_ID'] = df.apply(lambda row: str(uuid.uuid4()) if pd.isna(row['Post_ID']) and pd.notna(row['Output_Text']) else row['Post_ID'], axis=1)
        
        # Add buttons for processing
        col1, col2 = st.columns(2)
        with col1:
            enhance_button = st.button("Enhance Content")
        with col2:
            generate_button = st.button("Generate Content")
        
        if enhance_button or generate_button:
            process_type = "content" if enhance_button else "prompt"
            posts, output_rows = process_rows(df, process_type, config["NUM_VARIATIONS"])
            for post in posts:
                if 'Post_ID' not in post or not post['Post_ID']:
                    post['Post_ID'] = str(uuid.uuid4())
                    logger.warning(f"Assigned new Post_ID to post: {post['Post_ID']}")
            st.session_state.posts = posts
            logger.debug(f"Updated session state posts: {json.dumps(convert_pd_na_to_none(st.session_state.posts), indent=2)}")
            if output_rows:
                output_df = pd.DataFrame(output_rows)
                df = pd.concat([df, output_df], ignore_index=True)
                st.session_state.df = df
                
                try:
                    output_buffer = BytesIO()
                    df.to_excel(output_buffer, index=False)
                    logger.info(f"Saved {len(output_rows)} posts to Excel")
                    st.success(f"Saved {len(output_rows)} posts to Excel")
                    st.download_button(
                        label="Download Updated Excel",
                        data=output_buffer.getvalue(),
                        file_name="output.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    logger.error(f"Error saving to Excel: {e}")
                    st.error(f"Error saving Excel file. Check logs.")
            
            else:
                logger.info(f"No {process_type} rows processed.")
                st.warning(f"No {process_type} rows processed. Check input.xlsx and logs.")
        
        # Generate and offer schedule.csv download
        schedule_csv = generate_schedule_csv(df)
        if schedule_csv:
            st.download_button(
                label="Download Schedule CSV (Fallback)",
                data=schedule_csv,
                file_name="schedule.csv",
                mime="text/csv"
            )
            st.markdown("""
            **Scheduling Instructions (Fallback)**:
            - **LinkedIn Native Scheduler**: Log into LinkedIn, click 'Start a post', paste the post text from schedule.csv, click the 'Clock' icon, and set the DateTime. Upload the image manually if needed.
            - **Hootsuite**: Upload schedule.csv in Hootsuite’s Bulk Composer (Publisher > Content > Bulk Composer). Ensure DateTime is in YYYY-MM-DD HH:MM format (UTC) and upload images separately.
            - **Other Tools**: Use SocialPilot, Buffer, or EmbedSocial for bulk scheduling. Import schedule.csv and follow their instructions.
            """)

        # Display results
        if st.session_state.posts:
            st.write("**Generated/Enhanced Posts**")
            for i, post in enumerate(st.session_state.posts, 1):
                if 'Post_ID' not in post or not post['Post_ID']:
                    post['Post_ID'] = str(uuid.uuid4())
                    logger.warning(f"Assigned new Post_ID to post {i}: {post['Post_ID']}")
                with st.expander(f"Post {i}"):
                    if post['Type'] == "content":
                        st.write(f"**Original**: {post['Text']}")
                        st.write(f"**Enhanced**: {post['Output_Text']}")
                    else:
                        st.write(f"**Prompt**: {post['Text']}")
                        st.write(f"**Variation {post['Variation']}**: {post['Output_Text']}")
                    if post.get('image'):
                        st.write(f"**Image URL**: {post['image']}")
                    if post['Posted']:
                        st.write("**Status**: Posted to LinkedIn")
                    elif pd.notna(post.get('Scheduled_DateTime')):
                        st.write(f"**Status**: Scheduled for {post['Scheduled_DateTime']} UTC (Manual)")
                    else:
                        with st.form(key=f"edit_form_{post['Post_ID']}"):
                            edited_text = st.text_area("Edit Text:", value=post['Output_Text'], key=f"edit_text_{post['Post_ID']}")
                            edited_image = st.text_input("Edit Image URL:", value=post.get('image', ''), key=f"edit_image_{post['Post_ID']}")
                            if st.form_submit_button("Edit"):
                                logger.debug(f"Edit button clicked for post {i}, Post_ID: {post['Post_ID']}")
                                st.session_state.editing_post_id = post['Post_ID']
                                st.session_state.edited_text = edited_text
                                st.session_state.edited_image = edited_image
                                st.rerun()
                        
                        with st.form(key=f"schedule_form_{post['Post_ID']}"):
                            scheduled_datetime = st.text_input(
                                "Schedule Date and Time (YYYY-MM-DD HH:MM, UTC):",
                                value=st.session_state.scheduled_datetime,
                                key=f"schedule_datetime_{post['Post_ID']}"
                            )
                            if st.form_submit_button("Schedule"):
                                logger.debug(f"Schedule button clicked for post {i}, Post_ID: {post['Post_ID']}")
                                is_valid, error_msg = validate_schedule_datetime(scheduled_datetime, test_mode)
                                if is_valid:
                                    df.loc[df['Post_ID'] == post['Post_ID'], 'Scheduled_DateTime'] = scheduled_datetime
                                    post['Scheduled_DateTime'] = scheduled_datetime
                                    try:
                                        output_buffer = BytesIO()
                                        df.to_excel(output_buffer, index=False)
                                        logger.info(f"Updated Excel with scheduled post: {post['Output_Text'][:50]}...")
                                    except Exception as e:
                                        logger.error(f"Error saving Excel after scheduling: {e}")
                                        st.error(f"Error saving Excel after scheduling. Check logs.")
                                    st.success(f"Post scheduled for {scheduled_datetime} UTC. Download schedule.csv for manual posting.")
                                    st.session_state.scheduling_post_id = None
                                    st.session_state.scheduled_datetime = (datetime.now(pytz.UTC) + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
                                    st.rerun()
                                else:
                                    st.error(error_msg)
                                    logger.warning(f"Invalid schedule datetime: {error_msg}")
                        
                        if st.button("Post to LinkedIn", key=f"post_{post['Post_ID']}"):
                            logger.debug(f"Post to LinkedIn button clicked for post {i}: {post['Output_Text'][:50]}..., Post_ID: {post['Post_ID']}")
                            if not config["LINKEDIN_ACCESS_TOKEN"]:
                                logger.error("LinkedIn access token missing.")
                                st.error("LinkedIn access token is missing. Add it to Streamlit secrets.")
                            else:
                                user_id = get_linkedin_user_id(config["LINKEDIN_ACCESS_TOKEN"])
                                if user_id:
                                    success = post_to_linkedin(post['Output_Text'], config["LINKEDIN_ACCESS_TOKEN"], user_id, post.get('image'))
                                    if success:
                                        df.loc[df['Post_ID'] == post['Post_ID'], 'Posted'] = True
                                        post['Posted'] = True
                                        try:
                                            output_buffer = BytesIO()
                                            df.to_excel(output_buffer, index=False)
                                            logger.info("Updated Excel with Posted status")
                                        except Exception as e:
                                            logger.error(f"Error saving Excel after posting: {e}")
                                            st.error(f"Error saving Excel after posting. Check logs.")
                                        st.rerun()
                        
                        if st.session_state.editing_post_id == post['Post_ID']:
                            with st.form(key=f"save_form_{post['Post_ID']}"):
                                st.write("**Edit Post**")
                                edited_text = st.text_area("Modify the post content:", value=st.session_state.edited_text, key=f"edit_text_save_{post['Post_ID']}")
                                edited_image = st.text_input("Modify Image URL:", value=st.session_state.edited_image, key=f"edit_image_save_{post['Post_ID']}")
                                if st.form_submit_button("Save Changes"):
                                    logger.debug(f"Save Changes button clicked for Post_ID: {post['Post_ID']}, Edited text: {edited_text[:50]}...")
                                    if edited_text.strip():
                                        df.loc[df['Post_ID'] == post['Post_ID'], 'Output_Text'] = edited_text
                                        df.loc[df['Post_ID'] == post['Post_ID'], 'image'] = edited_image if edited_image.strip() else pd.NA
                                        df.loc[df['Post_ID'] == post['Post_ID'], 'Timestamp'] = time.ctime()
                                        post['Output_Text'] = edited_text
                                        post['image'] = edited_image if edited_image.strip() else None
                                        post['Timestamp'] = time.ctime()
                                        try:
                                            output_buffer = BytesIO()
                                            df.to_excel(output_buffer, index=False)
                                            logger.info(f"Updated Excel with edited post: {edited_text[:50]}...")
                                            st.success("Post updated successfully!")
                                        except Exception as e:
                                            logger.error(f"Error saving Excel after editing: {e}")
                                            st.error(f"Error saving Excel after editing. Check logs.")
                                        st.session_state.editing_post_id = None
                                        st.session_state.edited_text = ""
                                        st.session_state.edited_image = ""
                                        st.rerun()
                                    else:
                                        st.error("Edited text cannot be empty.")
                                        logger.warning("Edited text is empty, save aborted.")
            with st.expander("View Log"):
                st.text("\n".join([f"{record.asctime} - {record.levelname} - {record.message}" for record in logger.handlers[0].records]))

if __name__ == "__main__":
    main()
