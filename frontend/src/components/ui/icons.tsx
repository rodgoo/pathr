/**
 * The icon set, as components rather than markup strings.
 *
 * The design canvas carried each icon as raw SVG injected through
 * `dangerouslySetInnerHTML`. Here they are real elements: no HTML parsing at
 * render time, and `currentColor` still lets the caller tint them.
 *
 * Two families, both Phosphor: 24-unit outline icons for navigation and list
 * rows, and 256-unit filled icons where the design wanted a solid mark.
 */
import type { SVGProps } from "react";

const OUTLINE = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

/** Outline icons — 24-unit grid. */
const OUTLINE_PATHS = {
  home: ["M3 10.5 12 3l9 7.5", "M5 9.8V20h14V9.8", "M9.5 20v-5.5h5V20"],
  road: [],
  book: [
    "M4 5.2A2.2 2.2 0 0 1 6.2 3H20v15H6.2A2.2 2.2 0 0 0 4 20.2Z",
    "M4 18.2A2.2 2.2 0 0 1 6.2 16H20v5H6.2A2.2 2.2 0 0 1 4 18.8Z",
  ],
  library: ["M4 4h3.5v16H4z", "M9.5 4H13v16H9.5z", "m15.6 5 3.3.9-3.6 14-3.3-.9Z"],
  quiz: [],
  globe: [],
  user: [],
  file: [
    "M13.5 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.5Z",
    "M13.5 3v5.5H19",
  ],
  play: [],
  code: ["m8.4 8.4-4 3.6 4 3.6", "m15.6 8.4 4 3.6-4 3.6", "m13.6 5.4-3.2 13.2"],
  chat: ["M20 15.2a2.4 2.4 0 0 1-2.4 2.4H8.4L4 21V6.4A2.4 2.4 0 0 1 6.4 4h11.2A2.4 2.4 0 0 1 20 6.4Z"],
  db: [],
  server: [],
  coffee: [
    "M4.5 6.5h12v6.8a5 5 0 0 1-5 5h-2a5 5 0 0 1-5-5Z",
    "M16.5 8.4h1.6a2.6 2.6 0 0 1 0 5.2h-1.6",
    "M6.5 3.2v1.6M10 3.2v1.6M13.5 3.2v1.6",
  ],
  article: [
    "M5 4h11a2 2 0 0 1 2 2v13a2 2 0 0 0 2-2V8",
    "M5 4a1.6 1.6 0 0 0-1.6 1.6V19a2 2 0 0 0 2 2H18",
    "M7.6 8.2h6.8M7.6 12h6.8M7.6 15.8h4",
  ],
  cog: [
    "M19.4 14.2a1.5 1.5 0 0 0 .3 1.65l.05.05a1.8 1.8 0 1 1-2.55 2.55l-.05-.05a1.5 1.5 0 0 0-1.65-.3 1.5 1.5 0 0 0-.9 1.37V20a1.8 1.8 0 1 1-3.6 0v-.1a1.5 1.5 0 0 0-.98-1.37 1.5 1.5 0 0 0-1.65.3l-.05.05A1.8 1.8 0 1 1 4.3 16.3l.05-.05a1.5 1.5 0 0 0 .3-1.65 1.5 1.5 0 0 0-1.37-.9H3a1.8 1.8 0 1 1 0-3.6h.1a1.5 1.5 0 0 0 1.37-.98 1.5 1.5 0 0 0-.3-1.65L4.12 7.4A1.8 1.8 0 1 1 6.67 4.85l.05.05a1.5 1.5 0 0 0 1.65.3H8.5a1.5 1.5 0 0 0 .9-1.37V3a1.8 1.8 0 1 1 3.6 0v.1a1.5 1.5 0 0 0 .9 1.37 1.5 1.5 0 0 0 1.65-.3l.05-.05a1.8 1.8 0 1 1 2.55 2.55l-.05.05a1.5 1.5 0 0 0-.3 1.65v.08a1.5 1.5 0 0 0 1.37.9H21a1.8 1.8 0 1 1 0 3.6h-.1a1.5 1.5 0 0 0-1.37.9Z",
  ],
  flag: ["M5.5 21V4", "M5.5 5.2c4-2.4 8 2.4 12 0v8.4c-4 2.4-8-2.4-12 0Z"],
  // Usados pelo botão de mostrar/ocultar senha. O `eyeOff` é o mesmo olho com
  // a barra diagonal por cima — a convenção que as pessoas já reconhecem.
  eye: ["M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z", "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"],
  eyeOff: [
    "M2.5 12S6 5.5 12 5.5c1.6 0 3 .45 4.2 1.1M21.5 12s-1.6 3-4.3 4.6",
    "M9.9 9.9a3 3 0 0 0 4.2 4.2",
    "m4 4 16 16",
  ],
  check: ["m5 12.5 4.5 4.5L19 7.5"],
  // Sair: o batente da porta a esquerda e a seta saindo por ele — o mesmo
  // desenho do sign-out do Phosphor, redesenhado na grade de 24.
  signOut: [
    "M9.6 20H6.4A2.4 2.4 0 0 1 4 17.6V6.4A2.4 2.4 0 0 1 6.4 4h3.2",
    "m15.2 16 4-4-4-4",
    "M19.2 12H9.6",
  ],
} as const;

