from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

# default arguments for the DAG
default_args = {
    'owner': 'damg7245team9',
    'depends_on_past': False,
    'start_date': datetime(2024, 10, 11),
    'retries': 1,
}

# the DAG
with DAG(
    'google_doc_parsing',
    default_args=default_args,
    schedule_interval='@daily',
    catchup=False,
) as dag:

    # google_doc_parser Docker container
    run_google_doc_parser = BashOperator(
        task_id='run_google_doc_parser',
        bash_command='docker run --rm google_doc_parser:latest',
    )

    # pymupdf_parser Docker container
    run_pymupdf_parser = BashOperator(
        task_id='run_pymupdf_parser',
        bash_command='docker run --rm pymupdf_parser:latest',
    )

    # task dependencies 
    run_google_doc_parser >> run_pymupdf_parser
