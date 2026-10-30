import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class OrnamentDivider extends StatelessWidget {
  const OrnamentDivider({super.key});

  @override
  Widget build(BuildContext context) {
    return const ExcludeSemantics(
      child: SizedBox(
        height: 40,
        width: double.infinity,
        child: CustomPaint(painter: _OrnamentPainter()),
      ),
    );
  }
}

class _OrnamentPainter extends CustomPainter {
  const _OrnamentPainter();

  @override
  void paint(Canvas canvas, Size size) {
    const color = AppColors.gold;
    final y = size.height / 2;
    final cx = size.width / 2;
    final line = Paint()
      ..color = color
      ..strokeWidth = 1.15
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    const motif = 22.0;
    canvas.drawLine(Offset(28, y), Offset(cx - motif, y), line);
    canvas.drawLine(Offset(cx + motif, y), Offset(size.width - 28, y), line);

    _diamond(canvas, Offset(40, y), 3.2, line);
    _diamond(canvas, Offset(size.width - 40, y), 3.2, line);
    _diamond(canvas, Offset(cx - motif - 16, y), 3.4, line);
    _diamond(canvas, Offset(cx + motif + 16, y), 3.4, line);

    _rosette(canvas, Offset(cx, y), color);
  }

  void _diamond(Canvas canvas, Offset center, double radius, Paint paint) {
    final path = Path()
      ..moveTo(center.dx, center.dy - radius)
      ..lineTo(center.dx + radius, center.dy)
      ..lineTo(center.dx, center.dy + radius)
      ..lineTo(center.dx - radius, center.dy)
      ..close();
    canvas.drawPath(path, paint);
  }

  void _rosette(Canvas canvas, Offset center, Color color) {
    final fill = Paint()
      ..color = color.withOpacity(0.16)
      ..style = PaintingStyle.fill;
    final stroke = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.15;

    _diamond(canvas, center, 16, stroke);

    for (var i = 0; i < 8; i++) {
      canvas.save();
      canvas.translate(center.dx, center.dy);
      canvas.rotate(i * math.pi / 4);
      final petal = Rect.fromCenter(
        center: const Offset(0, -6.5),
        width: 4.6,
        height: 9,
      );
      canvas.drawOval(petal, fill);
      canvas.drawOval(petal, stroke);
      canvas.restore();
    }

    canvas.drawCircle(center, 2.6, Paint()..color = color);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
