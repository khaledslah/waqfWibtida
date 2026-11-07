import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';

/// Formats text for one scholar's opinion on a stop.
String formatOpinionText(
  WaqfStop stop,
  ScholarOpinion op, {
  String? surahName,
  bool includeHeader = true,
}) {
  final b = StringBuffer();
  if (includeHeader) {
    b.writeln(_stopHeader(stop, surahName));
  }
  final faces = <String>[];
  for (var i = 0; i < op.verdicts.length; i++) {
    final v = op.verdicts[i];
    final q = i < op.isQila.length && op.isQila[i];
    faces.add(q && !v.contains('قيل') ? 'قيل: $v' : v);
  }
  b.writeln('${op.scholar}: ${faces.join(' / ')}');
  if (op.targetWord.trim().isNotEmpty) {
    b.writeln('موضع الوقف عنده: «${op.targetWord}»');
  }
  final c = op.comment?.trim();
  if (c != null && c.isNotEmpty) {
    b.writeln(c);
  }
  final ref = op.page == null ? op.book : '${op.book}: ${op.page}';
  b.write('[$ref]');
  return b.toString();
}

/// Formats text for a stop including all scholars' opinions.
String formatStopText(WaqfStop stop, {String? surahName}) {
  final b = StringBuffer()..writeln(_stopHeader(stop, surahName));
  for (final op in stop.opinions) {
    b
      ..writeln()
      ..writeln(formatOpinionText(stop, op, includeHeader: false));
  }
  return b.toString().trimRight();
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

String _stopHeader(WaqfStop stop, String? surahName) {
  final sName = (surahName == null || surahName.isEmpty)
      ? 'سورة ${arabicDigits(stop.surah)}'
      : surahName;
  return '﴿${stop.word}﴾ — $sName، الآية ${arabicDigits(stop.ayah)}';
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
