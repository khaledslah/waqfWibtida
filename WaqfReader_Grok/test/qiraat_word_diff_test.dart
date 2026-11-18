import 'package:flutter_test/flutter_test.dart';
import 'package:waqf_reader_grok/utils/qiraat_word_diff.dart';

String _changed(String hafs, String modified) => [
      for (final r in qiraatDiffRuns(hafs, modified))
        if (r.$2) r.$1,
    ].join('|');

void main() {
  group('qiraatDiffRuns', () {
    test('only the letter carrying the swapped i\'rab is flagged', () {
      // رفع → نصب: tanween damma → tanween fatha on the last letter (ة + ً).
      expect(_changed('بَعُوضَةٌ', 'بَعُوضَةً'), 'ةً');
      // غَيْرِ → غَيْرُ: kasra → damma on ر.
      expect(_changed('غَيْرِ', 'غَيْرُ'), 'رُ');
    });

    test('identical words flag nothing', () {
      expect(_changed('الْحَمْدُ', 'الْحَمْدُ'), '');
    });

    test('runs reassemble to the modified word', () {
      const hafs = 'غِشَـٰوَةٌۭ';
      const mod = 'غِشَاوَةً';
      final text = qiraatDiffRuns(hafs, mod).map((r) => r.$1).join();
      expect(text, mod);
      expect(_changed(hafs, mod), isNotEmpty);
    });

    test('completely different word is fully flagged', () {
      expect(_changed('كتب', 'ذهب').replaceAll('|', ''), isNotEmpty);
    });
  });
}
