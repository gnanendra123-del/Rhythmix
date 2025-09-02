# A Flask application to serve a music discovery tool using the JioSaavn API.
# It includes routes for the main page, an API endpoint for search suggestions, and a streaming endpoint.

from flask import Flask, render_template, request, jsonify
import requests
import json
import urllib.parse
import urllib3

# Disable SSL warnings for the API calls.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- JioSaavn API Service Class ---
# This class encapsulates the logic for interacting with the JioSaavn API.
class SaavnApiService:
    BASE_URL = "https://www.jiosaavn.com/api.php"
    API_PARAMS = "&_format=json&_marker=0&api_version=4&ctx=web6dot0"

    @staticmethod
    def search_songs(query):
        """Search for songs on JioSaavn."""
        encoded_query = urllib.parse.quote(query)
        url = f"{SaavnApiService.BASE_URL}?__call=search.getResults&q={encoded_query}{SaavnApiService.API_PARAMS}"
        
        try:
            response = requests.get(url, verify=False)
            if response.status_code == 200:
                # Clean JSON response by removing any leading non-JSON characters.
                clean_json = response.text[response.text.find('{'):]
                data = json.loads(clean_json)
                return data.get('results', [])
            else:
                raise Exception('Failed to search songs')
        except Exception as e:
            print(f'Search Error: {e}')
            return [] # Return an empty list on failure

    @staticmethod
    def get_streaming_url(song_id):
        """Get streaming URL for a song."""
        # Step 1: Get song details to find the encrypted URL.
        details_url = f"{SaavnApiService.BASE_URL}?__call=song.getDetails&pids={song_id}{SaavnApiService.API_PARAMS}"
        
        try:
            details_response = requests.get(details_url, verify=False)
            details_data = json.loads(details_response.text)
            
            if 'songs' in details_data and len(details_data['songs']) > 0:
                song_data = details_data['songs'][0]
                more_info = song_data.get('more_info', {})
                if 'encrypted_media_url' in more_info:
                    encrypted_url = more_info['encrypted_media_url']
                else:
                    raise Exception('Encrypted media URL not found')
            else:
                raise Exception('Song data not found')
                
        except Exception as e:
            print(f'Get Details Error: {e}')
            raise Exception('Could not get song details')
        
        # Step 2: Generate an auth token for the streaming URL.
        encoded_encrypted_url = urllib.parse.quote(encrypted_url)
        token_url = f"{SaavnApiService.BASE_URL}?__call=song.generateAuthToken&url={encoded_encrypted_url}&bitrate=320{SaavnApiService.API_PARAMS}"
        
        try:
            token_response = requests.get(token_url, verify=False)
            token_data = json.loads(token_response.text)
            
            if isinstance(token_data.get('auth_url'), str):
                stream_url = token_data['auth_url']
                # Transform URL to the correct CDN for streaming.
                return stream_url.replace('web.saavncdn.com', 'aac.saavncdn.com').replace('_96.mp4', '_320.mp4')
            else:
                raise Exception('Failed to get auth_url, token may have expired')
                
        except Exception as e:
            print(f'Generate Token Error: {e}')
            raise Exception('Could not generate streaming URL')

# --- Flask App Setup and Routes ---
app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    """Main route to render the search page and display results."""
    results = []
    error = None
    query = ""
    
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if query:
            try:
                results = SaavnApiService.search_songs(query)
            except Exception as e:
                error = str(e)
    
    return render_template("index.html", results=results, error=error, query=query)

@app.route("/api/search")
def api_search():
    """API endpoint for search, to be used by the client-side JavaScript for live suggestions."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    try:
        results = SaavnApiService.search_songs(query)
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/stream/<song_id>")
def api_stream(song_id):
    """API endpoint to get a streaming URL for a specific song ID."""
    try:
        stream_url = SaavnApiService.get_streaming_url(song_id)
        return jsonify({'stream_url': stream_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Entry point for the application.
if __name__ == "__main__":
    app.run(debug=True)
