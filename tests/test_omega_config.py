import omega_config


def test_google_api_key_accepts_gemini_alias(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", " gemini-key ")

    assert omega_config.google_api_key() == "gemini-key"


def test_google_api_key_prefers_google_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", " google-key ")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")

    assert omega_config.google_api_key() == "google-key"


def test_supabase_public_config_uses_next_public_anon_fallback(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", " https://example.supabase.co ")
    monkeypatch.setenv("SUPABASE_KEY", " service-key ")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", " anon-key ")

    cfg = omega_config.supabase_config()

    assert cfg.configured is True
    assert cfg.url == "https://example.supabase.co"
    assert cfg.service_key == "service-key"
    assert cfg.public == {
        "url": "https://example.supabase.co",
        "anonKey": "anon-key",
    }


def test_developer_api_keys_supports_plural_and_legacy(monkeypatch):
    monkeypatch.setenv("ATLAS_DEV_API_KEYS", " k1, k2 ,, ")
    monkeypatch.setenv("ATLAS_DEV_API_KEY", "legacy")

    assert omega_config.developer_api_keys() == ["k1", "k2"]

    monkeypatch.delenv("ATLAS_DEV_API_KEYS", raising=False)
    assert omega_config.developer_api_keys() == ["legacy"]


def test_tier_daily_limit_uses_override_and_ignores_invalid(monkeypatch):
    monkeypatch.setenv("ATLAS_TIER_PRO_DAILY_QUERIES", "42")
    assert omega_config.tier_daily_limit("pro", 10) == 42

    monkeypatch.setenv("ATLAS_TIER_PRO_DAILY_QUERIES", "bad")
    assert omega_config.tier_daily_limit("pro", 10) == 10


def test_stripe_price_for_plan_supports_current_and_legacy_names(monkeypatch):
    monkeypatch.delenv("STRIPE_PRICE_PRO", raising=False)
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", "price_legacy_pro")

    assert omega_config.stripe_price_for_plan("pro") == "price_legacy_pro"

    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_current_pro")
    assert omega_config.stripe_price_for_plan("pro") == "price_current_pro"


def test_boolean_helpers(monkeypatch):
    monkeypatch.setenv("ATLAS_DISABLE_AUTH", "true")
    monkeypatch.setenv("ATLAS_ALLOW_UNSIGNED_STRIPE_WEBHOOK", "0")

    assert omega_config.auth_disabled() is True
    assert omega_config.allow_unsigned_stripe_webhook() is False
