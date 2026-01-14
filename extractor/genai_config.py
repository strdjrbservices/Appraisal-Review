import google as genai
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def configure_genai():
    """
    Configures the Google Generative AI client with the API key from Django settings.
    """
    api_key = settings.GOOGLE_API_KEY
    if api_key:
        genai.configure(api_key=api_key)
        logger.info("Google Generative AI client configured successfully.")
    else:
        logger.warning("GOOGLE_API_KEY is not set in Django settings. Generative AI features will be disabled.")
