import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:waqf_reader_grok/data/sample_data.dart';
import 'package:waqf_reader_grok/models/waqf_models.dart';
import 'package:waqf_reader_grok/screens/mushaf_screen.dart';
import 'package:waqf_reader_grok/widgets/stop_detail_dock.dart';

void main() {
  setUpAll(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  testWidgets(
      'Surah 74: الكل swipes through distinct-span demos, dots, and ghost previews',
      (tester) async {
    final controller = ReaderController();
    addTearDown(controller.dispose);
    await tester.runAsync(() => controller.bootstrap(initialSurah: 74));
    expect(controller.loadState, ReaderLoadState.ready);
    // Swipe-to-next-stop walks visible stops; make sure all are visible.
    controller.showAllStops();
    controller.setSelectedScholar(null);

    final stop = controller.stopById('s74-a53-w1')!;
    final groups = controller.stopDemoGroupsFor(stop);
    expect(groups.length, 2);
    // Cross-ayah demo is prioritized first when multiple demos exist.
    expect(groups[0].scholars, ['الداني', 'الأشموني', 'النحاس']);
    expect(groups[0].demo.spansOtherAyahs(stop.ayah), isTrue);
    expect(groups[0].demo.ayahExtent(stop.ayah), (52, 53));
    expect(groups[1].scholars, ['السجاوندي', 'ابن الأنباري']);

    // A single-scholar filter returns only that scholar's demos.
    controller.setSelectedScholar('الداني');
    final daniOnly = controller.stopDemoGroupsFor(stop);
    expect(daniOnly.length, 1);
    expect(daniOnly.single.scholar, 'الداني');
    controller.setSelectedScholar(null);

    // Open dock on s74-a53-w1 in المعاني tab -> starts on group 0 (cross-ayah).
    controller.openStopDock('s74-a53-w1', tab: 0);
    expect(controller.activeStopDemoGroupIndex(stop), 0);
    expect(
      controller.demoRoleForWord(ayahNumber: 52, wordIndex: 2),
      DemoSegmentRole.waqf,
    );
    expect(
      controller.demoRoleForWord(ayahNumber: 53, wordIndex: 1),
      DemoSegmentRole.waqf,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Directionality(
          textDirection: TextDirection.rtl,
          child: Scaffold(
            body: AnimatedBuilder(
              animation: controller,
              builder: (context, _) => Align(
                alignment: Alignment.bottomCenter,
                child: StopDetailDock(controller: controller),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Counter + label for the active variant (group 0: cross-ayah).
    expect(find.text('١ / ٢'), findsOneWidget);
    // Variant name appears once (in the tab row), not repeated in the header.
    expect(find.textContaining('الداني +٢'), findsOneWidget);
    expect(find.text('آية ٥٢–٥٣'), findsOneWidget);
    // Ayah 52 is actively highlighted, so it is not ghosted.
    expect(controller.ghostDemoForWord(ayahNumber: 52, wordIndex: 2), isNull);

    // Step forward -> single-ayah variant becomes active; at end it stops (no wrap).
    expect(controller.swipeStopVariant('s74-a53-w1', 1), isTrue);
    expect(controller.swipeStopVariant('s74-a53-w1', 1), isFalse);
    await tester.pumpAndSettle();
    expect(find.text('٢ / ٢'), findsOneWidget);
    expect(find.textContaining('السجاوندي، ابن الأنباري'), findsOneWidget);
    expect(controller.activeStopDemoGroupIndex(stop), 1);
    expect(
      controller.demoRoleForWord(ayahNumber: 52, wordIndex: 2),
      DemoSegmentRole.none,
    );
    // Ghost preview: group 0 reaches into Ayah 52 while group 1 is active.
    final ghost = controller.ghostDemoForWord(ayahNumber: 52, wordIndex: 2);
    expect(ghost, isNotNull);
    expect(ghost!.role, DemoSegmentRole.waqf);
    expect(ghost.group.scholars, ['الداني', 'الأشموني', 'النحاس']);

    // Switching dock tabs preserves the selected scholar/span.
    controller.setStopDockTab(1);
    await tester.pump();
    controller.setStopDockTab(0);
    await tester.pump();
    expect(controller.selectedDemoScholar, 'السجاوندي');
    expect(
      controller.demoRoleForWord(ayahNumber: 52, wordIndex: 2),
      DemoSegmentRole.none,
    );

    // Swipe back (previous) walks back to group 0 (cross-ayah), then stops at index 0.
    expect(controller.stepDemoOrStop(-1), isTrue);
    expect(controller.selectedStopId, 's74-a53-w1');
    expect(controller.activeStopDemoGroupIndex(stop), 0);
    expect(controller.stepStopDemo(-1), isFalse);
    expect(
      controller.demoRoleForWord(ayahNumber: 52, wordIndex: 2),
      DemoSegmentRole.waqf,
    );

    // Swipe next twice: first to variant 2, then on to the next visible stop.
    expect(controller.stepDemoOrStop(1), isTrue);
    expect(controller.activeStopDemoGroupIndex(stop), 1);
    expect(controller.stepDemoOrStop(1), isTrue);
    expect(controller.selectedStopId, isNot('s74-a53-w1'));

    // Swiping back onto a multi-variant stop lands on its LAST variant.
    expect(controller.stepDemoOrStop(-1), isTrue);
    expect(controller.selectedStopId, 's74-a53-w1');
    expect(controller.activeStopDemoGroupIndex(stop), 1);
  });

  testWidgets('Mushaf: dots over multi-variant symbol; swiping the page cycles demos',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final controller = ReaderController();
    addTearDown(controller.dispose);
    await tester.runAsync(() => controller.bootstrap(initialSurah: 74));
    controller.showAllStops();
    controller.setSelectedScholar(null);

    await tester.pumpWidget(
      MaterialApp(
        home: Directionality(
          textDirection: TextDirection.rtl,
          child: Scaffold(
            body: ListenableBuilder(
              listenable: controller,
              builder: (context, _) => MushafScreen(controller: controller),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final symbol =
        find.byKey(const ValueKey<String>('stop-variants-s74-a53-w1'));
    await tester.scrollUntilVisible(
      symbol,
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(
      find.descendant(
        of: symbol,
        matching: find.byKey(const ValueKey<String>('variant-dots')),
      ),
      findsOneWidget,
    );

    final page = find.byKey(const ValueKey<String>('mushaf-swipe-area'));
    final stop = controller.stopById('s74-a53-w1')!;

    // Dock closed: page swipe does nothing.
    await tester.fling(page, const Offset(160, 0), 800);
    await tester.pumpAndSettle();
    expect(controller.stopDockOpen, isFalse);

    // Open the stop in المعاني -> variant 1 (cross-ayah first), then swipe to variant 2.
    controller.openStopDock('s74-a53-w1', tab: 0);
    await tester.pumpAndSettle();
    expect(controller.activeStopDemoGroupIndex(stop), 0);
    expect(
      controller.demoRoleForWord(ayahNumber: 52, wordIndex: 2),
      DemoSegmentRole.waqf,
    );
    await tester.fling(page, const Offset(160, 0), 800);
    await tester.pumpAndSettle();
    expect(controller.selectedStopId, 's74-a53-w1');
    expect(controller.activeStopDemoGroupIndex(stop), 1);
    expect(
      controller.demoRoleForWord(ayahNumber: 52, wordIndex: 2),
      DemoSegmentRole.none,
    );

    // Swiping forward past the last variant does not wrap around.
    await tester.fling(page, const Offset(160, 0), 800);
    await tester.pumpAndSettle();
    expect(controller.activeStopDemoGroupIndex(stop), 1);

    // Swipe the other way -> back to variant 1, and stops there cleanly.
    await tester.fling(page, const Offset(-160, 0), 800);
    await tester.pumpAndSettle();
    expect(controller.activeStopDemoGroupIndex(stop), 0);
    await tester.fling(page, const Offset(-160, 0), 800);
    await tester.pumpAndSettle();
    expect(controller.activeStopDemoGroupIndex(stop), 0);

    // s74-a16-w1 has 2 distinct-span variants and differsFromUthmani == true.
    final a16 = controller.stopById('s74-a16-w1')!;
    expect(controller.stopDemoGroupsFor(a16).length, 2);
    expect(a16.differsFromUthmani, isTrue);

    // Single-variant stop: page swipe is a no-op (stays on the same stop).
    controller.openStopDock('s74-a31-w6', tab: 0);
    await tester.pumpAndSettle();
    expect(
      controller.stopDemoGroupsFor(controller.stopById('s74-a31-w6')!).length,
      1,
    );
    await tester.fling(page, const Offset(160, 0), 800);
    await tester.pumpAndSettle();
    expect(controller.selectedStopId, 's74-a31-w6');
  });

  test('الكل selects highest stop degree across opinions and breaks ties against qila',
      () {
    const stop = WaqfStop(
      id: 's1-a1-w1',
      surah: 1,
      ayah: 1,
      word: 'كلمة',
      opinions: [
        ScholarOpinion(
          scholar: 'السجاوندي',
          targetWord: 'كلمة',
          verdicts: ['لا يوقف'],
          verdictLabels: ['لا'],
          symbols: [StopSymbol.la],
          isQila: [false],
          book: 'علل الوقوف',
          page: '1',
        ),
        ScholarOpinion(
          scholar: 'الداني',
          targetWord: 'كلمة',
          verdicts: ['تام'],
          verdictLabels: ['ط'],
          symbols: [StopSymbol.tam],
          isQila: [true],
          book: 'المكتفى',
          page: '2',
        ),
        ScholarOpinion(
          scholar: 'ابن الأنباري',
          targetWord: 'كلمة',
          verdicts: ['حسن', 'تام'],
          verdictLabels: ['ص', 'ط'],
          symbols: [StopSymbol.mujawwaz, StopSymbol.tam],
          isQila: [false, false],
          book: 'إيضاح الوقف والابتداء',
          page: '3',
        ),
      ],
    );

    expect(stop.symbolForScholar(null), StopSymbol.tam);
    expect(stop.verdictLabelForScholar(null), 'ط');
    expect(stop.isQilaForScholar(null), isFalse);
    expect(stop.labelForScholar(null), 'تام');
    expect(stop.opinionForScholar(null)?.scholar, 'ابن الأنباري');

    // Specific scholar filter still returns that scholar's own primary ruling.
    expect(stop.symbolForScholar('السجاوندي'), StopSymbol.la);
    expect(stop.verdictLabelForScholar('السجاوندي'), 'لا');

    const withLazim = WaqfStop(
      id: 's1-a1-w2',
      surah: 1,
      ayah: 1,
      word: 'كلمة',
      opinions: [
        ScholarOpinion(
          scholar: 'ابن الأنباري',
          targetWord: 'كلمة',
          verdicts: ['تام'],
          verdictLabels: ['ط'],
          symbols: [StopSymbol.tam],
          isQila: [false],
          book: 'إيضاح الوقف والابتداء',
          page: '1',
        ),
        ScholarOpinion(
          scholar: 'السجاوندي',
          targetWord: 'كلمة',
          verdicts: ['لازم'],
          verdictLabels: ['م'],
          symbols: [StopSymbol.tam],
          isQila: [false],
          book: 'علل الوقوف',
          page: '2',
        ),
      ],
    );
    expect(withLazim.verdictLabelForScholar(null), 'م');
    expect(withLazim.labelForScholar(null), 'لازم');
  });

  testWidgets(
      'Default stop dock tab (آراء العلماء) cycles demo variants via stepDemoOrStop',
      (tester) async {
    final controller = ReaderController();
    addTearDown(controller.dispose);
    await tester.runAsync(() => controller.bootstrap(initialSurah: 74));
    controller.showAllStops();
    controller.setSelectedScholar(null);

    final stop = controller.stopById('s74-a53-w1')!;
    controller.openStopDock('s74-a53-w1');
    expect(controller.stopDockOpen, isTrue);
    expect(controller.stopDockTab, 1);
    expect(controller.demoHighlightActive, isTrue);
    expect(controller.activeStopDemoGroupIndex(stop), 0);

    expect(controller.stepDemoOrStop(1), isTrue);
    expect(controller.selectedStopId, 's74-a53-w1');
    expect(controller.activeStopDemoGroupIndex(stop), 1);
  });

  test(
      'hideUthmani keeps Uthmani positions whose opinions disagree on allowed vs non-allowed (even if qila)',
      () {
    ScholarOpinion op(
      String scholar,
      List<String> verdicts,
      List<String> labels,
      List<StopSymbol> symbols,
      List<bool> isQila,
    ) =>
        ScholarOpinion(
          scholar: scholar,
          targetWord: 'كلمة',
          verdicts: verdicts,
          verdictLabels: labels,
          symbols: symbols,
          isQila: isQila,
          book: 'علل الوقوف',
          page: '1',
        );

    final controller = ReaderController();
    addTearDown(controller.dispose);
    controller.hideUthmani = true;

    // 1. Uthmani allowed ('ج') + all opinions allowed -> hidden when hideUthmani=true.
    final agreedAllowed = WaqfStop(
      id: 't-1',
      surah: 1,
      ayah: 1,
      word: 'كلمة',
      inUthmaniMushaf: true,
      uthmaniMark: 'ج',
      uthmaniMarkName: 'جائز',
      opinions: [
        op('السجاوندي', ['تام'], ['ط'], [StopSymbol.tam], [false]),
        op('الداني', ['كاف'], ['ج'], [StopSymbol.jaiz], [false]),
      ],
    );
    expect(agreedAllowed.differsFromUthmani, isFalse);
    expect(controller.isStopVisible(agreedAllowed), isFalse);

    // 2. Uthmani allowed ('صلى') + at least one non-allowed face (even qila) -> shown.
    final uthmaniAllowedButQilaLa = WaqfStop(
      id: 't-2',
      surah: 1,
      ayah: 1,
      word: 'كلمة',
      inUthmaniMushaf: true,
      uthmaniMark: 'صلى',
      uthmaniMarkName: 'الوصل أولى',
      opinions: [
        op('الداني', ['تام'], ['ط'], [StopSymbol.tam], [false]),
        op('السجاوندي', ['حسن', 'لا يوقف'], ['ص', 'لا'],
            [StopSymbol.mujawwaz, StopSymbol.la], [false, true]),
      ],
    );
    expect(uthmaniAllowedButQilaLa.differsFromUthmani, isTrue);
    expect(controller.isStopVisible(uthmaniAllowedButQilaLa), isTrue);

    // 3. Uthmani non-allowed ('لا') + any allowed opinion (even qila) -> shown.
    final uthmaniLaButQilaAllowed = WaqfStop(
      id: 't-3',
      surah: 1,
      ayah: 1,
      word: 'كلمة',
      inUthmaniMushaf: true,
      uthmaniMark: 'لا',
      uthmaniMarkName: 'ممنوع',
      opinions: [
        op('السجاوندي', ['لا يوقف'], ['لا'], [StopSymbol.la], [false]),
        op('الأشموني', ['قيل فيه وقف'], ['ق'], [StopSymbol.jaiz], [true]),
      ],
    );
    expect(uthmaniLaButQilaAllowed.differsFromUthmani, isTrue);
    expect(controller.isStopVisible(uthmaniLaButQilaAllowed), isTrue);

    // 4. Uthmani non-allowed ('لا') + all opinions non-allowed -> hidden when hideUthmani=true.
    final agreedLa = WaqfStop(
      id: 't-4',
      surah: 1,
      ayah: 1,
      word: 'كلمة',
      inUthmaniMushaf: true,
      uthmaniMark: 'لا',
      uthmaniMarkName: 'ممنوع',
      opinions: [
        op('السجاوندي', ['لا يوقف'], ['لا'], [StopSymbol.la], [false]),
        op('الداني', ['لا يوقف'], ['لا'], [StopSymbol.la], [true]),
      ],
    );
    expect(agreedLa.differsFromUthmani, isFalse);
    expect(controller.isStopVisible(agreedLa), isFalse);

    // 5. Verse-end stop (isVerseEnd=true, inUthmaniMushaf=false) follows same Uthmani rule:
    //    all opinions allowed -> agrees with Uthmani verse-end -> hidden;
    //    any non-allowed ('لا يوقف', even qila) -> differs -> shown.
    final verseEndAgreed = WaqfStop(
      id: 't-5',
      surah: 1,
      ayah: 2,
      word: 'كلمة',
      inUthmaniMushaf: false,
      isVerseEnd: true,
      opinions: [
        op('الداني', ['تام'], ['ط'], [StopSymbol.tam], [false]),
      ],
    );
    expect(verseEndAgreed.differsFromUthmani, isFalse);
    expect(controller.isStopVisible(verseEndAgreed), isFalse);

    final verseEndWithQilaLa = WaqfStop(
      id: 't-6',
      surah: 1,
      ayah: 3,
      word: 'كلمة',
      inUthmaniMushaf: false,
      isVerseEnd: true,
      opinions: [
        op('الداني', ['تام'], ['ط'], [StopSymbol.tam], [false]),
        op('السجاوندي', ['لا يوقف'], ['لا'], [StopSymbol.la], [true]),
      ],
    );
    expect(verseEndWithQilaLa.differsFromUthmani, isTrue);
    expect(controller.isStopVisible(verseEndWithQilaLa), isTrue);

    // 6. Any stop with more than one demo (> 1 demo group) is ALWAYS shown,
    //    even when hideUthmani=true and it agrees with Uthmani.
    const demoA = WaqfDemoAndMeaning(
      verdict: 'جائز',
      isQila: false,
      waqfSegmentWords: [1, 2],
      waqfDemo: 'Demo A',
      ibtidaDemo: '',
      meaningAtWaqf: 'Meaning A',
      meaningAtIbtida: '',
      meaningIfConnected: '',
    );
    const demoB = WaqfDemoAndMeaning(
      verdict: 'جائز',
      isQila: false,
      waqfSegmentWords: [1, 3],
      waqfDemo: 'Demo B',
      ibtidaDemo: '',
      meaningAtWaqf: 'Meaning B',
      meaningAtIbtida: '',
      meaningIfConnected: '',
    );
    const multiDemoAgreed = WaqfStop(
      id: 't-7',
      surah: 1,
      ayah: 4,
      word: 'كلمة',
      inUthmaniMushaf: true,
      uthmaniMark: 'ج',
      uthmaniMarkName: 'جائز',
      opinions: [
        ScholarOpinion(
          scholar: 'السجاوندي',
          targetWord: 'كلمة',
          verdicts: ['تام'],
          verdictLabels: ['ط'],
          symbols: [StopSymbol.tam],
          isQila: [false],
          book: 'علل الوقوف',
          page: '1',
          demosAndMeanings: [demoA],
        ),
        ScholarOpinion(
          scholar: 'الداني',
          targetWord: 'كلمة',
          verdicts: ['كاف'],
          verdictLabels: ['ج'],
          symbols: [StopSymbol.jaiz],
          isQila: [false],
          book: 'المكتفى',
          page: '1',
          demosAndMeanings: [demoB],
        ),
      ],
    );
    expect(multiDemoAgreed.differsFromUthmani, isFalse);
    expect(controller.stopDemoGroupsFor(multiDemoAgreed).length, 2);
    expect(controller.isStopVisible(multiDemoAgreed), isTrue);

    // Turning hideUthmani off shows agreed single/zero-demo stops too,
    // while multi-demo stops remain visible.
    controller.hideUthmani = false;
    expect(controller.isStopVisible(agreedAllowed), isTrue);
    expect(controller.isStopVisible(agreedLa), isTrue);
    expect(controller.isStopVisible(verseEndAgreed), isTrue);
    expect(controller.isStopVisible(multiDemoAgreed), isTrue);
  });
}
