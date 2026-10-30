import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../widgets/ornament_divider.dart';
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
          items.isEmpty
              ? 'لا عناصر بانتظار المراجعة'
              : '${arabicDigits(items.length)} عناصر: حكم غير محسوم أو مقترح آلي',
          style: AppText.ui(size: 14, color: AppColors.muted),
        ),
        const SizedBox(height: 16),
        if (items.isEmpty)
          const _EmptyReview()
        else
          for (final stop in items) ...[
            _ReviewCard(
              stop: stop,
              sent: controller.isSent(stop.id),
              onTap: () => showWaqfSheet(context, controller, stop.id),
            ),
            const SizedBox(height: 12),
          ],
      ],
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
            'لا عناصر بانتظار المراجعة.',
            textAlign: TextAlign.center,
            style: AppText.ui(size: 16, color: AppColors.forestDeep),
          ),
          const SizedBox(height: 8),
          Text(
            'تظهر هنا الوقوف بلا حكم، أو التي فيها مقترح آلي.',
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
    required this.sent,
    required this.onTap,
  });

  final WaqfStop stop;
  final bool sent;
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
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.hairline),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  StopBadge(
                    symbol: stop.symbol,
                    semanticsLabel: '${stop.label} ${stop.word}',
                    core: 28,
                  ),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          stop.word,
                          style: AppText.quran(
                            size: 26,
                            color: AppColors.ink,
                            height: 1.2,
                          ),
                        ),
                        Text(
                          'يوسف ${arabicDigits(stop.ayah)} · ${stop.label}',
                          style: AppText.ui(size: 13, color: AppColors.muted),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                stop.reason,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: AppText.ui(size: 13, color: AppColors.ink, height: 1.5),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if (stop.symbol == StopSymbol.unsettled || stop.hasNullVerdict)
                    const _Tag(label: 'غير محسوم', amber: true),
                  if (stop.hasAiSuggestion)
                    const _Tag(label: 'مقترح AI', amber: false),
                  if (sent) const _Tag(label: 'أُرسلت للمراجعة', amber: false),
                ],
              ),
            ],
          ),
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
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: fill,
        borderRadius: BorderRadius.circular(20),
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
