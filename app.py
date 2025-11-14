import os
import vertexai
from flask import Flask, request, jsonify, render_template
from google.cloud import storage
# ADDED Content and Part to handle the full chat history structure
from vertexai.generative_models import GenerativeModel, Tool, Content, Part
from vertexai.preview import rag
import traceback
import time # <--- IMPORT TIME
import threading # <--- IMPORT THREADING

print("--- app.py: VERY VERY TOP ---")
t_start = time.time()
last_lap = t_start

def print_lap(msg):
    global last_lap
    now = time.time()
    print(f"--- LAP {msg}: {now - last_lap:.3f}s ---")
    last_lap = now

print_lap("Initial")

import os
    print_lap("After os import")
import vertexai
print_lap("After vertexai import")
from flask import Flask, request, jsonify, render_template
print_lap("After flask import")
from google.cloud import storage
print_lap("After google.cloud.storage import")
from vertexai.generative_models import GenerativeModel, Tool, Content, Part
print_lap("After vertexai.generative_models import")
from vertexai.preview import rag
print_lap("After vertexai.preview.rag import")
import traceback
print_lap("After traceback import")

print(f"--- app.py: Total import time: {time.time() - t_start:.3f}s ---")

# --- Configuration ---
PROJECT_ID = "sprintassistai-sandbox-148085"
LOCATION = "us-central1"
RAG_CORPUS_DISPLAY_NAME = "SprintAssist-corpus-1"
GCS_BUCKET_NAME = "sprintassist-corpus-files"

# --- Initialization ---
print("--- app.py: Flask app creating ---")
app = Flask(__name__)
print("--- app.py: Flask app created ---")

# Global variables for RAG model and tools
rag_model = None
rag_corpus = None
_model_init_lock = threading.Lock()

print("--- app.py: Initializing storage_client ---")
start_client_init = time.time()
storage_client = storage.Client(project=PROJECT_ID)
print(f"--- app.py: storage_client initialized in {time.time() - start_client_init:.2f}s ---")

def initialize_rag_model():
    """Initializes the RAG model and finds the corpus."""
    global rag_model, rag_corpus
    print("--- initialize_rag_model: START ---")
    init_start_time = time.time()

    try:
        print("--- initialize_rag_model: Calling vertexai.init ---")
        t0 = time.time()
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        print(f"--- initialize_rag_model: vertexai.init took {time.time() - t0:.2f}s ---")

        print(f"--- initialize_rag_model: Searching for RAG Corpus: '{RAG_CORPUS_DISPLAY_NAME}' ---")
        t0 = time.time()
        all_corpora = list(rag.list_corpora())
        print(f"--- initialize_rag_model: rag.list_corpora() took {time.time() - t0:.2f}s ---")

        corpus_list = [c for c in all_corpora if c.display_name == RAG_CORPUS_DISPLAY_NAME]

        if not corpus_list:
            raise ValueError(f"Corpus '{RAG_CORPUS_DISPLAY_NAME}' not found. Please create it first.")

        rag_corpus = corpus_list[0]
        print(f"--- initialize_rag_model: Corpus found: {rag_corpus.name} ---")

        print("--- initialize_rag_model: Creating Tool ---")
        t0 = time.time()
        rag_tool = Tool.from_retrieval(
            retrieval=rag.Retrieval(
                source=rag.VertexRagStore(
                    rag_resources=[rag.RagResource(rag_corpus=rag_corpus.name)]
                )
            )
        )
        print(f"--- initialize_rag_model: Tool.from_retrieval took {time.time() - t0:.2f}s ---")

        print("--- initialize_rag_model: Initializing GenerativeModel ---")
        t0 = time.time()
        rag_model = GenerativeModel("gemini-1.5-flash", tools=[rag_tool])
        print(f"--- initialize_rag_model: GenerativeModel init took {time.time() - t0:.2f}s ---")

        print(f"--- RAG-powered model configured successfully. Total init time: {time.time() - init_start_time:.2f} seconds ---")

    except Exception as e:
        print(f"--- FATAL RAG INITIALIZATION ERROR --- Elapsed: {time.time() - init_start_time:.2f} seconds ---")
        print(f"Failed to initialize RAG model. Check permissions and corpus name.")
        print(f"Error details: {str(e)}")
        traceback.print_exc()
        rag_model = None
        # Do not re-raise here in before_first_request, handle in route
    print("--- initialize_rag_model: END ---")

