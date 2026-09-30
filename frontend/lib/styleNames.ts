// Display names for style/title-moment preset ids -- shared between the
// Style Gallery preview cards and anywhere else a picked style needs a
// human-readable label (e.g. the auto-export result page).
export const STYLE_NAME_OVERRIDES: Record<string, string> = {
  "typewriter-glow": "Typewriter Glow",
  "corporate-lower-third": "Corporate Lower Third",
  "name-tag": "Name Tag",
  "decrypt-reveal": "Decrypt Reveal",
  "glitch-pop": "Glitch Pop",
  "wave-bounce": "Wave Bounce",
  "rise-up": "Rise Up",
  "blur-pop": "Blur Pop",
  "karaoke-highlight": "Karaoke Highlight",
  "popline-box": "PopLine Box",
  "flamingo-underline": "Flamingo Underline",
  "speaker-colors": "Speaker Colors",
  hormozi: "Hormozi",
  mrbeast: "MrBeast",
  "classic-yellow": "Classic Yellow",
  "karaoke-wipe": "Karaoke Wipe",
  "aarit-zoom": "Aarit Zoom",
};

export function styleDisplayName(id: string): string {
  return STYLE_NAME_OVERRIDES[id] ?? id;
}
