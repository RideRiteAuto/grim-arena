# Grim World: how to author a 3D asset that does not look cheap

Written August 6 2026, off the campfire build. This is the method, not a style
guide. Follow it in order.

The problem it exists to solve: given a list of things to make, the fast path is
to write one builder per item straight into the bundle, never look at any of
them, and ship ten blocky props. Every step below is here because skipping it
produced something visibly worse.

---

## 0. The rule that makes everything else work

**Author the asset as a standalone ES module in `model-lab/`, and have the patch
script GENERATE the bundle code from that module.**

`harness/patches/28_campfire.py` reads `model-lab/campfire.js`, strips the
`export`, indents it, and wraps it as a class method. Nothing is retyped.

This is not tidiness. It is the only way the thing you looked at on the
turntable and the thing that ships stay the same thing. Keep two copies and they
are identical for one afternoon and different forever after.

Consequences worth stating:

- The module takes `T` (the three namespace) as an argument and touches nothing
  else. No `this`, no `GRIM_WORLD`, no game object. Terrain sampling comes in as
  a callback.
- It exports one factory that returns `{ mats, build(opt), tick(seconds) }`.
  Materials are created ONCE per world and shared; `build` is per instance;
  `tick` is called once a frame for every instance at once.

---

## 1. Research before you model

Twenty minutes, and it changes the geometry, not just the notes.

- **What is it actually made of, and at what size?** Firewood is no thicker than
  an adult's wrist. Fire-ring stones are hand sized because somebody carried
  them one at a time from a riverbank. Getting either wrong turns a campfire
  into a bonfire in a boulder pile, and no amount of shader work rescues it.
- **What does the real thing do that a naive model does not?** Wood fire burns
  at five or six points across the fuel bed at once, so a flame is a CLUSTER of
  tongues. One teardrop is a candle no matter how good the noise is.
- **Get the physics of the colour.** A wood fire runs white-blue where it meets
  the wood, yellow, orange through the body, deep red where it thins into
  smoke. Flatten that to one orange and it reads as plastic.
- **What does the thing leave behind?** Soot on the inner face of every ring
  stone, a dished bed of ash black at the middle, logs charred at the ends
  nearest the heat and pale further out. An effect with no aftermath floats.

Write the findings down as numbers before writing any code.

---

## 2. Build to the project's contracts

Grim World is 100 percent procedural geometry. There are no imported meshes and
no `AnimationMixer`. Match what is already there:

- **One merged mesh on one material** for anything static. `dressChunk` makes a
  whole chunk of clutter one draw call and it is not going to make an exception.
- **Flat shaded, vertex coloured.** No textures. Colour by painting vertex
  colours from a function of the vertex's own position: soot by distance from
  the fire centre, char by distance along the log. It follows the geometry
  exactly and there is no UV layout for anyone to get wrong.
- **Place things by ENDPOINTS, not by Euler angles.** The campfire teepee was
  first written as heading plus tilt composed into a Euler, and because the
  axes apply in a fixed order it came out as a flat fan of pick-up sticks.
  Rewritten as "the foot is here, the tip is there", oriented with
  `setFromUnitVectors`, it was right first try. Endpoints cannot express the
  mistake.
- **Deterministic per instance.** A seeded RNG, so the same seed rebuilds the
  same object. A streaming world reloads props constantly and they must not
  flicker into a different shape.
- **Animate on the GPU off one uniform.** Per-instance seeds go in vertex
  attributes; per-object seeds can be read straight out of `modelMatrix[3]`,
  the object's world translation, which gives every instance in the world its
  own phase with no instancing and no per-object uniforms.

---

## 3. Look at it, from every angle, in every light

`harness/prop.js` exists for this. It drives a lab page through every named
camera, every lighting rig and several points in the animation cycle, and
writes a contact sheet.

Non negotiable:

- **Cancel the render loop on the first `__shot` call.** The turntable keeps
  drawing after the harness sets its camera, so the screenshot shows whatever
  the loop drew next. Every named view came back looking like the same 3/4
  until this was fixed, and the shots looked plausible the whole time.
- **Shoot it in daylight as well as dusk.** Additive fire hides in the dark.
  The flame that looked great at dusk was a glass cone at noon.
