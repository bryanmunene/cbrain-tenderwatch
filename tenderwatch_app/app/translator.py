"""
Translation module for TenderWatch
Translates tender titles and descriptions from any language to English
"""

import logging
import json
import requests
from typing import Tuple

logger = logging.getLogger(__name__)

# Common non-English words that indicate foreign language
FRENCH_INDICATORS = ['pour', 'les', 'des', 'une', 'aux', 'sur', 'dans', 'avec', 'par', 'mise', 'place', 'terme', 'long', 'accord', 'etablissement', 'hebergement', 'plateforme', 'classement', 'services', 'production', 'audiovisuelles', 'digitale']
SPANISH_INDICATORS = ['para', 'los', 'las', 'una', 'del', 'con', 'por', 'servicios', 'construccion', 'contratacion', 'adquisicion', 'suministro']
PORTUGUESE_INDICATORS = ['para', 'dos', 'das', 'uma', 'com', 'por', 'servicos', 'aquisicao', 'fornecimento', 'contratacao']
GERMAN_INDICATORS = ['für', 'die', 'der', 'das', 'und', 'mit', 'bei', 'zur', 'ausschreibung', 'vergabe', 'dienstleistungen']

def detect_language(text: str) -> str:
    """Detect the language of the given text with improved accuracy"""
    if not text:
        return "en"
    
    text_lower = text.lower()
    words = text_lower.split()
    
    # Check for common non-English word patterns first (more reliable for short texts)
    french_count = sum(1 for word in words if word in FRENCH_INDICATORS)
    spanish_count = sum(1 for word in words if word in SPANISH_INDICATORS)
    portuguese_count = sum(1 for word in words if word in PORTUGUESE_INDICATORS)
    german_count = sum(1 for word in words if word in GERMAN_INDICATORS)
    
    # If we find multiple indicator words, trust that over langdetect
    if french_count >= 2:
        return "fr"
    if spanish_count >= 2:
        return "es"
    if portuguese_count >= 2:
        return "pt"
    if german_count >= 2:
        return "de"
    
    # Fall back to langdetect
    try:
        from langdetect import detect
        lang = detect(text)
        return lang
    except Exception as e:
        logger.debug(f"Language detection failed: {e}")
        return "en"

def translate_to_english(text: str, source_lang: str = "auto") -> str:
    """
    Translate text to English using multiple fallback strategies
    
    Args:
        text: Text to translate
        source_lang: Source language code (default: auto-detect)
    
    Returns:
        Translated text in English, or original text if translation fails
    """
    import time
    
    if not text or len(text.strip()) == 0:
        return ""
    
    # Detect language
    detected_lang = detect_language(text) if source_lang == "auto" else source_lang
    
    # If English, return as is
    if detected_lang == "en":
        return text
    
    print(f"🌐 Translating from {detected_lang}: {text[:50]}...")
    
    # Try GoogleTranslator with retries
    for attempt in range(3):
        try:
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source='auto', target='en')
            translated = translator.translate(text[:5000])
            
            if translated and translated.lower() != text.lower():
                print(f"✅ Translated via Google: {translated[:50]}...")
                return translated
            break  # No error but same text, don't retry
        except Exception as e:
            print(f"⚠️ GoogleTranslator attempt {attempt+1} failed: {str(e)[:50]}")
            if attempt < 2:
                time.sleep(1)  # Wait before retry
    
    # Fallback: Try googletrans library (different Google endpoint)
    try:
        from googletrans import Translator
        translator = Translator()
        result = translator.translate(text[:5000], dest='en')
        if result and result.text and result.text.lower() != text.lower():
            print(f"✅ Translated via googletrans: {result.text[:50]}...")
            return result.text
    except Exception as e:
        print(f"⚠️ googletrans failed: {str(e)[:50]}")
    
    # Fallback: Try MyMemory with proper language code mapping
    try:
        from deep_translator import MyMemoryTranslator
        # Map 2-letter codes to MyMemory format
        lang_map = {'fr': 'french', 'de': 'german', 'es': 'spanish', 'pt': 'portuguese', 
                    'it': 'italian', 'nl': 'dutch', 'ru': 'russian', 'zh': 'chinese simplified',
                    'ar': 'arabic', 'ja': 'japanese', 'ko': 'korean'}
        source = lang_map.get(detected_lang, detected_lang)
        translator = MyMemoryTranslator(source=source, target='english')
        translated = translator.translate(text[:500])
        
        if translated and translated.lower() != text.lower():
            print(f"✅ Translated via MyMemory: {translated[:50]}...")
            return translated
    except Exception as e:
        print(f"⚠️ MyMemoryTranslator failed: {str(e)[:50]}")
    
    # Fallback: Try LibreTranslate API
    try:
        url = "https://libretranslate.de/translate"
        payload = {
            "q": text[:500],
            "source": detected_lang,
            "target": "en"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if "translatedText" in result:
                translated = result["translatedText"]
                if translated and translated.lower() != text.lower():
                    print(f"✅ Translated via LibreTranslate: {translated[:50]}...")
                    return translated
    except Exception as e:
        print(f"⚠️ LibreTranslate failed: {str(e)[:50]}")
    
    # Return original text if all methods fail
    print(f"❌ Translation failed, returning original text")
    return text

def translate_tender(title: str, description: str = "") -> Tuple[str, str]:
    """
    Translate tender title and description to English
    
    Returns:
        Tuple of (translated_title, translated_description)
    """
    translated_title = translate_to_english(title) if title else ""
    translated_description = translate_to_english(description) if description else ""
    
    return translated_title, translated_description