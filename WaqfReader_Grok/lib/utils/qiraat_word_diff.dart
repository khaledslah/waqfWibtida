import '../models/waqf_models.dart';

export '../models/waqf_models.dart' show QiraatWordOverride;

/// Returns the persisted, LLM-verified Qira'at word modifications for [demo].
List<QiraatWordOverride> extractQiraatWordOverrides({
  required WaqfStop stop,
  required WaqfDemoAndMeaning demo,
  required List<Ayah> ayahs,
}) {
  return demo.qiraatOverrides;
}

bool _isMark(int cu) =>
    (cu >= 0x064B && cu <= 0x065F) || // harakat, shadda, sukun …
    cu == 0x0670 || // superscript alef
    (cu >= 0x06D6 && cu <= 0x06ED) || // Quranic annotation marks
    cu == 0x0640; // tatweel

/// For each UTF-16 unit of [modified], whether it differs from [hafs]
/// (a letter or i'rab mark that was added/changed in the other Qira'ah).
///
/// Uses an LCS alignment on the raw characters, so an unchanged letter keeps
/// its colour while only the swapped harakat (e.g. ـٌ ← ـً) or letters light up.
/// A base letter whose own marks changed stays uncoloured; only the marks are.
List<bool> qiraatChangedMask(String hafs, String modified) {
  final a = hafs.runes.toList();
  final b = modified.runes.toList();
  final n = a.length;
  final m = b.length;

  // LCS table.
  final dp = List.generate(n + 1, (_) => List<int>.filled(m + 1, 0));
  for (var i = n - 1; i >= 0; i--) {
    for (var j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] == b[j]
          ? dp[i + 1][j + 1] + 1
          : (dp[i + 1][j] >= dp[i][j + 1] ? dp[i + 1][j] : dp[i][j + 1]);
    }
  }

  final changedRune = List<bool>.filled(m, true);
  var i = 0;
  var j = 0;
  while (i < n && j < m) {
    if (a[i] == b[j]) {
      changedRune[j] = false;
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      i++;
    } else {
      j++;
    }
  }

  // If the whole word is different (nothing aligned), colour everything.
  final anyKept = changedRune.contains(false);
  if (!anyKept) return List<bool>.filled(modified.length, true);

  // Widen each change to its whole letter cluster (base letter + its marks).
  // A lone coloured mark is nearly invisible (thin glyph, and some renderers
  // paint a combining mark with its base letter's colour), so the letter that
  // carries the changed i'rab is coloured with it.
  final cluster = List<bool>.of(changedRune);
  var k0 = 0;
  while (k0 < m) {
    var end = k0 + 1;
    while (end < m && _isMark(b[end])) {
      end++;
    }
    var anyChanged = false;
    for (var k = k0; k < end; k++) {
      if (changedRune[k]) anyChanged = true;
    }
    if (anyChanged) {
      for (var k = k0; k < end; k++) {
        cluster[k] = true;
      }
    }
    k0 = end;
  }
  for (var k = 0; k < m; k++) {
    changedRune[k] = cluster[k];
  }

  // Expand rune flags to UTF-16 units.
  final out = <bool>[];
  for (var k = 0; k < m; k++) {
    final units = String.fromCharCode(b[k]).length;
    for (var u = 0; u < units; u++) {
      out.add(changedRune[k]);
    }
  }
  return out;
}

/// Splits [modified] into (text, changed) runs for a RichText.
List<(String, bool)> qiraatDiffRuns(String hafs, String modified) {
  if (modified.isEmpty) return const <(String, bool)>[];
  final mask = qiraatChangedMask(hafs, modified);
  final runs = <(String, bool)>[];
  final buf = StringBuffer();
  var cur = mask.isEmpty ? false : mask.first;
  for (var i = 0; i < modified.length; i++) {
    final flag = i < mask.length ? mask[i] : false;
    if (flag != cur && buf.isNotEmpty) {
      runs.add((buf.toString(), cur));
      buf.clear();
      cur = flag;
    }
    buf.writeCharCode(modified.codeUnitAt(i));
  }
  if (buf.isNotEmpty) runs.add((buf.toString(), cur));
  return runs;
}

/// True if [cu] is an Arabic combining mark (i'rab etc.).
bool isArabicMarkUnit(int cu) => _isMark(cu);
