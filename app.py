import streamlit as st
import pandas as pd
import sqlite3
import random
import time
import os
from datetime import datetime

# ==========================================
# 1. SETUP & CONFIG
# ==========================================
st.set_page_config(page_title="WoxPrint System", page_icon="🖨️", layout="wide")

# Force absolute path for reliability
FOLDER_PATH = os.path.join(os.getcwd(), "uploaded_files")
os.makedirs(FOLDER_PATH, exist_ok=True)

# Hotjar Tracking (Technical Rigor)
hotjar_id = "5738291"
st.components.v1.html(f"""<script>(function(h,o,t,j,a,r){{h.hj=h.hj||function(){{(h.hj.q=h.hj.q||[]).push(arguments)}};h._hjSettings={{hjid:{hotjar_id},hjsv:6}};a=o.getElementsByTagName('head')[0];r=o.createElement('script');r.async=1;r.src=t+h._hjSettings.hjid+j+h._hjSettings.hjsv;a.appendChild(r);}})(window,document,'https://static.hotjar.com/c/hotjar-','.js?sv=');</script>""", height=0, width=0)

# ==========================================
# 2. BACKEND LOGIC
# ==========================================
# CHANGED DB NAME TO 'v2' TO FIX YOUR CRASH
DB_NAME = 'woxprint_v2.db'

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # Creates table with CORRECT 8 columns
        c.execute('''CREATE TABLE IF NOT EXISTS jobs
                     (token TEXT PRIMARY KEY, filename TEXT, type TEXT, urgent INTEGER, 
                      pages INTEGER, cost INTEGER, status TEXT, timestamp DATETIME)''')
        conn.commit()
        conn.close()
    except: pass

def add_job(filename, print_type, is_urgent, pages, cost):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    token = f"WP-{random.randint(1000, 9999)}"
    c.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
              (token, filename, print_type, 1 if is_urgent else 0, pages, cost, "QUEUED", datetime.now()))
    conn.commit()
    conn.close()
    return token

def mark_as_done(token):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE jobs SET status='COMPLETED' WHERE token=?", (token,))
    conn.commit()
    conn.close()

def count_pages_safe(file_obj):
    try:
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(file_obj)
        return len(pdf_reader.pages)
    except: return 1

init_db()

# Session State for Navigation
if 'payment_step' not in st.session_state: st.session_state.payment_step = False
if 'order_details' not in st.session_state: st.session_state.order_details = {}

# ==========================================
# 3. SIDEBAR
# ==========================================
st.sidebar.title("🖨️ WoxPrint")
page = st.sidebar.radio("Navigation", ["Student Portal", "Station In-Charge"])
st.sidebar.info("System Online ✅")

