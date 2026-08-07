#!/usr/bin/env python3
"""Patch 72.883: action bar grows from 6 slots to 8, stays centered, and
starts EMPTY for every new character.

Kevin's ask, verbatim: "upgrade it so there's eight slots in the action bar
... make sure the action bar is recentered ... make a default so when
players load in the game, none of their items are already in the action
bar so they can place them themselves."

Three separate changes, all in the same drop:

1. TWO MORE SLOTS (6 -> 8). The bar is built entirely off an array of
   React refs (slot0Ref..slot5Ref) that every bar-aware method rebuilds
   its slot list from -- paintBar(), switchWeapon()'s highlight pass, and
   cycleBar()'s scroll-through-your-weapons loop. Extend that array to
   slot0Ref..slot7Ref everywhere it appears (ref declarations, the props
   object handed to the template, the three refs-arrays above), add two
   more slot <div>s to the static markup, and add Digit7/Digit8 to the
   keyboard map plus their dispatch. bindBar() -- the function every drag,
   drop, and right-click bind path funnels through -- had its own
   hardcoded `i > 5` range check; missing that would have made the two
   new slots visible but silently unbindable by drag, which is worse than
   not having them.

2. RECENTERED. Turns out this needs no CSS math at all: the bar's outer
   wrapper is already `position:absolute; left:50%; transform:
   translateX(-50%)` with the slot row centered inside it by flexbox
   (`align-items:center`). That is a self-centering layout by
   construction -- it was never pinned to a fixed 6-slot width anywhere.
   Adding two more 54px slots widens the row and the existing transform
   keeps it dead center automatically. Nothing to change here beyond
   correctly adding the new slots in step 1.

3. EMPTY BY DEFAULT. Three separate places initialise this.bar, and Kevin
   only wants the NEW-CHARACTER case changed:

   - freshCharacter() (the true "brand new account, first login ever"
     path) hardcoded the whole starter loadout straight onto the bar:
     ['IRON SCIMITAR', 'OAK STAFF', 'HUNTING BOW', 'CRUDE PICK',
     'CRUDE AXE', 'GRIM CLEAVER']. This is the one Kevin is describing.
     Switched to 8 nulls. The starting gear itself is untouched --
     IRON SCIMITAR is still equipped in the WEAPON slot (worn, not bar),
     and the four tools still land in the pack -- so a new player still
     has everything, they just have to drag it onto the bar themselves,
     which is exactly the ask.
   - The other two this.bar assignments (top of invLoad() for the local/
     guest save path, and the equivalent spot in applySaveBlob() for the
     cloud/account path) are NOT a "new character" default in isolation --
     they are the FALLBACK value used per-slot when a returning player's
     saved bar is missing or invalid at that index:
       this.bar = this.bar.map((d, i) => (raw.bar[i] === null || IT[raw.bar[i]]) ? raw.bar[i] : d)
     A returning player's valid raw.bar[i] always wins over d, so an
     existing character's bound items in slots 0-5 are completely
     unaffected either way. What d controls is ONLY: (a) a slot with no
     saved entry at all (which after this patch means the two brand new
     slots 6/7 for every existing save, since old saves only have 6
     entries), and (b) the rare case of a corrupted/invalid saved id.
     Changed both to 8 nulls too, for the same reason as freshCharacter:
     nothing should silently reappear pre-bound in a slot the player
     never bound it to, whether that slot is old or new. Existing
     players lose nothing -- their real saved bindings still load from
     raw.bar exactly as before.

   Net effect: brand new characters get a fully empty 8-slot bar (worn
   gear and pack contents unchanged). Existing characters keep every bar
   slot they already had bound, and simply gain two new empty slots.

Also updated every player-facing "1-6" reference to "1-8" (the action bar
caption, the pack-panel drag hint, the first-time pack tutorial banner,
the front-menu control legend) so the UI does not lie about how many keys
now equip something. The front-menu legend line specifically named the
old fixed loadout ("1-5 blade . staff . bow . pick . axe"), which is now
inaccurate since nothing is pre-bound -- reworded to say what is actually
true: the keys equip whatever you bind. Historical patch-notes text
(the V12 entry mentioning "keys 1-6") is left alone on purpose -- it is a
record of what that version shipped, not current instructions.
"""
import io

SRC = '/tmp/game-src.html'
s = io.open(SRC, encoding='utf-8').read()
n = 0


