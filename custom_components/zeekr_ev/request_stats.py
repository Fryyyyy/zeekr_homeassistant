# Add API request/invoke counting and reset logic for ZeekrCoordinator
# This will be imported and used in the main coordinator and entity files

from datetime import datetime
from homeassistant.helpers.storage import Store
from homeassistant.core import HomeAssistant

STORAGE_KEY = "zeekr_ev_stats"
STORAGE_VERSION = 1


class ZeekrRequestStats:
    def __init__(self, hass: HomeAssistant):
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.api_requests_today = 0
        self.api_invokes_today = 0
        self.api_requests_total = 0
        self.api_invokes_total = 0
        self._last_reset = datetime.now().date()
        self._loaded = False

    async def async_load(self):
        """Load stats from storage."""
        if self._loaded:
            return

        data = await self._store.async_load()
        if data:
            self.api_requests_today = data.get('api_requests_today', 0)
            self.api_invokes_today = data.get('api_invokes_today', 0)
            self.api_requests_total = data.get('api_requests_total', 0)
            self.api_invokes_total = data.get('api_invokes_total', 0)
            try:
                self._last_reset = datetime.strptime(
                    data.get('last_reset', str(datetime.now().date())), '%Y-%m-%d'
                ).date()
            except (ValueError, TypeError):
                self._last_reset = datetime.now().date()

        self._loaded = True
        # Check reset after loading in case we loaded stale data from yesterday
        await self._async_check_reset()

    async def async_reset_today(self):
        self.api_requests_today = 0
        self.api_invokes_today = 0
        self._last_reset = datetime.now().date()
        await self.async_save()

    async def async_inc_request(self):
        await self._async_check_reset()
        self.api_requests_today += 1
        self.api_requests_total += 1
        await self.async_save()

    async def async_inc_invoke(self):
        await self._async_check_reset()
        self.api_invokes_today += 1
        self.api_invokes_total += 1
        await self.async_save()

    async def _async_check_reset(self):
        today = datetime.now().date()
        if today != self._last_reset:
            await self.async_reset_today()

    def as_dict(self):
        return {
            'api_requests_today': self.api_requests_today,
            'api_invokes_today': self.api_invokes_today,
            'api_requests_total': self.api_requests_total,
            'api_invokes_total': self.api_invokes_total,
            'last_reset': str(self._last_reset),
        }

    async def async_save(self):
        data = self.as_dict()
        await self._store.async_save(data)
