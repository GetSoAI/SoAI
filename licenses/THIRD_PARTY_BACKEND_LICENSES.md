# SoAI Optional Third-Party Backend License Notice

SoAI ships plugin code and release-time dependency notices separately from optional backend software that a user may install later from the Web UI.

Optional plugin backend installation is user-triggered. When a user chooses to install a third-party backend, SoAI may download packages, tools, model runtimes, language resources, or other components into a separate managed backend environment. Those components are not bundled inside the SoAI release archive and remain governed by their own upstream licenses.

## MeloTTS

The bundled MeloTTS plugin provides an optional text-to-speech backend installer. The backend installation flow downloads MeloTTS and supporting runtime packages into a managed plugin environment only after the user starts backend installation.

The MeloTTS backend dependency set includes packages with GPL or LGPL license terms, including:

- `num2words`
- `pykakasi`
- `unidecode`

Before installing the MeloTTS backend, SoAI displays a progress notice that the backend installs third-party open-source packages with their own licenses, including GPL/LGPL components. Continue only if you accept those third-party license terms.

SoAI release packages must not contain cached MeloTTS environments, downloaded wheels, backend archives, language packs, or model artifacts.
