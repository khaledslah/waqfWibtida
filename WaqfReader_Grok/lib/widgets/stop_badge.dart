import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/waqf_models.dart';
import '../theme/app_theme.dart';

String stopLetter(StopSymbol symbol) {
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

class StopBadge extends StatelessWidget {
  const StopBadge({
    super.key,
    required this.symbol,
    required this.semanticsLabel,
    this.verdictLabel,
    this.isQila = false,
    this.selected = false,
    this.onTap,
    this.onLongPress,
    this.core = 28,
    /// Shrinks the invisible hit box so demo washes stay continuous.
    this.compact = false,
    this.hasDemoCue = false,
  });

  final StopSymbol symbol;
  final String semanticsLabel;
  final String? verdictLabel;
  final bool isQila;
  final bool selected;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final double core;
  final bool compact;
  /// Non-interactive gold tip when demos/meanings exist.
  final bool hasDemoCue;

  @override
  Widget build(BuildContext context) {
    final ringed = selected && symbol == StopSymbol.tam && !isQila;
    // Fixed slot size so selection/highlight never shifts mushaf word positions.
    final slot = compact ? core : math.max(44.0, core);

    return Semantics(
      button: onTap != null || onLongPress != null,
      label: semanticsLabel,
      child: InkResponse(
        onTap: onTap,
        onLongPress: onLongPress,
        radius: slot / 2,
        customBorder: const CircleBorder(),
        containedInkWell: true,
        highlightShape: BoxShape.circle,
        child: SizedBox(
          width: slot,
          height: slot,
          child: Stack(
            clipBehavior: Clip.none,
            alignment: Alignment.center,
            children: [
              Center(child: _visual(ringed)),
              if (hasDemoCue)
                Positioned(
                  top: compact ? 2 : 4,
                  left: compact ? 2 : 4,
                  child: IgnorePointer(
                    child: Container(
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: AppColors.goldSoft,
                        border: Border.all(color: AppColors.parchment, width: 1),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _visual(bool ringed) {
    final disc = _disc();
    if (ringed) {
      return SizedBox(
        width: core + 18,
        height: core + 18,
        child: Stack(
          alignment: Alignment.center,
          children: [
            Container(
              width: core + 18,
              height: core + 18,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.badgeGreenRingOuter,
              ),
            ),
            Container(
              width: core + 8,
              height: core + 8,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.badgeGreenRing,
              ),
            ),
            disc,
          ],
        ),
      );
    }
    if (!selected) return disc;
    return Container(
      width: core + 8,
      height: core + 8,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: AppColors.goldSoft, width: 1.5),
      ),
      child: disc,
    );
  }

  Widget _disc() {
    final rawLbl = verdictLabel?.trim();
    final letter =
        (rawLbl != null && rawLbl.isNotEmpty) ? rawLbl : stopLetter(symbol);
    final dotted = isQila || symbol == StopSymbol.unsettled;
    final fgColor = dotted ? _dottedForeground : _foreground;
    final style = AppText.ui(
      size: letter.length > 1 ? core * 0.36 : core * 0.46,
      weight: FontWeight.w700,
      color: fgColor,
      height: 1,
    );

    if (dotted) {
      return Container(
        width: core,
        height: core,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: _dottedFill,
        ),
        child: CustomPaint(
          painter: _DashedCirclePainter(color: _dottedBorderColor),
          child: Center(
            child: Text(letter, style: style, textAlign: TextAlign.center),
          ),
        ),
      );
    }

    return Container(
      width: core,
      height: core,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: _fill,
        border: symbol == StopSymbol.mujawwaz
            ? Border.all(color: AppColors.gold, width: 1.4)
            : null,
      ),
      child: Text(letter, style: style),
    );
  }

  Color get _dottedFill {
    switch (symbol) {
      case StopSymbol.tam:
        return AppColors.badgeGreen.withOpacity(0.14);
      case StopSymbol.la:
        return AppColors.badgeGrey.withOpacity(0.55);
      case StopSymbol.jaiz:
        return AppColors.badgeAmber.withOpacity(0.32);
      case StopSymbol.mujawwaz:
      case StopSymbol.unsettled:
        return AppColors.goldSoft.withOpacity(0.14);
    }
  }

  Color get _dottedBorderColor {
    switch (symbol) {
      case StopSymbol.tam:
        return AppColors.badgeGreen;
      case StopSymbol.la:
        return AppColors.badgeGreyText;
      case StopSymbol.jaiz:
        return AppColors.forestDeep;
      case StopSymbol.mujawwaz:
      case StopSymbol.unsettled:
        return AppColors.gold;
    }
  }

  Color get _dottedForeground {
    switch (symbol) {
      case StopSymbol.tam:
        return AppColors.badgeGreen;
      case StopSymbol.la:
        return AppColors.badgeGreyText;
      case StopSymbol.jaiz:
        return AppColors.forestDeep;
      case StopSymbol.mujawwaz:
      case StopSymbol.unsettled:
        return AppColors.gold;
    }
  }

  Color get _fill {
    switch (symbol) {
      case StopSymbol.tam:
        return AppColors.badgeGreen;
      case StopSymbol.la:
        return AppColors.badgeGrey;
      case StopSymbol.jaiz:
        return AppColors.badgeAmber;
      case StopSymbol.mujawwaz:
        return AppColors.goldSoft.withOpacity(0.18);
      case StopSymbol.unsettled:
        return Colors.transparent;
    }
  }

  Color get _foreground {
    switch (symbol) {
      case StopSymbol.tam:
        return AppColors.white;
      case StopSymbol.la:
        return AppColors.badgeGreyText;
      case StopSymbol.jaiz:
        return AppColors.forestDeep;
      case StopSymbol.mujawwaz:
        return AppColors.gold;
      case StopSymbol.unsettled:
        return AppColors.gold;
    }
  }
}

class _DashedCirclePainter extends CustomPainter {
  const _DashedCirclePainter({required this.color});

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;
    final radius = size.width / 2 - 1.2;
    final center = Offset(size.width / 2, size.height / 2);
    const dash = 3.0;
    const gap = 2.4;
    final sweep = dash / radius;
    final step = (dash + gap) / radius;
    for (var angle = 0.0; angle < math.pi * 2; angle += step) {
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        angle,
        sweep,
        false,
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _DashedCirclePainter oldDelegate) {
    return oldDelegate.color != color;
  }
}