- **Put a 1.8 m human next to it.** Nothing else calibrates size.
- **Shoot from seated and standing height, not just from a turntable orbit.**
  A pale hoop on the ground that was invisible from above was the first thing
  you saw from a seated camera.

---

## 4. Critique it honestly, then fix the worst thing

After each render, name the three worst problems in order and fix only those.
The campfire took nine passes. Real entries from that list:

| Pass | Worst problem | Fix |
|---|---|---|
| 1 | Ground glow lit the whole clearing like a stage light | 2.9 m radius down to 1.75, opacity roughly halved |
| 1 | Ring stones were boulders and hid the fuel | 0.145-0.25 down to 0.072-0.13, more of them |
| 2 | Teepee was a flat fan of sticks | rebuilt on endpoints |
| 3 | Sparks and smoke rendered nothing at all | merge helper was guessing attribute item sizes |
| 4 | Sparks rose in a dead vertical column | eased height, spread widening with height |
| 5 | Flame was a glassy translucent cone | finer noise, harder erosion threshold, rim fade |
| 6 | A pale hoop drawn on the ground | ash bed was brightest at its own rim |
| 7 | Fuel read as a picture frame | shorter pieces, crossing nearer the middle |
| 8 | Flame stood a metre over a 30 cm heap | tongues down about a quarter |

Two general lessons in there:

- **A merge helper that has to know the names of your attributes will meet one
  it does not know.** Read item size off the source attribute. The version with
  a lookup table silently rebuilt a `vec2` as a float, the particle quads
  collapsed to zero size, and the shader compiled clean with no warning.
- **A gradient that peaks at an object's edge draws a line there.** Make it peak
  inside and fall back to whatever it is sitting on.

---

## 5. Sound, if it has any

Synthesise it, do not ship a sample. The game's audio is already a few filters
on a noise buffer.

- Layer it: a low bed for weight, a mid band for texture, and short bright
  transients for the events. Fire is brown noise under about 700 Hz, a band
  around 1.5 kHz, and 4 ms attacks above that.
- **Schedule events on exponential gaps.** Anything evenly spaced becomes a
  rhythm within ten seconds and the ear never lets go of it.
- **Take the start time as an argument, not from the clock.** That one change is
  what lets `harness/campfire-audio.js` render the exact graph offline into a
  WAV and measure it. First render: peak 0.31 against RMS 0.066, a crest factor
  under five, which is the sound of a hairdryer. The bed came down and the
  crackles went up.

---

## 6. Prove it in the game, not just in the lab

`harness/campfire.js` is the template. Assert the things a screenshot cannot:

- it got built, and it SITS on the terrain rather than hovering or sinking
- mesh count, triangle count and draw calls against a stated budget
- a second instance reuses the shared materials rather than cloning them
- a different seed gives different geometry; the same seed reproduces exactly
- the collider actually pushes a probe out of the flames
- the tick moves the shader clock, the light and the ground glow
- then photograph it at player camera height

Also register the prop in `dressBlocked`. A collider stops the PLAYER; it does
not stop the pure generator growing a boulder up through your fire, because
clutter placement never sees a collider. The first in-game shot caught exactly
that.

---

## 7. Doing several at once

The reason a list of five ore nodes comes back blocky is that the work above
gets done once and divided by five. It does not divide.

- Do the research pass for the WHOLE set first: what makes these five different
  from each other in the real world, not just in tint.
- Build ONE to a finished standard and get it approved.
- Then build the rest against that one, and run the contact sheet over all of
  them together. Side by side is the only way to catch "these are the same
  object recoloured", which is the actual failure mode.
- Keep the per-instance seed, so each of the five also varies within itself.

---

## Files this method lives in

| File | What it is |
|---|---|
| `model-lab/campfire.js` | the asset, authored standalone, the single source |
| `model-lab/campfire.html` | its turntable, with named cameras and lighting rigs |
| `harness/prop.js` | every camera, every light, several times, contact sheet, budgets |
| `harness/campfire-audio.js` | renders the sound offline to WAV and measures it |
| `harness/campfire.js` | the in-game regression test and player-height shots |
| `harness/patches/28_campfire.py` | generates the bundle code FROM the module |
