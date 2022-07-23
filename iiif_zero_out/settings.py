from pydantic import BaseSettings


class Settings(BaseSettings):
    BASE_SCALING_FACTORS: list[int] = [1, 2, 4, 8, 16, 32, 64, 128, 256]
    BASE_SMALLER_SIZES: list[int] = [16, 32, 64, 128, 256, 512]


settings = Settings()