def sub(old, new, count=1, tag=''):
    global s, n
    f = s.count(old)
    assert f == count, 'patch 72.883 [%s]: anchor found %d times, wanted %d' % (tag, f, count)
    s = s.replace(old, new)
    n += 1


# ---- 1. keyboard map: Digit7 / Digit8 -------------------------------------
sub(
    """      Digit1: '1', Digit2: '2', Digit3: '3', Digit4: '4', Digit5: '5', Digit6: '6', Numpad6: '6',
      Numpad1: '1', Numpad2: '2', Numpad3: '3', Numpad4: '4', Numpad5: '5',""",
    """      Digit1: '1', Digit2: '2', Digit3: '3', Digit4: '4', Digit5: '5', Digit6: '6', Numpad6: '6',
      Digit7: '7', Digit8: '8', Numpad7: '7', Numpad8: '8',
      Numpad1: '1', Numpad2: '2', Numpad3: '3', Numpad4: '4', Numpad5: '5',""",
    tag='CODES: add Digit7/Digit8/Numpad7/Numpad8')

# ---- 2. dispatch: keys 7 and 8 equip bar slots 6 and 7 --------------------
sub(
    """      if (k === '6') this.switchWeapon(5);""",
    """      if (k === '6') this.switchWeapon(5);
      if (k === '7') this.switchWeapon(6);
      if (k === '8') this.switchWeapon(7);""",
    tag='kd dispatch: 7/8 -> switchWeapon(6)/(7)')

# ---- 3. ref declarations: slot6Ref, slot7Ref ------------------------------
sub(
    """  slot3Ref = React.createRef(); slot4Ref = React.createRef(); slot5Ref = React.createRef(); lockHudRef = React.createRef();""",
    """  slot3Ref = React.createRef(); slot4Ref = React.createRef(); slot5Ref = React.createRef();
  slot6Ref = React.createRef(); slot7Ref = React.createRef(); lockHudRef = React.createRef();""",
    tag='ref declarations: slot6Ref/slot7Ref')

# ---- 4. renderVals(): pass the two new refs to the template ---------------
sub(
    """      slot3Ref: this.slot3Ref, slot4Ref: this.slot4Ref, slot5Ref: this.slot5Ref, lockHudRef: this.lockHudRef,""",
    """      slot3Ref: this.slot3Ref, slot4Ref: this.slot4Ref, slot5Ref: this.slot5Ref,
      slot6Ref: this.slot6Ref, slot7Ref: this.slot7Ref, lockHudRef: this.lockHudRef,""",
    tag='renderVals: slot6Ref/slot7Ref')

# ---- 5. static markup: two more 54px slot tiles + "1-8" caption -----------
sub(
    """      <div ref="{{ slot5Ref }}" style="width:54px; height:54px; background:rgba(10,11,8,0.62); border:2px solid #2c2f24; position:relative;"></div>
    </div>
    <div style="font-size:9.5px; letter-spacing:0.1em; color:#7d8a63; font-family:IBM Plex Mono,monospace; text-shadow:0 2px 4px #000; background:rgba(10,11,8,0.62); border:1px solid #2f3426; padding:4px 12px;"><span style="color:#b3c29a; font-weight:700;">1-6</span> equip &nbsp;·&nbsp; <span style="color:#b3c29a; font-weight:700;">SCROLL</span> swap weapon &nbsp;·&nbsp; <span style="color:#b3c29a; font-weight:700;">RMB</span> guard &nbsp;·&nbsp; <span style="color:#b3c29a; font-weight:700;">HOLD Q</span> spell <span ref="{{ spellNameRef }}" style="color:#ffa15c;">Fire</span></div>""",
    """      <div ref="{{ slot5Ref }}" style="width:54px; height:54px; background:rgba(10,11,8,0.62); border:2px solid #2c2f24; position:relative;"></div>
      <div ref="{{ slot6Ref }}" style="width:54px; height:54px; background:rgba(10,11,8,0.62); border:2px solid #2c2f24; position:relative;"></div>
      <div ref="{{ slot7Ref }}" style="width:54px; height:54px; background:rgba(10,11,8,0.62); border:2px solid #2c2f24; position:relative;"></div>
    </div>
    <div style="font-size:9.5px; letter-spacing:0.1em; color:#7d8a63; font-family:IBM Plex Mono,monospace; text-shadow:0 2px 4px #000; background:rgba(10,11,8,0.62); border:1px solid #2f3426; padding:4px 12px;"><span style="color:#b3c29a; font-weight:700;">1-8</span> equip &nbsp;·&nbsp; <span style="color:#b3c29a; font-weight:700;">SCROLL</span> swap weapon &nbsp;·&nbsp; <span style="color:#b3c29a; font-weight:700;">RMB</span> guard &nbsp;·&nbsp; <span style="color:#b3c29a; font-weight:700;">HOLD Q</span> spell <span ref="{{ spellNameRef }}" style="color:#ffa15c;">Fire</span></div>""",
    tag='static markup: slot6/slot7 tiles + 1-8 caption')

