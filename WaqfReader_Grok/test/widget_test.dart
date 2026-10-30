import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:waqf_reader_grok/main.dart';
import 'package:waqf_reader_grok/widgets/waqf_bottom_sheet.dart';

void main() {
  setUpAll(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  testWidgets('Mushaf, index, review, and stop sheet', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const WaqfReaderApp());
    await tester.pump();

    expect(find.text('وقف وابتداء'), findsOneWidget);
    expect(find.text('سورة يوسف'), findsOneWidget);
    expect(find.text('مصحف'), findsOneWidget);
    expect(find.text('فهرس'), findsOneWidget);
    expect(find.text('مراجعة'), findsOneWidget);

    await tester.ensureVisible(
      find.byKey(const ValueKey<String>('stop-yusuf-100-haqqa')),
    );
    await tester.tap(find.byKey(const ValueKey<String>('stop-yusuf-100-haqqa')));
    await tester.pumpAndSettle();

    expect(find.text('موافق للمراجعة'), findsOneWidget);
    expect(find.text('آراء العلماء'), findsOneWidget);
    expect(find.text('النحاس'), findsOneWidget);
    expect(find.text('مقترحات AI'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('مقترحات AI'),
      120,
      scrollable: find.descendant(
        of: find.byType(WaqfBottomSheet),
        matching: find.byType(Scrollable),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('مقترحات AI'));
    await tester.pumpAndSettle();
    expect(find.textContaining('اعتماد الوقف'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, 'موافق للمراجعة'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    await tester.tap(find.text('فهرس'));
    await tester.pumpAndSettle();
    expect(find.text('سورة الكهف'), findsOneWidget);
    expect(find.text('سورة مريم'), findsOneWidget);
    expect(find.text('لم تبدأ'), findsOneWidget);
    expect(find.text('بانتظار المراجعة'), findsOneWidget);

    await tester.tap(find.text('مراجعة'));
    await tester.pumpAndSettle();
    expect(find.text('كُذِبُوا'), findsWidgets);
    expect(find.text('أُرسلت للمراجعة'), findsOneWidget);
    expect(find.text('مقترح AI'), findsWidgets);
  });
}
