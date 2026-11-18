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
  extraOverUthmani,
  multiDemo,
  crossAyahDemo,
  withDemos,
  scholarDisagreement,
  withQila,
  qiraat,
  uthmani,
  favorites,
  needsAttention,
  verified,
}

extension ReviewListFilterLabel on ReviewListFilter {
  String get labelAr {
    switch (this) {
      case ReviewListFilter.all:
        return 'الكل';
      case ReviewListFilter.extraOverUthmani:
        return 'زائدة عن المصحف';
      case ReviewListFilter.multiDemo:
        return 'متعددة الأمثلة';
      case ReviewListFilter.crossAyahDemo:
        return 'تمتد عبر الآيات';
      case ReviewListFilter.withDemos:
        return 'لها أمثلة ومعانٍ';
      case ReviewListFilter.scholarDisagreement:
        return 'تعدد الأقوال';
      case ReviewListFilter.withQila:
        return 'فيها «قيل»';
      case ReviewListFilter.qiraat:
        return 'متعلقة بالقراءات';
      case ReviewListFilter.uthmani:
        return 'وقف المصحف';
      case ReviewListFilter.favorites:
        return 'المفضلة';
      case ReviewListFilter.needsAttention:
        return 'مُبلّغ عنها';
      case ReviewListFilter.verified:
        return 'مُتحقَّق';
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

class QiraatWordOverride {
  const QiraatWordOverride({
    required this.ayahNumber,
    required this.wordIndex,
    required this.hafsWord,
    required this.modifiedWord,
  });

  final int ayahNumber;
  final int wordIndex;
  final String hafsWord;
  final String modifiedWord;
}

class WaqfDemoAndMeaning {
  const WaqfDemoAndMeaning({
    required this.verdict,
    required this.isQila,
    this.attributedTo,
    this.waqfSegmentWords,
    this.waqfStartAyah,
    this.waqfEndAyah,
    this.ibtidaSegmentWords,
    this.ibtidaStartAyah,
    this.ibtidaEndAyah,
    required this.waqfDemo,
    required this.ibtidaDemo,
    required this.meaningAtWaqf,
    required this.meaningAtIbtida,
    required this.meaningIfConnected,
    this.qiraatOverrides = const <QiraatWordOverride>[],
  });

  final String verdict;
  final bool isQila;
  final String? attributedTo;
  final List<int>? waqfSegmentWords;
  final int? waqfStartAyah;
  final int? waqfEndAyah;
  final List<int>? ibtidaSegmentWords;
  final int? ibtidaStartAyah;
  final int? ibtidaEndAyah;
  final String waqfDemo;
  final String ibtidaDemo;
  final String meaningAtWaqf;
  final String meaningAtIbtida;
  final String meaningIfConnected;
  final List<QiraatWordOverride> qiraatOverrides;

  static final RegExp _demoQiraatCuePattern = RegExp(
    r'((?:على|في|عند)\s+قراءة\s+[^،.؛\n()]{2,48}'
    r'|(?:على|في)\s+قراءتي\s+[^،.؛\n()]{2,48}'
    r'|قراءة\s+(?:مَن|من)\s+قرأ[^،.؛\n()]{0,40}'
    r'|القراءة\s+الشاذة[^،.؛\n()]{0,35}'
    r'|قراءة\s+(?:الرفع|النصب|الجر|الخفض|الجزم|الفتح|الكسر|الضم|التشديد|التخفيف|التاء|الياء|النون|الخطاب|الغيبة|الإفراد|الجمع|التذكير|التأنيث)[^،.؛\n()]{0,30}'
    r'|(?:بالرفع|بالنصب|بالجر|بالخفض|بالتاء|بالياء|بالنون)\s+في\s+قراءة[^،.؛\n()]{0,35})',
  );

  /// Extracted Qira'at cue when this specific demo illustrates a different Qira'ah.
  String? get qiraatCue {
    for (final src in <String?>[
      attributedTo,
      meaningAtWaqf,
      meaningAtIbtida,
      meaningIfConnected,
    ]) {
      if (src == null || src.isEmpty) continue;
      final m = _demoQiraatCuePattern.firstMatch(src);
      if (m != null) {
        return m.group(0)!.trim();
      }
    }
    return null;
  }

  bool get isQiraatDemo => qiraatCue != null || qiraatOverrides.isNotEmpty;

  int resolvedWaqfEndAyah(int stopAyah) => waqfEndAyah ?? stopAyah;
  int resolvedWaqfStartAyah(int stopAyah) =>
      waqfStartAyah ?? resolvedWaqfEndAyah(stopAyah);

  int resolvedIbtidaStartAyah(int stopAyah) => ibtidaStartAyah ?? stopAyah;
  int resolvedIbtidaEndAyah(int stopAyah) =>
      ibtidaEndAyah ?? resolvedIbtidaStartAyah(stopAyah);

  bool spansOtherAyahs(int stopAyah) {
    final hasWaqf = waqfSegmentWords != null && waqfSegmentWords!.length >= 2;
    if (hasWaqf &&
        (resolvedWaqfStartAyah(stopAyah) != stopAyah ||
            resolvedWaqfEndAyah(stopAyah) != stopAyah)) {
      return true;
    }
    final hasIbtida =
        ibtidaSegmentWords != null && ibtidaSegmentWords!.length >= 2;
    if (hasIbtida &&
        (resolvedIbtidaStartAyah(stopAyah) != stopAyah ||
            resolvedIbtidaEndAyah(stopAyah) != stopAyah)) {
      return true;
    }
    return false;
  }

  (int minAyah, int maxAyah) ayahExtent(int stopAyah) {
    var minA = stopAyah;
    var maxA = stopAyah;
    if (waqfSegmentWords != null && waqfSegmentWords!.length >= 2) {
      final ws = resolvedWaqfStartAyah(stopAyah);
      final we = resolvedWaqfEndAyah(stopAyah);
      if (ws < minA) minA = ws;
      if (we < minA) minA = we;
      if (ws > maxA) maxA = ws;
      if (we > maxA) maxA = we;
    }
    if (ibtidaSegmentWords != null && ibtidaSegmentWords!.length >= 2) {
      final isA = resolvedIbtidaStartAyah(stopAyah);
      final ie = resolvedIbtidaEndAyah(stopAyah);
      if (isA < minA) minA = isA;
      if (ie < minA) minA = ie;
      if (isA > maxA) maxA = isA;
      if (ie > maxA) maxA = ie;
    }
    return (minA, maxA);
  }

  static String _normalizedSpanPart(
    List<int>? span,
    int startAyah,
    int endAyah,
  ) {
    if (span == null || span.length < 2) return '-';
    final sWord = span[0];
    final eWord = span[1];
    final reversed = compareWordCoord(startAyah, sWord, endAyah, eWord) > 0;
    final loA = reversed ? endAyah : startAyah;
    final loW = reversed ? eWord : sWord;
    final hiA = reversed ? startAyah : endAyah;
    final hiW = reversed ? sWord : eWord;
    return '$loA:$loW..$hiA:$hiW';
  }

  /// Canonical signature of the highlighted `(waqf, ibtida)` spans for [stopAyah].
  String spanKeyForStop(int stopAyah) {
    final wPart = _normalizedSpanPart(
      waqfSegmentWords,
      resolvedWaqfStartAyah(stopAyah),
      resolvedWaqfEndAyah(stopAyah),
    );
    final iPart = _normalizedSpanPart(
      ibtidaSegmentWords,
      resolvedIbtidaStartAyah(stopAyah),
      resolvedIbtidaEndAyah(stopAyah),
    );
    return '$wPart|$iPart';
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
    this.qiraatBasis,
    this.qiraatNote,
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

  /// Optional Qira'at classification:
  /// - `non_hafs_only`: ruling relies on a non-Hafs Qira'ah
  /// - `varies_by_qiraat`: ruling differs across Qira'at
  /// - `hafs_and_others`: mentions another Qira'ah; stop holds on Hafs
  final String? qiraatBasis;
  final String? qiraatNote;

  final List<WaqfDemoAndMeaning> demosAndMeanings;

  static final RegExp _commentQiraatPattern = RegExp(
    r'((?:على|في)\s+قراءة\s+[^،.؛\n()]{2,45}'
    r'|(?:على|في)\s+قراءتي\s+[^،.؛\n()]{2,45}'
    r'|(?:على|في)\s+القراءتين'
    r'|قراءة\s+(?:مَن|من)\s+قرأ[^،.؛\n()]{0,35}'
    r'|(?:و|ف)?(?:مَن|من|لمن)\s+قرأ\s+[^،.؛\n()]{2,40}'
    r'|وروى\s+المفضل[^،.؛\n()]{0,40}'
    r'|القراءة\s+الشاذة|قرئ\s+شاذ[ًا]?'
    r'|تعدد\s+القراءات|اختلاف\s+القراء)',
  );

  String? get inferredQiraatCue {
    for (final d in demosAndMeanings) {
      final cue = d.qiraatCue;
      if (cue != null && cue.isNotEmpty) return cue;
    }
    final c = comment;
    if (c != null && c.isNotEmpty) {
      final m = _commentQiraatPattern.firstMatch(c);
      if (m != null) return m.group(0)!.trim();
    }
    return null;
  }

  String? get effectiveQiraatNote {
    final explicit = qiraatNote?.trim();
    if (explicit != null && explicit.isNotEmpty) return explicit;
    return inferredQiraatCue;
  }

  bool get hasQiraatInfo =>
      (qiraatBasis != null && qiraatBasis!.isNotEmpty) ||
      (qiraatNote != null && qiraatNote!.isNotEmpty) ||
      inferredQiraatCue != null ||
      demosAndMeanings.any((d) => d.isQiraatDemo);

  bool get isQiraatDependent =>
      qiraatBasis == 'non_hafs_only' ||
      qiraatBasis == 'varies_by_qiraat' ||
      inferredQiraatCue != null ||
      demosAndMeanings.any((d) => d.qiraatOverrides.isNotEmpty);

  String? get qiraatBadgeLabel {
    switch (qiraatBasis) {
      case 'non_hafs_only':
        return 'على قراءة أخرى';
      case 'varies_by_qiraat':
        return 'يختلف باختلاف القراءات';
      case 'hafs_and_others':
        return 'موافق لحفص (مع ذكر قراءة)';
      default:
        return hasQiraatInfo ? 'قراءات' : null;
    }
  }

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
    this.uthmaniMark,
    this.uthmaniMarkName,
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
  final String? uthmaniMark;
  final String? uthmaniMarkName;
  final bool isVerseEnd;

  /// Page in علل الوقوف (matches page_N.png).
  final int? textPage;

  bool hasScholar(String scholarName) {
    return opinions.any((o) => o.scholar == scholarName);
  }

  /// True when any scholar opinion or demo on this stop relates to Qira'at.
  bool get hasQiraatVariation => opinions.any((o) => o.hasQiraatInfo);

  /// True when the Uthmani Mushaf mark at this position is non-allowed (`لا` / `ممنوع`).
  /// False when Uthmani marks it as allowed of any rank (`مـ`, `قلى`, `ج`, `صلى`, `∴`, `س`).
  bool get isUthmaniNonAllowed {
    final m = uthmaniMark?.trim() ?? '';
    final n = uthmaniMarkName?.trim() ?? '';
    return m == 'لا' || m == 'LA' || n == 'ممنوع';
  }

  /// True when this stop is neither in the Uthmani Mushaf nor at a verse end,
  /// or both are on the same position (including verse ends, which Uthmani
  /// treats as allowed stops unless marked `لا`) and at least one opinion face
  /// on this stop (even if `isQila`) has the opposite allowed vs. non-allowed
  /// ruling to the Uthmani Mushaf.
  bool get differsFromUthmani {
    if (!inUthmaniMushaf && !isVerseEnd) return true;
    final uthmaniNonAllowed = isUthmaniNonAllowed;
    if (opinions.isEmpty) {
      final fallbackNonAllowed = (fallbackSymbol == StopSymbol.la) ||
          (fallbackLabel?.contains('لا يوقف') ?? false) ||
          (fallbackLabel?.trim() == 'لا');
      return uthmaniNonAllowed ? !fallbackNonAllowed : fallbackNonAllowed;
    }
    for (final op in opinions) {
      final count = [
        op.verdicts.length,
        op.symbols.length,
        op.verdictLabels.length,
      ].reduce((a, b) => a > b ? a : b);
      final faces = count > 0 ? count : 1;
      for (var i = 0; i < faces; i++) {
        final v = i < op.verdicts.length ? op.verdicts[i] : op.primaryVerdict;
        final sym = i < op.symbols.length ? op.symbols[i] : op.primarySymbol;
        final lbl = i < op.verdictLabels.length
            ? op.verdictLabels[i]
            : op.primaryVerdictLabel;
        final faceNonAllowed = v.trim().contains('لا يوقف') ||
            lbl.trim() == 'لا' ||
            sym == StopSymbol.la;
        if (uthmaniNonAllowed && !faceNonAllowed) {
          return true;
        }
        if (!uthmaniNonAllowed && faceNonAllowed) {
          return true;
        }
      }
    }
    return false;
  }

  /// True when, across all opinion faces, at least one face allows stopping
  /// and at least one face says `لا يوقف` (scholars disagree on allowed vs not).
  bool get hasAllowedVsNonAllowedDisagreement {
    var allowed = false;
    var nonAllowed = false;
    for (final op in opinions) {
      final count = [
        op.verdicts.length,
        op.symbols.length,
        op.verdictLabels.length,
      ].reduce((a, b) => a > b ? a : b);
      final faces = count > 0 ? count : 1;
      for (var i = 0; i < faces; i++) {
        final v = i < op.verdicts.length ? op.verdicts[i] : op.primaryVerdict;
        final sym = i < op.symbols.length ? op.symbols[i] : op.primarySymbol;
        final lbl = i < op.verdictLabels.length
            ? op.verdictLabels[i]
            : op.primaryVerdictLabel;
        final faceNonAllowed = v.trim().contains('لا يوقف') ||
            lbl.trim() == 'لا' ||
            sym == StopSymbol.la;
        if (faceNonAllowed) {
          nonAllowed = true;
        } else {
          allowed = true;
        }
        if (allowed && nonAllowed) return true;
      }
    }
    return false;
  }

  /// True when any opinion face on this stop is reported with «قيل».
  bool get hasQilaFace => opinions.any((o) => o.isQila.any((q) => q));

  /// Highest stop degree across all opinion faces (the «الكل» verdict) as a
  /// base rank: 60 لازم, 50 تام, 40 كاف, 30 حسن, 25 جائز, 20 صالح,
  /// 10 قيل فيه وقف, 5 غير محسوم, 0 لا يوقف.
  int get highestDegreeBase {
    final best = _bestFaceForScholar(null);
    if (best == null) {
      return _verdictDegreeRank(
            fallbackLabel ?? '',
            '',
            fallbackSymbol ?? StopSymbol.unsettled,
            false,
          ) ~/
          2;
    }
    final op = best.opinion;
    final i = best.faceIndex;
    final v = i < op.verdicts.length ? op.verdicts[i] : op.primaryVerdict;
    final sym = i < op.symbols.length ? op.symbols[i] : op.primarySymbol;
    final lbl =
        i < op.verdictLabels.length ? op.verdictLabels[i] : op.primaryVerdictLabel;
    final qila = i < op.isQila.length ? op.isQila[i] : op.primaryIsQila;
    return _verdictDegreeRank(v, lbl, sym, qila) ~/ 2;
  }

  /// Ranks a stop face by degree of stop (higher = stronger stop):
  /// لازم > تام > كاف > حسن > جائز > صالح > قيل فيه وقف > لا يوقف,
  /// with direct rulings (`isQila == false`) preferred over `قيل` at the same degree.
  static int _verdictDegreeRank(
    String verdict,
    String verdictLabel,
    StopSymbol sym,
    bool qila,
  ) {
    final v = verdict.trim();
    final lbl = verdictLabel.trim();
    int base;
    if (v.contains('لازم') || lbl == 'م') {
      base = 60;
    } else if (v.contains('تام') || lbl == 'ط') {
      base = 50;
    } else if (v.contains('كاف')) {
      base = 40;
    } else if (v.contains('حسن') || lbl == 'ص') {
      base = 30;
    } else if (v.contains('جائز') || lbl == 'ج') {
      base = 25;
    } else if (v.contains('صالح') || lbl == 'ز') {
      base = 20;
    } else if (v.contains('قيل فيه وقف') || lbl == 'ق') {
      base = 10;
    } else if (v.contains('لا يوقف') || lbl == 'لا' || sym == StopSymbol.la) {
      base = 0;
    } else {
      switch (sym) {
        case StopSymbol.tam:
          base = 50;
        case StopSymbol.jaiz:
          base = 25;
        case StopSymbol.mujawwaz:
          base = 20;
        case StopSymbol.la:
          base = 0;
        case StopSymbol.unsettled:
          base = 5;
      }
    }
    return base * 2 + (qila ? 0 : 1);
  }

  /// Finds the `(ScholarOpinion, faceIndex)` with the highest stop degree across
  /// all opinions (when `scholarName == null` / empty) or the primary face for a specific scholar.
  ({ScholarOpinion opinion, int faceIndex})? _bestFaceForScholar(
    String? scholarName,
  ) {
    if (opinions.isEmpty) return null;
    if (scholarName != null && scholarName.isNotEmpty) {
      for (final op in opinions) {
        if (op.scholar == scholarName) {
          return (opinion: op, faceIndex: 0);
        }
      }
      return (opinion: opinions.first, faceIndex: 0);
    }

    ScholarOpinion? bestOp;
    int bestIdx = 0;
    int bestRank = -1;

    for (final op in opinions) {
      final count = [
        op.verdicts.length,
        op.symbols.length,
        op.verdictLabels.length,
        op.isQila.length,
      ].reduce((a, b) => a > b ? a : b);
      final faces = count > 0 ? count : 1;
      for (int i = 0; i < faces; i++) {
        final v = i < op.verdicts.length ? op.verdicts[i] : op.primaryVerdict;
        final sym = i < op.symbols.length ? op.symbols[i] : op.primarySymbol;
        final lbl = i < op.verdictLabels.length
            ? op.verdictLabels[i]
            : op.primaryVerdictLabel;
        final qila = i < op.isQila.length ? op.isQila[i] : op.primaryIsQila;
        final rank = _verdictDegreeRank(v, lbl, sym, qila);
        if (rank > bestRank) {
          bestRank = rank;
          bestOp = op;
          bestIdx = i;
        }
      }
    }

    if (bestOp == null) return (opinion: opinions.first, faceIndex: 0);
    return (opinion: bestOp, faceIndex: bestIdx);
  }

  /// Resolves the opinion to display for a chosen scholar filter.
  /// If `scholarName == null` ("الكل"), returns the opinion holding the highest stop degree.
  ScholarOpinion? opinionForScholar(String? scholarName) {
    return _bestFaceForScholar(scholarName)?.opinion;
  }

  StopSymbol symbolForScholar(String? scholarName) {
    final best = _bestFaceForScholar(scholarName);
    if (best != null) {
      final op = best.opinion;
      final i = best.faceIndex;
      return i < op.symbols.length ? op.symbols[i] : op.primarySymbol;
    }
    return fallbackSymbol ?? StopSymbol.jaiz;
  }

  String verdictLabelForScholar(String? scholarName) {
    final best = _bestFaceForScholar(scholarName);
    if (best != null) {
      final op = best.opinion;
      final i = best.faceIndex;
      return i < op.verdictLabels.length
          ? op.verdictLabels[i]
          : op.primaryVerdictLabel;
    }
    return defaultVerdictLabelForSymbol(symbol);
  }

  bool isQilaForScholar(String? scholarName) {
    final best = _bestFaceForScholar(scholarName);
    if (best != null) {
      final op = best.opinion;
      final i = best.faceIndex;
      return i < op.isQila.length ? op.isQila[i] : op.primaryIsQila;
    }
    return false;
  }

  String labelForScholar(String? scholarName) {
    if (scholarName != null && scholarName.isNotEmpty) {
      final op = opinionForScholar(scholarName);
      if (op != null) {
        return op.verdicts.join(' / ');
      }
    } else {
      final best = _bestFaceForScholar(null);
      if (best != null) {
        final op = best.opinion;
        final i = best.faceIndex;
        return i < op.verdicts.length ? op.verdicts[i] : op.primaryVerdict;
      }
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

int compareWordCoord(int ayahA, int wordA, int ayahB, int wordB) {
  if (ayahA != ayahB) return ayahA.compareTo(ayahB);
  return wordA.compareTo(wordB);
}

bool wordInAyahSpan({
  required List<int>? span,
  required int wordIndex,
  int? ayahNumber,
  int? startAyah,
  int? endAyah,
}) {
  if (span == null || span.length < 2 || wordIndex < 1) return false;
  final sWord = span[0];
  final eWord = span[1];
  if (ayahNumber == null || startAyah == null || endAyah == null) {
    return sWord > eWord
        ? (wordIndex >= eWord && wordIndex <= sWord)
        : (wordIndex >= sWord && wordIndex <= eWord);
  }
  if (startAyah == endAyah) {
    if (ayahNumber != startAyah) return false;
    return sWord > eWord
        ? (wordIndex >= eWord && wordIndex <= sWord)
        : (wordIndex >= sWord && wordIndex <= eWord);
  }
  final reversed = compareWordCoord(startAyah, sWord, endAyah, eWord) > 0;
  final loA = reversed ? endAyah : startAyah;
  final loW = reversed ? eWord : sWord;
  final hiA = reversed ? startAyah : endAyah;
  final hiW = reversed ? sWord : eWord;
  return compareWordCoord(ayahNumber, wordIndex, loA, loW) >= 0 &&
      compareWordCoord(ayahNumber, wordIndex, hiA, hiW) <= 0;
}

bool wordIndexInSpan(List<int>? span, int wordIndex) =>
    wordInAyahSpan(span: span, wordIndex: wordIndex);

DemoSegmentRole demoSegmentRoleForWord({
  required WaqfDemoAndMeaning? demo,
  required int wordIndex,
  int? ayahNumber,
  int? stopAyah,
}) {
  if (demo == null) return DemoSegmentRole.none;
  if (wordInAyahSpan(
    span: demo.waqfSegmentWords,
    wordIndex: wordIndex,
    ayahNumber: ayahNumber,
    startAyah: stopAyah == null ? null : demo.resolvedWaqfStartAyah(stopAyah),
    endAyah: stopAyah == null ? null : demo.resolvedWaqfEndAyah(stopAyah),
  )) {
    return DemoSegmentRole.waqf;
  }
  if (wordInAyahSpan(
    span: demo.ibtidaSegmentWords,
    wordIndex: wordIndex,
    ayahNumber: ayahNumber,
    startAyah: stopAyah == null ? null : demo.resolvedIbtidaStartAyah(stopAyah),
    endAyah: stopAyah == null ? null : demo.resolvedIbtidaEndAyah(stopAyah),
  )) {
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