# ---- 6. paintBar(): the slot-refs array it paints every frame -------------
sub(
    """    const refs = [this.slot0Ref, this.slot1Ref, this.slot2Ref, this.slot3Ref, this.slot4Ref, this.slot5Ref];
    const worn = this.worn.WEAPON && this.worn.WEAPON.item;""",
    """    const refs = [this.slot0Ref, this.slot1Ref, this.slot2Ref, this.slot3Ref, this.slot4Ref, this.slot5Ref, this.slot6Ref, this.slot7Ref];
    const worn = this.worn.WEAPON && this.worn.WEAPON.item;""",
    tag='paintBar refs -> 8 slots')

# ---- 7. cycleBar(): scroll through weapons across all 8 slots -------------
sub(
    """  cycleBar(dir) {
    // scroll flips through the WEAPONS you actually have, in bar order
    const idxs = [];
    for (let i = 0; i < 6; i++) {""",
    """  cycleBar(dir) {
    // scroll flips through the WEAPONS you actually have, in bar order
    const idxs = [];
    for (let i = 0; i < 8; i++) {""",
    tag='cycleBar loop -> 8 slots')

# ---- 8. switchWeapon(): the highlight-the-active-slot refs array ----------
sub(
    """    const refs = [this.slot0Ref, this.slot1Ref, this.slot2Ref, this.slot3Ref, this.slot4Ref, this.slot5Ref];
    refs.forEach((r, i) => {""",
    """    const refs = [this.slot0Ref, this.slot1Ref, this.slot2Ref, this.slot3Ref, this.slot4Ref, this.slot5Ref, this.slot6Ref, this.slot7Ref];
    refs.forEach((r, i) => {""",
    tag='switchWeapon highlight refs -> 8 slots')

# ---- 9. switchWeapon()'s doc comment, cosmetic but worth keeping honest ---
sub(
    """    // keys 1-6 equip the item BOUND to that bar slot. the bar holds ids,""",
    """    // keys 1-8 equip the item BOUND to that bar slot. the bar holds ids,""",
    tag='switchWeapon comment 1-6 -> 1-8')

# ---- 10. bindBar(): the hard range check every bind path funnels through -
sub(
    """  bindBar(i, id) {
    if (i < 0 || i > 5) return;""",
    """  bindBar(i, id) {
    if (i < 0 || i > 7) return;""",
    tag='bindBar range check -> 8 slots')

# ---- 11. freshCharacter(): the actual "new player" default -- EMPTY bar --
sub(
    """    this.bar = ['IRON SCIMITAR', 'OAK STAFF', 'HUNTING BOW', 'CRUDE PICK', 'CRUDE AXE', 'GRIM CLEAVER'];
    this.overflow = [];
    this.bankV = [];
    let i = 0;
    for (const t of ['OAK STAFF', 'HUNTING BOW', 'CRUDE PICK', 'CRUDE AXE']) this.inv[i++] = { item: t, qty: 1 };""",
    """    // Bar starts EMPTY on purpose (Kevin, Aug 7): a new character still
    // gets the full starter kit (scimitar worn, the rest in the pack below)
    // but nothing is pre-bound to the action bar -- you drag it on yourself.
    this.bar = [null, null, null, null, null, null, null, null];
    this.overflow = [];
    this.bankV = [];
    let i = 0;
    for (const t of ['OAK STAFF', 'HUNTING BOW', 'CRUDE PICK', 'CRUDE AXE']) this.inv[i++] = { item: t, qty: 1 };""",
    tag='freshCharacter bar -> empty')

