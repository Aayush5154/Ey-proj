import streamlit as st
import pandas as pd
import datetime
import time
import smtplib
import os
import geocoder
from gtts import gTTS 
from io import BytesIO
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pymongo import MongoClient

load_dotenv()

def get_config(key, default_value=None):
    """
    Tries to get config from .env (Local). 
    If not found, tries Streamlit Secrets (Cloud).
    If neither, returns default.
    """
    val = os.getenv(key)
    if val:
        return val
    
    try:
        return st.secrets.get(key, default_value)
    except Exception:

        return default_value

MONGO_URI = get_config("MONGO_URI")
SENDER_EMAIL = get_config("SENDER_EMAIL")
SENDER_PASSWORD = get_config("SENDER_PASSWORD")

DB_NAME = "smoke"
SENSOR_COLLECTION = "mq2Data"

FLEET_DB = {
    "XUV-700-IND (Aayush)": {
        "name": get_config("USER1_NAME", "User 1"),
        "email": get_config("USER1_EMAIL", "email1@test.com"),
        "model": "Mahindra XUV 700",
        "region": "Rajasthan (Hot/Dry)",
        "map_fallback": "26.9124, 75.7873" 
    },
    "THAR-4X4-US (Rahul)": {
        "name": get_config("USER2_NAME", "User 2"),
        "email": get_config("USER2_EMAIL", "email2@test.com"),
        "model": "Mahindra Thar Roxx",
        "region": "Delhi NCR (Urban)",
        "map_fallback": "28.6139, 77.2090" 
    }
}

if 'service_slots' not in st.session_state:
    st.session_state['service_slots'] = ["Slot #102 (10:00 AM)", "Slot #105 (12:30 PM)", "Slot #108 (03:00 PM)"]
if 'last_val' not in st.session_state:
    st.session_state['last_val'] = 0
if 'action_taken' not in st.session_state:
    st.session_state['action_taken'] = False
if 'security_logs' not in st.session_state:
    st.session_state['security_logs'] = []

@st.cache_resource
def init_db():
    if not MONGO_URI: return None
    try:
        client = MongoClient(MONGO_URI)
        return client[DB_NAME]
    except: return None

db = init_db()

def get_location(fallback_coords):
    try:
        g = geocoder.ip('me')
        if g.latlng:
            lat, lng = g.latlng
            link = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            return f"{lat}, {lng}", link
    except: pass
    return fallback_coords, f"http://googleusercontent.com/maps.google.com/?q={fallback_coords}"

def send_email_alert(target_email, subject, body):
    if not SENDER_EMAIL or not SENDER_PASSWORD: return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = target_email 
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, target_email, msg.as_string())
        server.quit()
        return True
    except Exception as e: 
        print(e)
        return False

def ueba_check(agent, action):
    permissions = {
        "Diagnosis_Agent": ["read_stream"],
        "Customer_Ops_Agent": ["dispatch_email", "initiate_call", "access_crm"],
        "Scheduling_Agent": ["write_calendar"],
        "Quality_Agent": ["read_logs", "write_insight"]
    }
    if action in permissions.get(agent, []): return True
    st.session_state['security_logs'].append(f" SECURITY BLOCK: {agent} tried '{action}'")
    return False

def play_voice_announcement(text):
    """Generates MP3 and plays it in the browser"""
    try:
        sound_file = BytesIO()
        tts = gTTS(text, lang='en')
        tts.write_to_fp(sound_file)
        st.audio(sound_file, format='audio/mp3', autoplay=True)
    except Exception as e:
        st.error(f"Audio Error: {e}")

def orchestrate_response(sensor_val, diagnosis, user_profile, loc_str, loc_link):
    target_name = user_profile['name']
    target_email = user_profile['email']
    vehicle_model = user_profile['model']

    st.markdown(f"### Automating Response for {target_name}")
    
    if ueba_check("Customer_Ops_Agent", "dispatch_email"):
        body = (f"URGENT SERVICE REQUEST\nVehicle: {vehicle_model}\nOwner: {target_name}\nRegion: {user_profile['region']}\nIssue: {diagnosis}\nValue: {sensor_val}\nGPS: {loc_link}")
        if send_email_alert(target_email, f"Automo-ve Alert: {vehicle_model}", body):
            st.success(f"✅ Email Gateway: Alert sent to {target_email}")
    
    if ueba_check("Customer_Ops_Agent", "initiate_call"):
        st.info(" Voice Gateway: Initiating Automated Call...")
        play_voice_announcement(f"Hello {target_name}. This is Automo-ve. Critical issue detected in your {vehicle_model}. Please check your email.")

    if ueba_check("Scheduling_Agent", "write_calendar"):
        if st.session_state['service_slots']:
            slot = st.session_state['service_slots'].pop(0)
            st.success(f"✅ Scheduler: Priority Slot '{slot}' Confirmed.")
        else:
            st.error(" Scheduler: No slots available.")

