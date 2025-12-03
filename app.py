import streamlit as st
from openai import OpenAI
import os
import pdfplumber
from fpdf import FPDF
import json
from datetime import datetime

# -------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------
st.set_page_config(
    page_title="SMU COX Case Study Bot",
    page_icon="🎓",
    layout="wide"
)

SMU_BLUE = "#0033A0"

# KEEP ORIGINAL UI COLORS AND STYLING
st.markdown("""
<style>
    .stApp { 
        background-color: #FFFFFF !important; 
    }
    h1, h2, h3, label { 
        color: #0033A0 !important; 
    }
    p, div { 
        color: #000000 !important; 
    }
    .left-panel {
        background-color: #F8F9FA;
        padding: 20px;
        border-radius: 10px;
        border: 2px solid #0033A0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .role-header {
        background: linear-gradient(135deg, #0033A0 0%, #0055CC 100%);
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .role-header h3 {
        color: #FFFFFF !important;
        margin: 0;
        font-weight: 600;
    }
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    div[data-testid="stChatInput"] {
        border-radius: 10px;
        border: 2px solid #0033A0;
    }
    .stChatMessage {
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    /* Hide empty container */
    .element-container:has(> .stMarkdown:empty) {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------
# API KEY HANDLING
# -------------------------------------------------------
# Try to get API key from Streamlit secrets first (for cloud deployment)
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except:
    # Fallback to demo key for local testing
    api_key = "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"

client = OpenAI(api_key=api_key)

# -------------------------------------------------------
# HELPERS
# -------------------------------------------------------
def extract_text_from_file(uploaded_file):
    if uploaded_file is None:
        return ""
    if uploaded_file.name.lower().endswith(".pdf"):
        text = ""
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text.strip()
    elif uploaded_file.name.lower().endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")
    return ""


def extract_roles_and_people(case_text):
    """
    Extract ONLY meaningful roles:
    - Named individuals (e.g., Maya, Jordan)
    - Essential roles explicitly referenced (Barista)
    EXCLUDE:
    - Customers
    - Mobile order customers
    - POS operators
    - Any generic implicit actor
    """

    system_prompt = """
You are an expert case-study analyzer.

Extract ONLY the meaningful human roles in the case study.

VALID ROLES TO RETURN:
1. Named individuals (e.g., Maya, Jordan)
2. Essential operational human roles explicitly mentioned (e.g., Barista)

DO NOT RETURN:
- Customer / customers
- Mobile order customers
- POS operators
- Cashier (unless explicitly named as a character)
- Inventory managers (unless named)
- Quality check staff
- Any system/device role
- Any implied generic role

RETURN STRICT JSON ONLY:

{
  "roles": [
    {"name": "Person Name or Role", "title": "Their Title"}
  ]
}

RULES:
- If a name & title appear:
      "Maya, the owner" → {"name": "Maya", "title": "Owner"}
- If only a role appears and it's valid (Barista):
      {"name": "Barista", "title": "Barista"}

DO NOT include customers or other generic roles.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": case_text}
        ]
    )

    raw = response.choices[0].message.content.strip()

    try:
        data = json.loads(raw)
        return data["roles"]
    except:
        return [{"name": "General Role", "title": "General Role"}]


def build_system_prompt(role, case_text):
    return f"""
You are **{role['name']} ({role['title']})**.

INTRODUCTION RULE:
If the user greets you or asks who you are, you MUST:
- Introduce yourself (name + title)
- Describe your responsibilities based on the case study
- Explain your concerns, priorities, and involvement

Use only facts from the case study.

CASE STUDY:
{case_text}
"""


def get_role_description(role, case_text):
    """
    Extract a brief description of the role from the case study
    """
    system_prompt = f"""
You are analyzing a case study to provide a brief description of a specific role.

Role: {role['name']} ({role['title']})

Based on the case study, provide a 2-3 sentence description of this role that includes:
1. Their main responsibilities or position
2. Their key challenges or concerns in the case
3. Their relevance to the scenario

Keep it concise and factual. Return ONLY the description text, no extra formatting.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": case_text}
            ]
        )
        return response.choices[0].message.content.strip()
    except:
        return f"{role['name']} is a key stakeholder in this case study."


def get_case_summary(case_text):
    """
    Extract a brief summary of the case study
    """
    system_prompt = """
You are analyzing a case study to provide a brief overview.

