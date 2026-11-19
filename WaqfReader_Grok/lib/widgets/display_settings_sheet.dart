import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../screens/mushaf_screen.dart';
import '../theme/app_theme.dart';

/// Opens the display & Qira'at highlight color settings sheet.
Future<void> showDisplaySettingsSheet(
  BuildContext context,
  ReaderController controller,
) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: const Color(0x88000000),
    builder: (_) => DisplaySettingsSheet(controller: controller),
  );
}

class DisplaySettingsSheet extends StatelessWidget {
  const DisplaySettingsSheet({super.key, required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.paddingOf(context).bottom;
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Material(
        color: AppColors.parchment,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        clipBehavior: Clip.antiAlias,
        child: ListenableBuilder(
          listenable: controller,
          builder: (context, _) {
            final qColor = controller.qiraatHighlightColor;
            final dotted = controller.qiraatDottedOutline;
            final isDefault = controller.qiraatColorId == 'copper' &&
                dotted &&
                controller.quranSize == 26;

            return SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(20, 10, 20, 20 + bottom),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: AppColors.hairline,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  ),
                  Row(
                    children: [
                      const Icon(
                        Icons.tune_rounded,
                        size: 20,
                        color: AppColors.forestDeep,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'إعدادات العرض والألوان',
                          style: AppText.ui(
                            size: 17,
                            weight: FontWeight.w800,
                            color: AppColors.forestDeep,
                          ),
                        ),
                      ),
                      if (!isDefault)
                        TextButton(
                          onPressed: controller.resetDisplaySettings,
                          child: Text(
                            'الافتراضي',
                            style: AppText.ui(
                              size: 13,
                              weight: FontWeight.w700,
                              color: AppColors.forest,
                            ),
                          ),
                        ),
                      IconButton(
                        tooltip: 'إغلاق',
                        onPressed: () => Navigator.of(context).pop(),
                        icon: const Icon(
                          Icons.close,
                          size: 20,
                          color: AppColors.muted,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  _PreviewStrip(
                    qColor: qColor,
                    dotted: dotted,
                    fontSize: controller.quranSize.clamp(22, 28),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'لون كلمة القراءة الأخرى',
                    style: AppText.ui(
                      size: 13,
                      weight: FontWeight.w700,
                      color: AppColors.forestDeep,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final preset in AppColors.qiraatPresets)
                        _ColorChip(
                          option: preset,
                          selected: controller.qiraatColorId == preset.id,
                          onTap: () => controller.setQiraatColorId(preset.id),
                        ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  DecoratedBox(
                    decoration: BoxDecoration(
                      color: AppColors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.hairline),
                    ),
                    child: SwitchListTile(
                      dense: true,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 2,
                      ),
                      activeColor: qColor,
                      title: Text(
                        'إطار منقط حول كلمة القراءة',
                        style: AppText.ui(
                          size: 13.5,
                          weight: FontWeight.w600,
                          color: AppColors.ink,
                        ),
                      ),
                      subtitle: Text(
                        'يميز الكلمة بوضوح فوق تظليل الوقف والابتداء',
                        style: AppText.ui(
                          size: 11.5,
                          color: AppColors.muted,
                        ),
                      ),
                      value: dotted,
                      onChanged: controller.setQiraatDottedOutline,
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    'حجم خط المصحف',
                    style: AppText.ui(
                      size: 13,
                      weight: FontWeight.w700,
                      color: AppColors.forestDeep,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      for (final opt in const <(double, String)>[
                        (22, 'صغير'),
                        (26, 'متوسط'),
                        (32, 'كبير'),
                      ]) ...[
                        if (opt.$1 != 22) const SizedBox(width: 8),
                        Expanded(
                          child: _SizeChip(
                            label: opt.$2,
                            selected: controller.quranSize == opt.$1,
                            onTap: () => controller.setQuranSize(opt.$1),
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _PreviewStrip extends StatelessWidget {
  const _PreviewStrip({
    required this.qColor,
    required this.dotted,
    required this.fontSize,
  });

  final Color qColor;
  final bool dotted;
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    Widget qBox = DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.demoIbtidaWash,
        borderRadius: BorderRadius.circular(6),
        border: const Border(
          bottom: BorderSide(color: AppColors.demoIbtidaMarker, width: 2.4),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 1),
        child: QiraatWordText(
          word: 'غِشَـٰوَةً',
          size: fontSize,
          color: qColor,
        ),
      ),
    );
    if (dotted) {
      qBox = CustomPaint(
        foregroundPainter: QiraatDottedOutlinePainter(color: qColor),
        child: qBox,
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.hairline),
      ),
      child: Column(
        children: [
          Wrap(
            alignment: WrapAlignment.center,
            crossAxisAlignment: WrapCrossAlignment.center,
            textDirection: TextDirection.rtl,
            spacing: 2,
            children: [
              _SegWord(
                text: 'وَعَلَىٰ',
                wash: AppColors.demoWaqfWash,
                marker: AppColors.demoWaqfMarker,
                size: fontSize,
              ),
              _SegWord(
                text: 'سَمْعِهِمْ',
                wash: AppColors.demoWaqfWash,
                marker: AppColors.demoWaqfMarker,
                size: fontSize,
              ),
              const SizedBox(width: 4),
              _SegWord(
                text: 'وَعَلَىٰٓ',
                wash: AppColors.demoIbtidaWash,
                marker: AppColors.demoIbtidaMarker,
                size: fontSize,
              ),
              _SegWord(
                text: 'أَبْصَـٰرِهِمْ',
                wash: AppColors.demoIbtidaWash,
                marker: AppColors.demoIbtidaMarker,
                size: fontSize,
              ),
              qBox,
            ],
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const _LegendDot(color: AppColors.demoWaqfMarker, label: 'وقف'),
              const SizedBox(width: 12),
              const _LegendDot(color: AppColors.demoIbtidaMarker, label: 'ابتداء'),
              const SizedBox(width: 12),
              _LegendDot(color: qColor, label: 'قراءة أخرى'),
            ],
          ),
        ],
      ),
    );
  }
}

class _SegWord extends StatelessWidget {
  const _SegWord({
    required this.text,
    required this.wash,
    required this.marker,
    required this.size,
  });

  final String text;
  final Color wash;
  final Color marker;
  final double size;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: wash,
        borderRadius: BorderRadius.circular(6),
        border: Border(bottom: BorderSide(color: marker, width: 2.4)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 1),
        child: Text(
          text,
          textDirection: TextDirection.rtl,
          style: AppText.quran(
            size: size,
            color: AppColors.ink,
            height: 1.35,
          ),
        ),
      ),
    );
  }
}

class _LegendDot extends StatelessWidget {
  const _LegendDot({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 3.5,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: AppText.ui(size: 11, color: AppColors.muted),
        ),
      ],
    );
  }
}

class _ColorChip extends StatelessWidget {
  const _ColorChip({
    required this.option,
    required this.selected,
    required this.onTap,
  });

  final QiraatColorOption option;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      key: ValueKey<String>('qiraat-color-${option.id}'),
      borderRadius: BorderRadius.circular(10),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        decoration: BoxDecoration(
          color: selected ? option.color.withOpacity(0.10) : AppColors.white,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: selected ? option.color : AppColors.hairline,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 14,
              height: 14,
              decoration: BoxDecoration(
                color: option.color,
                shape: BoxShape.circle,
              ),
              child: selected
                  ? const Icon(Icons.check, size: 10, color: AppColors.white)
                  : null,
            ),
            const SizedBox(width: 6),
            Text(
              option.label,
              style: AppText.ui(
                size: 12.5,
                weight: selected ? FontWeight.w700 : FontWeight.w600,
                color: selected ? option.color : AppColors.ink,
                height: 1.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SizeChip extends StatelessWidget {
  const _SizeChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected ? AppColors.chipFill : AppColors.white,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: selected ? AppColors.forest : AppColors.hairline,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Text(
          label,
          style: AppText.ui(
            size: 13,
            weight: selected ? FontWeight.w700 : FontWeight.w600,
            color: selected ? AppColors.forestDeep : AppColors.ink,
            height: 1.2,
          ),
        ),
      ),
    );
  }
}
