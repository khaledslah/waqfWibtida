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

class WaqfDemoAndMeaning {
  const WaqfDemoAndMeaning({
    required this.verdict,
    required this.isQila,
    this.attributedTo,
    this.waqfSegmentWords,
    this.ibtidaSegmentWords,
    required this.waqfDemo,
    required this.ibtidaDemo,
    required this.meaningAtWaqf,
    required this.meaningAtIbtida,
    required this.meaningIfConnected,
  });

  final String verdict;
  final bool isQila;
  final String? attributedTo;
  final List<int>? waqfSegmentWords;
  final List<int>? ibtidaSegmentWords;
  final String waqfDemo;
  final String ibtidaDemo;
  final String meaningAtWaqf;
  final String meaningAtIbtida;
  final String meaningIfConnected;
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
    this.demosAndMeanings = const <WaqfDemoAndMeaning>[],
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

  final List<WaqfDemoAndMeaning> demosAndMeanings;

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

  bool get hasDemosAndMeanings =>
      opinions.any((o) => o.demosAndMeanings.isNotEmpty);
}

enum DemoSegmentRole { none, waqf, ibtida }

class AyahWord {
  const AyahWord(this.text, [this.stopId, this.index = 0]);

  final String text;
  final String? stopId;

  /// 1-based word index in the ayah (matches feed `index` / demo spans).
  final int index;
}

bool wordIndexInSpan(List<int>? span, int wordIndex) {
  if (span == null || span.length < 2 || wordIndex < 1) return false;
  final start = span[0];
  final end = span[1];
  if (start > end) return wordIndex >= end && wordIndex <= start;
  return wordIndex >= start && wordIndex <= end;
}

DemoSegmentRole demoSegmentRoleForWord({
  required WaqfDemoAndMeaning? demo,
  required int wordIndex,
}) {
  if (demo == null) return DemoSegmentRole.none;
  if (wordIndexInSpan(demo.waqfSegmentWords, wordIndex)) {
    return DemoSegmentRole.waqf;
  }
  if (wordIndexInSpan(demo.ibtidaSegmentWords, wordIndex)) {
    return DemoSegmentRole.ibtida;
  }
  return DemoSegmentRole.none;
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

class BookPageRef {
  const BookPageRef({
    this.volume,
    this.page,
    this.endPage,
    this.ayahNumber,
  });

  final int? volume;
  final int? page;
  final int? endPage;
  final int? ayahNumber;

  bool get isAyahRef => ayahNumber != null && page == null;

  static String toWesternDigits(String input) {
    return input.replaceAllMapped(RegExp(r'[٠-٩]'), (m) {
      const digits = '٠١٢٣٤٥٦٧٨٩';
      return '${digits.indexOf(m.group(0)!)}';
    });
  }

  static BookPageRef? parse(String? raw) {
    if (raw == null || raw.trim().isEmpty) return null;
    final western = toWesternDigits(raw).trim();

    final ayahMatch = RegExp(r'^آية\s*(\d+)').firstMatch(western);
    if (ayahMatch != null) {
      return BookPageRef(ayahNumber: int.tryParse(ayahMatch.group(1)!));
    }

    // Standard "vol/page..." e.g. "1/173-179", "3/853 - 3/854", "2/697_698"
    final volPageMatch =
        RegExp(r'^([1-9])\s*/\s*(\d+)').firstMatch(western);
    if (volPageMatch != null) {
      final vol = int.tryParse(volPageMatch.group(1)!);
      final start = int.tryParse(volPageMatch.group(2)!);
      final rest = western.substring(volPageMatch.end);
      final trailingVolPage =
          RegExp(r'[1-9]\s*/\s*(\d+)').firstMatch(rest);
      final end = trailingVolPage != null
          ? int.tryParse(trailingVolPage.group(1)!)
          : int.tryParse(RegExp(r'(\d+)').firstMatch(rest)?.group(1) ?? '');
      return BookPageRef(volume: vol, page: start, endPage: end);
    }

    // Reversed trailing volume, e.g. "1027-1029/3" or "753 - 2/754"
    final firstNum = RegExp(r'(\d+)').firstMatch(western);
    if (firstNum == null) return null;
    final start = int.tryParse(firstNum.group(1)!);
    final rest = western.substring(firstNum.end);

    int? vol;
    int? end;
    final revVol = RegExp(r'/\s*([1-9])\s*$').firstMatch(rest);
    final midVolPage =
        RegExp(r'(?:^|[\s\-_،])([1-9])\s*/\s*(\d+)').firstMatch(rest);
    if (midVolPage != null) {
      vol = int.tryParse(midVolPage.group(1)!);
      end = int.tryParse(midVolPage.group(2)!);
    } else {
      if (revVol != null) {
        vol = int.tryParse(revVol.group(1)!);
      }
      final beforeSlash = rest.split('/').first;
      final endMatch = RegExp(r'(\d+)').firstMatch(beforeSlash);
      if (endMatch != null) {
        end = int.tryParse(endMatch.group(1)!);
      }
    }

    return BookPageRef(volume: vol, page: start, endPage: end);
  }
}

int? parsePageNumber(String? raw) => BookPageRef.parse(raw)?.page;
