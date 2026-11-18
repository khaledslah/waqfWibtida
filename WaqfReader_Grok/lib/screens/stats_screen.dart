import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../data/stop_stats.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';

/// Statistics of waqf stops and their types, for the current surah or the
/// whole Mushaf, rendered with circular canvas gauges and donut rings.
class StopStatsScreen extends StatefulWidget {
  const StopStatsScreen({super.key, required this.controller});

  final ReaderController controller;

  /// Whole-Mushaf stats are expensive (all 114 feeds); compute once per session.
  static StopStats? _quranCache;

  @override
  State<StopStatsScreen> createState() => _StopStatsScreenState();
}

class _StopStatsScreenState extends State<StopStatsScreen> {
  int _scope = 0; // 0 = current surah, 1 = whole Mushaf.
  bool _loadingQuran = false;
  int _loadedSurahs = 0;

  int? _surahStatsFor;
  StopStats? _surahStats;

  StopStats _currentSurahStats() {
    final c = widget.controller;
    if (_surahStats == null || _surahStatsFor != c.currentSurah) {
      _surahStats = StopStats.compute(c.sampleStops);
      _surahStatsFor = c.currentSurah;
    }
    return _surahStats!;
  }

  Future<void> _loadQuran() async {
    if (StopStatsScreen._quranCache != null || _loadingQuran) return;
    setState(() {
      _loadingQuran = true;
      _loadedSurahs = 0;
    });
    final all = <WaqfStop>[];
    final rows = <SurahStatRow>[];
    for (final entry in widget.controller.catalog) {
      if (!mounted) return;
      try {
        final bundle = await AppFeedBundle.loadAsset(entry.asset);
        all.addAll(bundle.stops);
        var extra = 0;
        var multi = 0;
        for (final s in bundle.stops) {
          if (s.differsFromUthmani) extra++;
          if (StopStats.distinctDemoSpans(s) > 1) multi++;
        }
        rows.add(
          SurahStatRow(
            number: entry.number,
            name: entry.name,
            total: bundle.stops.length,
            differsFromUthmani: extra,
            multiDemo: multi,
          ),
        );
      } catch (_) {}
      if (mounted) setState(() => _loadedSurahs++);
      await Future<void>.delayed(Duration.zero);
    }
    StopStatsScreen._quranCache = StopStats.compute(all, surahRows: rows);
    if (mounted) setState(() => _loadingQuran = false);
  }

