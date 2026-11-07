import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:waqf_reader_grok/main.dart';

Future<void> _pumpUntilReady(WidgetTester tester) async {
  await tester.pumpWidget(const WaqfReaderApp());
  await tester.pump();
  for (var i = 0; i < 100; i++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    await tester.pump(const Duration(milliseconds: 50));
    if (find.text('إخفاء رؤوس الآي').evaluate().isNotEmpty) {
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

  testWidgets('Long pressing Ayah word or tapping Ayah mark opens AyahOptionsSheet',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await _pumpUntilReady(tester);

    // Verify Surah Al-Fatiha is rendered
    expect(find.text('بِسْمِ'), findsOneWidget);

    // Tap on Ayah mark 1 (e.g. verse 1 or 2)
    final ayahMark = find.bySemanticsLabel(RegExp(r'خيارات الآية'));
    expect(ayahMark, findsWidgets);

    // Tap the first Ayah badge
    await tester.tap(ayahMark.first);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    // Verify Ayah options sheet is open
    expect(find.text('نسخ الآية'), findsOneWidget);
    expect(find.text('مشاركة الآية'), findsOneWidget);
    expect(find.text('نسخ مع الوقوف'), findsOneWidget);
    expect(find.text('مشاركة مع الوقوف'), findsOneWidget);

    // Close the sheet
    await tester.tap(find.byTooltip('إغلاق'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('نسخ الآية'), findsNothing);

    // Now test long-press on a word in the Ayah
    final wordWidget = find.text('بِسْمِ');
    await tester.longPress(wordWidget);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    // Verify Ayah options sheet opened again
    expect(find.text('نسخ الآية'), findsOneWidget);
  });
}
