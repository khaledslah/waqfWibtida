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

String defaultVerdictLabelForSymbol(StopSymbol symbol) {
  switch (symbol) {
    case StopSymbol.tam:
      return 'ط';
    case StopSymbol.la:
      return 'لا';
    case StopSymbol.jaiz:
      return 'ج';
    case StopSymbol.mujawwaz:
      return 'ز';
    case StopSymbol.unsettled:
      return 'ج';
  }
}

class ScholarOpinion {
  const ScholarOpinion({
    required this.scholar,
    required this.targetWord,
    required this.verdicts,
    required this.verdictLabels,
    required this.symbols,
    required this.isQila,
    required this.book,
    required this.page,
    this.comment,
    this.fromMargin = false,
  });

  final String scholar;
  final String targetWord;
  final List<String> verdicts;
  final List<String> verdictLabels;
  final List<StopSymbol> symbols;
  final List<bool> isQila;
  final String book;
  final String? page;
  final String? comment;

  /// True for secondary apparatus opinions when grouped separately.
  final bool fromMargin;

  String get primaryVerdict => verdicts.isNotEmpty ? verdicts.first : 'جائز';

  String get primaryVerdictLabel => verdictLabels.isNotEmpty
      ? verdictLabels.first
      : defaultVerdictLabelForSymbol(primarySymbol);

  StopSymbol get primarySymbol =>
      symbols.isNotEmpty ? symbols.first : StopSymbol.jaiz;

  bool get primaryIsQila => isQila.isNotEmpty ? isQila.first : false;

  String? get verdict => verdicts.isNotEmpty ? verdicts.join(' / ') : null;

  bool get isSajawandiMatn =>
      !fromMargin && (scholar == 'السجاوندي' || book.contains('علل الوقوف'));
}

class WaqfStop {
  const WaqfStop({
    required this.id,
    required this.surah,
    required this.ayah,
    required this.word,
    required this.opinions,
    this.wordIndex = 1,
    this.fallbackSymbol,
    this.fallbackLabel,
    this.fallbackReason,
    this.aiSuggestion,
    this.inUthmaniMushaf = false,
    this.isVerseEnd = false,
    this.textPage,
  });

  final String id;
  final int surah;
  final int ayah;
  final int wordIndex;
  final String word;
  final List<ScholarOpinion> opinions;
  final StopSymbol? fallbackSymbol;
  final String? fallbackLabel;
  final String? fallbackReason;
  final String? aiSuggestion;
  final bool inUthmaniMushaf;
  final bool isVerseEnd;

  /// Page in علل الوقوف (matches page_N.png).
  final int? textPage;

  bool hasScholar(String scholarName) {
    return opinions.any((o) => o.scholar == scholarName);
  }

  ScholarOpinion? opinionForScholar(String? scholarName) {
    if (opinions.isEmpty) return null;
    if (scholarName != null && scholarName.isNotEmpty) {
      for (final op in opinions) {
        if (op.scholar == scholarName) return op;
      }
    }
    return opinions.first;
  }

  StopSymbol symbolForScholar(String? scholarName) {
    final op = opinionForScholar(scholarName);
    if (op != null) return op.primarySymbol;
    return fallbackSymbol ?? StopSymbol.jaiz;
  }

  String verdictLabelForScholar(String? scholarName) {
    final op = opinionForScholar(scholarName);
    if (op != null) return op.primaryVerdictLabel;
    return defaultVerdictLabelForSymbol(symbol);
  }

  bool isQilaForScholar(String? scholarName) {
    final op = opinionForScholar(scholarName);
    if (op != null) return op.primaryIsQila;
    return false;
  }

  String labelForScholar(String? scholarName) {
    final op = opinionForScholar(scholarName);
    if (op != null) {
      return op.verdicts.join(' / ');
    }
    return fallbackLabel ?? 'جائز';
  }

  String reasonForScholar(String? scholarName) {
    final op = opinionForScholar(scholarName);
    if (op != null) {
      if (op.comment != null && op.comment!.trim().isNotEmpty) {
        return op.comment!;
      }
      return 'وقف ${op.scholar} (${op.book}): ${op.verdicts.join(" / ")}';
    }
    return fallbackReason ?? '';
  }

  StopSymbol get symbol => symbolForScholar(null);

  String get verdictLabel => verdictLabelForScholar(null);

  bool get isQila => isQilaForScholar(null);

  String get label => labelForScholar(null);

  String get reason => reasonForScholar(null);

  bool get needsReview {
    if (symbol == StopSymbol.unsettled) return true;
    final suggestion = aiSuggestion;
    if (suggestion != null && suggestion.trim().isNotEmpty) return true;
    return opinions.isEmpty || opinions.any((opinion) => opinion.verdicts.isEmpty);
  }

  bool get hasAiSuggestion {
    final suggestion = aiSuggestion;
    return suggestion != null && suggestion.trim().isNotEmpty;
  }

  bool get hasNullVerdict =>
      opinions.isEmpty || opinions.any((opinion) => opinion.verdicts.isEmpty);

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
