import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime
import uuid
from deep_translator import GoogleTranslator
from supabase import create_client
from dotenv import load_dotenv
import re

def is_valid_bucket_name(name):
    """Check if bucket name follows Supabase rules"""
    return bool(re.match(r'^[a-z0-9.-]+$', name))

# Usage:
if not is_valid_bucket_name("heritage-uploads"):
    print("Invalid bucket name")

# -------------------------
# Configuration
# -------------------------
st.set_page_config(
    page_title="BharathVani - Cultural Heritage Corpus",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_STORAGE_BUCKET = "heritage-uploads"

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------
# Translation Function
# -------------------------
def t(text, target_lang="en"):
    try:
        if target_lang == "en":
            return text
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except:
        return text

# -------------------------
# Supabase Functions
# -------------------------
def init_supabase_storage():
    """Initialize the Supabase storage bucket if it doesn't exist"""
    try:
        # First try to access the bucket
        try:
            # This will fail if bucket doesn't exist
            supabase.storage.from_(SUPABASE_STORAGE_BUCKET).list()
            return  # Bucket exists, we're good
        except Exception as e:
            # Bucket doesn't exist, create it
            try:
                supabase.storage.create_bucket(SUPABASE_STORAGE_BUCKET, public=True)
                st.success(f"Storage bucket '{SUPABASE_STORAGE_BUCKET}' created successfully")
            except Exception as create_error:
                st.error(f"Failed to create bucket: {create_error}")
    except Exception as e:
        st.error(f"Storage initialization error: {e}")

def sign_up_user(email, password, username):
    try:
        result = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {"username": username}
            }
        })
        return result
    except Exception as e:
        st.error(f"Signup failed: {e}")
        return None

def login_user(email, password):
    try:
        result = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return result
    except Exception as e:
        st.error(f"Login failed: {e}")
        return None

def login_user(email, password):
    try:
        # Perform the login
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            # Store all necessary user information
            st.session_state.user = auth_response.user.user_metadata.get("username") or auth_response.user.email
            st.session_state.user_id = auth_response.user.id  # Crucial for RLS
            st.session_state.supabase_session = auth_response.session
            
            # Update the Supabase client with the new session
            supabase.auth.set_session(
                auth_response.session.access_token,
                auth_response.session.refresh_token
            )
            
            st.success("Login successful!")
            return True
        return False
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        return False
    
def verify_session():
    """Ensure we have an active authenticated session"""
    if 'user_id' not in st.session_state:
        st.error("Please log in to continue")
        st.stop()  # This stops further execution
        
    try:
        # Refresh the session if needed
        current_user = supabase.auth.get_user()
        if not current_user.user:
            st.session_state.clear()
            st.error("Session expired. Please log in again.")
            st.stop()
    except Exception as e:
        st.session_state.clear()
        st.error("Session verification failed")
        st.stop()

def save_corpus_entry(entry):
    verify_session()  # Check authentication first
    
    try:
        # Ensure we have the current user ID
        if not st.session_state.get('user_id'):
            st.error("User identification missing")
            return None
            
        # Set both contributor fields
        entry['contributor_id'] = st.session_state.user_id
        entry['contributor_name'] = st.session_state.user
        
        # Insert the record
        response = supabase.table('heritage_corpus').insert(entry).execute()
        
        if response.data:
            return response.data[0]['id']
        st.error("No data returned from insert")
        return None
    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return None

def load_corpus_data():
    try:
        response = supabase.table('heritage_corpus').select('*').execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"{t('Error loading corpus data:', st.session_state['lang'])} {str(e)}")
        return []

def save_uploaded_file(uploaded_file, entry_id):
    if uploaded_file is None:
        return None
    
    try:
        # Generate unique filename
        file_ext = os.path.splitext(uploaded_file.name)[1]
        filename = f"{entry_id}_{uuid.uuid4()}{file_ext}"
        
        # Upload to Supabase Storage
        file_bytes = uploaded_file.getvalue()
        res = supabase.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
            file=file_bytes,
            path=filename,
            file_options={"content-type": uploaded_file.type}
        )
        
        # Get public URL
        url = supabase.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(filename)
        
        return {
            'filename': filename,
            'url': url,
            'size': uploaded_file.size,
            'type': uploaded_file.type
        }
        
    except Exception as e:
        st.error(f"{t('Error uploading file:', st.session_state['lang'])} {str(e)}")
        return None