# ---- 12. invLoad() (local/guest path): per-slot fallback default, not a --
#          direct new-character default, but must stop supplying a full
#          pre-bound loadout for any slot a save does not actually have ---
sub(
    """    this.worn = { HEAD: null, AMULET: null, WEAPON: null, BODY: null, SHIELD: null, LEGS: null };
    this.bar = ['IRON SCIMITAR', 'OAK STAFF', 'HUNTING BOW', 'IRON PICKAXE', 'IRON AXE', 'GRIM CLEAVER'];
    this.overflow = [];
    let raw = null;
    try { raw = JSON.parse(localStorage.getItem('grim-inv-v1') || 'null'); } catch (e) {}""",
    """    this.worn = { HEAD: null, AMULET: null, WEAPON: null, BODY: null, SHIELD: null, LEGS: null };
    // Default here is the per-slot FALLBACK used only when a saved bar has
    // no valid entry at that index (see the raw.bar map below) -- a
    // returning player's real bindings always win. Empty so neither a
    // brand new guest nor a newly added slot 6/7 on an old save comes back
    // pre-bound to anything the player never actually chose.
    this.bar = [null, null, null, null, null, null, null, null];
    this.overflow = [];
    let raw = null;
    try { raw = JSON.parse(localStorage.getItem('grim-inv-v1') || 'null'); } catch (e) {}""",
    tag='invLoad bar default -> empty fallback')

# ---- 13. applySaveBlob() (cloud/account path): same fallback treatment ---
sub(
    """    this.worn = { HEAD: null, AMULET: null, WEAPON: null, BODY: null, SHIELD: null, LEGS: null };
    this.bar = ['IRON SCIMITAR', 'OAK STAFF', 'HUNTING BOW', 'IRON PICKAXE', 'IRON AXE', 'GRIM CLEAVER'];
    this.overflow = [];
    this.bankV = [];
    if (raw && raw.inv) {""",
    """    this.worn = { HEAD: null, AMULET: null, WEAPON: null, BODY: null, SHIELD: null, LEGS: null };
    // Same fallback-only role as invLoad's default above -- a returning
    // account's real raw.bar entries always win; this only backfills a
    // slot with no saved entry (new slots 6/7 on an old save) with empty
    // instead of a pre-bound item the player never chose.
    this.bar = [null, null, null, null, null, null, null, null];
    this.overflow = [];
    this.bankV = [];
    if (raw && raw.inv) {""",
    tag='applySaveBlob bar default -> empty fallback')

# ---- 14. player-facing "1-6" copy -> "1-8" --------------------------------
sub(
    """DRAG ITEMS ONTO THE BOTTOM BAR TO BIND KEYS 1-6""",
    """DRAG ITEMS ONTO THE BOTTOM BAR TO BIND KEYS 1-8""",
    tag='pack panel hint 1-6 -> 1-8')
sub(
    """this.banner('YOUR PACK & GEAR', 'DRAG ITEMS TO WEAR THEM, BIND WEAPONS TO KEYS 1-6, RIGHT-CLICK FOR MORE. THE LEGEND AT THE BOTTOM LISTS EVERY CONTROL.', false, 6500);""",
    """this.banner('YOUR PACK & GEAR', 'DRAG ITEMS TO WEAR THEM, BIND WEAPONS TO KEYS 1-8, RIGHT-CLICK FOR MORE. THE LEGEND AT THE BOTTOM LISTS EVERY CONTROL.', false, 6500);""",
    tag='first-time pack tutorial banner 1-6 -> 1-8')

# ---- 15. front-menu control legend: no longer a fixed loadout, say so ----
sub(
    """            <div style="color:#b3afa0;"><span style="color:#f2efe6;">1-5</span> &nbsp;blade · staff · bow · pick · axe</div><div style="color:#b3afa0;"><span style="color:#f2efe6;">HOLD Q</span> &nbsp;spell wheel (staff)</div><div style="color:#b3afa0;"><span style="color:#f2efe6;">HOLD O</span> &nbsp;who is online</div>""",
    """            <div style="color:#b3afa0;"><span style="color:#f2efe6;">1-8</span> &nbsp;equip whatever you bind &nbsp;<span style="color:#5f6b4a;">TAB to drag items on</span></div><div style="color:#b3afa0;"><span style="color:#f2efe6;">HOLD Q</span> &nbsp;spell wheel (staff)</div><div style="color:#b3afa0;"><span style="color:#f2efe6;">HOLD O</span> &nbsp;who is online</div>""",
    tag='front-menu MOVEMENT legend 1-5 -> 1-8, wording')

io.open(SRC, 'w', encoding='utf-8').write(s)
print('72.883_action_bar_eight_slots: %d edits applied (1-15)' % n)
