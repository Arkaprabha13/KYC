import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
from pydantic import BaseModel
from typing import Optional, List
import io
import pandas as pd
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Gemini KYC Data Extractor Pro",
    page_icon="📄",
    layout="wide"
)

# --- Constants ---
EXCEL_FILE_PATH = "kyc_database.xlsx"

# --- Pydantic Schema for KYC Data Structure ---
class KYCFormData(BaseModel):
    """Structured schema for KYC form data extraction"""
    document_title: Optional[str]
    society_name: Optional[str]
    control_number: Optional[str]
    name: Optional[str]
    father_husband_name: Optional[str]
    designation: Optional[str]
    bill_unit_number: Optional[str]
    department: Optional[str]
    sr_number: Optional[str]
    office_address: Optional[str]
    residential_address: Optional[str]
    date_of_birth: Optional[str]
    date_of_appointment: Optional[str]
    mobile_number: Optional[str]
    pan_number: Optional[str]
    aadhar_number: Optional[str]
    bank_name: Optional[str]
    branch_name: Optional[str]
    branch_code: Optional[str]
    account_number: Optional[str]
    ifsc_code: Optional[str]
    nominee_name: Optional[str]
    nominee_relation: Optional[str]
    nominee_dob: Optional[str]
    nominee_aadhar: Optional[str]
    nominee_pan: Optional[str]
    confidence_score: Optional[float]
    model_used: Optional[str]

# Define the column order for the Excel file
EXCEL_COLUMNS = list(KYCFormData.model_fields.keys())

# --- Excel Database Functions ---
def create_excel_file():
    """Creates the Excel file with proper headers if it doesn't exist"""
    if not os.path.exists(EXCEL_FILE_PATH):
        df = pd.DataFrame(columns=EXCEL_COLUMNS)
        df.to_excel(EXCEL_FILE_PATH, index=False)
        st.success(f"✅ Created new database file: {EXCEL_FILE_PATH}")
        return df
    return pd.read_excel(EXCEL_FILE_PATH)

def load_excel_data():
    """Loads existing Excel data or creates new file"""
    return create_excel_file()

def save_to_excel(data_dict):
    """Saves the KYC data to Excel file"""
    try:
        # Load existing data
        df = load_excel_data()
        
        # Create new record DataFrame
        new_record = pd.DataFrame([data_dict])
        
        # Ensure all columns are present in the correct order
        for col in EXCEL_COLUMNS:
            if col not in new_record.columns:
                new_record[col] = None
        
        new_record = new_record[EXCEL_COLUMNS]
        
        # Append to existing data
        df = pd.concat([df, new_record], ignore_index=True)
        
        # Save to Excel
        df.to_excel(EXCEL_FILE_PATH, index=False)
        
        st.success(f"✅ Data successfully saved to {EXCEL_FILE_PATH}")
        return True
    except Exception as e:
        st.error(f"❌ Error saving to Excel: {e}")
        return False

def download_excel_file():
    """Prepares Excel file for download"""
    try:
        df = load_excel_data()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='KYC_Data', index=False)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"Error preparing Excel download: {e}")
        return None

