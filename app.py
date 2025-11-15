from flask import Flask
import os
import sys

print("--- SIMPLE APP: Top Level ---", file=sys.stderr)
app = Flask(__name__)
print("--- SIMPLE APP: Flask created ---", file=sys.stderr)

@app.route('/')
def home():
    print("--- SIMPLE APP: Handling / route ---", file=sys.stderr)
    return "Simple App Says Hello!", 200

@app.route('/test')
def test():
    print("--- SIMPLE APP: Handling /test route ---", file=sys.stderr)
    return "Simple App Test OK!", 200

print("--- SIMPLE APP: End of File ---", file=sys.stderr)
