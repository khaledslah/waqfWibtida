import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../widgets/ayah_options_sheet.dart';
import '../widgets/ornament_divider.dart';
import '../widgets/stop_badge.dart';
import '../widgets/waqf_bottom_sheet.dart';
import '../widgets/waqf_filter_bar.dart';

class MushafScreen extends StatelessWidget {
  const MushafScreen({super.key, required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        WaqfFilterBar(controller: controller),
        const OrnamentDivider(),
        Expanded(
          child: controller.currentAyahs.isEmpty
              ? const _EmptyReading()
              : SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                  child: _ReadingBlock(controller: controller),
                ),
        ),
        const Padding(
          padding: EdgeInsets.only(bottom: 4),
          child: OrnamentDivider(),
        ),
      ],
    );
  }
}

class _EmptyReading extends StatelessWidget {
  const _EmptyReading();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(
          'لا نص للعرض في هذه السورة.',
          textAlign: TextAlign.center,
          style: AppText.ui(size: 16, color: AppColors.forestDeep),
        ),
      ),
    );
  }
}

class _ReadingBlock extends StatelessWidget {
  const _ReadingBlock({required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[];
    for (final ayah in controller.currentAyahs) {
      for (final word in ayah.words) {
        children.add(
          _WordToken(
            word: word,
            ayah: ayah,
            controller: controller,
          ),
        );
      }
      children.add(_AyahMark(ayah: ayah, controller: controller));
    }

    return Wrap(
      textDirection: TextDirection.rtl,
      alignment: WrapAlignment.center,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 2,
      runSpacing: 14,
      children: children,
    );
  }
}

class _WordToken extends StatelessWidget {
  const _WordToken({
    required this.word,
    required this.ayah,
    required this.controller,
  });

  final AyahWord word;
  final Ayah ayah;
  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final stopId = word.stopId;
    final stop = stopId == null ? null : controller.stopById(stopId);
    final visibleStop =
        (stop != null && controller.isStopVisible(stop)) ? stop : null;
    final selected =
        visibleStop != null && controller.selectedStopId == visibleStop.id;
    final activeScholar = controller.selectedScholar;
    final text = Text(
      word.text,
      textDirection: TextDirection.rtl,
      style: AppText.quran(
        size: controller.quranSize,
        color: AppColors.ink,
        height: 1.35,
      ),
    );

    return Row(
      mainAxisSize: MainAxisSize.min,
      textDirection: TextDirection.rtl,
      children: [
        GestureDetector(
          behavior: HitTestBehavior.opaque,
          onLongPress: () => showAyahOptionsSheet(context, controller, ayah),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: selected ? AppColors.wordGlow : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 1),
              child: text,
            ),
          ),
        ),
        if (visibleStop != null)
          StopBadge(
            key: ValueKey<String>(
              'stop-${visibleStop.id}-${activeScholar ?? "all"}',
            ),
            symbol: visibleStop.symbolForScholar(activeScholar),
            verdictLabel: visibleStop.verdictLabelForScholar(activeScholar),
            isQila: visibleStop.isQilaForScholar(activeScholar),
            selected: selected,
            semanticsLabel:
                'وقف ${visibleStop.labelForScholar(activeScholar)} عند ${visibleStop.word}',
            onTap: () {
              controller.select(visibleStop.id);
              showWaqfSheet(context, controller, visibleStop.id);
            },
          ),
      ],
    );
  }
}

class _AyahMark extends StatelessWidget {
  const _AyahMark({required this.ayah, required this.controller});

  final Ayah ayah;
  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'خيارات الآية ${arabicDigits(ayah.number)}',
      child: InkWell(
        onTap: () => showAyahOptionsSheet(context, controller, ayah),
        onLongPress: () => showAyahOptionsSheet(context, controller, ayah),
        borderRadius: BorderRadius.circular(11),
        child: Container(
          constraints: const BoxConstraints(minWidth: 28, minHeight: 22),
          margin: const EdgeInsets.symmetric(horizontal: 3),
          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(11),
            border: Border.all(color: AppColors.gold),
          ),
          child: Text(
            arabicDigits(ayah.number),
            style: AppText.ui(
              size: 10,
              weight: FontWeight.w700,
              color: AppColors.gold,
              height: 1.1,
            ),
          ),
        ),
      ),
    );
  }
}
