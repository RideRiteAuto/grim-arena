#!/usr/bin/env python3
"""Generate game sound effects with the ElevenLabs text-to-sound-effects API.

    export ELEVENLABS_API_KEY=sk_...
    python3 harness/sfx.py            # every effect in MANIFEST
    python3 harness/sfx.py anvil      # only ids starting "anvil"

Why this exists rather than an MCP connector: the hosted "ElevenLabs" connector
in Claude's directory is the Agents Platform product and has no sound-effects
tool at all, only text_to_speech. The official open-source MCP server does have
text_to_sound_effects but hardcodes a 0.5-5 second cap and does not expose
prompt_influence, and it is stdio-only so it cannot be added as a connector.
Calling the REST endpoint directly gets the full 30 second range, prompt
influence, and loop:true, which is what a campfire bed needs.

Every effect is generated SEVERAL TIMES with different prompt_influence. The
model is stochastic and the spread between takes is much larger than the spread
between two carefully worded prompts, so the way to get a good one is to ask
for five and throw four away. At 11 credits per second a 3 second effect is 33
credits, so five takes of it costs 165 of a 30,000 credit monthly allowance.

Everything is written to /tmp/sfx as both mp3 (what the API returns) and wav
(what the measuring code and the ear want), plus a report.json with peak, RMS,
crest factor and true duration so takes can be compared on numbers as well as
by listening.
"""
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API = 'https://api.elevenlabs.io/v1/sound-generation'
OUT = os.environ.get('SFX_OUT', '/tmp/sfx')

# Prompt notes, because the wording is the whole job and it is worth recording
# why each one reads the way it does.
#
# ANVIL. A real strike is two sounds, not one: a broadband impact lasting a few
# milliseconds, then inharmonic modes that ring for over a second. A blow
# landing on hot iron is DULLER than a tap on the bare face, because the hot
# billet absorbs the energy, so the forge sequence wants both. Naming the
# material twice ("steel hammer", "steel anvil") reliably gets metal rather
# than the generic thud the model reaches for when only "hammer" is present.
#
# CAMPFIRE. Asking for "crackling" alone gets a loop of pops with no bed under
# it. The flame roar has to be asked for explicitly. loop=True is only
# supported on the v2 model and is the reason this is worth doing at all: a
# looping bed can be a sample without the seam being audible.
MANIFEST = [
    {
        'id': 'anvil-heavy',
        'text': 'A single heavy blacksmith hammer blow striking hot iron on a '
                'steel anvil. A dull forceful impact, then a bright metallic '
                'ring that sustains and slowly decays. Close microphone in a '
                'stone forge.',
        'seconds': 3.0,
        'takes': [0.3, 0.5, 0.7],
    },
    {
        'id': 'anvil-tap',
        'text': 'A steel hammer tapping the bare face of a large steel anvil. '
                'One sharp bright metallic ping with a long shimmering '
                'sustain. Close microphone, quiet workshop.',
        'seconds': 3.0,
        'takes': [0.3, 0.5, 0.7],
    },
    {
        'id': 'anvil-sledge',
        'text': 'A heavy sledgehammer striking a large steel anvil. A deep '
                'resonant clang, powerful low thud under bright metallic '
                'overtones ringing out for several seconds.',
        'seconds': 4.0,
        'takes': [0.4, 0.6],
    },
    {
        'id': 'fire-bed',
        'text': 'A steady wood campfire burning close by. Dry wood popping and '
                'snapping, the soft low roar of flame underneath, occasional '
                'ember hiss. Quiet outdoors at night, continuous.',
        'seconds': 11.0,
        'loop': True,
        'takes': [0.3, 0.5],
    },
    {
        'id': 'fire-crackle',
        'text': 'Dry firewood crackling and popping in a small campfire, '
                'sharp snaps and embers hissing, intimate close perspective, '
                'very little flame roar.',
        'seconds': 8.0,
        'loop': True,
        'takes': [0.4, 0.6],
    },
]