# -------------------------
# Location & Data Functions
# -------------------------
from streamlit_js_eval import get_geolocation

def get_city_name(lat, lon):
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "jsonv2", "lat": lat, "lon": lon},
            headers={"User-Agent": "StreamlitApp/1.0"}
        )
        address = response.json().get("address", {})
        return address.get("city") or address.get("town") or address.get("village") or address.get("state")
    except:
        return "Unknown"

def get_user_location():
    """Get user's location from browser geolocation and reverse geocode."""
    gps = get_geolocation()
    if gps and "coords" in gps:
        lat = gps["coords"]["latitude"]
        lon = gps["coords"]["longitude"]
        city = get_city_name(lat, lon)
        return {
            'latitude': lat,
            'longitude': lon,
            'city': city,
            'region': "",
            'country': "",
            'postal_code': ""
        }
    else:
        return None

def search_place_info(place_name):
    results = {}
    try:
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{place_name.replace(' ', '_')}"
        wiki_response = requests.get(wiki_url, timeout=5)
        if wiki_response.status_code == 200:
            wiki_data = wiki_response.json()
            results['wikipedia'] = {
                'title': wiki_data.get('title'),
                'extract': wiki_data.get('extract'),
                'url': wiki_data.get('content_urls', {}).get('desktop', {}).get('page')
            }
    except Exception as e:
        st.warning(t(f"Wikipedia search failed: {str(e)}", st.session_state['lang']))

    try:
        osm_url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': place_name,
            'format': 'json',
            'limit': 1,
            'addressdetails': 1,
            'extratags': 1
        }
        osm_response = requests.get(osm_url, params=params, timeout=5)
        if osm_response.status_code == 200:
            osm_data = osm_response.json()
            if osm_data:
                results['openstreetmap'] = osm_data[0]
    except Exception as e:
        st.warning(t(f"OpenStreetMap search failed: {str(e)}", st.session_state['lang']))
    return results

