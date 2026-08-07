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

    # COMBAT ONE-SHOTS, August 6. The melee funnel in applyDamage plays
    # parry/block/crit/hit; windups play swing/heavy. These six are the most
    # heard sounds in the game.
    #
    # SWING. A real swing is 150-350 ms of broadband air displacement with no
    # tonal content and NO impact at the end -- the model loves to add one, so
    # the prompt forbids it twice. Light swing sits brighter; the heavy swing
    # wants audible low-end mass, which "thick blade" and "deep" buy.
    #
    # HIT. A game melee hit is a composite: a low thump around 80-120 Hz, a
    # mid crack, and a thin leather/cloth layer. "Blunt" and "padded" keep the
    # model away from gore squelch, which would be wrong for this game's tone.
    # CRIT is the same family, stated heavier, so the pair reads as one weapon
    # at two intensities rather than two different weapons.
    #
    # BLOCK. A wooden shield with a metal boss: dead wood thunk, boss ring
    # damped almost immediately. If the ring sustains it reads as a bell.
    #
    # PARRY. Steel on steel, bright, with a fast decay and a hint of scrape.
    # The synth version is currently two triangle waves, the single most
    # artificial sound in combat.
    # v3 (patch 44). SWING is a miss: every impact word was removed and the
    # take chosen on shape, since a whoosh peaks in the MIDDLE and an impact
    # peaks at sample zero. HITS split by target material, because one impact
    # cannot serve a rat and a suit of plate; naming the metal twice
    # ("steel sword blade", "steel plate armor") is the same trick that got
    # the anvil to sound like metal. CRIT is no longer a sound of its own: it
    # is the material impact plus crit-ring layered over it, so it stays
    # satisfying whatever it lands on and armoured enemies never need a crit
    # sample of their own. Six takes each.
    {
        'id': 'combat-swing',
        'text': 'A sword swinging through empty air and missing. One fast '
                'clean whoosh with a soft airy whistle as the blade passes '
                'by. The blade hits nothing at all: no impact, no contact, '
                'no clang. Dry close recording, brief. No voice, no music.',
        'seconds': 1.0,
        'takes': [0.25, 0.4, 0.5, 0.6, 0.7, 0.85],
    },
    {
        'id': 'combat-hit-flesh',
        'text': 'A sword blade striking an unarmored creature. One solid '
                'meaty impact, a dull muffled thud with a soft slicing edge '
                'to it. Close and dry. No metal, no clang, no voice, no '
                'music. Brief.',
        'seconds': 1.0,
        'takes': [0.25, 0.4, 0.5, 0.6, 0.7, 0.85],
    },
    {
        'id': 'combat-hit-leather',
        'text': 'A steel sword blade striking hardened leather armor. One '
                'firm impact: a thick leathery slap with a dull woody crack '
                'as the blade bites into the hide, slight creak of leather. '
                'Close and dry. No clang, no voice, no music. Brief.',
        'seconds': 1.0,
        'takes': [0.25, 0.4, 0.5, 0.6, 0.7, 0.85],
    },
    {
        'id': 'combat-hit-plate',
        'text': 'A steel sword blade striking steel plate armor. One hard '
                'metallic impact: a bright clang with a short scraping skid '
                'as the steel blade glances off the steel plate, quick '
                'metallic decay. Close and dry. No voice, no music. Brief.',
        'seconds': 1.2,
        'takes': [0.25, 0.4, 0.5, 0.6, 0.7, 0.85],
    },
    {
        'id': 'combat-crit-ring',
        'text': 'A bright shimmering metallic ring of a fine steel blade '
                'singing after a perfect strike. Clean bell-like sustain '
                'with a sparkling shimmer, rising and satisfying, decaying '
                'smoothly. Only the ring: no impact, no thud, no clang at '
                'the start. No voice, no music.',
        'seconds': 1.8,
        'takes': [0.25, 0.4, 0.5, 0.6, 0.7, 0.85],
    },
    {
        'id': 'combat-heavy',
        'text': 'A single slow powerful weapon swing through air, a heavy '
                'thick blade or club moving fast. One deep forceful whoosh '
                'with low air pressure, no impact, no voice. Brief.',
        'seconds': 1.2,
        'takes': [0.3, 0.5, 0.7],
    },
    {
        'id': 'combat-block',
        'text': 'A heavy sword strike slamming into a sturdy round wooden shield '
                'with a steel boss. One massive solid impact: deep wooden '
                'boom, sharp crack of wood, short damped metallic clank. '
                'Powerful, punchy, dry, no long ring, no voice.',
        'seconds': 1.0,
        'takes': [0.3, 0.5, 0.7],
    },
    {
        'id': 'combat-parry',
        'text': 'Two steel sword blades clashing once in a parry. One bright '
                'sharp metallic clang with a brief scrape, decaying quickly, '
                'no voice. Close, dry.',
        'seconds': 1.2,
        'takes': [0.3, 0.5, 0.7],
    },

    # TREES AND MINING, August 7. One set of sounds shared by every tree and
    # every ore node in the game, so they get tuned once and reused forever.
    #
    # CHOP. A real axe blow into green wood is a THOCK, not a click: a woody
    # impact with a splintering bite and the trunk resonating underneath.
    # Naming the resonance keeps the model from producing a kindling snap.
    #
    # FELL. Kevin wants the crack, the groan, the branch whoosh and the ground
    # hit as ONE cohesive event; the fall animation gets tuned to this take's
    # timing rather than the other way round. Describing the sequence in
    # strict order ("then... ending in...") is what keeps the phases distinct
    # instead of smeared together. Chosen take: crack at 0.05s, crash at 3.0s.
    #
    # MINING. Strike is steel point on stone: bright tink plus grit. Chip is
    # the reward moment, so it carries a faint mineral chime the strike does
    # not. Deplete is the same family but heavier, ending dry and flat.
    {
        'id': 'tree-chop',
        'text': 'A single sharp axe blow chopping into a living tree trunk. '
                'One clean powerful impact: a deep woody thock with a brief '
                'splintering bite as the blade sinks in, a low knock '
                'resonating through the trunk. Close microphone in a quiet '
                'forest. No voice, no birds, no wind. Brief.',
        'seconds': 1.2,
        'takes': [0.3, 0.5, 0.7],
    },
    {
        'id': 'tree-fell',
        'text': 'A large tree being felled in a quiet forest, one continuous '
                'sequence: a loud sharp crack of the trunk splitting with '
                'wood fibers tearing, then a slow groaning creak that '
                'accelerates, branches whooshing and snapping through the '
                'air, ending in one heavy ground impact, a deep thud with '
                'breaking branches and a leafy rustle settling. No voice, no '
                'birds, no chainsaw.',
        'seconds': 5.0,
        'takes': [0.35, 0.55, 0.75],
    },
    {
        'id': 'tree-impact',
        'text': 'A massive tree trunk slamming into forest ground. One '
                'single enormous heavy thud, deep and dull, with branches '
                'cracking under the weight and a shower of leaves and small '
                'debris settling afterwards. No voice, no crack of '
                'splitting, just the landing.',
        'seconds': 2.0,
        'takes': [0.4, 0.6],
    },
    {
        'id': 'mine-strike',
        'text': 'A single pickaxe blow striking hard rock. One sharp stony '
                'impact: a bright metallic tink of the steel point, stone '
                'chips scattering, a short gritty debris rattle. Close '
                'microphone in the open air. No voice, no echo tail. Brief.',
        'seconds': 1.0,
        'takes': [0.3, 0.5, 0.7],
    },
    {
        'id': 'mine-chip',
        'text': 'A chunk of ore breaking loose from a rock face. A crunching '
                'stony crack as the piece gives way, small rocks and gravel '
                'tumbling and scattering on the ground, with a faint bright '
                'mineral chime as the ore chunk lands. No voice. Short.',
        'seconds': 1.5,
        'takes': [0.3, 0.5, 0.7],
    },
    {
        'id': 'mine-deplete',
        'text': 'The last ore breaking out of an exhausted rock vein. A '
                'heavier crumbling collapse: rock fracturing, a small '
                'cascade of rubble and gravel pouring down, dust settling, '
                'ending flat and dry. No voice, no explosion.',
        'seconds': 2.5,
        'takes': [0.4, 0.6],
    },
    # FOOTSTEPS (patch 68.x). Kevin's brief named WoW as the reference, and
    # WoW's own terrain footstep files (Wowhead's Footsteps category,
    # MON_Footstep_Bipedal_Foot_<size>_<material>) turned out to be a single
    # pool of one-shot variants PER MATERIAL with no separate walk/run
    # recordings at all - the game differentiates gait by animation cadence
    # and impact force, not by swapping samples. That finding reshaped this
    # manifest: one texture per material, shaped against the real reference
    # numbers below, with walk/run handled at PLAYBACK time (gain/pitch) in
    # the patch script rather than as separate generated takes. See
    # measure.py numbers pulled from the real WoW files in /tmp/footref.
    #
    # WOOD  target: dur .14-.21s  cent 1000-1500  <200Hz .48-.52 (high, a
    #   hollow plank resonance)  pkpos .06-.09  tail .13-.14s  some tonal
    #   ring (13-29%, the wood "knock"). Shortest, tightest, most resonant.
    {
        'id': 'foot-wood',
        'text': 'A single footstep, a boot sole striking a wooden plank '
                'floor. One short hollow wooden knock with a tight low '
                'thud, no scrape, no creak, no reverb tail, no music.',
        'seconds': 1.0,
        'takes': [0.25, 0.45, 0.65],
    },
    # DIRT  target: dur .27-.41s  cent 1900-2500  <200Hz .17-.30  pkpos
    #   .03-.41 (mostly instant)  tail .11-.24s  0% tonal. Dull, no ring.
    {
        'id': 'foot-dirt',
        'text': 'A single footstep on dry packed dirt ground. One dull '
                'crunching thud with a light gritty scuff, no bounce, no '
                'wood, no metal, no ring, no music.',
        'seconds': 1.0,
        'takes': [0.25, 0.45, 0.65],
    },
    # SAND  target: dur .33-.49s (longest)  cent 3970-4240 (brightest, by
    #   far)  <200Hz .03-.09 (almost none, loose fine grain has no body to
    #   resonate)  tail .24-.40s (longest, granular settling). 0% tonal.
    {
        'id': 'foot-sand',
        'text': 'A single footstep sinking into loose dry sand. A soft '
                'muffled press with a granular scattering hiss trailing '
                'off, no crunch, no thud, no impact click, no music.',
        'seconds': 1.2,
        'takes': [0.25, 0.45, 0.65],
    },
    # METAL  target: dur .19-.23s  cent 1240-1750 (a dull clank, NOT a
    #   bright ring - footfall force is far below a weapon strike)  <200Hz
    #   .26-.36 (a hollow plate boom)  tail .12-.16s (short, damped). This
    #   is a different target than combat-hit-plate (cent ~4947): a boot on
    #   a metal deck, not a blade on armour.
    {
        'id': 'foot-metal',
        'text': 'A single footstep, a boot striking a thin hollow metal '
                'floor plate. One short dull metallic clank with a brief '
                'low resonance, no long ring, no bell, no weapon clang, no '
                'music.',
        'seconds': 1.0,
        'takes': [0.25, 0.45, 0.65],
    },

    # LEGACY SOUND SWEEP, August 7 (patch 77.612). The remaining names still
    # falling through to sfxVoice_'s raw tone()/hiss() synth switch, found by
    # reading the live game source rather than trusting the docs (routing has
    # moved around enough times that a couple of these are only reachable via
    # a variable, e.g. the MSFX dispatch table, and don't show up in a plain
    # string search). Full audit and reuse map in
    # claude/LEGACY-SOUND-AUDIT.md. Explicitly OUT of this batch: the old
    # arena/duel round system (tick-as-countdown, horn-as-FIGHT-call,
    # win/lose-as-round-outcome) -- confirmed by reading stepRound() itself
    # ("the open world has no rounds") to be gated off entirely whenever
    # mode === 'ai', i.e. dead the moment the real MMO loads. Kevin's call,
    # confirmed in the code.

    # CREATURE-NOTICE-GENERIC. Every one of the 10 creatures currently shares
    # 'tick', the duel countdown blip, for its aggro cue. This is a stopgap
    # until the full per-creature roster (SFX-PROJECT-PLAN.md 3.3) lands --
    # a single generic "something just noticed you" cue, not a specific
    # animal, so it can't clash once real per-creature voices exist.
    {
        'id': 'creature-notice',
        'text': 'A wild creature suddenly noticing a threat nearby. A quick '
                'sharp alert grunt with a fast intake of breath, tense and '
                'immediate. No human voice, no words, no reverb, no music.',
        'seconds': 1.0,
        'takes': [0.3, 0.5, 0.7],
    },

    # GOBLIN SHRIEK. The rally-the-kin signature move currently plays 'bray',
    # a sawtooth honk with no creature character at all. HERO tier: this is
    # one of the most distinct, most repeated monster sounds in the game.
    {
        'id': 'goblin-shriek',
        'text': 'A small goblin creature shrieking a piercing rallying cry '
                'to summon its kin. A harsh ragged screeching call, high and '
                'carrying, monstrous and unpleasant. Not a human scream, no '
                'words, no reverb, no music.',
        'seconds': 2.0,
        'takes': [0.2, 0.3, 0.4, 0.55, 0.7, 0.85],
    },

    # NPC-TAUNT-WARCRY. Mr. Sailers' taunt special also plays 'bray' today.
    # A human NPC, not a monster, so this one gets a voice-adjacent but
    # wordless roar rather than the goblin's screech.
    {
        'id': 'npc-taunt-warcry',
        'text': 'A grizzled human warrior shouting a short defiant battle '
                'roar with no words, raw and gravelly, aggressive and '
                'forceful. No singing, no reverb, no music.',
        'seconds': 1.5,
        'takes': [0.3, 0.5, 0.7],
    },

    # BOW-DRAW / BOW-RELEASE. Every arrow fired, player or NPC, still plays
    # two raw synth tones ('draw' and 'arrow'). These are two of the most
    # frequently heard sounds left in the game. HERO tier both.
    {
        'id': 'bow-draw',
        'text': 'Drawing a heavy wooden longbow. Creaking wood under strain '
                'and the taut stretching of a bowstring, slow and increasing '
                'in tension. No release, no twang at the end, no reverb, no '
                'music.',
        'seconds': 1.8,
        'takes': [0.2, 0.3, 0.4, 0.55, 0.7, 0.85],
    },
    {
        'id': 'bow-release',
        'text': 'Loosing an arrow from a heavy wooden longbow. One sharp '
                'deep bowstring thwack with a woody snap and a fast '
                'departing whoosh. Powerful and immediate, no impact at the '
                'end, no reverb, no music.',
        'seconds': 1.2,
        'takes': [0.2, 0.3, 0.4, 0.55, 0.7, 0.85],
    },

    # CREATURE-WINDUP-CHARGE. Every boss/NPC special-move windup that isn't
    # the goblin shriek falls through to the bow-draw synth today (a boss
    # charging up currently creaks like a longbow). One generic "a big
    # creature is about to do something" cue.
    {
        'id': 'creature-windup-charge',
        'text': 'A large creature gathering itself before a powerful move. '
                'A deep straining grunt with tensing muscle and a scrape of '
                'claws or hooves digging in for traction. No human voice, no '
                'reverb, no music.',
        'seconds': 1.2,
        'takes': [0.3, 0.5, 0.7],
    },

    # PLAYER-DODGE / PLAYER-JUMP. Both currently play the identical 'dodge'
    # synth tone -- an evasive roll and a jump sound the same today.
    {
        'id': 'player-dodge',
        'text': 'A person doing a quick evasive roll on the ground. A fast '
                'fabric and leather rustle with a light scuff of boots '
                'pushing off. Athletic and brief. No voice, no reverb, no '
                'music.',
        'seconds': 0.6,
        'takes': [0.3, 0.5, 0.7],
    },
    {
        'id': 'player-jump',
        'text': 'A person pushing off the ground into a jump. A quick '
                'effortful push with a soft creak of leather gear and a '
                'brief whoosh of movement. No voice, no grunt, no reverb, no '
                'music.',
        'seconds': 0.5,
        'takes': [0.3, 0.5, 0.7],
    },

    # SPELL-FROST-FREEZE. Freezing a target solid is still a raw triangle-
    # wave sweep. HERO: it's the payoff moment of a full crowd-control spell.
    {
        'id': 'spell-frost-freeze',
        'text': 'A body freezing solid in an instant from magical cold. A '
                'deep groaning crystalline creak spreading outward, then a '
                'settling glassy shimmer as ice locks into place. Cold, '
                'thick, final. No voice, no reverb tail, no music.',
        'seconds': 2.5,
        'takes': [0.2, 0.3, 0.4, 0.55, 0.7, 0.85],
    },

    # CREATURE-CLAW-SWIPE. Claw and bite player weapon-type windups route to
    # 'slash' through the MSFX dispatch table -- easy to miss with a plain
    # string search since nothing calls sfx('slash') literally, but it is
    # live on every claw/bite swing.
    {
        'id': 'creature-claw-swipe',
        'text': 'A clawed hand swiping fast through open air, striking '
                'nothing. A quick sharp fleshy whoosh with a faint scrape of '
                'claws parting air. No impact, no metal, no voice, no '
                'reverb, no music.',
        'seconds': 0.5,
        'takes': [0.3, 0.5, 0.7],
    },

    # SPELL-SNARE-CAST. The snare spell windup routes to the generic 'cast'
    # synth through the same MSFX table, also invisible to a literal search.
    {
        'id': 'spell-snare-cast',
        'text': 'Casting a binding root spell. A low earthy rumble with '
                'creaking twisting wood and rustling growth rushing '
                'outward. Organic and grasping, no impact at the end, no '
                'reverb, no music.',
        'seconds': 1.4,
        'takes': [0.3, 0.5, 0.7],
    },

    # BOSS-LEAP-TELEGRAPH. A boss leap attack currently plays 'crit' -- the
    # player's own sword-critical-hit ring -- because of a state ternary that
    # was never given its own name. HERO: heard on every boss leap.
    {
        'id': 'boss-leap-telegraph',
        'text': 'A massive creature launching itself into a leap. A heavy '
                'grunt of exertion with a deep gust of displaced air and a '
                'brief rumble of coiling legs. Huge and weighty, no impact '
                'at the end, no human voice, no reverb, no music.',
        'seconds': 1.0,
        'takes': [0.2, 0.3, 0.4, 0.55, 0.7, 0.85],
    },

    # LEVEL-UP / QUEST-COMPLETE / SPELL-LEARNED / BOSS-PHASE-SHIFT. All four
    # of these currently fire the identical 'win' synth arpeggio: a skill
    # level-up, a duel win (left alone, see note above), a quest milestone
    # banner, the "TOME OF STORMS" spell-learned banner, and a boss crossing
    # into m.phase >= 1. LEVEL-UP and BOSS-PHASE-SHIFT are HERO tier --
    # they're the two most emotionally loaded of the four.
    {
        'id': 'level-up',
        'text': 'A triumphant magical level up flourish. A warm rising '
                'shimmer of bells and glowing tones resolving upward to a '
                'bright satisfying peak. Rewarding and uplifting. No '
                'voices, no choir, no orchestral fanfare, no reverb hall.',
        'seconds': 3.0,
        'takes': [0.2, 0.3, 0.4, 0.55, 0.7, 0.85],
    },
    {
        'id': 'quest-complete',
        'text': 'A quest objective completing. A warm confident two note '
                'chime with a soft magical shimmer settling after it. '
                'Satisfying and understated. No voices, no reverb hall, no '
                'music.',
        'seconds': 2.5,
        'takes': [0.3, 0.5, 0.7],
    },
    {
        'id': 'spell-learned',
        'text': 'Ancient magical knowledge being absorbed into a person\'s '
                'mind. A rising arcane shimmer of glassy tones with a soft '
                'magical whoosh, blooming outward and settling into a low '
                'resonant hum. Mystical and weighty. No voices, no reverb '
                'hall, no music.',
        'seconds': 2.5,
        'takes': [0.3, 0.5, 0.7],
    },
    {
        'id': 'boss-phase-shift',
        'text': 'A powerful creature surging with a fresh burst of dark '
                'elemental power mid-battle. A deep rising swell of '
                'gathering energy with a heavy percussive boom at the peak '
                'and a resonant trailing hum. Ominous and huge. No human '
                'voice, no reverb hall, no music.',
        'seconds': 3.0,
        'takes': [0.2, 0.3, 0.4, 0.55, 0.7, 0.85],
    },

    # HEAVY-IMPACT-CRASH. The 'slam' special move (Wild Boar charge, Argent
    # Warden slam) currently plays 'break', a sawtooth-and-hiss thud with no
    # weight to it at all despite being one of the harder-hitting moves in
    # the game.
    {
        'id': 'heavy-impact-crash',
        'text': 'A massive weapon or body slamming into stone ground. A '
                'deep bassy crash with cracking stone fragments and a heavy '
                'dust-settling tail. Huge and percussive, no metal ring, no '
                'voice, no reverb hall, no music.',
        'seconds': 1.5,
        'takes': [0.3, 0.5, 0.7],
    },

    # UI-SWITCH-CLICK. Loadout/paperdoll tab switching, four call sites,
    # cosmetic and cheap -- included since it costs almost nothing next to
    # everything above.
    {
        'id': 'ui-switch-click',
        'text': 'A short clean digital UI click, a single crisp neutral '
                'tone confirming a selection. Minimal and unobtrusive, no '
                'reverb, no music.',
        'seconds': 0.5,
        'takes': [0.3, 0.5, 0.7],
    },

    # UPDATE-READY-CHIME. The "a new build is ready" banner also plays 'horn'
    # today -- the same brassy synth triad as the (legacy, unused) duel
    # ready-up call. This one IS current: it fires whenever a live deploy is
    # detected while someone is playing. Deliberately calm and meta, not
    # diegetic, so it never reads as "a fight is starting."
    {
        'id': 'update-ready-chime',
        'text': 'A calm two tone UI notification chime, soft and '
                'unobtrusive, letting someone know something is ready. '
                'Clean digital tones, no shimmer, no reverb, no music.',
        'seconds': 0.8,
        'takes': [0.3, 0.5, 0.7],
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
