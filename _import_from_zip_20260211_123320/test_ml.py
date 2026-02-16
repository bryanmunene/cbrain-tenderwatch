"""Test ML Ranker Module"""
from app.ml_ranker import extract_features, get_model_status, ml_score

# Test feature extraction
print("Testing feature extraction...")
features = extract_features("Electronic Document Management System for Ministry of Finance")
print(f"Features extracted: {len(features)}")
print("Sample features:")
for k in list(features.keys())[:8]:
    print(f"  {k}: {features[k]}")

print()
print("Testing ML score...")
result = ml_score("Case Management System for citizen complaints handling", "")
print(f"Method: {result['method']}")
print(f"Keyword Score: {result['keyword_score']}")
print(f"Semantic Score: {result['semantic_score']}")
print(f"Final Score: {result['final_score']}")
print(f"Explanation: {result['explanation']}")

print()
print("Testing locked tender...")
result2 = ml_score("Power Platform Implementation Partner for document management", "The Authority has procured Microsoft Power Platform")
print(f"Method: {result2['method']}")
print(f"Final Score: {result2['final_score']}")
print(f"Explanation: {result2['explanation']}")

print()
print("Model Status:")
status = get_model_status()
for k, v in status.items():
    print(f"  {k}: {v}")
