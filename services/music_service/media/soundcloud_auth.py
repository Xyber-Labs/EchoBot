"""
This script is used to authenticate with SoundCloud and get the access token and refresh token.
First you need to get auth_code. For this constract the link with your client id and redirect uri.
Redirect uri can be localhost or any other uri doesnt matter.
Than follow the link and after authorizing you will get the auth_code by following redirect uri.
Uri example:
https://soundcloud.com/connect?client_id=CLIENT_ID&redirect_uri=http://localhost&response_type=code
"""

import json

import requests

CLIENT_SECRET = (
    ""  # Your cliend secret from settings.soundcloud.SOUNDCLOUD_CLIENT_SECRET
)

# Compose the uri example about with this client id and redirect uri
# uri = f"https://soundcloud.com/connect?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code"
# 2. Go to the AUTH_URL, authorize, and get the NEW code from the redirect URL.
#    It must be a fresh code you get right before running this script.
# Get it from the redirect uri
AUTHORIZATION_CODE = ""

# These values should be correct
CLIENT_ID = ""  # take it from .env
REDIRECT_URI = "http://localhost"
# ==============================================================================


# The SoundCloud API endpoint for exchanging the token
token_url = "https://api.soundcloud.com/oauth2/token"

payload = {
    "grant_type": "authorization_code",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "code": AUTHORIZATION_CODE,
}

print("Attempting to exchange code for token...")
print(f"  - Using Client ID: {CLIENT_ID}")
print(f"  - Using Redirect URI: {REDIRECT_URI}")
print(f"  - Using Code (first 15 chars): {AUTHORIZATION_CODE[:15]}...")


try:
    # We send the request to the SoundCloud API
    response = requests.post(token_url, data=payload)

    # This line is CRITICAL. It will raise an error if the status is 4xx or 5xx.
    response.raise_for_status()

    # If the request was successful (status 200), we get the tokens.
    data = response.json()
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")

    print("\n--- SUCCESS! ---")
    print("Save these tokens in a safe place.")
    print(f"\nYour Access Token is: {access_token}")
    print(f"Your Refresh Token is: {refresh_token}")


except requests.exceptions.HTTPError as http_err:
    # THIS IS THE MOST IMPORTANT PART FOR DEBUGGING
    # It catches the HTTP error and prints the response from SoundCloud
    print("\n--- HTTP ERROR OCCURRED ---")
    print(f"Status Code: {http_err.response.status_code}")
    print("Full error response from SoundCloud:")

    # SoundCloud usually sends a JSON object with the error details
    try:
        error_details = http_err.response.json()
        print(json.dumps(error_details, indent=2))
    except json.JSONDecodeError:
        # If the response isn't JSON, print it as raw text
        print(http_err.response.text)

except Exception as err:
    print("\n--- A DIFFERENT ERROR OCCURRED ---")
    print(err)
