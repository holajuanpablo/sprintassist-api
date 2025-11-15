from flask import Flask
from waitress import serve
import os
import sys

print("--- WAITRESS APP: Top Level ---", file=sys.stderr, flush=True)
app = Flask(__name__)
print("--- WAITRESS APP: Flask created ---", file=sys.stderr, flush=True)

@app.route('/')
def home():
    print("--- WAITRESS APP: Handling / route ---", file=sys.stderr, flush=True)
    return "Waitress Says Hello!", 200

@app.route('/test')
def test():
    print("--- WAITRESS APP: Handling /test route ---", file=sys.stderr, flush=True)
    return "Waitress Test OK!", 200

print("--- WAITRESS APP: End of File,  __name__ is {} ---".format(__name__), file=sys.stderr, flush=True)

if __name__ == '__main__':
    print("--- WAITRESS APP: Running in main ---", file=sys.stderr, flush=True)
    port = int(os.environ.get("PORT", 8080))
    print(f"--- WAITRESS APP: Starting server on 0.0.0.0:{port} ---", file=sys.stderr, flush=True)
    serve(app, host='0.0.0.0', port=port)
