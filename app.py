import streamlit as st
import streamlit.components.v1 as components
import os
import time
import json
import datetime
import hashlib
import re
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

st.set_page_config(
    page_title="Civic Navigation | Pakistan",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── RAG SETUP (Pinecone + Google Embeddings) ─────────────────────────────────
@st.cache_resource(show_spinner=False)
def init_rag():
    try:
        from pinecone import Pinecone
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from langchain_pinecone import PineconeVectorStore

        pinecone_api_key = os.environ.get("PINECONE_API_KEY", "")
        google_api_key   = os.environ.get("GOOGLE_API_KEY", "")

        if not pinecone_api_key or not google_api_key:
            return None, ""

        clean_google_key = google_api_key.encode("ascii", "ignore").decode("ascii").strip()
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=clean_google_key,
        )
        pc           = Pinecone(api_key=pinecone_api_key)
        index_name   = "hec2"
        index        = pc.Index(index_name)
        vector_store = PineconeVectorStore(embedding=embeddings, index=index)
        return vector_store, "✅ RAG ready — Pinecone + Gemini Embeddings connected."

    except Exception:
        return None, ""


def retrieve_rag_context(vector_store, query: str, k: int = 3) -> str:
    if vector_store is None:
        return ""
    try:
        docs = vector_store.similarity_search(query, k=k)
        if not docs:
            return ""
        parts = []
        for doc in docs:
            src = doc.metadata.get("source", "dataset")
            parts.append(f"[Source: {src}]\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)
    except Exception:
        return ""


# ─── CHAT PERSISTENCE ─────────────────────────────────────────────────────────
CHATS_DIR = Path("saved_chats")
CHATS_DIR.mkdir(exist_ok=True)

def save_chat(session_id, history, card_key=None, title=""):
    try:
        fname   = f"{session_id}_{card_key}.json" if card_key else f"{session_id}.json"
        path    = CHATS_DIR / fname
        payload = {
            "id": session_id, "card_key": card_key,
            "title": title or (history[0]["user"][:40] if history else "New Chat"),
            "timestamp": datetime.datetime.now().isoformat(),
            "history": history,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def load_all_chats():
    chats = []
    try:
        for p in sorted(CHATS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                chats.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
    except Exception:
        pass
    return chats

def delete_chat(session_id, card_key=None):
    try:
        fname = f"{session_id}_{card_key}.json" if card_key else f"{session_id}.json"
        (CHATS_DIR / fname).unlink(missing_ok=True)
    except Exception:
        pass

def new_session_id():
    return hashlib.md5(str(time.time()).encode()).hexdigest()[:12]


# ─── SESSION STATE INITIALISATION ─────────────────────────────────────────────
_defaults = {
    "lang":           "English",
    "lang_radio":     "English",
    "session_id":     new_session_id(),
    "chat_history":   {},
    "page":           "home",
    "openrouter_key": os.environ.get("OPENROUTER_API_KEY", ""),
    "sidebar_history":[],
    "card_quick_reply":{},
    "show_rag_ctx":   False,
    "key_saved_this_session": False,
    "_ls_key_loaded": False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── PERSIST OPENROUTER KEY VIA LOCALSTORAGE ──────────────────────────────────
_LS_KEY = "civic_nav_or_key"

if not st.session_state.get("_ls_key_loaded"):
    # Read query param injected by JS on previous load
    params = st.query_params
    if "_or_key" in params and not st.session_state.openrouter_key:
        st.session_state.openrouter_key = params["_or_key"]
        try:
            st.query_params.clear()
        except Exception:
            pass
    st.session_state["_ls_key_loaded"] = True

# Inject JS to read localStorage and push key via query param on page load
components.html(f"""
<script>
(function() {{
    var saved = localStorage.getItem("{_LS_KEY}");
    if (saved && saved.length > 10) {{
        var url = new URL(window.parent.location.href);
        if (!url.searchParams.get("_or_key")) {{
            url.searchParams.set("_or_key", saved);
            window.parent.location.replace(url.toString());
        }}
    }}
}})();
</script>
""", height=0)


# ─── TRANSLATIONS ─────────────────────────────────────────────────────────────
TEXTS = {
    "English": {
        "title": "Civic Navigation",
        "subtitle": "Pakistan's AI-Powered Public Services Guide",
        "nav_home": "Home", "nav_chat": "Chat", "nav_finder": "Service Finder",
        "nav_tracker": "App Tracker", "nav_offices": "Find Offices", "nav_settings": "API Settings",
        "chat_welcome": "Assalamu Alaikum! I'm your Civic Navigation assistant. I help with NADRA, Passports, SIM registration, banking, taxes, and all civic services in Pakistan.",
        "chat_placeholder": "e.g. What documents do I need for a new passport?",
        "saved_chats": "Saved Chats",
        "no_api": "API key not configured. Go to API Settings first.",
        "settings_title": "API Configuration",
        "settings_info": "Your key is stored only in your session — never sent anywhere except OpenRouter.",
        "save_settings": "Save Settings",
        "settings_saved": "Settings saved for this session.",
        "tracker_title": "Application Status Tracker",
        "offices_title": "Find Nearby Offices",
        "city_label": "Your City", "service_type": "Service Type", "find_offices": "Find Offices",
        "back_home": "← Back to Home",
        "quick_questions": "Quick Questions",
        "open_assistant": "Open Assistant →",
        "dedicated_assistant": "Dedicated Assistant",
        "quick_assistant": "Quick Assistant",
        "card_cnic": "CNIC & Identity", "card_passport": "Passport & Travel",
        "card_sim": "SIM & PTA", "card_banking": "Banking & Finance",
        "card_tax": "Tax & FBR", "card_driving": "Driving License",
        "card_cnic_desc": "Renew or apply for your National ID Card",
        "card_passport_desc": "Apply or renew your Pakistani passport",
        "card_sim_desc": "Register devices & manage SIM status",
        "card_banking_desc": "Open Asaan accounts & banking help",
        "card_tax_desc": "NTN registration, returns & tax filing",
        "card_driving_desc": "Get or renew your driving license",
        "services_title": "Our Services",
        "services_sub": "Choose a service to open its dedicated assistant",
        "prev_convos": "previous conversation(s)",
        "rag_context_label": "📚 Retrieved Knowledge",
        "rag_status": "Knowledge Base",
        "lang_toggle_en": "🇬🇧 English",
        "lang_toggle_ur": "🇵🇰 اردو",
    },
    "Urdu": {
        "title": "سوِک نیویگیشن",
        "subtitle": "پاکستان کی سرکاری خدمات کے لیے اے آئی گائیڈ",
        "nav_home": "ہوم", "nav_chat": "چیٹ", "nav_finder": "سروس فائنڈر",
        "nav_tracker": "ٹریکر", "nav_offices": "دفاتر", "nav_settings": "سیٹنگز",
        "chat_welcome": "السلام علیکم! میں آپ کا سوِک نیویگیشن اسسٹنٹ ہوں۔",
        "chat_placeholder": "مثلاً: نئے پاسپورٹ کے لیے کون سے دستاویز درکار ہیں؟",
        "saved_chats": "محفوظ چیٹس",
        "no_api": "API کی ترتیب نہیں۔ سیٹنگز پر جائیں۔",
        "settings_title": "API ترتیبات",
        "settings_info": "آپ کی کی صرف آپ کے سیشن میں محفوظ ہے۔",
        "save_settings": "سیٹنگز محفوظ کریں",
        "settings_saved": "سیٹنگز محفوظ ہو گئیں۔",
        "tracker_title": "درخواست اسٹیٹس ٹریکر",
        "offices_title": "قریبی دفاتر تلاش کریں",
        "city_label": "آپ کا شہر", "service_type": "سروس کی قسم", "find_offices": "دفاتر تلاش کریں",
        "back_home": "← ہوم پر واپس",
        "quick_questions": "فوری سوالات",
        "open_assistant": "اسسٹنٹ کھولیں →",
        "dedicated_assistant": "مخصوص اسسٹنٹ",
        "quick_assistant": "فوری اسسٹنٹ",
        "card_cnic": "شناختی کارڈ", "card_passport": "پاسپورٹ",
        "card_sim": "سم اور PTA", "card_banking": "بینکنگ",
        "card_tax": "ٹیکس و FBR", "card_driving": "ڈرائیونگ لائسنس",
        "card_cnic_desc": "قومی شناختی کارڈ کی تجدید یا درخواست",
        "card_passport_desc": "پاکستانی پاسپورٹ کی درخواست یا تجدید",
        "card_sim_desc": "ڈیوائس رجسٹریشن اور سم اسٹیٹس",
        "card_banking_desc": "آسان اکاؤنٹ اور بینکنگ مدد",
        "card_tax_desc": "NTN رجسٹریشن اور ٹیکس ریٹرن",
        "card_driving_desc": "ڈرائیونگ لائسنس حاصل کریں یا تجدید کریں",
        "services_title": "ہماری خدمات",
        "services_sub": "کسی سروس کو کھولنے کے لیے منتخب کریں",
        "prev_convos": "پچھلی گفتگو",
        "rag_context_label": "📚 بازیافت شدہ معلومات",
        "rag_status": "نالج بیس",
        "lang_toggle_en": "🇬🇧 English",
        "lang_toggle_ur": "🇵🇰 اردو",
    },
}

# ─── CARDS ────────────────────────────────────────────────────────────────────
CARDS = [
    {
        "key": "cnic", "emoji": "🪪", "accent": "#2563EB", "light": "#EFF6FF",
        "title_key": "card_cnic", "desc_key": "card_cnic_desc",
        "image_url": "https://images.unsplash.com/photo-1586953208448-b95a79798f07?w=400&q=80",
        "questions_en": ["What documents are needed to renew my CNIC?",
                         "How do I apply for a smart card?",
                         "What is the fee for CNIC renewal?",
                         "How long does CNIC renewal take?"],
        "questions_ur": ["شناختی کارڈ تجدید کے لیے کیا دستاویزات چاہیں؟",
                         "سمارٹ کارڈ کے لیے کیسے درخواست دیں؟",
                         "شناختی کارڈ تجدید کی فیس کیا ہے؟"],
    },
    {
        "key": "passport", "emoji": "📘", "accent": "#7C3AED", "light": "#F5F3FF",
        "title_key": "card_passport", "desc_key": "card_passport_desc",
        "image_url": "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=400&q=80",
        "questions_en": ["What documents do I need for a new passport?",
                         "What is the urgent passport fee?",
                         "How long does passport processing take?",
                         "How to renew an expired passport?"],
        "questions_ur": ["نئے پاسپورٹ کے لیے کون سے دستاویز درکار ہیں؟",
                         "ایمرجنسی پاسپورٹ کی فیس کیا ہے؟",
                         "پاسپورٹ کتنے دنوں میں بنتا ہے؟"],
    },
    {
        "key": "sim", "emoji": "📱", "accent": "#059669", "light": "#ECFDF5",
        "title_key": "card_sim", "desc_key": "card_sim_desc",
        "image_url": "https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=400&q=80",
        "questions_en": ["How do I register my device with PTA?",
                         "How to check if my SIM is biometrically verified?",
                         "How many SIMs can I have on my CNIC?",
                         "How to block a lost SIM card?"],
        "questions_ur": ["PTA کے ساتھ ڈیوائس کیسے رجسٹر کریں؟",
                         "سم بائیومیٹرک تصدیق کیسے چیک کریں؟",
                         "CNIC پر کتنی سمیں لی جا سکتی ہیں؟"],
    },
    {
        "key": "banking", "emoji": "🏦", "accent": "#DC2626", "light": "#FEF2F2",
        "title_key": "card_banking", "desc_key": "card_banking_desc",
        "image_url": "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=400&q=80",
        "questions_en": ["What is an Asaan account and how to open one?",
                         "What documents are needed to open a bank account?",
                         "Can I open a bank account without a salary slip?",
                         "What is Roshan Digital Account?"],
        "questions_ur": ["آسان اکاؤنٹ کیا ہے اور کیسے کھولیں؟",
                         "بینک اکاؤنٹ کھولنے کے لیے کیا چاہیے؟",
                         "روشن ڈیجیٹل اکاؤنٹ کیا ہے؟"],
    },
    {
        "key": "tax", "emoji": "🏛️", "accent": "#D97706", "light": "#FFFBEB",
        "title_key": "card_tax", "desc_key": "card_tax_desc",
        "image_url": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=400&q=80",
        "questions_en": ["How do I register for NTN?",
                         "What is the last date to file tax returns?",
                         "How to become an active tax filer?",
                         "What documents are needed for NTN registration?"],
        "questions_ur": ["NTN رجسٹریشن کیسے کریں؟",
                         "ٹیکس ریٹرن جمع کروانے کی آخری تاریخ کیا ہے؟",
                         "ایکٹو ٹیکس فائلر کیسے بنیں؟"],
    },
    {
        "key": "driving", "emoji": "🚗", "accent": "#0891B2", "light": "#ECFEFF",
        "title_key": "card_driving", "desc_key": "card_driving_desc",
        "image_url": "https://images.unsplash.com/photo-1449965408869-eaa3f722e40d?w=400&q=80",
        "questions_en": ["How to apply for a driving license in Pakistan?",
                         "What is the learner permit process?",
                         "What documents are needed for driving license renewal?",
                         "What is the driving test process?"],
        "questions_ur": ["ڈرائیونگ لائسنس کے لیے کیسے درخواست دیں؟",
                         "لرنر پرمٹ کا طریقہ کار کیا ہے؟",
                         "ڈرائیونگ لائسنس تجدید کے لیے کیا چاہیے؟"],
    },
]

# ─── OFFICE DATA ──────────────────────────────────────────────────────────────
OFFICES = {
    "NADRA": {
        "Islamabad": [
            {"name": "NADRA Headquarters", "address": "G-5/2, Shahrah-e-Jamhuriat, Constitution Avenue, Islamabad", "phone": "051-111-786-100", "hours": "Mon–Sat 8AM–6PM", "lat": 33.7208, "lng": 73.0901},
            {"name": "NADRA e-Sahulat F-10 Markaz", "address": "F-10 Markaz, Islamabad", "phone": "051-111-786-100", "hours": "Mon–Sat 8AM–6PM", "lat": 33.6942, "lng": 73.0134},
        ],
        "Rawalpindi": [
            {"name": "NADRA Registration Centre Satellite Town", "address": "Satellite Town, near Committee Chowk, Rawalpindi", "phone": "051-111-786-100", "hours": "Mon–Sat 8AM–6PM", "lat": 33.6007, "lng": 73.0483},
        ],
        "Karachi": [
            {"name": "NADRA Regional Headquarters Karachi", "address": "Clifton Block 5, Karachi", "phone": "021-111-786-100", "hours": "Mon–Sat 8AM–6PM", "lat": 24.8138, "lng": 67.0300},
            {"name": "NADRA Office Saddar Karachi", "address": "Saddar Town, Karachi", "phone": "021-111-786-100", "hours": "Mon–Sat 9AM–5PM", "lat": 24.8557, "lng": 67.0154},
        ],
        "Lahore": [
            {"name": "NADRA Regional Office Lahore", "address": "7-B, Egerton Road, Lahore", "phone": "042-111-786-100", "hours": "Mon–Sat 8AM–6PM", "lat": 31.5564, "lng": 74.3148},
        ],
        "Peshawar": [
            {"name": "NADRA Regional Office Peshawar", "address": "University Town, Shaheen Chowk, Peshawar", "phone": "091-111-786-100", "hours": "Mon–Sat 8AM–5PM", "lat": 34.0108, "lng": 71.5609},
        ],
        "Quetta": [
            {"name": "NADRA Regional Office Quetta", "address": "Zarghoon Road, Quetta", "phone": "081-111-786-100", "hours": "Mon–Sat 8AM–4PM", "lat": 30.1978, "lng": 67.0097},
        ],
        "Multan": [
            {"name": "NADRA Office Multan", "address": "Nishtar Road, Multan", "phone": "061-111-786-100", "hours": "Mon–Sat 8AM–5PM", "lat": 30.1575, "lng": 71.4934},
        ],
        "Faisalabad": [
            {"name": "NADRA Office Faisalabad", "address": "Susan Road, D Ground, Faisalabad", "phone": "041-111-786-100", "hours": "Mon–Sat 8AM–5PM", "lat": 31.4181, "lng": 73.0797},
        ],
    },
    "Passport": {
        "Islamabad": [
            {"name": "Directorate General of Immigration and Passports Islamabad", "address": "Kohsar Block, Pak Secretariat, Islamabad", "phone": "051-9214751", "hours": "Mon–Fri 8AM–4PM", "lat": 33.7294, "lng": 73.0931},
        ],
        "Rawalpindi": [
            {"name": "Regional Passport Office Rawalpindi", "address": "Liaquat Road, near Benazir Bhutto Hospital, Rawalpindi", "phone": "051-4411760", "hours": "Mon–Fri 8AM–4PM", "lat": 33.5906, "lng": 73.0468},
        ],
        "Karachi": [
            {"name": "Regional Passport Office Karachi", "address": "M.A. Jinnah Road, near Pakistan Chowk, Karachi", "phone": "021-9212201", "hours": "Mon–Fri 8AM–4PM", "lat": 24.8607, "lng": 67.0109},
        ],
        "Lahore": [
            {"name": "Regional Passport Office Lahore", "address": "25-West, Davis Road, Lahore Cantonment", "phone": "042-9201271", "hours": "Mon–Fri 8AM–4PM", "lat": 31.5564, "lng": 74.3587},
        ],
        "Peshawar": [
            {"name": "Regional Passport Office Peshawar", "address": "Shami Road, Peshawar City", "phone": "091-9213601", "hours": "Mon–Fri 8AM–4PM", "lat": 34.0070, "lng": 71.5580},
        ],
        "Quetta": [
            {"name": "Regional Passport Office Quetta", "address": "Jinnah Road, Quetta", "phone": "081-9201051", "hours": "Mon–Fri 8AM–3PM", "lat": 30.1922, "lng": 67.0091},
        ],
        "Multan": [
            {"name": "Regional Passport Office Multan", "address": "Multan Cantonment, Multan", "phone": "061-9201120", "hours": "Mon–Fri 8AM–4PM", "lat": 30.2128, "lng": 71.4792},
        ],
        "Faisalabad": [
            {"name": "Regional Passport Office Faisalabad", "address": "Peoples Colony No.1, Faisalabad", "phone": "041-9220075", "hours": "Mon–Fri 8AM–4PM", "lat": 31.4228, "lng": 73.0780},
        ],
    },
    "FBR": {
        "Islamabad": [
            {"name": "FBR Federal Board of Revenue Headquarters Islamabad", "address": "Constitution Avenue, G-5/2, Islamabad", "phone": "051-111-772-772", "hours": "Mon–Fri 9AM–5PM", "lat": 33.7202, "lng": 73.0938},
            {"name": "Regional Tax Office RTO Islamabad", "address": "Civic Centre, Melody Market G-6, Islamabad", "phone": "051-9268100", "hours": "Mon–Fri 8AM–4PM", "lat": 33.7150, "lng": 73.0760},
        ],
        "Rawalpindi": [
            {"name": "RTO Rawalpindi FBR", "address": "Adamjee Road, Saddar, Rawalpindi", "phone": "051-9271871", "hours": "Mon–Fri 8AM–4PM", "lat": 33.5967, "lng": 73.0479},
        ],
        "Karachi": [
            {"name": "Large Taxpayer Office LTO Karachi FBR", "address": "Custom House Building, I.I. Chundrigar Road, Karachi", "phone": "021-99211001", "hours": "Mon–Fri 8AM–4PM", "lat": 24.8608, "lng": 67.0099},
        ],
        "Lahore": [
            {"name": "Large Taxpayer Office LTO Lahore FBR", "address": "99 Ferozepur Road, Lahore Cantonment", "phone": "042-99210001", "hours": "Mon–Fri 8AM–4PM", "lat": 31.5312, "lng": 74.3562},
        ],
        "Peshawar": [
            {"name": "RTO Peshawar FBR", "address": "Jamrud Road, University Town, Peshawar", "phone": "091-9210301", "hours": "Mon–Fri 8AM–4PM", "lat": 34.0041, "lng": 71.4690},
        ],
        "Quetta": [
            {"name": "RTO Quetta FBR", "address": "Zarghoon Road, Quetta", "phone": "081-9201060", "hours": "Mon–Fri 8AM–3PM", "lat": 30.1948, "lng": 67.0090},
        ],
        "Multan": [
            {"name": "RTO Multan FBR", "address": "Abdali Road, Multan", "phone": "061-9200101", "hours": "Mon–Fri 8AM–4PM", "lat": 30.1988, "lng": 71.4590},
        ],
        "Faisalabad": [
            {"name": "RTO Faisalabad FBR", "address": "Susan Road, D Ground, Faisalabad", "phone": "041-9220101", "hours": "Mon–Fri 8AM–4PM", "lat": 31.4163, "lng": 73.0787},
        ],
    },
    "PTA": {
        "Islamabad": [
            {"name": "PTA Pakistan Telecommunication Authority Headquarters", "address": "Mauve Area, G-8/4, Islamabad", "phone": "051-9225341", "hours": "Mon–Fri 9AM–5PM", "lat": 33.6880, "lng": 73.0489},
        ],
        "Rawalpindi": [
            {"name": "PTA Office Rawalpindi", "address": "Peshawar Road, Rawalpindi", "phone": "051-9271041", "hours": "Mon–Fri 9AM–5PM", "lat": 33.5975, "lng": 73.0284},
        ],
        "Karachi": [
            {"name": "PTA Regional Office Karachi", "address": "PTCL Exchange Building, Korangi Industrial Area, Karachi", "phone": "021-99221041", "hours": "Mon–Fri 9AM–5PM", "lat": 24.8403, "lng": 67.0935},
        ],
        "Lahore": [
            {"name": "PTA Regional Office Lahore", "address": "PTCL Building, The Mall Road, Lahore", "phone": "042-99201041", "hours": "Mon–Fri 9AM–5PM", "lat": 31.5497, "lng": 74.3436},
        ],
        "Peshawar": [
            {"name": "PTA Regional Office Peshawar", "address": "PTCL Building, Shami Road, Peshawar", "phone": "091-9210041", "hours": "Mon–Fri 9AM–5PM", "lat": 34.0107, "lng": 71.5609},
        ],
        "Quetta": [
            {"name": "PTA Office Quetta", "address": "PTCL Building, Jinnah Road, Quetta", "phone": "081-9201041", "hours": "Mon–Fri 9AM–4PM", "lat": 30.1922, "lng": 67.0091},
        ],
        "Multan": [
            {"name": "PTA Office Multan", "address": "Nishtar Road, Multan", "phone": "061-9201041", "hours": "Mon–Fri 9AM–5PM", "lat": 30.1984, "lng": 71.4687},
        ],
        "Faisalabad": [
            {"name": "PTA Office Faisalabad", "address": "Clock Tower Area, Faisalabad", "phone": "041-9220041", "hours": "Mon–Fri 9AM–5PM", "lat": 31.4181, "lng": 73.0797},
        ],
    },
}

CITIES       = sorted(["Islamabad", "Rawalpindi", "Karachi", "Lahore", "Peshawar", "Quetta", "Multan", "Faisalabad", "Other"])
OFFICE_ICONS = {"NADRA": "🪪", "Passport": "📘", "FBR": "🏛️", "PTA": "📱"}

TRACKER_INFO = {
    "CNIC / NADRA": {
        "portal": "https://id.nadra.gov.pk/e-id/", "helpline": "0800-24632",
        "description": "Track your CNIC/Smart Card delivery status using the tracking ID on your acknowledgment slip.",
        "steps": ["Visit: id.nadra.gov.pk/e-id/",
                  "Enter your 13-digit CNIC number or tracking ID from your receipt",
                  "Click Track — your status and estimated delivery date will display"],
    },
    "Passport": {
        "portal": "https://passport.gov.pk/trackpassport.aspx", "helpline": "111-777-788",
        "description": "Track your passport application using the reference number from your receipt.",
        "steps": ["Visit: passport.gov.pk/trackpassport.aspx",
                  "Enter your CNIC number and Reference ID from your passport receipt",
                  "Your passport status (In Process / Dispatched / Ready) will be shown"],
    },
    "FBR / Tax Return": {
        "portal": "https://iris.fbr.gov.pk", "helpline": "111-772-772",
        "description": "Check your NTN status, return filing status, or refund status through the Iris portal.",
        "steps": ["Log in to iris.fbr.gov.pk with your NTN and password",
                  "Navigate to the Declaration section",
                  "View your filing status, refund status, or any pending notices"],
    },
    "PTA Device": {
        "portal": "https://dirbs.pta.gov.pk/", "helpline": "0800-5500",
        "description": "Check if your device IMEI is registered, blocked, or compliant. Dial *#06# to get your IMEI.",
        "steps": ["Dial *#06# on your phone to get your 15-digit IMEI number",
                  "Visit: dirbs.pta.gov.pk",
                  "Enter your IMEI — status shows instantly (Compliant / Non-Compliant / Blocked)"],
    },
    "Driving License": {
        "portal": "https://dlims.punjab.gov.pk", "helpline": "042-111-786-786",
        "description": "Track via DLIMS (Punjab). Sindh: transport.sindh.gov.pk | KPK: transport.kp.gov.pk",
        "steps": ["Visit your province's DLIMS portal (Punjab: dlims.punjab.gov.pk)",
                  "Enter your CNIC and the reference number from your application receipt",
                  "Check status and expected dispatch date"],
    },
}

COMPLAINTS = {
    "NADRA":    {"body": "Federal Ombudsman",    "portal": "https://www.mohtasib.gov.pk", "helpline": "1050"},
    "Passport": {"body": "Ministry of Interior", "portal": "https://interior.gov.pk",     "helpline": "051-9204044"},
    "FBR":      {"body": "FBR Iris Complaints",  "portal": "https://iris.fbr.gov.pk",     "helpline": "111-772-772"},
    "PTA":      {"body": "PTA Consumer Support", "portal": "https://complaint.pta.gov.pk","helpline": "0800-5500"},
}

HELPLINES = [
    ("🪪", "NADRA",          "051-111-786-100", "CNIC, Smart Card, B-Form"),
    ("📘", "Passport",       "111-777-788",     "Passport, Visa, Travel Documents"),
    ("🏛️", "FBR Tax",        "111-772-772",     "NTN, Tax Returns, FBR Iris"),
    ("📱", "PTA",            "0800-5500",       "SIM, Device Registration"),
    ("🏦", "SBP Banking",    "111-727-273",     "Asaan Account, Banking Complaints"),
    ("🚗", "NTRC / Driving", "042-111-786-786", "Driving License (Punjab)"),
]

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Nastaliq+Urdu:wght@400;700&family=Playfair+Display:wght@400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

* { box-sizing: border-box; }

.stApp { background: #F0FDF4 !important; font-family: 'Plus Jakarta Sans', sans-serif !important; color: #111827 !important; }
.main .block-container { padding: 1.5rem 2rem 4rem !important; max-width: 1300px !important; }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

section[data-testid="stSidebar"] { background: #064e3b !important; border-right: none !important; width: 340px !important; }
section[data-testid="stSidebar"] > div { padding: 1.2rem 1rem; }
section[data-testid="stSidebar"] .stTextInput > div > div > input { background: rgba(255,255,255,0.1) !important; border: 1px solid rgba(255,255,255,0.2) !important; color: #fff !important; border-radius: 10px !important; font-size: 0.82rem !important; }
section[data-testid="stSidebar"] .stTextInput > div > div > input::placeholder { color: rgba(255,255,255,0.3) !important; }
section[data-testid="stSidebar"] .stButton > button { background: rgba(255,255,255,0.12) !important; border: 1px solid rgba(255,255,255,0.22) !important; color: #fff !important; border-radius: 8px !important; font-size: 0.78rem !important; padding: 0.35rem 0.8rem !important; }
section[data-testid="stSidebar"] .stButton > button:hover { background: rgba(255,255,255,0.22) !important; }
section[data-testid="stSidebar"] .stRadio label { color: rgba(255,255,255,0.8) !important; font-size: 0.82rem !important; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }

.civic-header { background: linear-gradient(135deg, #064e3b 0%, #047857 100%); border-radius: 20px; padding: 1.8rem 2.5rem; margin-bottom: 0.8rem; display: flex; align-items: center; justify-content: space-between; gap: 1rem; box-shadow: 0 4px 24px rgba(6,78,59,0.3); }
.header-title { font-family: 'Playfair Display', serif; font-size: 2.4rem; font-weight: 700; color: #fff !important; margin: 0 0 0.2rem; line-height: 1; }
.header-subtitle { font-size: 0.8rem; color: rgba(255,255,255,0.6) !important; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 0.9rem; }
.header-badges { display: flex; gap: 8px; flex-wrap: wrap; }
.badge { background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); color: rgba(255,255,255,0.9) !important; padding: 3px 12px; border-radius: 20px; font-size: 0.7rem; font-weight: 600; }
.header-logo { width: 80px; height: 80px; background: rgba(1,65,28,0.85); border: 2.5px solid rgba(255,255,255,0.25); border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; overflow: hidden; }

.lang-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 1rem; justify-content: flex-end; }
.lang-btn { display: inline-flex; align-items: center; gap: 6px; padding: 6px 18px; border-radius: 30px; font-size: 0.82rem; font-weight: 700; cursor: pointer; border: 2px solid #D1FAE5; background: #fff; color: #065f46 !important; transition: all 0.18s; text-decoration: none; }
.lang-btn.active { background: #059669 !important; color: #fff !important; border-color: #059669 !important; box-shadow: 0 2px 10px rgba(5,150,105,0.35); }
.lang-btn:hover { background: #D1FAE5 !important; }

.rag-pill { display:inline-flex; align-items:center; gap:6px; background:#D1FAE5; border:1px solid #6EE7B7; border-radius:20px; padding:4px 14px; font-size:0.72rem; font-weight:700; color:#065f46 !important; }
.rag-pill-dot { width:8px; height:8px; border-radius:50%; background:#059669; animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }

.rag-ctx-box { background:#F0FDF4; border:1px solid #A7F3D0; border-left:4px solid #10B981; border-radius:12px; padding:0.8rem 1rem; margin-bottom:0.8rem; font-size:0.78rem; color:#374151 !important; line-height:1.6; }
.rag-ctx-label { font-size:0.68rem; font-weight:700; color:#059669 !important; text-transform:uppercase; letter-spacing:1px; margin-bottom:5px; display:flex; align-items:center; gap:6px; }

.top-nav-active { background: #059669; color: #fff; border-radius: 10px; padding: 8px 14px; text-align: center; font-size: 0.82rem; font-weight: 700; cursor: default; box-shadow: 0 2px 8px rgba(5,150,105,0.35); }

.section-title { font-family: 'Playfair Display', serif; font-size: 1.5rem; font-weight: 700; color: #065f46 !important; margin: 0 0 0.2rem; }
.section-sub { font-size: 0.78rem; color: #6b7280 !important; margin-bottom: 1.5rem; letter-spacing: 1px; text-transform: uppercase; }

.service-card { background: #fff; border-radius: 18px; overflow: hidden; border: 1.5px solid #D1FAE5; transition: transform 0.22s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.22s ease; cursor: pointer; box-shadow: 0 2px 12px rgba(5,150,105,0.06); }
.service-card:hover { transform: translateY(-5px); box-shadow: 0 16px 40px rgba(5,150,105,0.15); border-color: #6EE7B7; }
.card-img-wrapper { width: 100%; height: 140px; overflow: hidden; }
.card-img-wrapper img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.4s ease; display: block; }
.service-card:hover .card-img-wrapper img { transform: scale(1.05); }
.card-accent-bar { height: 4px; width: 100%; }
.card-content { padding: 1rem 1.2rem 0.6rem; }
.card-icon-row { display: flex; align-items: center; gap: 10px; margin-bottom: 5px; }
.card-emoji { font-size: 1.3rem; line-height: 1.1; }
.card-title { font-family: 'Playfair Display', serif; font-size: 1.05rem; font-weight: 700; color: #111827 !important; }
.card-desc { font-size: 0.8rem; color: #4b5563 !important; line-height: 1.5; margin-bottom: 0.4rem; }
.card-prev { font-size: 0.72rem; color: #059669 !important; font-weight: 600; margin-bottom: 0.4rem; }

.card-detail-header { display: flex; align-items: center; gap: 16px; padding: 1.4rem 1.8rem; background: #fff; border-radius: 18px; border: 1.5px solid #D1FAE5; margin-bottom: 1.2rem; box-shadow: 0 2px 10px rgba(5,150,105,0.07); }
.card-detail-title { font-family: 'Playfair Display', serif; font-size: 1.6rem; font-weight: 700; color: #065f46 !important; }
.card-detail-desc { font-size: 0.86rem; color: #4b5563 !important; margin-top: 3px; }
.dedicated-badge { margin-left: auto; display: flex; align-items: center; gap: 8px; background: #D1FAE5; border: 1px solid #6EE7B7; border-radius: 20px; padding: 5px 14px; font-size: 0.75rem; font-weight: 600; color: #065f46 !important; flex-shrink: 0; }

.msg-user-bubble { background: #059669 !important; color: #fff !important; border-radius: 18px 18px 4px 18px; padding: 12px 16px; font-size: 0.9rem; line-height: 1.6; display: inline-block; max-width: 100%; word-break: break-word; box-shadow: 0 2px 8px rgba(5,150,105,0.25); }
.msg-bot-bubble { background: #fff !important; color: #111827 !important; border: 1.5px solid #D1FAE5; border-radius: 4px 18px 18px 18px; padding: 12px 16px; font-size: 0.9rem; line-height: 1.75; display: inline-block; max-width: 100%; word-break: break-word; box-shadow: 0 2px 8px rgba(5,150,105,0.06); }
.msg-timestamp { font-size: 0.67rem; color: #9ca3af !important; margin-top: 4px; }
.bot-avatar { background: #D1FAE5; border-radius: 50%; width: 34px; height: 34px; min-width: 34px; display: flex; align-items: center; justify-content: center; font-size: 1rem; margin-top: 2px; }
.chat-welcome { background: #fff; border: 1.5px solid #D1FAE5; border-left: 4px solid #059669; border-radius: 14px; padding: 1.1rem 1.4rem; margin-bottom: 1rem; font-size: 0.9rem; color: #374151 !important; line-height: 1.7; }

.qs-panel { background: #fff; border: 1.5px solid #D1FAE5; border-radius: 16px; padding: 1.1rem 1.3rem; box-shadow: 0 2px 8px rgba(5,150,105,0.05); margin-bottom: 1rem; }
.qs-label { font-size: 0.72rem; font-weight: 700; color: #059669 !important; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.qs-hint { font-size: 0.8rem; color: #6b7280 !important; margin-bottom: 12px; line-height: 1.5; }

.ai-answer-box { background: #F0FDF4; border: 1.5px solid #A7F3D0; border-left: 4px solid #059669; border-radius: 14px; padding: 1.1rem 1.3rem; margin-top: 0.8rem; font-size: 0.88rem; color: #111827 !important; line-height: 1.75; }
.ai-answer-label { display: flex; align-items: center; gap: 8px; font-size: 0.7rem; font-weight: 700; color: #059669 !important; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.ai-answer-q { font-size: 0.78rem; color: #6b7280 !important; font-style: italic; margin-bottom: 8px; }

.stChatInput > div { background: #fff !important; border: 2px solid #6EE7B7 !important; border-radius: 16px !important; box-shadow: 0 2px 8px rgba(5,150,105,0.1) !important; }
[data-testid="stChatInputContainer"] { background: #fff !important; }
.stChatInput textarea { color: #111827 !important; background: #fff !important; font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 0.9rem !important; }
.stChatInput textarea::placeholder { color: #9ca3af !important; }
.stChatInput button { background: #059669 !important; border-radius: 10px !important; }

.stTextInput > div > div > input { background: #fff !important; border: 1.5px solid #D1FAE5 !important; color: #111827 !important; border-radius: 10px !important; font-size: 0.9rem !important; }
.stTextInput > div > div > input:focus { border-color: #059669 !important; box-shadow: 0 0 0 3px rgba(5,150,105,0.12) !important; }
.stNumberInput > div > div > input { background: #fff !important; border: 1.5px solid #D1FAE5 !important; color: #111827 !important; border-radius: 10px !important; }
.stSelectbox > div > div { background: #fff !important; border: 1.5px solid #D1FAE5 !important; color: #111827 !important; border-radius: 10px !important; }
.stTextArea > div > div > textarea { background: #fff !important; border: 1.5px solid #D1FAE5 !important; color: #111827 !important; border-radius: 10px !important; }

label, .stTextInput label, .stSelectbox label, .stNumberInput label,
.stTextArea label, .stCheckbox label, .stRadio label,
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span { color: #111827 !important; font-size: 0.88rem !important; font-weight: 600 !important; }
[data-testid="stCheckbox"] { margin-bottom: 8px !important; }
[data-testid="stCheckbox"] label, [data-testid="stCheckbox"] label p,
[data-testid="stCheckbox"] label span,
[data-testid="stCheckbox"] div[data-testid="stMarkdownContainer"] p { color: #111827 !important; font-size: 0.88rem !important; font-weight: 500 !important; }

.stButton > button { background: #059669 !important; border: none !important; color: #fff !important; border-radius: 12px !important; font-weight: 600 !important; font-family: 'Plus Jakarta Sans', sans-serif !important; transition: all 0.2s !important; padding: 0.5rem 1.2rem !important; font-size: 0.88rem !important; }
.stButton > button:hover { background: #047857 !important; transform: translateY(-1px) !important; box-shadow: 0 4px 16px rgba(5,150,105,0.3) !important; }
.stFormSubmitButton > button { background: #059669 !important; border: none !important; color: #fff !important; border-radius: 12px !important; font-weight: 700 !important; font-family: 'Plus Jakarta Sans', sans-serif !important; padding: 0.6rem 1.5rem !important; font-size: 0.92rem !important; width: 100% !important; box-shadow: 0 2px 10px rgba(5,150,105,0.25) !important; transition: all 0.2s !important; }
.stFormSubmitButton > button:hover { background: #047857 !important; box-shadow: 0 4px 20px rgba(5,150,105,0.4) !important; transform: translateY(-1px) !important; }

.stSuccess { background: rgba(5,150,105,0.07) !important; border-color: rgba(5,150,105,0.25) !important; color: #065f46 !important; border-radius: 12px !important; }
.stError { background: rgba(220,38,38,0.07) !important; border-color: rgba(220,38,38,0.2) !important; border-radius: 12px !important; }
.stInfo { background: rgba(37,99,235,0.06) !important; border-color: rgba(37,99,235,0.15) !important; color: #1e3a8a !important; border-radius: 12px !important; }
.stWarning { background: rgba(217,119,6,0.07) !important; border-color: rgba(217,119,6,0.2) !important; color: #78350f !important; border-radius: 12px !important; }
[data-testid="stAlert"] p { color: inherit !important; }

.info-card { background: #fff; border: 1.5px solid #D1FAE5; border-radius: 16px; padding: 1.3rem 1.5rem; margin-bottom: 1rem; box-shadow: 0 2px 8px rgba(5,150,105,0.05); }
.info-card-title { font-family: 'Playfair Display', serif; font-size: 1.05rem; font-weight: 600; color: #065f46 !important; margin-bottom: 0.4rem; }
.info-card-body { font-size: 0.84rem; color: #374151 !important; line-height: 1.65; }
.office-card { background: #fff; border: 1.5px solid #D1FAE5; border-radius: 16px; padding: 1.1rem 1.3rem; margin-bottom: 0.8rem; transition: all 0.2s; display: flex; align-items: flex-start; gap: 14px; box-shadow: 0 2px 8px rgba(5,150,105,0.04); }
.office-card:hover { border-color: #059669; box-shadow: 0 4px 20px rgba(5,150,105,0.15); transform: translateY(-2px); }
.office-icon { font-size: 1.8rem; flex-shrink: 0; margin-top: 2px; }
.office-info { flex: 1; }
.office-name { font-weight: 700; color: #065f46 !important; font-size: 0.92rem; margin-bottom: 3px; }
.office-addr { font-size: 0.78rem; color: #4b5563 !important; margin-bottom: 4px; }
.office-phone { font-size: 0.76rem; color: #059669 !important; font-weight: 600; }
.office-tag { display: inline-block; background: #D1FAE5; color: #065f46 !important; padding: 2px 8px; border-radius: 10px; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; }
.maps-btn { display: inline-block; font-size: 0.76rem; color: #065f46 !important; text-decoration: none; font-weight: 600; background: #D1FAE5; padding: 4px 12px; border-radius: 8px; border: 1px solid #A7F3D0; transition: background 0.15s; }
.maps-btn:hover { background: #A7F3D0 !important; }

.metric-tile { background: #fff; border: 1.5px solid #D1FAE5; border-radius: 16px; padding: 1rem 1.2rem; text-align: center; box-shadow: 0 2px 8px rgba(5,150,105,0.04); }
.metric-value { font-family: 'Playfair Display', serif; font-size: 1.3rem; font-weight: 700; color: #059669 !important; }
.metric-label { font-size: 0.7rem; color: #6b7280 !important; text-transform: uppercase; letter-spacing: 1px; margin-top: 3px; }
.step-num { background: #059669; color: #fff; border-radius: 50%; width: 24px; height: 24px; min-width: 24px; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; }
.roadmap-card { background: #fff; border: 1.5px solid #D1FAE5; border-left: 5px solid #059669; border-radius: 20px; padding: 2rem; margin-top: 1.5rem; box-shadow: 0 4px 20px rgba(5,150,105,0.08); }
.msg-bot-sb { background: rgba(255,255,255,0.1) !important; border-radius: 4px 12px 12px 12px; padding: 8px 12px; font-size: 0.82rem; color: rgba(255,255,255,0.9) !important; line-height: 1.55; margin-bottom: 8px; max-width: 95%; }
.msg-user-sb { background: rgba(167,243,208,0.2) !important; border: 1px solid rgba(167,243,208,0.3); border-radius: 12px 4px 12px 12px; padding: 8px 12px; font-size: 0.82rem; color: #fff !important; line-height: 1.55; margin-bottom: 8px; max-width: 95%; margin-left: auto; text-align: right; }
.chat-hist-label { font-size: 0.68rem; font-weight: 700; color: rgba(255,255,255,0.3) !important; text-transform: uppercase; letter-spacing: 1.5px; margin: 12px 0 6px; display: block; }
.stTabs [data-baseweb="tab-list"] { background: transparent !important; border-bottom: 2px solid #D1FAE5 !important; }
.stTabs [data-baseweb="tab"] { background: transparent !important; color: #6b7280 !important; font-size: 0.85rem !important; }
.stTabs [aria-selected="true"] { color: #059669 !important; border-bottom: 2px solid #059669 !important; font-weight: 700 !important; }
.stTabs [data-baseweb="tab-panel"] { background: transparent !important; padding: 1rem 0 0 !important; }
hr { border-color: #D1FAE5 !important; }
.stSpinner > div { border-top-color: #059669 !important; }
.urdu { font-family: 'Noto Nastaliq Urdu', serif !important; direction: rtl; text-align: right; line-height: 2.4 !important; font-size: 1.02rem; }
</style>
""", unsafe_allow_html=True)


# ─── INITIALISE RAG (cached) ──────────────────────────────────────────────────
vector_store, rag_status_msg = init_rag()
rag_ready = vector_store is not None

def get_lang():    return st.session_state.lang
def get_t():       return TEXTS[get_lang()]
def get_is_urdu(): return get_lang() == "Urdu"
def get_dir_cls(): return "urdu" if get_is_urdu() else ""


# ─── AI CALL (RAG-AUGMENTED) ──────────────────────────────────────────────────
def call_ai(messages, system, api_key, rag_context: str = ""):
    if not api_key:
        return "⚠️ Please add your OpenRouter API key in **API Settings** first."

    full_system = system
    if rag_context.strip():
        full_system = (
            f"{system}\n\n"
            "══ RETRIEVED KNOWLEDGE BASE CONTEXT ══\n"
            "The following passages were retrieved from official Pakistani government websites. "
            "Prioritise this information when answering. Cite facts from it where possible. "
            "If the context does not cover the question, use your own knowledge.\n\n"
            f"{rag_context}\n"
            "══ END OF CONTEXT ══"
        )

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://civic-navigation.pk",
                "X-Title": "Civic Navigation Pakistan",
            },
            json={
                "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
                "messages": [{"role": "system", "content": full_system}] + messages,
                "max_tokens": 1500,
                "temperature": 0.3,
            },
            timeout=60,
        )
        r.raise_for_status()
        data    = r.json()
        content = data["choices"][0]["message"].get("content", "").strip()
        if not content:
            return "The AI returned an empty response. Please try again."
        text = re.sub(r'^["\u201c\u201d]+|["\u201c\u201d]+$', "", content).strip()
        return text or "No response received. Please try again."

    except requests.exceptions.Timeout:
        return "Request timed out. Please try again."
    except requests.exceptions.HTTPError as e:
        if "401" in str(e):
            return "Invalid API key. Please check your key in API Settings."
        if "429" in str(e):
            return "Rate limit reached. Please wait a moment."
        return f"API error: {e}"
    except Exception as e:
        return f"Error: {e}"


def call_ai_with_rag(messages, system, api_key, query: str = ""):
    ctx   = retrieve_rag_context(vector_store, query) if query and rag_ready else ""
    reply = call_ai(messages, system, api_key, rag_context=ctx)
    return reply, ctx


def make_system(lang, context=""):
    s = (
        f"You are Civic Navigation, a precise expert AI assistant for Pakistani citizens navigating government services.\n"
        f"You ONLY help with: NADRA, Passports, SIM/PTA, FBR/taxes, banking, driving licenses, domicile, "
        f"e-Khidmat Markaz, police verification, and related Pakistani civic services.\n"
        f"Rules: Answer DIRECTLY and FACTUALLY. Give EXACT fees, documents, step-by-step processes. "
        f"Use **bold** for key terms, numbered steps, bullet points for lists. "
        f"Never mention tools or search processes. Redirect non-civic questions. "
        f"Respond entirely in {lang}. Never wrap response in quotes."
    )
    if context:
        s += f"\n\nFOCUS: {context}"
    return s


# ─── RENDER CHAT TURN ─────────────────────────────────────────────────────────
def render_turn(turn, bot_emoji="🏛️", accent="#059669"):
    ts  = turn.get("timestamp", "")
    dc  = get_dir_cls()
    ctx = turn.get("rag_context", "")
    t   = get_t()
    st.markdown(
        f'<div style="display:flex;justify-content:flex-end;margin-bottom:10px;">'
        f'<div style="max-width:80%;"><div class="msg-user-bubble {dc}">{turn["user"]}</div>'
        f'<div class="msg-timestamp" style="text-align:right;">{ts}</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="display:flex;gap:10px;margin-bottom:{"4px" if ctx else "12px"};align-items:flex-start;">'
        f'<div class="bot-avatar" style="background:{accent}20;">{bot_emoji}</div>'
        f'<div style="max-width:82%;"><div class="msg-bot-bubble {dc}">{turn["bot"]}</div>'
        f'<div class="msg-timestamp">{ts}</div></div></div>',
        unsafe_allow_html=True,
    )
    if ctx and st.session_state.get("show_rag_ctx"):
        preview = ctx[:400] + ("…" if len(ctx) > 400 else "")
        st.markdown(
            f'<div class="rag-ctx-box" style="margin-left:44px;margin-bottom:12px;">'
            f'<div class="rag-ctx-label">📚 {t["rag_context_label"]}</div>'
            f'<div>{preview}</div></div>',
            unsafe_allow_html=True,
        )


# ─── PAK LOGO ─────────────────────────────────────────────────────────────────
PAK_SVG = (
    '<svg width="60" height="60" viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg">'
    '<rect width="60" height="60" rx="30" fill="#01411C"/>'
    '<rect x="0" y="0" width="15" height="60" fill="white"/>'
    '<circle cx="36" cy="30" r="12" fill="white"/>'
    '<circle cx="41" cy="27" r="9.5" fill="#01411C"/>'
    '<polygon points="48,22 49.4,27 54.4,27 50.5,29.8 51.9,34.8 48,32 44.1,34.8 45.5,29.8 41.6,27 46.6,27" fill="white"/>'
    '</svg>'
)


# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
def _on_lang_radio_change():
    st.session_state.lang = st.session_state.lang_radio

with st.sidebar:
    st.markdown(
        '<div style="padding:0.8rem 0 1rem;border-bottom:1px solid rgba(255,255,255,0.15);margin-bottom:1rem;">'
        '<div style="font-family:\'Playfair Display\',serif;font-size:1.2rem;font-weight:700;color:#fff;">Civic Navigation</div>'
        '<div style="font-size:0.68rem;color:rgba(255,255,255,0.4);letter-spacing:1.5px;text-transform:uppercase;">AI Services Guide · Pakistan</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.session_state.lang_radio = st.session_state.lang
    st.radio(
        "Language",
        ["English", "Urdu"],
        horizontal=True,
        key="lang_radio",
        on_change=_on_lang_radio_change,
        label_visibility="visible",
    )

    t       = get_t()
    is_urdu = get_is_urdu()
    dir_cls = get_dir_cls()

    # Only show RAG pill when active — never show errors to user
    if rag_ready:
        st.markdown(
            '<div style="margin:10px 0;">'
            '<div class="rag-pill"><div class="rag-pill-dot"></div>RAG Active</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.checkbox("Show retrieved context in chat", key="show_rag_ctx", value=False)
    else:
        if "show_rag_ctx" not in st.session_state:
            st.session_state["show_rag_ctx"] = False

    st.markdown("---")
    st.markdown(
        f'<div style="font-size:0.7rem;font-weight:700;color:rgba(255,255,255,0.35);'
        f'text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;">'
        f'{t["quick_assistant"]}</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.sidebar_history:
        st.markdown('<div class="msg-bot-sb">Ask me anything about Pakistani government services.</div>', unsafe_allow_html=True)
    else:
        html = "".join(
            f'<div class="msg-user-sb">{h["user"]}</div>'
            f'<div class="msg-bot-sb">{h["bot"][:280]}{"..." if len(h["bot"])>280 else ""}</div>'
            for h in st.session_state.sidebar_history[-5:]
        )
        st.markdown(f'<div style="max-height:230px;overflow-y:auto;">{html}</div>', unsafe_allow_html=True)

    sb_in  = st.text_input("Ask", placeholder=t["chat_placeholder"], key="sb_input", label_visibility="collapsed")
    c1, c2 = st.columns([2, 1])
    with c1:
        sb_send = st.button("Send →", key="sb_send", use_container_width=True)
    with c2:
        if st.button("New", key="sb_new", use_container_width=True):
            st.session_state.sidebar_history = []
            st.rerun()

    if sb_send and sb_in.strip():
        msgs = []
        for h in st.session_state.sidebar_history[-4:]:
            msgs += [{"role": "user", "content": h["user"]}, {"role": "assistant", "content": h["bot"]}]
        msgs.append({"role": "user", "content": sb_in})
        with st.spinner("..."):
            reply, _ = call_ai_with_rag(msgs, make_system(get_lang()), st.session_state.openrouter_key, sb_in)
        st.session_state.sidebar_history.append({"user": sb_in, "bot": reply})
        st.rerun()

    st.markdown("---")
    st.markdown(f'<span class="chat-hist-label">{t["saved_chats"]}</span>', unsafe_allow_html=True)
    for ch in load_all_chats()[:8]:
        ck  = ch.get("card_key")
        lbl = ch.get("title", "Chat")[:24]
        tag = f" [{ck}]" if ck else ""
        cc1, cc2 = st.columns([5, 1])
        with cc1:
            if st.button(f"💬 {lbl}{tag}", key=f"load_{ch['id']}_{ck or ''}", use_container_width=True):
                if ck:
                    st.session_state.chat_history[ck] = ch.get("history", [])
                    st.session_state.page = f"card_{ck}"
                else:
                    st.session_state.chat_history["main"] = ch.get("history", [])
                    st.session_state.page = "chat"
                st.rerun()
        with cc2:
            if st.button("✕", key=f"del_{ch['id']}_{ck or ''}"):
                delete_chat(ch["id"], ck)
                st.rerun()


# ─── RE-SYNC VARS AFTER SIDEBAR ───────────────────────────────────────────────
t       = get_t()
is_urdu = get_is_urdu()
dir_cls = get_dir_cls()
page    = st.session_state.page


# ─── HEADER ───────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="civic-header">'
    f'<div>'
    f'<h1 class="header-title {dir_cls}">{t["title"]}</h1>'
    f'<p class="header-subtitle">{t["subtitle"]}</p>'
    f'<div class="header-badges">'
    f'<span class="badge">AI-Powered</span>'
    f'<span class="badge">RAG-Enhanced</span>'
    f'<span class="badge">Pakistan</span>'
    f'<span class="badge">Bilingual</span>'
    f'<span class="badge">Free to Use</span>'
    f'</div></div>'
    f'<div class="header-logo">{PAK_SVG}</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ─── LANGUAGE TOGGLE ──────────────────────────────────────────────────────────
_spacer, _col_en, _col_ur = st.columns([6, 1, 1])
with _col_en:
    if st.button("🇬🇧 EN", key="_btn_en", use_container_width=True, help="Switch to English"):
        st.session_state.lang = "English"
        st.rerun()
with _col_ur:
    if st.button("🇵🇰 UR", key="_btn_ur", use_container_width=True, help="Switch to Urdu / اردو"):
        st.session_state.lang = "Urdu"
        st.rerun()

t       = get_t()
is_urdu = get_is_urdu()
dir_cls = get_dir_cls()

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ─── TOP NAV ──────────────────────────────────────────────────────────────────
NAV = [
    ("home",     t["nav_home"],    "🏠"),
    ("chat",     t["nav_chat"],    "💬"),
    ("finder",   t["nav_finder"],  "📋"),
    ("tracker",  t["nav_tracker"], "🔍"),
    ("offices",  t["nav_offices"], "📍"),
    ("settings", t["nav_settings"],"⚙️"),
]
highlight = page if not page.startswith("card_") else "home"
ncols = st.columns(len(NAV))
for i, (pk, pl, pi) in enumerate(NAV):
    with ncols[i]:
        lbl = f"{pi} {pl}"
        if highlight == pk:
            st.markdown(f'<div class="top-nav-active">{lbl}</div>', unsafe_allow_html=True)
        else:
            if st.button(lbl, key=f"nav_{pk}", use_container_width=True):
                st.session_state.page = pk
                st.rerun()

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════════════════════════════
if page == "home":
    st.markdown(
        f'<div class="section-title">{t["services_title"]}</div>'
        f'<div class="section-sub">{t["services_sub"]}</div>',
        unsafe_allow_html=True,
    )
    for row in [CARDS[:3], CARDS[3:]]:
        cols = st.columns(3)
        for ci, card in enumerate(row):
            with cols[ci]:
                title    = t.get(card["title_key"], card["key"].upper())
                desc     = t.get(card["desc_key"], "")
                hist     = st.session_state.chat_history.get(card["key"], [])
                n_convos = len(hist) // 2
                prev_html = f'<div class="card-prev">💬 {n_convos} {t["prev_convos"]}</div>' if n_convos > 0 else ""
                st.markdown(
                    f'<div class="service-card">'
                    f'<div class="card-img-wrapper"><img src="{card["image_url"]}" alt="{title}" loading="lazy"/></div>'
                    f'<div class="card-accent-bar" style="background:{card["accent"]};"></div>'
                    f'<div class="card-content">'
                    f'<div class="card-icon-row"><span class="card-emoji">{card["emoji"]}</span>'
                    f'<span class="card-title">{title}</span></div>'
                    f'<div class="card-desc">{desc}</div>'
                    f'{prev_html}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
                if st.button(t["open_assistant"], key=f"open_{card['key']}", use_container_width=True):
                    st.session_state.page = f"card_{card['key']}"
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: CARD DETAIL
# ══════════════════════════════════════════════════════════════════════════════
elif page.startswith("card_"):
    card_key = page[5:]
    card     = next((c for c in CARDS if c["key"] == card_key), None)

    if not card:
        st.error("Service not found.")
        if st.button("← Back to Home"):
            st.session_state.page = "home"
            st.rerun()
    else:
        title   = t.get(card["title_key"], card_key.upper())
        desc    = t.get(card["desc_key"], "")
        api_key = st.session_state.openrouter_key

        if st.button(t["back_home"], key="back_card"):
            st.session_state.page = "home"
            st.rerun()
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        st.markdown(
            f'<div class="card-detail-header">'
            f'<div style="font-size:2.5rem;">{card["emoji"]}</div>'
            f'<div><div class="card-detail-title">{title}</div>'
            f'<div class="card-detail-desc">{desc}</div></div>'
            f'<div class="dedicated-badge">'
            f'<div style="width:9px;height:9px;background:{card["accent"]};border-radius:50%;"></div>'
            f'{t["dedicated_assistant"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if not api_key:
            st.warning(f"⚠️ {t['no_api']}")

        if card_key not in st.session_state.chat_history:
            st.session_state.chat_history[card_key] = []
        card_hist = st.session_state.chat_history[card_key]

        col_chat, col_qs = st.columns([3, 2], gap="medium")

        with col_qs:
            st.markdown(
                f'<div class="qs-panel">'
                f'<div class="qs-label">💡 {t["quick_questions"]}</div>'
                f'<div class="qs-hint">Click a question for an instant answer, or type your own in the chat.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            q_list = card.get("questions_ur" if is_urdu else "questions_en", card["questions_en"])
            for qi, q in enumerate(q_list):
                if st.button(f"▸ {q}", key=f"qs_{card_key}_{qi}", use_container_width=True):
                    if not api_key:
                        st.session_state.card_quick_reply[card_key] = (q, "Please add your OpenRouter API key in **API Settings** first.", "")
                    else:
                        with st.spinner("Answering..."):
                            reply, ctx = call_ai_with_rag(
                                [{"role": "user", "content": q}],
                                make_system(get_lang(), f"{title} — {desc}"),
                                api_key, q,
                            )
                        st.session_state.card_quick_reply[card_key] = (q, reply, ctx)
                    st.rerun()

            if card_key in st.session_state.card_quick_reply:
                qr   = st.session_state.card_quick_reply[card_key]
                aq   = qr[0]
                rt   = qr[1]
                rctx = qr[2] if len(qr) > 2 else ""
                st.markdown(
                    f'<div class="ai-answer-box" style="border-left-color:{card["accent"]};">'
                    f'<div class="ai-answer-label">🏛️ Answer</div>'
                    f'<div class="ai-answer-q">Q: {aq}</div>'
                    f'<div class="{dir_cls}">{rt}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if rctx and st.session_state.get("show_rag_ctx"):
                    preview = rctx[:300] + ("…" if len(rctx) > 300 else "")
                    st.markdown(
                        f'<div class="rag-ctx-box"><div class="rag-ctx-label">📚 {t["rag_context_label"]}</div>{preview}</div>',
                        unsafe_allow_html=True,
                    )
                if st.button("↓ Move to chat", key=f"to_chat_{card_key}", use_container_width=True):
                    ts = datetime.datetime.now().strftime("%H:%M")
                    card_hist.append({"user": aq, "bot": rt, "timestamp": ts, "rag_context": rctx})
                    st.session_state.chat_history[card_key] = card_hist
                    st.session_state.card_quick_reply.pop(card_key, None)
                    save_chat(st.session_state.session_id, card_hist, card_key, f"{title} — {aq[:30]}")
                    st.rerun()

        with col_chat:
            if not card_hist:
                st.markdown(
                    f'<div class="chat-welcome {dir_cls}">'
                    f'👋 Welcome! I\'m your dedicated <strong>{title}</strong> assistant. '
                    f'I answer questions about <strong>{desc.lower()}</strong>, required documents, fees, and step-by-step processes. '
                    f'Ask below or use a quick question on the right.'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            for turn in card_hist:
                render_turn(turn, card["emoji"], card["accent"])

            user_in = st.chat_input(t["chat_placeholder"], key=f"ci_{card_key}")
            if user_in:
                if not api_key:
                    st.error("Please configure your OpenRouter API key in API Settings first.")
                else:
                    ts   = datetime.datetime.now().strftime("%H:%M")
                    msgs = []
                    for h in card_hist[-4:]:
                        msgs += [{"role": "user", "content": h["user"]}, {"role": "assistant", "content": h["bot"]}]
                    msgs.append({"role": "user", "content": user_in})
                    with st.spinner("جواب تیار ہو رہا ہے..." if is_urdu else "Thinking..."):
                        resp, ctx = call_ai_with_rag(
                            msgs,
                            make_system(get_lang(), f"{title} — {desc}"),
                            api_key,
                            user_in,
                        )
                    card_hist.append({"user": user_in, "bot": resp, "timestamp": ts, "rag_context": ctx})
                    st.session_state.chat_history[card_key] = card_hist
                    save_chat(st.session_state.session_id, card_hist, card_key)
                    st.rerun()

            if card_hist:
                if st.button("🗑 Clear conversation", key=f"clear_{card_key}"):
                    st.session_state.chat_history[card_key] = []
                    st.session_state.card_quick_reply.pop(card_key, None)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: GENERAL CHAT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "chat":
    api_key = st.session_state.openrouter_key
    st.markdown(
        f'<div class="section-title">{"چیٹ اسسٹنٹ" if is_urdu else "Chat Assistant"}</div>'
        f'<div class="section-sub">{"پاکستانی سرکاری خدمات کے بارے میں کچھ بھی پوچھیں" if is_urdu else "Ask anything about Pakistani government services"}</div>',
        unsafe_allow_html=True,
    )
    if not api_key:
        st.warning(f"⚠️ {t['no_api']}")

    QUICK = {
        "English": ["CNIC renewal documents", "Emergency passport fee", "PTA device registration", "Asaan Account", "Driving license steps", "NTN registration"],
        "Urdu":    ["شناختی کارڈ تجدید", "ایمرجنسی پاسپورٹ", "PTA رجسٹریشن", "آسان اکاؤنٹ", "ڈرائیونگ لائسنس", "NTN رجسٹریشن"],
    }
    qcols = st.columns(3)
    for i, q in enumerate(QUICK[get_lang()]):
        with qcols[i % 3]:
            if st.button(q, key=f"qq_{i}", use_container_width=True):
                st.session_state["_pend"] = q

    main_hist = st.session_state.chat_history.get("main", [])
    if not main_hist:
        st.markdown(
            f'<div class="chat-welcome {dir_cls}"><div style="display:flex;gap:14px;">'
            f'<span style="font-size:2rem;flex-shrink:0;">🏛️</span>'
            f'<span>{t["chat_welcome"]}</span></div></div>',
            unsafe_allow_html=True,
        )

    for turn in main_hist:
        render_turn(turn)

    pend    = st.session_state.pop("_pend", None)
    user_in = st.chat_input(t["chat_placeholder"])
    if pend and not user_in:
        user_in = pend

    if user_in:
        if not api_key:
            st.error("Please configure your OpenRouter API key in API Settings first.")
        else:
            ts   = datetime.datetime.now().strftime("%H:%M")
            msgs = []
            for h in main_hist[-4:]:
                msgs += [{"role": "user", "content": h["user"]}, {"role": "assistant", "content": h["bot"]}]
            msgs.append({"role": "user", "content": user_in})
            with st.spinner("جواب تیار ہو رہا ہے..." if is_urdu else "Thinking..."):
                resp, ctx = call_ai_with_rag(msgs, make_system(get_lang()), api_key, user_in)
            main_hist.append({"user": user_in, "bot": resp, "timestamp": ts, "rag_context": ctx})
            st.session_state.chat_history["main"] = main_hist
            save_chat(st.session_state.session_id, main_hist, None)
            st.rerun()

    if main_hist:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑 Clear conversation"):
                st.session_state.chat_history["main"] = []
                st.rerun()
        with c2:
            if st.button("💾 Save & New"):
                st.session_state.session_id = new_session_id()
                st.session_state.chat_history["main"] = []
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SERVICE FINDER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "finder":
    st.markdown(
        f'<div class="section-title {dir_cls}">{t["nav_finder"]}</div>'
        f'<div class="section-sub">{"پروفائل بھریں — ذاتی ایکشن پلان پائیں" if is_urdu else "Fill your profile — get a personalised action plan"}</div>',
        unsafe_allow_html=True,
    )
    if st.button(t["back_home"], key="back_finder"):
        st.session_state.page = "home"
        st.rerun()
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    with st.form("finder_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<p style="font-size:0.88rem;font-weight:700;color:#065f46;margin-bottom:8px;">Personal</p>', unsafe_allow_html=True)
            age     = st.number_input("Age", 1, 100, 25, key="f_age")
            marital = st.selectbox("Marital Status", ["Single", "Married", "Divorced", "Widowed"], key="f_marital")
            res     = st.selectbox("Residence", ["Pakistan (Resident)", "Overseas Pakistani"], key="f_res")
        with c2:
            st.markdown('<p style="font-size:0.88rem;font-weight:700;color:#065f46;margin-bottom:8px;">Documents You Have</p>', unsafe_allow_html=True)
            has_cnic     = st.checkbox("Valid CNIC / SNIC",       key="f_cnic")
            has_passport = st.checkbox("Valid Passport",           key="f_pass")
            has_ntn      = st.checkbox("NTN / Active Tax Filer",  key="f_ntn")
            has_domicile = st.checkbox("Domicile Certificate",    key="f_dom")
            has_driving  = st.checkbox("Driving License",         key="f_drv")
            has_phone    = st.checkbox("Registered SIM / Mobile", key="f_phone")
        with c3:
            st.markdown('<p style="font-size:0.88rem;font-weight:700;color:#065f46;margin-bottom:8px;">Economic Status</p>', unsafe_allow_html=True)
            employment = st.selectbox("Employment", ["Student", "Unemployed", "Salaried", "Business Owner", "Freelancer", "Government Employee"], key="f_emp")
            income     = st.selectbox("Monthly Income (PKR)", ["Under 50,000", "50,000–100,000", "100,000–300,000", "Above 300,000"], key="f_inc")

        st.markdown('<p style="font-size:0.88rem;font-weight:700;color:#065f46;margin:14px 0 8px;">What do you need to do?</p>', unsafe_allow_html=True)
        goal = st.selectbox("Primary Goal", [
            "Get / Renew my CNIC", "Apply for a Passport", "Travel Abroad", "Open a Bank Account",
            "Register / Verify a Mobile Device (PTA)", "Register for Taxes (NTN / FBR)", "Get a Driving License",
            "Register a SIM Card", "Apply for Domicile Certificate", "Police Verification / Character Certificate",
            "Register a Property / Vehicle", "Access e-Khidmat Markaz Services"], key="f_goal")

        submitted = st.form_submit_button("Generate My Action Plan →", use_container_width=True)

    if submitted:
        if not st.session_state.openrouter_key:
            st.error(t["no_api"])
        else:
            profile = (
                f"Age: {age} | Marital: {marital} | Residence: {res}\n"
                f"Employment: {employment} | Income: {income}\n"
                f"CNIC: {has_cnic} | Passport: {has_passport} | NTN: {has_ntn} | "
                f"Domicile: {has_domicile} | Driving: {has_driving} | SIM: {has_phone}\n"
                f"Goal: {goal}"
            )
            prompt = (
                f"Pakistani citizen profile:\n{profile}\n\nProvide a complete action plan:\n"
                f"1. Eligibility Assessment\n2. Required Documents Checklist\n"
                f"3. Step-by-Step Process (numbered, with portal/office)\n4. Official Fees\n"
                f"5. Processing Time (normal & urgent)\n6. Pro Tips & Common Mistakes\n"
                f"7. Official Helpline & Portal\nBe specific, factual. Reply in {get_lang()}."
            )
            with st.spinner("Generating your personalised plan..."):
                resp, _ = call_ai_with_rag(
                    [{"role": "user", "content": prompt}],
                    make_system(get_lang()),
                    st.session_state.openrouter_key,
                    goal,
                )
            st.markdown(
                f'<div class="roadmap-card">'
                f'<div style="font-family:\'Playfair Display\',serif;font-size:1.3rem;font-weight:700;color:#065f46;margin-bottom:1rem;">'
                f'{"آپ کا ذاتی ایکشن پلان" if is_urdu else "Your Personalised Action Plan"}</div>'
                f'<div class="{dir_cls}" style="color:#111827;font-size:0.88rem;line-height:{"2.2" if is_urdu else "1.8"};">{resp}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: APP TRACKER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "tracker":
    st.markdown(
        f'<div class="section-title {dir_cls}">{t["tracker_title"]}</div>'
        f'<div class="section-sub">{"سرکاری درخواستوں کی حیثیت چیک کریں" if is_urdu else "Track your government applications"}</div>',
        unsafe_allow_html=True,
    )
    if st.button(t["back_home"], key="back_tracker"):
        st.session_state.page = "home"
        st.rerun()
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    svc  = st.selectbox("Select Service", list(TRACKER_INFO.keys()), key="trk_svc")
    info = TRACKER_INFO[svc]
    st.markdown(f'<div class="info-card"><div class="info-card-title">{svc}</div><div class="info-card-body">{info["description"]}</div></div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.88rem;font-weight:700;color:#065f46;margin:12px 0 8px;">How to Track:</p>', unsafe_allow_html=True)
    for i, step in enumerate(info["steps"], 1):
        st.markdown(
            f'<div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;">'
            f'<div class="step-num">{i}</div>'
            f'<div style="color:#374151;font-size:0.87rem;line-height:1.5;padding-top:3px;">{step}</div></div>',
            unsafe_allow_html=True,
        )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f'<div class="info-card" style="margin-top:1rem;"><div class="info-card-title" style="font-size:0.9rem;">Official Portal</div>'
            f'<div class="info-card-body"><a href="{info["portal"]}" target="_blank" style="color:#059669;font-weight:700;">{info["portal"]}</a></div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="info-card" style="margin-top:1rem;"><div class="info-card-title" style="font-size:0.9rem;">Helpline</div>'
            f'<div style="font-size:1.5rem;color:#059669;font-weight:800;padding-top:4px;">{info["helpline"]}</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown("---")
    st.markdown('<div class="section-title" style="font-size:1.2rem;">Complaint & Escalation</div>', unsafe_allow_html=True)
    for sname, data in COMPLAINTS.items():
        st.markdown(
            f'<div class="office-card"><div class="office-icon">{OFFICE_ICONS.get(sname,"🏛️")}</div>'
            f'<div class="office-info"><div class="office-name">{sname} — {data["body"]}</div>'
            f'<div class="office-addr"><a href="{data["portal"]}" target="_blank" style="color:#059669;font-weight:600;">{data["portal"]}</a></div>'
            f'<div class="office-phone">Helpline: {data["helpline"]}</div></div></div>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: FIND OFFICES
# ══════════════════════════════════════════════════════════════════════════════
elif page == "offices":
    st.markdown(
        f'<div class="section-title {dir_cls}">{t["offices_title"]}</div>'
        f'<div class="section-sub">{"نقشوں کے ساتھ سرکاری دفاتر تلاش کریں" if is_urdu else "Locate government offices with maps and directions"}</div>',
        unsafe_allow_html=True,
    )
    if st.button(t["back_home"], key="back_offices"):
        st.session_state.page = "home"
        st.rerun()
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        city = st.selectbox(t["city_label"], CITIES, key="off_city")
    with c2:
        svc_type = st.selectbox(t["service_type"], ["All"] + list(OFFICES.keys()), key="off_svc")
    with c3:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        st.button(t["find_offices"], use_container_width=True)

    if city == "Other":
        st.info("For unlisted cities, call:\n• **NADRA:** 051-111-786-100\n• **Passport:** 111-777-788\n• **FBR:** 111-772-772\n• **PTA:** 0800-5500")
    else:
        svcs  = list(OFFICES.keys()) if svc_type == "All" else [svc_type]
        found = False
        for svc in svcs:
            offices = OFFICES.get(svc, {}).get(city, [])
            if not offices:
                continue
            found = True
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;margin:1.2rem 0 0.8rem;">'
                f'<span style="font-size:1.4rem;">{OFFICE_ICONS.get(svc,"🏛️")}</span>'
                f'<span style="font-family:\'Playfair Display\',serif;font-size:1.15rem;color:#065f46;font-weight:700;">{svc} Offices — {city}</span></div>',
                unsafe_allow_html=True,
            )
            for off in offices:
                search_q = f"{off['name']}, {city}, Pakistan".replace(" ", "+").replace(",", "%2C")
                maps_url = f"https://www.google.com/maps/search/?api=1&query={search_q}"
                dir_url  = f"https://www.google.com/maps/dir/?api=1&destination={off['lat']},{off['lng']}&travelmode=driving"
                st.markdown(
                    f'<div class="office-card">'
                    f'<div class="office-icon">{OFFICE_ICONS.get(svc,"🏛️")}</div>'
                    f'<div class="office-info">'
                    f'<div class="office-name">{off["name"]}</div>'
                    f'<div class="office-addr">📍 {off["address"]}</div>'
                    f'<div class="office-phone">📞 {off["phone"]}</div>'
                    f'<div style="margin-top:8px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">'
                    f'<span class="office-tag">⏰ {off["hours"]}</span>'
                    f'<a href="{maps_url}" target="_blank" class="maps-btn">🗺️ Open in Maps</a>'
                    f'<a href="{dir_url}" target="_blank" class="maps-btn">🧭 Get Directions</a>'
                    f'</div></div></div>',
                    unsafe_allow_html=True,
                )
        if not found:
            st.info(f"No office data for **{svc_type}** in **{city}**. Please call the national helpline.")

    st.markdown("---")
    st.markdown('<div class="section-title" style="font-size:1.2rem;">National Helplines</div>', unsafe_allow_html=True)
    hcols = st.columns(3)
    for i, (icon, name, num, desc) in enumerate(HELPLINES):
        with hcols[i % 3]:
            st.markdown(
                f'<div class="metric-tile" style="margin-bottom:0.8rem;">'
                f'<div style="font-size:1.5rem;">{icon}</div>'
                f'<div class="metric-label">{name}</div>'
                f'<div class="metric-value">{num}</div>'
                f'<div style="font-size:0.65rem;color:#9ca3af;margin-top:4px;">{desc}</div></div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: API SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "settings":
    st.markdown(
        f'<div class="section-title {dir_cls}">{t["settings_title"]}</div>'
        f'<div class="section-sub">{t["settings_info"]}</div>',
        unsafe_allow_html=True,
    )
    if st.button(t["back_home"], key="back_settings"):
        st.session_state.page = "home"
        st.rerun()
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    env_key_present = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    if env_key_present:
        st.success("✅ OpenRouter API key is configured via environment variable. No action needed.")
    else:
        st.info("ℹ️ Enter your OpenRouter API key below — it will be remembered automatically across refreshes.")

    # Only show RAG status if it's working — never show errors
    if rag_ready:
        st.markdown(
            f'<div class="info-card" style="border-left:4px solid #059669;">'
            f'<div class="info-card-title">✅ {t["rag_status"]}</div>'
            f'<div class="info-card-body">{rag_status_msg}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if not env_key_present:
        st.markdown(
            '<div class="info-card" style="border-left:4px solid #059669;">'
            '<div class="info-card-title">How to Get Your Free OpenRouter API Key (3 Minutes)</div>'
            '<div class="info-card-body">'
            '<b>Step 1:</b> Go to <a href="https://openrouter.ai/keys" target="_blank" style="color:#059669;font-weight:700;">openrouter.ai/keys</a><br><br>'
            '<b>Step 2:</b> Click <b>Sign Up</b> — use Google or GitHub (completely free, no credit card)<br><br>'
            '<b>Step 3:</b> Click <b>Create Key</b><br><br>'
            '<b>Step 4:</b> Copy the key <span style="background:#D1FAE5;padding:2px 8px;border-radius:4px;color:#065f46;font-family:monospace;font-size:0.85rem;">sk-or-v1-...</span> and paste it below<br><br>'
            '<b>Step 5:</b> Click <b>Save Settings</b> — the AI model used is 100% free.'
            '</div></div>',
            unsafe_allow_html=True,
        )

        with st.form("api_form"):
            new_key = st.text_input(
                "OpenRouter API Key",
                value=st.session_state.openrouter_key,
                type="password",
                placeholder="sk-or-v1-...",
                help="Saved to your browser — persists across page refreshes automatically.",
            )
            st.markdown(
                '<p style="font-size:0.8rem;color:#6b7280;margin-top:-6px;margin-bottom:12px;">'
                'ℹ️ Your key is saved in your browser storage and loaded automatically on every visit.</p>',
                unsafe_allow_html=True,
            )
            save_btn = st.form_submit_button(t["save_settings"], use_container_width=True)

        if save_btn:
            cleaned_key = new_key.strip()
            st.session_state.openrouter_key = cleaned_key
            if cleaned_key:
                # Save key to localStorage so it persists across refreshes
                components.html(f"""
                <script>
                try {{
                    localStorage.setItem("{_LS_KEY}", "{cleaned_key}");
                }} catch(e) {{}}
                </script>
                """, height=0)
                st.success(t["settings_saved"])
            else:
                # Clear key from localStorage
                components.html(f"""
                <script>
                try {{
                    localStorage.removeItem("{_LS_KEY}");
                }} catch(e) {{}}
                </script>
                """, height=0)
                st.warning("OpenRouter key is empty. AI will not work without it.")

    if st.session_state.openrouter_key:
        st.markdown("---")
        col_test, col_clear = st.columns(2)
        with col_test:
            if st.button("🔌 Test AI Connection"):
                with st.spinner("Testing..."):
                    resp, _ = call_ai_with_rag(
                        [{"role": "user", "content": "Reply with exactly: Civic Navigation is ready!"}],
                        "You are a test bot. Follow instructions exactly.",
                        st.session_state.openrouter_key,
                        "test",
                    )
                if "ready" in resp.lower() or "civic" in resp.lower():
                    st.success(f"✅ Connected! Response: {resp}")
                else:
                    st.info(f"Connection works. Response: {resp}")
        with col_clear:
            if st.button("🗑 Clear Saved Key"):
                st.session_state.openrouter_key = ""
                components.html(f"""
                <script>
                try {{
                    localStorage.removeItem("{_LS_KEY}");
                }} catch(e) {{}}
                </script>
                """, height=0)
                st.success("Key cleared from browser storage.")
                st.rerun()