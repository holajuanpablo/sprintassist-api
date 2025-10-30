import vertexai
from vertexai.generative_models import GenerativeModel, Tool
from vertexai.preview import rag
import os
import time

# --- Configuration ---
# Your Google Cloud project ID and region.
# This should match your project setup in Nexus.
PROJECT_ID = "sprintassistai-sandbox-148085"
LOCATION = "us-central1"

# The display name of your RAG corpus.
# This is the corpus you already created and populated.
RAG_CORPUS_DISPLAY_NAME = "SprintAssist-corpus-1"

# A unique display name for your new RAG model and endpoint.
MODEL_DISPLAY_NAME = "SprintAssist-Model"
ENDPOINT_DISPLAY_NAME = "SprintAssist-Endpoint"


# --- Initialization ---
print("Initializing Vertex AI...")
vertexai.init(project=PROJECT_ID, location=LOCATION)

# --- Find and Configure the RAG Corpus ---
print(f"Searching for RAG Corpus: '{RAG_CORPUS_DISPLAY_NAME}'...")
# The Vertex AI SDK's list_corpora function does not support the 'filter' argument.
# We retrieve all corpora and filter them with Python.
all_corpora = rag.list_corpora()
corpus_list = [c for c in all_corpora if c.display_name == RAG_CORPUS_DISPLAY_NAME]

if not corpus_list:
    raise ValueError(f"Corpus '{RAG_CORPUS_DISPLAY_NAME}' not found. Please create it first.")
rag_corpus = corpus_list[0]
print(f"Corpus found with name: {rag_corpus.name}")

# Define the retrieval tool that uses your corpus.
rag_tool = Tool.from_retrieval(
    retrieval=rag.Retrieval(
        source=rag.VertexRagStore(
            rag_resources=[rag.RagResource(rag_corpus=rag_corpus.name)]
        )
    )
)

# --- Define the RAG-Powered Model ---
# This defines the model you will deploy, a Gemini model configured to use your RAG tool.
rag_model = GenerativeModel(
    "gemini-2.5-flash", 
    tools=[rag_tool]
)

print(f"Model '{MODEL_DISPLAY_NAME}' defined successfully.")

# --- Deploy the Model ---
# This is the step that makes your model a resource in Vertex AI
print("Creating and deploying the model to an endpoint...")
try:
    endpoint = rag_model.deploy(
        endpoint_name=ENDPOINT_DISPLAY_NAME,
        display_name=MODEL_DISPLAY_NAME,
        # This machine type is a good starting point for a conversational agent
        machine_type="e2-standard-4",
        min_replica_count=1,
        max_replica_count=1
    )
    print("Deployment initiated. This may take several minutes...")
    # Optional: Poll for deployment to finish
    endpoint.wait()
    print("Deployment completed successfully!")
    
    # After deployment, the model is registered and gets a unique ID.
    print(f"\nYour RAG-powered model ID is: {endpoint.name}")
    print(f"The API endpoint URL is: {endpoint.uri}")

except Exception as e:
    print(f"An error occurred during deployment: {e}")

