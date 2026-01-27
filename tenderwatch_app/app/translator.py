"""
Translation module for TenderWatch
Translates tender titles and descriptions from any language to English
"""

import logging
import json
import requests
from typing import Tuple

logger = logging.getLogger(__name__)

def detect_language(text: str) -> str:
    """Detect the language of the given text"""
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
    if not text or len(text.strip()) == 0:
        return ""
    
    # First check: if already English, return as is
    try:
        detected_lang = detect_language(text)
        if detected_lang == "en":
            return text
    except Exception as e:
        logger.debug(f"Language detection failed: {e}")
    
    # Try: Free translation service (LibreTranslate API)
    try:
        detected_lang = detect_language(text) if source_lang == "auto" else source_lang
        
        if detected_lang == "en":
            return text
        
        # Using LibreTranslate free API (no API key needed)
        url = "https://libretranslate.de/translate"
        payload = {
            "q": text[:500],  # Limit to 500 chars
            "source": detected_lang,
            "target": "en"
        }
        
        response = requests.post(url, json=payload, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            if "translatedText" in result:
                translated = result["translatedText"]
                if translated and translated != text:
                    logger.info(f"✅ Translated {detected_lang} -> en (LibreTranslate)")
                    return translated
    except Exception as e:
        logger.debug(f"LibreTranslate API failed: {str(e)}")
    
    # Fallback: Try deep_translator MyMemory (no API key, local service)
    try:
        from deep_translator import MyMemoryTranslator
        detected_lang = detect_language(text) if source_lang == "auto" else source_lang
        
        if detected_lang == "en":
            return text
        
        translator = MyMemoryTranslator(source_language=detected_lang, target_language='en')
        translated = translator.translate(text[:500])
        
        if translated and translated != text:
            logger.info(f"✅ Translated {detected_lang} -> en (MyMemory)")
            return translated
    except Exception as e:
        logger.debug(f"MyMemoryTranslator failed: {str(e)}")
    
    # Final fallback: Try GoogleTranslator one more time
    try:
        from deep_translator import GoogleTranslator
        detected_lang = detect_language(text) if source_lang == "auto" else source_lang
        
        if detected_lang == "en":
            return text
        
        translator = GoogleTranslator(source_language=detected_lang, target_language='en')
        translated = translator.translate(text[:500])
        
        if translated and translated != text:
            logger.info(f"✅ Translated {detected_lang} -> en (Google)")
            return translated
    except Exception as e:
        logger.debug(f"GoogleTranslator failed: {str(e)}")
    
    # Return original text if all methods fail
    logger.debug(f"Translation failed, returning original text")
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