# --- DASHBOARD UI ---
st.set_page_config(page_title="Automo-ve Fleet Manager", layout="wide")

st.title("🏢 Automo-ve: Multi-Fleet Command Center")
st.markdown("**System Status:** :green[ONLINE] | **Region:** :green[INDIA-NORTH] | **UEBA Sentinel:** :green[ARMED]")
st.divider()

with st.sidebar:
    st.header("📡 Incoming Feed Selector")
    selected_vehicle_id = st.selectbox("Active Data Stream", list(FLEET_DB.keys()), index=0)
    current_profile = FLEET_DB[selected_vehicle_id]
    
    st.divider()
    st.markdown(f"**Current Owner:** {current_profile['name']}")
    st.markdown(f"**Vehicle:** {current_profile['model']}")
    st.markdown(f"**Region:** {current_profile['region']}")
    st.divider()
    
    st.header("🛡️ Security Log")
    if st.session_state['security_logs']:
        for log in st.session_state['security_logs']:
            st.error(log)
    else:
        st.caption("No anomalies.")
    
    if st.button("Simulate Attack"):
        ueba_check("Scheduling_Agent", "delete_database")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"📡 Telematics: {selected_vehicle_id}")
    
    if db is not None:
        query = {"vehicle_id": selected_vehicle_id}
        if "Aayush" in selected_vehicle_id:
             query = {"$or": [{"vehicle_id": selected_vehicle_id}, {"vehicle_id": {"$exists": False}}]}

        latest = db["mq2Data"].find_one(query, sort=[('_id', -1)])
        
        if latest:
            val = latest.get('value', 0)
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Vehicle ID", selected_vehicle_id.split(" ")[0], delta_color="off")
            k2.metric("Sensor Value (MQ2)", f"{val} PPM", delta=val-st.session_state['last_val'])
            
            status = "NORMAL"
            if val > 400: status = "CRITICAL"
            elif val > 300: status = "WARNING"
            
            k3.metric("Health Status", status, delta_color="inverse" if status!="NORMAL" else "normal")
            
            if status == "CRITICAL":
                st.error(f"🚨 ALERT: {current_profile['model']} - {current_profile['name']}")
                current_latlng, current_map_link = get_location(current_profile['map_fallback'])

                with st.expander(f"🎫 Incident Ticket: {current_profile['name']}", expanded=True):
                    c1, c2 = st.columns(2)
                    c1.write(f"**Customer:** {current_profile['name']}")
                    c1.write(f"**Model:** {current_profile['model']}")
                    c2.markdown(f"**📍 GPS:** [{current_latlng}]({current_map_link})")
                    c2.markdown(f"**Zone:** {current_profile['region']}")
                    
                    st.divider()
                    
                    if not st.session_state['action_taken'] or st.session_state['last_val'] != val:
                        orchestrate_response(val, "Gasket Integrity Failure", current_profile, current_latlng, current_map_link)
                        st.session_state['last_val'] = val
                        st.session_state['action_taken'] = True
                    else:
                        st.info("✅ Response Active.")
            elif status == "WARNING":
                st.warning(" Advisory: Engine Temp Rising.")
                st.session_state['action_taken'] = False
            else:
                st.success("✅ System Optimal.")
                st.session_state['action_taken'] = False
        else:
            st.info("Waiting for data stream...")
    else:
        st.error(" Database Connection Lost.")

with col2:
    st.subheader("🏭 Root Cause Analysis (RCA)")
    if st.button("Generate Hotspot Analysis"):
        if ueba_check("Quality_Agent", "read_logs"):
             st.success("Analysis Complete")
             st.markdown("### 🔍 Pattern Detected:")
             st.error(" High Failure Rate Detected in Region: **Rajasthan (Hot/Dry)**")
             st.info(" **Correlation:** High ambient heat + sensor spikes > 400 PPM indicates inadequate cooling.")
             st.caption("Recommendation: Recall cooling pumps for vehicles in arid zones.")
             chart_data = pd.DataFrame({"Region": ["Rajasthan", "Delhi", "Mumbai", "Bangalore"], "Failures": [42, 12, 8, 5]})
             st.bar_chart(chart_data.set_index("Region"))