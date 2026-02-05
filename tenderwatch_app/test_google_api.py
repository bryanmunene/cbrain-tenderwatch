"""
Test Google Custom Search API credentials directly
"""
import requests

# Replace with your actual API key and CX
API_KEY = "AIzaSyDyh1DFo-MkpO8piC3-HGWpaI-CyIPwuKofg"
CX = "808d5448c489544e4"  # Correct CX from screenshot (no 'b')

# Test URL
url = f"https://www.googleapis.com/customsearch/v1?key={API_KEY}&cx={CX}&q=test&num=1"

print(f"Testing Google Custom Search API...")
print(f"API Key: {API_KEY[:10]}...{API_KEY[-4:]}")
print(f"CX: {CX}")
print(f"\nURL: {url}\n")

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! API credentials are valid.")
        data = response.json()
        print(f"Total results: {data.get('searchInformation', {}).get('totalResults', 0)}")
    elif response.status_code == 403:
        print("\n❌ 403 Forbidden - Possible causes:")
        print("   1. API key is invalid or expired")
        print("   2. Custom Search API not enabled in Google Cloud Console")
        print("   3. API key restrictions (check HTTP referrers/IP allowlist)")
        print("   4. CX ID doesn't match your search engine")
    elif response.status_code == 400:
        print("\n❌ 400 Bad Request - Possible causes:")
        print("   1. CX ID is incorrect")
        print("   2. Billing not set up (free tier requires billing on file)")
        print("   3. Custom Search API not enabled")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")

print("\n\n🔍 Next steps:")
print("1. Go to: https://console.cloud.google.com/apis/library/customsearch.googleapis.com")
print("2. Ensure 'Custom Search API' is ENABLED")
print("3. Go to: https://console.cloud.google.com/billing")
print("4. Ensure billing account is linked (even for free tier)")
print("5. Verify CX at: https://programmablesearchengine.google.com/controlpanel/all")
