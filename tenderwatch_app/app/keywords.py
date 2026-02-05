"""
TenderWatch Keywords — F2-Aligned (Non-Strict)
===============================================
Flat keyword domains for detecting cBrain F2-relevant tenders:
EDMS + records + workflow + case handling + process automation + e-government.

Design Principles:
- Favor recall over precision (miss nothing, rank later)
- Any keyword hit is a signal, not a filter
- Multiple hits increase relevance
- Phrase proximity increases relevance
- No single keyword is mandatory
- Let scoring, not exclusion, decide relevance

Role Separation:
- Scanner = capture + timing filter
- AI = reasoning + ranking  
- Human = decision
"""

# =============================================================================
# FLAT KEYWORD DOMAINS (for domain tagging and scoring)
# =============================================================================

KEYWORD_DOMAINS = {
    "EDMS": [
        # Core terms
        "electronic document management",
        "edms",
        "edrms",  # Electronic Document AND Records Management System
        "electronic document and records management",
        "dms",
        "document management system",
        "document management",
        "document repository",
        "document tracking",
        "document capture",
        "document digitization",
        "intelligent document processing",
        "optical character recognition",
        "ocr",
        "paperless",
    ],
    
    "Records": [
        # Core records
        "records management",
        "electronic records",
        "records management system",
        "records information",
        "records lifecycle",
        "records retention",
        "records disposal",
        "records digitization",
        "digital records",
        # Archives & registry
        "archives",
        "archival system",
        "archives management",
        "registry",
        "file registry",
        "file tracking",
        "file plan",
        "classification scheme",
        # Compliance
        "information governance",
        "audit trail",
        "audit logging",
        "legal hold",
        "retention policy",
        "data retention",
        "compliance management",
        "iso 15489",
        "right to information",
        "foia",
    ],
    
    "ECM": [
        "enterprise content management",
        "ecm",
        "content services platform",
        "content services",
        "content management",
        "unstructured data management",
    ],
    
    "Workflow": [
        # Core workflow
        "workflow",
        "workflow system",
        "workflow automation",
        "workflow management",
        "approval workflow",
        "approval system",
        "approval process",
        # BPM
        "business process management",
        "bpm",
        "process automation",
        "digital process automation",
        "process optimization",
        "process orchestration",
        # Tasks
        "task routing",
        "task management",
        "work item",
        "service orchestration",
    ],
    
    "Case": [
        # Core case
        "case management",
        "case handling",
        "case tracking",
        "case management system",
        "docket",
        "docket management",
        "matter management",
        # Complaints & grievances
        "complaint management",
        "complaints handling",
        "grievance",
        "grievance redress",
        "grm",
        "feedback management",
        # Legal/regulatory
        "legal case management",
        "litigation management",
        "court management",
        "judicial case management",
        "regulatory case",
        "inspection management",
        "licensing system",
        "permit management",
    ],
    
    "Forms": [
        "electronic forms",
        "e-forms",
        "digital forms",
        "form automation",
        "e-memos",
        "electronic memos",
        "digital correspondence",
        "correspondence management",
    ],
    
    "ServiceDelivery": [
        "service request",
        "citizen services",
        "e-services",
        "service delivery",
        "public service delivery",
        "citizen portal",
        "government portal",
        "citizen engagement",
        "public grievance",
    ],
    
    "Gov": [
        # E-government
        "e-government",
        "egovernment",
        "digital government",
        "e-governance",
        "egovernance",
        "smart government",
        "government automation",
        "public sector digitization",
        "public sector digitalisation",
        "public sector transformation",
        # Context signals
        "government",
        "ministry",
        "county government",
        "public sector",
        "parastatal",
        "state corporation",
        "government agency",
        "government department",
        "public institution",
        "local authority",
        "municipal",
        "regional government",
    ],
    
    "Collaboration": [
        "intranet",
        "collaboration platform",
    ],
    
    "Implementation": [
        "system implementation",
        "solution implementation",
        "software implementation",
        "solution deployment",
        "system configuration",
        "system integration",
        "change management",
        "capacity building",
        "user training",
        "knowledge transfer",
        "post-implementation support",
        "managed services",
        "support and maintenance",
    ],
}

# =============================================================================
# PLATFORM LOCK-IN SIGNALS (already chose a vendor - F2 unlikely to compete)
# Flag these but don't exclude - client may be open to alternatives
# =============================================================================

