"""Test platform lock-in detection."""
import json
from app.scoring import score_text

def test_tender(name, text):
    print("="*60)
    print(f"TEST: {name}")
    print("="*60)
    score, _, breakdown_json = score_text(text, text)
    result = json.loads(breakdown_json)
    print(f"Score: {score}")
    print(f"Priority: {result.get('priority_level', result.get('priority', 'N/A'))}")
    print(f"Procurement Status: {result.get('procurement_status', 'N/A')}")
    print(f"F2 Fit: {result.get('likely_fit_for_f2', result.get('likely_fit_for_F2', 'N/A'))}")
    if result.get('platform_lockin_signals'):
        print(f"Lock-in signals: {result['platform_lockin_signals']}")
    if result.get('open_procurement_signals'):
        print(f"Open signals: {result['open_procurement_signals']}")
    if result.get('inferred_domains'):
        print(f"Domains: {result['inferred_domains']}")
    elif result.get('domains_matched'):
        print(f"Domains: {result['domains_matched']}")
    print()

# Test 1: Clear lock-in (Microsoft Power Platform implementation)
test_tender(
    "Microsoft Power Platform Implementation (LOCKED)", 
    "Tender for Power Platform Implementation Partner - KAA seeks a firm to implement Microsoft Power Platform for document management and workflow automation"
)

# Test 2: Open procurement
test_tender(
    "Open Tender for EDRMS (OPEN)",
    "Request for Proposal for Provision of Electronic Document and Records Management System - The Authority invites sealed bids for supply, installation and implementation of EDRMS"
)

# Test 3: Mixed - has both lock-in and open signals
test_tender(
    "SharePoint mentioned but open tender (DISCUSS)",
    "Open Tender for Provision of Records Management System - Preference for SharePoint integration capabilities. Sealed bids invited."
)

# Test 4: Oracle implementation for EDMS (locked but relevant)
test_tender(
    "Oracle EDMS Implementation (LOCKED + RELEVANT)",
    "Documentum Implementation Services - Consultancy for Oracle document management and records management solutions"
)

# Test 5: Pure Oracle (no F2 relevance)
test_tender(
    "Pure Oracle ERP (NOT RELEVANT)",
    "Oracle ERP Implementation Services - Consultancy for Oracle Financials and HR modules implementation"
)

# Test 5: Real KAA example - open
test_tender(
    "KAA EDRMS (like the real tender you shared)",
    "PROVISION OF ELECTRONIC DOCUMENT RECORD MANAGEMENT SYSTEM(EDRMS) FOR KENYA AIRPORTS AUTHORITY - Deadline: 15-Jan-2026"
)
