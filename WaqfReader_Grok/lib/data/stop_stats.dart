import '../models/waqf_models.dart';

/// One labelled count in a statistics breakdown.
class StatCount {
  const StatCount(this.label, this.count, {this.symbol});

  final String label;
  final int count;

  /// Optional short mark shown before the label (e.g. `ط`, `قلى`).
  final String? symbol;
}

/// Per-scholar coverage: how many stops a scholar rules on, split by the
/// scholar's primary ruling (allowed vs `لا يوقف`).
class ScholarStat {
  const ScholarStat({
    required this.scholar,
    required this.total,
    required this.allowed,
    required this.notAllowed,
    required this.withQila,
  });

  final String scholar;
  final int total;
  final int allowed;
  final int notAllowed;
  final int withQila;
}

/// Per-surah summary row for the whole-Mushaf view.
class SurahStatRow {
  const SurahStatRow({
    required this.number,
    required this.name,
    required this.total,
    required this.differsFromUthmani,
    required this.multiDemo,
  });

  final int number;
  final String name;
  final int total;
  final int differsFromUthmani;
  final int multiDemo;
}

/// Aggregate statistics over a set of waqf stops.
class StopStats {
  const StopStats({
    required this.total,
    required this.inUthmani,
    required this.verseEnd,
    required this.midAyah,
    required this.differsFromUthmani,
    required this.agreesWithUthmani,
    required this.withDemos,
    required this.multiDemo,
    required this.crossAyahDemo,
    required this.scholarDisagreement,
    required this.withQila,
    required this.qiraatDependent,
    required this.byDegree,
    required this.byUthmaniMark,
    required this.byScholar,
    this.surahRows = const [],
  });

  final int total;
  final int inUthmani;
  final int verseEnd;
  final int midAyah;
  final int differsFromUthmani;
  final int agreesWithUthmani;
  final int withDemos;
  final int multiDemo;
  final int crossAyahDemo;
  final int scholarDisagreement;
  final int withQila;
  final int qiraatDependent;
  final List<StatCount> byDegree;
  final List<StatCount> byUthmaniMark;
  final List<ScholarStat> byScholar;
  final List<SurahStatRow> surahRows;

  /// Degree buckets in display order (strongest → weakest), keyed by
  /// [WaqfStop.highestDegreeBase].
  static const List<(int, String, String)> degreeBuckets = [
    (60, 'لازم', 'م'),
    (50, 'تام', 'ط'),
    (40, 'كاف', 'ك'),
    (30, 'حسن', 'ص'),
    (25, 'جائز', 'ج'),
    (20, 'صالح', 'ز'),
    (10, 'قيل فيه وقف', 'ق'),
    (5, 'غير محسوم', '؟'),
    (0, 'لا يوقف', 'لا'),
  ];

  static const List<String> _scholarOrder = [
    'السجاوندي',
    'الأشموني',
    'الداني',
    'ابن الأنباري',
    'النحاس',
  ];

  static bool _faceNonAllowed(ScholarOpinion op, int i) {
    final v = i < op.verdicts.length ? op.verdicts[i] : op.primaryVerdict;
    final sym = i < op.symbols.length ? op.symbols[i] : op.primarySymbol;
    final lbl =
        i < op.verdictLabels.length ? op.verdictLabels[i] : op.primaryVerdictLabel;
    return v.trim().contains('لا يوقف') ||
        lbl.trim() == 'لا' ||
        sym == StopSymbol.la;
  }

  /// Number of distinct-span demo variants across all scholars on [stop].
  static int distinctDemoSpans(WaqfStop stop) {
    final keys = <String>{};
    for (final op in stop.opinions) {
      for (final d in op.demosAndMeanings) {
        keys.add(d.spanKeyForStop(stop.ayah));
      }
    }
    return keys.length;
  }

