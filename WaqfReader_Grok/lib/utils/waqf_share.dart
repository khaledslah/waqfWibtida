import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';

/// What the stop share menu sends.
enum StopShareMode { opinions, meanings, all }

const String _sectionDivider = '┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈';

final RegExp _arabicMarksPattern = RegExp(
  r'[\u0610-\u061A\u0640\u064B-\u065F\u06D6-\u06ED]',
);
final RegExp _leadingWaqfRecitePrefix = RegExp(
  r'^\s*تلاوة(?:\s+الوقف)?\s*:\s*',
);
final RegExp _leadingIbtidaRecitePrefix = RegExp(
  r'^\s*تلاوة\s+الابتداء\s*:\s*',
);

/// Formats text for one scholar's opinion on a stop.
String formatOpinionText(
  WaqfStop stop,
  ScholarOpinion op, {
  String? surahName,
  bool includeHeader = true,
  bool includeDemos = true,
}) {
  final b = StringBuffer();
  if (includeHeader) {
    b
      ..writeln(_stopHeader(stop, surahName))
      ..writeln();
  }
  _writeOpinionEntry(b, stop, op);
  if (includeDemos && op.demosAndMeanings.isNotEmpty) {
    for (final demo in op.demosAndMeanings) {
      b.writeln();
      final header = _demoHeaderDetails(demo);
      b.writeln('✨ *بيان الوقف والابتداء* — $header:');
      _writeDemoBodyLines(b, demo);
    }
  }
  return b.toString().trimRight();
}

/// Formats text for a stop: header, then all opinions, then meanings.
String formatStopText(WaqfStop stop, {String? surahName}) {
  final mainDemo = _firstDemoWithSpans(stop) ?? _firstDemo(stop);
  final b = StringBuffer()..writeln(_stopHeader(stop, surahName));
  _writeOpinionsSection(b, stop);
  _writeMeaningsSection(
    b,
    stop,
    mainDemo: mainDemo,
    includeBookRef: false,
    showEmptyNotice: false,
  );
  return b.toString().trimRight();
}

/// Share payload for the stop menu (أقوال / معاني / الكل).
String formatStopShare(
  WaqfStop stop, {
  required StopShareMode mode,
  Ayah? ayah,
  String? surahName,
  WaqfDemoAndMeaning? highlightDemo,
}) {
  final demo = highlightDemo ?? _firstDemoWithSpans(stop) ?? _firstDemo(stop);
  final b = StringBuffer();

  if (ayah != null) {
    b.writeln(
      formatAyahMarkedForStop(
        ayah,
        stop: stop,
        demo: demo,
        surahName: surahName,
      ),
    );
    b.writeln('🔖 *موضع الوقف*: ﴿${stop.word}﴾');
  } else {
    b.writeln(_stopHeader(stop, surahName));
  }

  switch (mode) {
    case StopShareMode.opinions:
      _writeOpinionsSection(b, stop);
    case StopShareMode.meanings:
      _writeMeaningsSection(
        b,
        stop,
        mainDemo: demo,
        includeBookRef: true,
        showEmptyNotice: true,
      );
    case StopShareMode.all:
      _writeOpinionsSection(b, stop);
      _writeMeaningsSection(
        b,
        stop,
        mainDemo: demo,
        includeBookRef: false,
        showEmptyNotice: false,
      );
  }

  return b.toString().trimRight();
}

