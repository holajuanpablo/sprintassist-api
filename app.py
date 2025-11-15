import os
import sys
import time
import threading
import traceback
import logging

from flask import Flask, request, jsonify, render_template
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel, Tool, Content, Part
from vertexai.preview import rag

print("--- app.py: VERY VERY TOP ---", file=sys.stderr, flush=True)
t_start = time.time()
last_lap = t_start

def print_lap(msg):
    global last_lap
    now = time.time()
    print(f"--- LAP {msg}: {now - last_lap:.3f}s ---", file=sys.stderr, flush=True)
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

import threading
print_lap("After threading import")

print(f"--- app.py: Total import time: {time.time() - t_start:.3f}s ---", file=sys.stderr, flush=True)

# --- Configuration ---
PROJECT_ID = "sprintassistai-sandbox-148085"
LOCATION = "us-central1"
RAG_CORPUS_DISPLAY_NAME = "SprintAssist-corpus-1"
GCS_BUCKET_NAME = "sprintassist-corpus-files"

# --- Initialization ---
print("--- app.py: Flask app creating ---", file=sys.stderr, flush=True)
app = Flask(__name__)
print("--- app.py: Flask app created ---", file=sys.stderr, flush=True)

# Global variables for RAG model and tools
rag_model = None
rag_corpus = None
_model_initialized = False
_model_init_lock = threading.Lock()
storage_client = None

try:
    print("--- app.py: Initializing storage_client ---", file=sys.stderr, flush=True)
    start_client_init = time.time()
    storage_client = storage.Client(project=PROJECT_ID)
    print(f"--- app.py: storage_client initialized in {time.time() - start_client_init:.2f}s ---", file=sys.stderr, flush=True)
except Exception as e:
    print(f"--- ERROR: Failed to initialize storage_client: {e} ---", file=sys.stderr, flush=True)
    traceback.print_exc(file=sys.stderr)