PLATFORM_LOCKIN_SIGNALS = [
    # Microsoft ecosystem (if they're asking for implementation, not procurement)
    "power platform implementation",
    "power platform solution",
    "power apps development",
    "power automate implementation", 
    "sharepoint implementation",
    "sharepoint development",
    "sharepoint solution",
    "microsoft 365 implementation",
    "dynamics 365 implementation",
    "azure implementation",
    "build solutions in power platform",
    "develop on power platform",
    "power platform developer",
    "power platform consultant",
    
    # Oracle ecosystem
    "oracle implementation",
    "oracle consultant",
    "oracle erp",
    "oracle financials",
    "oracle cloud",
    "oracle fusion",
    
    # SAP ecosystem  
    "sap implementation",
    "sap consultant",
    "sap erp",
    "sap s/4hana",
    "sap successfactors",
    
    # Salesforce ecosystem
    "salesforce implementation",
    "salesforce developer",
    "salesforce consultant",
    
    # OpenText ecosystem
    "opentext implementation",
    "documentum implementation",
    "opentext consultant",
    
    # Other specific platforms
    "laserfiche implementation",
    "alfresco implementation",
    "m-files implementation",
    "ibm filenet implementation",
    "hyland onbase implementation",
]

# Signals that the client is OPEN to alternatives (good for F2)
OPEN_PROCUREMENT_SIGNALS = [
    "supply and implementation",
    "supply, installation",
    "provision of",
    "procurement of",
    "acquisition of",
    "request for proposal",
    "request for quotation",
    "invitation to tender",
    "expression of interest",
    "prequalification",
    "open tender",
    "competitive bidding",
    "best value",
    "solution agnostic",
    "platform agnostic",
    "vendor neutral",
]

# =============================================================================
# NEGATIVE SIGNALS (reduce score, don't exclude)
# =============================================================================

NEGATIVE_SIGNALS = [
    # Pure hosting/storage (no process/workflow)
    "data center",
    "data centre",
    "colocation",
    "hosting services",
    "cloud hosting",
    "storage infrastructure",
    "backup services",
    "disaster recovery only",
    # Website-only
    "website design",
    "website development only",
    "web design",
    "social media management",
    # Hardware-only
    "hardware supply",
    "computer supply",
    "laptop supply",
    "printer supply",
    "networking equipment",
    "cabling",
]

# =============================================================================
# FLATTENED KEYWORDS (for simple matching)
# =============================================================================

ALL_KEYWORDS = sorted(
    {kw.lower() for domain in KEYWORD_DOMAINS.values() for kw in domain}
)

# Map each keyword back to its domain(s)
KEYWORD_TO_DOMAIN = {}
for domain, keywords in KEYWORD_DOMAINS.items():
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower not in KEYWORD_TO_DOMAIN:
            KEYWORD_TO_DOMAIN[kw_lower] = []
        KEYWORD_TO_DOMAIN[kw_lower].append(domain)

# =============================================================================
# PRIORITY DOMAIN COMBINATIONS (bonus scoring)
# =============================================================================

# These combinations signal high relevance for F2
PRIORITY_COMBINATIONS = [
    # HIGH priority: workflow + records + government
    (["Workflow", "Records", "Gov"], 10, "HIGH"),
    (["Case", "Records", "Gov"], 10, "HIGH"),
    (["Workflow", "Case", "Gov"], 10, "HIGH"),
    
    # MEDIUM priority: records OR workflow + public context
    (["Records", "Gov"], 5, "MEDIUM"),
    (["Workflow", "Gov"], 5, "MEDIUM"),
    (["Case", "Gov"], 5, "MEDIUM"),
    (["EDMS", "Gov"], 5, "MEDIUM"),
    (["ECM", "Gov"], 5, "MEDIUM"),
    
    # Records + workflow/case (even without gov context)
    (["Records", "Workflow"], 4, "MEDIUM"),
    (["Records", "Case"], 4, "MEDIUM"),
    (["EDMS", "Workflow"], 4, "MEDIUM"),
    (["EDMS", "Case"], 4, "MEDIUM"),
]

# =============================================================================
# LEGACY EXPORTS (for backward compatibility)
# =============================================================================

# Keep KEYWORD_GROUPS for categorizer.py compatibility
KEYWORD_GROUPS = KEYWORD_DOMAINS

# Generic standalone keywords (still count but with lower weight alone)
GENERIC_STANDALONE_KEYWORDS = {
    "bid", "tender", "rfp", "rfq", "procurement", "contract",
    "ministry", "government", "agency", "department", "system",
    "platform", "solution", "software", "services", "management"
}

# Priority phrases (multi-word exact matches for bonus)
PRIORITY_PHRASES = [
    # 5+ word phrases (very specific)
    "electronic document and records management",
    "electronic document management system",
    "enterprise content management system",
    "business process management system",
    "case management system implementation",
    
    # 4 word phrases
    "document management system",
    "records management system", 
    "case management system",
    "workflow management system",
    "content services platform",
    "business process automation",
    "digital government platform",
    "complaint management system",
    "grievance redress system",
    "permit management system",
    
    # 3 word phrases
    "workflow automation",
    "process automation",
    "case handling",
    "case tracking",
    "document tracking",
    "records digitization",
    "digital transformation",
    "system implementation",
]
