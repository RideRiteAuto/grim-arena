#!/usr/bin/env python3
"""Bring the nine hand-defined materials up to the same standard, and make the
dark ones readable.

Patch 21 gave the generated materials real art. That left an odd result in the
pack: PALM LOGS, WILLOW LOGS and ACACIA LOGS were drawn as cut logs with end
grain, while LOGS and OAK LOGS - the first wood a player ever gets - were still
plain brown CSS rectangles sitting right next to them. Same for IRON ORE beside
COPPER ORE and GOLD ORE. The oldest items in the game had become the worst ones.

These nine were still CSS `div` blobs and are now drawn:

  LOGS, OAK LOGS   cut logs with end grain, matching the generated wood family
  IRON ORE         rock with iron flecks, matching the generated ore family
  IRON BAR         a cast ingot with a bevel
  WOOL             a fleece
  RAT TAIL         a tapering tail with a kink
  DEER HIDE        a stretched hide
  WOLF PELT        a pelt with the head still on it
  VENISON          a cut of meat with the bone showing

Also: three materials are legitimately near-black - COAL, OBSIDIAN and BLACK
LOTUS - and the inventory background is #232323, so they were reading as holes
rather than items. Solid ore chunks now carry a rim highlight, and the lotus
bloom is lightened off its true tint with a dark centre kept for contrast. The
world models keep their real colours; this is the icon only, where the item has
to be legible against a dark panel at 46 pixels.

And the pick heads from patch 21 were too thin a crescent to read at icon size.
Thickened across all six tiers.

No stats, values or behaviour change.
"""
import io

SRC = '/tmp/game-src.html'
src = io.open(SRC, encoding='utf-8').read()
edits = []


def sub(old, new, label):
    n = src.count(old)
    assert n == 1, 'anchor %s matched %d times, expected 1' % (label, n)
    edits.append((old, new, label))


O = "' + O + '"

# ------------------------------------------------- 1. the nine CSS materials
sub("""    def('LOGS',          { value: 2,  icon: '<div style="width:26px;height:12px;background:#7a5a34;border:2px solid #0e0f0d;border-radius:6px;"></div>' });""",
    """    def('LOGS',          { value: 2,  icon: svg('<rect x="6" y="10.4" width="20" height="11" rx="3.2" fill="#b8a074" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M14 11 L14 20.8 M19.4 11 L19.4 20.8" stroke="#84734f" stroke-width="1.3" opacity="0.75"/>' +
      '<ellipse cx="8.6" cy="15.9" rx="3.4" ry="5.5" fill="#84734f" stroke="' + O + '" stroke-width="1.6"/>' +
      '<ellipse cx="8.6" cy="15.9" rx="1.5" ry="2.7" fill="none" stroke="' + O + '" stroke-width="1"/>') });""",
    'LOGS')

sub("""    def('OAK LOGS',      { value: 5,  icon: '<div style="width:24px;height:12px;background:#4a3a24;border-radius:5px;border:1px solid #2a2016;"></div>' });""",
    """    def('OAK LOGS',      { value: 5,  icon: svg('<rect x="6" y="10.4" width="20" height="11" rx="3.2" fill="#8a6a3e" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M14 11 L14 20.8 M19.4 11 L19.4 20.8" stroke="#634c2d" stroke-width="1.3" opacity="0.75"/>' +
      '<ellipse cx="8.6" cy="15.9" rx="3.4" ry="5.5" fill="#634c2d" stroke="' + O + '" stroke-width="1.6"/>' +
      '<ellipse cx="8.6" cy="15.9" rx="1.5" ry="2.7" fill="none" stroke="' + O + '" stroke-width="1"/>') });""",
    'OAK LOGS')

sub("""    def('IRON ORE',      { value: 6,  icon: '<div style="width:20px;height:18px;background:#8a8a82;border:2px solid #0e0f0d;clip-path:polygon(50% 0%,100% 30%,85% 100%,15% 100%,0% 30%);"></div>' });""",
    """    def('IRON ORE',      { value: 6,  icon: svg('<path d="M15 3.4 L25 9.6 L23 22 L11.4 24.4 L4.6 16 L7.8 6.6 Z" fill="#8b8b84" stroke="' + O + '" stroke-width="1.9"/>' +
      '<path d="M11.6 8.6 L16 7.6 L17 12 L12.6 13 Z M18 14 L22 12.8 L23 17 L19 18.4 Z M8.6 16 L12.8 17 L11.8 21 L7.8 19 Z" fill="#9a6a4a" stroke="' + O + '" stroke-width="1.1"/>') });""",
    'IRON ORE')

