import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import 'waqf_bottom_sheet.dart';

/// Resolves the active demo opinion for a stop (for highlight + meanings box).
ScholarOpinion? demoOpinionForStop(WaqfStop stop, String? preferredScholar) {
  if (preferredScholar != null && preferredScholar.isNotEmpty) {
    final op = stop.opinionForScholar(preferredScholar);
    if (op != null && op.demosAndMeanings.isNotEmpty) return op;
  }
  for (final op in stop.opinions) {
    if (op.demosAndMeanings.isNotEmpty) return op;
  }
  return null;
}

/// Inline dotted meanings strip under the active ayah (not a dialog).
class DemoMeaningsBox extends StatefulWidget {
  const DemoMeaningsBox({
    super.key,
    required this.controller,
    this.showClose = true,
    this.dark = false,
  });

  final ReaderController controller;
  final bool showClose;
  final bool dark;

  @override
  State<DemoMeaningsBox> createState() => _DemoMeaningsBoxState();
}

class _DemoMeaningsBoxState extends State<DemoMeaningsBox> {
  bool _expanded = false;

  @override
  void didUpdateWidget(covariant DemoMeaningsBox oldWidget) {
    super.didUpdateWidget(oldWidget);
    final oldId = oldWidget.controller.selectedStopId;
    final newId = widget.controller.selectedStopId;
    if (oldId != newId || !widget.controller.demoHighlightActive) {
      _expanded = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.controller.demoHighlightActive) {
      return const SizedBox.shrink();
    }
    final stopId = widget.controller.selectedStopId;
    final stop = stopId == null ? null : widget.controller.stopById(stopId);
    final demo = widget.controller.activeDemoHighlight;
    if (stop == null || demo == null) return const SizedBox.shrink();

    final meaningWaqf = demo.meaningAtWaqf.trim();
    final meaningIbtida = demo.meaningAtIbtida.trim();
    if (meaningWaqf.isEmpty && meaningIbtida.isEmpty) {
      return const SizedBox.shrink();
    }

    final maxH = MediaQuery.sizeOf(context).height * 0.38;
    final tone = DockTone.of(widget.dark);
    final border = widget.dark ? AppColors.goldSoft : AppColors.gold;
    final fav = widget.controller.isFavorite(stop.id);
    final sent = widget.controller.isSent(stop.id);
    final groups = widget.controller.stopDemoGroupsFor(stop);
    final activeGroupIdx = widget.controller.activeStopDemoGroupIndex(stop);
    final activeGroup = (activeGroupIdx >= 0 && activeGroupIdx < groups.length)
        ? groups[activeGroupIdx]
        : null;
    final activeOp = activeGroup?.opinion ??
        demoOpinionForStop(
          stop,
          widget.controller.selectedDemoScholar ??
              widget.controller.selectedScholar,
        );
    final qiraatOp = activeGroup?.qiraatOpinion(stop) ??
        (activeOp != null && activeOp.hasQiraatInfo ? activeOp : null);
    final hasAnyQiraatOverrideGroup =
        groups.any((g) => g.demo.qiraatOverrides.isNotEmpty);
    final extent = demo.ayahExtent(stop.ayah);
    final isCrossAyah = demo.spansOtherAyahs(stop.ayah);

    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 10, 4, 4),
      child: CustomPaint(
        painter: _DottedRoundRectPainter(
          color: border,
          radius: 10,
          strokeWidth: 1.2,
          dash: 4,
          gap: 3,
        ),
        child: ConstrainedBox(
          constraints: BoxConstraints(maxHeight: maxH),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
            decoration: BoxDecoration(
              color: tone.bg.withOpacity(0.96),
              borderRadius: BorderRadius.circular(10),
            ),
            child: SingleChildScrollView(
              physics: const ClampingScrollPhysics(),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '«${stop.word}»',
                          style: AppText.ui(
                            size: 12,
                            weight: FontWeight.w700,
                            color: tone.quran,
                          ),
                        ),
                      ),
                      IconButton(
                        tooltip: fav ? 'إزالة من المفضلة' : 'إضافة للمفضلة',
                        onPressed: () =>
                            widget.controller.toggleFavorite(stop.id),
                        icon: Icon(
                          fav ? Icons.favorite : Icons.favorite_border,
                          color: fav
                              ? const Color(0xFFE8A0A0)
                              : tone.muted,
                        ),
                      ),
                      IconButton(
                        tooltip: sent
                            ? 'في قائمة المراجعة (انقر للإلغاء)'
                            : 'إبلاغ / إضافة للمراجعة',
                        onPressed: () => confirmAndToggleStopReport(
                          context,
                          widget.controller,
                          stop.id,
                        ),
                        icon: Icon(
                          sent
                              ? Icons.flag_rounded
                              : Icons.outlined_flag_rounded,
                          color: sent
                              ? const Color(0xFFE2A44B)
                              : tone.muted,
                        ),
                      ),
                      WaqfStopShareMenu(
                        controller: widget.controller,
                        stop: stop,
                        tone: tone,
                      ),
                      if (widget.showClose)
                        IconButton(
                          tooltip: 'إغلاق',
                          onPressed: () {
                            if (widget.controller.stopDockOpen) {
                              widget.controller.closeStopDock();
                            } else {
                              widget.controller.clearDemoHighlight();
                            }
                          },
                          icon: Icon(Icons.close, color: tone.muted),
                        ),
                    ],
                  ),
                  if (groups.length > 1 || isCrossAyah) ...[
                    const SizedBox(height: 6),
                    if (groups.length > 1)
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Variant tabs first (start edge), counter last.
                          Expanded(
                            child: Wrap(
                              spacing: 14,
                              runSpacing: 2,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                for (var i = 0; i < groups.length; i++)
                                  Builder(
                                    builder: (context) {
                                      final isCurrent = i ==
                                          (activeGroupIdx < 0
                                              ? 0
                                              : activeGroupIdx);
                                      final hasQ = groups[i]
                                          .demo
                                          .qiraatOverrides
                                          .isNotEmpty;
                                      final pillAccent = hasQ
                                          ? (tone.dark
                                              ? AppColors.qiraatSoft
                                              : AppColors.qiraat)
                                          : (tone.dark
                                              ? AppColors.goldSoft
                                              : AppColors.forest);
                                      return InkWell(
                                        onTap: () =>
                                            widget.controller.selectDemo(
                                          scholar: groups[i].scholar,
                                          demoIndex: groups[i].demoIndex,
                                        ),
                                        child: Container(
                                          padding: const EdgeInsets.symmetric(
                                            horizontal: 2,
                                            vertical: 4,
                                          ),
                                          decoration: BoxDecoration(
                                            border: Border(
                                              bottom: BorderSide(
                                                color: isCurrent
                                                    ? pillAccent
                                                    : Colors.transparent,
                                                width: 2,
                                              ),
                                            ),
                                          ),
                                          child: Text(
                                            '${arabicDigits(i + 1)}: ${demoGroupLabel(groups[i], stop.ayah, markHafs: hasAnyQiraatOverrideGroup)}',
                                            style: AppText.ui(
                                              size: 11,
                                              weight: isCurrent
                                                  ? FontWeight.w700
                                                  : FontWeight.w600,
                                              color: hasQ
                                                  ? pillAccent
                                                  : (isCurrent
                                                      ? (tone.dark
                                                          ? AppColors.goldSoft
                                                          : AppColors
                                                              .forestDeep)
                                                      : tone.muted),
                                              height: 1.2,
                                            ),
                                          ),
                                        ),
                                      );
                                    },
                                  ),
                                if (isCrossAyah)
                                  Text(
                                    'آية ${arabicDigits(extent.$1)}–${arabicDigits(extent.$2)}',
                                    style: AppText.ui(
                                      size: 11,
                                      weight: FontWeight.w600,
                                      color: tone.muted,
                                      height: 1.2,
                                    ),
                                  ),
                              ],
                            ),
                          ),
                          InkWell(
                            borderRadius: BorderRadius.circular(8),
                            onTap: () {
                              final curIdx =
                                  activeGroupIdx < 0 ? 0 : activeGroupIdx;
                              final next = (curIdx + 1) % groups.length;
                              widget.controller.selectDemo(
                                scholar: groups[next].scholar,
                                demoIndex: groups[next].demoIndex,
                              );
                            },
                            child: Padding(
                              padding: const EdgeInsetsDirectional.only(
                                start: 8,
                                top: 4,
                                bottom: 4,
                              ),
                              child: Text(
                                '${arabicDigits((activeGroupIdx < 0 ? 0 : activeGroupIdx) + 1)} / ${arabicDigits(groups.length)}',
                                key: const ValueKey<String>('demo-counter'),
                                style: AppText.ui(
                                  size: 11,
                                  weight: FontWeight.w700,
                                  color: tone.muted,
                                  height: 1.1,
                                ),
                              ),
                            ),
                          ),
                        ],
                      )
                    else
                      _DemoVariantLabel(
                        stopAyah: stop.ayah,
                        group: activeGroup,
                        markHafs: hasAnyQiraatOverrideGroup,
                        extent: extent,
                        isCrossAyah: isCrossAyah,
                        tone: tone,
                      ),
                  ],
                  if (demo.isQiraatDemo || qiraatOp != null) ...[
                    const SizedBox(height: 6),
                    if ((qiraatOp ?? activeOp) != null)
                      QiraatBadge(
                        opinion: (qiraatOp ?? activeOp)!,
                        demo: demo,
                        tone: tone,
                      ),
                    if (widget.controller.activeQiraatWordOverrides.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          [
                            for (final m
                                in widget.controller.activeQiraatWordOverrides)
                              '${m.modifiedWord}  ‹  حفص: ${m.hafsWord}',
                          ].join('   ·   '),
                          style: AppText.ui(
                            size: 12,
                            weight: FontWeight.w600,
                            color: tone.dark
                                ? AppColors.qiraatSoft
                                : AppColors.qiraat,
                            height: 1.4,
                          ),
                        ),
                      ),
                  ],
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 220),
                    switchInCurve: Curves.easeOutCubic,
                    switchOutCurve: Curves.easeInCubic,
                    transitionBuilder: (child, anim) => FadeTransition(
                      opacity: anim,
                      child: SlideTransition(
                        position: Tween<Offset>(
                          begin: const Offset(0.08, 0),
                          end: Offset.zero,
                        ).animate(anim),
                        child: child,
                      ),
                    ),
                    layoutBuilder: (current, previous) => Stack(
                      alignment: Alignment.topCenter,
                      children: [
                        ...previous,
                        if (current != null) current,
                      ],
                    ),
                    child: Column(
                      key: ValueKey<String>('${stop.id}#$activeGroupIdx'),
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (meaningWaqf.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          _MeaningLine(
                            swatch: AppColors.demoWaqfMarker,
                            label: 'المعنى عند الوقف',
                            body: meaningWaqf,
                            expanded: _expanded,
                            tone: tone,
                          ),
                        ],
                        if (meaningIbtida.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          _MeaningLine(
                            swatch: AppColors.demoIbtidaMarker,
                            label: 'المعنى عند الابتداء',
                            body: meaningIbtida,
                            expanded: _expanded,
                            tone: tone,
                          ),
                        ],
                      ],
                    ),
                  ),
                  if (_needsExpand(meaningWaqf) ||
                      _needsExpand(meaningIbtida)) ...[
                    const SizedBox(height: 6),
                    Align(
                      alignment: AlignmentDirectional.centerStart,
                      child: InkWell(
                        onTap: () => setState(() => _expanded = !_expanded),
                        borderRadius: BorderRadius.circular(8),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 4,
                            vertical: 8,
                          ),
                          child: Text(
                            _expanded ? 'أقل' : 'المزيد',
                            style: AppText.ui(
                              size: 12,
                              weight: FontWeight.w700,
                              color: tone.accent,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  bool _needsExpand(String text) {
    return text.trim().length > 70;
  }
}

class _MeaningLine extends StatelessWidget {
  const _MeaningLine({
    required this.swatch,
    required this.label,
    required this.body,
    required this.expanded,
    required this.tone,
  });

  final Color swatch;
  final String label;
  final String body;
  final bool expanded;
  final DockTone tone;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Container(
              width: 12,
              height: 3,
              decoration: BoxDecoration(
                color: swatch,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: AppText.ui(
                size: 11,
                weight: FontWeight.w700,
                color: tone.muted,
              ),
            ),
          ],
        ),
        const SizedBox(height: 3),
        Text(
          body,
          textAlign: TextAlign.start,
          softWrap: true,
          maxLines: expanded ? null : 2,
          overflow: expanded ? TextOverflow.visible : TextOverflow.ellipsis,
          style: AppText.ui(
            size: 13,
            color: tone.text,
            height: 1.5,
          ),
        ),
      ],
    );
  }
}

