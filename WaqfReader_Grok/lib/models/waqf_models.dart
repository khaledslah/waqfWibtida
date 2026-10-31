enum StopSymbol { tam, la, jaiz, mujawwaz, unsettled }

/// Maps app-feed symbol strings onto existing badge styles (no new UI).
StopSymbol stopSymbolFromFeed(String? raw) {
  switch (raw) {
    case 'tam':
    case 'lazim':
      return StopSymbol.tam;
    case 'la':
      return StopSymbol.la;
    case 'jaiz':
      return StopSymbol.jaiz;
    case 'mujawwaz':
    case 'murakhkhas':
      return StopSymbol.mujawwaz;
    default:
      return StopSymbol.unsettled;
  }
}

enum SurahLoadStatus { inProgress, notStarted, awaitingReview }

enum ReviewListFilter {
  all,
  needsAttention,
  favorites,
  verified,
  unsettled,
  ai,
  uthmani,
  verseEnd,
}

extension ReviewListFilterLabel on ReviewListFilter {
  String get labelAr {
    switch (this) {
      case ReviewListFilter.all:
        return 'الكل';
      case ReviewListFilter.needsAttention:
        return 'يحتاج مراجعة';
      case ReviewListFilter.favorites:
        return 'المفضلة';
      case ReviewListFilter.verified:
        return 'مُتحقَّق';
      case ReviewListFilter.unsettled:
        return 'غير محسوم';
      case ReviewListFilter.ai:
        return 'مقترح AI';
      case ReviewListFilter.uthmani:
        return 'عثماني';
      case ReviewListFilter.verseEnd:
        return 'رأس آية';
    }
  }
}

class ScholarOpinion {
  const ScholarOpinion({
    required this.scholar,
    required this.verdict,
    required this.book,
    required this.page,
    this.comment,
    this.fromMargin = false,
  });

  final String scholar;
  final String? verdict;
  final String book;
  final String? page;
  final String? comment;

  /// True for margin apparatus opinions (not the matn Sajawandi row).
  final bool fromMargin;

  bool get isSajawandiMatn =>
      !fromMargin && (scholar == 'السجاوندي' || book.contains('علل الوقوف'));
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
    this.inUthmaniMushaf = false,
    this.isVerseEnd = false,
    this.textPage,
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
  final bool inUthmaniMushaf;
  final bool isVerseEnd;

  /// Page in علل الوقوف (matches page_N.png).
  final int? textPage;

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

  List<ScholarOpinion> get matnOpinions =>
      opinions.where((o) => !o.fromMargin).toList();

  List<ScholarOpinion> get marginOpinions =>
      opinions.where((o) => o.fromMargin).toList();
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

int? parsePageNumber(String? raw) {
  if (raw == null || raw.trim().isEmpty) return null;
  final western = raw
      .replaceAllMapped(RegExp('[٠-٩]'), (m) {
        const digits = '٠١٢٣٤٥٦٧٨٩';
        return '${digits.indexOf(m.group(0)!)}';
      })
      .replaceAll(RegExp(r'[^0-9]'), '');
  return int.tryParse(western);
}