# --- Gemini API Extraction Logic ---
def enhanced_gemini_extraction(image: Image.Image):
    """
    Extracts data from a KYC form image using multiple Gemini models for best results.
    """
    models_to_try = [
        'gemini-1.5-pro-latest',
        'gemini-1.5-flash-latest',
    ]
    
    # Comprehensive prompt for high-accuracy extraction
    prompt = """
    You are an expert AI data extraction specialist for KYC (Know Your Customer) forms.
    Your task is to analyze the provided KYC form image and extract ALL visible information into a structured JSON format with extreme accuracy.

    Key Information to Extract:
    - PERSONAL: Full name, Father's/Husband's name, Date of birth, Residential address, Mobile number.
    - EMPLOYMENT: Control number, Designation, Bill unit number, Department, S.R. number, Office address, Date of appointment.
    - IDENTITY DOCS: PAN number, Aadhar number.
    - BANKING: Bank name, Branch name, Branch code, Account number, IFSC code.
    - NOMINEE: Nominee name, Relation, Date of birth, Aadhar, PAN.

    Instructions:
    - Extract text precisely as it appears, even with minor OCR errors.
    - Standardize dates to DD/MM/YYYY format if possible.
    - If a field is blank or unreadable, use a null value.
    - Provide a confidence score (0.0 to 1.0) reflecting the overall accuracy of the extraction.
    - Distinguish clearly between handwritten and printed text values and associate them with the correct fields.
    - Return the data strictly following the provided JSON schema.
    """
    
    best_result = None
    highest_confidence = -1.0
    errors = []

    # Resize image for optimal performance
    image.thumbnail([2048, 2048], Image.Resampling.LANCZOS)
    
    for model_name in models_to_try:
        try:
            st.write(f"⚙️ Trying model: `{model_name}`...")
            model = genai.GenerativeModel(model_name)
            
            response = model.generate_content(
                [prompt, image],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=KYCFormData
                )
            )
            
            result_data = json.loads(response.text)
            confidence = result_data.get('confidence_score', 0.0) or 0.0
            
            # If this result is better, store it
            if confidence > highest_confidence:
                highest_confidence = confidence
                best_result = result_data
                best_result['model_used'] = model_name

            # If we get a very confident result, we can stop early
            if confidence > 0.98:
                st.write("✅ High confidence result achieved. Finalizing...")
                break

        except Exception as e:
            error_message = f"Model `{model_name}` failed: {e}"
            errors.append(error_message)
            st.warning(error_message)
            continue
            
    if not best_result and errors:
        st.error("All models failed to process the image. Please check the API key, quotas, and image quality.")

    return best_result

# --- Streamlit App UI ---
st.title("📄 Gemini KYC Data Extractor Pro")
st.markdown("Upload a KYC form image to automatically extract, review, edit, and save the information.")

# Initialize session state variables
if 'api_key_valid' not in st.session_state:
    st.session_state.api_key_valid = False
if 'extracted_data' not in st.session_state:
    st.session_state.extracted_data = None
if 'edited_data' not in st.session_state:
    st.session_state.edited_data = None

