import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';

class IndexScreen extends StatelessWidget {
  const IndexScreen({super.key, required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        Text(
          'الفهرس',
          style: AppText.ui(
            size: 22,
            weight: FontWeight.w700,
            color: AppColors.forestDeep,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          controller.catalog.isEmpty
              ? 'لا فهرس محمّل'
              : '${arabicDigits(controller.catalog.length)} سورة من علل الوقوف',
          style: AppText.ui(size: 14, color: AppColors.muted),
        ),
        const SizedBox(height: 16),
        if (controller.sampleSurahs.isEmpty)
          const _EmptyIndex()
        else
          for (final surah in controller.sampleSurahs) ...[
            _SurahCard(
              surah: surah,
              onTap: () => _open(context, controller, surah),
            ),
            const SizedBox(height: 12),
          ],
      ],
    );
  }

  Future<void> _open(
    BuildContext context,
    ReaderController controller,
    SurahIndexEntry surah,
  ) async {
    if (surah.number == controller.currentSurah) {
      controller.setTab(0);
      return;
    }
    await controller.loadSurah(surah.number);
    if (!context.mounted) return;
    if (controller.loadState == ReaderLoadState.ready) {
      controller.setTab(0);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(controller.loadError ?? 'تعذّر فتح السورة')),
      );
    }
  }
}

class _EmptyIndex extends StatelessWidget {
  const _EmptyIndex();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 48),
      child: Text(
        'لا سور في الفهرس.',
        textAlign: TextAlign.center,
        style: AppText.ui(size: 16, color: AppColors.forestDeep),
      ),
    );
  }
}

class _SurahCard extends StatelessWidget {
  const _SurahCard({required this.surah, required this.onTap});

  final SurahIndexEntry surah;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.hairline),
          ),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: AppColors.chipFill,
                  border: Border.all(color: AppColors.forest),
                ),
                child: Text(
                  arabicDigits(surah.number),
                  style: AppText.ui(
                    size: 14,
                    weight: FontWeight.w700,
                    color: AppColors.forest,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      surah.name,
                      style: AppText.ui(
                        size: 16,
                        weight: FontWeight.w700,
                        color: AppColors.forestDeep,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      surah.detail,
                      style: AppText.ui(size: 13, color: AppColors.muted),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              _StatusChip(status: surah.status, label: surah.statusLabel),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status, required this.label});

  final SurahLoadStatus status;
  final String label;

  @override
  Widget build(BuildContext context) {
    final Color fill;
    final Color foreground;
    switch (status) {
      case SurahLoadStatus.inProgress:
        fill = AppColors.chipFill;
        foreground = AppColors.forest;
      case SurahLoadStatus.notStarted:
        fill = const Color(0xFFEFECE4);
        foreground = AppColors.muted;
      case SurahLoadStatus.awaitingReview:
        fill = AppColors.amberWash;
        foreground = AppColors.forestDeep;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: fill,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: foreground.withOpacity(0.35)),
      ),
      child: Text(
        label,
        style: AppText.ui(
          size: 12,
          weight: FontWeight.w700,
          color: foreground,
          height: 1.2,
        ),
      ),
    );
  }
}