# ==========================================
# 4. STUDENT PORTAL
# ==========================================
if page == "Student Portal":
    
    # --- SCREEN 1: UPLOAD ---
    if not st.session_state.payment_step:
        st.title("Student Printing Portal")
        st.markdown("Upload your assignment to the queue.")
        
        try:
            conn = sqlite3.connect(DB_NAME)
            queue_len = len(pd.read_sql_query("SELECT * FROM jobs WHERE status='QUEUED'", conn))
            conn.close()
        except: queue_len = 0
        
        col1, col2 = st.columns(2)
        col1.metric("Students in Queue", f"{queue_len}")
        col2.metric("Estimated Wait", f"{queue_len * 2} mins")
        
        st.divider()
        
        uploaded_file = st.file_uploader("Upload PDF", type=['pdf'])
        
        if uploaded_file:
            with st.spinner("Counting pages..."):
                time.sleep(0.5)
                pages = count_pages_safe(uploaded_file)
            
            st.success(f"Detected {pages} Pages.")
            
            st.subheader("Print Settings")
            c1, c2 = st.columns(2)
            with c1:
                p_count = st.number_input("Number of Pages", min_value=1, value=pages)
                p_type = st.radio("Color Mode", ["Black & White (₹4)", "Color (₹15)"])
            with c2:
                st.write("")
                st.write("")
                is_urgent = st.checkbox("⚡ Urgent Priority (+₹5)")
            
            price = 15 if "Color" in p_type else 4
            total = (p_count * price) + (5 if is_urgent else 0)
            
            st.info(f"### Total Bill: ₹{total}")
            
            if st.button("Proceed to Payment", type="primary"):
                st.session_state.order_details = {
                    "file": uploaded_file, "pages": p_count, "type": p_type,
                    "urgent": is_urgent, "cost": total
                }
                st.session_state.payment_step = True
                st.rerun()

    # --- SCREEN 2: PAYMENT GATEWAY (WITH QR) ---
    else:
        st.title("Secure Payment")
        total_cost = st.session_state.order_details['cost']
        st.markdown(f"**Amount to Pay: ₹{total_cost}**")
        
        method = st.radio("Payment Method", ["📱 Scan UPI QR", "💳 Credit/Debit Card", "🆔 UPI ID"])
        
        # --- NEW QR CODE FEATURE ---
        if method == "📱 Scan UPI QR":
            col1, col2 = st.columns([1, 2])
            with col1:
                # Generates a dynamic QR code for the exact amount
                # Uses a public QR API (No extra install needed)
                qr_data = f"upi://pay?pa=woxprint@upi&pn=WoxPrintStation&am={total_cost}&cu=INR"
                st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={qr_data}", caption="Scan with GPay/PhonePe")
            with col2:
                st.info("1. Open any UPI App\n2. Scan this QR\n3. Click 'Confirm Payment' below")
        
        elif method == "🆔 UPI ID":
            st.text_input("Enter UPI ID (e.g. student@oksbi)")
            
        else:
            c1, c2 = st.columns(2)
            c1.text_input("Card Number")
            c2.text_input("CVV", type="password")
            
        st.write("---")
        b1, b2 = st.columns(2)
        if b1.button("Cancel"):
            st.session_state.payment_step = False
            st.rerun()
            
        if b2.button("Confirm Payment", type="primary"):
            with st.spinner("Verifying Transaction..."):
                time.sleep(2)
            
            det = st.session_state.order_details
            f = det['file']
            f.seek(0)
            with open(os.path.join(FOLDER_PATH, f.name), "wb") as file: 
                file.write(f.getbuffer())
                
            token = add_job(f.name, det['type'], det['urgent'], det['pages'], det['cost'])
            
            st.balloons()
            st.session_state.payment_step = False
            st.success("Payment Successful!")
            st.success(f"### Token: {token}")

# ==========================================
# 5. ADMIN PORTAL
# ==========================================
elif page == "Station In-Charge":
    st.title("Station Dashboard")
    
    pwd = st.text_input("Admin Password", type="password")
    st.caption("🔑 Prototype Access: Password is **admin123**")
    if pwd == "admin123":
        try:
            conn = sqlite3.connect(DB_NAME)
            df = pd.read_sql_query("SELECT * FROM jobs WHERE status='QUEUED' ORDER BY urgent DESC", conn)
            conn.close()
        except: df = pd.DataFrame()
        
        if not df.empty:
            st.write(f"Pending Jobs: {len(df)}")
            
            for i, row in df.iterrows():
                with st.container():
                    c1, c2, c3, c4 = st.columns([2, 3, 2, 2])
                    
                    with c1:
                        st.subheader(row['token'])
                        if row['urgent']: st.error("URGENT")
                    
                    with c2:
                        st.write(f"**{row['filename']}**")
                        st.caption(f"{row['type']} | {row['pages']} Pages")
                    
                    with c3:
                        path = os.path.join(FOLDER_PATH, row['filename'])
                        if st.button("🖨️ Print", key=f"p{i}"):
                            if os.path.exists(path):
                                try: 
                                    os.startfile(path, "print")
                                    st.toast("Sent to Printer!")
                                except: st.error("Printer Error")
                    
                    with c4:
                        if st.button("Done ✅", key=f"d{i}"):
                            mark_as_done(row['token'])
                            st.rerun()
                    st.divider()
        else:
            st.info("Queue is empty.")