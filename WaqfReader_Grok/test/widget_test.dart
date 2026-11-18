import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:waqf_reader_grok/data/sample_data.dart';
import 'package:waqf_reader_grok/main.dart';
import 'package:waqf_reader_grok/models/waqf_models.dart';

Future<void> _pumpUntilReady(WidgetTester tester) async {
  await tester.pumpWidget(const WaqfReaderApp());
  await tester.pump();
  for (var i = 0; i < 100; i++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    await tester.pump(const Duration(milliseconds: 50));
    if (find.textContaining('وقف المصحف').evaluate().isNotEmpty) {
      await tester.pump();
      return;
    }
  }
  fail('App did not leave loading state');
}

void main() {
  setUpAll(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  testWidgets('Full catalog: Fatiha loads and index lists 114 surahs',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await _pumpUntilReady(tester);

    expect(find.text('وقف وابتداء'), findsOneWidget);
    expect(find.text('الفاتحة'), findsWidgets);
    expect(find.textContaining('وقف المصحف'), findsOneWidget);
    expect(find.byTooltip('اختيار العالم الرئيسي'), findsOneWidget);

    await tester.tap(find.byTooltip('عرض وقوف الفاتحة'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.textContaining('١١٤ سورة'), findsOneWidget);
    expect(find.text('سورة البقرة'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('سورة الناس'),
      400,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('سورة الناس'), findsOneWidget);
  });

  testWidgets('Surah 66 multi-opinion parallel arrays, isQila, and S66:6 recovery',
      (tester) async {
    final bundle = await tester.runAsync(
      () => AppFeedBundle.loadAsset('app_feed/surah_066.json'),
    );
    expect(bundle, isNotNull);

    // Verify S66:4-5 mid-line prose recovery (ظهير -> منكن) and وأبكارا multi-face
    final s66a4w21 = bundle!.stops.firstWhere((s) => s.id == 's66-a4-w21');
    expect(s66a4w21.opinionForScholar('الأشموني')!.comment, 'ظهير كاف.');

    final s66a5w9 = bundle.stops.firstWhere((s) => s.id == 's66-a5-w9');
    final ashmMinkun = s66a5w9.opinionForScholar('الأشموني')!;
    expect(ashmMinkun.verdicts, ['لا يوقف']);
    expect(ashmMinkun.verdictLabels, ['لا']);
    expect(ashmMinkun.comment, contains('فلا يوقف على منكن'));

    final s66a5w17 = bundle.stops.firstWhere((s) => s.id == 's66-a5-w17');
    final daniAbkar = s66a5w17.opinionForScholar('الداني')!;
    expect(daniAbkar.verdicts, ['كاف', 'تام']);
    expect(daniAbkar.verdictLabels, ['ج', 'ط']);
    expect(daniAbkar.isQila, [false, true]);

    // Verify S66:6 recovered Ashmuni prose verb rulings on وأهليكم and نارا
    final s66a6w6 = bundle.stops.firstWhere((s) => s.id == 's66-a6-w6');
    expect(s66a6w6.hasScholar('الأشموني'), isTrue);
    expect(s66a6w6.verdictLabelForScholar('الأشموني'), 'ج');
    expect(s66a6w6.symbolForScholar('الأشموني'), StopSymbol.jaiz);
    expect(s66a6w6.isQilaForScholar('الأشموني'), isTrue);

    final s66a6w7 = bundle.stops.firstWhere((s) => s.id == 's66-a6-w7');
    expect(s66a6w7.hasScholar('الأشموني'), isTrue);
    expect(s66a6w7.verdictLabelForScholar('الأشموني'), 'ج');

    // Verify S66:8 w28 (معه) multi-opinion parallel arrays and qila flags
    final s66a8w28 = bundle.stops.firstWhere((s) => s.id == 's66-a8-w28');
    final saj = s66a8w28.opinionForScholar('السجاوندي')!;
    expect(saj.verdicts, ['جائز', 'لا يوقف']);
    expect(saj.verdictLabels, ['ج', 'لا']);
    expect(saj.isQila, [false, true]);

    final dani = s66a8w28.opinionForScholar('الداني')!;
    expect(dani.verdicts, ['تام']);
    expect(dani.verdictLabels, ['ط']);
    expect(dani.isQila, [false]);
    expect(s66a8w28.verdictLabelForScholar('الداني'), 'ط');
    expect(s66a8w28.isQilaForScholar('الداني'), isFalse);

    final ashm = s66a8w28.opinionForScholar('الأشموني')!;
    expect(ashm.verdicts, ['تام', 'لا يوقف']);
    expect(ashm.verdictLabels, ['ط', 'لا']);
    expect(ashm.isQila, [false, true]);
  });

  testWidgets('Surah 4 Ayah 1 complete coverage across all 4 scholars',
      (tester) async {
    final bundle = await tester.runAsync(
      () => AppFeedBundle.loadAsset('app_feed/surah_004.json'),
    );
    expect(bundle, isNotNull);

    // 1. من نفس واحدة (s4-a1-w9): الأشموني لا يوقف
    final s4a1w9 = bundle!.stops.firstWhere((s) => s.id == 's4-a1-w9');
    expect(s4a1w9.opinionForScholar('الأشموني')!.verdicts, ['لا يوقف']);

    // 2. كثيرًا (s4-a1-w16): الأشموني لا يوقف (ومثله)
    final s4a1w16 = bundle.stops.firstWhere((s) => s.id == 's4-a1-w16');
    expect(s4a1w16.opinionForScholar('الأشموني')!.verdicts, ['لا يوقف']);

    // 3. ونساء (s4-a1-w17): 4 scholars
    final s4a1w17 = bundle.stops.firstWhere((s) => s.id == 's4-a1-w17');
    expect(s4a1w17.opinionForScholar('السجاوندي')!.verdicts, ['جائز']);
    expect(s4a1w17.opinionForScholar('ابن الأنباري')!.verdicts, ['حسن']);
    expect(s4a1w17.opinionForScholar('الداني')!.verdicts, ['تام', 'كاف']);
    expect(s4a1w17.opinionForScholar('الأشموني')!.verdicts, ['تام']);

    // 4. به (s4-a1-w22): current grounded feed opinions
    final s4a1w22 = bundle.stops.firstWhere((s) => s.id == 's4-a1-w22');
    expect(s4a1w22.opinionForScholar('السجاوندي')!.verdicts, ['قيل فيه وقف']);
    expect(s4a1w22.opinionForScholar('ابن الأنباري')!.verdicts, ['لا يوقف']);
    expect(s4a1w22.opinionForScholar('الداني')!.verdicts, ['لا يوقف', 'تام']);
    final ashmBihi = s4a1w22.opinionForScholar('الأشموني')!;
    expect(ashmBihi.verdicts, ['لا يوقف', 'قيل فيه وقف', 'كاف', 'تام']);

    // 5. والأرحام (s4-a1-w23): الأشموني كاف / حسن / لا يوقف (without leaking تام from به)
    final s4a1w23 = bundle.stops.firstWhere((s) => s.id == 's4-a1-w23');
    final ashmArham = s4a1w23.opinionForScholar('الأشموني')!;
    expect(ashmArham.verdicts, ['كاف', 'حسن', 'لا يوقف']);
    expect(ashmArham.isQila, [false, true, true]);
  });
}