Provide a 2-3 sentence summary that captures:
1. The main situation or context
2. The primary challenge or issue
3. What needs to be addressed

Keep it concise and neutral. Return ONLY the summary text, no extra formatting.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": case_text}
            ]
        )
        return response.choices[0].message.content.strip()
    except:
        return "A business case study scenario requiring analysis and decision-making."


def export_chat_to_pdf(role_name, chat_history):
    """Export chat history to PDF"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    # Title
    title = f"Chat with {role_name}"
    pdf.cell(0, 10, title.encode('latin-1', 'replace').decode('latin-1'), ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 10, f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(10)
    
    # Chat messages
    pdf.set_font("Arial", "", 11)
    for msg in chat_history:
        role = "You" if msg["role"] == "user" else role_name.encode('latin-1', 'replace').decode('latin-1')
        pdf.set_font("Arial", "B", 11)
        pdf.multi_cell(0, 8, f"{role}:")
        pdf.set_font("Arial", "", 11)
        # Handle special characters in content
        content = msg["content"].encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 6, content)
        pdf.ln(5)
    
    return pdf.output(dest="S").encode("latin-1", errors="replace")


# -------------------------------------------------------
# SESSION STATE INIT
# -------------------------------------------------------
if "case_study_text" not in st.session_state:
    st.session_state.case_study_text = ""

if "roles" not in st.session_state:
    st.session_state.roles = []

if "selected_role" not in st.session_state:
    st.session_state.selected_role = None

# Each role gets its own chat
if "role_chats" not in st.session_state:
    st.session_state.role_chats = {}

# Track if roles have been extracted
if "roles_extracted" not in st.session_state:
    st.session_state.roles_extracted = False

# Store role descriptions
if "role_descriptions" not in st.session_state:
    st.session_state.role_descriptions = {}

# Store case summary
if "case_summary" not in st.session_state:
    st.session_state.case_summary = ""

# Store PDF data for export
if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = None

if "pdf_filename" not in st.session_state:
    st.session_state.pdf_filename = ""


# -------------------------------------------------------
# LAYOUT
# -------------------------------------------------------
left, center, right = st.columns([1, 2, 1])

# -------------------------------------------------------
# RIGHT PANEL – CASE STUDY
# -------------------------------------------------------
with right:
    st.markdown("<h2>Case Study</h2>", unsafe_allow_html=True)

    upload = st.file_uploader("Upload Case Study", type=["pdf", "txt"], key="file_uploader")
    manual = st.text_area("Or paste case study text", height=200, key="manual_text")

    # Button to process case study
    if st.button("📚 Load & Extract Roles", use_container_width=True, type="primary"):
        case_text = ""
        
        if upload:
            case_text = extract_text_from_file(upload)
        elif manual.strip():
            case_text = manual.strip()
        
        if case_text:
            st.session_state.case_study_text = case_text
            
            # Extract roles only once
            if not st.session_state.roles_extracted:
                with st.spinner("Extracting roles and analyzing case study..."):
                    # Extract roles
                    st.session_state.roles = extract_roles_and_people(case_text)
                    st.session_state.roles_extracted = True
                    
                    if st.session_state.roles:
                        # Get case summary
                        st.session_state.case_summary = get_case_summary(case_text)
                        
                        # Get description for each role
                        for r in st.session_state.roles:
                            label = f"{r['name']} ({r['title']})"
                            st.session_state.role_descriptions[label] = get_role_description(r, case_text)
                            
                            # Initialize chat for all roles
                            if label not in st.session_state.role_chats:
                                st.session_state.role_chats[label] = []
                        
                        st.session_state.selected_role = st.session_state.roles[0]
                
                st.success(f"✅ Loaded! Found {len(st.session_state.roles)} roles.")
                st.rerun()
        else:
            st.error("Please upload a file or paste text first!")

    # Show case study if loaded
    if st.session_state.case_study_text and st.session_state.roles:
        st.markdown("---")
        
        # Case Study Summary
        st.markdown("**📋 Case Study Overview:**")
        st.markdown(st.session_state.case_summary)
        
        st.markdown("---")
        
        # Button to reset and start over
        if st.button("🔄 Reset All & Load New Case", use_container_width=True):
            st.session_state.case_study_text = ""
            st.session_state.roles = []
            st.session_state.selected_role = None
            st.session_state.role_chats = {}
            st.session_state.roles_extracted = False
            st.session_state.role_descriptions = {}
            st.session_state.case_summary = ""
            st.rerun()


# -------------------------------------------------------
# LEFT PANEL – ROLES
# -------------------------------------------------------
with left:
    st.markdown("<div class='left-panel'>", unsafe_allow_html=True)
    st.markdown("<h2>👥 Available Roles</h2>", unsafe_allow_html=True)
    
    if st.session_state.roles:
        st.markdown(f"**{len(st.session_state.roles)} roles found**")
        st.markdown("---")
        
        for r in st.session_state.roles:
            label = f"{r['name']} ({r['title']})"
            selected = (st.session_state.selected_role == r)
            
            if selected:
                btn_type = "primary"
                btn_label = f"✅ {label}"
            else:
                btn_type = "secondary"
                btn_label = label

            if st.button(btn_label, use_container_width=True, key=f"role_btn_{label}", type=btn_type):
                st.session_state.selected_role = r

                # Initialize chat for role if it doesn't exist
                if label not in st.session_state.role_chats:
                    st.session_state.role_chats[label] = []
                
                st.rerun()
        
        # Show selected role details below the roles
        st.markdown("---")
        if st.session_state.selected_role:
            current_label = f"{st.session_state.selected_role['name']} ({st.session_state.selected_role['title']})"
            st.markdown(f"**👤 About {st.session_state.selected_role['name']}:**")
            if current_label in st.session_state.role_descriptions:
                st.markdown(st.session_state.role_descriptions[current_label])
    else:
        st.info("Load a case study to see available roles")

    st.markdown("</div>", unsafe_allow_html=True)


# -------------------------------------------------------
# CENTER PANEL – ROLE-BASED CHAT
# -------------------------------------------------------
with center:

    st.markdown("<h1>SMU COX Case Study Bot</h1>", unsafe_allow_html=True)

    if st.session_state.selected_role and st.session_state.roles:
        current_label = f"{st.session_state.selected_role['name']} ({st.session_state.selected_role['title']})"
        
        # Initialize chat for current role if it doesn't exist
        if current_label not in st.session_state.role_chats:
            st.session_state.role_chats[current_label] = []

        # -------------------------------------------------------
        # ROLE DISPLAY AND ACTION BUTTONS (Display only, no dropdown)
        # -------------------------------------------------------
        st.markdown("<div class='role-header'>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.markdown(f"### 💬 Talking to: **{current_label}**")
        
        with col2:
            if st.button("📄 Export PDF", use_container_width=True, key="export_btn"):
                if st.session_state.role_chats[current_label]:
                    pdf_bytes = export_chat_to_pdf(current_label, st.session_state.role_chats[current_label])
                    st.session_state.pdf_data = pdf_bytes
                    st.session_state.pdf_filename = f"chat_{current_label.replace(' ', '_').replace('(', '').replace(')', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                else:
                    st.warning("No messages to export")
            
            # Show download button if PDF was generated
            if "pdf_data" in st.session_state and st.session_state.pdf_data:
                st.download_button(
                    label="⬇️ Download PDF",
                    data=st.session_state.pdf_data,
                    file_name=st.session_state.pdf_filename,
                    mime="application/pdf",
                    key="download_pdf",
                    use_container_width=True
                )
        
        with col3:
            if st.button("🔄 Reset", use_container_width=True, key="reset_btn"):
                st.session_state.role_chats[current_label] = []
                st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")

        # -------------------------------------------------------
        # CHAT DISPLAY
        # -------------------------------------------------------
        # Display chat for THIS ROLE ONLY
        for msg in st.session_state.role_chats[current_label]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # -------------------------------------------------------
        # USER INPUT
        # -------------------------------------------------------
        user_input = st.chat_input("Ask something...")

        if user_input:
            # Add user message
            st.session_state.role_chats[current_label].append({"role": "user", "content": user_input})

            # Display user message
            with st.chat_message("user"):
                st.markdown(user_input)

            # Generate response
            prompt = build_system_prompt(st.session_state.selected_role, st.session_state.case_study_text)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}] + st.session_state.role_chats[current_label]
            )

            reply = response.choices[0].message.content
            st.session_state.role_chats[current_label].append({"role": "assistant", "content": reply})

            # Display assistant message
            with st.chat_message("assistant"):
                st.markdown(reply)

    elif not st.session_state.case_study_text:
        st.info("👉 Please upload or paste a case study in the right panel to get started.")
    else:
        st.info("👈 Select a role from the left panel to start chatting.")