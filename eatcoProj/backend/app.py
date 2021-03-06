from audioop import cross
from flask import Flask, request, redirect, render_template, url_for, session
from webSearchAPI import lookupRecipes
from pymongo import MongoClient
from dotenv import load_dotenv
from urllib.parse import quote
import os, json, requests
from googlesearch import search
from bs4 import BeautifulSoup
from flask_cors import CORS, cross_origin

app = Flask(__name__)
cors = CORS(app)

app.config['SECRET_KEY'] = 'Shivam&Arnav - Ended 2022'

load_dotenv()

cluster = MongoClient(os.environ.get('dbURI'))# + '&ssl=true&ssl_cert_reqs=CERT_NONE&connect=false')

SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID')

SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')

db = cluster["mydb"]

users = db["todos"]

@app.route('/auth/')
def auth_page_for_redirect():
    return render_template("auth.html")

@app.route('/get-recipe', methods=['GET'])
@cross_origin()
def getRecipe():
    return lookupRecipes(request.args['search'])

@app.route('/get-trees-saved')
@cross_origin()
def getTreesSaved():
    username = request.args.get('user')
    user = users.find_one({"username":username})
    if user is not None:
        return {"message": user['treesSaved']}
    else:
        return {"message": 0}

@app.route('/update-saved', methods=['GET','POST'])
@cross_origin()
def savedUpdate():
    if request.method == 'GET':
        user = request.args.get("username")
        the_user = users.find_one({'username': user})
        return {"recipesSaved": the_user["recipesSaved"]} if the_user != None else {"recipesSaved": []}
    recipe_string = request.form.get("recipe")
    if recipe_string != None:
        recipe_string = recipe_string.replace('\'','\"')
        recipe = json.loads(recipe_string)
        user = request.form.get("username")
        if user == "null":
            return {"recipedSaved": []}
        trees_saved = recipe['trees_saved']
        updateTrees = {
            "$set": {"treesSaved": 10}
        }
        users.update_one({'username': user}, updateTrees)

        updateSavedRecipes(user, recipe)
        the_user = users.find_one({'username': user})
        return {"recipesSaved": the_user["recipesSaved"]}
    else:
        return {"recipesSaved": []}

@app.route('/update-viewed', methods=['GET','POST'])
@cross_origin()
def viewedUpdate():
    if request.method == 'GET':
        user = request.args.get("username")
        the_user = users.find_one({'username': user})
        return {"recipesSaved": the_user["recipesViewed"]} if the_user != None else {"recipesViewed": []}
    recipe_string = request.form.get("recipe")
    if recipe_string != None:
        recipe_string = recipe_string.replace('\'','\"')
        recipe = json.loads(recipe_string)
        user = request.form.get("username")
        if user == "null":
            return {"recipesViewed": []}
        updateViewedValue(user, recipe)
        the_user = users.find_one({'username': user})
        return {"recipesViewed": the_user["recipesViewed"]}
    else:
        return {"recipesViewed": []}
    
def updateSavedRecipes(username, recipe):
    exists = False
    for user in list(users.find({"recipesSaved": {"$exists": True, "$not": {"$size": 0}}})):
        if user['username'] == username:
            exists = True 
            break
    if not exists:
        updateEmpty = {
            "$set": {"recipesSaved": [recipe]}
        }
        users.update_one({'username':username}, updateEmpty)
    else:
        recipes = list(users.find({'username':username}))[0]['recipesSaved']
        recipes.append(recipe)
        updateFilled = {
            "$set": {"recipesSaved": recipes}
        }
        users.update_one({'username':username}, updateFilled)

def updateViewedValue(username, recipe):

    exists = False
    for user in list(users.find({"recipesViewed": {"$exists": True}})):
        if user['username'] == username:
            exists = True 
            break
    
    if not exists:
        updateEmpty = {
            "$set": {"recipesViewed": [recipe]}
        }
        users.update_one({'username':username}, updateEmpty)
    else:
        recipes = list(users.find({'username':username}))[0]['recipesViewed']
        recipes.append(recipe)
        updateFilled = {
            "$set": {"recipesViewed": recipes}
        }
        users.update_one({'username':username}, updateFilled)