/// Full ayah with *bold* stop/highlight words.
/// When meaning spans exist: `*[…]*` around each waqf/ibtida bracket span.
String formatAyahMarkedForStop(
  Ayah ayah, {
  required WaqfStop stop,
  WaqfDemoAndMeaning? demo,
  String? surahName,
}) {
  final hasWaqf = _spanValid(demo?.waqfSegmentWords);
  final hasIbtida = _spanValid(demo?.ibtidaSegmentWords);
  final useSpans = hasWaqf || hasIbtida;

  final parts = <String>[];
  var spanDepth = 0;
  for (var i = 0; i < ayah.words.length; i++) {
    final w = ayah.words[i];
    final idx = w.index > 0 ? w.index : i + 1;
    final isStop = w.stopId == stop.id || idx == stop.wordIndex;

    var openCount = 0;
    var closeCount = 0;
    if (useSpans) {
      if (hasWaqf && _isSpanStart(demo!.waqfSegmentWords, idx)) openCount++;
      if (hasIbtida && _isSpanStart(demo!.ibtidaSegmentWords, idx)) {
        openCount++;
      }
      if (hasWaqf && _isSpanEnd(demo!.waqfSegmentWords, idx)) closeCount++;
      if (hasIbtida && _isSpanEnd(demo!.ibtidaSegmentWords, idx)) closeCount++;
    }

    final open = StringBuffer();
    if (openCount > 0) {
      if (spanDepth == 0) {
        // Place one bold marker pair outside the `[]` span (`*[…]*`).
        open.write('*');
      }
      open.write('[' * openCount);
      spanDepth += openCount;
    }

    var text = w.text;
    if (isStop && spanDepth == 0) {
      text = '*$text*';
    }

    final close = StringBuffer();
    if (closeCount > 0) {
      spanDepth = (spanDepth - closeCount).clamp(0, 100);
      close.write(']' * closeCount);
      if (spanDepth == 0) {
        close.write('*');
      }
    }

    parts.add('$open$text$close');
  }

  final sName = (surahName == null || surahName.isEmpty) ? 'السورة' : surahName;
  return '﴿ ${parts.join(' ')} ﴾\n[$sName: آية ${arabicDigits(ayah.number)}]';
}

/// Formats clean Quran text for an Ayah:
/// ﴿...﴾ [سورة النساء: 1]
String formatAyahText(Ayah ayah, {required String surahName}) {
  final text = ayah.words.map((w) => w.text).join(' ');
  final sName = surahName.isEmpty ? 'السورة' : surahName;
  return '﴿$text﴾\n[$sName: آية ${arabicDigits(ayah.number)}]';
}

/// Formats Ayah text along with all waqf stops and scholar rulings.
String formatAyahWithStopsText(
  Ayah ayah,
  ReaderController controller, {
  required String surahName,
}) {
  final b = StringBuffer()..writeln(formatAyahText(ayah, surahName: surahName));
  final stopIds = ayah.words
      .map((w) => w.stopId)
      .whereType<String>()
      .toSet()
      .toList();

  if (stopIds.isNotEmpty) {
    b.writeln('\n--- وقوف الآية ---');
    for (final id in stopIds) {
      final stop = controller.stopById(id);
      if (stop != null) {
        b
          ..writeln()
          ..writeln(formatStopText(stop, surahName: surahName));
      }
    }
  }
  return b.toString().trimRight();
}

Ayah? ayahForStop(ReaderController controller, WaqfStop stop) {
  for (final a in controller.currentAyahs) {
    if (a.number == stop.ayah) return a;
  }
  return null;
}

WaqfDemoAndMeaning? shareHighlightDemo(
  ReaderController controller,
  WaqfStop stop,
) {
  if (controller.selectedStopId == stop.id) {
    final active = controller.activeDemoHighlight;
    if (active != null) return active;
  }
  return _firstDemoWithSpans(stop) ?? _firstDemo(stop);
}

void _writeOpinionsSection(StringBuffer b, WaqfStop stop) {
  b
    ..writeln()
    ..writeln(_sectionDivider)
    ..writeln('📜 *آراء العلماء*');
  for (final op in stop.opinions) {
    b.writeln();
    _writeOpinionEntry(b, stop, op);
  }
}

