import os
from google.cloud import storage, documentai_v1 as documentai
from PyPDF2 import PdfReader, PdfWriter
import toml

# Initialize the Document AI client
def get_document_ai_client():
    return documentai.DocumentProcessorServiceClient()

# Process a PDF file using Document AI
def process_document(project_id, location, processor_id, file_path):
    client = get_document_ai_client()

    # Read the PDF from local storage
    with open(file_path, "rb") as pdf_file:
        content = pdf_file.read()

    # Configure the request for Document AI API
    raw_document = {"content": content, "mime_type": "application/pdf"}
    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

    # Call the API to process the document
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    result = client.process_document(request=request)
    return result.document

# Upload combined JSON results to GCP bucket
def upload_json_to_gcp(bucket_name, destination_blob_name, content):
    storage_client = storage.Client(project="civil-tube-436417-k8")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # Upload the JSON content
    blob.upload_from_string(content)
    print(f"Uploaded combined result to {destination_blob_name} in bucket {bucket_name}")

# Split the PDF into chunks of a maximum of 15 pages
def split_pdf(input_pdf_path, output_dir, chunk_size=15):
    pdf_reader = PdfReader(input_pdf_path)
    total_pages = len(pdf_reader.pages)
    chunk_paths = []

    for i in range(0, total_pages, chunk_size):
        pdf_writer = PdfWriter()
        chunk_filename = os.path.join(output_dir, f"split_{i // chunk_size + 1}.pdf")

        for j in range(i, min(i + chunk_size, total_pages)):
            pdf_writer.add_page(pdf_reader.pages[j])

        with open(chunk_filename, 'wb') as output_pdf:
            pdf_writer.write(output_pdf)
        
        chunk_paths.append(chunk_filename)

    return chunk_paths

# Process each chunked PDF, combine the results, and upload the combined result
def process_and_upload_combined_chunks(project_id, location, processor_id, bucket_name, pdf_file, output_dir):
    # Split the large PDF into chunks
    chunk_paths = split_pdf(pdf_file, "/tmp")

    combined_text = ""
    for chunk_path in chunk_paths:
        print(f"Processing chunk: {chunk_path}")
        processed_doc = process_document(project_id, location, processor_id, chunk_path)

        # Combine the text from each processed chunk
        combined_text += processed_doc.text

    # Upload the combined result as one JSON file
    json_output_path = f"{output_dir}/{os.path.basename(pdf_file).replace('.pdf', '_combined.json')}"
    full_output_path = os.path.join("project_2", json_output_path)  # Ensure correct path structure
    upload_json_to_gcp(bucket_name, full_output_path, combined_text)

# Function to list PDF files in nested directories of the GCP bucket
def list_pdfs_in_bucket(bucket_name, prefix):
    storage_client = storage.Client(project="civil-tube-436417-k8")
    bucket = storage_client.bucket(bucket_name)

    # Recursively list all blobs in the bucket with the specified prefix (directory)
    blobs = bucket.list_blobs(prefix=prefix)
    pdf_files = [blob.name for blob in blobs if blob.name.endswith(".pdf")]
    return pdf_files

# Main function to process PDFs from GCP bucket, combine results, and upload the combined result
def process_pdfs_in_bucket(bucket_name, prefix, project_id, location, processor_id, output_dir):
    # List all PDF files in the GCP bucket
    pdf_files = list_pdfs_in_bucket(bucket_name, prefix)

    # Process each PDF and combine results
    for pdf_file in pdf_files:
        print(f"Processing file: {pdf_file}")

        # Download the file to local temporarily
        local_pdf_path = f"/tmp/{os.path.basename(pdf_file)}"
        storage_client = storage.Client(project="civil-tube-436417-k8")
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(pdf_file)
        blob.download_to_filename(local_pdf_path)

        # Process the PDF using Document AI API in chunks and combine results
        process_and_upload_combined_chunks(project_id, location, processor_id, bucket_name, local_pdf_path, output_dir)


# Load configuration from TOML
config = toml.load('googledocai_config.toml')

# Access the values from the TOML file
project_id = config['google_doc_ai']['project_id']
location = config['google_doc_ai']['location']
processor_id = config['google_doc_ai']['processor_id']
bucket_name = config['google_doc_ai']['bucket_name']
prefix = config['google_doc_ai']['prefix']
output_directory = config['google_doc_ai']['output_directory']



# Call the function to process and store the parsed results
process_pdfs_in_bucket(BUCKET_NAME, PREFIX, PROJECT_ID, LOCATION, PROCESSOR_ID, OUTPUT_DIR)