def generate(key, text, seconds, influence, loop):
    body = json.dumps({
        'text': text,
        'model_id': 'eleven_text_to_sound_v2',
        'duration_seconds': seconds,
        'prompt_influence': influence,
        'loop': bool(loop),
    }).encode()
    # 128 kbps is the right ceiling here: 192 needs Creator and up, and this
    # audio is going into a game bundle as base64 where every byte is paid for
    # twice over.
    req = urllib.request.Request(
        API + '?output_format=mp3_44100_128', data=body, method='POST',
        headers={'xi-api-key': key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        # Never echo the key, only what the server said about it.
        raise SystemExit('HTTP %d from ElevenLabs: %s'
                         % (e.code, e.read().decode('utf-8', 'replace')[:400]))


def measure(wav):
    """Peak, RMS and true duration, straight out of ffmpeg."""
    p = subprocess.run(
        ['ffmpeg', '-hide_banner', '-i', wav, '-af', 'volumedetect',
         '-f', 'null', '-'],
        capture_output=True, text=True)
    out = p.stderr
    def grab(tag):
        for ln in out.splitlines():
            if tag in ln:
                try:
                    return float(ln.split(tag)[1].split('dB')[0].strip(': '))
                except ValueError:
                    return None
        return None
    dur = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', wav], capture_output=True, text=True).stdout.strip()
    peak, rms = grab('max_volume:'), grab('mean_volume:')
    return {
        'seconds': round(float(dur), 2) if dur else None,
        'peak_db': peak,
        'rms_db': rms,
        # Crest factor is what separates a real impact from a hairdryer. The
        # procedural campfire failed on exactly this number once already: a
        # peak only 5x above the RMS meant the crackles had been flattened
        # into the noise bed and it read as a fault, not a fire.
        'crest_db': round(peak - rms, 1) if (peak is not None and rms is not None) else None,
    }


def main():
    key = os.environ.get('ELEVENLABS_API_KEY', '')
    if not key.startswith('sk_'):
        raise SystemExit(
            'Set ELEVENLABS_API_KEY to a real key. ElevenLabs validates the '
            'shape server side: it must start with "sk_" and be exactly 51 '
            'characters. A bare hex string is some other secret, not the API '
            'key, and every endpoint rejects it on format before it is even '
            'looked up.')

    only = sys.argv[1] if len(sys.argv) > 1 else ''
    os.makedirs(OUT, exist_ok=True)
    report, credits = [], 0

    for spec in MANIFEST:
        if only and not spec['id'].startswith(only):
            continue
        for influence in spec['takes']:
            tag = '%s-p%02d' % (spec['id'], round(influence * 10))
            mp3, hdr = generate(key, spec['text'], spec['seconds'],
                                influence, spec.get('loop', False))
            cost = int(hdr.get('character-cost', 0) or 0)
            credits += cost
            mp3_path = os.path.join(OUT, tag + '.mp3')
            wav_path = os.path.join(OUT, tag + '.wav')
            with open(mp3_path, 'wb') as f:
                f.write(mp3)
            subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                            '-i', mp3_path, '-ar', '44100', '-ac', '1', wav_path],
                           check=True)
            row = {'id': spec['id'], 'take': tag, 'influence': influence,
                   'loop': spec.get('loop', False), 'credits': cost,
                   'mp3_bytes': len(mp3),
                   # what it would cost the bundle if we inlined it
                   'b64_kb': round(len(base64.b64encode(mp3)) / 1024, 1)}
            row.update(measure(wav_path))
            report.append(row)
            print(json.dumps(row))

    with open(os.path.join(OUT, 'report.json'), 'w') as f:
        json.dump({'takes': report, 'credits_spent': credits}, f, indent=2)
    print('\n%d take(s), %d credits, written to %s' % (len(report), credits, OUT))


if __name__ == '__main__':
    main()
