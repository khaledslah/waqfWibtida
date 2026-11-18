import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../utils/book_page_service.dart';
import '../widgets/ornament_divider.dart';
import '../widgets/page_image_viewer.dart';
import '../widgets/stop_badge.dart';
import '../widgets/waqf_bottom_sheet.dart';

class ReviewScreen extends StatelessWidget {
  const ReviewScreen({super.key, required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final items = controller.reviewItems;
    final poolCount = controller.reviewPoolStops.length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _ReviewFilterBar(
          controller: controller,
          shownCount: items.length,
          poolCount: poolCount,
        ),
        if (controller.loadingAllSurahs)
          const LinearProgressIndicator(
            minHeight: 2,
            color: AppColors.forest,
            backgroundColor: AppColors.hairline,
          ),
        Expanded(
          child: ListView.builder(
            key: ValueKey<String>(
              'review-${controller.reviewAllSurahs ? "all" : controller.currentSurah}-${controller.reviewFilter.name}-${controller.selectedScholar ?? ""}',
            ),
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 24),
            itemCount: items.isEmpty ? 1 : items.length,
            itemBuilder: (context, index) {
              if (items.isEmpty) {
                return const _EmptyReview();
              }
              final stop = items[index];
              final pageTarget = _resolveReviewPageTarget(
                context,
                stop,
                controller.selectedScholar,
              );
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _ReviewCard(
                  stop: stop,
                  surahName: controller.surahNameFor(stop.surah),
                  favorite: controller.isFavorite(stop.id),
                  verified: controller.isVerified(stop.id),
                  sent: controller.isSent(stop.id),
                  variantCount: controller.stopDemoGroupsFor(stop).length,
                  onOpen: () async {
                    if (stop.surah != controller.currentSurah) {
                      await controller.loadSurah(stop.surah);
                    }
                    if (context.mounted) {
                      showWaqfSheet(context, controller, stop.id);
                    }
                  },
                  onToggleFavorite: () => controller.toggleFavorite(stop.id),
                  onToggleVerified: () => controller.toggleVerified(stop.id),
                  pageLabel: pageTarget?.label,
                  onOpenPage: pageTarget?.onTap,
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

/// Top underline dropdown filter bar matching the main Mushaf page [WaqfFilterBar].
class _ReviewFilterBar extends StatelessWidget {
  const _ReviewFilterBar({
    required this.controller,
    required this.shownCount,
    required this.poolCount,
  });

  final ReaderController controller;
  final int shownCount;
  final int poolCount;

  @override
  Widget build(BuildContext context) {
    final activeScholar = controller.selectedScholar;
    final scholarLabel = activeScholar ?? 'الكل';
    final scholarMenuValue = activeScholar ?? ReaderController.scholarAllSentinel;
    final rawSurah = controller.currentSurahName;
    final shortSurah = rawSurah.isEmpty
        ? 'السورة'
        : 'سورة ${rawSurah.replaceFirst(RegExp(r'^سورة\s*'), '')}';
    final scopeLabel = controller.reviewAllSurahs ? 'كل السور' : shortSurah;
    final activeFilter = controller.reviewFilter;
    final activeFilterLabel =
        '${activeFilter.labelAr} (${arabicDigits(controller.reviewCountForFilter(activeFilter))})';

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
                  flex: 4,
                  child: _UnderlineDropdown<bool>(
                    tooltip: 'نطاق العرض',
                    initialValue: controller.reviewAllSurahs,
                    label: scopeLabel,
                    onSelected: controller.setReviewAllSurahs,
                    itemBuilder: (_) => [
                      PopupMenuItem<bool>(
                        value: false,
                        child: Text(
                          shortSurah,
                          style: AppText.ui(
                            size: 14,
                            weight: !controller.reviewAllSurahs
                                ? FontWeight.w700
                                : FontWeight.w500,
                            color: AppColors.forestDeep,
                          ),
                        ),
                      ),
                      PopupMenuItem<bool>(
                        value: true,
                        child: Text(
                          'كل السور',
                          style: AppText.ui(
                            size: 14,
                            weight: controller.reviewAllSurahs
                                ? FontWeight.w700
                                : FontWeight.w500,
                            color: AppColors.forestDeep,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  flex: 6,
                  child: _UnderlineDropdown<ReviewListFilter>(
                    tooltip: 'تصفية الوقوف',
                    initialValue: activeFilter,
                    label: activeFilterLabel,
                    onSelected: controller.setReviewFilter,
                    itemBuilder: (_) => [
                      for (final filter in ReviewListFilter.values)
                        PopupMenuItem<ReviewListFilter>(
                          value: filter,
                          child: Text(
                            '${filter.labelAr} (${arabicDigits(controller.reviewCountForFilter(filter))})',
                            style: AppText.ui(
                              size: 14,
                              weight: filter == activeFilter
                                  ? FontWeight.w700
                                  : FontWeight.w500,
                              color: AppColors.forestDeep,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  flex: 4,
                  child: _UnderlineDropdown<String>(
                    tooltip: 'اختيار العالم الرئيسي',
                    initialValue: scholarMenuValue,
                    label: scholarLabel,
                    onSelected: controller.setSelectedScholarFromMenu,
                    itemBuilder: (_) => [
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
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'يظهر ${arabicDigits(shownCount)} من ${arabicDigits(poolCount)} · '
              '${controller.reviewAllSurahs ? "جميع السور" : controller.currentSurahName} · '
              'العرض حسب: ${activeScholar ?? "جميع العلماء"}',
              style: AppText.ui(size: 11, color: AppColors.muted, height: 1.3),
            ),
          ],
        ),
      ),
    );
  }
}

class _UnderlineDropdown<T extends Object> extends StatelessWidget {
  const _UnderlineDropdown({
    required this.tooltip,
    required this.initialValue,
    required this.label,
    required this.onSelected,
    required this.itemBuilder,
  });

  final String tooltip;
  final T initialValue;
  final String label;
  final PopupMenuItemSelected<T> onSelected;
  final PopupMenuItemBuilder<T> itemBuilder;

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<T>(
      tooltip: tooltip,
      initialValue: initialValue,
      onSelected: onSelected,
      itemBuilder: itemBuilder,
      child: Container(
        constraints: const BoxConstraints(minHeight: 44),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: AppColors.forest.withOpacity(0.35),
              width: 1,
            ),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: AppText.ui(
                  size: 12,
                  weight: FontWeight.w700,
                  color: AppColors.forestDeep,
                  height: 1.1,
                ),
              ),
            ),
            const Icon(
              Icons.expand_more,
              size: 18,
              color: AppColors.muted,
            ),
          ],
        ),
      ),
    );
  }
}

({String label, VoidCallback onTap})? _resolveReviewPageTarget(
  BuildContext context,
  WaqfStop stop,
  String? selectedScholar,
) {
  ScholarOpinion? targetOp;
  if (selectedScholar != null && stop.hasScholar(selectedScholar)) {
    final op = stop.opinionForScholar(selectedScholar);
    if (op != null) {
      final bk = bookKeyForScholar(scholar: op.scholar, book: op.book);
      if (bk != null && (op.page != null || bk == 'nahhas')) {
        targetOp = op;
      }
    }
  }
  if (targetOp == null && stop.textPage != null) {
    return (
      label: '${stop.textPage}',
      onTap: () => showSajawandiPage(context, page: stop.textPage!),
    );
  }
  if (targetOp == null) {
    for (final op in stop.opinions) {
      final bk = bookKeyForScholar(scholar: op.scholar, book: op.book);
      if (bk != null && (op.page != null || bk == 'nahhas')) {
        targetOp = op;
        break;
      }
    }
  }
  if (targetOp == null) return null;
  final op = targetOp;
  final label = op.page ?? 'آية ${arabicDigits(stop.ayah)}';
  return (
    label: label,
    onTap: () => showScholarBookPage(
      context,
      scholar: op.scholar,
      book: op.book,
      pageStr: op.page,
      sajawandiPage: stop.textPage,
      surah: stop.surah,
      ayah: stop.ayah,
    ),
  );
}

class _EmptyReview extends StatelessWidget {
  const _EmptyReview();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 32),
      child: Column(
        children: [
          const OrnamentDivider(),
          const SizedBox(height: 16),
          Text(
            'لا وقوف تحت هذا المرشّح.',
            textAlign: TextAlign.center,
            style: AppText.ui(size: 16, color: AppColors.forestDeep),
          ),
          const SizedBox(height: 8),
          Text(
            'جرّب «الكل» لعرض كل وقوف السورة الحالية.',
            textAlign: TextAlign.center,
            style: AppText.ui(size: 14, color: AppColors.muted),
          ),
        ],
      ),
    );
  }
}

class _ReviewCard extends StatelessWidget {
  const _ReviewCard({
    required this.stop,
    required this.surahName,
    required this.favorite,
    required this.verified,
    required this.sent,
    required this.variantCount,
    required this.onOpen,
    required this.onToggleFavorite,
    required this.onToggleVerified,
    required this.pageLabel,
    required this.onOpenPage,
  });

  final WaqfStop stop;
  final String surahName;
  final bool favorite;
  final bool verified;
  final bool sent;
  final int variantCount;
  final VoidCallback onOpen;
  final VoidCallback onToggleFavorite;
  final VoidCallback onToggleVerified;
  final String? pageLabel;
  final VoidCallback? onOpenPage;

  @override
  Widget build(BuildContext context) {
    final metaBits = <String>[
      surahName,
      'آية ${arabicDigits(stop.ayah)}',
      stop.label,
    ];
    final hasCrossAyah = stop.opinions.any(
      (o) => o.demosAndMeanings.any((d) => d.spansOtherAyahs(stop.ayah)),
    );
    final statusTags = <Widget>[
      if (stop.differsFromUthmani)
        const _Tag(label: 'زائد عن المصحف', amber: true),
      if (stop.inUthmaniMushaf &&
          stop.uthmaniMark != null &&
          stop.uthmaniMark!.trim().isNotEmpty)
        _Tag(label: 'مصحف: ${stop.uthmaniMark!.trim()}', amber: false),
      if (variantCount > 1)
        _Tag(label: '${arabicDigits(variantCount)} أمثلة', amber: false),
      if (hasCrossAyah) const _Tag(label: 'عبر الآيات', amber: true),
      if (stop.hasAllowedVsNonAllowedDisagreement)
        const _Tag(label: 'تعدد أقوال', amber: true),
      if (stop.hasQiraatVariation) const _Tag(label: 'قراءات', amber: true),
      if (sent) const _Tag(label: 'مُبلّغ عنها', amber: true),
    ];

    return Material(
      color: AppColors.white,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onOpen,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.fromLTRB(10, 10, 6, 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.hairline),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: StopBadge(
                  symbol: stop.symbol,
                  verdictLabel: stop.verdictLabel,
                  isQila: stop.isQila,
                  semanticsLabel: '${stop.label} ${stop.word}',
                  core: 24,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        Expanded(
                          child: Padding(
                            // Amiri diacritics need room above/below the line box.
                            padding: const EdgeInsets.symmetric(vertical: 6),
                            child: Text(
                              stop.word,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppText.quran(
                                size: 22,
                                color: AppColors.ink,
                                height: 2.0,
                              ),
                            ),
                          ),
                        ),
                        IconButton(
                          tooltip: favorite ? 'إزالة من المفضلة' : 'مفضلة',
                          onPressed: onToggleFavorite,
                          visualDensity: VisualDensity.compact,
                          constraints: const BoxConstraints(
                            minWidth: 34,
                            minHeight: 34,
                          ),
                          padding: EdgeInsets.zero,
                          iconSize: 20,
                          icon: Icon(
                            favorite ? Icons.favorite : Icons.favorite_border,
                            color: favorite
                                ? const Color(0xFFB85C5C)
                                : AppColors.muted,
                          ),
                        ),
                        IconButton(
                          tooltip: verified ? 'إلغاء التحقق' : 'تحقّق',
                          onPressed: onToggleVerified,
                          visualDensity: VisualDensity.compact,
                          constraints: const BoxConstraints(
                            minWidth: 34,
                            minHeight: 34,
                          ),
                          padding: EdgeInsets.zero,
                          iconSize: 20,
                          icon: Icon(
                            verified
                                ? Icons.verified
                                : Icons.verified_outlined,
                            color: verified
                                ? AppColors.forest
                                : AppColors.muted,
                          ),
                        ),
                      ],
                    ),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            metaBits.join(' · '),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppText.ui(
                              size: 12,
                              color: AppColors.muted,
                              height: 1.3,
                            ),
                          ),
                        ),
                        if (pageLabel != null)
                          _PageButton(
                            label: pageLabel!,
                            onTap: onOpenPage,
                          ),
                      ],
                    ),
                    if (stop.reason.trim().isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        stop.reason,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.ui(
                          size: 12,
                          color: AppColors.ink,
                          height: 1.35,
                        ),
                      ),
                    ],
                    if (statusTags.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: statusTags,
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PageButton extends StatelessWidget {
  const _PageButton({required this.label, required this.onTap});

  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          textDirection: TextDirection.ltr,
          children: [
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 96),
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppText.ui(size: 13, color: AppColors.ink),
              ),
            ),
            const SizedBox(width: 4),
            const Icon(
              Icons.menu_book_outlined,
              size: 16,
              color: AppColors.muted,
            ),
          ],
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag({required this.label, required this.amber});

  final String label;
  final bool amber;

  @override
  Widget build(BuildContext context) {
    final fill = amber ? AppColors.amberWash : AppColors.chipFill;
    final foreground = amber ? AppColors.forestDeep : AppColors.forest;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: fill,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: AppText.ui(
          size: 11,
          weight: FontWeight.w700,
          color: foreground,
          height: 1.15,
        ),
      ),
    );
  }
}