@app.before_first_request
def load_model():
    global rag_model
    # Use a lock to ensure initialization only happens once
    with _model_init_lock:
        if not rag_model:
            print("--- app.py: Calling initialize_rag_model (before first request) ---")
            try:
                initialize_rag_model()
                print("--- app.py: initialize_rag_model call complete ---")
            except Exception as e:
                 print(f"--- app.py: initialize_rag_model failed: {e} ---")
                 # rag_model remains None
        else:
            print("--- app.py: Model already initialized ---")

# --- API Endpoints ---
@app.route("/")
def index():
    """Serves the index.html file."""
    print("--- Request to / route IN INDEX FUNCTION ---")
    try:
        template_folder = os.path.abspath(app.template_folder)
        index_path = os.path.join(template_folder, "index.html")
        print(f"Flask template folder: {template_folder}")
        print(f"Expected index.html path: {index_path}")

        if os.path.exists('/app'):
            print(f"Contents of WORKDIR (/app): {os.listdir('/app')}")
        else:
            print("/app does not exist")

        if os.path.isdir(template_folder):
             print(f"Contents of template folder ({template_folder}): {os.listdir(template_folder)}")
        else:
             print(f"Template folder {template_folder} DOES NOT EXIST")

        print(f"templates folder exists: {os.path.isdir(template_folder)}")
        print(f"index.html file exists: {os.path.isfile(index_path)}")

        if not os.path.isfile(index_path):
            return jsonify({"error": "index.html not found at " + index_path, "details": "Check build process and .dockerignore"}), 404

        return render_template("index.html")
    except Exception as e:
        print(f"Error in / route: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Error rendering page", "details": str(e)}), 500

@app.route("/chat", methods=["POST"])
def chat():
    """
    Endpoint for a chat query.
    """
    global rag_model
    if not rag_model:
        print("--- CHAT: RAG model not initialized, attempting to load ---")
        load_model() # Attempt to initialize if not done yet
        if not rag_model:
             return jsonify({"error": "RAG model not initialized. Check server logs."}), 500

    request_data = request.get_json()
    conversation_history_dicts = request_data.get("contents")

    if not conversation_history_dicts or not isinstance(conversation_history_dicts, list):
        return jsonify({"error": "The 'contents' (chat history) array is required and must be a list."}), 400

    contents_for_sdk = []
    try:
        for turn in conversation_history_dicts:
            role = turn['role']
            text = turn['parts'][0]['text']
            contents_for_sdk.append(Content(role=role, parts=[Part.from_text(text)]))
    except (KeyError, IndexError) as e:
        return jsonify({"error": f"Invalid structure in chat history payload: {str(e)}"}), 400

    try:
        response = rag_model.generate_content(contents_for_sdk)
        return jsonify({"response": response.text})
    except Exception as e:
        print(f"Error during agent content generation: {e}")
        return jsonify({"error": f"Agent generation failed: {str(e)}"}), 500

@app.route("/upload", methods=["POST"])
def upload_file():
    """Endpoint to upload a file and update the RAG corpus."""
    global rag_corpus
    if not rag_corpus:
        print("--- UPLOAD: RAG model/corpus not initialized, attempting to load ---")
        load_model() # Attempt to initialize if not done yet
        if not rag_corpus:
             return jsonify({"error": "RAG Corpus is not initialized or found."}), 500

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        try:
            bucket = storage_client.bucket(GCS_BUCKET_NAME)
            if not bucket.exists():
                print(f"Bucket {GCS_BUCKET_NAME} not found, creating...")
                try:
                    bucket.create(location=LOCATION)
                    print(f"Bucket {GCS_BUCKET_NAME} created.")
                except Exception as bucket_e:
                    print(f"Error creating bucket: {str(bucket_e)}")
                    raise

            blob = bucket.blob(file.filename)
            print(f"Uploading {file.filename} to gs://{GCS_BUCKET_NAME}/{file.filename}")
            blob.upload_from_file(file)
            gcs_uri = f"gs://{GCS_BUCKET_NAME}/{file.filename}"
            print(f"File uploaded to {gcs_uri}. Starting RAG import...")

            import_response = rag.import_files(corpus_name=rag_corpus.name, paths=[gcs_uri])
            print(f"RAG import finished. Imported: {import_response.imported_rag_files_count}, Skipped: {import_response.skipped_rag_files_count}")
            return jsonify({"message": f"File '{file.filename}' uploaded and sent to RAG for processing."})
        except Exception as e:
            print(f"Error in upload_file: {str(e)}")
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "An unknown error occurred."}), 500

print("--- app.py: End of file ---")
