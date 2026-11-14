import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:waqf_reader_grok/data/sample_data.dart';
import 'package:waqf_reader_grok/models/waqf_models.dart';
import 'package:waqf_reader_grok/screens/mushaf_screen.dart';
import 'package:waqf_reader_grok/utils/waqf_share.dart';

void main() {
  group('Waqf Sharing & Formatting Tests', () {
    const sampleStop = WaqfStop(
      id: 's1-a2-w2',
      surah: 1,
      ayah: 2,
      wordIndex: 2,
      word: 'لِلَّهِ',
      fallbackSymbol: StopSymbol.tam,
      fallbackLabel: 'ط',
      fallbackReason: 'للابتداء بما بعده',
      inUthmaniMushaf: true,
      textPage: 12,
      opinions: [
        ScholarOpinion(
          scholar: 'السجاوندي',
          book: 'علل الوقوف',
          page: '12',
          verdicts: ['تام'],
          verdictLabels: ['ط'],
          symbols: [StopSymbol.tam],
          isQila: [false],
          targetWord: 'لِلَّهِ',
          comment: 'علة الوقف الابتداء بالحمد.',
        ),
        ScholarOpinion(
          scholar: 'الداني',
          book: 'المكتفى',
          page: '45',
          verdicts: ['كاف', 'تام'],
          verdictLabels: ['ج', 'ط'],
          symbols: [StopSymbol.jaiz, StopSymbol.tam],
          isQila: [false, true],
          targetWord: 'لِلَّهِ',
          comment: 'وقيل تام.',
        ),
      ],
    );

    test('formatOpinionText puts book, scholar, verdict on one line and labels comment',
        () {
      final op = sampleStop.opinions.first;
      final text = formatOpinionText(sampleStop, op, surahName: 'سورة الفاتحة');
      expect(text, contains('🕌 ﴿ *لِلَّهِ* ﴾ — سورة الفاتحة، الآية ٢'));
      expect(text, contains('📖 [علل الوقوف: 12] · *السجاوندي* — 🟢 *تام*'));
      expect(text, contains('💬 *رأي السجاوندي*: علة الوقف الابتداء بالحمد.'));
      expect(text, isNot(contains('موضع الوقف عنده')));
    });

    test('formatOpinionText formats multi-face opinions with qila', () {
      final op2 = sampleStop.opinions[1];
      final text = formatOpinionText(sampleStop, op2, surahName: 'سورة الفاتحة');
      expect(
        text,
        contains('📖 [المكتفى: 45] · *الداني* — 🔵 *كاف* / 🟢 *قيل: تام*'),
      );
      expect(text, contains('💬 *رأي الداني*: وقيل تام.'));
    });

    test('formatOpinionText only prints targetWord when distinct from stop word',
        () {
      const altOp = ScholarOpinion(
        scholar: 'النحاس',
        book: 'القطع والائتناف',
        page: '48',
        verdicts: ['كاف'],
        verdictLabels: ['ج'],
        symbols: [StopSymbol.jaiz],
        isQila: [false],
        targetWord: 'الحمد لله',
        comment: 'الوقف على تمام الجملة.',
      );
      final text = formatOpinionText(sampleStop, altOp, surahName: 'سورة الفاتحة');
      expect(text, contains('📍 *موضع الوقف عنده*: «الحمد لله»'));
    });

    test('formatStopText arranges header then opinions then meanings', () {
      final fullText = formatStopText(sampleStop, surahName: 'سورة الفاتحة');
      expect(fullText, contains('🕌 ﴿ *لِلَّهِ* ﴾ — سورة الفاتحة، الآية ٢'));
      expect(fullText, contains('📜 *آراء العلماء*'));
      expect(fullText, contains('📖 [علل الوقوف: 12] · *السجاوندي* — 🟢 *تام*'));
      expect(
        fullText,
        contains('📖 [المكتفى: 45] · *الداني* — 🔵 *كاف* / 🟢 *قيل: تام*'),
      );
    });

    test('formatAyahText formats clean Quran verse with brackets', () {
      const ayah = Ayah(
        number: 2,
        words: [
          AyahWord('الْحَمْدُ', null, 1),
          AyahWord('لِلَّهِ', 's1-a2-w2', 2),
          AyahWord('رَبِّ', null, 3),
          AyahWord('الْعَالَمِينَ', null, 4),
        ],
      );
      final text = formatAyahText(ayah, surahName: 'سورة الفاتحة');
      expect(text, '﴿الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ﴾\n[سورة الفاتحة: آية ٢]');
    });

    test('formatAyahMarkedForStop bolds stop word when no meaning spans', () {
      const ayah = Ayah(
        number: 2,
        words: [
          AyahWord('الْحَمْدُ', null, 1),
          AyahWord('لِلَّهِ', 's1-a2-w2', 2),
          AyahWord('رَبِّ', null, 3),
          AyahWord('الْعَالَمِينَ', null, 4),
        ],
      );
      final text = formatAyahMarkedForStop(
        ayah,
        stop: sampleStop,
        surahName: 'سورة الفاتحة',
      );
      expect(
        text,
        '﴿ الْحَمْدُ *لِلَّهِ* رَبِّ الْعَالَمِينَ ﴾\n[سورة الفاتحة: آية ٢]',
      );
    });

    test('formatAyahMarkedForStop wraps waqf/ibtida spans in brackets', () {
      const ayah = Ayah(
        number: 28,
        words: [
          AyahWord('كَيْفَ', null, 1),
          AyahWord('تَكْفُرُونَ', null, 2),
          AyahWord('بِٱللَّهِ', null, 3),
          AyahWord('وَكُنتُمْ', null, 4),
          AyahWord('أَمْوَٰتًا', null, 5),
          AyahWord('فَأَحْيَـٰكُمْ', 's2-a28-w6', 6),
          AyahWord('ثُمَّ', null, 7),
          AyahWord('يُمِيتُكُمْ', null, 8),
        ],
      );
      const stop = WaqfStop(
        id: 's2-a28-w6',
        surah: 2,
        ayah: 28,
        wordIndex: 6,
        word: 'فَأَحْيَـٰكُمْ',
        opinions: [],
      );
      const demo = WaqfDemoAndMeaning(
        verdict: 'تام',
        isQila: false,
        waqfSegmentWords: [1, 6],
        ibtidaSegmentWords: [7, 8],
        waqfDemo: '',
        ibtidaDemo: '',
        meaningAtWaqf: 'م',
        meaningAtIbtida: 'م',
        meaningIfConnected: '',
      );
      final text = formatAyahMarkedForStop(
        ayah,
        stop: stop,
        demo: demo,
        surahName: 'سورة البقرة',
      );
      expect(
        text,
        contains(
          '﴿ *[كَيْفَ تَكْفُرُونَ بِٱللَّهِ وَكُنتُمْ أَمْوَٰتًا فَأَحْيَـٰكُمْ]* *[ثُمَّ يُمِيتُكُمْ]* ﴾',
        ),
      );
    });

    test('formatStopShare opinions omits demos; meanings keeps them', () {
      const stopWithDemos = WaqfStop(
        id: 's2-a28-w6',
        surah: 2,
        ayah: 28,
        wordIndex: 6,
        word: 'فَأَحْيَـٰكُمْ',
        opinions: [
          ScholarOpinion(
            scholar: 'ابن الأنباري',
            targetWord: 'فَأَحْيَـٰكُمْ',
            verdicts: ['تام'],
            verdictLabels: ['ط'],
            symbols: [StopSymbol.tam],
            isQila: [false],
            book: 'إيضاح',
            page: '1',
            demosAndMeanings: [
              WaqfDemoAndMeaning(
                verdict: 'تام',
                isQila: false,
                waqfSegmentWords: [1, 6],
                ibtidaSegmentWords: [7, 13],
                waqfDemo: 'تلاوة الوقف',
                ibtidaDemo: 'تلاوة الابتداء',
                meaningAtWaqf: 'معنى الوقف.',
                meaningAtIbtida: 'معنى الابتداء.',
                meaningIfConnected: '',
              ),
            ],
          ),
        ],
      );
      final opinions = formatStopShare(
        stopWithDemos,
        mode: StopShareMode.opinions,
        surahName: 'سورة البقرة',
      );
      expect(opinions, contains('📜 *آراء العلماء*'));
      expect(opinions, contains('📖 [إيضاح: 1] · *ابن الأنباري* — 🟢 *تام*'));
      expect(opinions, isNot(contains('معنى الوقف')));
      expect(opinions, isNot(contains('موضع الوقف عنده')));

      final meanings = formatStopShare(
        stopWithDemos,
        mode: StopShareMode.meanings,
        surahName: 'سورة البقرة',
      );
      expect(meanings, contains('✨ *بيان الوقف والابتداء والمعاني*'));
      expect(meanings, contains('💡 *المعنى الأساسي (وقف وابتداء)*:'));
      expect(meanings, contains('📑 *تفصيل العلماء*:'));
      expect(
        meanings.indexOf('💡 *المعنى الأساسي (وقف وابتداء)*:'),
        lessThan(meanings.indexOf('📑 *تفصيل العلماء*:')),
      );
      expect(meanings, contains('📖 [إيضاح: 1] · *ابن الأنباري* — *تام*'));
      expect(meanings, contains('معنى الوقف.'));
      expect(meanings, isNot(contains('موضع الوقف عنده')));

      final all = formatStopShare(
        stopWithDemos,
        mode: StopShareMode.all,
        surahName: 'سورة البقرة',
      );
      final opinionsIdx = all.indexOf('📜 *آراء العلماء*');
      final meaningsIdx = all.indexOf('✨ *بيان الوقف والابتداء والمعاني*');
      final mainMeaningIdx = all.indexOf('💡 *المعنى الأساسي (وقف وابتداء)*:');
      final scholarsDetailIdx = all.indexOf('📑 *تفصيل العلماء*:');
      expect(opinionsIdx, greaterThanOrEqualTo(0));
      expect(meaningsIdx, greaterThan(opinionsIdx));
      expect(mainMeaningIdx, greaterThan(meaningsIdx));
      expect(scholarsDetailIdx, greaterThan(mainMeaningIdx));
      expect(all, isNot(contains('موضع الوقف عنده')));
    });

    test('formatOpinionText includes demosAndMeanings when present', () {
      const stopWithDemos = WaqfStop(
        id: 's2-a28-w6',
        surah: 2,
        ayah: 28,
        wordIndex: 6,
        word: 'فَأَحْيَـٰكُمْ',
        opinions: [
          ScholarOpinion(
            scholar: 'ابن الأنباري',
            targetWord: 'فَأَحْيَـٰكُمْ',
            verdicts: ['لا يوقف', 'تام'],
            verdictLabels: ['لا', 'ط'],
            symbols: [StopSymbol.la, StopSymbol.tam],
            isQila: [false, true],
            book: 'إيضاح الوقف والابتداء',
            page: '1/506-514',
            comment: 'تعليق موجز.',
            demosAndMeanings: [
              WaqfDemoAndMeaning(
                verdict: 'تام',
                isQila: true,
                attributedTo: 'أبو حاتم السجستاني (حكاه ابن الأنباري وضعّفه)',
                waqfSegmentWords: [1, 6],
                ibtidaSegmentWords: [7, 13],
                waqfDemo:
                    'تلاوة: ﴿ كَيْفَ تَكْفُرُونَ بِٱللَّهِ ﴾ [قف على: فَأَحْيَـٰكُمْ]',
                ibtidaDemo: '﴿ ثُمَّ يُمِيتُكُمْ ﴾ [قف على: تُرْجَعُونْ]',
                meaningAtWaqf: 'معنى الوقف.',
                meaningAtIbtida: 'معنى الابتداء.',
                meaningIfConnected: 'معنى الوصل.',
              ),
            ],
          ),
        ],
      );

      final text = formatOpinionText(
        stopWithDemos,
        stopWithDemos.opinions.first,
        surahName: 'سورة البقرة',
      );
      expect(
        text,
        contains(
          '📖 [إيضاح الوقف والابتداء: 1/506-514] · *ابن الأنباري* — 🔴 *لا يوقف* / 🟢 *قيل: تام*',
        ),
      );
      expect(text, contains('💬 *رأي ابن الأنباري*: تعليق موجز.'));
      expect(text, isNot(contains('موضع الوقف عنده')));
      expect(
        text,
        contains(
          '✨ *بيان الوقف والابتداء* — *قيل: تام* — أبو حاتم السجستاني (حكاه ابن الأنباري وضعّفه):',
        ),
      );
      expect(
        text,
        contains('  ⏸️ *تلاوة الوقف*: ﴿ كَيْفَ تَكْفُرُونَ بِٱللَّهِ ﴾ [قف على: فَأَحْيَـٰكُمْ]'),
      );
      expect(
        text,
        contains('  ▶️ *تلاوة الابتداء*: ﴿ ثُمَّ يُمِيتُكُمْ ﴾ [قف على: تُرْجَعُونْ]'),
      );
      expect(text, contains('  🔹 *المعنى عند الوقف*: معنى الوقف.'));
      expect(text, contains('  🔸 *المعنى عند الابتداء*: معنى الابتداء.'));
      expect(text, contains('  🔗 *المعنى عند الوصل*: معنى الوصل.'));
    });

    testWidgets('Surah 2 Ayah 28 parses demosAndMeanings and preserves Nahhas page',
        (tester) async {
      final bundle = await tester.runAsync(
        () => AppFeedBundle.loadAsset('app_feed/surah_002.json'),
      );
      expect(bundle, isNotNull);

      final w1 = bundle!.stops.firstWhere((s) => s.id == 's2-a28-w1');
      expect(w1.opinionForScholar('ابن الأنباري')!.demosAndMeanings, isEmpty);

      final w3 = bundle.stops.firstWhere((s) => s.id == 's2-a28-w3');
      final anbariW3 = w3.opinionForScholar('ابن الأنباري')!;
      expect(anbariW3.demosAndMeanings, hasLength(1));
      expect(anbariW3.demosAndMeanings.first.verdict, 'حسن');
      expect(anbariW3.demosAndMeanings.first.isQila, isFalse);
      expect(anbariW3.demosAndMeanings.first.attributedTo, isNull);
      expect(anbariW3.demosAndMeanings.first.waqfSegmentWords, [1, 3]);
      expect(anbariW3.demosAndMeanings.first.ibtidaSegmentWords, [4, 13]);
      expect(w3.opinionForScholar('النحاس')!.page, '48');
      expect(w3.opinionForScholar('النحاس')!.demosAndMeanings, isEmpty);

      final w6 = bundle.stops.firstWhere((s) => s.id == 's2-a28-w6');
      final anbariW6 = w6.opinionForScholar('ابن الأنباري')!;
      expect(anbariW6.demosAndMeanings, hasLength(1));
      expect(anbariW6.demosAndMeanings.first.isQila, isTrue);
      expect(
        anbariW6.demosAndMeanings.first.attributedTo,
        'أبو حاتم السجستاني (حكاه ابن الأنباري وضعّفه)',
      );

      final w13 = bundle.stops.firstWhere((s) => s.id == 's2-a28-w13');
      final daniW13 = w13.opinionForScholar('الداني')!;
      expect(daniW13.demosAndMeanings, hasLength(1));
      expect(daniW13.demosAndMeanings.first.waqfSegmentWords, [1, 13]);
      expect(daniW13.demosAndMeanings.first.ibtidaSegmentWords, isNull);
      expect(
        formatOpinionText(w13, daniW13, surahName: 'سورة البقرة'),
        contains('✨ *بيان الوقف والابتداء* — *تام*:'),
      );

      final ayah28 = bundle.ayahs.firstWhere((a) => a.number == 28);
      final allShare = formatStopShare(
        w6,
        mode: StopShareMode.all,
        ayah: ayah28,
        surahName: 'سورة البقرة',
      );
      final opinionsPos = allShare.indexOf('📜 *آراء العلماء*');
      final meaningsPos = allShare.indexOf('✨ *بيان الوقف والابتداء والمعاني*');
      expect(allShare, contains('🔖 *موضع الوقف*: ﴿فَأَحْيَـٰكُمْ﴾'));
      expect(opinionsPos, greaterThan(0));
      expect(meaningsPos, greaterThan(opinionsPos));
      expect(allShare, contains('💬 *رأي السجاوندي*:'));
      expect(allShare, contains('💬 *رأي ابن الأنباري*:'));
      expect(allShare, contains('💬 *رأي الأشموني*:'));
      expect(allShare, contains('💬 *رأي النحاس*:'));
      expect(allShare, isNot(contains('موضع الوقف عنده')));
    });

    testWidgets('Selecting stop highlights demo waqf/ibtida spans in ayah',
        (tester) async {
      final controller = ReaderController();
      addTearDown(controller.dispose);
      await tester.runAsync(() => controller.bootstrap(initialSurah: 2));
      expect(controller.loadState, ReaderLoadState.ready);
      expect(controller.currentSurah, 2);

      // Normal select must NOT paint demo spans.
      controller.select('s2-a28-w3');
      expect(
        controller.demoRoleForWord(ayahNumber: 28, wordIndex: 1),
        DemoSegmentRole.none,
      );

      controller.activateDemoHighlight(
        's2-a28-w3',
        scholar: 'ابن الأنباري',
        demoIndex: 0,
      );

      expect(
        controller.demoRoleForWord(ayahNumber: 28, wordIndex: 1),
        DemoSegmentRole.waqf,
      );
      expect(
        controller.demoRoleForWord(ayahNumber: 28, wordIndex: 3),
        DemoSegmentRole.waqf,
      );
      expect(
        controller.demoRoleForWord(ayahNumber: 28, wordIndex: 4),
        DemoSegmentRole.ibtida,
      );
      expect(
        controller.demoRoleForWord(ayahNumber: 28, wordIndex: 13),
        DemoSegmentRole.ibtida,
      );
      expect(
        controller.demoRoleForWord(ayahNumber: 27, wordIndex: 1),
        DemoSegmentRole.none,
      );
    });

    testWidgets(
        'MushafScreen scrolls focused ayah into view even without demo highlight',
        (tester) async {
      GoogleFonts.config.allowRuntimeFetching = false;
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final controller = ReaderController();
      addTearDown(controller.dispose);
      await tester.runAsync(() => controller.bootstrap(initialSurah: 2));
      expect(controller.loadState, ReaderLoadState.ready);

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

      final listFinder = find.descendant(
        of: find.byType(MushafScreen),
        matching: find.byWidgetPredicate(
          (w) => w is Scrollable && w.axisDirection == AxisDirection.down,
        ),
      );
      final scrollable = tester.state<ScrollableState>(listFinder.first);
      expect(scrollable.position.pixels, 0.0);

      // s2-a10-w2 has no demosAndMeanings -> demoHighlightActive stays false.
      controller.openStopDock('s2-a10-w2');
      await tester.pumpAndSettle();
      expect(controller.stopDockOpen, isTrue);
      expect(controller.demoHighlightActive, isFalse);
      final noHighlightPixels = scrollable.position.pixels;
      expect(noHighlightPixels, greaterThan(0.0));

      // Stepping to a stop WITH highlight behaves the same way.
      controller.openStopDock('s2-a28-w3');
      await tester.pumpAndSettle();
      expect(controller.stopDockOpen, isTrue);
      expect(controller.demoHighlightActive, isTrue);
      expect(scrollable.position.pixels, greaterThan(noHighlightPixels));
    });
  });
}
