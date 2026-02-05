"""
Google API Troubleshooting Checklist
=====================================

CURRENT STATUS: 403 Forbidden - "This project does not have the access to Custom Search JSON API."

This means the Custom Search API is NOT enabled in your Google Cloud project.

Follow these steps EXACTLY:
"""

import webbrowser

print("=" * 80)
print("GOOGLE CUSTOM SEARCH API TROUBLESHOOTING")
print("=" * 80)

print("\n✓ STEP 1: Find which Google Cloud Project your API key belongs to")
print("-" * 80)
print("1. Go to: https://console.cloud.google.com/apis/credentials")
print("2. Find API key: AIzaSyCx93DPr9QmJQKZu9MEOxKqQPnCPLDPwG4")
print("3. Note the PROJECT NAME at the top of the page")
print("4. Make sure you stay in THIS project for all remaining steps")
print("\nPress Enter when you've found the project name...")
input()

print("\n✓ STEP 2: Enable Custom Search API in that project")
print("-" * 80)
print("1. Open: https://console.cloud.google.com/apis/library/customsearch.googleapis.com")
print("2. Make sure the PROJECT NAME matches from Step 1")
print("3. Look for 'Custom Search API' heading")
print("4. Check the button - does it say 'ENABLE' or 'MANAGE'?")
print("   - If 'ENABLE': Click it, wait 30 seconds")
print("   - If 'MANAGE': API is already enabled (good!)")
print("\nPress Enter after clicking ENABLE (or if already enabled)...")
input()

print("\n✓ STEP 3: Check for API key restrictions")
print("-" * 80)
print("1. Go back to: https://console.cloud.google.com/apis/credentials")
print("2. Click on your API key: AIzaSyCx93DPr9QmJQKZu9MEOxKqQPnCPLDPwG4")
print("3. Scroll to 'API restrictions' section")
print("4. What is selected?")
print("   - 'Don't restrict key' (recommended for testing)")
print("   - 'Restrict key' with Custom Search API selected")
print("\nIf restricted to OTHER APIs, change to 'Don't restrict key' for now")
print("Press Enter when done...")
input()

print("\n✓ STEP 4: Verify billing account")
print("-" * 80)
print("1. Go to: https://console.cloud.google.com/billing")
print("2. Is a billing account linked to your project?")
print("   - If NO: Click 'LINK A BILLING ACCOUNT' and add credit card")
print("   - If YES: You're good (won't be charged for free tier)")
print("\nPress Enter when billing is set up...")
input()

print("\n✓ STEP 5: Wait 1-2 minutes for changes to propagate")
print("-" * 80)
print("Google Cloud takes time to activate new services...")
print("Press Enter to run test in 30 seconds...")
input()

import time
for i in range(30, 0, -1):
    print(f"\rWaiting {i} seconds...  ", end="", flush=True)
    time.sleep(1)

print("\n\n" + "=" * 80)
print("TESTING API NOW...")
print("=" * 80)

import requests

API_KEY = "AIzaSyCx93DPr9QmJQKZu9MEOxKqQPnCPLDPwG4"
CX = "808d5448c489544e4"
url = f"https://www.googleapis.com/customsearch/v1?key={API_KEY}&cx={CX}&q=test&num=1"

try:
    response = requests.get(url)
    print(f"\nStatus Code: {response.status_code}\n")
    
    if response.status_code == 200:
        print("🎉 SUCCESS! API is working!")
        print("✅ Auto-discovery is ready to use!")
        print("\nNext: Go to Streamlit Cloud and enter these credentials in Settings:")
        print(f"  Google API Key: {API_KEY}")
        print(f"  Google CX: {CX}")
    elif response.status_code == 403:
        print("❌ STILL 403 FORBIDDEN")
        print("\nPossible issues:")
        print("1. You enabled the API in the WRONG project")
        print("   → Go back to Step 1 and verify project name")
        print("2. API restrictions are blocking Custom Search API")
        print("   → Go back to Step 3 and set to 'Don't restrict key'")
        print("3. Changes haven't propagated yet")
        print("   → Wait another 5 minutes and run: python test_google_api.py")
        print("4. You need to create a NEW API key in the correct project")
        print("   → Delete old key, create new one, run: python test_google_api.py")
    else:
        print(f"❌ Unexpected status code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 80)
print("If still not working, you may need to:")
print("1. Create a NEW Google Cloud project")
print("2. Enable Custom Search API from the start")
print("3. Create a NEW API key in that project")
print("4. Link billing to the new project")
print("=" * 80)
