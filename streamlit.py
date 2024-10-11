#Final_Streamlit_layout
import streamlit as st
import requests
import openai
import mysql.connector
from mysql.connector import Error
from hashlib import sha256  # For hashing passwords
from PIL import Image
from io import BytesIO

#Set up OpenAI API key
openai.api_key = "removed"
BUCKET_NAME = "bigdataia_fall2024_team9_assignment1_bucket"

#Database connection details
DB_CONFIG = {
    'user': 'root',
    'password': 'removed',
    'host': '34.82.158.68',
    'database': 'team9_gaia_db',
    'port': 3306
}

#Function to get answer from OpenAI based on a question
def get_openai_answer(question, context):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"{context}\n\nQ: {question}\nA:"}]
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        st.error(f"Error while fetching answer from OpenAI: {str(e)}")
        return None

# Streamlit app
def main():
    # Page setup for titles and colors
    st.set_page_config(page_title="NEW AGE JSON READER", layout="centered")
    st.markdown(
        """
        <style>
        .stButton>button {width: 100%;} /* Full-width buttons */
        .header {color: black; text-align: center; font-size: 28px;}
        .subheader {color: black; text-align: center; font-size: 22px;}
        body {background-color: #FAFAD2;} /* Light yellow background */
        </style>
        """, 
        unsafe_allow_html=True
    )

    # Initialize session state variables for user registration and login flow
    if 'registered' not in st.session_state:
        st.session_state.registered = False
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    # Logout message when coming to the registration page
    if 'logout_message' in st.session_state:
        st.success(st.session_state.logout_message)
        del st.session_state.logout_message  # Clear the message after displaying it

    # Registration form first, then login if already registered
    if not st.session_state.registered:
        st.markdown("<h1 class='header'>New Age JSON Reader</h1>", unsafe_allow_html=True)
        st.markdown("<h3 class='subheader'>Register</h3>", unsafe_allow_html=True)

        reg_username = st.text_input("Create Username", placeholder="Choose a username")
        reg_password = st.text_input("Create Password", type="password", placeholder="Choose a secure password")

        # Check for username and password length requirements
        if st.button("Register"):
            if len(reg_username) < 3:
                st.error("Username must be at least 3 characters long.")
            elif len(reg_password) < 6:
                st.error("Password must be at least 6 characters long.")
            else:
                # Hash the password before storing
                hashed_password = sha256(reg_password.encode()).hexdigest()
                try:
                    connection = mysql.connector.connect(**DB_CONFIG)
                    cursor = connection.cursor()
                    cursor.execute("SELECT * FROM users WHERE username = %s", (reg_username,))
                    
                    if cursor.fetchone():
                        st.error("Username already exists. Please choose another.")
                    else:
                        cursor.execute("INSERT INTO users (username, hashed_password) VALUES (%s, %s)", (reg_username, hashed_password))
                        connection.commit()
                        st.success("Registration successful! Please proceed to login.")
                        st.session_state.registered = True
                except Error as e:
                    st.error(f"Database error: {str(e)}")
                finally:
                    if connection.is_connected():
                        cursor.close()
                        connection.close()
                        
        
        #Button to navigate to Login Page
        if st.button("Already Registered? Go to Login"):
            st.session_state.registered = True  
            st.session_state.logged_in = False 
            st.rerun() 

    elif not st.session_state.logged_in:
        # Login Page
        st.markdown("<h1 class='header'>New Age JSON Reader</h1>", unsafe_allow_html=True)
        st.markdown("<h3 class='subheader'>Login</h3>", unsafe_allow_html=True)

        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")

        if st.button("Login"):
            hashed_password = sha256(password.encode()).hexdigest()

            try:
                connection = mysql.connector.connect(**DB_CONFIG)
                cursor = connection.cursor()
                cursor.execute("SELECT * FROM users WHERE username = %s AND hashed_password = %s", (username, hashed_password))

                if cursor.fetchone():
                    st.session_state.logged_in = True
                    st.success("Login successful!")
                else:
                    st.error("Invalid username or password.")
            except Error as e:
                st.error(f"Database error: {str(e)}")
            finally:
                if connection.is_connected():
                    cursor.close()
                    connection.close()
                    st.rerun() 

        # Back button to return to the registration page
        if st.button("Back to Registration"):
            st.session_state.registered = False 
            st.session_state.logged_in = False   
            st.rerun() 

    else:
        # Content Selection Page with Tabs
        st.markdown("<h1 class='header'>Select Your Content</h1>", unsafe_allow_html=True)

        # Create tabs
        tab1, tab2, tab3 = st.tabs(["Open Source Extract", "API Extract", "Image Extracts"])

        # Logout button
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.registered = False
            st.session_state.logout_message = "You have logged out successfully."
            st.rerun() 
            st.success(st.session_state.logout_message)
            st.experimental_rerun()  

        # Tab for Open Source Extract
        with tab1:
            # Fetch list of available JSON files
            response = requests.get("http://127.0.0.1:8000/list_json_files/")
            # response = requests.get("http://fastapi:8000/list_json_files/")

            # response = requests.get("http://fastapi:8000/list_json_files/")

            if response.status_code == 200:
                json_files = response.json().get("json_files", [])
            else:
                st.error("Error fetching JSON list from FastAPI.")
                json_files = []

            if not json_files:
                st.error("No JSON files found in the specified folder.")
            else:
                selected_json = st.selectbox("Choose a JSON file to load (Open Source)", json_files, key="open_source_selectbox")

                if st.button("Load JSON (Open Source)"):
                    if 'loading_json' not in st.session_state or not st.session_state.loading_json:
                        st.session_state.loading_json = True
                        # Fetch JSON content from FastAPI
                        response = requests.get(f"http://127.0.0.1:8000/load_json/?filename={selected_json}")

                        if response.status_code == 200:
                            result = response.json()
                            if 'content' in result:
                                json_content = result['content']
                                st.text_area("JSON Content", json_content, height=300)
                                st.session_state.json_content = json_content
                            else:
                                st.error(f"Error: {result.get('error', 'Unknown error')}")
                        else:
                            st.error("Error loading JSON content from FastAPI.")
                        
                        # Reset loading state
                        st.session_state.loading_json = False

                # Ask a Question feature
                question = st.text_input("Ask a Question about this JSON content (Open Source)")
                if st.button("Get Answer (Open Source)"):
                    if 'json_content' in st.session_state:
                        answer = get_openai_answer(question, st.session_state.json_content)
                        if answer:
                            st.text_area("Answer", answer, height=200)

        # Tab for API Extract
        with tab2:
            # This tab replicates the same content as the Open Source Extract tab.
            response = requests.get("http://127.0.0.1:8000/list_json_files/")
            if response.status_code == 200:
                json_files = response.json().get("json_files", [])
            else:
                st.error("Error fetching JSON list from FastAPI.")
                json_files = []

            if not json_files:
                st.error("No JSON files found in the specified folder.")
            else:
                selected_json = st.selectbox("Choose a JSON file to load (API Extract)", json_files, key="api_extract_selectbox")

                if st.button("Load JSON (API Extract)"):
                    if 'loading_json' not in st.session_state or not st.session_state.loading_json:
                        st.session_state.loading_json = True
                        response = requests.get(f"http://127.0.0.1:8000/load_json/?filename={selected_json}")

                        if response.status_code == 200:
                            result = response.json()
                            if 'content' in result:
                                json_content = result['content']
                                st.text_area("JSON Content", json_content, height=300)
                                st.session_state.json_content = json_content
                            else:
                                st.error(f"Error: {result.get('error', 'Unknown error')}")
                        else:
                            st.error("Error loading JSON content from FastAPI.")
                        
                        st.session_state.loading_json = False

                # Ask a Question feature
                question = st.text_input("Ask a Question about this JSON content (API Extract)")
                if st.button("Get Answer (API Extract)"):
                    if 'json_content' in st.session_state:
                        answer = get_openai_answer(question, st.session_state.json_content)
                        if answer:
                            st.text_area("Answer", answer, height=200)

        # New tab for Image Extracts
        with tab3:
            st.subheader("Image Extracts")
            if st.button("Load Extracted Images"):
                # Fetch image URLs
                image_response = requests.get(f"http://127.0.0.1:8000/load_images/")
                if image_response.status_code == 200:
                    image_urls = image_response.json().get("image_paths", [])
                    if image_urls:
                        st.subheader("All Associated Images")
                        for url in image_urls:
                            full_image_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{url}"
                            img_response = requests.get(full_image_url)
                            if img_response.status_code == 200:
                                img = Image.open(BytesIO(img_response.content))
                                st.image(img, use_column_width=True)
                            else:
                                st.error(f"Error loading image from URL: {full_image_url}")
                    else:
                        st.info("No images associated with this JSON file.")
                else:
                    st.error("Error fetching image URLs from FastAPI.")

if __name__ == "__main__":
    main()


