import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';

/// Resolves the active demo opinion for a stop (for ؟ highlight + meanings box).
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
  });

  final ReaderController controller;

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

    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 10, 4, 4),
      child: CustomPaint(
        painter: const _DottedRoundRectPainter(
          color: AppColors.gold,
          radius: 10,
          strokeWidth: 1.2,
          dash: 4,
          gap: 3,
        ),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
          decoration: BoxDecoration(
            color: AppColors.parchment.withOpacity(0.96),
            borderRadius: BorderRadius.circular(10),
          ),
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
                        color: AppColors.forestDeep,
                      ),
                    ),
                  ),
                  InkWell(
                    onTap: widget.controller.clearDemoHighlight,
                    borderRadius: BorderRadius.circular(12),
                    child: const Padding(
                      padding: EdgeInsets.all(4),
                      child: Icon(
                        Icons.close,
                        size: 16,
                        color: AppColors.muted,
                      ),
                    ),
                  ),
                ],
              ),
              if (meaningWaqf.isNotEmpty) ...[
                const SizedBox(height: 8),
                _MeaningLine(
                  swatch: AppColors.demoWaqfMarker,
                  label: 'المعنى عند الوقف',
                  body: meaningWaqf,
                  expanded: _expanded,
                ),
              ],
              if (meaningIbtida.isNotEmpty) ...[
                const SizedBox(height: 8),
                _MeaningLine(
                  swatch: AppColors.demoIbtidaMarker,
                  label: 'المعنى عند الابتداء',
                  body: meaningIbtida,
                  expanded: _expanded,
                ),
              ],
              if (_needsExpand(meaningWaqf) || _needsExpand(meaningIbtida)) ...[
                const SizedBox(height: 6),
                Align(
                  alignment: AlignmentDirectional.centerStart,
                  child: InkWell(
                    onTap: () => setState(() => _expanded = !_expanded),
                    borderRadius: BorderRadius.circular(8),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 4,
                        vertical: 2,
                      ),
                      child: Text(
                        _expanded ? 'أقل' : 'المزيد',
                        style: AppText.ui(
                          size: 12,
                          weight: FontWeight.w700,
                          color: AppColors.forest,
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
    );
  }

  bool _needsExpand(String text) {
    // Rough mobile cutoff for ~2 lines of Arabic UI text.
    return text.trim().length > 70;
  }
}

class _MeaningLine extends StatelessWidget {
  const _MeaningLine({
    required this.swatch,
    required this.label,
    required this.body,
    required this.expanded,
  });

  final Color swatch;
  final String label;
  final String body;
  final bool expanded;

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
                color: AppColors.muted,
              ),
            ),
          ],
        ),
        const SizedBox(height: 3),
        Text(
          body,
          textAlign: TextAlign.start,
          maxLines: expanded ? null : 2,
          overflow: expanded ? TextOverflow.visible : TextOverflow.ellipsis,
          style: AppText.ui(
            size: 13,
            color: AppColors.ink,
            height: 1.5,
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