  static StopStats compute(
    Iterable<WaqfStop> stops, {
    List<SurahStatRow> surahRows = const [],
  }) {
    var total = 0;
    var inUthmani = 0;
    var verseEnd = 0;
    var differs = 0;
    var withDemos = 0;
    var multiDemo = 0;
    var crossAyah = 0;
    var disagreement = 0;
    var withQila = 0;
    var qiraat = 0;
    final degree = <int, int>{};
    final marks = <String, (String, String?, int)>{};
    final scholarTotals = <String, List<int>>{};

    for (final s in stops) {
      total++;
      if (s.inUthmaniMushaf) {
        inUthmani++;
        final mark = s.uthmaniMark?.trim() ?? '';
        final name = s.uthmaniMarkName?.trim() ?? '';
        final key = mark.isEmpty ? (name.isEmpty ? '؟' : name) : mark;
        final prev = marks[key];
        marks[key] = (
          name.isEmpty ? (mark.isEmpty ? 'غير محدد' : mark) : name,
          mark.isEmpty ? null : mark,
          (prev?.$3 ?? 0) + 1,
        );
      }
      if (s.isVerseEnd) verseEnd++;
      if (s.differsFromUthmani) differs++;
      if (s.hasDemosAndMeanings) {
        withDemos++;
        if (distinctDemoSpans(s) > 1) multiDemo++;
        final crosses = s.opinions.any(
          (o) => o.demosAndMeanings.any((d) => d.spansOtherAyahs(s.ayah)),
        );
        if (crosses) crossAyah++;
      }
      if (s.hasAllowedVsNonAllowedDisagreement) disagreement++;
      if (s.hasQilaFace) withQila++;
      if (s.hasQiraatVariation) qiraat++;

      final base = s.highestDegreeBase;
      degree[base] = (degree[base] ?? 0) + 1;

      final seenScholars = <String>{};
      for (final op in s.opinions) {
        if (!seenScholars.add(op.scholar)) continue;
        final row = scholarTotals.putIfAbsent(op.scholar, () => [0, 0, 0, 0]);
        row[0]++;
        if (_faceNonAllowed(op, 0)) {
          row[2]++;
        } else {
          row[1]++;
        }
        if (op.isQila.any((q) => q)) row[3]++;
      }
    }

    final byDegree = <StatCount>[
      for (final b in degreeBuckets)
        if ((degree[b.$1] ?? 0) > 0) StatCount(b.$2, degree[b.$1]!, symbol: b.$3),
    ];

    final byMark = [
      for (final e in marks.values) StatCount(e.$1, e.$3, symbol: e.$2),
    ]..sort((a, b) => b.count.compareTo(a.count));

    final scholarNames = scholarTotals.keys.toList()
      ..sort((a, b) {
        final ia = _scholarOrder.indexOf(a);
        final ib = _scholarOrder.indexOf(b);
        if (ia >= 0 && ib >= 0) return ia.compareTo(ib);
        if (ia >= 0) return -1;
        if (ib >= 0) return 1;
        return scholarTotals[b]![0].compareTo(scholarTotals[a]![0]);
      });

    return StopStats(
      total: total,
      inUthmani: inUthmani,
      verseEnd: verseEnd,
      midAyah: total - verseEnd,
      differsFromUthmani: differs,
      agreesWithUthmani: total - differs,
      withDemos: withDemos,
      multiDemo: multiDemo,
      crossAyahDemo: crossAyah,
      scholarDisagreement: disagreement,
      withQila: withQila,
      qiraatDependent: qiraat,
      byDegree: byDegree,
      byUthmaniMark: byMark,
      byScholar: [
        for (final name in scholarNames)
          ScholarStat(
            scholar: name,
            total: scholarTotals[name]![0],
            allowed: scholarTotals[name]![1],
            notAllowed: scholarTotals[name]![2],
            withQila: scholarTotals[name]![3],
          ),
      ],
      surahRows: surahRows,
    );
  }
}
