import pathlib
import threading
import urllib.error
import urllib.request
from typing import Generic, Optional, TypeVar

import obspython as obs

import stream_utils

T = TypeVar('T')

MY_DIR = pathlib.Path(__file__).parent.resolve()

VIDEOS = [
    str(MY_DIR / 'giphy480p.mp4'),
    str(MY_DIR / 'match-0.mp4'),
]

class Guarded(Generic[T]):
    def __init__(self, initial: T) -> None:
        self._value = initial
        self._lock = threading.Lock()

    def get(self) -> T:
        with self._lock:
            return self._value

    def set(self, value: T):
        with self._lock:
            self._value = value


class Listener(threading.Thread):
    def __init__(self, stream_url: str, video_path: Guarded[str]) -> None:
        super().__init__(daemon=True)
        self.stream_url = stream_url
        self.video_path = video_path

        self._running = True
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def run(self) -> None:
        idx = 0

        with urllib.request.urlopen(self.stream_url) as response:
            print('connected')
            while self.running:
                name, data = stream_utils.consume_event(response)
                print(name)
                if name == 'match':
                    idx ^= 1
                    print(f"Match: {idx}")
                    self.video_path.set(VIDEOS[idx])


video_path = Guarded(VIDEOS[0])
last_video_path: Optional[str] = None
source_name = ""
thread: Optional[Listener] = None


def update_match_video():
    global last_video_path

    print('update_match_video')

    path = video_path.get()
    if last_video_path == path:
        print(f"{path!r} has already played")
        return

    last_video_path = path
    print(f"Updating to {path!r}")

    source = obs.obs_get_source_by_name(source_name)
    if source != None:
        print('got source')

        settings = obs.obs_data_create()
        source_id = obs.obs_source_get_id(source)
        if source_id == "ffmpeg_source":

            obs.obs_data_set_string(settings, "local_file", path)
            obs.obs_data_set_bool(settings, "is_local_file", True)

            # updating will automatically cause the source to
            # refresh if the source is currently active
            obs.obs_source_update(source, settings)

        elif source_id == "vlc_source":
            # "playlist"
            array = obs.obs_data_array_create()
            item = obs.obs_data_create()
            obs.obs_data_set_string(item, "value", path)
            obs.obs_data_array_push_back(array, item)
            obs.obs_data_set_array(settings, "playlist", array)

            # updating will automatically cause the source to
            # refresh if the source is currently active
            obs.obs_source_update(source, settings)
            obs.obs_data_release(item)
            obs.obs_data_array_release(array)

        obs.obs_data_release(settings)
        obs.obs_source_release(source)

    print('update_match_video done')


def refresh_pressed(props, prop):
    print(f'refresh_pressed({props!r}, {prop!r}')
    update_match_video()


# ------------------------------------------------------------

def script_unload():
    global thread
    if thread != None:
        thread.stop()


def script_description():
    return "Configures a video to play in response to SRComp events"

def script_update(settings):
    print('script_update')
    global url
    global source_name
    global thread

    if thread is not None:
        thread.stop()

    stream_url  = obs.obs_data_get_string(settings, "stream_url")
    interval    = obs.obs_data_get_int(settings, "interval")
    source_name = obs.obs_data_get_string(settings, "source")

    obs.timer_remove(update_match_video)

    if stream_url != "" and source_name != "":
        thread = Listener(stream_url, video_path)
        thread.start()

        obs.timer_add(update_match_video, interval * 100)

def script_defaults(settings):
    print('script_defaults')
    obs.obs_data_set_default_int(settings, "interval", 30)

def script_properties():
    print('script_properties')
    props = obs.obs_properties_create()

    obs.obs_properties_add_text(props, "stream_url", "Stream URL", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_int(props, "interval", "Update Interval (milliseconds)", 1, 500, 1)

    p = obs.obs_properties_add_list(props, "source", "Media Source", obs.OBS_COMBO_TYPE_EDITABLE, obs.OBS_COMBO_FORMAT_STRING)
    sources = obs.obs_enum_sources()
    if sources is not None:
        for source in sources:
            source_id = obs.obs_source_get_id(source)
            if source_id == "ffmpeg_source":
                name = obs.obs_source_get_name(source)
                obs.obs_property_list_add_string(p, name, name)
            elif source_id == "vlc_source":
                name = obs.obs_source_get_name(source)
                obs.obs_property_list_add_string(p, name, name)

        obs.source_list_release(sources)

    obs.obs_properties_add_button(props, "button", "Refresh", refresh_pressed)
    return props
