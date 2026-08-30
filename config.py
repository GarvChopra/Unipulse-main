"""Environment configuration. One object, read once at startup."""
import os


class Config:
    DATABASE_URL         = os.environ.get("DATABASE_URL", "").strip()
    SECRET_KEY           = os.environ.get("SECRET_KEY", "").strip() or "unipulse-dev-secret"
    JWT_SECRET           = os.environ.get("JWT_SECRET", "").strip() or "unipulse-jwt-dev-secret-not-for-production-use-0000"
    APP_ENV              = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development")).lower()
    GROQ_API_KEY         = os.environ.get("GROQ_API_KEY", "").strip()
    RESEND_API_KEY       = os.environ.get("RESEND_API_KEY", "").strip()
    IMAGEKIT_PRIVATE_KEY = os.environ.get("IMAGEKIT_PRIVATE_KEY", "").strip()
    # Groq: qwen3.6-27b is multimodal (text + image), so one model covers both paths.
    GROQ_MODEL_TEXT   = os.environ.get("GROQ_MODEL_TEXT", "qwen/qwen3.6-27b").strip()
    GROQ_MODEL_VISION = os.environ.get("GROQ_MODEL_VISION", "qwen/qwen3.6-27b").strip()
    RESEND_FROM       = os.environ.get("RESEND_FROM", "UniPulse <onboarding@resend.dev>").strip()
    ADMIN_ALERT_EMAIL = (os.environ.get("ADMIN_ALERT_EMAIL")
                         or os.environ.get("DEMO_RECIPIENT_EMAIL") or "").strip()

    @classmethod
    def is_production(cls) -> bool:
        return cls.APP_ENV == "production"
