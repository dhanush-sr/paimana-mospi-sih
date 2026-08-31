// Build a red sequential ramp matching the blue reference ramp's OKLCH
// lightness trajectory (same L at each step), hue rotated to the palette's
// categorical red (#e34948), chroma held as high as sRGB gamut allows at
// that L. Standard OKLab/OKLCH conversion (Björn Ottosson, public formulas).

function srgbToLin(c) {
  c /= 255;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}
function linToSrgb(c) {
  c = Math.max(0, Math.min(1, c));
  return Math.round(255 * (c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055));
}
function hexToRgb(h) {
  h = h.replace('#', '');
  return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)];
}
function rgbToHex([r,g,b]) {
  return '#' + [r,g,b].map(v => v.toString(16).padStart(2,'0')).join('');
}
function linToOklab(r,g,b) {
  const l = 0.4122214708*r + 0.5363325363*g + 0.0514459929*b;
  const m = 0.2119034982*r + 0.6806995451*g + 0.1073969566*b;
  const s = 0.0883024619*r + 0.2817188376*g + 0.6299787005*b;
  const l_ = Math.cbrt(l), m_ = Math.cbrt(m), s_ = Math.cbrt(s);
  return [
    0.2104542553*l_ + 0.7936177850*m_ - 0.0040720468*s_,
    1.9779984951*l_ - 2.4285922050*m_ + 0.4505937099*s_,
    0.0259040371*l_ + 0.7827717662*m_ - 0.8086757660*s_,
  ];
}
function oklabToLin(L,a,b) {
  const l_ = L + 0.3963377774*a + 0.2158037573*b;
  const m_ = L - 0.1055613458*a - 0.0638541728*b;
  const s_ = L - 0.0894841775*a - 1.2914855480*b;
  const l = l_**3, m = m_**3, s = s_**3;
  return [
    +4.0767416621*l - 3.3077115913*m + 0.2309699292*s,
    -1.2684380046*l + 2.6097574011*m - 0.3413193965*s,
    -0.0041960863*l - 0.7034186147*m + 1.7076147010*s,
  ];
}
function hexToOklch(hex) {
  const [r,g,b] = hexToRgb(hex).map(srgbToLin);
  const [L,a,bb] = linToOklab(r,g,b);
  const C = Math.hypot(a,bb);
  const H = Math.atan2(bb,a);
  return [L,C,H];
}
function inGamut(r,g,b) { return [r,g,b].every(v => v >= -1e-4 && v <= 1+1e-4); }
function oklchToHex(L,C,H) {
  // reduce chroma until in-gamut
  let c = C;
  for (let i = 0; i < 40; i++) {
    const a = c*Math.cos(H), b = c*Math.sin(H);
    const [r,g,bl] = oklabToLin(L,a,b);
    if (inGamut(r,g,bl)) return rgbToHex([linToSrgb(r),linToSrgb(g),linToSrgb(bl)]);
    c *= 0.92;
  }
  const a = 0, b = 0;
  const [r,g,bl] = oklabToLin(L,a,b);
  return rgbToHex([linToSrgb(r),linToSrgb(g),linToSrgb(bl)]);
}

const BLUE = {
  100:'#cde2fb',150:'#b7d3f6',200:'#9ec5f4',250:'#86b6ef',300:'#6da7ec',
  350:'#5598e7',400:'#3987e5',450:'#2a78d6',500:'#256abf',550:'#1c5cab',
  600:'#184f95',650:'#104281',700:'#0d366b',
};
const RED_HUE_ANCHOR = '#e34948'; // categorical slot 8 (red)
const [,, hueRed] = hexToOklch(RED_HUE_ANCHOR);

console.log('step  blueL   blueC   ->  redHex   redL    redC');
const out = {};
for (const [step, hex] of Object.entries(BLUE)) {
  const [L, C] = hexToOklch(hex);
  // slightly boost target chroma request since red gamut allows more at
  // low L than blue does - oklchToHex clamps to gamut regardless.
  const redHex = oklchToHex(L, Math.max(C, 0.09), hueRed);
  const [L2, C2] = hexToOklch(redHex);
  out[step] = redHex;
  console.log(`${step}  ${L.toFixed(3)}  ${C.toFixed(3)}   ->  ${redHex}  ${L2.toFixed(3)}  ${C2.toFixed(3)}`);
}
console.log('\nJSON:', JSON.stringify(out));

// ---- dark-mode ramp: sequential anchor flips near the dark surface ----
// Dark surface #1a1a19 has OKLCH L ~0.15. Near-zero magnitude should sit
// close to that surface (low L, low chroma - barely present), rising to a
// bright, saturated red at the high-magnitude end (L in the dark band so it
// still reads as a mark, not a "light mode color pasted on dark").
console.log('\n--- DARK RAMP ---');
const outDark = {};
const steps = Object.keys(BLUE).map(Number);
const n = steps.length;
for (let i = 0; i < n; i++) {
  const t = i / (n - 1); // 0 = near-zero magnitude, 1 = max
  const L = 0.26 + t * (0.74 - 0.26);       // 0.26 -> 0.74
  const C = 0.05 + Math.min(t, 0.6)/0.6 * 0.13; // rises then plateaus ~0.18
  const hex = oklchToHex(L, C, hueRed);
  outDark[steps[i]] = hex;
  const [L2,C2] = hexToOklch(hex);
  console.log(`${steps[i]}  target L ${L.toFixed(3)} C ${C.toFixed(3)}  -> ${hex}  actualL ${L2.toFixed(3)} C ${C2.toFixed(3)}`);
}
console.log('\nJSON dark:', JSON.stringify(outDark));
