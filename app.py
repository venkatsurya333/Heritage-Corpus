import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime
import uuid
from deep_translator import GoogleTranslator

# -------------------------
# Configuration
# -------------------------
st.set_page_config(
    page_title="BharathVani - Cultural Heritage Corpus",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# File paths
USER_FILE = "users.csv"
CORPUS_FILE = "heritage_corpus.json"
UPLOAD_DIR = "uploads"

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
# Sidebar with Language Support
# -------------------------
with st.sidebar:
    st.markdown("### 🏛️ BharathVani")
    # Display names with native script
    language_display = ['English', 'हिन्दी', 'తెలుగు', 'தமிழ்', 'বাংলা', 'ಕನ್ನಡ', 'മലയാളം']
    # Corresponding language codes for translation
    language_codes = {
        'English': 'en',
        'हिन्दी': 'hi',
        'తెలుగు': 'te',
        'தமிழ்': 'ta',
        'বাংলা': 'bn',
        'ಕನ್ನಡ': 'kn',
        'മലയാളം': 'ml'
    }
    selected_display = st.selectbox("🌐 Select Language", language_display, index=0)
    selected_code = language_codes[selected_display]
    st.session_state['lang'] = selected_code

# -------------------------
# Authentication Functions
# -------------------------
def reset_user_file():
    pd.DataFrame(columns=["username", "password"]).to_csv(USER_FILE, index=False)

def save_user(username, password):
    username, password = username.strip(), password.strip()
    if not (username and password):
        return None
    if not os.path.exists(USER_FILE):
        reset_user_file()
    df = pd.read_csv(USER_FILE)
    if username in df["username"].values:
        return False
    new_row = pd.DataFrame({
        "username": [username],
        "password": [password]
    })
    pd.concat([df, new_row], ignore_index=True).to_csv(USER_FILE, index=False)
    return True

def get_user(username):
    if not os.path.exists(USER_FILE):
        reset_user_file()
    df = pd.read_csv(USER_FILE)
    user_df = df[df["username"] == username]
    return user_df.iloc[0] if not user_df.empty else None

def login_user(username, password):
    user = get_user(username)
    if user is None:
        return False
    return user["password"] == password

# -------------------------
# Location & Data Functions (Improved)
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

def save_corpus_entry(entry):
    if os.path.exists(CORPUS_FILE):
        try:
            with open(CORPUS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []
    else:
        data = []

    entry['id'] = str(uuid.uuid4())
    entry['timestamp'] = datetime.now().isoformat()
    entry['created_date'] = datetime.now().strftime('%Y-%m-%d')
    data.append(entry)

    with open(CORPUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return entry['id']

def load_corpus_data():
    if os.path.exists(CORPUS_FILE):
        try:
            with open(CORPUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_uploaded_file(uploaded_file, entry_id):
    if uploaded_file is None:
        return None
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{entry_id}_{uploaded_file.name}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return {
        'filename': filename,
        'filepath': filepath,
        'size': uploaded_file.size,
        'type': uploaded_file.type
    }

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
    with st.form("auth_form", clear_on_submit=True):
        st.markdown(f"### 🔐 {t('Authentication', st.session_state['lang'])}")
        username = st.text_input(t("Username", st.session_state['lang']), placeholder=t("Enter your username", st.session_state['lang']))
        password = st.text_input(t("Password", st.session_state['lang']), type="password", placeholder=t("Enter your password", st.session_state['lang']))
        col1, col2 = st.columns(2)
        with col1:
            login = st.form_submit_button(t("🔑 Login", st.session_state['lang']))
        with col2:
            signup = st.form_submit_button(t("📝 Sign Up", st.session_state['lang']))
        if login and username and password:
            if login_user(username, password):
                st.session_state.user = username
                st.success(t("Login successful!", st.session_state['lang']))
                st.rerun()
            else:
                st.error(t("❌ Username or password incorrect.", st.session_state['lang']))
        elif signup and username and password:
            result = save_user(username, password)
            if result is None:
                st.error(t("❌ Both username and password are required.", st.session_state['lang']))
            elif result is False:
                st.error(t("❌ Username already exists. Please log in.", st.session_state['lang']))
            elif result:
                st.session_state.user = username
                st.success(t("Account created successfully!", st.session_state['lang']))
                st.rerun()
        elif (login or signup) and not (username and password):
            st.warning(t("⚠️ Please fill all fields!", st.session_state['lang']))

def show_sidebar():
    with st.sidebar:
        st.markdown("### 🏛️ BharathVani")
        st.markdown(f"**{t('Welcome', st.session_state['lang'])}, {st.session_state.user}!**")
        page = st.radio(t("📍 Navigate", st.session_state['lang']), [
            t("📊 Collect Heritage Data", st.session_state['lang']),
            t("📚 Browse Corpus", st.session_state['lang']),
            t("📈 View Statistics", st.session_state['lang']),
            t("👤 Profile", st.session_state['lang'])
        ])
        corpus_data = load_corpus_data()
        user_entries = [entry for entry in corpus_data if entry.get('contributor_name') == st.session_state.user]
        st.markdown("---")
        st.markdown(f"### {t('📊 Quick Stats', st.session_state['lang'])}")
        st.metric(t("Your Entries", st.session_state['lang']), len(user_entries))
        st.metric(t("Total Entries", st.session_state['lang']), len(corpus_data))
        try:
            requests.get("https://www.google.com", timeout=3)
            st.success(t("🌐 Online", st.session_state['lang']))
        except:
            st.warning(t("📴 Offline", st.session_state['lang']))
        st.markdown("---")
        if st.button(t("🚪 Logout", st.session_state['lang'])):
            st.session_state.user = None
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
        col1, col2 = st.columns(2)
        with col1:
            latitude = st.number_input(t("Latitude", st.session_state['lang']), 
                value=location_data['latitude'] if location_data else 0.0,
                format="%.6f")
        with col2:
            longitude = st.number_input(t("Longitude", st.session_state['lang']), 
                value=location_data['longitude'] if location_data else 0.0,
                format="%.6f")
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
            entry_id = save_corpus_entry(entry)
            if uploaded_files:
                file_info = []
                for uploaded_file in uploaded_files:
                    file_data = save_uploaded_file(uploaded_file, entry_id)
                    if file_data:
                        file_info.append(file_data)
                corpus_data = load_corpus_data()
                for item in corpus_data:
                    if item['id'] == entry_id:
                        item['uploaded_files'] = file_info
                        break
                with open(CORPUS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(corpus_data, f, indent=2, ensure_ascii=False)
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
            st.success(t("✅ Entry saved successfully!", st.session_state['lang']))
            st.balloons()
            st.info(f"{t('Entry ID', st.session_state['lang'])}: {entry_id}")

def show_corpus_browser():
    st.markdown(f'<div class="main-header">{t("📚 Heritage Corpus Browser", st.session_state["lang"])}</div>', unsafe_allow_html=True)
    corpus_data = load_corpus_data()
    if not corpus_data:
        st.info(t("📭 No corpus data available yet. Start by collecting some heritage data!", st.session_state['lang']))
        return
    st.subheader(t("📊 Corpus Summary", st.session_state['lang']))
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(t("Total Entries", st.session_state['lang']), len(corpus_data))
    with col2:
        categories = set(item.get('category', 'Unknown') for item in corpus_data)
        st.metric(t("Categories", st.session_state['lang']), len(categories))
    with col3:
        locations = set(item.get('location', '') for item in corpus_data if item.get('location'))
        st.metric(t("Locations", st.session_state['lang']), len(locations))
    with col4:
        total_files = sum(len(item.get('uploaded_files', [])) for item in corpus_data)
        st.metric(t("Media Files", st.session_state['lang']), total_files)
    st.subheader(t("🔍 Filter & Search", st.session_state['lang']))
    col1, col2, col3 = st.columns(3)
    with col1:
        search_term = st.text_input(t("🔍 Search keyword", st.session_state['lang']), placeholder=t("Search in titles and descriptions", st.session_state['lang']))
    with col2:
        all_categories = sorted(set(item.get('category', 'Unknown') for item in corpus_data))
        category_filter = st.selectbox(t("📂 Filter by Category", st.session_state['lang']), [t("All", st.session_state['lang'])] + all_categories)
    with col3:
        all_contributors = sorted(set(item.get('contributor_name', 'Unknown') for item in corpus_data))
        contributor_filter = st.selectbox(t("👤 Filter by Contributor", st.session_state['lang']), [t("All", st.session_state['lang'])] + all_contributors)
    filtered_data = corpus_data
    if search_term:
        filtered_data = [
            item for item in filtered_data
            if search_term.lower() in item.get('title', '').lower() or
               search_term.lower() in item.get('description', '').lower()
        ]
    if category_filter != t("All", st.session_state['lang']):
        filtered_data = [item for item in filtered_data if item.get('category') == category_filter]
    if contributor_filter != t("All", st.session_state['lang']):
        filtered_data = [item for item in filtered_data if item.get('contributor_name') == contributor_filter]
    st.subheader(f"{t('📋 Results', st.session_state['lang'])} ({len(filtered_data)} {t('entries', st.session_state['lang'])})")
    for item in filtered_data:
        with st.expander(f"🏛️ {item.get('title', t('Untitled', st.session_state['lang']))} — {item.get('place_name', t('Unknown Location', st.session_state['lang']))}"):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**{t('Description', st.session_state['lang'])}:** {item.get('description', t('No description available', st.session_state['lang']))}")
                if item.get('significance'):
                    st.write(f"**{t('Cultural Significance', st.session_state['lang'])}:** {item.get('significance')}")
                if item.get('sources'):
                    st.write(f"**{t('Sources', st.session_state['lang'])}:** {item.get('sources')}")
            with col2:
                st.write(f"**📂 {t('Category', st.session_state['lang'])}:** {item.get('category', t('Unknown', st.session_state['lang']))}")
                st.write(f"**📍 {t('Location', st.session_state['lang'])}:** {item.get('location', t('Unknown', st.session_state['lang']))}")
                st.write(f"**🕐 {t('Period', st.session_state['lang'])}:** {item.get('historical_period', t('Unknown', st.session_state['lang']))}")
                st.write(f"**🗣️ {t('Language', st.session_state['lang'])}:** {item.get('language', t('Unknown', st.session_state['lang']))}")
                st.write(f"**👤 {t('Contributor', st.session_state['lang'])}:** {item.get('contributor_name', t('Anonymous', st.session_state['lang']))}")
                st.write(f"**📅 {t('Added', st.session_state['lang'])}:** {item.get('created_date', t('Unknown', st.session_state['lang']))}")
                if item.get('uploaded_files'):
                    st.write(f"**📎 {t('Files', st.session_state['lang'])}:** {len(item.get('uploaded_files', []))}")
                if item.get('tags'):
                    st.write(f"**🏷️ {t('Tags', st.session_state['lang'])}:** {', '.join(item.get('tags', []))}")

def show_statistics():
    st.markdown(f'<div class="main-header">{t("📈 Corpus Statistics", st.session_state["lang"])}</div>', unsafe_allow_html=True)
    corpus_data = load_corpus_data()
    if not corpus_data:
        st.info(t("📭 No data available for statistics yet.", st.session_state['lang']))
        return
    st.subheader(t("📊 Category Distribution", st.session_state['lang']))
    categories = [item.get('category', t('Unknown', st.session_state['lang'])) for item in corpus_data]
    category_counts = {}
    for cat in categories:
        category_counts[cat] = category_counts.get(cat, 0) + 1
    if category_counts:
        st.bar_chart(category_counts)
    st.subheader(t("📅 Entries Timeline", st.session_state['lang']))
    dates = [item.get('created_date', t('Unknown', st.session_state['lang'])) for item in corpus_data]
    date_counts = {}
    for date in dates:
        date_counts[date] = date_counts.get(date, 0) + 1
    if date_counts:
        st.line_chart(date_counts)
    st.subheader(t("👥 Top Contributors", st.session_state['lang']))
    contributors = [item.get('contributor_name', t('Anonymous', st.session_state['lang'])) for item in corpus_data]
    contributor_counts = {}
    for contrib in contributors:
        contributor_counts[contrib] = contributor_counts.get(contrib, 0) + 1
    sorted_contributors = sorted(contributor_counts.items(), key=lambda x: x[1], reverse=True)
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**{t('Contributor Rankings', st.session_state['lang'])}:**")
        for i, (name, count) in enumerate(sorted_contributors[:10], 1):
            st.write(f"{i}. {name}: {count} {t('entries', st.session_state['lang'])}")
    with col2:
        if sorted_contributors:
            st.bar_chart(dict(sorted_contributors[:10]))

def show_profile():
    st.markdown(f'<div class="main-header">{t("👤 User Profile", st.session_state["lang"])}</div>', unsafe_allow_html=True)
    corpus_data = load_corpus_data()
    user_entries = [entry for entry in corpus_data if entry.get('contributor_name') == st.session_state.user]
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
    if user_entries:
        st.subheader(t("📝 Your Recent Entries", st.session_state['lang']))
        sorted_entries = sorted(user_entries, key=lambda x: x.get('timestamp', ''), reverse=True)
        for entry in sorted_entries[:5]:
            with st.expander(f"{entry.get('title', t('Untitled', st.session_state['lang']))} - {entry.get('created_date', t('Unknown', st.session_state['lang']))}"):
                st.write(f"**{t('Place', st.session_state['lang'])}:** {entry.get('place_name', t('Unknown', st.session_state['lang']))}")
                st.write(f"**{t('Category', st.session_state['lang'])}:** {entry.get('category', t('Unknown', st.session_state['lang']))}")
                st.write(f"**{t('Description', st.session_state['lang'])}:** {entry.get('description', t('No description', st.session_state['lang']))}")
                if entry.get('uploaded_files'):
                    st.write(f"**{t('Files', st.session_state['lang'])}:** {len(entry.get('uploaded_files', []))}")
    else:
        st.info(t("🌟 You haven't created any entries yet. Start collecting heritage data!", st.session_state['lang']))

def main():
    apply_custom_styles()
    if "user" not in st.session_state:
        st.session_state.user = None
    if not os.path.exists(USER_FILE):
        reset_user_file()
    if not st.session_state.user:
        show_authentication()
    else:
        page = show_sidebar()
        if page == t("📊 Collect Heritage Data", st.session_state['lang']):
            show_data_collection_form()
        elif page == t("📚 Browse Corpus", st.session_state['lang']):
            show_corpus_browser()
        elif page == t("📈 View Statistics", st.session_state['lang']):
            show_statistics()
        elif page == t("👤 Profile", st.session_state['lang']):
            show_profile()

if __name__ == "__main__":
    main()