# -------------------------
# UI Components
# -------------------------
def apply_custom_styles():
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(125deg, #181c22 0%, #111111 100%) !important;
            min-height: 100vh;
        }
        .main-header {
            font-family: 'Montserrat', sans-serif;
            font-size: 2.5rem; font-weight: 800; letter-spacing: 2px;
            text-align: center; margin-bottom: 30px;
            background: linear-gradient(90deg,#3498db 30%, #e67e22 90%);
            background-clip: text; -webkit-background-clip: text;
            color: transparent; -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 2px 20px rgba(52,152,219,0.13));
        }
        .auth-form {
            max-width: 410px; margin: 0 auto; padding: 32px 20px 24px 20px;
            border-radius: 22px; background: rgba(30,30,30,0.97);
            box-shadow: 0 10px 40px 0 rgba(44,62,80,0.23);
            border: 2px solid #3498db44; backdrop-filter: blur(2.5px);
        }
        .stTextInput > div > input {
            background: rgba(52, 152, 219, 0.08);
            border-radius: 12px; padding: 10px 16px;
            border: 2px solid #e67e22;
            font-size: 1.10rem; color: #fff;
            box-shadow: 0 1px 6px rgba(44,62,80,0.18);
            transition: border 0.32s, background 0.32s;
        }
        .stTextInput > div > input:focus {
            border: 2.5px solid #3498db; background: #222;
            outline: none;
        }
        .stTextInput > label {
            color: #e67e22; font-family: 'Montserrat', sans-serif;
            font-size: 1rem; margin-bottom: 3px;
        }
        .stButton > button {
            background: linear-gradient(90deg, #3498db 58%, #e67e22 100%);
            color: #fff !important; border: none !important;
            border-radius: 8px !important; font-weight: bold; font-size: 1.08rem;
            box-shadow: 0 2px 10px rgba(52,152,219,0.16);
            transition: background 0.32s, transform 0.14s;
            padding: 10px 0;
        }
        .stButton > button:hover {
            background: linear-gradient(90deg, #e67e22 62%, #3498db 100%);
            color: #fff !important; transform: scale(1.04);
            box-shadow: 0 4px 20px rgba(52,152,219,0.19);
        }
        .welcome-message {
            background: rgba(52, 152, 219, 0.1);
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
            color: #fff;
        }
        .metric-card {
            background: rgba(30,30,30,0.8);
            border-radius: 12px;
            padding: 15px;
            border: 1px solid #3498db44;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        </style>
    """, unsafe_allow_html=True)

def show_authentication():
    st.markdown('<div class="main-header">🏛️ BharathVani</div>', unsafe_allow_html=True)
    
    # Use a unique form key based on language
    form_key = f"auth_form_{st.session_state.lang}"
    
    with st.form(form_key, clear_on_submit=True):
        st.markdown(f"### 🔐 {t('Authentication', st.session_state['lang'])}")
        email = st.text_input("Email", placeholder=t("Enter your email", st.session_state['lang']))
        password = st.text_input("Password", type="password", placeholder=t("Enter your password", st.session_state['lang']))
        username = st.text_input("Preferred Username (for signup)", placeholder=t("Enter a username", st.session_state['lang']))
        
        col1, col2 = st.columns(2)
        with col1:
            login_pressed = st.form_submit_button(t("🔑 Login", st.session_state['lang']))
        with col2:
            signup_pressed = st.form_submit_button(t("📝 Sign Up", st.session_state['lang']))

        if login_pressed and email and password:
            if login_user(email, password):
                st.rerun()
                
        elif signup_pressed and email and password and username:
            result = sign_up_user(email, password, username)
            if result and result.user:
                st.success(t("✅ Account created! Please verify your email before logging in.", st.session_state['lang']))
            else:
                st.error(t("❌ Signup failed. Email may already exist.", st.session_state['lang']))
                
        elif (login_pressed or signup_pressed) and not (email and password):
            st.warning(t("⚠️ Please fill all fields!", st.session_state['lang']))

def show_sidebar():
    with st.sidebar:
        st.markdown("### 🏛️ BharathVani")
        st.markdown(f"**{t('Welcome', st.session_state['lang'])}, {st.session_state.user}!**")
        
        # Navigation options
        pages = [
            t("📊 Collect Heritage Data", st.session_state['lang']),
            t("📚 Browse Corpus", st.session_state['lang']),
            t("📈 View Statistics", st.session_state['lang']),
            t("👤 Profile", st.session_state['lang'])
        ]
        
        if st.session_state.is_admin:
            pages.append(t("🛠️ Admin Panel", st.session_state['lang']))
            
        page = st.radio(t("📍 Navigate", st.session_state['lang']), pages)
        
        # Quick stats
        corpus_data = load_corpus_data()
        user_entries = [entry for entry in corpus_data if entry.get('contributor_name') == st.session_state.user]
        
        st.markdown("---")
        st.markdown(f"### {t('📊 Quick Stats', st.session_state['lang'])}")
        st.metric(t("Your Entries", st.session_state['lang']), len(user_entries))
        st.metric(t("Total Entries", st.session_state['lang']), len(corpus_data))
        
        # Online status
        try:
            requests.get("https://www.google.com", timeout=3)
            st.success(t("🌐 Online", st.session_state['lang']))
        except:
            st.warning(t("📴 Offline", st.session_state['lang']))
        
        st.markdown("---")
        if st.button(t("🚪 Logout", st.session_state['lang'])):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.session_state.is_admin = False
            st.rerun()
        
        return page

def show_location_info(location_data):
    if location_data:
        st.success(t(f"📍 Detected Location: {location_data['city']}", st.session_state['lang']))
        st.write(f"{t('**Coordinates:**', st.session_state['lang'])} {location_data['latitude']:.4f}, {location_data['longitude']:.4f}")
    else:
        st.warning(t("📍 Unable to detect location automatically", st.session_state['lang']))

def show_data_collection_form():
    st.markdown(f'<div class="main-header">{t("📊 Cultural Heritage Data Collection", st.session_state["lang"])}</div>', unsafe_allow_html=True)
    location_data = get_user_location()
    show_location_info(location_data)

    with st.form("corpus_collection_form"):
        st.subheader(t("📝 Place & Cultural Information", st.session_state['lang']))
        col1, col2 = st.columns(2)
        with col1:
            place_name = st.text_input(t("Place Name *", st.session_state['lang']), placeholder=t("Enter the place name", st.session_state['lang']))
            category = st.selectbox(t("Category *", st.session_state['lang']), [
                t("Monument", st.session_state['lang']), t("Temple", st.session_state['lang']),
                t("Festival", st.session_state['lang']), t("Tradition", st.session_state['lang']),
                t("Craft", st.session_state['lang']), t("Music", st.session_state['lang']),
                t("Dance", st.session_state['lang']), t("Literature", st.session_state['lang']),
                t("Architecture", st.session_state['lang']), t("Other", st.session_state['lang'])
            ])
            language = st.text_input(t("Language", st.session_state['lang']), placeholder=t("e.g., Hindi, Telugu, English", st.session_state['lang']))
        with col2:
            location_display = f"{location_data['city']}" if location_data else ""
            manual_location = st.text_input(t("Location", st.session_state['lang']), value=location_display)
            historical_period = st.selectbox(t("Historical Period", st.session_state['lang']), [
                t("Ancient", st.session_state['lang']), t("Medieval", st.session_state['lang']),
                t("Colonial", st.session_state['lang']), t("Modern", st.session_state['lang']),
                t("Contemporary", st.session_state['lang']), t("Unknown", st.session_state['lang'])
            ])
            tags = st.text_input(t("Tags (comma-separated)", st.session_state['lang']), placeholder=t("temple, folklore, craft, etc.", st.session_state['lang']))
        
        # Coordinates
        if location_data:
            col1, col2 = st.columns(2)
            with col1:
                latitude = st.number_input(t("Latitude", st.session_state['lang']), 
                    value=location_data['latitude'],
                    format="%.6f")
            with col2:
                longitude = st.number_input(t("Longitude", st.session_state['lang']), 
                    value=location_data['longitude'],
                    format="%.6f")
        else:
            latitude = 0.0
            longitude = 0.0
        
        # Content details
        st.subheader(t("📋 Content Details", st.session_state['lang']))
        title = st.text_input(t("Title *", st.session_state['lang']), placeholder=t("Give a descriptive title", st.session_state['lang']))
        description = st.text_area(t("Description *", st.session_state['lang']), 
            placeholder=t("Describe this place, tradition, or cultural element...", st.session_state['lang']), 
            height=150)
        significance = st.text_area(t("Cultural Significance", st.session_state['lang']), 
            placeholder=t("Why is it culturally or historically significant?", st.session_state['lang']), 
            height=100)
        sources = st.text_area(t("Sources/References", st.session_state['lang']), 
            placeholder=t("Mention your sources if any", st.session_state['lang']), 
            height=100)
        
        # Media upload
        st.subheader(t("📁 Upload Media", st.session_state['lang']))
        uploaded_files = st.file_uploader(
            t("Upload files (images, audio, video, documents)", st.session_state['lang']),
            type=['jpg', 'jpeg', 'png', 'mp4', 'mp3', 'wav', 'pdf', 'txt', 'doc', 'docx'],
            accept_multiple_files=True
        )
        
        auto_search = st.checkbox(t("🔍 Automatically fetch information from Wikipedia & OpenStreetMap", st.session_state['lang']))
        submitted = st.form_submit_button(t("🚀 Submit Entry", st.session_state['lang']))
        
        if submitted:
            if not place_name or not title or not description:
                st.error(t("❌ Please fill in required fields: Place Name, Title, and Description.", st.session_state['lang']))
                return
            
            # Prepare entry data
            entry = {
                'contributor_name': st.session_state.user,
                'place_name': place_name,
                'category': category,
                'language': language,
                'location': manual_location,
                'latitude': latitude,
                'longitude': longitude,
                'title': title,
                'description': description,
                'historical_period': historical_period,
                'significance': significance,
                'tags': [tag.strip() for tag in tags.split(',') if tag.strip()],
                'sources': sources,
                'uploaded_files': []
            }
            
            # Save uploaded files
            if uploaded_files:
                file_info = []
                for uploaded_file in uploaded_files:
                    file_data = save_uploaded_file(uploaded_file, str(uuid.uuid4()))
                    if file_data:
                        file_info.append(file_data)
                entry['uploaded_files'] = file_info
            
            # Save entry to Supabase
            entry_id = save_corpus_entry(entry)
            
            if entry_id:
                st.success(t("✅ Entry saved successfully!", st.session_state['lang']))
                st.balloons()
                st.info(f"{t('Entry ID', st.session_state['lang'])}: {entry_id}")
                
                # Auto-search for additional information
                if auto_search:
                    with st.spinner(t("🔍 Searching for additional information...", st.session_state['lang'])):
                        search_results = search_place_info(place_name)
                        if search_results:
                            st.success(t("✅ Additional information found!", st.session_state['lang']))
                            if 'wikipedia' in search_results:
                                wiki = search_results['wikipedia']
                                st.markdown(f"### {t('📖 Wikipedia Summary', st.session_state['lang'])}")
                                st.write(f"**{wiki['title']}**")
                                st.write(wiki['extract'])
                                if wiki.get('url'):
                                    st.markdown(f"[{t('📖 Read More on Wikipedia', st.session_state['lang'])}]({wiki['url']})")
                            if 'openstreetmap' in search_results:
                                osm = search_results['openstreetmap']
                                st.markdown(f"### {t('🗺️ OpenStreetMap Information', st.session_state['lang'])}")
                                st.write(f"**{t('Location', st.session_state['lang'])}:** {osm.get('display_name', 'N/A')}")
                                st.write(f"**{t('Type', st.session_state['lang'])}:** {osm.get('type', 'N/A')}")

def show_corpus_browser():
    st.markdown(f'<div class="main-header">{t("📚 Heritage Corpus Browser", st.session_state["lang"])}</div>', unsafe_allow_html=True)
    
    # Search and filter controls
    st.subheader(t("🔍 Filter & Search", st.session_state['lang']))
    col1, col2, col3 = st.columns(3)
    with col1:
        search_term = st.text_input(t("🔍 Search keyword", st.session_state['lang']), placeholder=t("Search in titles and descriptions", st.session_state['lang']))
    with col2:
        all_categories = supabase.table('heritage_corpus').select('category').execute().data
        unique_categories = sorted(set(item['category'] for item in all_categories))
        category_filter = st.selectbox(t("📂 Filter by Category", st.session_state['lang']), [t("All", st.session_state['lang'])] + unique_categories)
    with col3:
        all_contributors = supabase.table('heritage_corpus').select('contributor_name').execute().data
        unique_contributors = sorted(set(item['contributor_name'] for item in all_contributors))
        contributor_filter = st.selectbox(t("👤 Filter by Contributor", st.session_state['lang']), [t("All", st.session_state['lang'])] + unique_contributors)
    
    # Pagination
    page_size = 10
    page_number = st.number_input(t("Page", st.session_state['lang']), min_value=1, value=1)
    offset = (page_number - 1) * page_size
    
    # Build query
    query = supabase.table('heritage_corpus').select('*')
    
    if search_term:
        query = query.or_(f"title.ilike.%{search_term}%,description.ilike.%{search_term}%")
    
    if category_filter != t("All", st.session_state['lang']):
        query = query.eq('category', category_filter)
    
    if contributor_filter != t("All", st.session_state['lang']):
        query = query.eq('contributor_name', contributor_filter)
    
    # Get count for pagination
    count_query = query.select('count', count='exact')
    total_count = count_query.execute().count
    
    # Apply pagination and execute query
    query = query.range(offset, offset + page_size - 1)
    filtered_data = query.execute().data
    
    # Display results
    st.subheader(f"{t('📋 Results', st.session_state['lang'])} ({total_count} {t('entries', st.session_state['lang'])})")
    
    if not filtered_data:
        st.info(t("No entries match your search criteria.", st.session_state['lang']))
        return
    
    for item in filtered_data:
        with st.expander(f"🏛️ {item.get('title', t('Untitled', st.session_state['lang']))} — {item.get('place_name', t('Unknown Location', st.session_state['lang']))}"):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**{t('Description', st.session_state['lang'])}:** {item.get('description', t('No description available', st.session_state['lang']))}")
                if item.get('significance'):
                    st.write(f"**{t('Cultural Significance', st.session_state['lang'])}:** {item.get('significance')}")
                if item.get('sources'):
                    st.write(f"**{t('Sources', st.session_state['lang'])}:** {item.get('sources')}")
                
                # Display uploaded files if any
                if item.get('uploaded_files'):
                    st.markdown(f"**{t('📎 Attachments', st.session_state['lang'])}**")
                    for file in item['uploaded_files']:
                        st.markdown(f"- [{file['filename']}]({file['url']}) ({file['type']}, {file['size']/1024:.1f} KB)")
                
            with col2:
                st.write(f"**📂 {t('Category', st.session_state['lang'])}:** {item.get('category', t('Unknown', st.session_state['lang']))}")
                st.write(f"**📍 {t('Location', st.session_state['lang'])}:** {item.get('location', t('Unknown', st.session_state['lang']))}")
                st.write(f"**🕐 {t('Period', st.session_state['lang'])}:** {item.get('historical_period', t('Unknown', st.session_state['lang']))}")
                st.write(f"**🗣️ {t('Language', st.session_state['lang'])}:** {item.get('language', t('Unknown', st.session_state['lang']))}")
                st.write(f"**👤 {t('Contributor', st.session_state['lang'])}:** {item.get('contributor_name', t('Anonymous', st.session_state['lang']))}")
                st.write(f"**📅 {t('Added', st.session_state['lang'])}:** {item.get('created_date', t('Unknown', st.session_state['lang']))}")
                if item.get('tags'):
                    st.write(f"**🏷️ {t('Tags', st.session_state['lang'])}:** {', '.join(item.get('tags', []))}")
    
    # Pagination controls
    total_pages = (total_count + page_size - 1) // page_size
    if total_pages > 1:
        st.write(f"{t('Page', st.session_state['lang'])} {page_number} {t('of', st.session_state['lang'])} {total_pages}")

def show_statistics():
    st.markdown(f'<div class="main-header">{t("📈 Corpus Statistics", st.session_state["lang"])}</div>', unsafe_allow_html=True)
    
    try:
        # Get statistics from Supabase RPC function
        stats = supabase.rpc('get_corpus_stats').execute().data
    except:
        stats = None
    
    if not stats:
        st.info(t("📭 No data available for statistics yet.", st.session_state['lang']))
        return
    
    # Display general stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(t("Total Entries", st.session_state['lang']), stats.get('total_entries', 0))
    with col2:
        st.metric(t("Verified Entries", st.session_state['lang']), stats.get('verified_entries', 0))
    with col3:
        st.metric(t("Unique Contributors", st.session_state['lang']), stats.get('unique_contributors', 0))
    
    # Category distribution
    st.subheader(t("📊 Category Distribution", st.session_state['lang']))
    if stats.get('categories'):
        category_data = {k: v for k, v in stats['categories'].items()}
        st.bar_chart(category_data)
    
    # Timeline chart
    st.subheader(t("📅 Entries Timeline", st.session_state['lang']))
    try:
        timeline_data = supabase.table('heritage_corpus') \
            .select('created_date, count') \
            .group('created_date') \
            .execute().data
        
        if timeline_data:
            timeline_dict = {item['created_date']: item['count'] for item in timeline_data}
            st.line_chart(timeline_dict)
    except Exception as e:
        st.warning(t("Could not load timeline data", st.session_state['lang']))
    
    # Top contributors
    st.subheader(t("👥 Top Contributors", st.session_state['lang']))
    try:
        contributors_data = supabase.table('heritage_corpus') \
            .select('contributor_name, count') \
            .group('contributor_name') \
            .order('count', desc=True) \
            .limit(10) \
            .execute().data
        
        if contributors_data:
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**{t('Contributor Rankings', st.session_state['lang'])}:**")
                for i, item in enumerate(contributors_data, 1):
                    st.write(f"{i}. {item['contributor_name']}: {item['count']} {t('entries', st.session_state['lang'])}")
            with col2:
                contributors_dict = {item['contributor_name']: item['count'] for item in contributors_data}
                st.bar_chart(contributors_dict)
    except Exception as e:
        st.warning(t("Could not load contributors data", st.session_state['lang']))

def show_profile():
    st.markdown(f'<div class="main-header">{t("👤 User Profile", st.session_state["lang"])}</div>', unsafe_allow_html=True)
    
    try:
        # Get user's entries from Supabase
        user_entries = supabase.table('heritage_corpus') \
            .select('*') \
            .eq('contributor_name', st.session_state.user) \
            .execute().data
    except:
        user_entries = []
    
    # Profile summary
    st.subheader(f"{t('Profile', st.session_state['lang'])}: {st.session_state.user}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(t("Your Entries", st.session_state['lang']), len(user_entries))
    with col2:
        user_categories = set(entry.get('category', t('Unknown', st.session_state['lang'])) for entry in user_entries)
        st.metric(t("Categories Covered", st.session_state['lang']), len(user_categories))
    with col3:
        user_files = sum(len(entry.get('uploaded_files', [])) for entry in user_entries)
        st.metric(t("Files Uploaded", st.session_state['lang']), user_files)
    
    # Recent entries
    if user_entries:
        st.subheader(t("📝 Your Recent Entries", st.session_state['lang']))
        sorted_entries = sorted(user_entries, key=lambda x: x.get('created_at', ''), reverse=True)
        for entry in sorted_entries[:5]:
            with st.expander(f"{entry.get('title', t('Untitled', st.session_state['lang']))} - {entry.get('created_date', t('Unknown', st.session_state['lang']))}"):
                st.write(f"**{t('Place', st.session_state['lang'])}:** {entry.get('place_name', t('Unknown', st.session_state['lang']))}")
                st.write(f"**{t('Category', st.session_state['lang'])}:** {entry.get('category', t('Unknown', st.session_state['lang']))}")
                st.write(f"**{t('Description', st.session_state['lang'])}:** {entry.get('description', t('No description', st.session_state['lang']))}")
                if entry.get('uploaded_files'):
                    st.write(f"**{t('Files', st.session_state['lang'])}:** {len(entry.get('uploaded_files', []))}")
    else:
        st.info(t("🌟 You haven't created any entries yet. Start collecting heritage data!", st.session_state['lang']))

def show_admin_panel():
    if not st.session_state.is_admin:
        st.warning(t("Admin access required", st.session_state['lang']))
        return
    
    st.subheader(t("🛠️ Corpus Management", st.session_state['lang']))
    
    tab1, tab2, tab3 = st.tabs([
        t("🗑️ Delete Entries", st.session_state['lang']),
        t("✅ Verify Entries", st.session_state['lang']),
        t("📊 Database Stats", st.session_state['lang'])
    ])
    
    with tab1:
        try:
            entries = supabase.table('heritage_corpus').select('id,title,contributor_name').execute().data
            entry_options = [f"{e['id']} - {e['title']} by {e['contributor_name']}" for e in entries]
            
            to_delete = st.multiselect(t("Select entries to delete", st.session_state['lang']), entry_options)
            
            if st.button(t("Delete Selected", st.session_state['lang'])):
                for entry in to_delete:
                    entry_id = entry.split(' - ')[0]
                    supabase.table('heritage_corpus').delete().eq('id', entry_id).execute()
                
                # Also delete associated files
                for entry in to_delete:
                    entry_id = entry.split(' - ')[0]
                    files = supabase.table('heritage_corpus').select('uploaded_files').eq('id', entry_id).execute().data
                    if files and files[0]['uploaded_files']:
                        for file in files[0]['uploaded_files']:
                            try:
                                supabase.storage.from_(SUPABASE_STORAGE_BUCKET).remove([file['filename']])
                            except:
                                pass
                
                st.success(t("Entries deleted", st.session_state['lang']))
                st.rerun()
        except Exception as e:
            st.error(f"{t('Error:', st.session_state['lang'])} {str(e)}")
    
    with tab2:
        try:
            unverified = supabase.table('heritage_corpus').select('*').eq('verified', False).execute().data
            for entry in unverified:
                with st.expander(f"{entry['title']} - {entry['contributor_name']}"):
                    st.write(entry['description'])
                    if st.button(f"Verify {entry['id']}"):
                        supabase.table('heritage_corpus').update({'verified': True}).eq('id', entry['id']).execute()
                        st.success("Verified!")
                        st.rerun()
        except Exception as e:
            st.error(f"{t('Error:', st.session_state['lang'])} {str(e)}")
    
    with tab3:
        try:
            stats = supabase.rpc('get_corpus_stats').execute().data
            st.write(f"**{t('Total entries', st.session_state['lang'])}:** {stats.get('total_entries', 0)}")
            st.write(f"**{t('Verified entries', st.session_state['lang'])}:** {stats.get('verified_entries', 0)}")
            st.write(f"**{t('Unique contributors', st.session_state['lang'])}:** {stats.get('unique_contributors', 0)}")
            
            # Storage usage
            try:
                storage_stats = supabase.storage.from_(SUPABASE_STORAGE_BUCKET).list()
                total_size = sum(file['metadata']['size'] for file in storage_stats if 'metadata' in file)
                st.write(f"**{t('Storage used', st.session_state['lang'])}:** {total_size/1024/1024:.2f} MB")
                st.write(f"**{t('Files stored', st.session_state['lang'])}:** {len(storage_stats)}")
            except:
                st.warning(t("Could not retrieve storage statistics", st.session_state['lang']))
        except Exception as e:
            st.error(f"{t('Error:', st.session_state['lang'])} {str(e)}")

def main():
    # Apply custom styles
    apply_custom_styles()
    
    # Initialize Supabase storage
    try:
        init_supabase_storage()
    except Exception as e:
        st.error(f"Storage initialization error: {e}")

    # Initialize session variables safely
    session_defaults = {
        'user_id': None,
        'user': None,
        'supabase_session': None,
        'lang': 'en',
        'is_admin': False
    }
    
    for key, value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Sidebar language selection
    with st.sidebar:
        st.markdown("### 🌐 Language")
        language_display = ['English', 'हिन्दी', 'తెలుగు', 'தமிழ்', 'বাংলা', 'ಕನ್ನಡ', 'മലയാളം']
        language_codes = {
            'English': 'en',
            'हिन्दी': 'hi',
            'తెలుగు': 'te',
            'தமிழ்': 'ta',
            'বাংলা': 'bn',
            'ಕನ್ನಡ': 'kn',
            'മലയാളം': 'ml'
        }
        selected_display = st.selectbox("Select Language", language_display, index=0)
        st.session_state['lang'] = language_codes[selected_display]

    # Check authentication state
    if not st.session_state.user_id:
        show_authentication()
    else:
        try:
            # Verify and refresh session
            if st.session_state.supabase_session:
                supabase.auth.set_session(
                    st.session_state.supabase_session.access_token,
                    st.session_state.supabase_session.refresh_token
                )
            
            current_user = supabase.auth.get_user()
            if not current_user.user:
                st.session_state.clear()
                st.rerun()
            
            # Get updated user metadata
            user_metadata = supabase.auth.get_user().user.user_metadata or {}
            st.session_state.is_admin = user_metadata.get('role') == 'admin'

            # Main application flow
            page = show_sidebar()
            
            if page == t("📊 Collect Heritage Data", st.session_state['lang']):
                show_data_collection_form()
            elif page == t("📚 Browse Corpus", st.session_state['lang']):
                show_corpus_browser()
            elif page == t("📈 View Statistics", st.session_state['lang']):
                show_statistics()
            elif page == t("👤 Profile", st.session_state['lang']):
                show_profile()
            elif page == t("🛠️ Admin Panel", st.session_state['lang']) and st.session_state.is_admin:
                show_admin_panel()
            elif page == t("🛠️ Admin Panel", st.session_state['lang']):
                st.warning(t("Admin access required", st.session_state['lang']))
                
        except Exception as e:
            st.error(f"Session error: {str(e)}")
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