  void _setScope(int scope) {
    setState(() => _scope = scope);
    if (scope == 1) _loadQuran();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    final surahName = c.currentSurahName.replaceFirst(RegExp(r'^سورة\s*'), '');
    final catalogCount = c.catalog.length;

    Widget body;
    if (_scope == 0) {
      body = _StatsView(
        key: const ValueKey('stats-surah'),
        stats: _currentSurahStats(),
      );
    } else if (StopStatsScreen._quranCache != null) {
      body = _StatsView(
        key: const ValueKey('stats-quran'),
        stats: StopStatsScreen._quranCache!,
      );
    } else {
      final progress = catalogCount == 0 ? 0.0 : _loadedSurahs / catalogCount;
      body = Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 96,
                height: 96,
                child: CustomPaint(
                  painter: _RadialGaugePainter(
                    fraction: progress,
                    color: AppColors.forest,
                    trackColor: AppColors.hairline,
                    strokeWidth: 8,
                    ornamentalOuter: true,
                  ),
                  child: Center(
                    child: Text(
                      _percent(_loadedSurahs, catalogCount),
                      textDirection: TextDirection.ltr,
                      style: AppText.ui(
                        size: 16,
                        weight: FontWeight.w800,
                        color: AppColors.forestDeep,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'جارٍ حساب إحصائيات المصحف… '
                '${arabicDigits(_loadedSurahs)} / ${arabicDigits(catalogCount)}',
                textAlign: TextAlign.center,
                style: AppText.ui(size: 14, color: AppColors.forestDeep),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppColors.parchment,
      appBar: AppBar(
        backgroundColor: AppColors.parchment,
        surfaceTintColor: Colors.transparent,
        foregroundColor: AppColors.forestDeep,
        elevation: 0,
        title: Text(
          'إحصائيات الوقوف',
          style: AppText.ui(
            size: 18,
            weight: FontWeight.w800,
            color: AppColors.forestDeep,
          ),
        ),
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
            child: Row(
              children: [
                Expanded(
                  child: _UnderlineScopeTab(
                    label: surahName.isEmpty ? 'هذه السورة' : 'سورة $surahName',
                    selected: _scope == 0,
                    onTap: () => _setScope(0),
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: _UnderlineScopeTab(
                    label: 'المصحف كاملاً',
                    selected: _scope == 1,
                    onTap: () => _setScope(1),
                  ),
                ),
              ],
            ),
          ),
          Expanded(child: body),
        ],
      ),
    );
  }
}

class _StatsView extends StatelessWidget {
  const _StatsView({super.key, required this.stats});

  final StopStats stats;

  static Color _colorForDegree(String label) {
    switch (label) {
      case 'لازم':
        return AppColors.forestDeep;
      case 'تام':
        return AppColors.forest;
      case 'كاف':
        return const Color(0xFF2D7A62);
      case 'حسن':
        return const Color(0xFF4F967E);
      case 'جائز':
        return AppColors.gold;
      case 'صالح':
        return AppColors.goldSoft;
      case 'قيل فيه وقف':
        return AppColors.badgeAmber;
      case 'غير محسوم':
        return AppColors.muted;
      case 'لا يوقف':
        return const Color(0xFFB0574B);
      default:
        return AppColors.forest;
    }
  }

  static Color _colorForMark(String? symbol) {
    switch (symbol?.trim()) {
      case 'مـ':
        return AppColors.forestDeep;
      case 'قلى':
        return AppColors.forest;
      case 'ج':
        return AppColors.gold;
      case 'صلى':
        return AppColors.goldSoft;
      case 'لا':
        return const Color(0xFFB0574B);
      case '∴':
        return const Color(0xFF4F967E);
      case 'س':
        return AppColors.badgeAmber;
      default:
        return AppColors.gold;
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = stats;
    if (s.total == 0) {
      return Center(
        child: Text(
          'لا توجد وقوف',
          style: AppText.ui(size: 15, color: AppColors.muted),
        ),
      );
    }

    final degreeSlices = <_DonutSlice>[
      for (final d in s.byDegree)
        _DonutSlice(
          value: d.count.toDouble(),
          color: _colorForDegree(d.label),
        ),
    ];

    final mushafSlices = <_DonutSlice>[
      _DonutSlice(
        value: s.differsFromUthmani.toDouble(),
        color: AppColors.gold,
      ),
      _DonutSlice(
        value: s.agreesWithUthmani.toDouble(),
        color: AppColors.approve,
      ),
    ];

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
      children: [
        // 1. Hero circular donut canvas + 4 circular summary gauges.
        _Section(
          title: 'درجات الوقف',
          subtitle: 'توزيع المواضع وفق أعلى درجة وقف قال بها أحد العلماء (الكل)',
          children: [
            const SizedBox(height: 6),
            Center(
              child: SizedBox(
                width: 196,
                height: 196,
                child: CustomPaint(
                  painter: _MultiSegmentDonutPainter(
                    slices: degreeSlices,
                    strokeWidth: 20,
                    ornamentalOuter: true,
                  ),
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          arabicDigits(s.total),
                          style: AppText.ui(
                            size: 28,
                            weight: FontWeight.w800,
                            color: AppColors.forestDeep,
                            height: 1.1,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'إجمالي الوقوف',
                          style: AppText.ui(
                            size: 12,
                            weight: FontWeight.w700,
                            color: AppColors.muted,
                            height: 1.2,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _SummaryRingTile(
                    label: 'زائدة عن المصحف',
                    value: s.differsFromUthmani,
                    total: s.total,
                    color: AppColors.gold,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _SummaryRingTile(
                    label: 'في المصحف العثماني',
                    value: s.inUthmani,
                    total: s.total,
                    color: AppColors.forest,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: _SummaryRingTile(
                    label: 'متعددة الأمثلة',
                    value: s.multiDemo,
                    total: s.total,
                    color: const Color(0xFF2D7A62),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _SummaryRingTile(
                    label: 'رؤوس الآي',
                    value: s.verseEnd,
                    total: s.total,
                    color: AppColors.goldSoft,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Divider(color: AppColors.hairline.withOpacity(0.8), height: 1),
            const SizedBox(height: 12),
            _PairedGrid(
              items: [
                for (final d in s.byDegree)
                  _DegreeRingItem(
                    label: d.label,
                    symbol: d.symbol,
                    count: d.count,
                    total: s.total,
                    color: _colorForDegree(d.label),
                  ),
              ],
            ),
          ],
        ),

        // 2. Relationship to Uthmani Mushaf marks (circular split ring + mark medallions).
        _Section(
          title: 'العلاقة بعلامات المصحف العثماني',
          subtitle:
              'وقوف زائدة في كتب الوقف والابتداء أو فيها تفصيل إضافي عند علامة المصحف',
          children: [
            const SizedBox(height: 6),
            Row(
              children: [
                SizedBox(
                  width: 112,
                  height: 112,
                  child: CustomPaint(
                    painter: _MultiSegmentDonutPainter(
                      slices: mushafSlices,
                      strokeWidth: 13,
                      ornamentalOuter: true,
                    ),
                    child: Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            _percent(s.differsFromUthmani, s.total),
                            textDirection: TextDirection.ltr,
                            style: AppText.ui(
                              size: 18,
                              weight: FontWeight.w800,
                              color: AppColors.forestDeep,
                              height: 1.1,
                            ),
                          ),
                          Text(
                            'زائدة',
                            style: AppText.ui(
                              size: 11,
                              color: AppColors.muted,
                              height: 1.2,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _LegendCountRow(
                        label: 'زائدة عن المصحف',
                        count: s.differsFromUthmani,
                        total: s.total,
                        color: AppColors.gold,
                      ),
                      const SizedBox(height: 10),
                      _LegendCountRow(
                        label: 'موافقة للمصحف',
                        count: s.agreesWithUthmani,
                        total: s.total,
                        color: AppColors.approve,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (s.byUthmaniMark.isNotEmpty) ...[
              const SizedBox(height: 14),
              Divider(color: AppColors.hairline.withOpacity(0.8), height: 1),
              const _SubHeader('علامات الوقف في المصحف العثماني'),
              const SizedBox(height: 8),
              Center(
                child: Wrap(
                  spacing: 10,
                  runSpacing: 12,
                  alignment: WrapAlignment.center,
                  children: [
                    for (final m in s.byUthmaniMark)
                      _CircularMetricPod(
                        label: m.label,
                        centerText: m.symbol ?? '؟',
                        count: m.count,
                        total: s.inUthmani,
                        color: _colorForMark(m.symbol),
                        diameter: 58,
                        strokeWidth: 6,
                        centerIsSymbol: true,
                      ),
                  ],
                ),
              ),
            ],
          ],
        ),

        // 3. Positions & applied examples as circular radial pods.
        _Section(
          title: 'موضع الوقف والأمثلة التطبيقية',
          children: [
            const SizedBox(height: 8),
            Center(
              child: Wrap(
                spacing: 12,
                runSpacing: 14,
                alignment: WrapAlignment.center,
                children: [
                  _CircularMetricPod(
                    label: 'رؤوس الآي',
                    centerText: _percent(s.verseEnd, s.total),
                    centerLtr: true,
                    count: s.verseEnd,
                    total: s.total,
                    color: AppColors.forest,
                  ),
                  _CircularMetricPod(
                    label: 'وسط الآية',
                    centerText: _percent(s.midAyah, s.total),
                    centerLtr: true,
                    count: s.midAyah,
                    total: s.total,
                    color: const Color(0xFF2D7A62),
                  ),
                  _CircularMetricPod(
                    label: 'لها أمثلة ومعانٍ',
                    centerText: _percent(s.withDemos, s.total),
                    centerLtr: true,
                    count: s.withDemos,
                    total: s.total,
                    color: AppColors.forestDeep,
                  ),
                  _CircularMetricPod(
                    label: 'متعددة الأمثلة',
                    centerText: _percent(s.multiDemo, s.total),
                    centerLtr: true,
                    count: s.multiDemo,
                    total: s.total,
                    color: AppColors.gold,
                  ),
                  _CircularMetricPod(
                    label: 'تمتد عبر الآيات',
                    centerText: _percent(s.crossAyahDemo, s.total),
                    centerLtr: true,
                    count: s.crossAyahDemo,
                    total: s.total,
                    color: AppColors.goldSoft,
                  ),
                ],
              ),
            ),
          ],
        ),

        // 4. Multiplicity of rulings & qiraat.
        _Section(
          title: 'تعدد الأقوال والوجوه',
          subtitle: 'مواضع تتنوع فيها وجوه الوقف والابتداء أو روايات القراء',
          children: [
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                Expanded(
                  child: _CircularMetricPod(
                    label: 'تعدد الأقوال (وقف ووصل)',
                    centerText: _percent(s.scholarDisagreement, s.total),
                    centerLtr: true,
                    count: s.scholarDisagreement,
                    total: s.total,
                    color: AppColors.badgeAmber,
                  ),
                ),
                Expanded(
                  child: _CircularMetricPod(
                    label: 'فيها قول بـ«قيل»',
                    centerText: _percent(s.withQila, s.total),
                    centerLtr: true,
                    count: s.withQila,
                    total: s.total,
                    color: AppColors.gold,
                  ),
                ),
                Expanded(
                  child: _CircularMetricPod(
                    label: 'متعلقة بالقراءات',
                    centerText: _percent(s.qiraatDependent, s.total),
                    centerLtr: true,
                    count: s.qiraatDependent,
                    total: s.total,
                    color: const Color(0xFF4F967E),
                  ),
                ),
              ],
            ),
          ],
        ),

        // 5. Scholars with circular coverage + allowed/disallowed dual-arc rings.
        _Section(
          title: 'تغطية أئمة الوقف والابتداء',
          subtitle: 'عدد الوقوف التي تكلّم فيها كل عالم، ونسبة الجواز مقابل المنع',
          children: [
            const SizedBox(height: 4),
            for (final sc in s.byScholar) _ScholarRingRow(stat: sc, total: s.total),
          ],
        ),

        // 6. Per-surah expandable breakdown for whole-Mushaf view.
        if (s.surahRows.isNotEmpty)
          _Section(
            title: 'حسب السورة',
            children: [
              Theme(
                data: Theme.of(context)
                    .copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: Text(
                    'عرض التفصيل (${arabicDigits(s.surahRows.length)} سورة)',
                    style: AppText.ui(
                      size: 14,
                      weight: FontWeight.w700,
                      color: AppColors.forestDeep,
                    ),
                  ),
                  children: [
                    for (final r in s.surahRows) _SurahRow(row: r),
                  ],
                ),
              ),
            ],
          ),
      ],
    );
  }
}

class _DonutSlice {
  const _DonutSlice({required this.value, required this.color});

  final double value;
  final Color color;
}

/// Multi-segment circular donut canvas with optional outer gold ornament ring.
class _MultiSegmentDonutPainter extends CustomPainter {
  const _MultiSegmentDonutPainter({
    required this.slices,
    this.strokeWidth = 18,
    this.ornamentalOuter = false,
  });

  final List<_DonutSlice> slices;
  final double strokeWidth;
  final bool ornamentalOuter;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final outerRadius = math.min(size.width, size.height) / 2;
    final radius = outerRadius - strokeWidth / 2 - (ornamentalOuter ? 8 : 2);
    if (radius <= 0) return;

    if (ornamentalOuter) {
      final ringPaint = Paint()
        ..color = AppColors.gold.withOpacity(0.32)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2;
      canvas.drawCircle(center, outerRadius - 2, ringPaint);
    }

    final trackPaint = Paint()
      ..color = AppColors.hairline.withOpacity(0.55)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
    canvas.drawCircle(center, radius, trackPaint);

    final nonZero = [for (final s in slices) if (s.value > 0) s];
    final total = nonZero.fold<double>(0, (sum, s) => sum + s.value);
    if (total <= 0) return;

    final gap = nonZero.length > 1 ? 0.025 : 0.0;
    final usable = 2 * math.pi - gap * nonZero.length;
    var startAngle = -math.pi / 2 + gap / 2;
    final rect = Rect.fromCircle(center: center, radius: radius);

    for (final s in nonZero) {
      final sweep = usable * (s.value / total);
      final paint = Paint()
        ..color = s.color
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.butt;
      canvas.drawArc(rect, startAngle, sweep, false, paint);
      startAngle += sweep + gap;
    }
  }

  @override
  bool shouldRepaint(covariant _MultiSegmentDonutPainter old) {
    return old.strokeWidth != strokeWidth ||
        old.ornamentalOuter != ornamentalOuter ||
        old.slices.length != slices.length;
  }
}

/// Single-value circular radial gauge painter.
class _RadialGaugePainter extends CustomPainter {
  const _RadialGaugePainter({
    required this.fraction,
    required this.color,
    this.trackColor = AppColors.hairline,
    this.strokeWidth = 6,
    this.ornamentalOuter = false,
  });

  final double fraction;
  final Color color;
  final Color trackColor;
  final double strokeWidth;
  final bool ornamentalOuter;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final outerRadius = math.min(size.width, size.height) / 2;
    final radius = outerRadius - strokeWidth / 2 - (ornamentalOuter ? 5 : 1);
    if (radius <= 0) return;

    if (ornamentalOuter) {
      final outerPaint = Paint()
        ..color = AppColors.gold.withOpacity(0.28)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1;
      canvas.drawCircle(center, outerRadius - 1, outerPaint);
    }

    final trackPaint = Paint()
      ..color = trackColor.withOpacity(0.6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
    canvas.drawCircle(center, radius, trackPaint);

    final clamped = fraction.clamp(0.0, 1.0);
    if (clamped <= 0) return;

    final sweep = 2 * math.pi * clamped;
    final arcPaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = clamped >= 0.999 ? StrokeCap.butt : StrokeCap.round;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      sweep,
      false,
      arcPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _RadialGaugePainter old) {
    return old.fraction != fraction ||
        old.color != color ||
        old.strokeWidth != strokeWidth;
  }
}

/// Circular coverage ring split into allowed vs non-allowed arcs for a scholar.
class _DualArcRingPainter extends CustomPainter {
  const _DualArcRingPainter({
    required this.coverage,
    required this.allowedShare,
    this.strokeWidth = 6,
  });

  final double coverage;
  final double allowedShare;
  final double strokeWidth;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - strokeWidth / 2 - 1;
    if (radius <= 0) return;

    final trackPaint = Paint()
      ..color = AppColors.hairline.withOpacity(0.65)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
    canvas.drawCircle(center, radius, trackPaint);

    final totalSweep = 2 * math.pi * coverage.clamp(0.0, 1.0);
    if (totalSweep <= 0) return;

    final rect = Rect.fromCircle(center: center, radius: radius);
    final allowedSweep = totalSweep * allowedShare.clamp(0.0, 1.0);
    final notAllowedSweep = totalSweep - allowedSweep;

    if (allowedSweep > 0) {
      final p = Paint()
        ..color = AppColors.forest
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.butt;
      canvas.drawArc(rect, -math.pi / 2, allowedSweep, false, p);
    }
    if (notAllowedSweep > 0) {
      final p = Paint()
        ..color = const Color(0xFFB0574B)
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.butt;
      canvas.drawArc(rect, -math.pi / 2 + allowedSweep, notAllowedSweep, false, p);
    }
  }

  @override
  bool shouldRepaint(covariant _DualArcRingPainter old) {
    return old.coverage != coverage || old.allowedShare != allowedShare;
  }
}

class _SummaryRingTile extends StatelessWidget {
  const _SummaryRingTile({
    required this.label,
    required this.value,
    required this.total,
    required this.color,
  });

  final String label;
  final int value;
  final int total;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final frac = total <= 0 ? 0.0 : value / total;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.parchment.withOpacity(0.55),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.hairline),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 48,
            height: 48,
            child: CustomPaint(
              painter: _RadialGaugePainter(
                fraction: frac,
                color: color,
                strokeWidth: 5,
              ),
              child: Center(
                child: Text(
                  _percent(value, total),
                  textDirection: TextDirection.ltr,
                  style: AppText.ui(
                    size: 11,
                    weight: FontWeight.w800,
                    color: AppColors.forestDeep,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  arabicDigits(value),
                  style: AppText.ui(
                    size: 18,
                    weight: FontWeight.w800,
                    color: AppColors.forestDeep,
                    height: 1.15,
                  ),
                ),
                Text(
                  label,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.ui(
                    size: 11,
                    color: AppColors.muted,
                    height: 1.25,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PairedGrid extends StatelessWidget {
  const _PairedGrid({required this.items});

  final List<Widget> items;

  @override
  Widget build(BuildContext context) {
    final rows = <Widget>[];
    for (var i = 0; i < items.length; i += 2) {
      rows.add(
        Padding(
          padding: EdgeInsets.only(top: i == 0 ? 0 : 8),
          child: Row(
            children: [
              Expanded(child: items[i]),
              const SizedBox(width: 8),
              Expanded(
                child: i + 1 < items.length
                    ? items[i + 1]
                    : const SizedBox.shrink(),
              ),
            ],
          ),
        ),
      );
    }
    return Column(children: rows);
  }
}

class _DegreeRingItem extends StatelessWidget {
  const _DegreeRingItem({
    required this.label,
    required this.symbol,
    required this.count,
    required this.total,
    required this.color,
  });

  final String label;
  final String? symbol;
  final int count;
  final int total;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final frac = total <= 0 ? 0.0 : count / total;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
      decoration: BoxDecoration(
        color: AppColors.parchment.withOpacity(0.45),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.hairline.withOpacity(0.75)),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 42,
            height: 42,
            child: CustomPaint(
              painter: _RadialGaugePainter(
                fraction: frac,
                color: color,
                strokeWidth: 4.5,
              ),
              child: Center(
                child: Text(
                  symbol ?? '؟',
                  style: AppText.ui(
                    size: 13.5,
                    weight: FontWeight.w800,
                    color: color,
                    height: 1.2,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.ui(
                    size: 13,
                    weight: FontWeight.w700,
                    color: AppColors.ink,
                    height: 1.2,
                  ),
                ),
                Row(
                  children: [
                    Text(
                      arabicDigits(count),
                      style: AppText.ui(
                        size: 12.5,
                        weight: FontWeight.w800,
                        color: AppColors.forestDeep,
                        height: 1.25,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '(${_percent(count, total)})',
                      textDirection: TextDirection.ltr,
                      style: AppText.ui(
                        size: 11,
                        color: AppColors.muted,
                        height: 1.25,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _LegendCountRow extends StatelessWidget {
  const _LegendCountRow({
    required this.label,
    required this.count,
    required this.total,
    required this.color,
  });

  final String label;
  final int count;
  final int total;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 11,
          height: 11,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            label,
            style: AppText.ui(
              size: 13.5,
              weight: FontWeight.w700,
              color: AppColors.ink,
            ),
          ),
        ),
        Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              arabicDigits(count),
              style: AppText.ui(
                size: 14,
                weight: FontWeight.w800,
                color: AppColors.forestDeep,
                height: 1.1,
              ),
            ),
            Text(
              _percent(count, total),
              textDirection: TextDirection.ltr,
              style: AppText.ui(size: 11.5, color: AppColors.muted, height: 1.2),
            ),
          ],
        ),
      ],
    );
  }
}

class _CircularMetricPod extends StatelessWidget {
  const _CircularMetricPod({
    required this.label,
    required this.centerText,
    required this.count,
    required this.total,
    required this.color,
    this.diameter = 64,
    this.strokeWidth = 6.5,
    this.centerLtr = false,
    this.centerIsSymbol = false,
  });

  final String label;
  final String centerText;
  final int count;
  final int total;
  final Color color;
  final double diameter;
  final double strokeWidth;
  final bool centerLtr;
  final bool centerIsSymbol;

  @override
  Widget build(BuildContext context) {
    final frac = total <= 0 ? 0.0 : count / total;
    return SizedBox(
      width: 96,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: diameter,
            height: diameter,
            child: CustomPaint(
              painter: _RadialGaugePainter(
                fraction: frac,
                color: color,
                strokeWidth: strokeWidth,
              ),
              child: Center(
                child: Text(
                  centerText,
                  textDirection: centerLtr ? TextDirection.ltr : null,
                  style: AppText.ui(
                    size: centerIsSymbol ? 16 : 13.5,
                    weight: FontWeight.w800,
                    color: centerIsSymbol ? color : AppColors.forestDeep,
                    height: 1.2,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            arabicDigits(count),
            style: AppText.ui(
              size: 14,
              weight: FontWeight.w800,
              color: AppColors.forestDeep,
              height: 1.15,
            ),
          ),
          Text(
            label,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: AppText.ui(
              size: 11.5,
              color: AppColors.muted,
              height: 1.25,
            ),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, this.subtitle, required this.children});

  final String title;
  final String? subtitle;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 14),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.hairline),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            title,
            style: AppText.ui(
              size: 15,
              weight: FontWeight.w800,
              color: AppColors.forestDeep,
            ),
          ),
          if (subtitle != null)
            Text(
              subtitle!,
              style: AppText.ui(size: 11.5, color: AppColors.muted, height: 1.4),
            ),
          const SizedBox(height: 6),
          ...children,
        ],
      ),
    );
  }
}

class _SubHeader extends StatelessWidget {
  const _SubHeader(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 10, bottom: 2),
      child: Text(
        text,
        style: AppText.ui(
          size: 13,
          weight: FontWeight.w700,
          color: AppColors.forestDeep,
        ),
      ),
    );
  }
}

String _percent(int count, int total) {
  if (total <= 0 || count <= 0) return '٠٪';
  final pct = count * 100 / total;
  if (pct < 1) return '<١٪';
  return '${arabicDigits(pct.round())}٪';
}

class _ScholarRingRow extends StatelessWidget {
  const _ScholarRingRow({required this.stat, required this.total});

  final ScholarStat stat;
  final int total;

  @override
  Widget build(BuildContext context) {
    final coverage = total <= 0 ? 0.0 : (stat.total / total).clamp(0.0, 1.0);
    final allowedShare = stat.total <= 0 ? 0.0 : stat.allowed / stat.total;
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.parchment.withOpacity(0.45),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.hairline.withOpacity(0.75)),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 54,
            height: 54,
            child: CustomPaint(
              painter: _DualArcRingPainter(
                coverage: coverage,
                allowedShare: allowedShare,
                strokeWidth: 5.5,
              ),
              child: Center(
                child: Text(
                  _percent(stat.total, total),
                  textDirection: TextDirection.ltr,
                  style: AppText.ui(
                    size: 11.5,
                    weight: FontWeight.w800,
                    color: AppColors.forestDeep,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        stat.scholar,
                        style: AppText.ui(
                          size: 14,
                          weight: FontWeight.w700,
                          color: AppColors.forestDeep,
                        ),
                      ),
                    ),
                    Text(
                      '${arabicDigits(stat.total)} وقف',
                      style: AppText.ui(
                        size: 13.5,
                        weight: FontWeight.w800,
                        color: AppColors.forestDeep,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  'يوقف ${arabicDigits(stat.allowed)} · '
                  'لا يوقف ${arabicDigits(stat.notAllowed)} · '
                  'قيل ${arabicDigits(stat.withQila)}',
                  style: AppText.ui(
                    size: 11.5,
                    color: AppColors.muted,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SurahRow extends StatelessWidget {
  const _SurahRow({required this.row});

  final SurahStatRow row;

  @override
  Widget build(BuildContext context) {
    final name = row.name.replaceFirst(RegExp(r'^سورة\s*'), '');
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          SizedBox(
            width: 30,
            child: Text(
              arabicDigits(row.number),
              style: AppText.ui(size: 12, color: AppColors.muted),
            ),
          ),
          Expanded(
            child: Text(
              name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppText.ui(size: 13.5, weight: FontWeight.w700),
            ),
          ),
          Text(
            '${arabicDigits(row.total)} وقف · '
            '${arabicDigits(row.differsFromUthmani)} زائد عن المصحف · '
            '${arabicDigits(row.multiDemo)} متعدد',
            style: AppText.ui(size: 12, color: AppColors.forestDeep),
          ),
        ],
      ),
    );
  }
}

class _UnderlineScopeTab extends StatelessWidget {
  const _UnderlineScopeTab({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Container(
          constraints: const BoxConstraints(minHeight: 44),
          padding: const EdgeInsets.symmetric(horizontal: 8),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(
                color: selected ? AppColors.forest : AppColors.hairline,
                width: selected ? 2 : 1,
              ),
            ),
          ),
          child: Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppText.ui(
              size: 12.5,
              weight: selected ? FontWeight.w700 : FontWeight.w500,
              color: selected ? AppColors.forest : AppColors.muted,
              height: 1.1,
            ),
          ),
        ),
      ),
    );
  }
}