@app.route('/login/', methods=['POST'])
@cross_origin()
def user_login_check():
    username = request.form.get('Username')
    password = request.form.get('Password')
    user = users.find_one({"username":username})
    if user is not None:
        if password == user['password']:
            return {"message" : "YAY"}
        else:
            return {"message": "Incorrect password"}
    else:
        return {"message": "Please create an account first"}

@app.route('/register/', methods=['POST'])
@cross_origin()
def user_register_check():
    username = request.form.get('Username')
    password = request.form.get('Password')
    Confpassword = request.form.get('ConfPassword')
    _id = users.count_documents({})+1
    if Confpassword != password:
        return "OPEN YOUR EYES"
    user = {
        '_id': _id,
        'username': username,
        'password': password,
        'treesSaved': 0
    }
    users.insert_one(user)
    return user

SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'

SPOTIFY_REDIRECT_URI = 'http://localhost:5000/authorize-spotify'
SPOTIFY_SCOPES = 'user-top-read playlist-modify-private playlist-modify-public'
SPOTIFY_SHOW_DIALOG = 'true'

spotify_auth_query_params = {
    'response_type': 'code',
    'redirect_uri': SPOTIFY_REDIRECT_URI,
    'scope': SPOTIFY_SCOPES,
    'show_dialog': SPOTIFY_SHOW_DIALOG,
    'client_id': SPOTIFY_CLIENT_ID
}

@app.route('/login-spotify', methods=['GET'])
@cross_origin()
def login_spotify():
    session['recipe'] = request.args.get('recipe')
    url_args = "&".join(["{}={}".format(key, quote(val)) for key, val in spotify_auth_query_params.items()])
    auth_url = "{}/?{}".format(SPOTIFY_AUTH_URL, url_args)
    return redirect(auth_url)

@app.route('/authorize-spotify/')
@cross_origin()
def auth_spotify():
    genres = []
    track_ids = []
    track_names = []
    auth_token = request.args['code']
    code_payload = {
        'grant_type': 'authorization_code',
        'code': str(auth_token),
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET,
    }
    post_request = requests.post(SPOTIFY_TOKEN_URL, data = code_payload)
    response_data = json.loads(post_request.text)
    access_token = response_data['access_token']
    refresh_token = response_data['refresh_token']
    token_type = response_data['token_type']
    expires_in = response_data['expires_in']

    authorization_header = {'Authorization': 'Bearer {}'.format(access_token)}

    user_profile_api_endpoint = "https://api.spotify.com/v1/me"
    profile_response = requests.get(user_profile_api_endpoint, headers = authorization_header)
    profile_data = json.loads(profile_response.text)
    user_id = profile_data['uri'][13:]

    recipe_from_session = session['recipe']
    recipe_from_session = recipe_from_session.replace('\'', '\"')
    recipe_json = json.loads(recipe_from_session)
    recipe_json_title = recipe_json['title']
    recipe_json_ingredients = recipe_json['ingredients']

    create_playlist_api_endpoint = f'https://api.spotify.com/v1/users/{user_id}/playlists'
    create_playlist_params = json.dumps({
        'name': recipe_json_title,
        'description': 'Generated by Khanna and Sons',
        'public': True
    })
    create_playlist_response = requests.post(create_playlist_api_endpoint, data = create_playlist_params, headers = authorization_header)
    create_playlist_data = json.loads(create_playlist_response.text)

    top_artists_endpoint = user_profile_api_endpoint + '/top/artists'
    top_tracks_endpoint = user_profile_api_endpoint + '/top/tracks'
    limit = 50
    time_range = 'medium_term'
    artists_response = requests.get(top_artists_endpoint + '?offset=0&limit=50&time_range=' + time_range, headers = authorization_header)
    artists_data = json.loads(artists_response.text)
    
    tracks_response = requests.get(top_tracks_endpoint + '?offset=0&limit=' + str(limit) + '&time_range=' + time_range, headers = authorization_header)
    tracks_data = json.loads(tracks_response.text)
    for item in tracks_data['items']:
        track_ids.append(item['id'])
        track_names.append(item['name'])
    track_ids_str = ','.join(track_ids)

    audio_features_endpoint = "https://api.spotify.com/v1/audio-features"
    audio_features_response = requests.get(audio_features_endpoint + '?ids=' + track_ids_str, headers = authorization_header)
    audio_features_data = json.loads(audio_features_response.text)
    acousticness, danceability, energy, liveness, loudness, tempo = 0,0,0,0,0,0
    for song_data in audio_features_data['audio_features']:
        acousticness += song_data['acousticness']
        danceability += song_data['danceability']
        energy += song_data['energy']
        liveness += song_data['liveness']
        loudness += song_data['loudness']
        tempo += song_data['tempo']
    acousticness_avg = acousticness / len(audio_features_data['audio_features'])
    danceability_avg = danceability / len(audio_features_data['audio_features'])
    energy_avg = energy / len(audio_features_data['audio_features'])
    liveness_avg = liveness / len(audio_features_data['audio_features'])
    loudness_avg = loudness / len(audio_features_data['audio_features'])
    tempo_avg = tempo / len(audio_features_data['audio_features'])

    audio_data = {"acousticness" : acousticness_avg, "danceability": danceability_avg, "energy": energy_avg, "liveness": liveness_avg, "loudness": loudness_avg, "tempo": tempo_avg}

    for artist in artists_data['items']:
        for genre in artist['genres']:
            genres.append(genre)
    genres = list(set(genres))
    
    for i, feature in enumerate(audio_features_data['audio_features']):
        feature['name'] = track_names[i]
    return generate_playlist({"audio_data": audio_data, "genres": genres, "recipe": {"title": recipe_json_title, "ingredients": recipe_json_ingredients}, "headers": authorization_header, 'playlist_id': create_playlist_data['id']})

