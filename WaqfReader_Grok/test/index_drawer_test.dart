import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:waqf_reader_grok/main.dart';
import 'package:waqf_reader_grok/screens/index_screen.dart';

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

  testWidgets(
      'IndexDrawer opens as sidebar and closes automatically when a Surah is selected',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await _pumpUntilReady(tester);

    // Initial state: Mushaf screen showing Al-Fatiha
    expect(find.text('سورة الفاتحة'), findsWidgets);
    expect(find.byType(IndexDrawer), findsNothing);

    // 1. Open sidebar via top bar Surah chip
    await tester.tap(find.byTooltip('فتح فهرس السور'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    // Verify sidebar drawer is now open
    expect(find.byType(IndexDrawer), findsOneWidget);
    expect(find.text('الفهرس'), findsOneWidget);
    expect(find.text('سورة البقرة'), findsOneWidget);

    // 2. Select a surah (e.g. سورة البقرة)
    await tester.tap(find.text('سورة البقرة'));
    await tester.pump();
    // Allow async surah load and drawer close animation
    for (var i = 0; i < 20; i++) {
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 20)),
      );
      await tester.pump(const Duration(milliseconds: 50));
    }

    // 3. Verify sidebar drawer is closed
    expect(find.byType(IndexDrawer), findsNothing);

    // 4. Verify the chosen Surah is now active in the Mushaf screen
    expect(find.text('سورة البقرة'), findsWidgets);

    // 5. Open sidebar again via bottom nav 'فهرس'
    await tester.tap(find.text('فهرس'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byType(IndexDrawer), findsOneWidget);

    // Test search filter in drawer
    await tester.enterText(find.byType(TextField), 'النساء');
    await tester.pump();

    expect(find.descendant(of: find.byType(IndexDrawer), matching: find.text('سورة النساء')), findsOneWidget);
    expect(find.descendant(of: find.byType(IndexDrawer), matching: find.text('سورة البقرة')), findsNothing);

    // Close via 'X' button
    await tester.tap(find.byTooltip('إغلاق الفهرس'));
    await tester.pumpAndSettle();

    expect(find.byType(IndexDrawer), findsNothing);
  });
}
