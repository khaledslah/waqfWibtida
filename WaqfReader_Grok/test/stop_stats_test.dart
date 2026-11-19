import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:waqf_reader_grok/data/sample_data.dart';
import 'package:waqf_reader_grok/data/stop_stats.dart';
import 'package:waqf_reader_grok/models/waqf_models.dart';
import 'package:waqf_reader_grok/screens/mushaf_screen.dart';
import 'package:waqf_reader_grok/screens/my_mushaf_screen.dart';
import 'package:waqf_reader_grok/screens/review_screen.dart';
import 'package:waqf_reader_grok/screens/stats_screen.dart';

ScholarOpinion _op(
  String scholar,
  List<String> verdicts,
  List<String> labels,
  List<StopSymbol> symbols,
  List<bool> qila, {
  List<WaqfDemoAndMeaning> demos = const [],
}) =>
    ScholarOpinion(
      scholar: scholar,
      targetWord: 'كلمة',
      verdicts: verdicts,
      verdictLabels: labels,
      symbols: symbols,
      isQila: qila,
      book: 'علل الوقوف',
      page: '1',
      demosAndMeanings: demos,
    );

WaqfDemoAndMeaning _demo(List<int> span, {int? startAyah, int? endAyah}) =>
    WaqfDemoAndMeaning(
      verdict: 'تام',
      isQila: false,
      waqfSegmentWords: span,
      waqfStartAyah: startAyah,
      waqfEndAyah: endAyah,
      waqfDemo: 'd',
      ibtidaDemo: '',
      meaningAtWaqf: 'm',
      meaningAtIbtida: '',
      meaningIfConnected: '',
    );

