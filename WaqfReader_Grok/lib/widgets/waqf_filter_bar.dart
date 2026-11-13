import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../theme/app_theme.dart';

/// 1.1.1+3 underline filter theme, with clear إظهار / إخفاء labels.
class WaqfFilterBar extends StatelessWidget {
  const WaqfFilterBar({super.key, required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final visible = controller.visibleStopCount;
    final total = controller.sampleStops.length;
    final activeScholar = controller.selectedScholar;
    final scholarLabel = activeScholar ?? 'الكل';
    final menuValue =
        activeScholar ?? ReaderController.scholarAllSentinel;

    return Material(
      color: AppColors.parchment,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: _FilterToggle(
                    label: controller.hideVerseEnd
                        ? 'إظهار رؤوس الآي'
                        : 'إخفاء رؤوس الآي',
                    selected: controller.hideVerseEnd,
                    semanticsLabel: controller.hideVerseEnd
                        ? 'إظهار وقوف رؤوس الآيات'
                        : 'إخفاء وقوف رؤوس الآيات',
                    onTap: controller.toggleHideVerseEnd,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _FilterToggle(
                    label: controller.hideUthmani
                        ? 'إظهار وقف المصحف'
                        : 'إخفاء وقف المصحف',
                    selected: controller.hideUthmani,
                    semanticsLabel: controller.hideUthmani
                        ? 'إظهار الوقوف الموجودة في المصحف العثماني'
                        : 'إخفاء الوقوف الموجودة في المصحف العثماني',
                    onTap: controller.toggleHideUthmani,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            PopupMenuButton<String>(
              tooltip: 'اختيار العالم الرئيسي',
              initialValue: menuValue,
              onSelected: controller.setSelectedScholarFromMenu,
              itemBuilder: (context) {
                return [
                  for (final sOpt in ReaderController.scholarOptions)
                    PopupMenuItem<String>(
                      value: sOpt ?? ReaderController.scholarAllSentinel,
                      child: Text(
                        sOpt ?? 'الكل (الافتراضي)',
                        style: AppText.ui(
                          size: 14,
                          weight: (sOpt == activeScholar) ||
                                  (sOpt == null && activeScholar == null)
                              ? FontWeight.w700
                              : FontWeight.w500,
                          color: AppColors.forestDeep,
                        ),
                      ),
                    ),
                ];
              },
              child: Container(
                constraints: const BoxConstraints(minHeight: 44),
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                      color: AppColors.forest.withOpacity(0.35),
                      width: 1,
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    Text(
                      'العالم:',
                      style: AppText.ui(
                        size: 13,
                        weight: FontWeight.w700,
                        color: AppColors.forestDeep,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        scholarLabel,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.ui(
                          size: 13,
                          weight: FontWeight.w600,
                          color: AppColors.ink,
                        ),
                      ),
                    ),
                    const Icon(
                      Icons.expand_more,
                      size: 20,
                      color: AppColors.muted,
                    ),
                  ],
                ),
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

class _FilterToggle extends StatelessWidget {
  const _FilterToggle({
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
      toggled: selected,
      label: semanticsLabel,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          child: Container(
            constraints: const BoxConstraints(minHeight: 44),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              border: Border(
                bottom: BorderSide(
                  color: selected ? AppColors.forest : AppColors.hairline,
                  width: selected ? 2 : 1,
                ),
              ),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  selected ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                  size: 18,
                  color: selected ? AppColors.forest : AppColors.muted,
                ),
                const SizedBox(width: 4),
                Flexible(
                  child: Text(
                    label,
                    textAlign: TextAlign.center,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.ui(
                      size: 12,
                      weight: selected ? FontWeight.w700 : FontWeight.w500,
                      color: selected ? AppColors.forest : AppColors.muted,
                      height: 1.1,
                    ),
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
