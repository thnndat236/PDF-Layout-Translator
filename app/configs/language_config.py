# configs/language_config.py

CODE_TO_NAME = {
    "en": "English",       
    "vi": "Vietnamese",    
    "fr": "French",        
    "es": "Spanish",       
    "de": "German",        
    "pt": "Portuguese",    
    "it": "Italian",       
    "nl": "Dutch",         
    "pl": "Polish",        
    "tr": "Turkish",       
    "id": "Indonesian",    
    "sv": "Swedish",    
    "cs": "Czech",      
    "hu": "Hungarian",  
    "ro": "Romanian",   
    "ca": "Catalan",    
    "tl": "Tagalog",    
    "et": "Estonian"    
}

# Mapping full name to 2-letter code
NAME_TO_CODE = {v: k for k, v in CODE_TO_NAME.items()}

# List of languages
LANGUAGE_CHOICES = sorted(CODE_TO_NAME.values())