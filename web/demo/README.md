# Local Web UI demo

The demo opens the regular Lit interface with a fixed Ryzen 9 7900X and RX 7900 XTX example. Every tab shows **Демонстрационные данные**. The split-screen illustration previews the configured slots. All displayed values, connection indicators, media names and profiles are fixtures.

From the repository root, install the locked Web dependencies if needed and start Vite on its dedicated loopback port.

```sh
npm --prefix web ci
npm --prefix web run demo
```

Open [the demo on port 5173](http://127.0.0.1:5173/). Use the navigation tabs to explore the dashboard, screen, media, profiles and settings. The demo handles reads and one fixed snapshot event in memory. It rejects writes, and disables ADB uploads and media previews. The daemon can stay stopped. Stop the demo with Ctrl+C in its terminal.

## Capture the documentation images

Leave the demo running. In another terminal at the repository root, run the capture with Node.js 22.13+ and Firefox on the path. Set `FIREFOX` to the executable path if needed. The tested versions were Node.js 22.23.3 and Firefox 155.0 on Linux.

```sh
node web/demo/capture.mjs
```

The command launches headless Firefox with a temporary profile. It waits for the example values, checks the demo label and horizontal fit, and writes four 1440-pixel-wide PNGs at device pixel ratio 1. Each desktop viewport expands to include the page controls. [Documentation gallery](../../docs/web-ui.md#demo-screenshots)

For an additional 390 × 844 mobile Dashboard capture, supply a destination outside the documentation gallery.

```sh
node web/demo/capture.mjs /tmp/ryuo-mobile-smoke.png
```

The sample data and viewport stay fixed. Browser versions, fonts and operating-system controls affect the pixels.