# --- Sidebar: API Key and Database Viewer ---
with st.sidebar:
    st.header("🔑 API Configuration")
    api_key = st.text_input("Enter your Google Gemini API Key", type="password")

    if st.button("Validate and Set API Key"):
        if api_key:
            try:
                genai.configure(api_key=api_key)
                # Test the key by listing models
                models = [m for m in genai.list_models()]
                st.session_state.api_key_valid = True
                st.success("API Key is valid!")
            except Exception as e:
                st.session_state.api_key_valid = False
                st.error(f"Invalid API Key. Error: {e}")
        else:
            st.warning("Please enter an API key.")
    
    st.markdown("---")
    
    # Database Management Section
    st.header("📊 KYC Database")
    
    if st.session_state.api_key_valid:
        # Initialize Excel file
        df = load_excel_data()
        
        # Display database stats
        st.metric("Total Records", len(df))
        
        # Refresh button
        if st.button("🔄 Refresh Database"):
            st.rerun()
        
        # Download database button
        excel_data = download_excel_file()
        if excel_data:
            st.download_button(
                label="📥 Download Database",
                data=excel_data,
                file_name="kyc_database.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # Display database in tabular format
        with st.expander("📋 View Database Table", expanded=False):
            if len(df) > 0:
                st.dataframe(df, use_container_width=True, height=300)
            else:
                st.info("No records found. Extract some KYC data to populate the database.")
    else:
        st.info("Validate your API key to access database features.")

# --- Main App Body ---
if st.session_state.api_key_valid:
    st.header("1. Upload Your KYC Form")
    uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        col1, col2 = st.columns(2)
        with col1:
            st.image(uploaded_file, caption="Uploaded KYC Form", use_column_width=True)

        with col2:
            if st.button("🚀 Extract Data from Image", use_container_width=True):
                with st.spinner("🤖 Gemini is analyzing the document... Please wait."):
                    try:
                        image = Image.open(uploaded_file)
                        # Configure genai again in case the app was re-run
                        genai.configure(api_key=api_key)
                        extracted_data = enhanced_gemini_extraction(image)
                        st.session_state.extracted_data = extracted_data
                        st.session_state.edited_data = extracted_data.copy() if extracted_data else None
                        
                        if extracted_data:
                            st.success("✅ Data extraction complete!")
                        else:
                            st.error("❌ Extraction failed. Please try another image or model.")
                    except Exception as e:
                        st.error(f"An error occurred during processing: {e}")

    # --- Display, Edit, and Save Results ---
    if st.session_state.extracted_data:
        st.header("2. Review and Edit Extracted Data")
        st.info("The extracted data is shown below. You can edit any field before saving.")

        data_to_edit = st.session_state.edited_data
        
        # Display summary metrics
        col1, col2 = st.columns(2)
        with col1:
            confidence_score = data_to_edit.get('confidence_score', 0)
            if confidence_score:
                st.metric("Confidence Score", f"{confidence_score:.2f}")
            else:
                st.metric("Confidence Score", "N/A")
        with col2:
            st.metric("Best Model Used", data_to_edit.get('model_used', 'Unknown'))
        
        # Create tabs for different views
        tab1, tab2 = st.tabs(["📝 Edit Form", "📊 Table View"])
        
        with tab1:
            # Create editable fields for each piece of data
            edited_data_temp = {}
            form_fields = KYCFormData.model_fields.keys()
            
            # Group fields for better layout
            personal_info = ['name', 'father_husband_name', 'date_of_birth', 'mobile_number', 'pan_number', 'aadhar_number']
            employment_info = ['control_number', 'designation', 'bill_unit_number', 'department', 'sr_number', 'date_of_appointment']
            address_info = ['office_address', 'residential_address']
            bank_info = ['bank_name', 'branch_name', 'branch_code', 'account_number', 'ifsc_code']
            nominee_info = ['nominee_name', 'nominee_relation', 'nominee_dob', 'nominee_aadhar', 'nominee_pan']
            
            def create_form_section(title: str, fields: List[str]):
                with st.expander(title, expanded=True):
                    for field in fields:
                        if field in data_to_edit:
                            edited_data_temp[field] = st.text_input(
                                label=field.replace('_', ' ').title(),
                                value=data_to_edit.get(field, "") or "",
                                key=f"edit_{field}"
                            )

            create_form_section("👤 Personal & Identity", personal_info)
            create_form_section("🏢 Employment Details", employment_info)
            create_form_section("🏠 Address Information", address_info)
            create_form_section("🏦 Banking Details", bank_info)
            create_form_section("👨‍👩‍👧 Nominee Details", nominee_info)

            # Keep non-editable metadata
            edited_data_temp['document_title'] = data_to_edit.get('document_title')
            edited_data_temp['society_name'] = data_to_edit.get('society_name')
            # edited_data_temp['confidence_score'] = data_to_edit.get('confidence_score')
            # edited_data_temp['model_used'] = data_to_edit.get('model_used')

            # Update session state with edits
            st.session_state.edited_data = edited_data_temp

        with tab2:
            # Display data in tabular format
            st.subheader(" Extracted Data in Table Format")
            
            # Convert data to DataFrame for table display
            table_data = []
            for field, value in st.session_state.edited_data.items():
                table_data.append({
                    "Field": field.replace('_', ' ').title(),
                    "Value": value if value is not None else ""
                })
            
            df_display = pd.DataFrame(table_data)
            st.dataframe(df_display, use_container_width=True, height=600)

        st.header("3. Save or Download Data")
        
        #  action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Save to Excel Database", use_container_width=True):
                if save_to_excel(st.session_state.edited_data):
                    st.balloons()
        
        with col2:
            # Download as JSON
            json_string = json.dumps(st.session_state.edited_data, indent=2)
            file_name = "extracted_kyc_data.json"
            if uploaded_file:
                file_name = f"{uploaded_file.name.split('.')[0]}_extracted.json"

            st.download_button(
                label="Download as JSON",
                data=json_string,
                file_name=file_name,
                mime="application/json",
                use_container_width=True
            )
        
        with col3:
            # Download current record as Excel
            buffer = io.BytesIO()
            df_single = pd.DataFrame([st.session_state.edited_data])
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_single.to_excel(writer, sheet_name='KYC_Record', index=False)
            
            st.download_button(
                label="Download as Excel",
                data=buffer.getvalue(),
                file_name=f"{uploaded_file.name.split('.')[0]}_kyc.xlsx" if uploaded_file else "kyc_record.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        

        with st.expander("🔍 Show Raw JSON Data"):
            st.json(st.session_state.edited_data)

else:
    st.info("Please validate your API key in the sidebar and upload an image to begin.")

# --- Footer ---
st.markdown("---")
st.markdown("**Note:** The Excel database file will be created automatically in the same directory as this application.")
