# Bundled board fonts

These assets are packaged with the backend for snapshot rendering and bundled by Vite for
browser canvases. No font service, Internet access or host font installation is needed.

- Kalam Regular: Google Fonts `ofl/kalam/Kalam-Regular.ttf`, downloaded 16 November 2026.
  SIL Open Font License 1.1: [Kalam-LICENSE.txt](Kalam-LICENSE.txt).
- DejaVu Sans, Serif and Sans Mono: DejaVu fonts distributed with Debian's
  `fonts-dejavu-core`; [DejaVu-LICENSE.txt](DejaVu-LICENSE.txt) retains the copyright and licence.

The application exposes only `sans`, `serif`, `mono` and `handwritten`, with sizes 8–48.
The API does not accept arbitrary CSS, font paths or font URLs.