void main() {
  setUpAll(() {
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  test('StopStats counts degrees, Uthmani comparison, demos, and scholars', () {
    final stops = [
      // Uthmani 'ج' + all allowed -> agrees; highest degree تام.
      WaqfStop(
        id: 'a',
        surah: 1,
        ayah: 1,
        word: 'كلمة',
        inUthmaniMushaf: true,
        uthmaniMark: 'ج',
        uthmaniMarkName: 'جائز',
        opinions: [
          _op('السجاوندي', ['تام'], ['ط'], [StopSymbol.tam], [false]),
          _op('الداني', ['كاف'], ['ج'], [StopSymbol.jaiz], [false]),
        ],
      ),
      // Mid-ayah, not Uthmani -> differs; scholars disagree; qila face.
      WaqfStop(
        id: 'b',
        surah: 1,
        ayah: 2,
        word: 'كلمة',
        opinions: [
          _op('السجاوندي', ['لا يوقف'], ['لا'], [StopSymbol.la], [false]),
          _op('الأشموني', ['حسن'], ['ص'], [StopSymbol.mujawwaz], [true],
              demos: [
                _demo([1, 2]),
                _demo([3, 1], startAyah: 1, endAyah: 2),
              ]),
        ],
      ),
      // Verse end, all لا يوقف -> differs from Uthmani verse-end; degree لا يوقف.
      WaqfStop(
        id: 'c',
        surah: 1,
        ayah: 3,
        word: 'كلمة',
        isVerseEnd: true,
        opinions: [
          _op('الداني', ['لا يوقف'], ['لا'], [StopSymbol.la], [false]),
        ],
      ),
    ];

    final s = StopStats.compute(stops);
    expect(s.total, 3);
    expect(s.inUthmani, 1);
    expect(s.verseEnd, 1);
    expect(s.midAyah, 2);
    expect(s.differsFromUthmani, 2);
    expect(s.agreesWithUthmani, 1);
    expect(s.withDemos, 1);
    expect(s.multiDemo, 1);
    expect(s.crossAyahDemo, 1);
    expect(s.scholarDisagreement, 1);
    expect(s.withQila, 1);

    final degrees = {for (final d in s.byDegree) d.label: d.count};
    expect(degrees, {'تام': 1, 'حسن': 1, 'لا يوقف': 1});

    expect(s.byUthmaniMark.single.symbol, 'ج');
    expect(s.byUthmaniMark.single.count, 1);

    final sajawandi = s.byScholar.firstWhere((x) => x.scholar == 'السجاوندي');
    expect(sajawandi.total, 2);
    expect(sajawandi.allowed, 1);
    expect(sajawandi.notAllowed, 1);
    final ashmuni = s.byScholar.firstWhere((x) => x.scholar == 'الأشموني');
    expect(ashmuni.withQila, 1);
    // Display order follows the scholar picker order.
    expect(s.byScholar.map((x) => x.scholar).toList(),
        ['السجاوندي', 'الأشموني', 'الداني']);
  });

  testWidgets('Stats screen shows current surah statistics', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final controller = ReaderController();
    addTearDown(controller.dispose);
    await tester.runAsync(() => controller.bootstrap(initialSurah: 74));
    expect(controller.loadState, ReaderLoadState.ready);

    await tester.pumpWidget(
      MaterialApp(
        home: Directionality(
          textDirection: TextDirection.rtl,
          child: StopStatsScreen(controller: controller),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('إحصائيات الوقوف'), findsOneWidget);
    expect(find.text('إجمالي الوقوف'), findsOneWidget);
    expect(find.text('المصحف كاملاً'), findsOneWidget);
    expect(find.text('زائدة عن المصحف'), findsWidgets);
    expect(find.text('تخالف المصحف'), findsNothing);
    expect(
      find.text(arabicDigits(controller.sampleStops.length)),
      findsWidgets,
    );
    expect(find.text('درجات الوقف'), findsOneWidget);
  });

  test('ReviewListFilter removes unused filters and applies useful filters',
      () async {
    final names = ReviewListFilter.values.map((f) => f.name).toSet();
    expect(names.contains('unsettled'), isFalse);
    expect(names.contains('ai'), isFalse);
    expect(names.contains('verseEnd'), isFalse);

    final controller = ReaderController();
    addTearDown(controller.dispose);
    await controller.bootstrap(initialSurah: 74);

    final stops = controller.sampleStops;
    expect(
      controller.reviewCountForFilter(ReviewListFilter.all),
      stops.length,
    );
    expect(
      controller.reviewCountForFilter(ReviewListFilter.extraOverUthmani),
      stops.where((s) => s.differsFromUthmani).length,
    );
    expect(
      controller.reviewCountForFilter(ReviewListFilter.multiDemo),
      stops.where((s) => controller.stopDemoGroupsFor(s).length > 1).length,
    );
    expect(
      controller.reviewCountForFilter(ReviewListFilter.crossAyahDemo),
      greaterThan(0),
    );
    expect(
      controller.reviewCountForFilter(ReviewListFilter.withDemos),
      stops.where((s) => s.hasDemosAndMeanings).length,
    );
    expect(
      controller.reviewCountForFilter(ReviewListFilter.scholarDisagreement),
      stops.where((s) => s.hasAllowedVsNonAllowedDisagreement).length,
    );
    expect(
      controller.reviewCountForFilter(ReviewListFilter.withQila),
      stops.where((s) => s.hasQilaFace).length,
    );
    expect(
      controller.reviewCountForFilter(ReviewListFilter.uthmani),
      stops.where((s) => s.inUthmaniMushaf).length,
    );

    final crossStop = controller.stopById('s74-a53-w1')!;
    expect(
      controller.matchesReviewFilter(crossStop, ReviewListFilter.multiDemo),
      isTrue,
    );
    expect(
      controller.matchesReviewFilter(crossStop, ReviewListFilter.crossAyahDemo),
      isTrue,
    );

    // Scholar filter combines with review filters.
    controller.setSelectedScholar('السجاوندي');
    expect(
      controller.reviewItems.every((s) => s.hasScholar('السجاوندي')),
      isTrue,
    );
    controller.setSelectedScholar(null);

    // Switching scope between current surah and all surahs preserves loaded pools.
    expect(controller.reviewAllSurahs, isFalse);
    await AppFeedBundle.loadAsset('app_feed/surah_001.json');
    controller.setReviewAllSurahs(true);
    expect(controller.reviewAllSurahs, isTrue);
    expect(
      controller.reviewPoolStops.length,
      greaterThan(controller.sampleStops.length),
    );
    controller.setReviewAllSurahs(false);
    expect(controller.reviewPoolStops.length, controller.sampleStops.length);
  });

  testWidgets('ReviewScreen renders scope toggle and underline filters matching main bar',
      (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final controller = ReaderController();
    addTearDown(controller.dispose);
    await tester.runAsync(() => controller.bootstrap(initialSurah: 74));

    await tester.pumpWidget(
      MaterialApp(
        home: Directionality(
          textDirection: TextDirection.rtl,
          child: Scaffold(
            body: ListenableBuilder(
              listenable: controller,
              builder: (context, _) => ReviewScreen(controller: controller),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('سورة المدثر'), findsOneWidget);
    expect(find.textContaining('الكل ('), findsOneWidget);
    expect(find.text('الكل'), findsOneWidget);

    await tester.tap(find.byTooltip('تصفية الوقوف'));
    await tester.pumpAndSettle();
    expect(find.textContaining('زائدة عن المصحف'), findsOneWidget);
    expect(find.textContaining('متعددة الأمثلة'), findsOneWidget);
    // Dismiss popup menu by tapping the modal barrier at bottom-left, then open scope dropdown.
    await tester.tapAt(const Offset(10, 800));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('نطاق العرض'));
    await tester.pumpAndSettle();
    expect(find.text('كل السور'), findsOneWidget);
  });

  test('WaqfDemoAndMeaning identifies demos for different Qiraat', () {
    const qDemo = WaqfDemoAndMeaning(
      verdict: 'كاف',
      isQila: false,
      attributedTo: null,
      waqfSegmentWords: [1, 2],
      waqfDemo: 'demo',
      ibtidaDemo: 'ibtida',
      meaningAtWaqf: 'انقضاء الكلام',
      meaningAtIbtida: 'على قراءة ابن كثير بالياء التحتية',
      meaningIfConnected: '',
    );
    expect(qDemo.isQiraatDemo, isTrue);
    expect(qDemo.qiraatCue, 'على قراءة ابن كثير بالياء التحتية');

    const regularDemo = WaqfDemoAndMeaning(
      verdict: 'تام',
      isQila: false,
      waqfSegmentWords: [1, 2],
      waqfDemo: 'd',
      ibtidaDemo: '',
      meaningAtWaqf: 'تمام الكلام هنا',
      meaningAtIbtida: '',
      meaningIfConnected: '',
    );
    expect(regularDemo.isQiraatDemo, isFalse);
    expect(regularDemo.qiraatCue, isNull);

    const stop = WaqfStop(
      id: 'q-1',
      surah: 2,
      ayah: 74,
      word: 'تعملون',
      opinions: [
        ScholarOpinion(
          scholar: 'الداني',
          targetWord: 'تعملون',
          verdicts: ['كاف'],
          verdictLabels: ['ج'],
          symbols: [StopSymbol.jaiz],
          isQila: [false],
          book: 'المكتفى',
          page: '1',
          demosAndMeanings: [qDemo],
        ),
      ],
    );
    expect(stop.hasQiraatVariation, isTrue);

    final controller = ReaderController();
    addTearDown(controller.dispose);
    expect(controller.matchesReviewFilter(stop, ReviewListFilter.qiraat), isTrue);
  });

  test('Qiraat demo extracts and applies modified word override in Mushaf',
      () async {
    final controller = ReaderController();
    addTearDown(controller.dispose);
    await controller.bootstrap(initialSurah: 1);

    // In "الكل" mode, s1-a7-w4 separates the Qiraat reading (غيرُ) as its own variant.
    final groups = controller.stopDemoGroupsFor(controller.stopById('s1-a7-w4')!);
    expect(groups.length, 2);

    // Activate Ayah 7 stop (s1-a7-w4) on الأشموني's 2nd demo (القراءة الشاذة بالرفع: غيرُ)
    controller.activateDemoHighlight(
      's1-a7-w4',
      scholar: 'الأشموني',
      demoIndex: 1,
    );
    final mod = controller.qiraatOverrideForWord(ayahNumber: 7, wordIndex: 5);
    expect(mod, isNotNull);
    expect(mod!.hafsWord, 'غَيْرِ');
    expect(mod.modifiedWord, 'غَيْرُ');

    // Switching back to the Hafs demo clears the Qiraat word override.
    controller.selectDemo(scholar: 'الأشموني', demoIndex: 0);
    expect(
      controller.qiraatOverrideForWord(ayahNumber: 7, wordIndex: 5),
      isNull,
    );

    // Persisted LLM qiraatOverrides (Surah 62, Ayah 1) load and apply cleanly.
    await controller.loadSurah(62);
    controller.activateDemoHighlight(
      's62-a1-w8',
      scholar: 'النحاس',
      demoIndex: 0,
    );
    final s62Mod = controller.qiraatOverrideForWord(ayahNumber: 1, wordIndex: 9);
    expect(s62Mod, isNotNull);
    expect(s62Mod!.hafsWord, 'ٱلْمَلِكِ');
    expect(s62Mod.modifiedWord, 'ٱلْمَلِكُ');

    // Cache-poisoning regression guard: computing stopDemoGroupsFor on Surah 2
    // while currentSurah != 2 must still preserve s2-a26-w8's Qira'at variant.
    final asset2 = controller.catalog.firstWhere((e) => e.number == 2).asset;
    final bundle2 = await AppFeedBundle.loadAsset(asset2);
    expect(controller.currentSurah, 62);
    expect(
      controller.stopDemoGroupsFor(bundle2.stopsById['s2-a26-w8']!).length,
      2,
    );
    await controller.loadSurah(2);
    final s2Stop = controller.stopById('s2-a26-w8')!;
    final s2Groups = controller.stopDemoGroupsFor(s2Stop);
    expect(s2Groups.length, 2);
    final qGroup = s2Groups.firstWhere((g) => g.demo.qiraatOverrides.isNotEmpty);
    expect(qGroup.scholar, 'الأشموني');
    controller.activateDemoHighlight(
      's2-a26-w8',
      scholar: qGroup.scholar,
      demoIndex: qGroup.demoIndex,
    );
    final s2Mod = controller.qiraatOverrideForWord(ayahNumber: 26, wordIndex: 9);
    expect(s2Mod, isNotNull);
    expect(s2Mod!.hafsWord, 'بَعُوضَةًۭ');
    expect(s2Mod.modifiedWord, 'بَعُوضَةٌ');

    // Surah 2 Ayah 7 (سَمْعِهِمْ): Hafs group comes first, still surfaces Qira'at
    // opinion from group members, and second group swaps غِشَـٰوَةٌۭ -> غِشَـٰوَةً.
    final s2a7w6 = controller.stopById('s2-a7-w6')!;
    final a7w6Groups = controller.stopDemoGroupsFor(s2a7w6);
    expect(a7w6Groups.length, 2);
    expect(a7w6Groups[0].demo.qiraatOverrides, isEmpty);
    expect(a7w6Groups[0].qiraatOpinion(s2a7w6)?.hasQiraatInfo, isTrue);
    expect(a7w6Groups[1].demo.qiraatOverrides.length, 1);
    expect(a7w6Groups[1].demo.qiraatOverrides.first.hafsWord, 'غِشَـٰوَةٌۭ');
    expect(a7w6Groups[1].demo.qiraatOverrides.first.modifiedWord, 'غِشَـٰوَةً');

    // Surah 2 Ayah 7 (أَبْصَـٰرِهِمْ): non-Hafs-only stop swaps غِشَـٰوَةً immediately.
    final s2a7w8 = controller.stopById('s2-a7-w8')!;
    final a7w8Groups = controller.stopDemoGroupsFor(s2a7w8);
    expect(a7w8Groups.length, 1);
    expect(a7w8Groups.first.demo.qiraatOverrides.first.modifiedWord, 'غِشَـٰوَةً');

    // Surah 2 Ayah 9 (ءَامَنُوا۟): leading السجاوندي does not hide الأشموني's Qira'at badge.
    final s2a9w4 = controller.stopById('s2-a9-w4')!;
    final a9w4Groups = controller.stopDemoGroupsFor(s2a9w4);
    expect(a9w4Groups.first.scholar, 'السجاوندي');
    expect(a9w4Groups.first.qiraatOpinion(s2a9w4)?.scholar, 'الأشموني');

    // Surah 2 Ayah 17 (يُبْصِرُونَ): cross-ayah 3-word Qira'at swap in Ayah 18.
    final s2a17w17 = controller.stopById('s2-a17-w17')!;
    final a17Groups = controller.stopDemoGroupsFor(s2a17w17);
    expect(a17Groups.length, 2);
    final a17Q = a17Groups.firstWhere((g) => g.demo.qiraatOverrides.isNotEmpty);
    expect(a17Q.demo.qiraatOverrides.length, 3);
    expect(a17Q.demo.qiraatOverrides.first.ayahNumber, 18);
    expect(a17Q.demo.qiraatOverrides.first.modifiedWord, 'صُمًّا');

    // Display color & outline settings switch live and reset cleanly.
    expect(controller.qiraatColorId, 'copper');
    expect(controller.qiraatDottedOutline, isTrue);
    controller.setQiraatColorId('teal');
    expect(controller.qiraatHighlightColor.value, 0xFF1E7F86);
    controller.setQiraatDottedOutline(false);
    expect(controller.qiraatDottedOutline, isFalse);
    controller.resetDisplaySettings();
    expect(controller.qiraatColorId, 'copper');
    expect(controller.qiraatDottedOutline, isTrue);
  });

  testWidgets('MyMushaf 604 pages + add/remove custom stops work cleanly',
      (tester) async {
    final controller = ReaderController();
    addTearDown(controller.dispose);
    await tester.runAsync(() async {
      await controller.bootstrap(initialSurah: 1);
      await controller.ensureMushafPagesLoaded();

      expect(controller.mushafPageInfo(1)?.juz, 1);
      expect(controller.mushafPageInfo(604)?.ranges.length, 3);
      expect(controller.firstMushafPageForSurah(1), 1);
      expect(controller.firstMushafPageForSurah(2), 2);
      expect(controller.firstMushafPageForSurah(114), 604);
      expect(controller.mushafPageForVerse(2, 26), 5);
      expect(controller.mushafPageForVerse(114, 1), 604);

      await controller.loadSurah(2);
      final stop = controller.stopById('s2-a26-w8')!;
      final scholarOp =
          stop.opinions.firstWhere((o) => o.scholar == 'الأشموني');

      // Add default, then replace with explicit scholar via forceAdd, then toggle remove.
      expect(controller.toggleMyMushafStop(stop), isTrue);
      expect(controller.isInMyMushaf(stop.id), isTrue);
      expect(
        controller.toggleMyMushafStop(stop, opinion: scholarOp, forceAdd: true),
        isTrue,
      );
      expect(controller.myMushafEntryFor(stop.id)?.scholar, 'الأشموني');
      expect(controller.sortedMyMushafStops.length, 1);

      await controller.jumpToMyMushafAtVerse(2, 26);
      expect(controller.tab, 1);
      expect(controller.currentMushafPage, 5);
    });

    final stop = controller.stopById('s2-a26-w8')!;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MyMushafScreen(controller: controller),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('my-mushaf-page-pill')), findsOneWidget);
    expect(find.textContaining('ص ٥ / ٦٠٤'), findsOneWidget);
    expect(find.textContaining('وقوفي (١)'), findsOneWidget);
    expect(find.byKey(ValueKey<String>('my-mushaf-badge-${stop.id}')),
        findsOneWidget);

    // Full Waqf (amber) + Ibtida (green) phrase spans & Qira'at word swap
    // are always highlighted for added My Mushaf stops (s2-a26-w8, الأشموني demo 0).
    expect(
      find.byKey(const ValueKey('my-mushaf-hl-2-26-1-waqf')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('my-mushaf-hl-2-26-8-waqf')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('my-mushaf-hl-2-26-9-ibtida')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('my-mushaf-hl-2-26-11-ibtida')),
      findsOneWidget,
    );
    expect(find.byType(QiraatWordText), findsOneWidget);

    // Next arrow sits to the RIGHT of Previous arrow around the page pill,
    // and both chevron icons lock LTR direction so they point outward (< [page] >).
    expect(
      tester.getCenter(find.byKey(const ValueKey('my-mushaf-next-btn'))).dx,
      greaterThan(
        tester.getCenter(find.byKey(const ValueKey('my-mushaf-prev-btn'))).dx,
      ),
    );
    expect(
      tester
          .widget<Icon>(find.descendant(
            of: find.byKey(const ValueKey('my-mushaf-next-btn')),
            matching: find.byType(Icon),
          ))
          .textDirection,
      TextDirection.ltr,
    );
    expect(
      tester
          .widget<Icon>(find.descendant(
            of: find.byKey(const ValueKey('my-mushaf-prev-btn')),
            matching: find.byType(Icon),
          ))
          .textDirection,
      TextDirection.ltr,
    );

    // Horizontal swipe left-to-right advances to Next Mushaf page (5 -> 6).
    await tester.runAsync(() async {
      await tester.fling(
        find.byType(PageView),
        const Offset(300, 0),
        1000,
      );
      await tester.pumpAndSettle();
    });
    expect(controller.currentMushafPage, 6);

    // Next/Prev tap back from 6 -> 5.
    await tester.runAsync(() async {
      await tester.tap(find.byKey(const ValueKey('my-mushaf-prev-btn')));
      await tester.pumpAndSettle();
    });
    expect(controller.currentMushafPage, 5);

    await tester.tap(find.byKey(const ValueKey('my-mushaf-stops-pill')));
    await tester.pumpAndSettle();
    expect(find.textContaining('وقوفي المضافة إلى مصحفي'), findsOneWidget);

    controller.removeFromMyMushaf(stop.id);
    await tester.pumpAndSettle();
    expect(controller.isInMyMushaf(stop.id), isFalse);
    expect(find.textContaining('وقوفي (٠)'), findsOneWidget);
    expect(
      find.byKey(const ValueKey('my-mushaf-hl-2-26-1-waqf')),
      findsNothing,
    );
    expect(
      find.byKey(const ValueKey('my-mushaf-hl-2-26-9-ibtida')),
      findsNothing,
    );
    expect(find.byType(QiraatWordText), findsNothing);
  });
}
