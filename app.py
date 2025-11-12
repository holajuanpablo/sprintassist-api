import os
import vertexai
from flask import Flask, request, jsonify, render_template
from google.cloud import storage
# ADDED Content and Part to handle the full chat history structure
from vertexai.generative_models import GenerativeModel, Tool, Content, Part
from vertexai.preview import rag

# --- Configuration ---
PROJECT_ID = "sprintassistai-sandbox-148085"
LOCATION = "us-central1"
RAG_CORPUS_DISPLAY_NAME = "SprintAssist-corpus-1"
GCS_BUCKET_NAME = "sprintassist-corpus-files"

# --- Initialization ---
app = Flask(__name__)
first_request_processed = False

# Global variables for RAG model and tools
rag_model = None
rag_corpus = None

# Set up Cloud Storage client
storage_client = storage.Client(project=PROJECT_ID)

@app.before_request
def run_on_first_request():
    global first_request_processed
    if not first_request_processed:
        print("This code runs only before the very first request!")
        first_request_processed = True
        initialize_rag_model()

def initialize_rag_model():
    """Initializes the RAG model and finds the corpus."""
    global rag_model, rag_corpus
    
    print("Initializing Vertex AI...")
    try:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        print("Vertex AI initialized.")

        print(f"Searching for RAG Corpus: '{RAG_CORPUS_DISPLAY_NAME}'...")
        all_corpora = list(rag.list_corpora())
        corpus_list = [c for c in all_corpora if c.display_name == RAG_CORPUS_DISPLAY_NAME]

        if not corpus_list:
            raise ValueError(f"Corpus '{RAG_CORPUS_DISPLAY_NAME}' not found. Please create it first.")
        
        rag_corpus = corpus_list[0]
        print(f"Corpus found with name: {rag_corpus.name}")

        # The RAG tool is correctly set up here
        rag_tool = Tool.from_retrieval(
            retrieval=rag.Retrieval(
                source=rag.VertexRagStore(
                    rag_resources=[rag.RagResource(rag_corpus=rag_corpus.name)]
                )
            )
        )

        rag_model = GenerativeModel("gemini-2.5-flash", tools=[rag_tool])
        print("RAG-powered model configured successfully.")

    except Exception as e:
        print(f"--- FATAL RAG INITIALIZATION ERROR ---")
        print(f"Failed to initialize RAG model. Check permissions and corpus name.")
        print(f"Error details: {str(e)}")
        print(f"--------------------------------------")
        rag_model = None
        # You may want to re-raise the exception to cause the container to fail
        # and not serve traffic.
        raise e

# --- API Endpoints ---

@app.route("/")
def index():
"""Serves the index.html file."""
print("--- Request to / route ---")
try:
    template_folder = os.path.abspath(app.template_folder)
    index_path = os.path.join(template_folder, "index.html")
    print(f"Flask template folder: {template_folder}")
    print(f"Expected index.html path: {index_path}")

    # Check existence
    print(f"Contents of WORKDIR (/app): {os.listdir('/app')}")
    print(f"Contents of template folder ({template_folder}): {os.listdir(template_folder) if os.path.isdir(template_folder) else 'DOES NOT EXIST'}")
    print(f"templates folder exists: {os.path.isdir(template_folder)}")
    print(f"index.html file exists: {os.path.isfile(index_path)}")

    if not os.path.isfile(index_path):
        return jsonify({"error": "index.html not found at " + index_path, "details": "Check build process and .dockerignore"}), 404

    return render_template("index.html")
except Exception as e:
    print(f"Error in / route: {str(e)}")
    # Log the full traceback for more details
    import traceback
    print(traceback.format_exc())
    return jsonify({"error": "Error rendering page", "details": str(e)}), 500

@app.route("/chat", methods=["POST"])
def chat():
    """
    Endpoint for a chat query.
    MODIFIED: Now accepts the full 'contents' array (conversation history) 
    and converts it to the format required by the Vertex AI SDK.
    """
    global rag_model
    
    if not rag_model:
        return jsonify({"error": "RAG model not initialized. Check server logs."}), 500

    request_data = request.get_json()
    
    # CRITICAL CHANGE 1: Extract the 'contents' array sent by the frontend
    conversation_history_dicts = request_data.get("contents")

    if not conversation_history_dicts or not isinstance(conversation_history_dicts, list):
        return jsonify({"error": "The 'contents' (chat history) array is required and must be a list."}), 400

    # CRITICAL CHANGE 2: Convert the list of dictionaries into Vertex AI SDK Content objects
    contents_for_sdk = []
    try:
        for turn in conversation_history_dicts:
            # We must ensure roles are 'user' or 'model' and parts contain text
            role = turn['role']
            # We assume the frontend sends a simple text part
            text = turn['parts'][0]['text'] 
            
            contents_for_sdk.append(
                Content(
                    role=role, 
                    parts=[Part.from_text(text)]
                )
            )
    except (KeyError, IndexError) as e:
        # This handles malformed messages in the history
        return jsonify({"error": f"Invalid structure in chat history payload: {str(e)}"}), 400

    try:
        # CRITICAL CHANGE 3: Pass the full list of Content objects to generate_content
        # This enables multi-turn conversation context.
        response = rag_model.generate_content(contents_for_sdk)
        return jsonify({"response": response.text})
    except Exception as e:
        # Provide a more detailed error message if possible
        print(f"Error during agent content generation: {e}")
        return jsonify({"error": f"Agent generation failed: {str(e)}"}), 500

@app.route("/upload", methods=["POST"])
def upload_file():
    """Endpoint to upload a file and update the RAG corpus."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        try:
            try:
                bucket = storage_client.get_bucket(GCS_BUCKET_NAME)
            except Exception:
                bucket = storage_client.create_bucket(GCS_BUCKET_NAME, location=LOCATION)

            blob = bucket.blob(file.filename)
            blob.upload_from_file(file)
            gcs_uri = f"gs://{GCS_BUCKET_NAME}/{file.filename}"
            
            print(f"File uploaded to {gcs_uri}. Starting RAG import...")
            
            # Ensure rag_corpus is initialized before trying to access its name
            if not rag_corpus:
                return jsonify({"error": "RAG Corpus is not initialized or found."}), 500

            import_response = rag.import_files(
                corpus_name=rag_corpus.name,
                paths=[gcs_uri]
            )

            if import_response.skipped_rag_files_count > 0:
                print("Skipped files:", import_response.skipped_rag_files_count)

            return jsonify({"message": f"File '{file.filename}' uploaded and sent to RAG for processing."})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "An unknown error occurred."}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
