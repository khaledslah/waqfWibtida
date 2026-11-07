import 'package:flutter_test/flutter_test.dart';
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
  });
}
