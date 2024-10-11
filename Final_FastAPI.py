#FInal_FastAPI_Auth
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPBasicCredentials
from google.cloud import storage
import os
import mysql.connector
from mysql.connector import Error
from hashlib import sha256  # For hashing passwords
import jwt  # For JWT Auth
from datetime import datetime, timedelta  # For token expiration

app = FastAPI()
# Set up Google Cloud credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/damg7245team9/fastapi_ui/fastapi/civil-tube-436417-k8-948121b56cf9.json'
BUCKET_NAME = "bigdataia_fall2024_team9_assignment1_bucket"
FOLDER_NAME = "project_2/gcp_document_fitz_processed/"
API_FOLDER_NAME = "project_2/gcp_document_api_processed/"  # New folder path for API

# Database connection details
DB_CONFIG = {
    'host': '34.82.158.68',  # Your Cloud SQL instance IP address
    'user': 'root',          # Your Cloud SQL username
    'password': 'removed-for-github',  # Cloud SQL password
    'database': 'team9_gaia_db'  # Database name
}

# JWT configuration
SECRET_KEY = ""  # Replace with a secure random key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Function to create a JWT token
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Function to decode a JWT token
def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

#Dependency for token validation
http_bearer = HTTPBearer()

#Function to list all JSON files in a specific GCS folder
def list_gcs_json_files(folder_name: str):
    client = storage.Client()
    bucket = client.get_bucket(BUCKET_NAME)
    blobs = bucket.list_blobs(prefix=folder_name)  # List all files with the given folder prefix
    
#Filter for files that end with .json
    json_files = [blob.name for blob in blobs if blob.name.endswith('.json')]
    return json_files

@app.get("/list_json_files/")
def get_json_files():
    try:
        json_files = list_gcs_json_files(FOLDER_NAME)
        if not json_files:
            return {"message": "No JSON files found in the specified folder."}
        return {"json_files": json_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error listing JSON files: " + str(e))

@app.get("/load_json/")
def load_json(filename: str):
    try:
        client = storage.Client()
        bucket = client.get_bucket(BUCKET_NAME)
        blob = bucket.blob(filename)

        # Check if the file exists
        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found.")

        # Download the JSON content
        json_content = blob.download_as_text()
        return {"content": json_content}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error loading JSON file: " + str(e))

#New Endpoint to Load All Image Paths from a Specific Folder
@app.get("/load_images/")
def load_images(folder_name: str = "project_2/gcp_document_fitz_processed/be353748-74eb-4904-8f17-f180ce087f1a_images"):
    try:
        client = storage.Client()
        bucket = client.get_bucket(BUCKET_NAME)
        
        #List all files in the specified folder
        blobs = bucket.list_blobs(prefix=folder_name)
        
        #Filter for image files (you can adjust the extensions as needed)
        image_files = [blob.name for blob in blobs if blob.name.endswith(('.jpg', '.jpeg', '.png', '.gif'))]
        
        if not image_files:
            raise HTTPException(status_code=404, detail="No images found in the specified folder.")

        return {"image_paths": image_files}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error loading image paths: " + str(e))

#Endpoint for user registration
@app.post("/register/")
async def register_user(username: str, password: str):
    try:
        #Hash the password before storing
        hashed_password = sha256(password.encode()).hexdigest()

        #Connect to the database
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        #Check if the user already exists
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists.")

        #Insert new user
        cursor.execute("INSERT INTO users (username, hashed_password) VALUES (%s, %s)", (username, hashed_password))
        connection.commit()

        return {"message": "User registered successfully!"}

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

#Endpoint for user login with just username and password
@app.post("/login/")
async def login_user(credentials: HTTPBasicCredentials):
    try:
        #Hash the entered password
        hashed_password = sha256(credentials.password.encode()).hexdigest()

        #Connect to the database
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()

        #Check if the user exists and if the password matches
        cursor.execute("SELECT * FROM users WHERE username = %s AND hashed_password = %s", (credentials.username, hashed_password))
        user = cursor.fetchone()

        if user is None:
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        #Create access token
        access_token = create_access_token(data={"sub": credentials.username})
        return {"access_token": access_token, "token_type": "bearer"}

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

#New endpoint to list JSON files from the API folder
@app.get("/list_api_json_files/")
def get_api_json_files():
    try:
        json_files = list_gcs_json_files(API_FOLDER_NAME)
        if not json_files:
            return {"message": "No JSON files found in the API folder."}
        return {"json_files": json_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error listing API JSON files: " + str(e))

#New endpoint to load JSON content from the API folder
@app.get("/load_api_json/")
def load_api_json(filename: str):
    try:
        client = storage.Client()
        bucket = client.get_bucket(BUCKET_NAME)
        blob = bucket.blob(API_FOLDER_NAME + filename)

        #Check if the file exists
        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found.")

        #Download the JSON content
        json_content = blob.download_as_text()
        return {"content": json_content}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error loading API JSON file: " + str(e))

#Dependency for protected routes
def get_current_user(token: str = Depends(http_bearer)):
    payload = decode_access_token(token.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials.")
    return payload

#Example of a protected route
@app.get("/protected_route/")
def protected_route(current_user: dict = Depends(get_current_user)):
    return {"message": f"Hello {current_user['sub']}, you have access to this protected route!"}