sub("""    def('IRON BAR',      { value: 14, icon: '<div style="width:24px;height:12px;background:linear-gradient(180deg,#c8ccd4,#8a8f9a);border:1px solid #3a3d44;"></div>' });""",
    """    def('IRON BAR',      { value: 14, icon: svg('<path d="M4 20.4 L8.6 12 L25.4 12 L26 20.4 Z" fill="#aab3bf" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M8.6 12 L25.4 12 L23.6 9.6 L10.6 9.6 Z" fill="#d8dee6" stroke="' + O + '" stroke-width="1.5"/>' +
      '<path d="M11 14.4 L23 14.4" stroke="#ffffff" stroke-width="1.2" opacity="0.55"/>') });""",
    'IRON BAR')

sub("""    def('WOOL',          { value: 3,  icon: '<div style="width:18px;height:14px;background:#e8e2d2;border-radius:50%;"></div>' });""",
    """    def('WOOL',          { value: 3,  icon: svg('<path d="M6 17 Q4 10.6 9.6 9.6 Q11 4.6 16.4 6.4 Q22 4.4 23.6 10 Q27 13.4 24 18 Q22.4 23.4 16 22.4 Q9.6 24 6 17 Z" fill="#efeade" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M11 12.4 Q13.4 15 11.6 18 M17 10.6 Q19.4 14 17.4 17.4 M21 14 Q22.6 16.6 20.6 19" fill="none" stroke="#c9c2ae" stroke-width="1.3"/>') });""",
    'WOOL')

sub("""    def('RAT TAIL',      { value: 4,  icon: '<div style="width:24px;height:4px;background:#b08a7a;border-radius:3px;transform:rotate(-18deg);"></div>' });""",
    """    def('RAT TAIL',      { value: 4,  icon: svg('<path d="M4.6 22.6 Q11 22 14 17 Q17 12 22 12.6 Q26 13 26.4 8" fill="none" stroke="#b08a7a" stroke-width="4" stroke-linecap="round"/>' +
      '<path d="M4.6 22.6 Q11 22 14 17 Q17 12 22 12.6 Q26 13 26.4 8" fill="none" stroke="#8a6558" stroke-width="1.2" opacity="0.7"/>' +
      '<circle cx="5" cy="22.6" r="2.4" fill="#c8a094" stroke="' + O + '" stroke-width="1.3"/>') });""",
    'RAT TAIL')

sub("""    def('DEER HIDE',     { value: 9,  icon: '<div style="width:22px;height:16px;background:#9a6a3a;border:1px solid #5a3c1e;border-radius:4px 10px 4px 10px;"></div>' });""",
    """    def('DEER HIDE',     { value: 9,  icon: svg('<path d="M9 4.6 L21 4.6 L26 11 L21.4 15 L23.4 25.4 L15 22 L6.6 25.4 L8.6 15 L4 11 Z" fill="#a5763f" stroke="' + O + '" stroke-width="1.8"/>' +
      '<circle cx="12.6" cy="12" r="1.5" fill="#d9b98a" opacity="0.85"/><circle cx="18" cy="10" r="1.3" fill="#d9b98a" opacity="0.85"/>' +
      '<circle cx="16.4" cy="16.4" r="1.4" fill="#d9b98a" opacity="0.85"/>') });""",
    'DEER HIDE')

sub("""    def('VENISON',       { value: 7,  icon: '<div style="width:20px;height:14px;background:#a8443a;border:1px solid #5e241e;border-radius:7px;"></div>' });""",
    """    def('VENISON',       { value: 7,  icon: svg('<path d="M8 21.4 Q4.6 14 10.6 9.6 Q17 5 22.4 9.6 Q27 14 22.4 20.4 Q16 25.4 8 21.4 Z" fill="#a8443a" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M11.6 12.6 Q15 15.4 13.4 19.4" fill="none" stroke="#d4756a" stroke-width="1.6"/>' +
      '<path d="M7.4 22.4 L3.6 25.4" stroke="#efeade" stroke-width="3.4" stroke-linecap="round"/>' +
      '<circle cx="3.4" cy="25.6" r="2.2" fill="#efeade" stroke="' + O + '" stroke-width="1.2"/>') });""",
    'VENISON')

