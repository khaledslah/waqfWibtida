enum StopSymbol { tam, la, jaiz, mujawwaz, unsettled }

enum SurahLoadStatus { inProgress, notStarted, awaitingReview }

class ScholarOpinion {
  const ScholarOpinion({
    required this.scholar,
    required this.verdict,
    required this.book,
    required this.page,
  });

  final String scholar;
  final String? verdict;
  final String book;
  final String? page;
}

class WaqfStop {
  const WaqfStop({
    required this.id,
    required this.surah,
    required this.ayah,
    required this.word,
    required this.symbol,
    required this.label,
    required this.reason,
    required this.opinions,
    this.aiSuggestion,
  });

  final String id;
  final int surah;
  final int ayah;
  final String word;
  final StopSymbol symbol;
  final String label;
  final String reason;
  final List<ScholarOpinion> opinions;
  final String? aiSuggestion;

  bool get needsReview {
    if (symbol == StopSymbol.unsettled) return true;
    final suggestion = aiSuggestion;
    if (suggestion != null && suggestion.trim().isNotEmpty) return true;
    return opinions.any((opinion) => opinion.verdict == null);
  }

  bool get hasAiSuggestion {
    final suggestion = aiSuggestion;
    return suggestion != null && suggestion.trim().isNotEmpty;
  }

  bool get hasNullVerdict => opinions.any((opinion) => opinion.verdict == null);
}

class AyahWord {
  const AyahWord(this.text, [this.stopId]);

  final String text;
  final String? stopId;
}

class Ayah {
  const Ayah({required this.number, required this.words});

  final int number;
  final List<AyahWord> words;
}

class SurahIndexEntry {
  const SurahIndexEntry({
    required this.number,
    required this.name,
    required this.status,
    required this.detail,
  });

  final int number;
  final String name;
  final SurahLoadStatus status;
  final String detail;

  String get statusLabel {
    switch (status) {
      case SurahLoadStatus.inProgress:
        return 'جارٍ';
      case SurahLoadStatus.notStarted:
        return 'لم تبدأ';
      case SurahLoadStatus.awaitingReview:
        return 'بانتظار المراجعة';
    }
  }
}

String arabicDigits(int value) {
  const map = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
  return value.toString().split('').map((digit) => map[int.parse(digit)]).join();
}
