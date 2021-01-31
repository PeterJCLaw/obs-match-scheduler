import datetime
import http
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple, Union

STREAM_URL = 'http://localhost:5001'

_current_match_lock = threading.Lock()
_current_match: Tuple[Optional[str], Optional[str]] = None, None


def get_playing_match() -> Optional[str]:
    with _current_match_lock:
        staging, playing = _current_match
        return playing


def set_playing_match(match: Optional[str]) -> None:
    with _current_match_lock:
        global _current_match
        staging, playing = _current_match
        _current_match = staging, match


def get_staging_match() -> Optional[str]:
    with _current_match_lock:
        staging, playing = _current_match
        return staging


def set_staging_match(match: Optional[str]) -> None:
    with _current_match_lock:
        global _current_match
        staging, playing = _current_match
        _current_match = match, playing


def consume_line(response: http.client.HTTPResponse) -> Tuple[str, str]:
    name, _, data = response.readline().decode('utf-8').rstrip('\n').partition(':')
    return name.strip(), data.strip()


def consume_event(response: http.client.HTTPResponse) -> Tuple[str, Any]:
    _, event = consume_line(response)
    _, raw_data = consume_line(response)

    # Swallow the intermediate line
    response.readline()

    return event, json.loads(raw_data)


def listener():
    try:
        with urllib.request.urlopen(STREAM_URL) as response:
            print('connected')
            while True:
                name, data = consume_event(response)
                # print(name, data)
                print(name)
                if name == 'match':
                    print(data)
                    if data:
                        print(data[0])
                        print('now: ', datetime.datetime.now())
                        print('slot:', data[0]['times']['slot']['start'])
                        print('game:', data[0]['times']['game']['start'])

    except urllib.error.URLError as err:
        print(err)


if __name__ == '__main__':
    threading.Thread(target=listener, daemon=True).start()

    try:
        import obspython as obs

    except:
        while True:
            time.sleep(5)
            print('<main>')