String demoGroupLabel(
  StopDemoGroup g,
  int stopAyah, {
  bool markHafs = false,
}) {
  String base;
  if (g.scholars.length <= 1) {
    final verdict = (g.demo.isQila && !g.demo.verdict.contains('قيل'))
        ? 'قيل: ${g.demo.verdict}'
        : g.demo.verdict;
    base = verdict.trim().isEmpty ? g.scholar : '${g.scholar} · $verdict';
  } else if (g.scholars.length == 2) {
    base = '${g.scholars[0]}، ${g.scholars[1]}';
  } else {
    base = '${g.scholars[0]} +${arabicDigits(g.scholars.length - 1)}';
  }
  if (g.demo.qiraatOverrides.isNotEmpty) {
    final words =
        g.demo.qiraatOverrides.map((m) => m.modifiedWord).join('، ');
    return '$base · قراءة: $words';
  }
  if (markHafs) {
    return '$base · حفص';
  }
  return base;
}

/// Compact header: which scholars the visible demo belongs to + ayah range.
class _DemoVariantLabel extends StatelessWidget {
  const _DemoVariantLabel({
    required this.stopAyah,
    required this.group,
    required this.extent,
    required this.isCrossAyah,
    required this.tone,
    this.markHafs = false,
  });

  final int stopAyah;
  final StopDemoGroup? group;
  final (int, int) extent;
  final bool isCrossAyah;
  final DockTone tone;
  final bool markHafs;