/** Icons whose shape needs primitives an array of paths cannot express. */
const OUTLINE_NODES = {
  road: (
    <>
      <circle cx="6" cy="6" r="2.4" />
      <circle cx="18" cy="18" r="2.4" />
      <path d="M6 8.4v4.6a3 3 0 0 0 3 3h6a3 3 0 0 1 3 3" />
    </>
  ),
  quiz: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.6 9.4A2.5 2.5 0 0 1 14.4 10c0 1.7-2.4 2-2.4 3.4" />
      <path d="M12 17h.01" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3.2 12h17.6" />
      <path d="M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8.4" r="3.6" />
      <path d="M4.8 20a7.2 7.2 0 0 1 14.4 0" />
    </>
  ),
  play: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m10.2 8.8 5.2 3.2-5.2 3.2Z" />
    </>
  ),
  db: (
    <>
      <ellipse cx="12" cy="6" rx="7.2" ry="3" />
      <path d="M4.8 6v12c0 1.7 3.2 3 7.2 3s7.2-1.3 7.2-3V6" />
      <path d="M4.8 12c0 1.7 3.2 3 7.2 3s7.2-1.3 7.2-3" />
    </>
  ),
  server: (
    <>
      <rect x="3.5" y="4" width="17" height="6.4" rx="1.8" />
      <rect x="3.5" y="13.6" width="17" height="6.4" rx="1.8" />
      <path d="M7.2 7.2h.01M7.2 16.8h.01" />
    </>
  ),
} as const;

/** Filled icons — 256-unit grid, drawn solid in `currentColor`. */
const FILLED_PATHS = {
  flame:
    "M173.8 51.5a183.1 183.1 0 0 0-30.6-32.6 8 8 0 0 0-9.6-.6C122.5 25.7 84 55.2 84 104a71.2 71.2 0 0 0 8.7 34.6 8 8 0 0 1-1.3 9.3l-8.3 8.3a8 8 0 0 1-12.4-1.3A69.4 69.4 0 0 1 60 121.9a8 8 0 0 0-12.9-5.3C36.3 126.2 24 145.8 24 172a80 80 0 0 0 160 0c0-49.3-28.9-96.4-42.6-116.7Z",
  trend:
    "M232 208a8 8 0 0 1-8 8H32a8 8 0 0 1-8-8V48a8 8 0 0 1 16 0v107.4l50.9-44.5a8 8 0 0 1 10.4-.1l46.2 39.6 54.2-47.4a8 8 0 1 1 10.6 12l-59.5 52a8 8 0 0 1-10.4.1l-46.2-39.6L40 176.7V200h184a8 8 0 0 1 8 8Z",
  clock:
    "M128 24a104 104 0 1 0 104 104A104.1 104.1 0 0 0 128 24Zm56 112h-56a8 8 0 0 1-8-8V72a8 8 0 0 1 16 0v48h48a8 8 0 0 1 0 16Z",
  playSolid:
    "M232 128a15.8 15.8 0 0 1-7.9 13.8l-112 66A16 16 0 0 1 88 194V62a16 16 0 0 1 24.1-13.8l112 66A15.8 15.8 0 0 1 232 128Z",
  upload:
    "M213.7 82.3l-56-56A8 8 0 0 0 152 24H56a16 16 0 0 0-16 16v176a16 16 0 0 0 16 16h144a16 16 0 0 0 16-16V88a8 8 0 0 0-2.3-5.7ZM152 51.3 188.7 88H152Zm-3.5 92.4a8 8 0 0 1-11.3 11.3L136 153.9V184a8 8 0 0 1-16 0v-30.1l-1.2 1.1a8 8 0 0 1-11.3-11.3l16-16a8 8 0 0 1 11.3 0Z",
} as const;

export type OutlineIconName = keyof typeof OUTLINE_PATHS;
export type FilledIconName = keyof typeof FILLED_PATHS;
export type IconName = OutlineIconName | FilledIconName;

interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  size?: number;
}

const isFilled = (name: IconName): name is FilledIconName => name in FILLED_PATHS;

/**
 * Renders one icon at `size` px in `currentColor`.
 *
 * Decorative by default: an icon that only repeats its neighbouring label is
 * hidden from assistive tech. Pass `aria-label` (with `role="img"`) where the
 * icon is the only thing carrying the meaning.
 */
export function Icon({ name, size = 16, ...rest }: IconProps) {
  const shared = {
    width: size,
    height: size,
    "aria-hidden": rest["aria-label"] ? undefined : true,
    focusable: false,
    ...rest,
  };

  if (isFilled(name)) {
    return (
      <svg viewBox="0 0 256 256" fill="currentColor" {...shared}>
        <path d={FILLED_PATHS[name]} />
      </svg>
    );
  }

  const nodes = OUTLINE_NODES[name as keyof typeof OUTLINE_NODES];
  return (
    <svg viewBox="0 0 24 24" {...OUTLINE} {...shared}>
      {nodes ?? OUTLINE_PATHS[name].map((d) => <path key={d} d={d} />)}
    </svg>
  );
}
