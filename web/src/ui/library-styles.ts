import {css} from "lit";

export const libraryStyles = css`
  :host { display: block; color: #f5f7fb; }
  *, *::before, *::after { box-sizing: border-box; }
  .page, .stack { display: grid; gap: 1rem; min-width: 0; }
  .columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; align-items: start; }
  .panel { min-width: 0; padding: clamp(.9rem, 2vw, 1.3rem); border: 1px solid #ffffff20; border-radius: 1rem; background: linear-gradient(145deg, #171b27, #10141e); }
  .row, .actions { display: flex; align-items: center; flex-wrap: wrap; gap: .5rem; }
  .row { justify-content: space-between; }
  ul, ol { margin: 0; padding-left: 1.25rem; }
  .list { list-style: none; padding: 0; }
  .list li { padding: .65rem 0; border-top: 1px solid #ffffff14; }
  h1, h2, h3, p { margin: 0; overflow-wrap: anywhere; }
  h1 { font-size: clamp(1.55rem, 3vw, 2.4rem); }
  h2 { font-size: 1.1rem; }
  h3 { font-size: .95rem; }
  .muted, label, dt { color: #b0bbcd; }
  .mono, dd, small { overflow-wrap: anywhere; }
  .mono, textarea { font-family: ui-monospace, monospace; }
  .active { color: #69e4d3; }
  label { display: grid; gap: .35rem; min-width: 0; }
  input, select, textarea, button, .button { color: inherit; font: inherit; border: 1px solid #ffffff30; border-radius: .55rem; background: #0c1320; padding: .55rem .7rem; min-width: 0; max-width: 100%; }
  :is(button, .button) { cursor: pointer; text-decoration: none; }
  :is(button, .button):hover:not(:disabled) { background: #24324a; }
  button.primary { background: #68e5d3; border-color: #68e5d3; color: #081816; font-weight: 750; }
  button.primary:hover:not(:disabled) { background: #9af0e4; }
  button.danger { color: #ffc0d6; }
  :disabled { opacity: .6; cursor: default; }
  :focus-visible { outline: 2px solid #6be9d8; outline-offset: 3px; }
  .notice { color: #fdd89d; border-left: 2px solid #fdd89d; padding: .4rem .7rem; }
  .error { color: #ffc3d9; border-left: 2px solid #ff94be; padding: .4rem .7rem; }
  dl { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); margin: 0; gap: .65rem; }
  dd { margin: 0; }
  @media (max-width: 760px) { .columns { grid-template-columns: minmax(0, 1fr); } }
  @media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; animation: none !important; transition: none !important; } }
`;