sub("""    def('WOLF PELT',     { value: 12, icon: '<div style="width:22px;height:16px;background:#5a5348;border:1px solid #33302a;border-radius:10px 4px 10px 4px;"></div>' });""",
    """    def('WOLF PELT',     { value: 12, icon: svg('<path d="M15 3 L19.4 7.4 L25.4 9.6 L22 16 L24.4 25.4 L15 21.4 L5.6 25.4 L8 16 L4.6 9.6 L10.6 7.4 Z" fill="#6e685c" stroke="' + O + '" stroke-width="1.8"/>' +
      '<path d="M15 3 L12.6 8 L15 12 L17.4 8 Z" fill="#8f887a" stroke="' + O + '" stroke-width="1.3"/>' +
      '<circle cx="13.2" cy="7" r="1.1" fill="#ffd24a"/><circle cx="16.8" cy="7" r="1.1" fill="#ffd24a"/>') });""",
    'WOLF PELT')

# ------------------------------------- 2. dark chunks need to read on #232323
sub("""        ? '<path d="M15 3.4 L25 9.6 L23 22 L11.4 24.4 L4.6 16 L7.8 6.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.9"/>' +
          '<path d="M15 3.4 L11.4 24.4 M25 9.6 L4.6 16" stroke="' + O + '" stroke-width="0.9" opacity="0.4"/>'""",
    """        ? '<path d="M15 3.4 L25 9.6 L23 22 L11.4 24.4 L4.6 16 L7.8 6.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.9"/>' +
          '<path d="M15 3.4 L11.4 24.4 M25 9.6 L4.6 16" stroke="' + O + '" stroke-width="0.9" opacity="0.4"/>' +
          // coal, obsidian and ember crystal are near-black against a #232323
          // panel and were reading as holes. A rim catch-light fixes it without
          // lying about the colour.
          '<path d="M7.8 6.6 L15 3.4 L25 9.6" fill="none" stroke="#ffffff" stroke-width="1.3" opacity="0.3"/>'""",
    'solid ore rim light')

sub("""        lotus: (c) => '<ellipse cx="15" cy="23.4" rx="12" ry="3.6" fill="#4e7a38" stroke="' + O + '" stroke-width="1.5"/>' +
                      '<path d="M15 20.4 Q9 18 7 11 Q13 12 15 20.4 Z M15 20.4 Q21 18 23 11 Q17 12 15 20.4 Z M15 20.4 Q15 11 15 4.6 Q19.4 12 15 20.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.5"/>' +
                      '<circle cx="15" cy="17.4" r="2" fill="#e0d8c4" stroke="' + O + '" stroke-width="1.1"/>',""",
    """        // the true lotus tint is near-black, which vanishes on the inventory
        // panel, so the icon lifts it and keeps a dark heart for contrast. The
        // world model still uses the real colour.
        lotus: (c) => '<ellipse cx="15" cy="23.4" rx="12" ry="3.6" fill="#4e7a38" stroke="' + O + '" stroke-width="1.5"/>' +
                      '<path d="M15 20.4 Q9 18 7 11 Q13 12 15 20.4 Z M15 20.4 Q21 18 23 11 Q17 12 15 20.4 Z M15 20.4 Q15 11 15 4.6 Q19.4 12 15 20.4 Z" fill="' + lighter(c, 2.5, 40) + '" stroke="' + O + '" stroke-width="1.5"/>' +
                      '<circle cx="15" cy="17.4" r="2.4" fill="' + c + '" stroke="#e0d8c4" stroke-width="1.3"/>',""",
    'lotus contrast')

sub("""      const darker = (hexIn, f) => {""",
    """      // lift a colour toward light: f multiplies, floor is the minimum channel
      // so a near-black tint still lands somewhere visible
      const lighter = (hexIn, f, floor) => {
        const n = parseInt(hexs(hexIn).slice(1), 16);
        const ch = (v) => Math.max(0, Math.min(255, Math.round(Math.max(v * f, (v || 0) + (floor || 0)))));
        const r2 = ch((n >> 16) & 255), g2 = ch((n >> 8) & 255), b2 = ch(n & 255);
        return '#' + ((1 << 24) | (r2 << 16) | (g2 << 8) | b2).toString(16).slice(1);
      };
      const darker = (hexIn, f) => {""",
    'lighter helper')

