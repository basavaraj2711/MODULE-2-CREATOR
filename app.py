import time
import streamlit as st
from PyPDF2 import PdfReader
from fpdf import FPDF
from concurrent.futures import ThreadPoolExecutor, as_completed
import google.generativeai as genai

# Directly include the API key (replace with your actual key)
API_KEY = "AIzaSyA52OyAzxBqfT4JgNBch02MVV50WhBGk_o"
genai.configure(api_key=API_KEY)

# Function to extract every piece of text from the PDF for Module 2 generation
def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = PdfReader(uploaded_file)
        all_text = ""
        # Loop through each page to ensure nothing is missed.
        for i, page in enumerate(pdf_reader.pages, start=1):
            page_text = page.extract_text()
            if page_text:
                all_text += f"\n\n--- Page {i} ---\n\n" + page_text
        return all_text.strip()
    except Exception as e:
        st.error(f"Error reading PDF file: {e}")
        return None

# Function to divide text into manageable chunks
def divide_text_into_chunks(text, chunk_size=3000):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

# Function to call Gemini API for content generation with retries
def call_gemini_api(prompt, max_retries=3):
    retries = 0
    # Instantiate the Gemini model (adjust the model name if needed)
    model = genai.GenerativeModel("gemini-1.5-pro")
    while retries < max_retries:
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            retries += 1
            wait_time = 2 ** retries  # Exponential backoff
            st.warning(f"Error with Gemini API: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    st.error("Max retries exceeded. Please try again later.")
    return None

# Function to create the Module 2 document using parallel API calls.
# For each chunk of the extracted input text, a prompt is built that instructs the AI to:
# - Act as an expert in creating Module 2 sections for regulatory dossiers.
# - Synthesize the input content.
# - Generate Module 2 content strictly adhering to the uploaded format reference.
# - Include every section and subsection specified in the format template.
# - Format the response exactly as follows:
#
#     section:{section name}
#     content:{Response of the gemini about this section with help of module 3}
#     ------------------------------------------------------------------------------------
#
#     section:{section name}
#     content:{Response of the gemini about this section with help of module 3}
#     ------------------------------------------------------------------------------------
#
# For each section, include placeholders with detailed descriptions.
def create_module2_document(input_text, format_template, workers=4, chunk_size=3000):
    chunks = divide_text_into_chunks(input_text, chunk_size=chunk_size)
    module2_sections = []

    # Build a detailed prompt for each chunk.
    prompts = []
    for chunk in chunks:
        prompt = (
            "You are an expert in creating Module 2 sections for Common Technical Dossiers (CTDs) for regulatory submissions. "
            "Using the input content provided below, generate a comprehensive Module 2 document that strictly follows the format and structure specified in the reference. "
            "Ensure that every section and subsection mentioned in the format template is addressed, with no omissions. "
            "Your response must be formatted exactly as specified, including detailed placeholders where necessary. "
            "The expected response format is:\n\n"
            "section:{section name}\n"
            "content:{Response of the gemini about this section with help of module 3}\n"
            "------------------------------------------------------------------------------------\n"
            "section:{section name}\n"
            "content:{Response of the gemini about this section with help of module 3}\n"
            "------------------------------------------------------------------------------------\n"
            "...\n\n"
            "For each section and subsection, if there is a placeholder, include a detailed description. "
            "Make sure no section or subsection from the provided format is missed out.\n\n"
            "Module 2 Format Reference:\n"
            f"{format_template}\n\n"
            "Input Content:\n"
            f"{chunk}\n\n"
            "Please generate the Module 2 content in full, ensuring clarity, compliance with regulatory standards, and strict adherence to the format."
        )
        prompts.append(prompt)

    # Process API calls concurrently using ThreadPoolExecutor.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_prompt = {executor.submit(call_gemini_api, prompt): prompt for prompt in prompts}
        for future in as_completed(future_to_prompt):
            section_output = future.result()
            if section_output:
                module2_sections.append(section_output)
    
    # Combine all section outputs into one consolidated Module 2 document.
    return "\n\n".join(module2_sections)

# Function to generate a PDF report from the AI-generated Module 2 content.
def generate_pdf_report(module2_content):
    pdf = FPDF()
    
    # ----- Cover Page with Company Logo -----
    pdf.add_page()
    logo_path = r"D:\wobb\review\123.png"
    try:
        # Adjust the x, y, and width (w) as needed to position and scale your logo.
        pdf.image(logo_path, x=50, y=30, w=100)
    except Exception as e:
        st.error(f"Error adding logo image: {e}")
    
    # ----- Content Page with Module 2 Document -----
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    # Use a Unicode font (update the path to your Arial.ttf file as needed).
    pdf.add_font("ArialUnicode", fname=r"D:\wobb\review\Arial.ttf", uni=True)
    pdf.set_font("ArialUnicode", size=12)
    pdf.multi_cell(0, 10, module2_content)

    pdf_path = r"D:\wobb\review\CTD_Module2_Report.pdf"
    pdf.output(pdf_path)
    return pdf_path

# --- Streamlit App Layout ---

# Set page configuration
st.set_page_config(page_title="Pharma docket automatic module 2 creator", page_icon="📄", layout="wide")

# Display the company logo in the UI centered at a medium size
logo_path_ui = r"D:\wobb\review\123.png"
try:
    # Create three columns and display the logo in the center column
    cols = st.columns(3)
    cols[1].image(logo_path_ui, width=300)
except Exception as e:
    st.error(f"Error loading logo for UI: {e}")

# App Title
st.title("Pharma docket automatic module 2 creator")

st.markdown(
    """
    Upload the source document (PDF format) that contains the relevant information to be used for creating Module 2.
    Also, upload a text file that specifies the proper Module 2 format.
    
 """
)

# File uploader for the source PDF.
uploaded_pdf = st.file_uploader("Upload Source Document for Module 2 (PDF format only)", type=["pdf"], key="module2_pdf")

# File uploader for the Module 2 format template (text file).
uploaded_template = st.file_uploader("Upload the Module 2 Format Template (Text file)", type=["txt"], key="template_txt")

if uploaded_pdf and uploaded_template:
    # Read the Module 2 format template from the text file.
    format_template = uploaded_template.read().decode("utf-8").strip()
    
    # Ensure the template includes at least a minimal structure.
    if not format_template:
        st.error("The format template file appears to be empty. Please provide a valid template.")
    else:
        # Extract complete text from the PDF for Module 2 generation.
        with st.spinner("Extracting text from the PDF..."):
            input_text = extract_text_from_pdf(uploaded_pdf)
    
        if input_text:
            st.subheader("📑 Extracted Document Text Preview (First 1000 characters)")
            st.text_area("Extracted Text Preview", input_text[:1000], height=200)

            if st.button("Create Module 2 Document"):
                with st.spinner("Generating Module 2 document using the AI agent..."):
                    module2_content = create_module2_document(input_text, format_template)
                
                if module2_content:
                    st.subheader("🔍 AI-Generated Module 2 Document")
                    st.text_area("Module 2 Output", module2_content, height=500)
                    
                    pdf_path = generate_pdf_report(module2_content)
                    with open(pdf_path, "rb") as f:
                        st.download_button("Download Module 2 Document (PDF)", f, file_name="CTD_Module2_Report.pdf", mime="application/pdf")
                else:
                    st.error("Failed to generate Module 2 content. Please try again.")
else:
    st.info("Please upload both the source PDF and the Module 2 format template to proceed.")