void _writeMeaningsSection(
  StringBuffer b,
  WaqfStop stop, {
  WaqfDemoAndMeaning? mainDemo,
  required bool includeBookRef,
  required bool showEmptyNotice,
}) {
  final withDemos =
      stop.opinions.where((op) => op.demosAndMeanings.isNotEmpty).toList();
  if (withDemos.isEmpty) {
    if (!showEmptyNotice) return;
    b
      ..writeln()
      ..writeln(_sectionDivider)
      ..writeln('✨ *بيان الوقف والابتداء والمعاني*')
      ..writeln()
      ..writeln('لا معاني مسجّلة لهذا الوقف.');
    return;
  }

  b
    ..writeln()
    ..writeln(_sectionDivider)
    ..writeln('✨ *بيان الوقف والابتداء والمعاني*');

  if (mainDemo != null) {
    final mWaqf = mainDemo.meaningAtWaqf.trim();
    final mIbtida = mainDemo.meaningAtIbtida.trim();
    if (mWaqf.isNotEmpty || mIbtida.isNotEmpty) {
      b
        ..writeln()
        ..writeln('💡 *المعنى الأساسي (وقف وابتداء)*:');
      if (mWaqf.isNotEmpty) {
        b.writeln('  🔹 *المعنى عند الوقف*: $mWaqf');
      }
      if (mIbtida.isNotEmpty) {
        b.writeln('  🔸 *المعنى عند الابتداء*: $mIbtida');
      }
    }
  }

  b
    ..writeln()
    ..writeln('📑 *تفصيل العلماء*:');
  for (final op in withDemos) {
    for (final demo in op.demosAndMeanings) {
      b.writeln();
      final details = _demoHeaderDetails(demo);
      if (includeBookRef) {
        final ref = _bookRef(op);
        b.writeln('📖 [$ref] · *${op.scholar}* — $details');
      } else {
        b.writeln('🏷️ *${op.scholar}* — $details');
      }
      _writeDemoBodyLines(b, demo);
    }
  }
}

void _writeOpinionEntry(StringBuffer b, WaqfStop stop, ScholarOpinion op) {
  final ref = _bookRef(op);
  final faces = <String>[];
  for (var i = 0; i < op.verdicts.length; i++) {
    final v = op.verdicts[i];
    final q = i < op.isQila.length && op.isQila[i];
    final sym = i < op.symbols.length ? op.symbols[i] : op.primarySymbol;
    final label = q && !v.contains('قيل') ? 'قيل: $v' : v;
    faces.add('${_symbolIcon(sym)} *$label*');
  }
  final header = faces.isEmpty
      ? '📖 [$ref] · *${op.scholar}*'
      : '📖 [$ref] · *${op.scholar}* — ${faces.join(' / ')}';
  b.writeln(header);

  final tw = op.targetWord.trim();
  if (tw.isNotEmpty && !_sameArabicWord(stop.word, tw)) {
    b.writeln('📍 *موضع الوقف عنده*: «$tw»');
  }

  final c = op.comment?.trim();
  if (c != null && c.isNotEmpty) {
    b.writeln('💬 *رأي ${op.scholar}*: $c');
  }
}

String _demoHeaderDetails(WaqfDemoAndMeaning demo) {
  final verdictTag = (demo.isQila && !demo.verdict.contains('قيل'))
      ? 'قيل: ${demo.verdict}'
      : demo.verdict;
  final attr = demo.attributedTo?.trim();
  return (attr != null && attr.isNotEmpty)
      ? '*$verdictTag* — $attr'
      : '*$verdictTag*';
}

void _writeDemoBodyLines(StringBuffer b, WaqfDemoAndMeaning demo) {
  final wDemo = demo.waqfDemo.trim().replaceFirst(_leadingWaqfRecitePrefix, '');
  if (wDemo.isNotEmpty) {
    b.writeln('  ⏸️ *تلاوة الوقف*: $wDemo');
  }
  final iDemo =
      demo.ibtidaDemo.trim().replaceFirst(_leadingIbtidaRecitePrefix, '');
  if (iDemo.isNotEmpty) {
    b.writeln('  ▶️ *تلاوة الابتداء*: $iDemo');
  }
  final mWaqf = demo.meaningAtWaqf.trim();
  if (mWaqf.isNotEmpty) {
    b.writeln('  🔹 *المعنى عند الوقف*: $mWaqf');
  }
  final mIbtida = demo.meaningAtIbtida.trim();
  if (mIbtida.isNotEmpty) {
    b.writeln('  🔸 *المعنى عند الابتداء*: $mIbtida');
  }
  final mConn = demo.meaningIfConnected.trim();
  if (mConn.isNotEmpty) {
    b.writeln('  🔗 *المعنى عند الوصل*: $mConn');
  }
}

