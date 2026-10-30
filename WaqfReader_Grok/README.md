# وقف وابتداء — WaqfReader_Grok

Flutter reader demo matching the Android mockups in `docs/mockups/`.

## Look

- Parchment mushaf (`#F9F4E8`) + forest green (`#1A5C48` / `#1B3D2F`)
- Gold ornament dividers around the reading block
- Circular stop badges: ط / ج / لا (selected ط has soft green rings)
- Dark green bottom sheet (`#1A2B20`) with آراء العلماء + مقترحات AI
- Tabs: مصحف · فهرس · مراجعة

## Run

```powershell
cd D:\AI_Projects\waqfWibtida2\WaqfReader_Grok
flutter pub get
flutter run                 # Android device/emulator
flutter run -d chrome       # quick preview
```

First launch needs internet once so Cairo + Amiri Quran fonts download.

## Sample data

Hardcoded Yusuf 100–111 in `lib/data/sample_data.dart`. Tap **حقًّا** (ط) to open the sheet from the mockup.
