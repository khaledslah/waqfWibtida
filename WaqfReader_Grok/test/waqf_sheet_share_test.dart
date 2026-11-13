import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:waqf_reader_grok/main.dart';
import 'package:waqf_reader_grok/widgets/waqf_bottom_sheet.dart';

Future<void> _pumpUntilReady(WidgetTester tester) async {
  await tester.pumpWidget(const WaqfReaderApp());
  await tester.pump();
  for (var i = 0; i < 100; i++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    await tester.pump(const Duration(milliseconds: 50));
    if (find.textContaining('رؤوس الآي').evaluate().isNotEmpty) {
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
      'WaqfBottomSheet has report flag on top, no bottom approve button, and review page keeps verify button',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await _pumpUntilReady(tester);

    // Full WaqfBottomSheet opens from ayah options → stop (badge opens dock)
    final ayahMark = find.bySemanticsLabel(RegExp(r'خيارات الآية'));
    expect(ayahMark, findsWidgets);
    await tester.tap(ayahMark.first);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.byType(ListTile).first);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    // Verify SelectionArea exists in the sheet
    expect(find.byType(SelectionArea), findsWidgets);

    // Verify per-opinion "نسخ" and "مشاركة" buttons exist
    expect(find.text('نسخ'), findsWidgets);
    expect(find.text('مشاركة'), findsWidgets);

    // Verify stop share menu button exists
    final shareMenuBtn = find.byTooltip('خيارات الوقف (نسخ ومشاركة)');
    expect(shareMenuBtn, findsOneWidget);

    // Verify report flag button is on top, and verify button is NOT on WaqfBottomSheet
    final reportFlagBtn = find.byTooltip('إبلاغ / إضافة للمراجعة');
    expect(reportFlagBtn, findsOneWidget);
    expect(find.byTooltip('تحقّق'), findsNothing);

    // Bottom approve button is removed
    expect(find.text('موافق للمراجعة'), findsNothing);
    expect(find.text('في قائمة المراجعة'), findsNothing);

    // Tap report flag to add to review
    await tester.tap(reportFlagBtn);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byTooltip('في قائمة المراجعة (انقر للإلغاء)'), findsOneWidget);

    // Close WaqfBottomSheet cleanly
    Navigator.of(tester.element(find.byType(WaqfBottomSheet))).pop();
    await tester.pumpAndSettle();

    // Navigate to Review Screen
    await tester.tap(find.text('مراجعة'));
    await tester.pumpAndSettle();

    // Verify that the verify button is kept on the review page
    expect(find.byTooltip('تحقّق'), findsWidgets);
  });
}
