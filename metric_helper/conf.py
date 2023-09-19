


class Settings:

    def __init__(self):
        self.TIME_ZONE = 'UTC'
        self.TRIM_MS = False


    def set_tz(self, value=None):
        if not value:
            value = 'UTC'
        self.TIME_ZONE = value


settings = Settings()