String _bookRef(ScholarOpinion op) {
  final book = op.book.trim();
  final page = op.page?.trim();
  if (page == null || page.isEmpty) return book;
  return '$book: $page';
}

String _symbolIcon(StopSymbol symbol) {
  switch (symbol) {
    case StopSymbol.tam:
      return '🟢';
    case StopSymbol.jaiz:
      return '🔵';
    case StopSymbol.mujawwaz:
      return '🟡';
    case StopSymbol.la:
      return '🔴';
    case StopSymbol.unsettled:
      return '⚖️';
  }
}

bool _sameArabicWord(String a, String b) =>
    _normalizeArabicWord(a) == _normalizeArabicWord(b);

String _normalizeArabicWord(String input) {
  var s = input.trim();
  s = s.replaceAll('و\u0670', 'ا').replaceAll('\u0640\u0670', 'ا').replaceAll('\u0670', 'ا');
  s = _arabicMarksPattern.allMatches(s).isEmpty
      ? s
      : s.replaceAll(_arabicMarksPattern, '');
  s = s
      .replaceAll('ٱ', 'ا')
      .replaceAll('أ', 'ا')
      .replaceAll('إ', 'ا')
      .replaceAll('آ', 'ا')
      .replaceAll('ى', 'ي');
  return s;
}

String _stopHeader(WaqfStop stop, String? surahName) {
  final sName = (surahName == null || surahName.isEmpty)
      ? 'سورة ${arabicDigits(stop.surah)}'
      : surahName;
  return '🕌 ﴿ *${stop.word}* ﴾ — $sName، الآية ${arabicDigits(stop.ayah)}';
}

bool _spanValid(List<int>? span) => span != null && span.length >= 2;

bool _isSpanStart(List<int>? span, int wordIndex) {
  if (!_spanValid(span)) return false;
  final a = span![0];
  final b = span[1];
  return wordIndex == (a <= b ? a : b);
}

bool _isSpanEnd(List<int>? span, int wordIndex) {
  if (!_spanValid(span)) return false;
  final a = span![0];
  final b = span[1];
  return wordIndex == (a <= b ? b : a);
}

WaqfDemoAndMeaning? _firstDemoWithSpans(WaqfStop stop) {
  for (final op in stop.opinions) {
    for (final d in op.demosAndMeanings) {
      if (_spanValid(d.waqfSegmentWords) || _spanValid(d.ibtidaSegmentWords)) {
        return d;
      }
    }
  }
  return null;
}

WaqfDemoAndMeaning? _firstDemo(WaqfStop stop) {
  for (final op in stop.opinions) {
    if (op.demosAndMeanings.isNotEmpty) return op.demosAndMeanings.first;
  }
  return null;
}

Future<void> copyText(BuildContext context, String text, {String message = 'تم النسخ'}) async {
  await Clipboard.setData(ClipboardData(text: text));
  if (!context.mounted) return;
  ScaffoldMessenger.maybeOf(context)?.showSnackBar(
    SnackBar(
      behavior: SnackBarBehavior.floating,
      duration: const Duration(seconds: 2),
      content: Text(
        message,
        style: AppText.ui(size: 14, color: AppColors.white),
      ),
    ),
  );
}

Future<void> shareText(BuildContext context, String text, {String? subject}) async {
  final box = context.findRenderObject() as RenderBox?;
  final origin =
      box == null ? null : (box.localToGlobal(Offset.zero) & box.size);
  await Share.share(
    text,
    subject: subject,
    sharePositionOrigin: origin,
  );
}
