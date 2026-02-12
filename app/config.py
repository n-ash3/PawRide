from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "PawRide API"
    environment: str = "development"
    database_url: str = "sqlite:///./pawride.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_exp_minutes: int = 30
    refresh_token_exp_days: int = 30
    otp_exp_minutes: int = 10
    default_currency: str = "usd"
    base_fare: float = 8.0
    per_km_fare: float = 2.5
    per_minute_fare: float = 0.4
    size_surcharge_medium: float = 2.0
    size_surcharge_large: float = 4.0
    size_surcharge_xlarge: float = 6.0
    additional_dog_fee: float = 5.0
    default_driver_commission_rate: float = 0.75
    free_cancel_window_minutes: int = 2
    cancel_fee_en_route: float = 5.0
    cancel_fee_with_dog: float = 15.0
    dispatch_offer_timeout_seconds: int = 15
    dispatch_initial_radius_km: float = 3.0
    dispatch_radius_step_km: float = 2.0
    dispatch_max_radius_km: float = 20.0
    driver_minimum_rating: float = 4.0
    scheduled_match_lead_minutes: int = 30
    camera_auto_snapshot_interval_minutes: int = 5
    instant_payout_fee_percent: float = 1.5
    weekly_payout_weekday: int = 0
    default_pass_price_monthly: float = 29.99
    default_pass_discount_percent: float = 10.0
    enable_background_jobs: bool = True


settings = Settings()
