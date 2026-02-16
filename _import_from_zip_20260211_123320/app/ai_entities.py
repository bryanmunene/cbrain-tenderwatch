"""
AI-powered entity extraction from tender descriptions
Automatically extracts buyer, budget, deadline, location, and duration
"""

import re
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Global spaCy model
_nlp = None

def load_nlp_model():
    """Load spaCy model (lazy loading)"""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            # Try to load model
            try:
                _nlp = spacy.load("en_core_web_sm")
                logger.info("✅ SpaCy NER model loaded successfully")
            except OSError:
                logger.warning("⚠️ SpaCy model not found. Run: python -m spacy download en_core_web_sm")
                _nlp = False
        except Exception as e:
            logger.error(f"❌ Failed to load spaCy: {e}")
            _nlp = False
    return _nlp if _nlp is not False else None

# Common buyer organizations
BUYER_KEYWORDS = [
    'ministry', 'government', 'county', 'department', 'authority', 
    'commission', 'agency', 'board', 'council', 'corporation',
    'united nations', 'world bank', 'undp', 'unicef', 'who',
    'african development bank', 'usaid', 'giz', 'dfid'
]

def extract_entities(title: str, description: str = "") -> Dict[str, any]:
    """
    Extract structured information from tender text
    
    Returns dict with:
        - buyer: Organization name
        - budget: Estimated value
        - deadline: Submission deadline
        - location: Country/region
        - duration: Contract duration
        - requirements: Key requirements list
    """
    text = f"{title} {description}".strip()
    
    entities = {
        'buyer': None,
        'budget': None,
        'deadline': None,
        'location': None,
        'duration': None,
        'requirements': []
    }
    
    if not text:
        return entities
    
    # Extract with spaCy NER if available
    nlp = load_nlp_model()
    if nlp:
        entities.update(_extract_with_spacy(text, nlp))
    
    # Extract with regex patterns (fallback or supplement)
    entities.update(_extract_with_regex(text))
    
    return entities

def _extract_with_spacy(text: str, nlp) -> Dict:
    """Extract entities using spaCy NER"""
    entities = {}
    
    try:
        doc = nlp(text[:5000])  # Limit to 5000 chars for performance
        
        # Extract organizations (potential buyers)
        orgs = [ent.text for ent in doc.ents if ent.label_ == 'ORG']
        if orgs:
            # Prefer organizations with buyer keywords
            for org in orgs:
                if any(kw in org.lower() for kw in BUYER_KEYWORDS):
                    entities['buyer'] = org
                    break
            if not entities.get('buyer'):
                entities['buyer'] = orgs[0]  # Use first org found
        
        # Extract locations
        locations = [ent.text for ent in doc.ents if ent.label_ in ['GPE', 'LOC']]
        if locations:
            entities['location'] = locations[0]
        
        # Extract money amounts
        money = [ent.text for ent in doc.ents if ent.label_ == 'MONEY']
        if money:
            entities['budget'] = money[0]
        
        # Extract dates (potential deadlines)
        dates = [ent.text for ent in doc.ents if ent.label_ == 'DATE']
        if dates:
            entities['deadline'] = dates[-1]  # Use last date mentioned
            
    except Exception as e:
        logger.error(f"SpaCy extraction error: {e}")
    
    return entities

def _extract_with_regex(text: str) -> Dict:
    """Extract entities using regex patterns"""
    entities = {}
    
    # Budget patterns
    budget_patterns = [
        r'(?:USD|KES|EUR|GBP)\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|M|thousand|K|billion|B))?',
        r'[\d,]+(?:\.\d+)?\s*(?:USD|KES|EUR|GBP)',
        r'budget.*?[\d,]+(?:\.\d+)?',
        r'value.*?[\d,]+(?:\.\d+)?'
    ]
    
    for pattern in budget_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and not entities.get('budget'):
            entities['budget'] = match.group().strip()
            break
    
    # Duration patterns
    duration_patterns = [
        r'\d+\s*(?:month|year|week)s?',
        r'(?:duration|period).*?\d+\s*(?:month|year|week)s?'
    ]
    
    for pattern in duration_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and not entities.get('duration'):
            duration_text = match.group()
            # Extract just the number and unit
            num_match = re.search(r'\d+\s*(?:month|year|week)s?', duration_text, re.IGNORECASE)
            if num_match:
                entities['duration'] = num_match.group().strip()
            break
    
    # Deadline patterns
    deadline_patterns = [
        r'(?:deadline|closing date|submission date).*?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        r'(?:before|by|until).*?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}'
    ]
    
    for pattern in deadline_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and not entities.get('deadline'):
            entities['deadline'] = match.group(1) if len(match.groups()) > 0 else match.group()
            break
    
    # Location patterns (countries)
    countries = [
        'Kenya', 'Uganda', 'Tanzania', 'Rwanda', 'Ethiopia',
        'Nigeria', 'South Africa', 'Ghana', 'Zambia', 'Zimbabwe',
        'Global', 'International', 'Regional', 'Africa'
    ]
    
    if not entities.get('location'):
        for country in countries:
            if country.lower() in text.lower():
                entities['location'] = country
                break
    
    # Extract key requirements (bullet points or numbered lists)
    requirements = []
    req_patterns = [
        r'(?:requirement|qualification|must have).*?(?:\n|$)',
        r'(?:•|\*|-|\d+\.)\s*(.+?)(?:\n|$)'
    ]
    
    for pattern in req_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        requirements.extend([m.strip() for m in matches if len(m.strip()) > 10])
    
    if requirements:
        entities['requirements'] = requirements[:5]  # Limit to top 5
    
    return entities

def extract_buyer(text: str) -> Optional[str]:
    """Quick extraction of just the buyer name"""
    entities = extract_entities(text, "")
    return entities.get('buyer')

def extract_budget(text: str) -> Optional[str]:
    """Quick extraction of just the budget"""
    entities = extract_entities(text, "")
    return entities.get('budget')

def extract_deadline(text: str) -> Optional[str]:
    """Quick extraction of just the deadline"""
    entities = extract_entities(text, "")
    return entities.get('deadline')

def format_entities_summary(entities: Dict) -> str:
    """Format extracted entities as readable summary"""
    parts = []
    
    if entities.get('buyer'):
        parts.append(f"👤 **Buyer:** {entities['buyer']}")
    
    if entities.get('budget'):
        parts.append(f"💰 **Budget:** {entities['budget']}")
    
    if entities.get('location'):
        parts.append(f"📍 **Location:** {entities['location']}")
    
    if entities.get('duration'):
        parts.append(f"⏱️ **Duration:** {entities['duration']}")
    
    if entities.get('deadline'):
        parts.append(f"📅 **Deadline:** {entities['deadline']}")
    
    if entities.get('requirements'):
        parts.append(f"📋 **Key Requirements:**")
        for req in entities['requirements'][:3]:
            parts.append(f"  • {req}")
    
    return "\n".join(parts) if parts else "No entities extracted"
