import 'package:flutter_test/flutter_test.dart';
import 'package:waqf_reader_grok/data/sample_data.dart';
import 'package:waqf_reader_grok/models/waqf_models.dart';
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

    test('formatOpinionText includes scholar, verdicts, and book ref', () {
      final op = sampleStop.opinions.first;
      final text = formatOpinionText(sampleStop, op, surahName: 'سورة الفاتحة');
      expect(text, contains('﴿لِلَّهِ﴾ — سورة الفاتحة، الآية ٢'));
      expect(text, contains('السجاوندي: تام'));
      expect(text, contains('موضع الوقف عنده: «لِلَّهِ»'));
      expect(text, contains('علة الوقف الابتداء بالحمد.'));
      expect(text, contains('[علل الوقوف: 12]'));
    });

    test('formatOpinionText formats multi-face opinions with qila', () {
      final op2 = sampleStop.opinions[1];
      final text = formatOpinionText(sampleStop, op2, surahName: 'سورة الفاتحة');
      expect(text, contains('الداني: كاف / قيل: تام'));
      expect(text, contains('[المكتفى: 45]'));
    });

    test('formatStopText combines all scholars', () {
      final fullText = formatStopText(sampleStop, surahName: 'سورة الفاتحة');
      expect(fullText, contains('﴿لِلَّهِ﴾ — سورة الفاتحة، الآية ٢'));
      expect(fullText, contains('السجاوندي: تام'));
      expect(fullText, contains('الداني: كاف / قيل: تام'));
    });

    test('formatAyahText formats clean Quran verse with brackets', () {
      const ayah = Ayah(
        number: 2,
        words: [
          AyahWord('الْحَمْدُ'),
          AyahWord('لِلَّهِ', 's1-a2-w2'),
          AyahWord('رَبِّ'),
          AyahWord('الْعَالَمِينَ'),
        ],
      );
      final text = formatAyahText(ayah, surahName: 'سورة الفاتحة');
      expect(text, '﴿الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ﴾\n[سورة الفاتحة: آية ٢]');
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
          '• بيان الوقف والابتداء (قيل: تام — أبو حاتم السجستاني (حكاه ابن الأنباري وضعّفه)):',
        ),
      );
      expect(text, contains('  - تلاوة: ﴿ كَيْفَ تَكْفُرُونَ بِٱللَّهِ ﴾ [قف على: فَأَحْيَـٰكُمْ]'));
      expect(text, contains('  - تلاوة الابتداء: ﴿ ثُمَّ يُمِيتُكُمْ ﴾ [قف على: تُرْجَعُونْ]'));
      expect(text, contains('  - المعنى عند الوقف: معنى الوقف.'));
      expect(text, contains('  - المعنى عند الابتداء: معنى الابتداء.'));
      expect(text, contains('  - المعنى عند الوصل: معنى الوصل.'));
      expect(text, endsWith('[إيضاح الوقف والابتداء: 1/506-514]'));
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
        contains('• بيان الوقف والابتداء (تام):'),
      );
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
  });
}
