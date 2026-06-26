/* Hand-drawn geometric glyphs — deliberately NOT lucide.
   Square-cornered, 1.6px stroke, currentColor. Minimal archival marks. */
import * as React from "react";

type P = { size?: number; className?: string };
const base = (size: number): React.SVGProps<SVGSVGElement> => ({
  width: size, height: size, viewBox: "0 0 24 24", fill: "none",
  stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "square", strokeLinejoin: "miter",
});

export const Glyph = {
  // dashboard: a filled ledger square split into quadrants
  board: ({ size = 18, className }: P) => (
    <svg {...base(size)} className={className}><rect x="3" y="3" width="18" height="18"/><path d="M3 12h18M12 3v18"/></svg>
  ),
  // search: lens as concentric square + tick (not the usual circle+handle)
  find: ({ size = 18, className }: P) => (
    <svg {...base(size)} className={className}><rect x="4" y="4" width="11" height="11"/><path d="M15 15l5 5"/></svg>
  ),
  // services: stacked rules (a list/registry)
  registry: ({ size = 18, className }: P) => (
    <svg {...base(size)} className={className}><path d="M4 6h16M4 12h16M4 18h10"/></svg>
  ),
  // partners: two offset frames (institutions)
  partners: ({ size = 18, className }: P) => (
    <svg {...base(size)} className={className}><rect x="3" y="7" width="11" height="13"/><path d="M10 7V4h11v13h-3"/></svg>
  ),
  // documents: a sheet with a folded corner drawn square
  docs: ({ size = 18, className }: P) => (
    <svg {...base(size)} className={className}><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/></svg>
  ),
  // review: a checkmark inside a frame
  review: ({ size = 18, className }: P) => (
    <svg {...base(size)} className={className}><rect x="3" y="3" width="18" height="18"/><path d="M7 12l3 3 6-7"/></svg>
  ),
  // arrow used inline
  arrow: ({ size = 16, className }: P) => (
    <svg {...base(size)} className={className}><path d="M5 12h12M12 6l6 6-6 6"/></svg>
  ),
  // plus
  plus: ({ size = 16, className }: P) => (
    <svg {...base(size)} className={className}><path d="M12 5v14M5 12h14"/></svg>
  ),
  // cross
  x: ({ size = 16, className }: P) => (
    <svg {...base(size)} className={className}><path d="M6 6l12 12M18 6L6 18"/></svg>
  ),
};