def initialize_rag_model():
    """Initializes the RAG model and finds the corpus."""
    global rag_model, rag_corpus
    print("--- initialize_rag_model: START ---", file=sys.stderr, flush=True)
    init_start_time = time.time()

    try:
        print("--- initialize_rag_model: Calling vertexai.init ---", file=sys.stderr, flush=True)
        t0 = time.time()
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        print(f"--- initialize_rag_model: vertexai.init took {time.time() - t0:.2f}s ---", file=sys.stderr, flush=True)

        print(f"--- initialize_rag_model: Searching for RAG Corpus: '{RAG_CORPUS_DISPLAY_NAME}' ---", file=sys.stderr, flush=True)
        t0 = time.time()
        all_corpora = list(rag.list_corpora())
        print(f"--- initialize_rag_model: rag.list_corpora() took {time.time() - t0:.2f}s ---", file=sys.stderr, flush=True)

        corpus_list = [c for c in all_corpora if c.display_name == RAG_CORPUS_DISPLAY_NAME]

        if not corpus_list:
            raise ValueError(f"Corpus '{RAG_CORPUS_DISPLAY_NAME}' not found. Please create it first.")

        rag_corpus = corpus_list[0]
        print(f"--- initialize_rag_model: Corpus found: {rag_corpus.name} ---", file=sys.stderr, flush=True)

        print("--- initialize_rag_model: Creating Tool ---", file=sys.stderr, flush=True)
        t0 = time.time()
        rag_tool = Tool.from_retrieval(
            retrieval=rag.Retrieval(
                source=rag.VertexRagStore(
                    rag_resources=[rag.RagResource(rag_corpus=rag_corpus.name)]
                )
            )
        )
        print(f"--- initialize_rag_model: Tool.from_retrieval took {time.time() - t0:.2f}s ---", file=sys.stderr, flush=True)

        print("--- initialize_rag_model: Initializing GenerativeModel ---", file=sys.stderr, flush=True)
        t0 = time.time()
        # Ensure you are using the model name intended for your use case.
        rag_model = GenerativeModel("gemini-1.5-flash", tools=[rag_tool])
        print(f"--- initialize_rag_model: GenerativeModel init took {time.time() - t0:.2f}s ---", file=sys.stderr, flush=True)

        print(f"--- RAG-powered model configured successfully. Total init time: {time.time() - init_start_time:.2f} seconds ---", file=sys.stderr, flush=True)

    except Exception as e:
        print(f"--- FATAL RAG INITIALIZATION ERROR --- Elapsed: {time.time() - init_start_time:.2f} seconds ---", file=sys.stderr, flush=True)
        print(f"Failed to initialize RAG model. Check permissions and corpus name.", file=sys.stderr, flush=True)
        print(f"Error details: {str(e)}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        rag_model = None
        # Re-raise to signal failure to the calling function
        raise
    print("--- initialize_rag_model: END ---", file=sys.stderr, flush=True)

@app.before_request
def ensure_model_is_loaded():
    global _model_initialized, rag_model, rag_corpus
    if _model_initialized:
        return

    with _model_init_lock:
        if not _model_initialized:
            print("--- app.py: Calling initialize_rag_model (before request) ---", file=sys.stderr, flush=True)
            try:
                initialize_rag_model()
                _model_initialized = True
                print("--- app.py: initialize_rag_model call complete ---", file=sys.stderr, flush=True)
            except Exception as e:
                 print(f"--- app.py: initialize_rag_model failed: {e} ---", file=sys.stderr, flush=True)
                 # rag_model and rag_corpus remain None

# --- API Endpoints ---
@app.route("/")
def index():
    """Serves the index.html file."""
    print("--- Request to / route IN INDEX FUNCTION ---", file=sys.stderr, flush=True)
    try:
        template_folder = os.path.abspath(app.template_folder)
        index_path = os.path.join(template_folder, "index.html")
        print(f"Flask template folder: {template_folder}", file=sys.stderr, flush=True)
        print(f"Expected index.html path: {index_path}", file=sys.stderr, flush=True)

        if os.path.exists('/app'):
            print(f"Contents of WORKDIR (/app): {os.listdir('/app')}", file=sys.stderr, flush=True)
        else:
            print("/app does not exist", file=sys.stderr, flush=True)

        if os.path.isdir(template_folder):
             print(f"Contents of template folder ({template_folder}): {os.listdir(template_folder)}", file=sys.stderr, flush=True)
        else:
             print(f"Template folder {template_folder} DOES NOT EXIST", file=sys.stderr, flush=True)

        print(f"templates folder exists: {os.path.isdir(template_folder)}", file=sys.stderr, flush=True)
        print(f"index.html file exists: {os.path.isfile(index_path)}", file=sys.stderr, flush=True)

        if not os.path.isfile(index_path):
            return jsonify({"error": "index.html not found at " + index_path, "details": "Check build process and .dockerignore"}), 404

        return render_template("index.html")
    except Exception as e:
        print(f"Error in / route: {str(e)}", file=sys.stderr, flush=True)
        print(traceback.format_exc(), file=sys.stderr)
        return jsonify({"error": "Error rendering page", "details": str(e)}), 500

@app.route("/test")
def test_route():
    print("--- Request to /test route ---", file=sys.stderr, flush=True)
    return "Test route OK!", 200

@app.route("/chat", methods=["POST"])
def chat():
    """
    Endpoint for a chat query.
    """
    global rag_model
    if not rag_model:
         print("--- CHAT: RAG model not available. Check server logs for initialization errors. ---", file=sys.stderr, flush=True)
         return jsonify({"error": "RAG model not available. Check server logs."}), 500

    request_data = request.get_json()
    print(f"--- CHAT: Request data: {request_data} ---", file=sys.stderr, flush=True)

    conversation_history_dicts = request_data.get("contents")

    if not conversation_history_dicts or not isinstance(conversation_history_dicts, list):
        print("--- CHAT: Invalid contents format ---", file=sys.stderr, flush=True)
        return jsonify({"error": "The 'contents' (chat history) array is required and must be a list."}), 400

    contents_for_sdk = []
    try:
        for turn in conversation_history_dicts:
            role = turn['role']
            text = turn['parts'][0]['text']
            contents_for_sdk.append(Content(role=role, parts=[Part.from_text(text)]))
        print(f"--- CHAT: Contents for SDK: {contents_for_sdk} ---", file=sys.stderr, flush=True)
    except (KeyError, IndexError) as e:
        print(f"--- CHAT: Error converting contents: {e} ---", file=sys.stderr, flush=True)
        return jsonify({"error": f"Invalid structure in chat history payload: {str(e)}"}), 400

    try:
        print("--- CHAT: Calling rag_model.generate_content ---", file=sys.stderr, flush=True)
        response = rag_model.generate_content(contents_for_sdk)
        print(f"--- CHAT: Raw response from model: {response} ---", file=sys.stderr, flush=True)

        if not response.candidates:
            print(f"--- CHAT: No candidates in response. Finish reason: {response.prompt_feedback} ---", file=sys.stderr, flush=True)
            return jsonify({"error": "Agent returned no response, possibly due to safety filters or other issues."}), 500

        response_text = response.text
        print(f"--- CHAT: Response text: '{response_text}' ---", file=sys.stderr, flush=True)

        if not response_text.strip():
             print("--- CHAT: Response text is empty ---", file=sys.stderr, flush=True)
             return jsonify({"error": "I apologize, the agent's response was empty."}), 200

        return jsonify({"response": response_text})
    except Exception as e:
        print(f"--- CHAT: Error during agent content generation: {e} ---", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": f"Agent generation failed: {str(e)}"}), 500

@app.route("/upload", methods=["POST"])
def upload_file():
    """Endpoint to upload a file and update the RAG corpus."""
    global rag_corpus, storage_client
    if not rag_corpus:
             return jsonify({"error": "RAG Corpus not available. Check server logs for initialization errors."}), 500
    if not storage_client:
             return jsonify({"error": "Storage client not initialized."}), 500

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        try:
            bucket = storage_client.bucket(GCS_BUCKET_NAME)
            if not bucket.exists():
                print(f"Bucket {GCS_BUCKET_NAME} not found, creating...", file=sys.stderr, flush=True)
                try:
                    bucket.create(location=LOCATION)
                    print(f"Bucket {GCS_BUCKET_NAME} created.", file=sys.stderr, flush=True)
                except Exception as bucket_e:
                    print(f"Error creating bucket: {str(bucket_e)}", file=sys.stderr, flush=True)
                    raise

            blob = bucket.blob(file.filename)
            print(f"Uploading {file.filename} to gs://{GCS_BUCKET_NAME}/{file.filename}", file=sys.stderr, flush=True)
            blob.upload_from_file(file)
            gcs_uri = f"gs://{GCS_BUCKET_NAME}/{file.filename}"
            print(f"File uploaded to {gcs_uri}. Starting RAG import...", file=sys.stderr, flush=True)

            import_response = rag.import_files(corpus_name=rag_corpus.name, paths=[gcs_uri])
            print(f"RAG import finished. Imported: {import_response.imported_rag_files_count}, Skipped: {import_response.skipped_rag_files_count}", file=sys.stderr, flush=True)
            return jsonify({"message": f"File '{file.filename}' uploaded and sent to RAG for processing."})
        except Exception as e:
            print(f"Error in upload_file: {str(e)}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "An unknown error occurred."}), 500

print("--- app.py: End of file ---", file=sys.stderr, flush=True)