# ------------------------------------------------------- 3. thicker pick heads
sub("""        1: (c) => '<path d="M6.4 13.4 Q15 5.6 23.6 13.4 Q15 9.4 6.4 13.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.7"/>' +
                  '<path d="M12.8 10.6 L12.8 16 M17.2 10.6 L17.2 16" stroke="#5d4726" stroke-width="1.5"/>',
        2: (c) => '<path d="M5.4 12.4 Q15 4.6 24.6 12.4 Q15 8.4 5.4 12.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.7"/>',
        3: (c) => '<path d="M4.2 11.4 Q15 2.4 25.8 11.4 Q15 7 4.2 11.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M8 9.6 Q15 4.6 22 9.6" fill="none" stroke="' + SHEEN + '" stroke-width="1.2"/>',
        4: (c) => '<path d="M3 11 Q15 1 27 11 Q15 6 3 11 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M7 9 Q15 3.4 23 9" fill="none" stroke="#ffffff" stroke-width="1.5" opacity="0.85"/>',
        5: (c) => '<path d="M3 12.4 L9.4 5.4 L15 7.4 L20.6 5.4 L27 12.4 L15 8.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M9.4 5.4 L11 11 M20.6 5.4 L19 11" stroke="#9a8fb4" stroke-width="1" opacity="0.85"/>',
        6: (c) => '<path d="M3 11 Q15 1 27 11 Q15 6 3 11 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<rect x="11.4" y="9.6" width="7.2" height="4" rx="1.2" fill="' + GOLD + '" stroke="' + O + '" stroke-width="1.2"/>' +
                  '<circle cx="15" cy="11.6" r="1.7" fill="' + GEM + '" stroke="' + O + '" stroke-width="1"/>'""",
    """        1: (c) => '<path d="M5.6 14.6 Q15 4.6 24.4 14.6 Q15 11 5.6 14.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.7"/>' +
                  '<path d="M12.6 11.6 L12.6 17 M17.4 11.6 L17.4 17" stroke="#5d4726" stroke-width="1.6"/>',
        2: (c) => '<path d="M4.6 13.6 Q15 3.4 25.4 13.6 Q15 10 4.6 13.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.7"/>',
        3: (c) => '<path d="M3.6 12.6 Q15 1.6 26.4 12.6 Q15 8.6 3.6 12.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M7.6 10.4 Q15 4.6 22.4 10.4" fill="none" stroke="' + SHEEN + '" stroke-width="1.3"/>',
        4: (c) => '<path d="M2.6 12.4 Q15 0.6 27.4 12.4 Q15 8 2.6 12.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M6.6 10 Q15 3.4 23.4 10" fill="none" stroke="#ffffff" stroke-width="1.6" opacity="0.85"/>',
        5: (c) => '<path d="M2.6 13.4 L9.4 4.6 L15 7.4 L20.6 4.6 L27.4 13.4 L15 9.6 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M9.4 4.6 L11 11.6 M20.6 4.6 L19 11.6" stroke="#9a8fb4" stroke-width="1.2" opacity="0.9"/>',
        6: (c) => '<path d="M2.6 12.4 Q15 0.6 27.4 12.4 Q15 8 2.6 12.4 Z" fill="' + c + '" stroke="' + O + '" stroke-width="1.8"/>' +
                  '<path d="M6.6 10 Q15 3.4 23.4 10" fill="none" stroke="#ffffff" stroke-width="1.4" opacity="0.7"/>' +
                  '<rect x="11.4" y="11" width="7.2" height="4.2" rx="1.2" fill="' + GOLD + '" stroke="' + O + '" stroke-width="1.2"/>' +
                  '<circle cx="15" cy="13.1" r="1.7" fill="' + GEM + '" stroke="' + O + '" stroke-width="1"/>'""",
    'thicker pick heads')


out = src
for old, new, label in edits:
    assert out.count(old) == 1, 'anchor %s went stale mid-apply' % label
    out = out.replace(old, new, 1)
assert out != src
io.open(SRC, 'w', encoding='utf-8').write(out)
print('applied %d edits, %d -> %d bytes' % (len(edits), len(src), len(out)))