# @app.route('/playlist-generate/')
def generate_playlist(messages):
    # return messages
    # messages = messages.replace('\'', '\"')
    search_query = (str(messages['recipe']['title']) + 'site:wikipedia.org').lower()

    country = None

    search_queries = []
    authorization_header = messages['headers']

    for link in search(search_query, tld='com', lang='en', num=1, start=0, stop=1, pause=2):
        result = requests.get(link)
        results = BeautifulSoup(result.text, "html.parser")
        country = results.find(("td"), {"class": "infobox-data country-name"}).find(("a")).text

    search_queries = [('https://api.spotify.com/v1/search?type=track&limit=1&q=' + country + ' ' + str(genre)) for genre in messages['genres']]
    audio_features_endpoint = "https://api.spotify.com/v1/audio-features"
    search_query_responses = [requests.get(query, headers = authorization_header) for query in search_queries]
    search_query_datas = [json.loads(response.text) for response in search_query_responses]

    track_ids = []
    for query in search_query_datas:
        for track in query['tracks']['items']:
            track_ids.append(track['id'])
    track_ids = list(set(track_ids))
    track_ids_str = ','.join(track_ids)
    audio_features_response = requests.get(audio_features_endpoint + '?ids=' + track_ids_str, headers = authorization_header)
    audio_features_data = json.loads(audio_features_response.text)
    data_diffs = []
    for song_data in audio_features_data['audio_features']:
        acousticness = song_data['acousticness'] - messages['audio_data']['acousticness']
        danceability = song_data['danceability'] - messages['audio_data']['danceability']
        energy = song_data['energy'] - messages['audio_data']['energy']
        liveness = song_data['liveness'] - messages['audio_data']['liveness']
        loudness = song_data['loudness'] - messages['audio_data']['loudness']
        tempo = song_data['tempo'] - messages['audio_data']['tempo']
        data_diff = acousticness + danceability + energy + liveness + loudness + tempo
        data_diffs.append((abs(data_diff), song_data['id']))

    data_diffs.sort(key=lambda tup: tup[0])
    uris_list = []
    for uri in data_diffs:
        uris_list.append("spotify:track:" + uri[1])
    uris_string = ','.join(uris_list)

    playlist_id = messages['playlist_id']
    add_song_api_endpoint = 'https://api.spotify.com/v1/playlists/' + str(playlist_id)+ '/tracks'
    print(add_song_api_endpoint)
    add_song_params = {
        'uris': uris_list
    }
    add_song_response = requests.post(add_song_api_endpoint, data = json.dumps(add_song_params), headers = authorization_header)
    add_song_data = json.loads(add_song_response.text)
    return redirect('https://open.spotify.com/playlist/' + playlist_id)

if __name__ == '__main__':
    app.run(debug=True)



