"""
TenderWatch Keywords
=====================
Comprehensive keyword groups for detecting cBrain-relevant tenders.

Philosophy:
- Treat any occurrence as a signal, not a filter
- Prioritize tenders where multiple terms appear close together
- Prefer language describing movement of work, approvals, cases, or process automation
- Let scoring, not exclusion, decide relevance
- Noise is cheaper to discard than missed signal

This list catches:
- EDMS tenders that don't say "EDMS"
- Case systems hiding as "service platforms"
- Workflow platforms disguised as "digitization"
- Government projects that avoid technical labels
"""

KEYWORD_GROUPS = {
    "Records & Document Management": [
        # Core EDMS/DMS terms
        "electronic document management",
        "document management system",
        "dms",
        "edms",
        "electronic document and records management",
        "records management system",
        "electronic records management",
        "records information system",
        "enterprise content management",
        "ecm",
        "content services platform",
        "document repository",
        "digital records",
        
        # Archives & Registry
        "archives management",
        "archival system",
        "file registry system",
        "registry management",
        "file tracking system",
        "document tracking",
        
        # Records Lifecycle
        "records lifecycle management",
        "records retention",
        "records disposal",
        "classification scheme",
        "file plan",
        "information governance",
        "legal hold",
        "data retention policy",
        
        # Digitization
        "digitization of records",
        "scanning and indexing",
        "document digitization",
        "records digitization",
        "document capture",
        "optical character recognition",
        "ocr system",
        "intelligent document processing",
        "paperless office",
        
        # Compliance & Standards
        "compliance management",
        "audit trail",
        "audit logging",
        "right to information",
        "foia",
        "iso 15489",
    ],
    
    "Correspondence & Communication": [
        "correspondence management",
        "digital correspondence",
        "intranet solution",
        "collaboration platform",
        "electronic memos",
        "e-memo",
        "inward and outward correspondence",
        "mail management system",
    ],
    
    "Microsoft & Enterprise Platforms": [
        "sharepoint",
        "microsoft sharepoint online",
        "microsoft 365",
        "power platform",
        "power automate",
        "power apps",
        "office 365",
        "teams integration",
        "azure",
        "dynamics 365",
    ],
    
    "Workflow & Process Automation": [
        # Core Workflow
        "workflow system",
        "workflow automation",
        "workflow management system",
        "business process management",
        "bpm",
        "process automation",
        "digital process automation",
        
        # Task & Work Management
        "service orchestration",
        "task routing",
        "work item management",
        "approval workflows",
        "task management system",
        "approval system",
        
        # Forms
        "electronic forms",
        "e-forms",
        "digital forms",
        "form automation",
        
        # Analytics
        "process analytics",
        "reports and dashboards",
        "performance monitoring",
        "decision support system",
        "process optimization",
        "business intelligence",
    ],
    
    "Case & Matter Management": [
        # Core Case Management
        "case management system",
        "case handling system",
        "case tracking system",
        "matter management",
        "docket management",
        
        # Complaints & Grievances
        "complaint management system",
        "grievance redress system",
        "grievance redress mechanism",
        "grm system",
        "complaints handling",
        "feedback management",
        
        # Legal & Regulatory
        "regulatory case management",
        "inspection management system",
        "licensing system",
        "permit management system",
        "legal case management",
        "litigation management",
        "court management system",
        "judicial case management",
    ],
    
    "E-Government & Citizen Services": [
        # Service Delivery
        "service request system",
        "citizen services portal",
        "e-services portal",
        "service delivery platform",
        "public service delivery",
        
        # E-Government
        "e-government platform",
        "digital government",
        "public sector digitization",
        "government workflow system",
        "e-governance",
        "smart government",
        "government automation",
        
        # Citizen Engagement
        "citizen portal",
        "government portal",
        "citizen engagement",
        "public grievance system",
    ],
    
    "Implementation & Services": [
        # Deployment
        "system implementation",
        "solution deployment",
        "system configuration",
        "system integration",
        "software implementation",
        
        # Change & Training
        "change management",
        "capacity building",
        "user training",
        "knowledge transfer",
        
        # Support
        "post-implementation support",
        "managed services",
        "support and maintenance",
        "system support",
    ],
    
    "General ICT & Software": [
        # ICT Terms
        "ict consultancy",
        "ict consulting",
        "ict services",
        "ict solution",
        "ict system",
        "ict infrastructure",
        
        # Software Development
        "software development",
        "software solution",
        "software system",
        "software consultancy",
        "system development",
        "enterprise software",
        "enterprise application",
        
        # Digital Transformation
        "digital platform",
        "digital solution",
        "digital system",
        "digital transformation",
        "digitalization",
        "modernization",
        
        # Enterprise Systems
        "management information system",
        "mis",
        "erp system",
        "enterprise resource planning",
        "database management",
        "database system",
        "web application",
        "web portal",
        "web-based system",
        "online system",
        
        # Cloud & Infrastructure
        "cloud platform",
        "cloud solution",
        "cloud migration",
        "saas",
        "software as a service",
    ],
    
    "Government & Public Sector": [
        # Government bodies
        "ministry",
        "government agency",
        "county government",
        "public sector",
        "parastatal",
        "state corporation",
        "government department",
        "public institution",
        "local authority",
        "municipal",
        "regional government",
    ],
}

# Flatten all keywords into a single list for matching
ALL_KEYWORDS = sorted(
    {kw.lower() for group in KEYWORD_GROUPS.values() for kw in group}
)

# Keywords that are too generic on their own but valuable in context
# These still contribute to scoring but with lower weight when alone
GENERIC_STANDALONE_KEYWORDS = {
    "bid", "tender", "rfp", "rfq", "procurement", "contract",
    "ministry", "government", "agency", "department", "system",
    "platform", "solution", "software", "services", "management"
}

# Multi-word phrases get bonus scoring (more specific = more relevant)
# Phrases with 3+ words are likely describing exactly what we want
PRIORITY_PHRASES = [
    # 5+ word phrases (very specific, high bonus)
    "electronic document and records management",
    "electronic document management system",
    "enterprise content management system",
    "business process management system",
    "case management system implementation",
    "workflow management system implementation",
    "citizen services portal development",
    "public sector digitization project",
    
    # 4 word phrases (specific, good bonus)
    "document management system",
    "records management system",
    "case management system",
    "workflow management system",
    "content services platform",
    "business process automation",
    "digital government platform",
    "e-government platform implementation",
    "complaint management system",
    "grievance redress system",
    "permit management system",
    "licensing management system",
    
    # 3 word phrases (moderately specific)
    "workflow automation",
    "process automation",
    "case handling",
    "case tracking",
    "document tracking",
    "records digitization",
    "approval workflows",
    "task routing",
    "service orchestration",
    "digital transformation",
    "system implementation",
]
