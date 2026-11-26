# Project credits

[FoxPodZ (foxpodz.de)](https://github.com/foxpodz/ryuo-iv-screen) is the author of the original Ryuo IV protocol research, device captures and Python reference client. The project uses GPL-3.0-or-later. Preserve the original author notices and the credit displayed in the browser. [License](LICENSE) · [Additional attribution terms](LICENSE-ADDITIONAL-TERMS.md)

## Design adaptations

[shorti1996/ryuo-display](https://github.com/shorti1996/ryuo-display), licensed under GPL-3.0-or-later, informed these local implementations.

| Local file | Design or behavior adapted |
| --- | --- |
| [ryuo_screen/device.py](ryuo_screen/device.py) | Maintain the display heartbeat, recover the connection and update screen controls during playback. |
| [ryuo_screen/media.py](ryuo_screen/media.py) | Inspect and convert media for playback and deliver custom files over ADB. |
| [web/src/ui/screen-page.ts](web/src/ui/screen-page.ts) | Present a configuration preview alongside six selectable sensor slots and screen controls. |

The branch records these as design and behavior adaptations. Its implementation history identifies no verbatim file import from ryuo-display.

## Research references

[dragocz95/asus-ryuo-iv-linux](https://github.com/dragocz95/asus-ryuo-iv-linux) served as a reference for AMD telemetry on Fedora, including k10temp and amdgpu. [zleo-ai/rog-studio](https://github.com/zleo-ai/rog-studio) served as a comparison with another Ryuo screen implementation.
