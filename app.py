import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime
import uuid

# -------------------------
# Configuration
# -------------------------
st.set_page_config(
    page_title="🏛️ BharathVani - Cultural Heritage Corpus",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# File paths
USER_FILE = "users.csv"
CORPUS_FILE = "heritage_corpus.json"
UPLOAD_DIR = "uploads"

# -------------------------
# Authentication Functions
# -------------------------
def reset_user_file():
    """Initialize or reset user file"""
    pd.DataFrame(columns=["username", "password"]).to_csv(USER_FILE, index=False)

def save_user(username, password):
    """Save new user to CSV file"""
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
    """Get user from CSV file"""
    if not os.path.exists(USER_FILE):
        reset_user_file()
    df = pd.read_csv(USER_FILE)
    user_df = df[df["username"] == username]
    return user_df.iloc[0] if not user_df.empty else None

def login_user(username, password):
    """Authenticate user login"""
    user = get_user(username)
    if user is None:
        return False
    return user["password"] == password

# -------------------------
# Location & Data Functions
# -------------------------
def get_user_location():
    """Get user's current location using IP geolocation"""
    try:
        response = requests.get("https://ipapi.co/json/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            lat = data.get('latitude')
            lon = data.get('longitude')
            if lat is not None and lon is not None:
                return {
                    'latitude': lat,
                    'longitude': lon,
                    'city': data.get('city', 'Unknown'),
                    'region': data.get('region', ''),
                    'country': data.get('country_name', ''),
                    'postal_code': data.get('postal', '')
                }
    except Exception as e:
        st.warning(f"🌐 Location detection error: {e}")
    return None

def search_place_info(place_name):
    """Search for place information from Wikipedia and OpenStreetMap"""
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
        st.warning(f"Wikipedia search failed: {str(e)}")

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
        st.warning(f"OpenStreetMap search failed: {str(e)}")
    return results

def save_corpus_entry(entry):
    """Save corpus entry to JSON file"""
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
    """Load corpus data from JSON file"""
    if os.path.exists(CORPUS_FILE):
        try:
            with open(CORPUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_uploaded_file(uploaded_file, entry_id):
    """Save uploaded file to disk"""
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
    """Apply custom CSS styling"""
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
    """Display authentication form"""
    st.markdown('<div class="main-header">🏛️ BharathVani</div>', unsafe_allow_html=True)
    
    with st.form("auth_form", clear_on_submit=True):
        st.markdown("### 🔐 Authentication")
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        col1, col2 = st.columns(2)
        with col1:
            login = st.form_submit_button("🔑 Login")
        with col2:
            signup = st.form_submit_button("📝 Sign Up")
        
        if login and username and password:
            if login_user(username, password):
                st.session_state.user = username
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("❌ Username or password incorrect.")
        elif signup and username and password:
            result = save_user(username, password)
            if result is None:
                st.error("❌ Both username and password are required.")
            elif result is False:
                st.error("❌ Username already exists. Please log in.")
            elif result:
                st.session_state.user = username
                st.success("Account created successfully!")
                st.rerun()
        elif (login or signup) and not (username and password):
            st.warning("⚠️ Please fill all fields!")

def show_sidebar():
    """Display sidebar navigation"""
    with st.sidebar:
        st.markdown("### 🏛️ BharathVani")
        st.markdown(f"**Welcome, {st.session_state.user}!**")
        
        # Navigation
        page = st.radio("📍 Navigate", [
            "📊 Collect Heritage Data", 
            "📚 Browse Corpus", 
            "📈 View Statistics",
            "👤 Profile"
        ])
        
        # Quick stats
        corpus_data = load_corpus_data()
        user_entries = [entry for entry in corpus_data if entry.get('contributor_name') == st.session_state.user]
        
        st.markdown("---")
        st.markdown("### 📊 Quick Stats")
        st.metric("Your Entries", len(user_entries))
        st.metric("Total Entries", len(corpus_data))
        
        # Connection status
        try:
            requests.get("https://www.google.com", timeout=3)
            st.success("🌐 Online")
        except:
            st.warning("📴 Offline")
        
        st.markdown("---")
        if st.button("🚪 Logout"):
            st.session_state.user = None
            st.rerun()
        
        return page

def show_location_info(location_data):
    """Display location information"""
    if location_data:
        st.success(f"📍 Detected Location: {location_data['city']}, {location_data['region']}, {location_data['country']}")
        st.write(f"**Coordinates:** {location_data['latitude']:.4f}, {location_data['longitude']:.4f}")
    else:
        st.warning("📍 Unable to detect location automatically")

def show_data_collection_form():
    """Display data collection form"""
    st.markdown('<div class="main-header">📊 Cultural Heritage Data Collection</div>', unsafe_allow_html=True)
    
    location_data = get_user_location()
    show_location_info(location_data)

    with st.form("corpus_collection_form"):
        st.subheader("📝 Place & Cultural Information")

        col1, col2 = st.columns(2)
        with col1:
            place_name = st.text_input("Place Name *", placeholder="Enter the place name")
            category = st.selectbox("Category *", [
                "Monument", "Temple", "Festival", "Tradition", "Craft", 
                "Music", "Dance", "Literature", "Architecture", "Other"
            ])
            language = st.text_input("Language", placeholder="e.g., Hindi, Telugu, English")
        with col2:
            location_display = f"{location_data['city']}, {location_data['region']}" if location_data else ""
            manual_location = st.text_input("Location", value=location_display)
            historical_period = st.selectbox("Historical Period", [
                "Ancient", "Medieval", "Colonial", "Modern", "Contemporary", "Unknown"
            ])
            tags = st.text_input("Tags (comma-separated)", placeholder="temple, folklore, craft, etc.")

        # Coordinates
        col1, col2 = st.columns(2)
        with col1:
            latitude = st.number_input("Latitude", 
                value=location_data['latitude'] if location_data else 0.0,
                format="%.6f")
        with col2:
            longitude = st.number_input("Longitude", 
                value=location_data['longitude'] if location_data else 0.0,
                format="%.6f")

        st.subheader("📋 Content Details")
        title = st.text_input("Title *", placeholder="Give a descriptive title")
        description = st.text_area("Description *", 
            placeholder="Describe this place, tradition, or cultural element...", 
            height=150)
        significance = st.text_area("Cultural Significance", 
            placeholder="Why is it culturally or historically significant?", 
            height=100)
        sources = st.text_area("Sources/References", 
            placeholder="Mention your sources if any", 
            height=100)

        st.subheader("📁 Upload Media")
        uploaded_files = st.file_uploader(
            "Upload files (images, audio, video, documents)",
            type=['jpg', 'jpeg', 'png', 'mp4', 'mp3', 'wav', 'pdf', 'txt', 'doc', 'docx'],
            accept_multiple_files=True
        )

        auto_search = st.checkbox("🔍 Automatically fetch information from Wikipedia & OpenStreetMap")

        submitted = st.form_submit_button("🚀 Submit Entry")

        if submitted:
            if not place_name or not title or not description:
                st.error("❌ Please fill in required fields: Place Name, Title, and Description.")
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

            # Handle file uploads
            if uploaded_files:
                file_info = []
                for uploaded_file in uploaded_files:
                    file_data = save_uploaded_file(uploaded_file, entry_id)
                    if file_data:
                        file_info.append(file_data)
                
                # Update entry with file info
                corpus_data = load_corpus_data()
                for item in corpus_data:
                    if item['id'] == entry_id:
                        item['uploaded_files'] = file_info
                        break
                
                with open(CORPUS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(corpus_data, f, indent=2, ensure_ascii=False)

            # Auto-search functionality
            if auto_search:
                with st.spinner("🔍 Searching for additional information..."):
                    search_results = search_place_info(place_name)
                    if search_results:
                        st.success("✅ Additional information found!")
                        
                        if 'wikipedia' in search_results:
                            wiki = search_results['wikipedia']
                            st.markdown("### 📖 Wikipedia Summary")
                            st.write(f"**{wiki['title']}**")
                            st.write(wiki['extract'])
                            if wiki.get('url'):
                                st.markdown(f"[📖 Read More on Wikipedia]({wiki['url']})")
                        
                        if 'openstreetmap' in search_results:
                            osm = search_results['openstreetmap']
                            st.markdown("### 🗺️ OpenStreetMap Information")
                            st.write(f"**Location:** {osm.get('display_name', 'N/A')}")
                            st.write(f"**Type:** {osm.get('type', 'N/A')}")

            st.success("✅ Entry saved successfully!")
            st.balloons()
            st.info(f"Entry ID: {entry_id}")

def show_corpus_browser():
    """Display corpus browser"""
    st.markdown('<div class="main-header">📚 Heritage Corpus Browser</div>', unsafe_allow_html=True)
    
    corpus_data = load_corpus_data()

    if not corpus_data:
        st.info("📭 No corpus data available yet. Start by collecting some heritage data!")
        return

    # Summary statistics
    st.subheader("📊 Corpus Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Entries", len(corpus_data))
    with col2:
        categories = set(item.get('category', 'Unknown') for item in corpus_data)
        st.metric("Categories", len(categories))
    with col3:
        locations = set(item.get('location', '') for item in corpus_data if item.get('location'))
        st.metric("Locations", len(locations))
    with col4:
        total_files = sum(len(item.get('uploaded_files', [])) for item in corpus_data)
        st.metric("Media Files", total_files)

    # Filters
    st.subheader("🔍 Filter & Search")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_term = st.text_input("🔍 Search keyword", placeholder="Search in titles and descriptions")
    with col2:
        all_categories = sorted(set(item.get('category', 'Unknown') for item in corpus_data))
        category_filter = st.selectbox("📂 Filter by Category", ["All"] + all_categories)
    with col3:
        all_contributors = sorted(set(item.get('contributor_name', 'Unknown') for item in corpus_data))
        contributor_filter = st.selectbox("👤 Filter by Contributor", ["All"] + all_contributors)

    # Apply filters
    filtered_data = corpus_data
    if search_term:
        filtered_data = [
            item for item in filtered_data 
            if search_term.lower() in item.get('title', '').lower() or 
               search_term.lower() in item.get('description', '').lower()
        ]
    if category_filter != "All":
        filtered_data = [item for item in filtered_data if item.get('category') == category_filter]
    if contributor_filter != "All":
        filtered_data = [item for item in filtered_data if item.get('contributor_name') == contributor_filter]

    # Display results
    st.subheader(f"📋 Results ({len(filtered_data)} entries)")
    
    for item in filtered_data:
        with st.expander(f"🏛️ {item.get('title', 'Untitled')} — {item.get('place_name', 'Unknown Location')}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Description:** {item.get('description', 'No description available')}")
                if item.get('significance'):
                    st.write(f"**Cultural Significance:** {item.get('significance')}")
                if item.get('sources'):
                    st.write(f"**Sources:** {item.get('sources')}")
                
            with col2:
                st.write(f"**📂 Category:** {item.get('category', 'Unknown')}")
                st.write(f"**📍 Location:** {item.get('location', 'Unknown')}")
                st.write(f"**🕐 Period:** {item.get('historical_period', 'Unknown')}")
                st.write(f"**🗣️ Language:** {item.get('language', 'Unknown')}")
                st.write(f"**👤 Contributor:** {item.get('contributor_name', 'Anonymous')}")
                st.write(f"**📅 Added:** {item.get('created_date', 'Unknown')}")
                
                if item.get('uploaded_files'):
                    st.write(f"**📎 Files:** {len(item.get('uploaded_files', []))}")
                
                if item.get('tags'):
                    st.write(f"**🏷️ Tags:** {', '.join(item.get('tags', []))}")

def show_statistics():
    """Display corpus statistics"""
    st.markdown('<div class="main-header">📈 Corpus Statistics</div>', unsafe_allow_html=True)
    
    corpus_data = load_corpus_data()
    
    if not corpus_data:
        st.info("📭 No data available for statistics yet.")
        return

    # Category distribution
    st.subheader("📊 Category Distribution")
    categories = [item.get('category', 'Unknown') for item in corpus_data]
    category_counts = {}
    for cat in categories:
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    if category_counts:
        st.bar_chart(category_counts)

    # Timeline
    st.subheader("📅 Entries Timeline")
    dates = [item.get('created_date', 'Unknown') for item in corpus_data]
    date_counts = {}
    for date in dates:
        date_counts[date] = date_counts.get(date, 0) + 1
    
    if date_counts:
        st.line_chart(date_counts)

    # Contributor stats
    st.subheader("👥 Top Contributors")
    contributors = [item.get('contributor_name', 'Anonymous') for item in corpus_data]
    contributor_counts = {}
    for contrib in contributors:
        contributor_counts[contrib] = contributor_counts.get(contrib, 0) + 1
    
    # Sort by contribution count
    sorted_contributors = sorted(contributor_counts.items(), key=lambda x: x[1], reverse=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Contributor Rankings:**")
        for i, (name, count) in enumerate(sorted_contributors[:10], 1):
            st.write(f"{i}. {name}: {count} entries")
    
    with col2:
        if sorted_contributors:
            st.bar_chart(dict(sorted_contributors[:10]))

def show_profile():
    """Display user profile"""
    st.markdown('<div class="main-header">👤 User Profile</div>', unsafe_allow_html=True)
    
    corpus_data = load_corpus_data()
    user_entries = [entry for entry in corpus_data if entry.get('contributor_name') == st.session_state.user]
    
    st.subheader(f"Profile: {st.session_state.user}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Your Entries", len(user_entries))
    with col2:
        user_categories = set(entry.get('category', 'Unknown') for entry in user_entries)
        st.metric("Categories Covered", len(user_categories))
    with col3:
        user_files = sum(len(entry.get('uploaded_files', [])) for entry in user_entries)
        st.metric("Files Uploaded", user_files)
    
    if user_entries:
        st.subheader("📝 Your Recent Entries")
        # Sort by timestamp, newest first
        sorted_entries = sorted(user_entries, key=lambda x: x.get('timestamp', ''), reverse=True)
        
        for entry in sorted_entries[:5]:  # Show last 5 entries
            with st.expander(f"{entry.get('title', 'Untitled')} - {entry.get('created_date', 'Unknown')}"):
                st.write(f"**Place:** {entry.get('place_name', 'Unknown')}")
                st.write(f"**Category:** {entry.get('category', 'Unknown')}")
                st.write(f"**Description:** {entry.get('description', 'No description')}")
                if entry.get('uploaded_files'):
                    st.write(f"**Files:** {len(entry.get('uploaded_files', []))}")
    else:
        st.info("🌟 You haven't created any entries yet. Start collecting heritage data!")

# -------------------------
# Main Application
# -------------------------
def main():
    """Main application logic"""
    apply_custom_styles()
    
    # Initialize session state
    if "user" not in st.session_state:
        st.session_state.user = None
    
    # Reset user file on startup (for demo purposes)
    if not os.path.exists(USER_FILE):
        reset_user_file()
    
    # Authentication check
    if not st.session_state.user:
        show_authentication()
    else:
        # Show main application
        page = show_sidebar()
        
        if page == "📊 Collect Heritage Data":
            show_data_collection_form()
        elif page == "📚 Browse Corpus":
            show_corpus_browser()
        elif page == "📈 View Statistics":
            show_statistics()
        elif page == "👤 Profile":
            show_profile()

if __name__ == "__main__":
    main()
