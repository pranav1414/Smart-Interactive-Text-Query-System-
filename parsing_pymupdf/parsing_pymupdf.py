# open source setup

import os
import json
import pandas as pd
from sqlalchemy import create_engine, text
from google.cloud import storage
from google.cloud.sql.connector import Connector
import pymysql
import fitz  # PyMuPDF
import toml

# Load configuration from TOML
config = toml.load('pymupdf_config.toml')

# Access the values from the TOML file
instance_connection_name = config['pymupdf']['instance_connection_name']
db_name = config['pymupdf']['db_name']
db_user = config['pymupdf']['db_user']
db_password = config['pymupdf']['db_password']
bucket_name = config['pymupdf']['bucket_name']
output_directory = config['pymupdf']['output_directory']

# Replace direct usage of credentials in your code with the variables above


# Initialize Cloud SQL Connector
connector = Connector()

# Use the connector to create a connection function
def get_db_connection():
    conn = connector.connect(
        instance_connection_name,
        "pymysql",
        user=db_user,
        password=db_password,
        db=db_name,
    )
    return conn

def fetch_pdf_info():
    """Fetch file_name, file_path, Question, Steps_without_answer, and data_from for PDFs."""
    query = """
    SELECT task_id, file_name, file_path, Question, Steps_without_answer, data_from 
    FROM project2_gaia_table 
    WHERE file_type = 'pdf';
    """
    # Use SQLAlchemy to read data into a pandas DataFrame
    engine = create_engine(
        "mysql+pymysql://",
        creator=get_db_connection,
    )
    pdf_info_df = pd.read_sql(query, con=engine)
    return pdf_info_df.to_dict(orient='records')

def extract_text_and_images(pdf_path):
    """Extracts text and images from a PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    extracted_data = {"pages": {}}
    image_paths = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        
        # Store extracted text
        extracted_data["pages"][f"page_{page_num + 1}"] = {"text": text}

        # Extract images
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = "jpeg"  # Store images as JPEG

            image_filename = f"{os.path.splitext(os.path.basename(pdf_path))[0]}_page_{page_num + 1}_img_{img_index + 1}.{image_ext}"
            image_path = os.path.join("/tmp", image_filename)
            with open(image_path, "wb") as img_file:
                img_file.write(image_bytes)
            image_paths.append(image_path)

    doc.close()
    return extracted_data, image_paths

def save_json_to_gcp(bucket_name, json_data, json_path, timeout=1080):
    """Uploads JSON data to a specified GCP path."""
    storage_client = storage.Client(project="civil-tube-436417-k8")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(json_path)
    blob.upload_from_string(json.dumps(json_data), content_type="application/json", timeout=timeout)
    print(f"Uploaded JSON to {json_path} in bucket {bucket_name}")

def upload_images_to_gcp(bucket_name, image_paths, output_dir):
    """Uploads images to GCP."""
    storage_client = storage.Client(project="civil-tube-436417-k8")
    bucket = storage_client.bucket(bucket_name)

    for image_path in image_paths:
        blob = bucket.blob(os.path.join(output_dir, os.path.basename(image_path)))
        blob.upload_from_filename(image_path)
        print(f"Uploaded image {os.path.basename(image_path)} to {output_dir} in bucket {bucket_name}")

def store_mapping_info(task_id, file_name, original_pdf_path, json_output_path, images_output_path, question, steps_without_answer, data_from):
    """Stores the mapping info in the MySQL database."""
    insert_query = """
    INSERT INTO project2_pdf_mapping_table (
        task_id, file_name, original_pdf_path, json_output_path, images_output_path, Question, Steps_without_answer, data_from
    ) VALUES (:task_id, :file_name, :original_pdf_path, :json_output_path, :images_output_path, :question, :steps_without_answer, :data_from)
    """
    
    engine = create_engine(
        "mysql+pymysql://",
        creator=get_db_connection,
    )
    
    with engine.begin() as conn:
        # Pass the parameters as a dictionary
        conn.execute(text(insert_query), {
            "task_id": task_id, 
            "file_name": file_name, 
            "original_pdf_path": original_pdf_path, 
            "json_output_path": json_output_path, 
            "images_output_path": images_output_path, 
            "question": question, 
            "steps_without_answer": steps_without_answer, 
            "data_from": data_from
        })
    
    print(f"Inserted mapping info for {file_name} into the database.")

def process_pdf_and_store_results(bucket_name, pdf_info, output_dir):
    """Process a PDF and store extracted data and images in GCP."""
    task_id = pdf_info['task_id']
    file_name = pdf_info['file_name']
    original_pdf_path = pdf_info['file_path']
    question = pdf_info['Question']
    steps_without_answer = pdf_info['Steps_without_answer']
    data_from = pdf_info['data_from']

    # Remove any 'gs://' prefix from the path if present
    if original_pdf_path.startswith("gs://"):
        original_pdf_path = original_pdf_path.replace(f"gs://{bucket_name}/", "")

    # Download the PDF from GCP to a local path
    local_pdf_path = f"/tmp/{os.path.basename(original_pdf_path)}"
    storage_client = storage.Client(project="civil-tube-436417-k8")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(original_pdf_path)
    blob.download_to_filename(local_pdf_path)

    # Extract text and images
    extracted_data, image_paths = extract_text_and_images(local_pdf_path)
    
    # Define paths for storing the JSON and images
    json_output_path = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}.json")
    images_output_path = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}_images")

    # Upload JSON with extracted text to GCP
    save_json_to_gcp(bucket_name, extracted_data, json_output_path)
    
    # Upload extracted images to GCP
    upload_images_to_gcp(bucket_name, image_paths, images_output_path)

    # Store mapping information in the database
    store_mapping_info(
        task_id=task_id,
        file_name=file_name,
        original_pdf_path=original_pdf_path,
        json_output_path=json_output_path,
        images_output_path=images_output_path,
        question=question,
        steps_without_answer=steps_without_answer,
        data_from=data_from
    )



# Fetch the PDFs info from the SQL table
pdfs_info = fetch_pdf_info()

# Process each PDF and store results
for pdf_info in pdfs_info:
    process_pdf_and_store_results(BUCKET_NAME, pdf_info, OUTPUT_DIR)

# Close the connector when done
connector.close()
