"""ElevenLabs: voiceover with word timings, sound effects, music. Needs ELEVENLABS_API_KEY."""
import base64, time
from .common import http, mean_db

API = "https://api.elevenlabs.io"


class ElevenLabs:
    def __init__(self, key):
        self.h = {"xi-api-key": key}

    def check(self):
        d = http("GET", API + "/v1/user/subscription", self.h)
        return f"ElevenLabs OK: {d.get('tier')} plan, {d.get('character_count')}/{d.get('character_limit')} characters used"

    def voices(self):
        d = http("GET", API + "/v2/voices?page_size=100", self.h)
        return [(v["voice_id"], v["name"], v.get("category")) for v in d.get("voices", [])]

    def tts(self, voice_id, model, text, settings, previous_text="", next_text=""):
        """Returns (mp3 bytes, [{"w","s","e"}]) with word timings from the character alignment."""
        d = http("POST", f"{API}/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_192", self.h,
                 {"text": text, "model_id": model, "previous_text": previous_text, "next_text": next_text, "voice_settings": settings})
        al = d["alignment"]; words, cur = [], None
        for ch, s, e in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
            if ch.isspace():
                cur = None; continue
            if cur is None:
                cur = {"w": "", "s": s, "e": e}; words.append(cur)
            cur["w"] += ch; cur["e"] = e
        return base64.b64decode(d["audio_base64"]), words

    def sfx(self, prompt, seconds, dst, tries=3):
        """Sound generation; silent results (mean < -45 dB) are retried."""
        for attempt in range(1, tries + 1):
            dst.write_bytes(http("POST", API + "/v1/sound-generation?output_format=mp3_44100_128", self.h,
                                 {"text": prompt, "duration_seconds": max(float(seconds), 0.5), "prompt_influence": 0.55}, raw=True))
            db = mean_db(dst)
            if db > -45:
                return db, attempt
            time.sleep(1)
        return db, tries

    def music(self, prompt, ms, dst):
        dst.write_bytes(http("POST", API + "/v1/music?output_format=mp3_44100_128", self.h,
                             {"prompt": prompt, "music_length_ms": int(ms), "model_id": "music_v1"}, timeout=900, raw=True))
        return mean_db(dst)
