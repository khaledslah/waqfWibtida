import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
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

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        Text(
          'المراجعة',
          style: AppText.ui(
            size: 22,
            weight: FontWeight.w700,
            color: AppColors.forestDeep,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '${controller.currentSurahName} · ${arabicDigits(items.length)} / ${arabicDigits(controller.sampleStops.length)}',
          style: AppText.ui(size: 14, color: AppColors.muted),
        ),
        const SizedBox(height: 12),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final filter in ReviewListFilter.values) ...[
                _FilterChip(
                  label: filter.labelAr,
                  selected: controller.reviewFilter == filter,
                  onTap: () => controller.setReviewFilter(filter),
                ),
                const SizedBox(width: 8),
              ],
            ],
          ),
        ),
        const SizedBox(height: 16),
        if (items.isEmpty)
          const _EmptyReview()
        else
          for (final stop in items) ...[
            _ReviewCard(
              stop: stop,
              surahName: controller.currentSurahName,
              favorite: controller.isFavorite(stop.id),
              verified: controller.isVerified(stop.id),
              sent: controller.isSent(stop.id),
              onOpen: () => showWaqfSheet(context, controller, stop.id),
              onToggleFavorite: () => controller.toggleFavorite(stop.id),
              onToggleVerified: () => controller.toggleVerified(stop.id),
              onOpenPage: stop.textPage == null
                  ? null
                  : () => showSajawandiPage(context, page: stop.textPage!),
            ),
            const SizedBox(height: 8),
          ],
      ],
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
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
        borderRadius: BorderRadius.circular(18),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Text(
            label,
            style: AppText.ui(
              size: 12,
              weight: FontWeight.w700,
              color: selected ? AppColors.forest : AppColors.muted,
              height: 1.1,
            ),
          ),
        ),
      ),
    );
  }
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
    required this.onOpen,
    required this.onToggleFavorite,
    required this.onToggleVerified,
    required this.onOpenPage,
  });

  final WaqfStop stop;
  final String surahName;
  final bool favorite;
  final bool verified;
  final bool sent;
  final VoidCallback onOpen;
  final VoidCallback onToggleFavorite;
  final VoidCallback onToggleVerified;
  final VoidCallback? onOpenPage;

  @override
  Widget build(BuildContext context) {
    final metaBits = <String>[
      surahName,
      'آية ${arabicDigits(stop.ayah)}',
      stop.label,
    ];
    final statusTags = <Widget>[
      if (stop.symbol == StopSymbol.unsettled || stop.hasNullVerdict)
        const _Tag(label: 'غير محسوم', amber: true),
      if (stop.hasAiSuggestion) const _Tag(label: 'مقترح AI', amber: false),
      if (sent) const _Tag(label: 'أُرسلت', amber: false),
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
                        if (stop.textPage != null)
                          _PageButton(
                            page: stop.textPage!,
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
  const _PageButton({required this.page, required this.onTap});

  final int page;
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
            Text(
              '$page',
              style: AppText.ui(size: 14, color: AppColors.ink),
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
