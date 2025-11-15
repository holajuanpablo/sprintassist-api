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
from waitress import serve

# --- Configuration ---
PROJECT_ID = "sprintassistai-sandbox-148085"
LOCATION = "us-central1"
RAG_CORPUS_DISPLAY_NAME = "SprintAssist-corpus-1"
GCS_BUCKET_NAME = "sprintassist-corpus-files"

# --- Initialization ---
print("--- app.py: Flask app creating ---", file=sys.stderr, flush=True)
app = Flask(__name__)
print("--- app.py: Flask app created ---", file=sys.stderr, flush=True)

# Global variables
rag_model = None
rag_corpus = None
_model_initialized = False
_model_init_lock = threading.Lock()
storage_client = None

try:
    print("--- app.py: Initializing storage_client ---", file=sys.stderr, flush=True)
    storage_client = storage.Client(project=PROJECT_ID)
    print(f"--- app.py: storage_client initialized ---", file=sys.stderr, flush=True)
except Exception as e:
    print(f"--- ERROR: Failed to initialize storage_client: {e} ---", file=sys.stderr, flush=True)
    traceback.print_exc(file=sys.stderr)

def initialize_rag_model():
    """Initializes the RAG model and finds the corpus."""
    global rag_model, rag_corpus
    print("--- initialize_rag_model: START ---", file=sys.stderr, flush=True)
    # ... (rest of initialize_rag_model function as before) ...
    try:
        print("--- initialize_rag_model: Calling vertexai.init ---", file=sys.stderr, flush=True)
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        print(f"--- initialize_rag_model: vertexai.init complete ---", file=sys.stderr, flush=True)

        print(f"--- initialize_rag_model: Searching for RAG Corpus: '{RAG_CORPUS_DISPLAY_NAME}' ---", file=sys.stderr, flush=True)
        all_corpora = list(rag.list_corpora())
        corpus_list = [c for c in all_corpora if c.display_name == RAG_CORPUS_DISPLAY_NAME]

        if not corpus_list:
            raise ValueError(f"Corpus '{RAG_CORPUS_DISPLAY_NAME}' not found.")
        rag_corpus = corpus_list[0]
        print(f"--- initialize_rag_model: Corpus found: {rag_corpus.name} ---", file=sys.stderr, flush=True)

        rag_tool = Tool.from_retrieval(
            retrieval=rag.Retrieval(source=rag.VertexRagStore(rag_resources=[rag.RagResource(rag_corpus=rag_corpus.name)]))
        )
        print("--- initialize_rag_model: RAG Tool created ---", file=sys.stderr, flush=True)

        rag_model = GenerativeModel("gemini-1.5-flash", tools=[rag_tool])
        print(f"--- RAG-powered model configured successfully ---", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"--- FATAL RAG INITIALIZATION ERROR ---", file=sys.stderr, flush=True)
        print(f"Error details: {str(e)}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        rag_model = None
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

# --- API Endpoints ---
@app.route("/")
def index():
    """Serves the index.html file."""
    print("--- Request to / route IN INDEX FUNCTION ---", file=sys.stderr, flush=True)
    return render_template("index.html")

@app.route("/test")
def test_route():
    print("--- Request to /test route ---", file=sys.stderr, flush=True)
    return "Test route OK!", 200

@app.route("/chat", methods=["POST"])
def chat():
    """Endpoint for a chat query."""
    print("--- CHAT: Request received ---", file=sys.stderr, flush=True)
    global rag_model
    if not rag_model:
         print("--- CHAT: RAG model not initialized ---", file=sys.stderr, flush=True)
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
             # This is where your frontend message comes from
             print("--- CHAT: Response text is empty ---", file=sys.stderr, flush=True)
             #  Slightly more informative message for you
             return jsonify({"error": "I apologize, the agent's response was empty."}), 200

        return jsonify({"response": response_text})
    except Exception as e:
        print(f"--- CHAT: Error during agent content generation: {e} ---", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": f"Agent generation failed: {str(e)}"}), 500

# ... (upload_file route as before) ...
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

if __name__ == '__main__':
    print("--- app.py: Running in main ---", file=sys.stderr, flush=True)
    port = int(os.environ.get("PORT", 8080))
    print(f"--- app.py: Starting server on 0.0.0.0:{port} ---", file=sys.stderr, flush=True)
    serve(app, host='0.0.0.0', port=port)
