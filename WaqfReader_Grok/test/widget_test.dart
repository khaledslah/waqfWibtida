import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:waqf_reader_grok/main.dart';

Future<void> _pumpUntilReady(WidgetTester tester) async {
  await tester.pumpWidget(const WaqfReaderApp());
  await tester.pump();
  for (var i = 0; i < 100; i++) {
    if (find.text('إخفاء رؤوس الآي').evaluate().isNotEmpty) {
      await tester.pump();
      return;
    }
    await tester.pump(const Duration(milliseconds: 50));
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
    expect(find.text('سورة الفاتحة'), findsWidgets);
    expect(find.text('إخفاء رؤوس الآي'), findsOneWidget);

    await tester.tap(find.text('فهرس'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.textContaining('١١٤ سورة'), findsOneWidget);
    expect(find.text('سورة البقرة'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('سورة الناس'),
      400,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('سورة الناس'), findsOneWidget);
  });
}
