import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../theme/app_theme.dart';

/// Toggle chips to hide verse-end stops, Uthmani-printed middle stops, and switch the main scholar.
class WaqfFilterBar extends StatelessWidget {
  const WaqfFilterBar({super.key, required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final visible = controller.visibleStopCount;
    final total = controller.sampleStops.length;
    final activeScholar = controller.selectedScholar;

    return Material(
      color: AppColors.parchment,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  _FilterChip(
                    label: 'إخفاء رؤوس الآي',
                    selected: controller.hideVerseEnd,
                    onTap: controller.toggleHideVerseEnd,
                    semanticsLabel: controller.hideVerseEnd
                        ? 'إخفاء وقوف رؤوس الآيات مفعّل'
                        : 'إخفاء وقوف رؤوس الآيات متوقف',
                  ),
                  const SizedBox(width: 8),
                  _FilterChip(
                    label: 'إخفاء وقف المصحف',
                    selected: controller.hideUthmani,
                    onTap: controller.toggleHideUthmani,
                    semanticsLabel: controller.hideUthmani
                        ? 'إخفاء الوقوف الموجودة في المصحف العثماني مفعّل'
                        : 'إخفاء الوقوف الموجودة في المصحف العثماني متوقف',
                  ),
                  const SizedBox(width: 8),
                  _FilterChip(
                    label: 'الكل',
                    selected: !controller.hideVerseEnd && !controller.hideUthmani,
                    onTap: controller.showAllStops,
                    semanticsLabel: 'إظهار كل الوقوف',
                  ),
                ],
              ),
            ),
            const SizedBox(height: 6),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  Text(
                    'العالم الرئيسي:',
                    style: AppText.ui(
                      size: 11,
                      weight: FontWeight.w700,
                      color: AppColors.forestDeep,
                    ),
                  ),
                  const SizedBox(width: 6),
                  for (final sOpt in ReaderController.scholarOptions) ...[
                    Padding(
                      padding: const EdgeInsetsDirectional.only(end: 6),
                      child: _ScholarChip(
                        label: sOpt ?? 'الكل (الافتراضي)',
                        selected: activeScholar == sOpt,
                        onTap: () => controller.setSelectedScholar(sOpt),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'يظهر $visible من $total · العرض حسب: ${activeScholar ?? "جميع العلماء"}',
              style: AppText.ui(size: 11, color: AppColors.muted, height: 1.3),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScholarChip extends StatelessWidget {
  const _ScholarChip({
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
      color: selected ? AppColors.forest : AppColors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(
          color: selected ? AppColors.forest : AppColors.hairline,
          width: 1,
        ),
      ),
      child: InkWell(
        onTap: onTap,
        customBorder: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          child: Text(
            label,
            style: AppText.ui(
              size: 11,
              weight: FontWeight.w700,
              color: selected ? AppColors.white : AppColors.forestDeep,
              height: 1.1,
            ),
          ),
        ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
    required this.semanticsLabel,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final String semanticsLabel;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: semanticsLabel,
      child: Material(
        color: selected ? AppColors.chipFill : AppColors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(
            color: selected ? AppColors.forest : AppColors.hairline,
            width: selected ? 1.4 : 1,
          ),
        ),
        child: InkWell(
          onTap: onTap,
          customBorder: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  selected ? Icons.check_circle : Icons.circle_outlined,
                  size: 16,
                  color: selected ? AppColors.forest : AppColors.muted,
                ),
                const SizedBox(width: 6),
                Text(
                  label,
                  style: AppText.ui(
                    size: 12,
                    weight: FontWeight.w700,
                    color: selected ? AppColors.forest : AppColors.muted,
                    height: 1.1,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
