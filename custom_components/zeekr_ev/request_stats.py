# Add API request/invoke counting and reset logic for ZeekrCoordinator
# This will be imported and used in the main coordinator and entity files

import os
import json
from datetime import datetime

class ZeekrRequestStats:
    STATS_FILE = os.path.join(os.path.dirname(__file__), 'zeekr_stats.json')

    def __init__(self):
        self.api_requests_today = 0
        self.api_invokes_today = 0
        self.api_requests_total = 0
        self.api_invokes_total = 0
        self._last_reset = datetime.now().date()
        self._load()

    def reset_today(self):
        self.api_requests_today = 0
        self.api_invokes_today = 0
        self._last_reset = datetime.now().date()
        self._save()

    def inc_request(self):
        self._check_reset()
        self.api_requests_today += 1
        self.api_requests_total += 1
        self._save()

    def inc_invoke(self):
        self._check_reset()
        self.api_invokes_today += 1
        self.api_invokes_total += 1
        self._save()

    def _check_reset(self):
        today = datetime.now().date()
        if today != self._last_reset:
            self.reset_today()

    def as_dict(self):
        return {
            'api_requests_today': self.api_requests_today,
            'api_invokes_today': self.api_invokes_today,
            'api_requests_total': self.api_requests_total,
            'api_invokes_total': self.api_invokes_total,
            'last_reset': str(self._last_reset),
        }

    def _save(self):
        data = self.as_dict()
        data['last_reset'] = str(self._last_reset)
        try:
            with open(self.STATS_FILE, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    def _load(self):
        try:
            if os.path.exists(self.STATS_FILE):
                with open(self.STATS_FILE, 'r') as f:
                    data = json.load(f)
                self.api_requests_today = data.get('api_requests_today', 0)
                self.api_invokes_today = data.get('api_invokes_today', 0)
                self.api_requests_total = data.get('api_requests_total', 0)
                self.api_invokes_total = data.get('api_invokes_total', 0)
                self._last_reset = datetime.strptime(data.get('last_reset', str(datetime.now().date())), '%Y-%m-%d').date()
        except Exception:
            pass