  @override
  Widget build(BuildContext context) {
    final badgeColor = tone.dark ? AppColors.goldSoft : AppColors.forestDeep;
    final g = group;
    return Wrap(
      spacing: 6,
      runSpacing: 4,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        if (g != null)
          Text(
            demoGroupLabel(g, stopAyah, markHafs: markHafs),
            style: AppText.ui(
              size: 11.5,
              weight: FontWeight.w700,
              color: badgeColor,
              height: 1.2,
            ),
          ),
        if (isCrossAyah)
          Text(
            'آية ${arabicDigits(extent.$1)}–${arabicDigits(extent.$2)}',
            style: AppText.ui(
              size: 11,
              weight: FontWeight.w600,
              color: tone.muted,
              height: 1.2,
            ),
          ),
      ],
    );
  }
}

class _DottedRoundRectPainter extends CustomPainter {
  const _DottedRoundRectPainter({
    required this.color,
    required this.radius,
    required this.strokeWidth,
    required this.dash,
    required this.gap,
  });

  final Color color;
  final double radius;
  final double strokeWidth;
  final double dash;
  final double gap;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
    final rrect = RRect.fromRectAndRadius(
      Rect.fromLTWH(
        strokeWidth / 2,
        strokeWidth / 2,
        size.width - strokeWidth,
        size.height - strokeWidth,
      ),
      Radius.circular(radius),
    );
    final path = Path()..addRRect(rrect);
    for (final metric in path.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        final next = (distance + dash).clamp(0.0, metric.length);
        canvas.drawPath(metric.extractPath(distance, next), paint);
        distance = next + gap;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DottedRoundRectPainter oldDelegate) {
    return oldDelegate.color != color ||
        oldDelegate.radius != radius ||
        oldDelegate.strokeWidth != strokeWidth ||
        oldDelegate.dash != dash ||
        oldDelegate.gap != gap;
  }
}
